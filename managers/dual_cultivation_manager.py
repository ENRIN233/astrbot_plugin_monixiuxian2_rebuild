# managers/dual_cultivation_manager.py
"""双修系统管理器"""
import time
import json
from datetime import datetime, timezone
from typing import Tuple, Optional, Dict
from ..data import DataBase
from ..models import Player
from ..models_extended import UserStatus

__all__ = ["DualCultivationManager"]

# 双修配置
DUAL_CULT_MAX_PER_DAY = 3  # 每日双修上限
DUAL_CULT_EXP_BONUS = 0.01  # 双方修为之和的1%
DUAL_CULT_REQUEST_EXPIRE = 300  # 请求过期时间（5分钟）
DUAL_CULT_MAX_EXP_RATIO = 3.0  # 双修双方修为差距最大3倍


class DualCultivationManager:
    """双修管理器"""

    def __init__(self, db: DataBase, pill_manager=None):
        self.db = db
        self.pill_manager = pill_manager

    async def _create_request(self, from_id: str, from_name: str, target_id: str) -> int:
        """创建双修请求（持久化到数据库）"""
        now = int(time.time())
        expires_at = now + DUAL_CULT_REQUEST_EXPIRE

        # 先清理该目标的旧请求
        await self.db.conn.execute(
            "DELETE FROM dual_cultivation_requests WHERE target_id = ?",
            (target_id,)
        )

        await self.db.conn.execute(
            """
            INSERT INTO dual_cultivation_requests (from_id, from_name, target_id, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (from_id, from_name, target_id, now, expires_at)
        )
        await self.db.conn.commit()

        async with self.db.conn.execute("SELECT last_insert_rowid()") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def _get_pending_request(self, target_id: str) -> Optional[Dict]:
        """获取待处理的双修请求"""
        now = int(time.time())

        # 清理过期请求
        await self.db.conn.execute(
            "DELETE FROM dual_cultivation_requests WHERE expires_at < ?",
            (now,)
        )
        await self.db.conn.commit()

        async with self.db.conn.execute(
            """
            SELECT id, from_id, from_name, target_id, created_at, expires_at
            FROM dual_cultivation_requests
            WHERE target_id = ? AND expires_at > ?
            ORDER BY created_at DESC LIMIT 1
            """,
            (target_id, now)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "from_id": row[1],
                    "from_name": row[2],
                    "target_id": row[3],
                    "created_at": row[4],
                    "expires_at": row[5]
                }
            return None

    async def _delete_request(self, request_id: int):
        """删除双修请求"""
        await self.db.conn.execute(
            "DELETE FROM dual_cultivation_requests WHERE id = ?",
            (request_id,)
        )
        await self.db.conn.commit()

    async def send_request(self, initiator: Player, target_id: str) -> Tuple[bool, str]:
        """发起双修请求"""
        if initiator.user_id == target_id:
            return False, "❌ 不能与自己双修。"

        # 检查发起者状态（状态互斥）
        user_cd = await self.db.ext.get_user_cd(initiator.user_id)
        if user_cd and user_cd.type != UserStatus.IDLE:
            current_status = UserStatus.get_name(user_cd.type)
            return False, f"❌ 你当前正{current_status}，无法发起双修！"

        # 检查目标是否存在
        target = await self.db.get_player_by_id(target_id)
        if not target:
            return False, "❌ 对方还未踏入修仙之路。"

        # 检查修为差距
        exp_ratio = max(initiator.experience, target.experience) / max(min(initiator.experience, target.experience), 1)
        if exp_ratio > DUAL_CULT_MAX_EXP_RATIO:
            return False, f"❌ 双方修为差距过大（最大{DUAL_CULT_MAX_EXP_RATIO}倍），无法双修。"

        # 检查目标状态
        target_cd = await self.db.ext.get_user_cd(target_id)
        if target_cd and target_cd.type != UserStatus.IDLE:
            return False, "❌ 对方正忙，无法接受双修请求。"

        # 检查发起者每日次数
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        initiator_count = await self._get_daily_count(initiator.user_id, today)
        initiator_bonus = await self.pill_manager.get_dual_cultivation_bonus(initiator) if self.pill_manager else 0
        max_initiator = DUAL_CULT_MAX_PER_DAY + (1 if initiator_bonus > 0 else 0)
        if initiator_count >= max_initiator:
            return False, f"❌ 今日双修次数已达上限（{max_initiator}次）。"

        # 检查目标每日次数
        target_count = await self._get_daily_count(target_id, today)
        target_bonus = await self.pill_manager.get_dual_cultivation_bonus(target) if self.pill_manager else 0
        max_target = DUAL_CULT_MAX_PER_DAY + (1 if target_bonus > 0 else 0)
        if target_count >= max_target:
            return False, "❌ 对方今日双修次数已达上限。"

        # 发起请求（持久化到数据库）
        await self._create_request(
            initiator.user_id,
            initiator.user_name or initiator.user_id[:8],
            target_id
        )

        return True, (
            f"💕 已向【{target.user_name or target_id[:8]}】发起双修请求！\n"
            f"对方使用 /接受双修 或 /拒绝双修 响应。\n"
            f"请求将在5分钟后过期。"
        )

    async def accept_request(self, acceptor: Player) -> Tuple[bool, str]:
        """接受双修请求"""
        request = await self._get_pending_request(acceptor.user_id)
        if not request:
            return False, "❌ 没有待处理的双修请求。"

        initiator = await self.db.get_player_by_id(request["from_id"])
        if not initiator:
            await self._delete_request(request["id"])
            return False, "❌ 请求发起者数据异常。"

        # 再次检查修为差距
        exp_ratio = max(initiator.experience, acceptor.experience) / max(min(initiator.experience, acceptor.experience), 1)
        if exp_ratio > DUAL_CULT_MAX_EXP_RATIO:
            await self._delete_request(request["id"])
            return False, "❌ 双方修为差距已超过限制，双修取消。"

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # 再次检查双方每日次数（防止请求期间次数已用完）
        acceptor_count = await self._get_daily_count(acceptor.user_id, today)
        acceptor_bonus = await self.pill_manager.get_dual_cultivation_bonus(acceptor) if self.pill_manager else 0
        max_acceptor = DUAL_CULT_MAX_PER_DAY + (1 if acceptor_bonus > 0 else 0)
        if acceptor_count >= max_acceptor:
            await self._delete_request(request["id"])
            return False, f"❌ 你的今日双修次数已达上限（{max_acceptor}次）。"

        initiator_count = await self._get_daily_count(initiator.user_id, today)
        initiator_bonus = await self.pill_manager.get_dual_cultivation_bonus(initiator) if self.pill_manager else 0
        max_initiator = DUAL_CULT_MAX_PER_DAY + (1 if initiator_bonus > 0 else 0)
        if initiator_count >= max_initiator:
            await self._delete_request(request["id"])
            return False, "❌ 对方今日双修次数已达上限。"

        # 计算双修收益：双方获得双方修为之和的百分比（丹药加成：任一方使用即翻倍，不叠加）
        exp_mult = 2.0 if max(initiator_bonus, acceptor_bonus) > 0 else 1.0
        total_exp = initiator.experience + acceptor.experience
        gain = int(total_exp * DUAL_CULT_EXP_BONUS * exp_mult)

        # 应用收益（双方获得相同修为）
        initiator.experience += gain
        acceptor.experience += gain
        await self.db.update_player(initiator)
        await self.db.update_player(acceptor)

        # 记录每日次数
        await self._increment_daily_count(initiator.user_id, today)
        await self._increment_daily_count(acceptor.user_id, today)

        # 消费双修丹药效果
        if self.pill_manager:
            if initiator_bonus > 0:
                await self.pill_manager.consume_dual_cultivation_bonus(initiator)
            if acceptor_bonus > 0:
                await self.pill_manager.consume_dual_cultivation_bonus(acceptor)

        # 清除请求
        await self._delete_request(request["id"])

        bonus_note = ""
        if exp_mult > 1.0:
            bonus_note = f"\n🔥 龙精虎猛丹生效！修为翻倍（2%）"

        return True, (
            f"💕 双修成功！\n"
            f"━━━━━━━━━━━━━━━\n"
            f"与【{request['from_name']}】双修\n"
            f"双方修为之和：{total_exp:,}\n"
            f"各自获得修为：+{gain:,}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"今日剩余次数：{max_acceptor - acceptor_count - 1}"
            f"{bonus_note}"
        )

    async def reject_request(self, rejecter_id: str) -> Tuple[bool, str]:
        """拒绝双修请求"""
        request = await self._get_pending_request(rejecter_id)
        if not request:
            return False, "❌ 没有待处理的双修请求。"

        from_name = request["from_name"]
        await self._delete_request(request["id"])

        return True, f"已拒绝【{from_name}】的双修请求。"

    async def _get_daily_count(self, user_id: str, today: str) -> int:
        """获取用户今日双修次数"""
        async with self.db.conn.execute(
            "SELECT daily_count, daily_date FROM dual_cultivation WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return 0
            count, date = row[0], row[1]
            if date != today:
                return 0
            return count

    async def _increment_daily_count(self, user_id: str, today: str):
        """增加用户今日双修次数"""
        await self.db.conn.execute(
            """
            INSERT INTO dual_cultivation (user_id, daily_count, daily_date)
            VALUES (?, 1, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                daily_count = CASE WHEN dual_cultivation.daily_date = excluded.daily_date
                    THEN dual_cultivation.daily_count + 1
                    ELSE 1 END,
                daily_date = excluded.daily_date
            """,
            (user_id, today)
        )
        await self.db.conn.commit()
