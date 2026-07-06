# handlers/equipment_handler.py

import json

from astrbot.api.event import AstrMessageEvent
from ..data import DataBase
from ..core import EquipmentManager, PillManager, StorageRingManager
from ..config_manager import ConfigManager
from ..models import Player
from .utils import player_required

CMD_SHOW_EQUIPMENT = "我的装备"
CMD_EQUIP_ITEM = "装备"
CMD_UNEQUIP_ITEM = "卸下"
CMD_WEAPON_LIST = "武器列表"

__all__ = ["EquipmentHandler"]


class EquipmentHandler:
    """装备系统处理器"""

    def __init__(self, db: DataBase, config_manager: ConfigManager):
        self.db = db
        self.config_manager = config_manager
        self.storage_ring_manager = StorageRingManager(db, config_manager)
        self.equipment_manager = EquipmentManager(db, config_manager, self.storage_ring_manager)
        self.pill_manager = PillManager(db, config_manager)
        self.db_extended = None  # 由外部注入

    @player_required
    async def handle_weapon_list(self, player: Player, event: AstrMessageEvent, args: str = ""):
        """显示玩家的所有武器/防具实例（支持分页）"""
        if not self.db_extended:
            yield event.plain_result("❌ 武器实例系统未初始化")
            return

        instances = await self.db_extended.get_player_weapon_instances(player.user_id)
        if not instances:
            yield event.plain_result("你的武器库是空的！使用 /锻造 来打造武器")
            return

        # 分页
        page = 1
        try:
            page = max(1, int(args))
        except (ValueError, TypeError):
            pass
        per_page = 8
        total_pages = (len(instances) + per_page - 1) // per_page
        page = min(page, total_pages)
        start = (page - 1) * per_page
        page_items = instances[start:start + per_page]

        lines = [f"⚔️ 我的武器库（第 {page}/{total_pages} 页）", "━━━━━━━━━━━━━━━"]
        for inst in page_items:
            try:
                affixes = json.loads(inst.get("affixes", "[]"))
            except (json.JSONDecodeError, TypeError):
                affixes = []
            affix_str = " ".join(f'{a.get("name","?")}+{a.get("val","?")}' for a in affixes)

            equipped_mark = " ⭐" if inst.get("is_equipped") else ""
            quality = inst.get("quality", "下品")
            template = inst.get("template_name", "?")
            iid_short = inst.get("instance_id", "?")[:12]
            atk = inst.get("atk_bonus", 0.0) * 100
            crit = inst.get("crit_rate", 0)

            lines.append(
                f"  {iid_short}  {template}·{quality}{equipped_mark}\n"
                f"    ATK+{atk:.0f}% 暴击+{crit}% {affix_str}"
            )

        lines.append("━━━━━━━━━━━━━━━")
        lines.append("💡 使用 /装备 <实例ID> 装备 | /分解 <实例ID> 分解")

        yield event.plain_result("\n".join(lines))

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
        ]

        # 武器（优先显示锻造实例）
        if player.equipped_weapon:
            weapon_text = f"{player.equipped_weapon[:12]}（锻造）"
        else:
            weapon_text = player.weapon if player.weapon else "未装备"
        equipment_lines.append(f"【武器】{weapon_text}\n")

        # 防具（优先显示锻造实例）
        if player.equipped_armor:
            armor_text = f"{player.equipped_armor[:12]}（锻造）"
        else:
            armor_text = player.armor if player.armor else "未装备"
        equipment_lines.append(f"【防具】{armor_text}\n")

        equipment_lines.append(f"【主修心法】{player.main_technique if player.main_technique else '未装备'}\n")

        # 神通
        equipment_lines.append(f"【神通】{player.shentong if player.shentong else '未装备'}\n")
        # 辅修功法
        equipment_lines.append(f"【辅修功法】{player.sub_technique if player.sub_technique else '未装备'}\n")

        # 总属性加成（合并武器/防具/心法所有属性，消除重复显示）
        if equipped_items:
            equipment_lines.append("\n--- 装备属性加成 ---\n")
            total_attrs = player.get_total_attributes(equipped_items, pill_multipliers)

            # 修炼类加成
            exp_multiplier = total_attrs["exp_multiplier"]
            if exp_multiplier > 0:
                equipment_lines.append(f"📈 修为倍率 +{exp_multiplier:.1%}\n")

            closing_exp_bonus = total_attrs.get("closing_exp_bonus", 0.0)
            if closing_exp_bonus > 0:
                equipment_lines.append(f"🧘 闭关经验 +{closing_exp_bonus:.0%}\n")

            closing_recovery_bonus = total_attrs.get("closing_recovery_bonus", 0.0)
            if closing_recovery_bonus > 0:
                equipment_lines.append(f"💚 闭关回复 +{closing_recovery_bonus:.0%}\n")

            # 属性加成
            atk_bonus = total_attrs.get("atk_bonus", 0.0)
            if atk_bonus > 0:
                equipment_lines.append(f"⚔️ 攻击力 +{atk_bonus:.0%}\n")

            hp_bonus = total_attrs.get("hp_bonus", 0.0)
            if hp_bonus > 0:
                equipment_lines.append(f"❤️ 生命值 +{hp_bonus:.1%}\n")

            mp_bonus = total_attrs.get("mp_bonus", 0.0)
            if mp_bonus > 0:
                equipment_lines.append(f"💧 真元 +{mp_bonus:.1%}\n")

            # 战斗属性
            crit_rate = total_attrs.get("crit_rate", 0)
            if crit_rate > 0:
                equipment_lines.append(f"💥 暴击率 +{crit_rate}%\n")

            crit_damage = total_attrs.get("crit_damage", 0.0)
            if crit_damage > 0:
                equipment_lines.append(f"🔥 暴击伤害 +{crit_damage:.0%}\n")

            armor_pen = total_attrs.get("armor_pen", 0)
            if armor_pen > 0:
                equipment_lines.append(f"🗡️ 穿透 +{armor_pen}%\n")

            lifesteal = total_attrs.get("lifesteal", 0)
            if lifesteal > 0:
                equipment_lines.append(f"🩸 吸血 +{lifesteal}%\n")

            double_hit = total_attrs.get("double_hit", 0)
            if double_hit > 0:
                equipment_lines.append(f"⚡ 连击 +{double_hit}%\n")

            # 防御类属性
            def_buff = total_attrs.get("def_buff", 0.0)
            if def_buff > 0:
                equipment_lines.append(f"🛡️ 减伤 +{def_buff:.0%}\n")

            damage_reduction = total_attrs.get("damage_reduction", 0.0)
            if damage_reduction > 0:
                equipment_lines.append(f"🛡️ 心法减伤 +{damage_reduction:.0%}\n")

            dodge_rate = total_attrs.get("dodge_rate", 0)
            if dodge_rate > 0:
                equipment_lines.append(f"💨 闪避 +{dodge_rate}%\n")

            crit_resist = total_attrs.get("crit_resist", 0)
            if crit_resist > 0:
                equipment_lines.append(f"🔰 抗暴 +{crit_resist}%\n")

            reflect_pct = total_attrs.get("reflect_pct", 0)
            if reflect_pct > 0:
                equipment_lines.append(f"🔄 反伤 +{reflect_pct}%\n")

            block_value = total_attrs.get("block_value", 0)
            if block_value > 0:
                equipment_lines.append(f"🛡️ 格挡 +{block_value}\n")

            hp_regen_pct = total_attrs.get("hp_regen_pct", 0.0)
            if hp_regen_pct > 0:
                equipment_lines.append(f"💚 回血 +{hp_regen_pct:.0%}\n")

            # 突破类加成
            breakthrough_bonus = total_attrs.get("breakthrough_bonus", 0.0)
            if breakthrough_bonus > 0:
                equipment_lines.append(f"✨ 突破成功率 +{breakthrough_bonus:.1%}\n")

            breakthrough_number = total_attrs.get("breakthrough_number", 0.0)
            if breakthrough_number > 0:
                equipment_lines.append(f"🎯 突破概率 +{breakthrough_number:.0f}%\n")

            # 生产采集类加成
            alchemy_exp_bonus = total_attrs.get("alchemy_exp_bonus", 0)
            if alchemy_exp_bonus > 0:
                equipment_lines.append(f"⚗️ 炼丹经验 +{alchemy_exp_bonus}\n")

            alchemy_count_bonus = total_attrs.get("alchemy_count_bonus", 0)
            if alchemy_count_bonus > 0:
                equipment_lines.append(f"⚗️ 出丹数 +{alchemy_count_bonus}\n")

            harvest_bonus = total_attrs.get("harvest_bonus", 0)
            if harvest_bonus > 0:
                equipment_lines.append(f"🌾 采集加成 +{harvest_bonus}\n")

            dual_cultivation_bonus = total_attrs.get("dual_cultivation_bonus", 0)
            if dual_cultivation_bonus > 0:
                equipment_lines.append(f"💕 双修次数 +{dual_cultivation_bonus}\n")

        equipment_lines.append("=" * 28)

        yield event.plain_result("".join(equipment_lines))

    @player_required
    async def handle_equip_item(self, player: Player, event: AstrMessageEvent, item_name: str):
        """装备物品"""
        if not item_name or item_name.strip() == "":
            yield event.plain_result(f"请指定要装备的物品名称\n用法：{CMD_EQUIP_ITEM} 物品名称")
            return

        item_name = item_name.strip()

        # ── 检查是否为锻造武器实例ID ──
        if item_name.startswith("forge_") and self.db_extended:
            inst = await self.db_extended.get_weapon_instance(item_name)
            if not inst:
                yield event.plain_result(f"❌ 武器实例 {item_name} 不存在")
                return
            if inst["user_id"] != player.user_id:
                yield event.plain_result(f"❌ 这不是你的武器")
                return

            # 从实例构建 Item 对象
            from ..models import Item as ItemModel
            item = ItemModel(
                item_id=inst["instance_id"],
                name=inst["template_name"],
                item_type=inst["item_type"],
                rank=inst["quality"],
                required_level_index=0,
                atk_bonus=inst.get("atk_bonus", 0.0),
                crit_rate=inst.get("crit_rate", 0),
                crit_damage=inst.get("crit_damage", 0.0),
                mp_bonus=inst.get("mp_bonus", 0.0),
                armor_pen=inst.get("armor_pen", 0),
                lifesteal=inst.get("lifesteal", 0),
                double_hit=inst.get("double_hit", 0),
                damage_reduction=inst.get("damage_reduction", 0.0),
                def_buff=inst.get("def_buff", 0.0),
                dodge_rate=inst.get("dodge_rate", 0),
                crit_resist=inst.get("crit_resist", 0),
                reflect_pct=inst.get("reflect_pct", 0),
                block_value=inst.get("block_value", 0),
                hp_regen_pct=inst.get("hp_regen_pct", 0.0),
            )

            success, msg = await self.equipment_manager.equip_item(player, item)
            yield event.plain_result(msg)
            return

        # ── 以下是原有逻辑（非锻造装备）──

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
