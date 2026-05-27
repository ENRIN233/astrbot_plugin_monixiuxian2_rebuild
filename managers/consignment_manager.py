"""寄售行业务逻辑。

5% 上架手续费，不退还。
7 天后自动过期，物品退回卖家。
"""
from __future__ import annotations
import time
import json
from typing import Optional


__all__ = ["ConsignmentManager"]

LISTING_FEE_RATE = 0.05
DEFAULT_DURATION = 7 * 24 * 3600


class ConsignmentManager:
    """寄售行业务逻辑。

    构造函数接受 aiosqlite.Connection（测试用）或 DataBase 包装器（运行时用）。
    如果传入 DataBase，每次访问 conn 时都会动态获取当前 self.db.conn，
    避免持有过期连接的问题。
    """

    def __init__(self, conn_or_db, config: Optional[dict] = None):
        # 兼容 aiosqlite.Connection（测试用）和 DataBase（运行时用）
        self._conn_or_db = conn_or_db
        cfg = config or {}
        self.listing_fee_rate = float(cfg.get("CONSIGNMENT_FEE_RATE", LISTING_FEE_RATE))
        self.default_duration = int(cfg.get("CONSIGNMENT_DURATION_DAYS", 7)) * 24 * 3600

    @property
    def conn(self):
        """运行时返回最新的连接，避免缓存过期 Connection。"""
        if hasattr(self._conn_or_db, "conn"):
            return self._conn_or_db.conn
        return self._conn_or_db

    async def list_item(self, seller_id: str, item_name: str, item_id: str,
                         item_type: str, price: int, quantity: int = 1,
                         duration_seconds: Optional[int] = None) -> int:
        if price <= 0:
            raise ValueError("价格必须为正整数")
        if quantity <= 0:
            raise ValueError("数量必须为正整数")
        if duration_seconds is None:
            duration_seconds = self.default_duration
        fee = int(price * self.listing_fee_rate)

        await self.conn.execute("BEGIN IMMEDIATE")
        try:
            async with self.conn.execute(
                "SELECT gold, storage_ring_items, pills_inventory FROM players WHERE user_id=?",
                (seller_id,)
            ) as cur:
                row = await cur.fetchone()
            if not row:
                raise ValueError("玩家不存在")
            if row[0] < fee:
                raise ValueError(f"灵石不足以支付手续费（需要 {fee:,} 灵石）")
            ring = json.loads(row[1] or "{}")
            pills = json.loads(row[2] or "{}")
            if ring.get(item_name, 0) >= quantity:
                ring[item_name] -= quantity
                if ring[item_name] == 0:
                    del ring[item_name]
                source = "ring"
            elif pills.get(item_name, 0) >= quantity:
                pills[item_name] -= quantity
                if pills[item_name] == 0:
                    del pills[item_name]
                source = "pill"
            else:
                raise ValueError(f"背包中【{item_name}】不足 {quantity} 个")

            # 扣手续费 + 写回背包
            await self.conn.execute(
                "UPDATE players SET gold = gold - ?, storage_ring_items=?, pills_inventory=? WHERE user_id=?",
                (fee, json.dumps(ring, ensure_ascii=False),
                 json.dumps(pills, ensure_ascii=False), seller_id),
            )

            now = int(time.time())
            # item_type 复用作 source 提示：以 'pill_' 前缀或额外列储存。为简化：
            # 把 source 编码进 item_type 字段（pill / 其他）
            effective_type = "pill" if source == "pill" else item_type
            cur = await self.conn.execute(
                "INSERT INTO consignment_listings "
                "(seller_id, item_id, item_name, item_type, quantity, price, "
                " listed_at, expires_at, status) VALUES (?,?,?,?,?,?,?,?, 'active')",
                (seller_id, item_id, item_name, effective_type, quantity, price,
                 now, now + duration_seconds),
            )
            await self.conn.commit()
            return cur.lastrowid
        except Exception:
            await self.conn.rollback()
            raise

    async def buy_listing(self, listing_id: int, buyer_id: str) -> dict:
        await self.conn.execute("BEGIN IMMEDIATE")
        try:
            async with self.conn.execute(
                "SELECT * FROM consignment_listings WHERE listing_id=? AND status='active'",
                (listing_id,),
            ) as cur:
                row = await cur.fetchone()
            if not row:
                raise ValueError("寄售物品不存在或已售出")
            listing = dict(row)
            if listing["seller_id"] == buyer_id:
                raise ValueError("不能购买自己的寄售物品")

            async with self.conn.execute(
                "SELECT gold, storage_ring_items, pills_inventory FROM players WHERE user_id=?",
                (buyer_id,)
            ) as cur:
                buyer = await cur.fetchone()
            if not buyer:
                raise ValueError("买家不存在")
            if buyer[0] < listing["price"]:
                raise ValueError("灵石不足")

            # 扣买家灵石，加卖家灵石
            await self.conn.execute(
                "UPDATE players SET gold = gold - ? WHERE user_id=?",
                (listing["price"], buyer_id),
            )
            await self.conn.execute(
                "UPDATE players SET gold = gold + ? WHERE user_id=?",
                (listing["price"], listing["seller_id"]),
            )
            # 物品进买家对应库存
            if listing["item_type"] == "pill":
                pills = json.loads(buyer[2] or "{}")
                pills[listing["item_name"]] = pills.get(listing["item_name"], 0) + listing["quantity"]
                await self.conn.execute(
                    "UPDATE players SET pills_inventory=? WHERE user_id=?",
                    (json.dumps(pills, ensure_ascii=False), buyer_id),
                )
            else:
                ring = json.loads(buyer[1] or "{}")
                ring[listing["item_name"]] = ring.get(listing["item_name"], 0) + listing["quantity"]
                await self.conn.execute(
                    "UPDATE players SET storage_ring_items=? WHERE user_id=?",
                    (json.dumps(ring, ensure_ascii=False), buyer_id),
                )
            await self.conn.execute(
                "UPDATE consignment_listings SET status='sold', buyer_id=?, sold_at=? "
                "WHERE listing_id=?",
                (buyer_id, int(time.time()), listing_id),
            )
            await self.conn.commit()
            return listing
        except Exception:
            await self.conn.rollback()
            raise

    async def cancel_listing(self, listing_id: int, user_id: str) -> None:
        await self.conn.execute("BEGIN IMMEDIATE")
        try:
            async with self.conn.execute(
                "SELECT * FROM consignment_listings WHERE listing_id=? AND status='active'",
                (listing_id,),
            ) as cur:
                row = await cur.fetchone()
            if not row:
                raise ValueError("寄售物品不存在或已售出")
            if row["seller_id"] != user_id:
                raise ValueError("不能下架他人的寄售物品")
            listing = dict(row)
            await self._return_item(listing)
            await self.conn.execute(
                "UPDATE consignment_listings SET status='cancelled' WHERE listing_id=?",
                (listing_id,),
            )
            await self.conn.commit()
        except Exception:
            await self.conn.rollback()
            raise

    async def expire_old_listings(self) -> int:
        now = int(time.time())
        async with self.conn.execute(
            "SELECT * FROM consignment_listings WHERE status='active' AND expires_at < ?", (now,)
        ) as cur:
            rows = [dict(r) for r in await cur.fetchall()]
        for listing in rows:
            await self.conn.execute("BEGIN IMMEDIATE")
            try:
                await self._return_item(listing)
                await self.conn.execute(
                    "UPDATE consignment_listings SET status='expired' WHERE listing_id=?",
                    (listing["listing_id"],),
                )
                await self.conn.commit()
            except Exception:
                await self.conn.rollback()
        return len(rows)

    async def _return_item(self, listing: dict) -> None:
        col = "pills_inventory" if listing["item_type"] == "pill" else "storage_ring_items"
        async with self.conn.execute(
            f"SELECT {col} FROM players WHERE user_id=?", (listing["seller_id"],)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return
        inv = json.loads(row[0] or "{}")
        inv[listing["item_name"]] = inv.get(listing["item_name"], 0) + listing["quantity"]
        await self.conn.execute(
            f"UPDATE players SET {col}=? WHERE user_id=?",
            (json.dumps(inv, ensure_ascii=False), listing["seller_id"]),
        )

    async def list_active(self, offset: int = 0, limit: int = 10) -> list[dict]:
        async with self.conn.execute(
            "SELECT * FROM consignment_listings WHERE status='active' "
            "ORDER BY listed_at DESC LIMIT ? OFFSET ?", (limit, offset)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def list_my(self, seller_id: str) -> list[dict]:
        async with self.conn.execute(
            "SELECT * FROM consignment_listings WHERE seller_id=? AND status='active'",
            (seller_id,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]
