# managers/spirit_eye_manager.py
"""天地灵眼系统管理器"""
import time
import random
from typing import Tuple, Optional, Dict, List
from ..data import DataBase
from ..models import Player

__all__ = ["SpiritEyeManager"]

# 灵眼配置（cultivation_bonus 为修炼效率百分比小数）
SPIRIT_EYE_TYPES = {
    1: {"name": "下品灵眼", "cultivation_bonus": 0.15, "spawn_rate": 50},
    2: {"name": "中品灵眼", "cultivation_bonus": 0.25, "spawn_rate": 30},
    3: {"name": "上品灵眼", "cultivation_bonus": 0.35, "spawn_rate": 15},
    4: {"name": "极品灵眼", "cultivation_bonus": 0.50, "spawn_rate": 5},
}


class SpiritEyeManager:
    """天地灵眼管理器"""
    
    def __init__(self, db: DataBase):
        self.db = db
    
    async def get_user_spirit_eye(self, user_id: str) -> Optional[Dict]:
        """获取用户占据的灵眼"""
        async with self.db.conn.execute(
            "SELECT * FROM spirit_eyes WHERE owner_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    async def get_available_spirit_eyes(self) -> List[Dict]:
        """获取所有无主的灵眼"""
        async with self.db.conn.execute(
            "SELECT * FROM spirit_eyes WHERE owner_id IS NULL OR owner_id = ''"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def spawn_spirit_eye(self) -> Tuple[bool, str]:
        """生成新灵眼（定时调用）"""
        # 随机生成灵眼类型
        roll = random.randint(1, 100)
        eye_type = 1
        cumulative = 0
        for etype, config in SPIRIT_EYE_TYPES.items():
            cumulative += config["spawn_rate"]
            if roll <= cumulative:
                eye_type = etype
                break
        
        config = SPIRIT_EYE_TYPES[eye_type]

        # exp_per_hour 列复用存储修炼效率百分比整数（如 15 表示 +15%）
        bonus_pct = int(config["cultivation_bonus"] * 100)
        await self.db.conn.execute(
            """
            INSERT INTO spirit_eyes (eye_type, eye_name, exp_per_hour, spawn_time)
            VALUES (?, ?, ?, ?)
            """,
            (eye_type, config["name"], bonus_pct, int(time.time()))
        )
        await self.db.conn.commit()
        
        return True, f"天地间出现了一处【{config['name']}】！速来抢占！"
    
    async def claim_spirit_eye(self, player: Player, eye_id: int) -> Tuple[bool, str]:
        """抢占灵眼（原子操作）"""
        await self.db.conn.execute("BEGIN IMMEDIATE")
        try:
            # 检查是否已有灵眼
            existing = await self.get_user_spirit_eye(player.user_id)
            if existing:
                await self.db.conn.rollback()
                return False, f"❌ 你已占据【{existing['eye_name']}】，无法再抢占。"
            
            # 获取目标灵眼（带锁）
            async with self.db.conn.execute(
                "SELECT * FROM spirit_eyes WHERE eye_id = ?",
                (eye_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    await self.db.conn.rollback()
                    return False, "❌ 灵眼不存在。"
                eye = dict(row)
            
            # 检查是否有主
            if eye["owner_id"]:
                await self.db.conn.rollback()
                return False, f"❌ 此灵眼已被【{eye['owner_name'] or '某人'}】占据。"
            
            # 抢占
            now = int(time.time())
            await self.db.conn.execute(
                """UPDATE spirit_eyes SET owner_id = ?, owner_name = ?, claim_time = ?, last_collect_time = ?
                   WHERE eye_id = ? AND (owner_id IS NULL OR owner_id = '')""",
                (player.user_id, player.user_name or player.user_id[:8], now, now, eye_id)
            )
            
            # 检查是否真的抢占成功（防止并发）
            if self.db.conn.total_changes == 0:
                await self.db.conn.rollback()
                return False, "❌ 抢占失败，灵眼已被他人占据。"
            
            await self.db.conn.commit()
            bonus_pct = eye.get("exp_per_hour", 15)
            return True, (
                f"✨ 成功抢占【{eye['eye_name']}】！\n"
                f"闭关修炼效率 +{bonus_pct}%！\n"
                f"闭关时自动生效"
            )
        except Exception as e:
            await self.db.conn.rollback()
            raise
    
    async def release_spirit_eye(self, user_id: str) -> Tuple[bool, str]:
        """释放灵眼"""
        eye = await self.get_user_spirit_eye(user_id)
        if not eye:
            return False, "❌ 你没有占据灵眼。"
        
        await self.db.conn.execute(
            """
            UPDATE spirit_eyes SET owner_id = NULL, owner_name = NULL, claim_time = NULL
            WHERE owner_id = ?
            """,
            (user_id,)
        )
        await self.db.conn.commit()
        
        return True, f"已释放【{eye['eye_name']}】。"
    
    async def get_spirit_eye_info(self, user_id: str) -> str:
        """获取灵眼信息"""
        my_eye = await self.get_user_spirit_eye(user_id)
        available = await self.get_available_spirit_eyes()

        lines = ["👁️ 天地灵眼", "━━━━━━━━━━━━━━━"]

        if my_eye:
            bonus_pct = my_eye.get("exp_per_hour", 15)
            lines.append(f"【我的灵眼】{my_eye['eye_name']}")
            lines.append(f"修炼效率：+{bonus_pct}%")
            lines.append("闭关时自动生效")
            lines.append("")

        if available:
            lines.append("【可抢占的灵眼】")
            for eye in available[:5]:
                bonus = eye.get("exp_per_hour", 15)
                lines.append(f"  [{eye['eye_id']}] {eye['eye_name']} (+{bonus}%)")
            lines.append("")
            lines.append("💡 /抢占灵眼 <ID>")
        else:
            lines.append("当前没有无主灵眼。")

        return "\n".join(lines)
