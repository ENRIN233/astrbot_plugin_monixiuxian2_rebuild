# core/pill_manager.py

import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from astrbot.api import logger

from ..models import Player
from ..data import DataBase
from ..config_manager import ConfigManager


class PillManager:
    """丹药管理器 - 处理丹药效果、属性加成和限制机制"""

    def __init__(self, db: DataBase, config_manager: ConfigManager):
        self.db = db
        self.config_manager = config_manager

    def _ensure_non_negative_attributes(self, player: Player):
        """保证属性不为负，并同步能量上限约束"""
        attrs = [
            "lifespan",
            "experience",
            "spiritual_qi",
            "max_spiritual_qi",
            "blood_qi",
            "max_blood_qi",
        ]
        for attr in attrs:
            value = getattr(player, attr, 0)
            if value < 0:
                setattr(player, attr, 0)

        # 保证当前能量不超过上限
        if player.spiritual_qi > player.max_spiritual_qi:
            player.spiritual_qi = player.max_spiritual_qi
        if player.blood_qi > player.max_blood_qi:
            player.blood_qi = player.max_blood_qi

    def get_pill_by_name(self, pill_name: str) -> Optional[dict]:
        """根据名称获取丹药配置

        Args:
            pill_name: 丹药名称

        Returns:
            丹药配置字典，如果找不到返回None
        """
        # 尝试从破境丹中查找
        pill = self.config_manager.pills_data.get(pill_name)
        if pill:
            return pill

        # 尝试从修为丹中查找
        pill = self.config_manager.exp_pills_data.get(pill_name)
        if pill:
            return pill

        # 尝试从功能丹中查找
        pill = self.config_manager.utility_pills_data.get(pill_name)
        if pill:
            return pill

        return None

    async def update_temporary_effects(self, player: Player):
        """更新临时丹药效果，移除过期效果

        Args:
            player: 玩家对象
        """
        effects = player.get_active_pill_effects()
        current_time = int(time.time())
        updated_effects = []
        has_changes = False

        for effect in effects:
            if self._apply_periodic_effects(player, effect, current_time):
                has_changes = True

            expiry_time = effect.get("expiry_time", 0)
            if expiry_time <= 0 or current_time < expiry_time:
                updated_effects.append(effect)
            else:
                has_changes = True
                logger.info(f"玩家 {player.user_id} 的丹药效果 {effect.get('pill_name')} 已过期")

        if has_changes or len(updated_effects) != len(effects):
            player.set_active_pill_effects(updated_effects)
            await self.db.update_player(player)

    async def use_pill(
        self,
        player: Player,
        pill_name: str,
        quantity: int = 1
    ) -> Tuple[bool, str]:
        """使用丹药（支持批量）

        Args:
            player: 玩家对象
            pill_name: 丹药名称
            quantity: 数量（默认1）

        Returns:
            (是否成功, 消息)
        """
        # 检查背包是否有该丹药
        inventory = player.get_pills_inventory()
        available = inventory.get(pill_name, 0)
        if available <= 0:
            return False, f"你的背包中没有【{pill_name}】！"

        # 限制数量为可用库存
        actual_quantity = min(quantity, available)

        # 获取丹药配置
        pill_data = self.get_pill_by_name(pill_name)
        if not pill_data:
            return False, f"丹药【{pill_name}】配置不存在！"


        # 根据丹药类型计算最大可服用数量
        effect_type = pill_data.get("effect_type", "instant")
        subtype = pill_data.get("subtype", "")
        max_consumable = actual_quantity

        # 回生丹：同时只能有1个效果
        if subtype == "resurrection":
            if player.has_resurrection_pill:
                return False, "你已经拥有回生丹效果，无需重复使用！"
            max_consumable = 1

        # 双修丹药：每日限2个
        elif subtype == "dual_cultivation_boost":
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if player.last_daily_reset != today:
                player.set_daily_pill_usage({})
                player.last_daily_reset = today
            daily_usage = player.get_daily_pill_usage()
            pill_id = pill_data.get("id", "")
            used_today = daily_usage.get(pill_id, 0)
            remaining = 2 - used_today
            if remaining <= 0:
                return False, "❌ 龙精虎猛丹每日最多服用2颗！"
            max_consumable = min(max_consumable, remaining)

        # 永久属性丹药：根据 max_usage 字段限制（0=无限制）
        elif effect_type == "permanent":
            max_usage = pill_data.get("max_usage", 0)
            if max_usage > 0:
                usage = player.get_permanent_pill_usage()
                used_count = usage.get(pill_name, 0)
                remaining = max_usage - used_count
                if remaining <= 0:
                    return False, f"你已经服用了{max_usage}颗【{pill_name}】，已达上限！"
                max_consumable = min(max_consumable, remaining)

        # 根据丹药类型处理
        if subtype == "exp":
            # 修为丹
            return await self._use_exp_pill(player, pill_name, pill_data, max_consumable)
        elif subtype == "resurrection":
            # 回生丹
            return await self._use_resurrection_pill(player, pill_name, pill_data, max_consumable)
        elif effect_type == "temporary":
            # 临时效果丹药
            return await self._use_temporary_pill(player, pill_name, pill_data, max_consumable)
        elif effect_type == "permanent":
            # 永久属性丹药
            return await self._use_permanent_pill(player, pill_name, pill_data, max_consumable)
        elif effect_type == "instant":
            # 瞬间效果丹药
            return await self._use_instant_pill(player, pill_name, pill_data, max_consumable)
        else:
            return False, f"未知的丹药类型：{effect_type}"

    async def _use_exp_pill(self, player: Player, pill_name: str, pill_data: dict, quantity: int = 1) -> Tuple[bool, str]:
        """使用修为丹（支持批量）"""
        exp_gain_per_pill = pill_data.get("exp_gain", 0)
        total_exp_gain = exp_gain_per_pill * quantity

        player.experience += total_exp_gain

        # 扣除丹药
        inventory = player.get_pills_inventory()
        inventory[pill_name] -= quantity
        if inventory[pill_name] <= 0:
            del inventory[pill_name]
        player.set_pills_inventory(inventory)

        await self.db.update_player(player)

        remaining = inventory.get(pill_name, 0)

        if quantity == 1:
            return True, (
                f"✨ 服用【{pill_name}】成功！\n"
                f"━━━━━━━━━━━━━━━\n"
                f"📈 获得修为：{exp_gain_per_pill}\n"
                f"💫 当前修为：{player.experience}\n"
                f"━━━━━━━━━━━━━━━"
            )
        else:
            return True, (
                f"✨ 成功服用 {quantity} 个【{pill_name}】！\n"
                f"━━━━━━━━━━━━━━━\n"
                f"📈 获得修为：{total_exp_gain} ({exp_gain_per_pill} × {quantity})\n"
                f"💫 当前修为：{player.experience}\n"
                f"💼 剩余库存：{remaining} 个\n"
                f"━━━━━━━━━━━━━━━"
            )

    async def _use_resurrection_pill(self, player: Player, pill_name: str, pill_data: dict, quantity: int = 1) -> Tuple[bool, str]:
        """使用回生丹（quantity参数仅用于向后兼容，实际只处理1个）"""
        if player.has_resurrection_pill:
            return False, "你已经拥有回生丹效果，无需重复使用！"

        player.has_resurrection_pill = pill_name

        # 扣除丹药
        inventory = player.get_pills_inventory()
        inventory[pill_name] -= 1
        if inventory[pill_name] <= 0:
            del inventory[pill_name]
        player.set_pills_inventory(inventory)

        await self.db.update_player(player)

        if pill_name == "涅槃重生丹":
            penalty_desc = "（复活后不损失任何属性）"
        else:
            penalty_desc = "（复活后损失15%属性）"

        return True, (
            f"✨ 服用【{pill_name}】成功！\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🛡️ 你获得了起死回生的能力\n"
            f"下次死亡时将自动复活\n"
            f"{penalty_desc}\n"
            f"━━━━━━━━━━━━━━━"
        )

    async def _use_temporary_pill(self, player: Player, pill_name: str, pill_data: dict, quantity: int = 1) -> Tuple[bool, str]:
        """使用临时效果丹药（批量会延长持续时间）"""
        duration_per_pill = pill_data.get("duration_minutes", 60)
        total_duration_minutes = duration_per_pill * quantity
        current_time = int(time.time())

        # 检查是否已有相同效果
        effects = player.get_active_pill_effects()
        existing_effect = None
        for effect in effects:
            if effect.get("pill_name") == pill_name:
                existing_effect = effect
                break

        if existing_effect:
            # 延长现有效果
            if existing_effect["expiry_time"] > 0:
                existing_effect["expiry_time"] += (duration_per_pill * 60 * quantity)
            existing_effect["duration_minutes"] += total_duration_minutes
            player.set_active_pill_effects(effects)
        else:
            # 创建新效果（duration_minutes=0 表示持续到被消耗，不自动过期）
            expiry_time = 0 if total_duration_minutes == 0 else current_time + total_duration_minutes * 60
            effect = {
                "pill_name": pill_name,
                "pill_id": pill_data.get("id", ""),
                "subtype": pill_data.get("subtype", ""),
                "start_time": current_time,
                "expiry_time": expiry_time,
                "duration_minutes": total_duration_minutes,
                "last_tick_time": current_time,
            }

            # 添加具体效果数据
            effect_keys = [
                "cultivation_multiplier",
                "lifespan_cost_per_minute", "lifespan_regen_per_minute",
                "spiritual_qi_regen_per_minute", "blood_qi_regen_per_minute", "blood_qi_cost_per_minute",
                "breakthrough_bonus", "dual_cultivation_exp_bonus"
            ]
            for key in effect_keys:
                if key in pill_data:
                    effect[key] = pill_data[key]

            effects.append(effect)
            player.set_active_pill_effects(effects)

        # 扣除丹药
        inventory = player.get_pills_inventory()
        inventory[pill_name] -= quantity
        if inventory[pill_name] <= 0:
            del inventory[pill_name]
        player.set_pills_inventory(inventory)

        # 记录每日使用次数（用于限制特定丹药每日用量）
        subtype = pill_data.get("subtype", "")
        if subtype == "dual_cultivation_boost":
            daily_usage = player.get_daily_pill_usage()
            pill_id = pill_data.get("id", "")
            daily_usage[pill_id] = daily_usage.get(pill_id, 0) + quantity
            player.set_daily_pill_usage(daily_usage)

        await self.db.update_player(player)

        # 构建效果描述
        effect_desc = []
        if "cultivation_multiplier" in pill_data:
            mult = pill_data["cultivation_multiplier"]
            if mult > 0:
                effect_desc.append(f"修炼速度+{mult:.0%}")
            else:
                effect_desc.append(f"修炼速度{mult:.0%}")

        if "lifespan_cost_per_minute" in pill_data:
            cost = pill_data["lifespan_cost_per_minute"]
            effect_desc.append(f"每分钟扣除寿命-{cost}")

        if "lifespan_regen_per_minute" in pill_data:
            regen = pill_data["lifespan_regen_per_minute"]
            effect_desc.append(f"每分钟恢复寿命+{regen}")

        if "spiritual_qi_regen_per_minute" in pill_data:
            regen = pill_data["spiritual_qi_regen_per_minute"]
            effect_desc.append(f"每分钟恢复灵气+{regen}")

        if "blood_qi_regen_per_minute" in pill_data:
            regen = pill_data["blood_qi_regen_per_minute"]
            effect_desc.append(f"每分钟恢复气血+{regen}")

        if "blood_qi_cost_per_minute" in pill_data:
            cost = pill_data["blood_qi_cost_per_minute"]
            effect_desc.append(f"每分钟扣除气血-{cost}")

        if "breakthrough_bonus" in pill_data:
            bonus = pill_data["breakthrough_bonus"]
            if bonus > 0:
                effect_desc.append(f"突破成功率+{bonus:.0%}")
            else:
                effect_desc.append(f"突破成功率{bonus:.0%}")

        if "dual_cultivation_exp_bonus" in pill_data:
            bonus = pill_data["dual_cultivation_exp_bonus"]
            effect_desc.append(f"双修次数+1、双修修为+{bonus:.0%}")

        effects_str = "、".join(effect_desc) if effect_desc else "特殊效果"

        remaining = inventory.get(pill_name, 0)

        if quantity == 1:
            duration_desc = f"⏱️ 持续时间：{duration_per_pill}分钟\n" if duration_per_pill > 0 else ""
            return True, (
                f"✨ 服用【{pill_name}】成功！\n"
                f"━━━━━━━━━━━━━━━\n"
                f"{duration_desc}"
                f"🎯 效果：{effects_str}\n"
                f"━━━━━━━━━━━━━━━"
            )
        else:
            action = "延长" if existing_effect else "获得"
            duration_desc = f"⏱️ 持续时间：{total_duration_minutes}分钟 ({duration_per_pill} × {quantity})\n" if total_duration_minutes > 0 else ""
            return True, (
                f"✨ 成功服用 {quantity} 个【{pill_name}】！\n"
                f"━━━━━━━━━━━━━━━\n"
                f"{duration_desc}"
                f"🎯 效果：{effects_str}\n"
                f"💼 剩余库存：{remaining} 个\n"
                f"━━━━━━━━━━━━━━━"
            )

    async def _use_permanent_pill(self, player: Player, pill_name: str, pill_data: dict, quantity: int = 1) -> Tuple[bool, str]:
        """使用永久属性丹药（支持批量，受属性上限限制，洗髓丹/易筋丹可提升）"""
        consumed = 0
        total_gains_applied = {}
        stop_reason = None

        for i in range(quantity):
            # 检查服用次数限制（根据 max_usage 字段，0=无限制）
            max_usage = pill_data.get("max_usage", 0)
            usage = player.get_permanent_pill_usage()
            current_count = usage.get(pill_name, 0)
            if max_usage > 0 and current_count >= max_usage:
                stop_reason = f"已达终身服用上限({max_usage}颗)"
                break

            # 检查境界限制（30%上限）
            permanent_gains = player.get_permanent_pill_gains()
            level_key = f"level_{player.level_index}"

            if level_key not in permanent_gains:
                permanent_gains[level_key] = {
                    "lifespan": 0,
                    "max_spiritual_qi": 0,
                    "max_blood_qi": 0,
                }

            # 计算基础属性（当前境界突破时获得的属性）
            base_attrs = self._get_base_attributes_for_level(player, player.level_index)

            # 检查各项属性是否已达上限
            attr_mapping = {
                "lifespan_gain": ("lifespan", "寿命"),
                "max_spiritual_qi_gain": ("max_spiritual_qi", "最大灵气"),
                "max_blood_qi_gain": ("max_blood_qi", "最大气血"),
            }

            gains_applied = {}
            all_blocked = True

            # 处理属性上限提升（洗髓丹/易筋丹）
            if "base_attribute_limit_increase" in pill_data:
                inc = pill_data["base_attribute_limit_increase"]
                if "base_attribute_limit_increase" not in permanent_gains:
                    permanent_gains["base_attribute_limit_increase"] = 0.0
                permanent_gains["base_attribute_limit_increase"] += inc
                gains_applied["属性上限提升"] = f"+{inc:.0%}"
                all_blocked = False

            # 计算当前属性上限比例（默认30%，洗髓丹/易筋丹可提升）
            attr_limit_ratio = 0.3 + permanent_gains.get("base_attribute_limit_increase", 0.0)

            for gain_key, (attr_key, attr_name) in attr_mapping.items():
                if gain_key not in pill_data:
                    continue

                gain = pill_data[gain_key]
                if gain == 0:
                    continue

                # 只有正向增益才受上限限制
                if gain > 0:
                    current_gain = permanent_gains[level_key].get(attr_key, 0)
                    base_value = base_attrs.get(attr_key, 100)
                    limit = base_value * attr_limit_ratio

                    if current_gain >= limit:
                        continue

                    # 计算实际可以增加的值
                    actual_gain = min(gain, limit - current_gain)

                    # 应用增益
                    permanent_gains[level_key][attr_key] += actual_gain
                    setattr(player, attr_key, getattr(player, attr_key) + int(actual_gain))
                    gains_applied[attr_name] = int(actual_gain)
                    all_blocked = False
                else:
                    # 负向效果直接应用
                    permanent_gains[level_key][attr_key] += gain
                    setattr(player, attr_key, getattr(player, attr_key) + int(gain))
                    gains_applied[attr_name] = int(gain)
                    all_blocked = False

            # 处理修炼倍率（永久，全局存储，不随境界丢失）
            if "_global" not in permanent_gains:
                permanent_gains["_global"] = {}
            if "cultivation_multiplier" in pill_data:
                cult_mult = pill_data["cultivation_multiplier"]
                if "cultivation_multiplier" not in permanent_gains["_global"]:
                    permanent_gains["_global"]["cultivation_multiplier"] = 0
                permanent_gains["_global"]["cultivation_multiplier"] += cult_mult
                gains_applied["修炼速度"] = f"{cult_mult:+.0%}"
                all_blocked = False

            # 处理战斗属性倍率（永久，全局存储，不随境界丢失） - 已废弃的物伤/法伤/物防/法防倍率已移除

            # 处理突破死亡概率降低（永久，全局存储）
            if "death_protection_multiplier" in pill_data:
                death_mult = pill_data["death_protection_multiplier"]
                if "death_protection_multiplier" not in permanent_gains["_global"]:
                    permanent_gains["_global"]["death_protection_multiplier"] = 1.0
                permanent_gains["_global"]["death_protection_multiplier"] *= death_mult
                gains_applied["突破死亡概率"] = f"降低{(1 - death_mult) * 100:.0f}%"
                all_blocked = False

            if all_blocked:
                limit_pct = int(attr_limit_ratio * 100)
                stop_reason = f"所有属性已达{limit_pct}%上限"
                break

            # 修正属性下限与能量上限
            self._ensure_non_negative_attributes(player)

            # 更新玩家数据
            player.set_permanent_pill_gains(permanent_gains)

            # 累加总增益
            for attr_name, value in gains_applied.items():
                if isinstance(value, int):
                    total_gains_applied[attr_name] = total_gains_applied.get(attr_name, 0) + value
                else:
                    total_gains_applied[attr_name] = value

            # 记录服用次数
            usage[pill_name] = current_count + 1
            player.set_permanent_pill_usage(usage)

            consumed += 1

        if consumed == 0:
            return False, "无法服用任何丹药！该丹药的所有属性增益都已达到上限。"

        # 扣除已消费的丹药
        inventory = player.get_pills_inventory()
        inventory[pill_name] -= consumed
        if inventory[pill_name] <= 0:
            del inventory[pill_name]
        player.set_pills_inventory(inventory)

        await self.db.update_player(player)

        # 构建消息
        msg_parts = []
        if consumed == 1:
            msg_parts.append(f"✨ 服用【{pill_name}】成功！")
        else:
            msg_parts.append(f"✨ 成功服用 {consumed} 个【{pill_name}】！")
            if consumed < quantity:
                msg_parts.append(f"⚠️ {stop_reason}")

        msg_parts.append("━━━━━━━━━━━━━━━")
        msg_parts.append("💪 永久增益：")

        for attr_name, value in total_gains_applied.items():
            if isinstance(value, int):
                msg_parts.append(f"  {attr_name} +{value}")
            else:
                msg_parts.append(f"  {attr_name} {value}")

        remaining = inventory.get(pill_name, 0)
        if quantity > 1:
            msg_parts.append(f"💼 剩余库存：{remaining} 个")

        msg_parts.append("━━━━━━━━━━━━━━━")
        permanent_gains = player.get_permanent_pill_gains()
        limit_pct = int((0.3 + permanent_gains.get("base_attribute_limit_increase", 0.0)) * 100)
        msg_parts.append(f"注：每个境界的永久属性丹药\n增益最多为基础属性的{limit_pct}%")

        return True, "\n".join(msg_parts)

    async def _use_instant_pill(self, player: Player, pill_name: str, pill_data: dict, quantity: int = 1) -> Tuple[bool, str]:
        """使用瞬间效果丹药（支持批量）"""
        effect = pill_data.get("effect", {})
        subtype = pill_data.get("subtype", "")

        # 恢复能量（灵气/气血）
        energy_restore = None
        energy_label = "灵气"
        current_energy = player.spiritual_qi
        max_energy = player.max_spiritual_qi

        # 体修优先使用专属气血恢复键；若无则复用灵气恢复作为气血恢复
        if player.cultivation_type == "体修" and "blood_qi_restore" in pill_data:
            energy_restore = pill_data["blood_qi_restore"]
            energy_label = "气血"
            current_energy = player.blood_qi
            max_energy = player.max_blood_qi
        elif "spiritual_qi_restore" in pill_data:
            energy_restore = pill_data["spiritual_qi_restore"]
            if player.cultivation_type == "体修":
                energy_label = "气血"
                current_energy = player.blood_qi
                max_energy = player.max_blood_qi

        total_restore = 0
        if energy_restore is not None:
            if energy_restore == -1:
                # 恢复至满（批量时只需一次）
                total_restore = max_energy - current_energy
                current_energy = max_energy
            else:
                # 批量累加恢复量
                total_restore_raw = energy_restore * quantity
                old_energy = current_energy
                current_energy = min(current_energy + total_restore_raw, max_energy)
                total_restore = current_energy - old_energy

            if energy_label == "气血":
                player.blood_qi = current_energy
            else:
                player.spiritual_qi = current_energy

        # --- GAP 2: 治疗丹药（heal_hp_pct）---
        heal_amount = 0
        heal_pct = effect.get("heal_hp_pct", 0)
        if heal_pct > 0:
            # 计算 max_hp：通过 experience 推导（与 combat_manager 一致）
            from ..managers.combat_manager import CombatManager
            hp_buff = 0.0
            if player.main_technique:
                items_data = self.config_manager.items_data
                tech = items_data.get(player.main_technique)
                if tech:
                    hp_buff_temp = tech.get("hp_bonus", 0.0)
                    hp, _ = CombatManager.calculate_hp_mp(player.experience, 0.0, 0.0, hp_buff_temp, 0.0)
                    # 使用标准 hp 计算，带心法加成
                    max_hp = hp
                else:
                    max_hp = max(1000, int(player.experience / 2))
            else:
                max_hp = max(1000, int(player.experience / 2))

            if heal_pct >= 1.0:
                # 完全恢复（批量时只需一次）
                heal_amount = max_hp - player.hp if hasattr(player, 'hp') and player.hp < max_hp else 0
                if hasattr(player, 'hp'):
                    player.hp = max_hp
            else:
                for _ in range(quantity):
                    heal_per_pill = int(max_hp * heal_pct)
                    if hasattr(player, 'hp'):
                        old_hp = player.hp
                        player.hp = min(max_hp, player.hp + heal_per_pill)
                        heal_amount += player.hp - old_hp

        # --- GAP 3: 永久攻击力丹药（atk_bonus）---
        atk_bonus_msg = None
        flat_atk_bonus = effect.get("atk_bonus", 0)
        if flat_atk_bonus > 0:
            permanent_gains = player.get_permanent_pill_gains()
            if "_global" not in permanent_gains:
                permanent_gains["_global"] = {}
            if "flat_atk_bonus" not in permanent_gains["_global"]:
                permanent_gains["_global"]["flat_atk_bonus"] = 0
            total_atk_gain = flat_atk_bonus * quantity
            permanent_gains["_global"]["flat_atk_bonus"] += total_atk_gain
            player.set_permanent_pill_gains(permanent_gains)
            atk_bonus_msg = f"永久攻击力 +{total_atk_gain:,}"

        # --- GAP 9: 突破加成丹药（breakthrough_boost）---
        breakthrough_boost_applied = False
        breakthrough_bonus_val = effect.get("breakthrough_bonus", 0)
        if subtype == "breakthrough_boost" and breakthrough_bonus_val > 0:
            # 检查 max_uses 限制
            max_uses = pill_data.get("max_uses", 0)
            if max_uses > 0:
                usage = player.get_permanent_pill_usage()
                used_count = usage.get(pill_name, 0)
                remaining_uses = max_uses - used_count
                if remaining_uses <= 0:
                    return False, f"你已经服用了{max_uses}颗【{pill_name}】，已达上限！"
                actual_quantity = min(quantity, remaining_uses)
            else:
                actual_quantity = quantity

            # 存储为临时活跃效果（突破时读取）
            current_time = int(time.time())
            effects = player.get_active_pill_effects()
            # 查找是否已有同名效果（累加 bonus）
            existing = None
            for eff in effects:
                if eff.get("pill_name") == pill_name and eff.get("subtype") == "breakthrough_boost":
                    existing = eff
                    break

            if existing:
                existing["breakthrough_bonus"] = existing.get("breakthrough_bonus", 0) + breakthrough_bonus_val * actual_quantity
            else:
                effects.append({
                    "pill_name": pill_name,
                    "pill_id": pill_data.get("id", ""),
                    "subtype": "breakthrough_boost",
                    "start_time": current_time,
                    "expiry_time": 0,  # 不自动过期，突破后消费
                    "duration_minutes": 0,
                    "breakthrough_bonus": breakthrough_bonus_val * actual_quantity,
                    "target_level_index": pill_data.get("target_level_index"),  # 记录目标境界，用于过滤
                })
            player.set_active_pill_effects(effects)

            # 记录服用次数
            usage = player.get_permanent_pill_usage()
            usage[pill_name] = usage.get(pill_name, 0) + actual_quantity
            player.set_permanent_pill_usage(usage)
            breakthrough_boost_applied = True

            # 调整实际消费数量
            if actual_quantity < quantity:
                quantity = actual_quantity

        # --- 渡厄金丹：死亡保护（突破失败时不损失修为）---
        death_protection_applied = False
        if subtype == "death_protection" and effect.get("death_protection"):
            # 检查 max_uses 限制
            max_uses = pill_data.get("max_uses", 0)
            if max_uses > 0:
                usage = player.get_permanent_pill_usage()
                used_count = usage.get(pill_name, 0)
                remaining_uses = max_uses - used_count
                if remaining_uses <= 0:
                    return False, f"你已经服用了{max_uses}颗【{pill_name}】，已达上限！"
                actual_quantity = min(quantity, remaining_uses)
            else:
                actual_quantity = quantity

            # 存储为临时活跃效果（突破时读取）
            current_time = int(time.time())
            effects = player.get_active_pill_effects()
            existing = None
            for eff in effects:
                if eff.get("pill_name") == pill_name and eff.get("subtype") == "death_protection":
                    existing = eff
                    break

            if not existing:
                effects.append({
                    "pill_name": pill_name,
                    "pill_id": pill_data.get("id", ""),
                    "subtype": "death_protection",
                    "start_time": current_time,
                    "expiry_time": 0,  # 不自动过期，突破后消费
                    "duration_minutes": 0,
                    "death_protection": True,
                })
            player.set_active_pill_effects(effects)

            # 记录服用次数
            usage = player.get_permanent_pill_usage()
            usage[pill_name] = usage.get(pill_name, 0) + actual_quantity
            player.set_permanent_pill_usage(usage)
            death_protection_applied = True

            # 调整实际消费数量
            if actual_quantity < quantity:
                quantity = actual_quantity

        # 处理特殊效果（只处理一次，不受数量影响）
        has_reset = False
        has_shield = False

        # 重置永久丹药增益
        if pill_data.get("resets_permanent_pills"):
            has_reset = self._reset_permanent_pill_effects(player)
            if has_reset:
                refund_ratio = pill_data.get("reset_refund_ratio", 0.5)
                refund = int(pill_data.get("price", 0) * refund_ratio)
                if refund > 0:
                    player.gold += refund

        # 定魂丹 - 下一次负面效果免疫
        if pill_data.get("blocks_next_debuff"):
            if not player.has_debuff_shield:
                player.has_debuff_shield = True
                has_shield = True

        # 扣除丹药
        inventory = player.get_pills_inventory()
        inventory[pill_name] -= quantity
        if inventory[pill_name] <= 0:
            del inventory[pill_name]
        player.set_pills_inventory(inventory)

        await self.db.update_player(player)

        # 构建消息
        msg_parts = []
        if quantity == 1:
            msg_parts.append(f"服用【{pill_name}】成功！")
        else:
            msg_parts.append(f"成功服用 {quantity} 个【{pill_name}】！")

        msg_parts.append("━━━━━━━━━━━━━━━")

        # 治疗丹药消息
        if heal_pct > 0:
            if heal_pct >= 1.0:
                msg_parts.append("恢复生命至满")
            else:
                msg_parts.append(f"恢复生命：+{heal_amount}")

        if total_restore > 0:
            if energy_restore == -1:
                if energy_label == "气血":
                    msg_parts.append(f"恢复气血至满")
                    msg_parts.append(f"当前气血：{player.blood_qi}/{player.max_blood_qi}")
                else:
                    msg_parts.append(f"恢复灵气至满")
                    msg_parts.append(f"当前灵气：{player.spiritual_qi}/{player.max_spiritual_qi}")
            else:
                if quantity > 1:
                    if energy_label == "气血":
                        msg_parts.append(f"恢复气血：+{total_restore} ({energy_restore} x {quantity})")
                        msg_parts.append(f"当前气血：{player.blood_qi}/{player.max_blood_qi}")
                    else:
                        msg_parts.append(f"恢复灵气：+{total_restore} ({energy_restore} x {quantity})")
                        msg_parts.append(f"当前灵气：{player.spiritual_qi}/{player.max_spiritual_qi}")
                else:
                    if energy_label == "气血":
                        msg_parts.append(f"恢复气血：+{total_restore}")
                        msg_parts.append(f"当前气血：{player.blood_qi}/{player.max_blood_qi}")
                    else:
                        msg_parts.append(f"恢复灵气：+{total_restore}")
                        msg_parts.append(f"当前灵气：{player.spiritual_qi}/{player.max_spiritual_qi}")

        # 永久攻击力丹药消息
        if atk_bonus_msg:
            msg_parts.append(atk_bonus_msg)

        # 突破加成丹药消息
        if breakthrough_boost_applied:
            msg_parts.append(f"突破成功率 +{breakthrough_bonus_val:.0%}（下次突破生效）")
            usage = player.get_permanent_pill_usage()
            max_uses = pill_data.get("max_uses", 0)
            if max_uses > 0:
                msg_parts.append(f"已服用 {usage.get(pill_name, 0)}/{max_uses}")

        # 死亡保护丹药消息
        if death_protection_applied:
            msg_parts.append("获得突破死亡保护：下次突破失败不损失修为")
            usage = player.get_permanent_pill_usage()
            max_uses = pill_data.get("max_uses", 0)
            if max_uses > 0:
                msg_parts.append(f"已服用 {usage.get(pill_name, 0)}/{max_uses}")

        if has_reset:
            msg_parts.append("已重置所有永久属性丹药增益")
            refund_ratio = pill_data.get("reset_refund_ratio", 0.5)
            refund = int(pill_data.get("price", 0) * refund_ratio)
            if refund > 0:
                msg_parts.append(f"返还灵石：{refund}")
        elif pill_data.get("resets_permanent_pills"):
            msg_parts.append("当前没有可重置的永久增益")

        if has_shield:
            msg_parts.append("获得定魂护盾：下一次负面效果将被抵消")
        elif pill_data.get("blocks_next_debuff") and player.has_debuff_shield:
            msg_parts.append("定魂护盾已存在，无需重复使用")

        remaining = inventory.get(pill_name, 0)
        if quantity > 1:
            msg_parts.append(f"剩余库存：{remaining} 个")

        msg_parts.append("━━━━━━━━━━━━━━━")
        return True, "\n".join(msg_parts)

    def _get_base_attributes_for_level(self, player: Player, level_index: int) -> dict:
        """获取当前境界的基础属性（用于计算30%上限）

        Args:
            player: 玩家对象，用于确定修炼类型
            level_index: 境界索引

        Returns:
            基础属性字典
        """
        level_data = self.config_manager.get_level_data(player.cultivation_type)
        # 兜底：如果数据为空，使用灵修配置避免索引错误
        if not level_data:
            level_data = self.config_manager.level_data

        # 越界保护
        if level_data:
            level_index = min(level_index, len(level_data) - 1)
            level_config = level_data[level_index]
        else:
            level_config = {}

        return {
            "lifespan": level_config.get("breakthrough_lifespan_gain", 100),
            "max_spiritual_qi": level_config.get("breakthrough_spiritual_qi_gain", 100),
            "max_blood_qi": level_config.get("breakthrough_blood_qi_gain", 100),
        }

    async def handle_resurrection(self, player: Player) -> Tuple[bool, str]:
        """处理玩家死亡时的回生丹效果

        Args:
            player: 玩家对象

        Returns:
            (是否成功复活, 使用的丹药名称)
        """
        if not player.has_resurrection_pill:
            return False, ""

        pill_name = str(player.has_resurrection_pill)
        if pill_name not in ("回生丹", "涅槃重生丹"):
            pill_name = "回生丹"
        logger.info(f"玩家 {player.user_id} 触发{pill_name}效果")

        # 消耗回生丹效果
        player.has_resurrection_pill = ""

        if pill_name != "涅槃重生丹":
            # 回生丹：所有属性损失15%
            factor = 0.85
            player.lifespan = int(player.lifespan * factor)
            player.experience = int(player.experience * factor)
            player.max_spiritual_qi = int(player.max_spiritual_qi * factor)
            player.spiritual_qi = player.max_spiritual_qi
            player.max_blood_qi = int(player.max_blood_qi * factor)
            player.blood_qi = player.max_blood_qi

        self._ensure_non_negative_attributes(player)

        await self.db.update_player(player)
        return True, pill_name

    def calculate_pill_attribute_effects(self, player: Player) -> dict:
        """计算丹药对属性的影响（乘法加成）

        Args:
            player: 玩家对象

        Returns:
            属性乘法倍率字典
        """
        effects = player.get_active_pill_effects()
        current_time = int(time.time())
        multipliers = {
            "cultivation_speed": 1.0,
        }

        # 累加临时效果
        for effect in effects:
            expiry_time = effect.get("expiry_time", 0)
            if expiry_time > 0 and current_time >= expiry_time:
                continue
            if "cultivation_multiplier" in effect:
                multipliers["cultivation_speed"] += effect["cultivation_multiplier"]

        # 累加永久效果（全局存储，自动迁移旧数据）
        permanent_gains = player.get_permanent_pill_gains()
        global_gains = permanent_gains.get("_global", {})
        if "cultivation_multiplier" in global_gains:
            multipliers["cultivation_speed"] += global_gains["cultivation_multiplier"]

        # 确保倍率不为负
        for key in multipliers:
            multipliers[key] = max(0.0, multipliers[key])

        return multipliers

    def get_breakthrough_modifiers(self, player: Player, target_level_index: int = None) -> dict:
        """获取突破时的临时与永久加成信息

        Args:
            player: 玩家对象
            target_level_index: 目标境界索引，用于过滤特定境界的突破丹效果（None 表示不过滤）
        """
        effects = player.get_active_pill_effects()
        current_time = int(time.time())
        temp_bonus = 0.0
        has_temp_effects = False

        for effect in effects:
            expiry_time = effect.get("expiry_time", 0)
            if expiry_time > 0 and current_time >= expiry_time:
                continue

            subtype = effect.get("subtype", "")
            if subtype in {"breakthrough_boost", "breakthrough_debuff", "death_protection"}:
                # 突破加成丹药需匹配目标境界（无 target_level_index 的为通用丹药，始终生效）
                if subtype == "breakthrough_boost" and target_level_index is not None:
                    effect_target = effect.get("target_level_index")
                    if effect_target is not None and effect_target != target_level_index:
                        continue  # 跳过不匹配的境界特定丹药
                temp_bonus += effect.get("breakthrough_bonus", 0)
                has_temp_effects = True

        permanent_multiplier = 1.0
        permanent_gains = player.get_permanent_pill_gains()
        death_mult = permanent_gains.get("_global", {}).get("death_protection_multiplier", 1.0)
        permanent_multiplier *= death_mult

        return {
            "temp_bonus": temp_bonus,
            "has_temp_effects": has_temp_effects,
            "permanent_death_multiplier": max(0.0, min(1.0, permanent_multiplier)),
        }

    async def consume_breakthrough_boost_only(self, player: Player):
        """突破成功后仅移除突破加成效果，保留死亡保护效果供下次突破使用"""
        effects = player.get_active_pill_effects()
        remaining_effects = [
            effect for effect in effects
            if effect.get("subtype", "") not in {"breakthrough_boost", "breakthrough_debuff"}
        ]

        if len(remaining_effects) != len(effects):
            player.set_active_pill_effects(remaining_effects)
            await self.db.update_player(player)

    async def get_dual_cultivation_bonus(self, player: Player) -> float:
        """获取双修丹药加成值（0 或 1.0，不叠加）"""
        effects = player.get_active_pill_effects()
        current_time = int(time.time())
        for effect in effects:
            expiry_time = effect.get("expiry_time", 0)
            if expiry_time > 0 and current_time >= expiry_time:
                continue
            if effect.get("subtype") == "dual_cultivation_boost":
                return 1.0
        return 0.0

    async def consume_dual_cultivation_bonus(self, player: Player):
        """双修完成后移除双修丹药效果"""
        effects = player.get_active_pill_effects()
        remaining = [e for e in effects if e.get("subtype") != "dual_cultivation_boost"]
        if len(remaining) != len(effects):
            player.set_active_pill_effects(remaining)
            await self.db.update_player(player)

    async def add_pill_to_inventory(self, player: Player, pill_name: str, count: int = 1):
        """添加丹药到背包

        Args:
            player: 玩家对象
            pill_name: 丹药名称
            count: 数量
        """
        inventory = player.get_pills_inventory()
        if pill_name in inventory:
            inventory[pill_name] += count
        else:
            inventory[pill_name] = count
        player.set_pills_inventory(inventory)
        await self.db.update_player(player)

    def get_pill_inventory_display(self, player: Player) -> str:
        """获取丹药背包显示文本

        Args:
            player: 玩家对象

        Returns:
            丹药背包的格式化文本
        """
        inventory = player.get_pills_inventory()
        if not inventory:
            return "你的丹药背包是空的！"

        # 获取永久丹药使用次数
        usage = player.get_permanent_pill_usage()

        lines = ["--- 丹药背包 ---"]
        for pill_name, count in inventory.items():
            pill_data = self.get_pill_by_name(pill_name)
            if pill_data:
                rank = pill_data.get("rank", "未知")
                # 如果是永久丹药，显示已服用次数
                if pill_data.get("effect_type") == "permanent":
                    used = usage.get(pill_name, 0)
                    max_usage = pill_data.get("max_usage", 0)
                    if max_usage > 0:
                        lines.append(f"[{rank}] {pill_name} × {count} (已服用 {used}/{max_usage})")
                    else:
                        lines.append(f"[{rank}] {pill_name} × {count}")
                else:
                    lines.append(f"[{rank}] {pill_name} × {count}")
            else:
                lines.append(f"{pill_name} × {count}")

        lines.append("-" * 20)
        return "\n".join(lines)

    def _apply_periodic_effects(self, player: Player, effect: dict, current_time: int) -> bool:
        """根据时间自动结算持续恢复/扣减"""
        expiry_time = effect.get("expiry_time", 0)
        tick_limit = min(current_time, expiry_time) if expiry_time > 0 else current_time
        last_tick = effect.get("last_tick_time", effect.get("start_time", current_time))

        if tick_limit <= last_tick:
            return False

        elapsed_seconds = tick_limit - last_tick
        minutes = elapsed_seconds // 60
        if minutes <= 0:
            return False

        effect["last_tick_time"] = last_tick + minutes * 60
        changed = False

        if "lifespan_cost_per_minute" in effect:
            total_cost = effect["lifespan_cost_per_minute"] * minutes
            player.lifespan = max(0, player.lifespan - total_cost)
            changed = True

        if "lifespan_regen_per_minute" in effect:
            total_regen = effect["lifespan_regen_per_minute"] * minutes
            player.lifespan += total_regen
            changed = True

        if "spiritual_qi_regen_per_minute" in effect:
            total_qi = effect["spiritual_qi_regen_per_minute"] * minutes
            player.spiritual_qi = min(player.max_spiritual_qi, player.spiritual_qi + total_qi)
            changed = True

        if "blood_qi_regen_per_minute" in effect:
            total_blood = effect["blood_qi_regen_per_minute"] * minutes
            player.blood_qi = min(player.max_blood_qi, player.blood_qi + total_blood)
            changed = True

        if "blood_qi_cost_per_minute" in effect:
            total_cost = effect["blood_qi_cost_per_minute"] * minutes
            player.blood_qi = max(0, player.blood_qi - total_cost)
            changed = True

        if changed:
            self._ensure_non_negative_attributes(player)

        return changed

    def _reset_permanent_pill_effects(self, player: Player) -> bool:
        """清空永久丹药增益并回退属性"""
        permanent_gains = player.get_permanent_pill_gains()
        if not permanent_gains:
            return False

        attr_keys = [
            "lifespan",
            "max_spiritual_qi",
            "max_blood_qi",
        ]

        changed = False
        for gain in permanent_gains.values():
            for attr_key in attr_keys:
                value = gain.get(attr_key, 0)
                if value:
                    delta = int(value)
                    setattr(player, attr_key, getattr(player, attr_key) - delta)
                    changed = True

            if "cultivation_multiplier" in gain:
                gain["cultivation_multiplier"] = 0
            if "death_protection_multiplier" in gain:
                gain["death_protection_multiplier"] = 1.0
            if "flat_atk_bonus" in gain:
                gain["flat_atk_bonus"] = 0

        player.set_permanent_pill_gains({})
        player.set_permanent_pill_usage({})  # 同时清除服用次数记录
        return changed
