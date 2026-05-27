"""即时交易（面对面）管理器。

职责：
- 创建/获取/取消/确认交易
- 物品/灵石的托管与返还
- 双方都确认后的原子结算

数据模型: trades 表（v21 schema）。
"""
from __future__ import annotations
import time
import json
from typing import Any, Optional


__all__ = ["TradeManager"]


class TradeManager:
    """即时交易业务逻辑。

    构造函数接受 aiosqlite.Connection（测试用）或 DataBase 包装器（运行时用）。
    如果传入 DataBase，每次访问 conn 时都会动态获取当前 self.db.conn，
    避免持有过期连接的问题。

    运行时（DataBase 模式）：accept_trade / settle / cancel / expire 会通过
    db.ext.set_user_busy / set_user_free 同步更新 user_cd 状态，把双方设为
    UserStatus.TRADING，让历练/闭关/秘境等系统能识别为忙碌中。
    测试时（裸 conn 模式）不调用 user_cd，因为测试 fixture 没有 user_cd 表。
    """

    # UserStatus.TRADING 数值（避免循环引用 models_extended，但要保持一致）
    _STATUS_TRADING = 5
    _STATUS_IDLE = 0

    def __init__(self, conn_or_db, config: Optional[dict] = None):
        # 兼容 aiosqlite.Connection（测试用）和 DataBase（运行时用）
        # 如果是 DataBase，conn 在每次调用时动态获取
        self._conn_or_db = conn_or_db
        cfg = config or {}
        self.default_duration_seconds = int(cfg.get("TRADE_TIMEOUT_SECONDS", 1800))

    @property
    def conn(self):
        """运行时返回最新的连接，避免缓存过期 Connection。"""
        if hasattr(self._conn_or_db, "conn"):
            return self._conn_or_db.conn
        return self._conn_or_db

    @property
    def _db(self):
        """返回 DataBase 实例（如果可用），否则 None。"""
        if hasattr(self._conn_or_db, "ext"):
            return self._conn_or_db
        return None

    async def _mark_trading(self, user_id: str, trade_id: int) -> None:
        """把玩家标记为 TRADING 状态。仅在 DataBase 模式下生效。
        测试模式（裸 conn）下为 no-op。失败时静默忽略，避免阻塞交易流程。
        """
        db = self._db
        if db is None:
            return
        try:
            await db.ext.set_user_busy(
                user_id, self._STATUS_TRADING, 0, extra_data={"trade_id": trade_id}
            )
        except Exception:
            # user_cd 表不存在或行不存在时，跳过；不阻塞交易主流程
            pass

    async def _mark_idle(self, user_id: str) -> None:
        """把玩家标记为 IDLE 状态。仅在 DataBase 模式下生效。"""
        db = self._db
        if db is None:
            return
        try:
            await db.ext.set_user_free(user_id)
        except Exception:
            pass

    async def create_trade(self, player_a: str, player_b: str,
                            duration_seconds: Optional[int] = None) -> int:
        """发起一笔交易（初始状态 pending，待 player_b 接受后才转为 trading）。
        任一方已有 pending 或 trading 交易则抛出 ValueError。
        duration_seconds 为 None 时使用 self.default_duration_seconds（来自配置）。
        """
        if player_a == player_b:
            raise ValueError("不能与自己交易")
        if duration_seconds is None:
            duration_seconds = self.default_duration_seconds
        # 检查双方都不在 pending/trading 状态
        async with self.conn.execute(
            "SELECT trade_id FROM trades WHERE status IN ('pending', 'trading') AND "
            "(player_a=? OR player_b=? OR player_a=? OR player_b=?)",
            (player_a, player_a, player_b, player_b),
        ) as cur:
            row = await cur.fetchone()
        if row:
            raise ValueError("已在交易中，请先结束当前交易")

        now = int(time.time())
        expires = now + duration_seconds
        cur = await self.conn.execute(
            "INSERT INTO trades (player_a, player_b, created_at, expires_at, status) "
            "VALUES (?, ?, ?, ?, 'pending')",
            (player_a, player_b, now, expires),
        )
        await self.conn.commit()
        return cur.lastrowid

    async def accept_trade(self, trade_id: int, user_id: str) -> dict:
        """接收方接受 pending 交易，转为 trading。仅 player_b 可调用。"""
        async with self.conn.execute(
            "SELECT * FROM trades WHERE trade_id=? AND status='pending'", (trade_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            raise ValueError("交易不存在或已被处理")
        trade = dict(row)
        if trade["player_b"] != user_id:
            raise ValueError("只有交易接收方可以接受交易")
        await self.conn.execute(
            "UPDATE trades SET status='trading' WHERE trade_id=?", (trade_id,)
        )
        await self.conn.commit()
        trade["status"] = "trading"
        # 同步更新 user_cd 状态（DataBase 模式下）
        await self._mark_trading(trade["player_a"], trade_id)
        await self._mark_trading(trade["player_b"], trade_id)
        return trade

    async def reject_trade(self, trade_id: int, user_id: str) -> None:
        """接收方拒绝 pending 交易，转为 cancelled。"""
        async with self.conn.execute(
            "SELECT * FROM trades WHERE trade_id=? AND status='pending'", (trade_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            raise ValueError("交易不存在或已被处理")
        trade = dict(row)
        if trade["player_b"] != user_id:
            raise ValueError("只有交易接收方可以拒绝交易")
        await self.conn.execute(
            "UPDATE trades SET status='cancelled' WHERE trade_id=?", (trade_id,)
        )
        await self.conn.commit()

    async def get_active_trade(self, user_id: str) -> Optional[dict]:
        """返回该玩家正在进行的交易（pending 或 trading 都算）。"""
        async with self.conn.execute(
            "SELECT * FROM trades WHERE status IN ('pending', 'trading') AND (player_a=? OR player_b=?)",
            (user_id, user_id),
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    # ---------- 内部辅助 ----------

    async def _get_trade_or_raise(self, trade_id: int, user_id: str) -> dict:
        async with self.conn.execute(
            "SELECT * FROM trades WHERE trade_id=? AND status='trading'", (trade_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            raise ValueError("交易不存在或已结束")
        if user_id not in (row["player_a"], row["player_b"]):
            raise ValueError("非交易参与者")
        return dict(row)

    def _which_side(self, trade: dict, user_id: str) -> str:
        return "a" if trade["player_a"] == user_id else "b"

    async def _set_confirmation_dirty(self, trade_id: int) -> None:
        """任何添加/移除操作都会清空双方确认（强制重新确认）"""
        await self.conn.execute(
            "UPDATE trades SET a_confirmed=0, b_confirmed=0 WHERE trade_id=?",
            (trade_id,),
        )

    # ---------- 灵石托管 ----------

    async def add_stones(self, trade_id: int, user_id: str, amount: int) -> None:
        if amount <= 0:
            raise ValueError("数量必须为正整数")
        await self.conn.execute("BEGIN IMMEDIATE")
        try:
            trade = await self._get_trade_or_raise(trade_id, user_id)
            side = self._which_side(trade, user_id)
            async with self.conn.execute(
                "SELECT gold FROM players WHERE user_id=?", (user_id,)
            ) as cur:
                row = await cur.fetchone()
            if not row or row[0] < amount:
                raise ValueError("灵石不足")
            await self.conn.execute(
                "UPDATE players SET gold = gold - ? WHERE user_id=?",
                (amount, user_id),
            )
            await self.conn.execute(
                f"UPDATE trades SET player_{side}_stones = player_{side}_stones + ? "
                "WHERE trade_id=?",
                (amount, trade_id),
            )
            await self._set_confirmation_dirty(trade_id)
            await self.conn.commit()
        except Exception:
            await self.conn.rollback()
            raise

    async def remove_stones(self, trade_id: int, user_id: str, amount: int) -> None:
        if amount <= 0:
            raise ValueError("数量必须为正整数")
        await self.conn.execute("BEGIN IMMEDIATE")
        try:
            trade = await self._get_trade_or_raise(trade_id, user_id)
            side = self._which_side(trade, user_id)
            current = trade[f"player_{side}_stones"]
            if current < amount:
                raise ValueError("托管灵石不足")
            await self.conn.execute(
                f"UPDATE trades SET player_{side}_stones = player_{side}_stones - ? "
                "WHERE trade_id=?",
                (amount, trade_id),
            )
            await self.conn.execute(
                "UPDATE players SET gold = gold + ? WHERE user_id=?",
                (amount, user_id),
            )
            await self._set_confirmation_dirty(trade_id)
            await self.conn.commit()
        except Exception:
            await self.conn.rollback()
            raise

    # ---------- 物品托管 ----------

    async def _find_item_source(self, user_id: str, item_name: str) -> tuple[str, dict] | tuple[None, None]:
        """返回 (source, current_inventory_dict)；source ∈ {'ring', 'pill'}"""
        async with self.conn.execute(
            "SELECT storage_ring_items, pills_inventory FROM players WHERE user_id=?",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None, None
        ring = json.loads(row[0] or "{}")
        if item_name in ring:
            return "ring", ring
        pills = json.loads(row[1] or "{}")
        if item_name in pills:
            return "pill", pills
        return None, None

    async def _save_inventory(self, user_id: str, source: str, inv: dict) -> None:
        col = "storage_ring_items" if source == "ring" else "pills_inventory"
        await self.conn.execute(
            f"UPDATE players SET {col}=? WHERE user_id=?",
            (json.dumps(inv, ensure_ascii=False), user_id),
        )

    async def add_item(self, trade_id: int, user_id: str, item_name: str, count: int = 1) -> None:
        if count <= 0:
            raise ValueError("数量必须为正整数")
        await self.conn.execute("BEGIN IMMEDIATE")
        try:
            trade = await self._get_trade_or_raise(trade_id, user_id)
            side = self._which_side(trade, user_id)

            source, inv = await self._find_item_source(user_id, item_name)
            if source is None:
                raise ValueError(f"背包中没有【{item_name}】")
            if inv.get(item_name, 0) < count:
                raise ValueError(f"【{item_name}】数量不足")
            inv[item_name] -= count
            if inv[item_name] == 0:
                del inv[item_name]
            await self._save_inventory(user_id, source, inv)

            items_col = f"player_{side}_items"
            escrow = json.loads(trade[items_col] or "[]")
            # 查找已存在条目合并
            for e in escrow:
                if e["name"] == item_name:
                    e["count"] += count
                    break
            else:
                escrow.append({"name": item_name, "count": count, "source": source})
            await self.conn.execute(
                f"UPDATE trades SET {items_col}=? WHERE trade_id=?",
                (json.dumps(escrow, ensure_ascii=False), trade_id),
            )
            await self._set_confirmation_dirty(trade_id)
            await self.conn.commit()
        except Exception:
            await self.conn.rollback()
            raise

    async def remove_item(self, trade_id: int, user_id: str, item_name: str, count: Optional[int] = None) -> None:
        """count 为 None 时移除全部"""
        await self.conn.execute("BEGIN IMMEDIATE")
        try:
            trade = await self._get_trade_or_raise(trade_id, user_id)
            side = self._which_side(trade, user_id)
            items_col = f"player_{side}_items"

            escrow = json.loads(trade[items_col] or "[]")
            target = next((e for e in escrow if e["name"] == item_name), None)
            if not target:
                raise ValueError(f"交易中未放入【{item_name}】")
            remove_n = target["count"] if count is None else count
            if remove_n > target["count"]:
                raise ValueError("移除数量超过托管数量")
            target["count"] -= remove_n
            escrow = [e for e in escrow if e["count"] > 0]
            await self.conn.execute(
                f"UPDATE trades SET {items_col}=? WHERE trade_id=?",
                (json.dumps(escrow, ensure_ascii=False), trade_id),
            )

            # 返还到玩家原来的库存
            source = target.get("source", "ring")
            await self._return_to_inventory(user_id, item_name, remove_n, source)

            await self._set_confirmation_dirty(trade_id)
            await self.conn.commit()
        except Exception:
            await self.conn.rollback()
            raise

    async def _return_to_inventory(self, user_id: str, item_name: str, count: int, source: str) -> None:
        col = "storage_ring_items" if source == "ring" else "pills_inventory"
        async with self.conn.execute(
            f"SELECT {col} FROM players WHERE user_id=?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return
        inv = json.loads(row[0] or "{}")
        inv[item_name] = inv.get(item_name, 0) + count
        await self.conn.execute(
            f"UPDATE players SET {col}=? WHERE user_id=?",
            (json.dumps(inv, ensure_ascii=False), user_id),
        )

    # ---------- 确认与结算 ----------

    async def confirm(self, trade_id: int, user_id: str) -> bool:
        """玩家确认交易。返回 True 表示交易已最终结算。"""
        await self.conn.execute("BEGIN IMMEDIATE")
        try:
            trade = await self._get_trade_or_raise(trade_id, user_id)
            side = self._which_side(trade, user_id)
            col = f"{side}_confirmed"
            await self.conn.execute(
                f"UPDATE trades SET {col}=1 WHERE trade_id=?", (trade_id,)
            )
            # 重新查
            async with self.conn.execute(
                "SELECT * FROM trades WHERE trade_id=?", (trade_id,)
            ) as cur:
                trade = dict(await cur.fetchone())
            if trade["a_confirmed"] == 1 and trade["b_confirmed"] == 1:
                await self._settle(trade)
                await self.conn.commit()
                return True
            await self.conn.commit()
            return False
        except Exception:
            await self.conn.rollback()
            raise

    async def _settle(self, trade: dict) -> None:
        """在事务内执行结算：双向转移托管的物品和灵石。"""
        a, b = trade["player_a"], trade["player_b"]
        a_items = json.loads(trade["player_a_items"] or "[]")
        b_items = json.loads(trade["player_b_items"] or "[]")
        a_stones = trade["player_a_stones"]
        b_stones = trade["player_b_stones"]

        # 灵石：a 给 b，b 给 a
        await self.conn.execute(
            "UPDATE players SET gold = gold + ? WHERE user_id=?", (b_stones, a)
        )
        await self.conn.execute(
            "UPDATE players SET gold = gold + ? WHERE user_id=?", (a_stones, b)
        )

        # 物品：a 给 b，b 给 a
        await self._add_items_to_player(b, a_items)
        await self._add_items_to_player(a, b_items)

        await self.conn.execute(
            "UPDATE trades SET status='completed' WHERE trade_id=?",
            (trade["trade_id"],),
        )
        # 清理双方的 TRADING 状态
        await self._mark_idle(a)
        await self._mark_idle(b)

    async def _add_items_to_player(self, user_id: str, items: list[dict]) -> None:
        """把交易托管的物品转入接收方背包。
        接收方的物品按 source 字段进入对应库存（ring/pill），缺省视为 ring。
        """
        if not items:
            return
        async with self.conn.execute(
            "SELECT storage_ring_items, pills_inventory FROM players WHERE user_id=?",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return
        ring = json.loads(row[0] or "{}")
        pills = json.loads(row[1] or "{}")
        for item in items:
            target = pills if item.get("source") == "pill" else ring
            target[item["name"]] = target.get(item["name"], 0) + item["count"]
        await self.conn.execute(
            "UPDATE players SET storage_ring_items=?, pills_inventory=? WHERE user_id=?",
            (json.dumps(ring, ensure_ascii=False), json.dumps(pills, ensure_ascii=False), user_id),
        )

    # ---------- 取消 / 过期 ----------

    async def cancel(self, trade_id: int, user_id: str) -> None:
        """取消交易。可在 pending 或 trading 状态下调用：
        - pending：发起方可撤回；接收方可拒绝（也走此函数）。
        - trading：任一方可主动结束。
        无托管物品/灵石的 pending 状态退款是零，但流程相同。
        """
        await self.conn.execute("BEGIN IMMEDIATE")
        try:
            async with self.conn.execute(
                "SELECT * FROM trades WHERE trade_id=? AND status IN ('pending', 'trading')",
                (trade_id,),
            ) as cur:
                row = await cur.fetchone()
            if not row:
                raise ValueError("交易不存在或已结束")
            if user_id not in (row["player_a"], row["player_b"]):
                raise ValueError("非交易参与者")
            trade = dict(row)
            was_trading = trade["status"] == "trading"
            await self._refund_escrow(trade)
            await self.conn.execute(
                "UPDATE trades SET status='cancelled' WHERE trade_id=?",
                (trade_id,),
            )
            await self.conn.commit()
        except Exception:
            await self.conn.rollback()
            raise
        # 事务外清理 TRADING 状态（仅当之前是 trading 才需要清理）
        if was_trading:
            await self._mark_idle(trade["player_a"])
            await self._mark_idle(trade["player_b"])

    async def expire_overdue_trades(self) -> int:
        """供后台调用：把所有 expires_at < now 的 pending/trading 交易自动取消。返回数量。"""
        now = int(time.time())
        async with self.conn.execute(
            "SELECT * FROM trades WHERE status IN ('pending', 'trading') AND expires_at < ?",
            (now,),
        ) as cur:
            rows = [dict(r) for r in await cur.fetchall()]
        for trade in rows:
            await self.conn.execute("BEGIN IMMEDIATE")
            try:
                await self._refund_escrow(trade)
                await self.conn.execute(
                    "UPDATE trades SET status='expired' WHERE trade_id=?",
                    (trade["trade_id"],),
                )
                await self.conn.commit()
            except Exception:
                await self.conn.rollback()
                continue
            # 事务外清理双方 TRADING 状态
            await self._mark_idle(trade["player_a"])
            await self._mark_idle(trade["player_b"])
        return len(rows)

    async def _refund_escrow(self, trade: dict) -> None:
        a, b = trade["player_a"], trade["player_b"]
        await self.conn.execute(
            "UPDATE players SET gold = gold + ? WHERE user_id=?",
            (trade["player_a_stones"], a),
        )
        await self.conn.execute(
            "UPDATE players SET gold = gold + ? WHERE user_id=?",
            (trade["player_b_stones"], b),
        )
        await self._add_items_to_player(a, json.loads(trade["player_a_items"] or "[]"))
        await self._add_items_to_player(b, json.loads(trade["player_b_items"] or "[]"))
