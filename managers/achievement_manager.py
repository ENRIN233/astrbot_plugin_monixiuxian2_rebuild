# managers/achievement_manager.py

from typing import Dict, List, Optional, Tuple
from astrbot.api import logger
from ..models import Player


class AchievementManager:
    """成就管理器 - 处理成就检查、解锁和装备"""

    def __init__(self, config_manager):
        self.config_manager = config_manager

    def get_all_achievements(self) -> Dict[str, dict]:
        """获取所有成就定义"""
        return self.config_manager.achievements_data

    def check_and_unlock(self, player: Player) -> List[str]:
        """检查并自动解锁成就，返回新解锁的成就名称列表"""
        achievements = self.get_all_achievements()
        if not achievements:
            return []

        ach_data = player.get_achievement_data()
        unlocked = ach_data.get("unlocked", {})
        newly_unlocked = []

        for ach_id, ach_def in achievements.items():
            ach_name = ach_def.get("name", "")
            if ach_name in unlocked:
                continue  # 已解锁

            if self._check_condition(ach_def.get("condition", {}), player):
                unlocked[ach_name] = True
                newly_unlocked.append(ach_name)

        if newly_unlocked:
            ach_data["unlocked"] = unlocked
            player.set_achievement_data(ach_data)

        return newly_unlocked

    def _check_condition(self, condition: dict, player: Player) -> bool:
        """检查成就条件是否满足"""
        cond_type = condition.get("type", "")
        value = condition.get("value", 0)

        if cond_type == "level_up_rate":
            return player.level_up_rate >= value
        elif cond_type == "level_index":
            return player.level_index >= value
        elif cond_type == "experience":
            return player.experience >= value
        elif cond_type == "gold":
            return player.gold >= value
        elif cond_type == "atkpractice":
            return player.atkpractice >= value
        elif cond_type == "level_index_and_type":
            required_type = condition.get("cultivation_type", "")
            return player.level_index >= value and player.cultivation_type == required_type
        elif cond_type == "sect_contribution":
            return player.sect_contribution >= value
        elif cond_type == "lifespan":
            return player.lifespan >= value

        return False

    def equip_achievement(self, player: Player, ach_name: str) -> Tuple[bool, str]:
        """装备成就

        Returns:
            (success, message)
        """
        achievements = self.get_all_achievements()

        # 验证成就存在
        ach_def = None
        for a in achievements.values():
            if a.get("name") == ach_name:
                ach_def = a
                break

        if not ach_def:
            available = [a.get("name", "") for a in achievements.values()]
            return False, f"成就【{ach_name}】不存在"

        # 验证已解锁
        ach_data = player.get_achievement_data()
        unlocked = ach_data.get("unlocked", {})

        if ach_name not in unlocked:
            return False, f"成就【{ach_name}】尚未解锁，无法装备"

        # 装备
        old_equipped = ach_data.get("equipped", "")
        ach_data["equipped"] = ach_name
        player.set_achievement_data(ach_data)

        if old_equipped and old_equipped != ach_name:
            return True, f"已将成就【{old_equipped}】替换为【{ach_name}】"
        elif old_equipped == ach_name:
            return False, f"成就【{ach_name}】已在装备中"
        else:
            return True, f"已装备成就【{ach_name}】"

    def unequip_achievement(self, player: Player) -> Tuple[bool, str]:
        """卸下成就"""
        ach_data = player.get_achievement_data()
        old_equipped = ach_data.get("equipped", "")

        if not old_equipped:
            return False, "当前未装备任何成就"

        ach_data["equipped"] = ""
        player.set_achievement_data(ach_data)
        return True, f"已卸下成就【{old_equipped}】"

    def get_achievement_bonus(self, player: Player) -> dict:
        """获取当前装备成就的属性加成"""
        ach_data = player.get_achievement_data()
        equipped_name = ach_data.get("equipped", "")

        if not equipped_name:
            return {}

        achievements = self.get_all_achievements()
        for ach_def in achievements.values():
            if ach_def.get("name") == equipped_name:
                # 验证确实已解锁
                unlocked = ach_data.get("unlocked", {})
                if equipped_name in unlocked:
                    return ach_def.get("bonus", {})
        return {}

    def get_cumulative_bonus(self, player: Player) -> dict:
        """获取所有已解锁成就的累加属性加成（不含装备加成，用于显示）"""
        ach_data = player.get_achievement_data()
        unlocked = ach_data.get("unlocked", {})
        achievements = self.get_all_achievements()

        total_bonus = {}
        for ach_def in achievements.values():
            ach_name = ach_def.get("name", "")
            if ach_name in unlocked:
                for attr, val in ach_def.get("bonus", {}).items():
                    total_bonus[attr] = total_bonus.get(attr, 0) + val

        return total_bonus

    def format_achievement_list(self, player: Player) -> str:
        """格式化成就列表"""
        achievements = self.get_all_achievements()
        if not achievements:
            return "暂无成就配置"

        ach_data = player.get_achievement_data()
        unlocked = ach_data.get("unlocked", {})
        equipped_name = ach_data.get("equipped", "")

        unlocked_names = set(unlocked.keys())
        total = len(achievements)
        unlocked_count = len(unlocked_names)

        lines = [
            f"🏆 成就系统\n",
            f"━━━━━━━━━━━━━━━\n",
        ]

        # 已解锁
        if unlocked_names:
            lines.append(f"【已解锁】({unlocked_count}/{total})\n")
            for ach_def in achievements.values():
                ach_name = ach_def.get("name", "")
                if ach_name in unlocked_names:
                    bonus_text = self._format_bonus_short(ach_def.get("bonus", {}))
                    equipped_mark = " ← 装备中" if ach_name == equipped_name else ""
                    lines.append(f"✅ {ach_name} — {bonus_text}{equipped_mark}\n")
            lines.append("\n")

        # 未解锁
        locked = [(d.get("name", ""), d.get("description", ""))
                  for d in achievements.values() if d.get("name", "") not in unlocked_names]
        if locked:
            lines.append(f"【未解锁】({len(locked)})\n")
            for name, desc in locked:
                lines.append(f"🔒 {name} — {desc}\n")

        lines.append(f"━━━━━━━━━━━━━━━\n")
        lines.append(f"💡 使用 /装备成就 [名称] 装备成就\n")
        lines.append(f"💡 使用 /卸下成就 卸下当前成就")

        return "".join(lines)

    def _format_bonus_short(self, bonus: dict) -> str:
        """简短格式化属性加成"""
        attr_names = {
            "hp_bonus": "气血",
            "mp_bonus": "真元",
            "lifespan": "寿命",
        }
        parts = []
        for attr, val in bonus.items():
            name = attr_names.get(attr, attr)
            parts.append(f"{name}+{val}")
        return "、".join(parts) if parts else "无加成"
