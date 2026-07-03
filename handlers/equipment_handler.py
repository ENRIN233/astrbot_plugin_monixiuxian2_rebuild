# handlers/equipment_handler.py

from astrbot.api.event import AstrMessageEvent
from ..data import DataBase
from ..core import EquipmentManager, PillManager, StorageRingManager
from ..config_manager import ConfigManager
from ..models import Player
from .utils import player_required

CMD_SHOW_EQUIPMENT = "我的装备"
CMD_EQUIP_ITEM = "装备"
CMD_UNEQUIP_ITEM = "卸下"

__all__ = ["EquipmentHandler"]

class EquipmentHandler:
    """装备系统处理器"""

    def __init__(self, db: DataBase, config_manager: ConfigManager):
        self.db = db
        self.config_manager = config_manager
        self.storage_ring_manager = StorageRingManager(db, config_manager)
        self.equipment_manager = EquipmentManager(db, config_manager, self.storage_ring_manager)
        self.pill_manager = PillManager(db, config_manager)

    @player_required
    async def handle_show_equipment(self, player: Player, event: AstrMessageEvent):
        """显示玩家当前装备"""
        display_name = event.get_sender_name()

        # 获取所有已装备物品
        equipped_items = self.equipment_manager.get_equipped_items(
            player,
            self.config_manager.items_data,
            self.config_manager.weapons_data,
            self.config_manager.skills_data
        )

        await self.pill_manager.update_temporary_effects(player)
        pill_multipliers = self.pill_manager.calculate_pill_attribute_effects(player)

        # 构建装备显示
        equipment_lines = [
            f"=== {display_name} 的装备 ===\n",
            f"【武器】{player.weapon if player.weapon else '未装备'}\n",
            f"【防具】{player.armor if player.armor else '未装备'}\n",
            f"【主修心法】{player.main_technique if player.main_technique else '未装备'}\n",
        ]

        # 神通
        equipment_lines.append(f"【神通】{player.shentong if player.shentong else '未装备'}\n")
        # 辅修功法
        equipment_lines.append(f"【辅修功法】{player.sub_technique if player.sub_technique else '未装备'}\n")

        # 总属性加成
        if equipped_items:
            equipment_lines.append("\n--- 装备属性加成 ---\n")
            total_attrs = player.get_total_attributes(equipped_items, pill_multipliers)

            # 计算加成值
            exp_multiplier = total_attrs["exp_multiplier"]

            if exp_multiplier > 0:
                equipment_lines.append(f"📈 修为倍率 +{exp_multiplier:.1%}\n")

            # 心法额外加成
            breakthrough_bonus = total_attrs.get("breakthrough_bonus", 0.0)
            atk_bonus = total_attrs.get("atk_bonus", 0.0)
            hp_bonus = total_attrs.get("hp_bonus", 0.0)
            mp_bonus = total_attrs.get("mp_bonus", 0.0)
            crit_rate = total_attrs.get("crit_rate", 0)
            crit_damage = total_attrs.get("crit_damage", 0.0)
            if breakthrough_bonus > 0:
                equipment_lines.append(f"✨ 突破成功率 +{breakthrough_bonus:.1%}\n")
            if atk_bonus > 0:
                equipment_lines.append(f"⚔️ 攻击力 +{atk_bonus:.0%}\n")
            if hp_bonus > 0:
                equipment_lines.append(f"❤️ 生命值 +{hp_bonus:.1%}\n")
            if mp_bonus > 0:
                equipment_lines.append(f"💧 真元 +{mp_bonus:.1%}\n")
            if crit_rate > 0:
                equipment_lines.append(f"💥 暴击率 +{crit_rate}%\n")
            if crit_damage > 0:
                equipment_lines.append(f"🔥 暴击伤害 +{crit_damage:.0%}\n")

            # nonebot 同步属性
            closing_exp_bonus = total_attrs.get("closing_exp_bonus", 0.0)
            closing_recovery_bonus = total_attrs.get("closing_recovery_bonus", 0.0)
            damage_reduction = total_attrs.get("damage_reduction", 0.0)
            breakthrough_number = total_attrs.get("breakthrough_number", 0.0)
            dual_cultivation_bonus = total_attrs.get("dual_cultivation_bonus", 0)
            alchemy_exp_bonus = total_attrs.get("alchemy_exp_bonus", 0)
            alchemy_count_bonus = total_attrs.get("alchemy_count_bonus", 0)
            harvest_bonus = total_attrs.get("harvest_bonus", 0)
            if closing_exp_bonus > 0:
                equipment_lines.append(f"🧘 闭关经验 +{closing_exp_bonus:.0%}\n")
            if closing_recovery_bonus > 0:
                equipment_lines.append(f"💚 闭关回复 +{closing_recovery_bonus:.0%}\n")
            if damage_reduction != 0:
                equipment_lines.append(f"🛡️ 减伤率 {damage_reduction:+.0%}\n")
            if breakthrough_number > 0:
                equipment_lines.append(f"🎯 突破概率 +{breakthrough_number:.0f}%\n")
            if dual_cultivation_bonus > 0:
                equipment_lines.append(f"💕 双修次数 +{dual_cultivation_bonus}\n")
            if alchemy_exp_bonus > 0:
                equipment_lines.append(f"⚗️ 炼丹经验 +{alchemy_exp_bonus}\n")
            if alchemy_count_bonus > 0:
                equipment_lines.append(f"⚗️ 出丹数 +{alchemy_count_bonus}\n")
            if harvest_bonus > 0:
                equipment_lines.append(f"🌾 采集加成 +{harvest_bonus}\n")

            # 武器战斗属性（从 weapons_data 读取，非 Item 模型）
            if player.weapon:
                wdata = self.config_manager.weapons_data.get(player.weapon)
                if wdata:
                    w_atk = wdata.get("atk_bonus", 0)
                    w_crit = wdata.get("crit_rate", 0)
                    w_cd = wdata.get("crit_damage", 0)
                    w_mp = wdata.get("mp_bonus", 0)
                    w_armor_pen = wdata.get("armor_pen", 0)
                    w_lifesteal = wdata.get("lifesteal", 0)
                    w_double_hit = wdata.get("double_hit", 0)
                    if w_atk > 0 or w_crit > 0 or w_cd > 0 or w_mp > 0 or w_armor_pen > 0 or w_lifesteal > 0 or w_double_hit > 0:
                        equipment_lines.append("\n--- 武器战斗属性 ---\n")
                        if w_atk > 0:
                            equipment_lines.append(f"⚔️ 攻击力 +{w_atk:.0%}\n")
                        if w_crit > 0:
                            equipment_lines.append(f"💥 暴击率 +{w_crit}%\n")
                        if w_cd > 0:
                            equipment_lines.append(f"🔥 暴击伤害 +{w_cd:.0%}\n")
                        if w_mp > 0:
                            equipment_lines.append(f"💧 真元 +{w_mp:.0%}\n")
                        if w_armor_pen > 0:
                            equipment_lines.append(f"🗡️ 穿透 +{w_armor_pen}%\n")
                        if w_lifesteal > 0:
                            equipment_lines.append(f"🩸 吸血 +{w_lifesteal}%\n")
                        if w_double_hit > 0:
                            equipment_lines.append(f"⚡ 连击 +{w_double_hit}%\n")

            # 防具战斗属性
            if player.armor:
                adata = self.config_manager.weapons_data.get(player.armor) or self.config_manager.items_data.get(player.armor)
                if adata:
                    armor_lines = []
                    a_def = adata.get("def_buff", 0.0)
                    a_dodge = adata.get("dodge_rate", 0)
                    a_crit_resist = adata.get("crit_resist", 0)
                    a_reflect = adata.get("reflect_pct", 0)
                    a_block = adata.get("block_value", 0)
                    a_hp_regen = adata.get("hp_regen_pct", 0.0)
                    if a_def > 0:
                        armor_lines.append(f"🛡️ 减伤 +{a_def:.0%}\n")
                    if a_dodge > 0:
                        armor_lines.append(f"💨 闪避 +{a_dodge}%\n")
                    if a_crit_resist > 0:
                        armor_lines.append(f"🔰 抗暴 +{a_crit_resist}%\n")
                    if a_reflect > 0:
                        armor_lines.append(f"🔄 反伤 +{a_reflect}%\n")
                    if a_block > 0:
                        armor_lines.append(f"🛡️ 格挡 +{a_block}\n")
                    if a_hp_regen > 0:
                        armor_lines.append(f"💚 回血 +{a_hp_regen:.0%}\n")
                    if armor_lines:
                        equipment_lines.append("\n--- 防具战斗属性 ---\n")
                        equipment_lines.extend(armor_lines)

        equipment_lines.append("=" * 28)

        yield event.plain_result("".join(equipment_lines))

    @player_required
    async def handle_equip_item(self, player: Player, event: AstrMessageEvent, item_name: str):
        """装备物品"""
        if not item_name or item_name.strip() == "":
            yield event.plain_result(f"请指定要装备的物品名称\n用法：{CMD_EQUIP_ITEM} 物品名称")
            return

        item_name = item_name.strip()

        # 检查物品是否存在于配置中（先查items再查weapons再查skills）
        item_config = self.config_manager.items_data.get(item_name)
        if not item_config:
            item_config = self.config_manager.weapons_data.get(item_name)
        if not item_config:
            item_config = self.config_manager.skills_data.get(item_name)
            if item_config:
                item_config = dict(item_config)
                if "type" not in item_config:
                    item_config["type"] = "shentong"
        if not item_config:
            item_config = self.config_manager.sub_techniques_data.get(item_name)

        if not item_config:
            yield event.plain_result(f"未找到物品：{item_name}")
            return

        # 检查物品类型是否可装备
        item_type = item_config.get("type", "")
        equippable_types = ["weapon", "armor", "main_technique", "shentong", "sub_technique"]

        if item_type not in equippable_types:
            yield event.plain_result(f"【{item_name}】不是可装备的物品类型")
            return

        # 检查储物戒中是否有该物品
        if not self.storage_ring_manager.has_item(player, item_name, 1):
            yield event.plain_result(
                f"❌ 储物戒中没有【{item_name}】\n"
                f"请先通过购买或获得该装备"
            )
            return

        # 从储物戒取出物品
        success, retrieve_msg = await self.storage_ring_manager.retrieve_item(player, item_name, 1)
        if not success:
            yield event.plain_result(f"❌ 无法从储物戒取出装备：{retrieve_msg}")
            return

        # 重新获取玩家对象（retrieve_item 内部已更新 DB，需要刷新本地对象）
        player = await self.db.get_player_by_id(event.get_sender_id())

        # 创建Item对象
        from ..models import Item
        item = Item(
            item_id=item_config.get("id", item_name),
            name=item_name,
            item_type=item_type,
            description=item_config.get("description", ""),
            rank=item_config.get("rank", ""),
            required_level_index=item_config.get("required_level_index", 0),
            weapon_category=item_config.get("weapon_category", ""),
            exp_multiplier=item_config.get("exp_multiplier", 0.0),
            atk_bonus=item_config.get("atk_bonus", 0.0),
            crit_rate=item_config.get("crit_rate", 0),
            crit_damage=item_config.get("crit_damage", 0.0),
            mp_bonus=item_config.get("mp_bonus", 0.0),
            armor_pen=item_config.get("armor_pen", 0),
            lifesteal=item_config.get("lifesteal", 0),
            double_hit=item_config.get("double_hit", 0),
        )

        # 装备物品
        success, message = await self.equipment_manager.equip_item(player, item)

        if success:
            # 显示属性加成
            attr_display = item.get_attribute_display()
            result_msg = (
                f"✅ {message}\n"
                f"━━━━━━━━━━━━━━━\n"
                f"属性加成：{attr_display}"
            )
            yield event.plain_result(result_msg)
        else:
            # 装备失败，将物品放回储物戒
            await self.storage_ring_manager.store_item(player, item_name, 1, silent=True)
            yield event.plain_result(f"❌ {message}")

    @player_required
    async def handle_unequip_item(self, player: Player, event: AstrMessageEvent, slot_or_name: str):
        """卸下装备"""
        if not slot_or_name or slot_or_name.strip() == "":
            yield event.plain_result(
                f"请指定要卸下的装备\n"
                f"用法：{CMD_UNEQUIP_ITEM} 武器/防具/心法/神通/功法名称"
            )
            return

        slot_or_name = slot_or_name.strip()

        # 获取卸下前的装备名称，用于存入储物戒
        unequipped_item_name = None
        if slot_or_name in ["武器", "weapon"]:
            unequipped_item_name = player.weapon
        elif slot_or_name in ["防具", "armor"]:
            unequipped_item_name = player.armor
        elif slot_or_name in ["主修心法", "心法", "main_technique"]:
            unequipped_item_name = player.main_technique
        elif slot_or_name in ["神通", "shentong"]:
            unequipped_item_name = player.shentong
        elif slot_or_name in ["辅修功法", "辅修", "sub_technique"]:
            unequipped_item_name = player.sub_technique

        # 卸下装备
        success, message = await self.equipment_manager.unequip_item(player, slot_or_name)

        if success:
            # 卸下成功后，将装备存入储物戒
            storage_msg = ""
            if unequipped_item_name:
                store_success, store_msg = await self.storage_ring_manager.store_item(
                    player, unequipped_item_name, 1, silent=True
                )
                if store_success:
                    storage_msg = f"\n已存入储物戒"
                else:
                    storage_msg = f"\n⚠️ 存入储物戒失败：{store_msg}"
            
            yield event.plain_result(f"✅ {message}{storage_msg}")
        else:
            yield event.plain_result(f"❌ {message}")
