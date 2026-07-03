# managers/blessed_land_manager.py
"""洞天福地系统管理器"""
import time
import json
from typing import Tuple, Optional, Dict
from ..data import DataBase
from ..models import Player

__all__ = ["BlessedLandManager"]

# 洞天配置
BLESSED_LANDS = {
    1: {"name": "小洞天", "price": 10000, "exp_bonus": 0.05, "max_level": 5},
    2: {"name": "中洞天", "price": 50000, "exp_bonus": 0.10, "max_level": 10},
    3: {"name": "大洞天", "price": 200000, "exp_bonus": 0.20, "max_level": 15},
    4: {"name": "福地", "price": 500000, "exp_bonus": 0.30, "max_level": 20},
    5: {"name": "洞天福地", "price": 1000000, "exp_bonus": 0.50, "max_level": 30},
}


class BlessedLandManager:
    """洞天福地管理器"""

    def __init__(self, db: DataBase):
        self.db = db

    async def get_user_blessed_land(self, user_id: str, land_type: int = 0) -> Optional[Dict]:
        """获取用户洞天信息（指定类型或全部）"""
        if land_type > 0:
            async with self.db.conn.execute(
                "SELECT * FROM blessed_lands WHERE user_id = ? AND land_type = ?",
                (user_id, land_type)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
        else:
            async with self.db.conn.execute(
                "SELECT * FROM blessed_lands WHERE user_id = ? ORDER BY land_type",
                (user_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows] if rows else []

    async def purchase_blessed_land(self, player: Player, land_type: int) -> Tuple[bool, str]:
        """购买洞天（每种各一个）"""
        if land_type not in BLESSED_LANDS:
            return False, "❌ 无效的洞天类型。可选：1-小洞天 2-中洞天 3-大洞天 4-福地 5-洞天福地"

        # 检查是否已有该类型洞天
        existing = await self.get_user_blessed_land(player.user_id, land_type)
        if existing:
            return False, f"❌ 你已拥有【{existing['land_name']}】，请使用 /升级洞天 {land_type} 来升级。"

        land_config = BLESSED_LANDS[land_type]
        price = land_config["price"]

        if player.gold < price:
            return False, f"❌ 灵石不足！购买{land_config['name']}需要 {price:,} 灵石。"

        # 扣除灵石
        player.gold -= price
        await self.db.update_player(player)

        # 创建洞天
        await self.db.conn.execute(
            """
            INSERT INTO blessed_lands (user_id, land_type, land_name, level, exp_bonus,
                                       gold_per_hour, last_collect_time)
            VALUES (?, ?, ?, 1, ?, 0, ?)
            """,
            (player.user_id, land_type, land_config["name"], land_config["exp_bonus"],
             int(time.time()))
        )
        await self.db.conn.commit()

        return True, (
            f"✨ 恭喜获得【{land_config['name']}】！\n"
            f"━━━━━━━━━━━━━━━\n"
            f"修炼加成：+{land_config['exp_bonus']:.0%}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"闭关修炼时自动生效"
        )

    async def upgrade_blessed_land(self, player: Player, land_type: int = 0) -> Tuple[bool, str]:
        """升级洞天（指定类型）"""
        if land_type <= 0:
            # 显示可升级的洞天列表
            all_lands = await self.get_user_blessed_land(player.user_id)
            if not all_lands:
                return False, "❌ 你还没有洞天！使用 /购买洞天 <类型> 获取。"
            lines = ["🏔️ 请选择要升级的洞天：", "━━━━━━━━━━━━━━━"]
            for land in all_lands:
                config = BLESSED_LANDS.get(land["land_type"], BLESSED_LANDS[1])
                if land["level"] < config["max_level"]:
                    cost = int(config["price"] * land["level"] * 0.5)
                    lines.append(f"  {land['land_type']}. {land['land_name']} Lv.{land['level']} → 升级需 {cost:,} 灵石")
                else:
                    lines.append(f"  {land['land_type']}. {land['land_name']} Lv.{land['level']} (已满级)")
            lines.append("━━━━━━━━━━━━━━━")
            lines.append("💡 使用 /升级洞天 <编号>")
            return False, "\n".join(lines)

        land = await self.get_user_blessed_land(player.user_id, land_type)
        if not land:
            return False, f"❌ 你还没有{BLESSED_LANDS.get(land_type, {}).get('name', '该类型')}！请先购买。"

        config = BLESSED_LANDS.get(land_type, BLESSED_LANDS[1])
        current_level = land["level"]

        if current_level >= config["max_level"]:
            return False, f"❌ 你的{land['land_name']}已达最高等级 {config['max_level']}！"

        # 升级费用：基础价格 × 当前等级 × 0.5
        upgrade_cost = int(config["price"] * current_level * 0.5)

        if player.gold < upgrade_cost:
            return False, f"❌ 灵石不足！升级需要 {upgrade_cost:,} 灵石。"

        # 升级加成
        new_level = current_level + 1
        new_exp_bonus = config["exp_bonus"] * (1 + new_level * 0.1)

        player.gold -= upgrade_cost
        await self.db.update_player(player)

        await self.db.conn.execute(
            """
            UPDATE blessed_lands SET level = ?, exp_bonus = ?, gold_per_hour = 0
            WHERE user_id = ? AND land_type = ?
            """,
            (new_level, new_exp_bonus, player.user_id, land_type)
        )
        await self.db.conn.commit()

        return True, (
            f"🎉 {land['land_name']}升级到 Lv.{new_level}！\n"
            f"━━━━━━━━━━━━━━━\n"
            f"修炼加成：+{new_exp_bonus:.1%}\n"
            f"花费：{upgrade_cost:,} 灵石"
        )

    async def get_blessed_land_info(self, user_id: str) -> str:
        """获取洞天信息展示"""
        all_lands = await self.get_user_blessed_land(user_id)
        if not all_lands:
            return (
                "🏔️ 洞天福地\n"
                "━━━━━━━━━━━━━━━\n"
                "你还没有洞天！\n\n"
                "可购买的洞天（每种各一个）：\n"
                "  1. 小洞天 - 10,000灵石 (+5%修炼)\n"
                "  2. 中洞天 - 50,000灵石 (+10%修炼)\n"
                "  3. 大洞天 - 200,000灵石 (+20%修炼)\n"
                "  4. 福地 - 500,000灵石 (+30%修炼)\n"
                "  5. 洞天福地 - 1,000,000灵石 (+50%修炼)\n\n"
                "💡 使用 /购买洞天 <编号>"
            )

        total_bonus = sum(land["exp_bonus"] for land in all_lands)
        lines = [
            f"🏔️ 洞天福地 (共{len(all_lands)}个)",
            f"━━━━━━━━━━━━━━━",
            f"总修炼加成：+{total_bonus:.1%}",
            f"━━━━━━━━━━━━━━━",
        ]
        for land in all_lands:
            config = BLESSED_LANDS.get(land["land_type"], BLESSED_LANDS[1])
            max_lv = config["max_level"]
            lines.append(f"  {land['land_name']} Lv.{land['level']}/{max_lv} +{land['exp_bonus']:.1%}")
        lines.append("━━━━━━━━━━━━━━━")
        lines.append("💡 闭关修炼时自动生效")
        lines.append("💡 /升级洞天 <编号> 提升加成")
        return "\n".join(lines)
