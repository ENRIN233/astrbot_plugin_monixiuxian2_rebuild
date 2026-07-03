# core/equipment_manager.py

from typing import Optional, List, Dict, TYPE_CHECKING
from ..models import Player, Item
from ..data import DataBase

if TYPE_CHECKING:
    from ..config_manager import ConfigManager
    from .storage_ring_manager import StorageRingManager

class EquipmentManager:
    """装备管理器 - 处理装备的穿戴、卸下和属性计算"""

    def __init__(self, db: DataBase, config_manager: "ConfigManager" = None, storage_ring_manager: "StorageRingManager" = None):
        self.db = db
        self.config_manager = config_manager
        self.storage_ring_manager = storage_ring_manager

    def parse_item_from_name(self, item_name: str, items_data: dict, weapons_data: dict = None, skills_data: dict = None) -> Optional[Item]:
        """从物品名称解析为Item对象

        Args:
            item_name: 物品名称
            items_data: 物品配置数据字典
            weapons_data: 武器配置数据字典（可选）
            skills_data: 神通配置数据字典（可选）

        Returns:
            Item对象，如果未找到则返回None
        """
        if not item_name or item_name == "":
            return None

        # 先从物品配置中查找
        item_config = items_data.get(item_name)

        # 如果没找到且提供了武器配置，从武器配置中查找
        if not item_config and weapons_data:
            item_config = weapons_data.get(item_name)

        # 如果还没找到且提供了神通配置，从神通配置中查找
        if not item_config and skills_data:
            item_config = skills_data.get(item_name)
            if item_config:
                # 为神通添加type标记
                item_config = dict(item_config)
                if "type" not in item_config:
                    item_config["type"] = "shentong"

        if not item_config:
            return None

        item_type = item_config.get("type", "")

        return Item(
            item_id=item_config.get("id", item_name),
            name=item_name,
            item_type=item_type,
            description=item_config.get("description", ""),
            rank=item_config.get("rank", ""),
            required_level_index=item_config.get("required_level_index", 0),
            weapon_category=item_config.get("weapon_category", ""),
            exp_multiplier=item_config.get("exp_multiplier", 0.0),
            breakthrough_bonus=item_config.get("breakthrough_bonus", 0.0),
            atk_bonus=item_config.get("atk_bonus", 0.0),
            hp_bonus=item_config.get("hp_bonus", 0.0),
            mp_bonus=item_config.get("mp_bonus", 0.0),
            crit_rate=item_config.get("crit_rate", 0),
            crit_damage=item_config.get("crit_damage", 0.0),
            # 补全漏读字段：心法/通用
            closing_exp_bonus=item_config.get("closing_exp_bonus", 0.0),
            closing_recovery_bonus=item_config.get("closing_recovery_bonus", 0.0),
            damage_reduction=item_config.get("damage_reduction", 0.0),
            breakthrough_number=item_config.get("breakthrough_number", 0.0),
            dual_cultivation_bonus=item_config.get("dual_cultivation_bonus", 0),
            alchemy_exp_bonus=item_config.get("alchemy_exp_bonus", 0),
            alchemy_count_bonus=item_config.get("alchemy_count_bonus", 0),
            harvest_bonus=item_config.get("harvest_bonus", 0),
            exclusive_weapon_id=item_config.get("exclusive_weapon_id", 0),
            # 武器战斗属性
            armor_pen=item_config.get("armor_pen", 0),
            lifesteal=item_config.get("lifesteal", 0),
            double_hit=item_config.get("double_hit", 0),
            # 防具战斗属性
            def_buff=item_config.get("def_buff", 0.0),
            dodge_rate=item_config.get("dodge_rate", 0),
            crit_resist=item_config.get("crit_resist", 0),
            reflect_pct=item_config.get("reflect_pct", 0),
            block_value=item_config.get("block_value", 0),
            hp_regen_pct=item_config.get("hp_regen_pct", 0.0),
        )

    def get_equipped_items(self, player: Player, items_data: dict, weapons_data: dict = None, skills_data: dict = None) -> List[Item]:
        """获取玩家所有已装备的物品

        Args:
            player: 玩家对象
            items_data: 物品配置数据字典
            weapons_data: 武器配置数据字典（可选）
            skills_data: 神通配置数据字典（可选）

        Returns:
            已装备物品列表
        """
        equipped = []

        # 武器
        if player.weapon:
            item = self.parse_item_from_name(player.weapon, items_data, weapons_data, skills_data)
            if item:
                equipped.append(item)

        # 防具
        if player.armor:
            item = self.parse_item_from_name(player.armor, items_data, weapons_data, skills_data)
            if item:
                equipped.append(item)

        # 主修心法
        if player.main_technique:
            item = self.parse_item_from_name(player.main_technique, items_data, weapons_data, skills_data)
            if item:
                equipped.append(item)

        # 神通
        if player.shentong:
            item = self.parse_item_from_name(player.shentong, items_data, weapons_data, skills_data)
            if item:
                equipped.append(item)

        return equipped

    def check_equipment_level_requirement(self, player: Player, item: Item) -> tuple[bool, str]:
        """检查玩家是否满足装备的境界要求（已禁用等级限制）"""
        return True, ""

    def _format_required_level(self, level_index: int) -> str:
        """格式化需求境界名称"""
        if not self.config_manager:
            return f"境界{level_index}"

        names = []
        if 0 <= level_index < len(self.config_manager.level_data):
            name = self.config_manager.level_data[level_index].get("name", "未知境界")
            if name:
                names.append(name)

        if not names:
            return f"境界{level_index}"
        return " / ".join(names)

    async def equip_item(self, player: Player, item: Item) -> tuple[bool, str]:
        """装备物品

        修复：先尝试存放旧装备，成功后再更新装备槽位，防止旧装备丢失。

        Args:
            player: 玩家对象
            item: 要装备的物品

        Returns:
            (是否成功, 消息)
        """
        # 检查境界要求
        can_equip, error_msg = self.check_equipment_level_requirement(player, item)
        if not can_equip:
            return False, error_msg

        # 确定装备槽位和旧装备名
        slot_map = {
            "weapon": "weapon",
            "armor": "armor",
            "main_technique": "main_technique",
            "shentong": "shentong",
            "sub_technique": "sub_technique",
        }
        slot = slot_map.get(item.item_type)
        if not slot:
            return False, f"未知的装备类型：{item.item_type}"

        old_item = getattr(player, slot, "") or ""

        # 如果有旧装备，先尝试存入储物戒
        storage_msg = ""
        if old_item:
            if not self.storage_ring_manager:
                return False, f"无法替换【{old_item}】：储物戒系统未初始化"
            success, msg = await self.storage_ring_manager.store_item(player, old_item, 1, silent=True)
            if not success:
                return False, f"无法替换【{old_item}】：储物戒已满，请先腾出空间"
            storage_msg = f"\n旧装备【{old_item}】已存入储物戒"
            # store_item 内部已更新了 player，需要刷新
            player = await self.db.get_player_by_id(player.user_id) or player

        # 旧装备已安全存放，现在更新装备槽位
        setattr(player, slot, item.name)
        await self.db.update_player(player)

        if old_item:
            return True, f"已将【{old_item}】替换为【{item.name}】（{item.rank}）{storage_msg}"
        else:
            type_names = {"weapon": "武器", "armor": "防具", "main_technique": "主修心法", "shentong": "神通", "sub_technique": "辅修功法"}
            return True, f"已装备{type_names.get(item.item_type, '装备')}【{item.name}】（{item.rank}）"

    async def unequip_item(self, player: Player, slot_or_name: str) -> tuple[bool, str]:
        """卸下装备

        Args:
            player: 玩家对象
            slot_or_name: 装备槽位名称（武器/防具/主修心法）或功法名称

        Returns:
            (是否成功, 消息)
        """
        # 尝试按槽位卸下
        if slot_or_name in ["武器", "weapon"]:
            if not player.weapon:
                return False, "未装备武器"
            item_name = player.weapon
            player.weapon = ""
            await self.db.update_player(player)
            return True, f"已卸下武器【{item_name}】"

        elif slot_or_name in ["防具", "armor"]:
            if not player.armor:
                return False, "未装备防具"
            item_name = player.armor
            player.armor = ""
            await self.db.update_player(player)
            return True, f"已卸下防具【{item_name}】"

        elif slot_or_name in ["主修心法", "心法", "main_technique"]:
            if not player.main_technique:
                return False, "未装备主修心法"
            item_name = player.main_technique
            player.main_technique = ""
            await self.db.update_player(player)
            return True, f"已卸下主修心法【{item_name}】"

        # 卸下神通
        if slot_or_name in ["神通", "shentong"]:
            if not player.shentong:
                return False, "未装备神通"
            item_name = player.shentong
            player.shentong = ""
            await self.db.update_player(player)
            return True, f"已卸下神通【{item_name}】"

        # 卸下辅修功法
        if slot_or_name in ["辅修功法", "辅修", "sub_technique"]:
            if not player.sub_technique:
                return False, "未装备辅修功法"
            item_name = player.sub_technique
            player.sub_technique = ""
            await self.db.update_player(player)
            return True, f"已卸下辅修功法【{item_name}】"

        return False, f"未找到装备：{slot_or_name}"
