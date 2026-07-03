# managers/combat_manager.py
"""
战斗系统管理器 - 处理HP/MP/ATK系统和战斗逻辑
支持会心、闪避、吸血、反伤、连击、格挡、无视防御、生命回复等属性
"""

import random
import math
from typing import Tuple, Dict, Optional, List
from dataclasses import dataclass, field


# 武器/防具特殊属性字段
WEAPON_SPECIAL_ATTRS = ['crit_rate', 'crit_damage', 'armor_pen', 'lifesteal', 'double_hit']
ARMOR_SPECIAL_ATTRS = ['dodge_rate', 'crit_resist', 'reflect_pct', 'block_value', 'hp_regen_pct']


def load_equipment_bonus(player, config_manager) -> dict:
    """从装备数据中读取所有战斗加成（武器+防具）"""
    bonus = {"atk_pct": 0.0, "mp_pct": 0.0, "armor_atk_pct": 0.0, "def_buff": 0.0}
    for attr in WEAPON_SPECIAL_ATTRS + ARMOR_SPECIAL_ATTRS:
        bonus[attr] = 0 if attr not in ('crit_damage', 'hp_regen_pct') else 0.0

    if not config_manager:
        return bonus

    # 武器
    if player.weapon and player.weapon in config_manager.weapons_data:
        wdata = config_manager.weapons_data[player.weapon]
        bonus["atk_pct"] += wdata.get("atk_bonus", 0.0)
        for attr in WEAPON_SPECIAL_ATTRS:
            val = wdata.get(attr, 0)
            if val:
                bonus[attr] += val
        bonus["mp_pct"] += wdata.get("mp_bonus", 0.0)
        # 武器减伤率叠加到 def_buff
        weapon_dmg_red = wdata.get("damage_reduction", 0.0)
        if weapon_dmg_red:
            bonus["def_buff"] += weapon_dmg_red

    # 防具（在 weapons_data 中）
    if player.armor:
        adata = None
        if player.armor in config_manager.weapons_data:
            adata = config_manager.weapons_data[player.armor]
        elif player.armor in config_manager.items_data:
            adata = config_manager.items_data[player.armor]
        if adata:
            bonus["def_buff"] += adata.get("def_buff", 0.0)
            bonus["armor_atk_pct"] += adata.get("atk_bonus", 0.0)
            for attr in ARMOR_SPECIAL_ATTRS:
                val = adata.get(attr, 0)
                if val:
                    bonus[attr] += val

    return bonus


@dataclass
class CombatStats:
    """战斗属性"""
    user_id: str
    name: str  # 道号
    hp: int  # 当前气血
    max_hp: int  # 最大气血
    mp: int  # 当前真元
    max_mp: int  # 最大真元
    atk: int  # 攻击力
    base_mp: int = 0  # 基础真元（心法加成后、装备百分比加成前）
    raw_base_mp: int = 0  # 原始真元（心法加成前，用于技能消耗百分比计算）
    base_def: float = 0.0  # 废弃（保留兼容）
    equip_def: int = 0  # 废弃（保留兼容）
    def_buff: float = 0.0  # 百分比减伤（来自防具 def_buff + 心法 damage_reduction）
    crit_rate: int = 0  # 会心率（百分比）
    exp: int = 0  # 修为（用于计算攻击力）
    # 新增属性
    crit_damage: float = 1.5  # 会心伤害倍率
    armor_pen: int = 0  # 无视防御百分比
    lifesteal: int = 0  # 吸血百分比
    double_hit: int = 0  # 连击百分比
    dodge_rate: int = 0  # 闪避率百分比
    crit_resist: int = 0  # 会心抵抗百分比
    reflect_pct: int = 0  # 反伤百分比
    block_value: int = 0  # 格挡固定值
    hp_regen_pct: float = 0.0  # 每回合生命回复百分比
    damage_reduction: float = 0.0  # 功法减伤率（如 0.1 = 10%减伤）
    # 辅修功法效果
    sub_buff_type: int = 0  # 辅修功法效果类型 (1-13)
    sub_buff_value: int = 0  # 辅修功法主效果数值
    sub_buff_value2: int = 0  # 辅修功法次要效果数值（仅 type=9）
    sub_break_pct: float = 0.0  # 辅修功法破甲比例（仅 type=13）


class CombatManager:
    """战斗系统管理器"""

    @staticmethod
    def calculate_hp_mp(experience: int, hp_buff: float = 0.0, mp_buff: float = 0.0, hp_bonus: float = 0.0, mp_bonus: float = 0.0) -> Tuple[int, int]:
        # nonebot 公式：HP = exp/2, MP = exp
        base_hp = max(1000, int(max(0, experience) / 2 * (1 + hp_buff)))
        hp = int(base_hp * (1 + hp_bonus))
        base_mp = max(100, int(max(0, experience) * (1 + mp_buff)))
        mp = int(base_mp * (1 + mp_bonus))
        return hp, mp

    @staticmethod
    def calculate_base_atk(experience: int) -> int:
        """计算经验基础攻击力（nonebot公式：exp/10）"""
        return max(100, int(max(0, experience) / 10))

    @staticmethod
    def convert_legacy_defense(old_def: int) -> int:
        """将旧版防御值转换为双层公式等比的 equip_def。

        旧公式: old_def / (old_def + 100)
        新公式: ln(equip_def+1)*20 / (ln(equip_def+1)*20 + 200)
        令两者相等，推导出: equip_val = 2 * old_def → equip_def = exp(old_def / 10) - 1
        """
        if old_def <= 0:
            return 0
        return int(math.exp(old_def / 10) - 1)

    @classmethod
    def build_player_combat_stats(cls, player, impart_info, config_manager) -> 'CombatStats':
        """从玩家数据构建 CombatStats（统一入口）"""
        hp_buff = impart_info.impart_hp_per if impart_info else 0.0
        mp_buff = impart_info.impart_mp_per if impart_info else 0.0
        atk_buff = impart_info.impart_atk_per if impart_info else 0.0

        # 获取主修心法加成
        technique_hp_bonus = 0.0
        technique_mp_bonus = 0.0
        technique_atk_bonus = 0.0
        technique_crit_rate = 0
        technique_crit_damage = 0.0
        technique_damage_reduction = 0.0
        if player.main_technique:
            items_data = config_manager.items_data
            technique_data = items_data.get(player.main_technique)
            if technique_data:
                technique_hp_bonus = technique_data.get("hp_bonus", 0.0)
                technique_mp_bonus = technique_data.get("mp_bonus", 0.0)
                technique_atk_bonus = technique_data.get("atk_bonus", 0.0)
                technique_crit_rate = technique_data.get("crit_rate", 0)
                technique_crit_damage = technique_data.get("crit_damage", 0.0)
                technique_damage_reduction = technique_data.get("damage_reduction", 0.0)

        hp, mp = cls.calculate_hp_mp(player.experience, hp_buff, mp_buff, technique_hp_bonus, technique_mp_bonus)
        base_atk = cls.calculate_base_atk(player.experience)

        # 记录心法加成前的原始真元（用于技能消耗百分比计算）
        raw_base_mp = max(100, int(max(0, player.experience) * (1 + mp_buff)))

        equip_bonus = load_equipment_bonus(player, config_manager)

        # 记录基础真元（心法加成后、装备百分比加成前）
        base_mp = mp
        # 武器 mp_bonus 乘算
        mp = int(mp * (1 + equip_bonus.get("mp_pct", 0.0)))

        # nonebot 乘法叠加公式：ATK = base * (practice+1) * (1+technique) * (1+weapon) * (1+armor) + permanent_buff + flat_atk_bonus
        atk_practice_mult = player.atkpractice * 0.04 + 1
        # 从永久丹药增益中读取 flat_atk_bonus
        permanent_gains = player.get_permanent_pill_gains()
        flat_atk_bonus = permanent_gains.get("_global", {}).get("flat_atk_bonus", 0)
        final_atk = int(base_atk * atk_practice_mult * (1 + technique_atk_bonus) * (1 + equip_bonus["atk_pct"]) * (1 + equip_bonus.get("armor_atk_pct", 0.0))) + int(atk_buff) + flat_atk_bonus

        # 获取辅修功法加成
        sub_buff_type = 0
        sub_buff_value = 0
        sub_buff_value2 = 0
        sub_break_pct = 0.0
        if player.sub_technique:
            sub_data = config_manager.sub_techniques_data.get(player.sub_technique)
            if sub_data:
                sub_buff_type = int(sub_data.get("buff_type", 0))
                sub_buff_value = int(sub_data.get("buff", 0))
                sub_buff_value2 = int(sub_data.get("buff2", 0))
                sub_break_pct = float(sub_data.get("break_pct", 0.0))
                # buff_type 1: 攻击力加成
                if sub_buff_type == 1:
                    final_atk = int(final_atk * (1 + sub_buff_value / 100))
                # buff_type 2: 暴击率加成
                # (applied below to crit_rate)
                # buff_type 3: 暴击伤害加成
                # (applied below to crit_damage)
                # buff_type 13: 破甲
                # (applied in combat loop)

        # 防御：百分比减伤（防具 def_buff + 心法 damage_reduction）
        def_buff = min(0.9, equip_bonus.get("def_buff", 0.0) + technique_damage_reduction)

        player.hp = hp
        player.mp = mp
        player.atk = final_atk

        crit_rate = int((impart_info.impart_know_per if impart_info else 0) * 100) + equip_bonus.get("crit_rate", 0) + technique_crit_rate
        # 辅修功法 buff_type 2: 暴击率加成
        if sub_buff_type == 2:
            crit_rate += sub_buff_value

        crit_damage_val = max(1.5, 1.0 + equip_bonus.get("crit_damage", 0) + technique_crit_damage + (impart_info.impart_burst_per if impart_info else 0))
        # 辅修功法 buff_type 3: 暴击伤害加成
        if sub_buff_type == 3:
            crit_damage_val += sub_buff_value / 100

        return CombatStats(
            user_id=player.user_id,
            name=player.user_name if player.user_name else f"道友{player.user_id}",
            hp=hp,
            max_hp=hp,
            mp=mp,
            max_mp=mp,
            base_mp=base_mp,
            raw_base_mp=raw_base_mp,
            atk=final_atk,
            base_def=0.0,
            equip_def=0,
            def_buff=def_buff,
            crit_rate=crit_rate,
            exp=player.experience,
            crit_damage=crit_damage_val,
            armor_pen=equip_bonus.get("armor_pen", 0),
            lifesteal=equip_bonus.get("lifesteal", 0),
            double_hit=equip_bonus.get("double_hit", 0),
            dodge_rate=equip_bonus.get("dodge_rate", 0),
            crit_resist=equip_bonus.get("crit_resist", 0),
            reflect_pct=equip_bonus.get("reflect_pct", 0),
            block_value=equip_bonus.get("block_value", 0),
            hp_regen_pct=equip_bonus.get("hp_regen_pct", 0.0),
            damage_reduction=technique_damage_reduction,
            sub_buff_type=sub_buff_type,
            sub_buff_value=sub_buff_value,
            sub_buff_value2=sub_buff_value2,
            sub_break_pct=sub_break_pct,
        )

    @staticmethod
    def calc_combat_power(stats: CombatStats, max_hp: int, max_mp: int,
                          experience: int = 0, root_speed: float = 1.0, realm_spend: float = 1.0) -> int:
        """计算战力评分。

        nonebot 公式：power = round(exp * root_speed * realm_spend)
        如果提供了 experience/root_speed/realm_spend 则使用 nonebot 公式，
        否则回退到详细战斗公式。
        """
        if experience > 0:
            return round(experience * root_speed * realm_spend)
        # ---- 攻击端 ----
        crit_rate = min(stats.crit_rate, 100)
        crit_mult = 1.0 + crit_rate / 100.0 * max(0.0, stats.crit_damage - 1.0)
        # 连击：每次触发造成半额伤害，等效 ×(1 + chance×0.5)
        double_mult = 1.0 + min(stats.double_hit, 100) / 100.0 * 0.5
        # 穿甲：无视对手装备防御层（约占总防御 85%），线性增伤
        armor_pen_mult = 1.0 + stats.armor_pen * 0.85 / 100.0
        expected_dmg = stats.atk * crit_mult * double_mult * armor_pen_mult

        # ---- 防御端（有效生命值） ----
        # 百分比减伤等效HP乘数（def_buff 已包含防具 + 心法减伤）
        def_buff_mult = 1.0 / max(0.01, 1.0 - min(0.9, stats.def_buff)) if stats.def_buff > 0 else 1.0
        # 闪避等效HP乘数
        dodge_mult = 100.0 / max(1, 100 - min(stats.dodge_rate, 95))
        # 格挡：用参考伤害（≈自身伤害）估算非暴击减伤比例，下限 0.2 防除零
        ref_dmg = stats.atk * crit_mult * double_mult
        block_ratio = stats.block_value / max(ref_dmg, 1)
        block_mult = 1.0 / max(0.2, 1.0 - block_ratio)
        # 会心抵抗：降低对手暴击伤害，参考对手 crit_rate=40%, crit_damage=1.8
        # effective_crit = max(0, 40 - crit_resist)
        # def_crit_mult = 1 + effective_crit/100 × 0.8 → crit_mult_without_resist / crit_mult_with_resist
        ref_crit_mult = 1.0 + 0.40 * 0.8  # 1.32
        eff_crit_mult = 1.0 + max(0, 40 - stats.crit_resist) / 100.0 * 0.8
        crit_resist_mult = ref_crit_mult / max(eff_crit_mult, 0.01)
        # 生命回复
        regen_mult = 1.0 + stats.hp_regen_pct / 100.0
        # 吸血：每回合回复伤害百分比，等效增加生存回合数
        lifesteal_mult = 1.0 + stats.lifesteal / 100.0
        # 反伤：反弹伤害同时削弱攻击者，等效增血（÷2 折算）
        reflect_mult = 1.0 + stats.reflect_pct / 200.0

        effective_hp = max_hp * def_buff_mult * dodge_mult \
            * block_mult * crit_resist_mult * regen_mult * lifesteal_mult * reflect_mult

        # ---- 战力 = log10(攻击 × 生命) ----
        power = expected_dmg * effective_hp
        if power <= 0:
            return 0
        return int(math.log10(power + 1) * 1000)

    @classmethod
    def execute_attack(
        cls,
        attacker: CombatStats,
        defender: CombatStats,
        is_double_hit: bool = False
    ) -> Dict:
        """
        执行一次完整攻击，包含所有特殊属性判定。

        Returns:
            dict with keys: dodged, is_crit, damage, lifesteal_heal, reflect_dmg, triggered_double
        """
        result = {
            "dodged": False, "is_crit": False, "damage": 0,
            "lifesteal_heal": 0, "reflect_dmg": 0, "triggered_double": False
        }

        # 1. 闪避判定
        if random.randint(1, 100) <= defender.dodge_rate:
            result["dodged"] = True
            return result

        # 2. 会心判定（考虑会心抵抗）
        effective_crit_rate = max(0, attacker.crit_rate - defender.crit_resist)
        is_crit = random.randint(1, 100) <= effective_crit_rate
        result["is_crit"] = is_crit

        # 3. 伤害计算（Excel公式：攻击 × 伤害减半0.5 × 会心伤害 × 武器加成1.5 × 浮动）
        crit_mult = attacker.crit_damage if is_crit else 1.0
        damage = int(round(random.uniform(0.95, 1.05), 2) * attacker.atk * 0.5 * crit_mult * 1.5)
        if is_double_hit:
            damage = damage // 2  # 连击伤害减半

        # 4. 百分比减伤（Excel公式：伤害 × (1 - 减伤率 + 穿甲)）
        # 穿甲直接加到减伤率上，可使减伤为负（增伤）
        # sub_break_pct 来自辅修功法破甲效果
        total_reduction = defender.def_buff - attacker.armor_pen / 100 - attacker.sub_break_pct
        if total_reduction != 0:
            damage = max(1, int(damage * (1 - total_reduction)))

        # 6. 格挡
        if defender.block_value > 0 and not is_crit:  # 暴击无视格挡
            damage = max(1, damage - defender.block_value)

        result["damage"] = max(1, damage)

        # 7. 吸血
        if attacker.lifesteal > 0:
            heal = int(damage * attacker.lifesteal / 100)
            if heal > 0:
                attacker.hp = min(attacker.max_hp, attacker.hp + heal)
                result["lifesteal_heal"] = heal

        # 8. 反伤
        if defender.reflect_pct > 0:
            reflect = int(damage * defender.reflect_pct / 100)
            if reflect > 0:
                attacker.hp = max(0, attacker.hp - reflect)
                result["reflect_dmg"] = reflect

        # 9. 连击判定（连击不再触发连击，防递归）
        if not is_double_hit and attacker.double_hit > 0:
            if random.randint(1, 100) <= attacker.double_hit:
                result["triggered_double"] = True

        return result

    @classmethod
    def _apply_hp_regen(cls, combatant: CombatStats):
        """每回合开始时的生命回复"""
        if combatant.hp_regen_pct > 0 and combatant.hp < combatant.max_hp:
            heal = int(combatant.max_hp * combatant.hp_regen_pct / 100)
            combatant.hp = min(combatant.max_hp, combatant.hp + heal)
            return heal
        return 0

    @classmethod
    def player_vs_player(
        cls,
        player1: CombatStats,
        player2: CombatStats,
        combat_type: int = 1,
        p1_skill_name: str = "",
        p2_skill_name: str = "",
        skill_manager=None
    ) -> Dict:
        from .skill_manager import SkillManager, CombatSkillState, format_skill_result

        combat_log = []
        combat_log.append(f"☆━━━━ 战斗开始 ━━━━☆")
        combat_log.append(f"{player1.name} VS {player2.name}")
        combat_log.append(f"{player1.name}：HP {player1.hp}/{player1.max_hp}，ATK {player1.atk}，MP {player1.mp}/{player1.max_mp}")
        combat_log.append(f"{player2.name}：HP {player2.hp}/{player2.max_hp}，ATK {player2.atk}，MP {player2.mp}/{player2.max_mp}")

        has_skills = skill_manager and (p1_skill_name or p2_skill_name)
        if has_skills:
            p1_state = SkillManager.init_combat_state(player1.user_id)
            p2_state = SkillManager.init_combat_state(player2.user_id)
        else:
            p1_state = p2_state = None

        round_num = 0
        max_rounds = 100

        while player1.hp > 0 and player2.hp > 0 and round_num < max_rounds:
            round_num += 1
            combat_log.append(f"-- 第 {round_num} 回合 --")

            if has_skills:
                SkillManager.tick_buffs_and_cooldowns(p1_state)
                SkillManager.tick_buffs_and_cooldowns(p2_state)
                # DOT结算（受防御方减伤影响）
                dot1 = SkillManager.apply_dot_damage(p1_state, player1.def_buff)
                if dot1 > 0:
                    player1.hp = max(0, player1.hp - dot1)
                    combat_log.append(f"{player1.name} 受到持续伤害 {dot1}，剩余 HP: {player1.hp}")
                dot2 = SkillManager.apply_dot_damage(p2_state, player2.def_buff)
                if dot2 > 0:
                    player2.hp = max(0, player2.hp - dot2)
                    combat_log.append(f"{player2.name} 受到持续伤害 {dot2}，剩余 HP: {player2.hp}")

            # 生命回复
            regen1 = cls._apply_hp_regen(player1)
            regen2 = cls._apply_hp_regen(player2)
            if regen1 > 0:
                combat_log.append(f"{player1.name} 回复 {regen1} HP")
            if regen2 > 0:
                combat_log.append(f"{player2.name} 回复 {regen2} HP")

            if player1.hp <= 0 or player2.hp <= 0:
                break

            # 玩家1攻击玩家2
            p1_won = cls._execute_turn_with_skill(
                player1, player2, p1_skill_name, p1_state, p2_state,
                skill_manager, combat_log
            )
            if player2.hp <= 0:
                break

            # 玩家2攻击玩家1
            p2_won = cls._execute_turn_with_skill(
                player2, player1, p2_skill_name, p2_state, p1_state,
                skill_manager, combat_log
            )
            if player1.hp <= 0:
                break

            combat_log.append("")

        # 判断胜负
        if player1.hp > 0:
            winner = player1.user_id
            combat_log.append(f"☆━━━━ {player1.name} 胜利！━━━━☆")
        elif player2.hp > 0:
            winner = player2.user_id
            combat_log.append(f"☆━━━━ {player2.name} 胜利！━━━━☆")
        else:
            winner = "平局"
            combat_log.append(f"☆━━━━ 平局！━━━━☆")

        # 切磋不消耗HP/MP
        if combat_type == 1:
            player1_final_hp = player1.max_hp
            player1_final_mp = player1.max_mp
            player2_final_hp = player2.max_hp
            player2_final_mp = player2.max_mp
        else:
            player1_final_hp = max(1, player1.hp) if player1.hp > 0 else 1
            player1_final_mp = max(0, player1.mp)
            player2_final_hp = max(1, player2.hp) if player2.hp > 0 else 1
            player2_final_mp = max(0, player2.mp)

        return {
            "winner": winner,
            "combat_log": combat_log,
            "player1_final_hp": player1_final_hp,
            "player1_final_mp": player1_final_mp,
            "player2_final_hp": player2_final_hp,
            "player2_final_mp": player2_final_mp,
            "rounds": round_num
        }

    @classmethod
    def player_vs_scarecrow(
        cls,
        player: CombatStats,
        max_rounds: int = 15,
        skill_name: str = "",
        skill_manager=None
    ) -> dict:
        """稻草人练习战：玩家正常输出，稻草人防御为0，每回合固定反伤1"""
        from .skill_manager import SkillManager, CombatSkillState

        # 构造稻草人：100M血，0防御
        scarecrow = CombatStats(
            user_id="scarecrow",
            name="稻草人",
            hp=100_000_000, max_hp=100_000_000,
            mp=0, max_mp=0,
            atk=1,
            base_def=0.0, equip_def=0,
            crit_rate=0, crit_damage=1.0,
            armor_pen=0, lifesteal=0, double_hit=0,
            dodge_rate=0, crit_resist=0,
            reflect_pct=0, block_value=0, hp_regen_pct=0.0,
        )

        total_damage = 0
        round_details = []
        p_state = CombatSkillState(user_id=player.user_id) if skill_name and skill_manager else None

        for round_num in range(1, max_rounds + 1):
            # 技能冷却递减
            if p_state:
                for sk in list(p_state.cooldowns):
                    p_state.cooldowns[sk] = max(0, p_state.cooldowns[sk] - 1)
                    if p_state.cooldowns[sk] <= 0:
                        del p_state.cooldowns[sk]

            # 玩家攻击稻草人
            used_skill = False
            if skill_name and skill_manager and p_state:
                can_use, _ = skill_manager.check_skill_usable(
                    skill_name, p_state, player.mp, player.hp, player.max_hp, player.raw_base_mp
                )
                if can_use and skill_manager.try_activate_skill(skill_name):
                    orig_hp = scarecrow.hp
                    result = skill_manager.execute_skill(
                        skill_name, player, scarecrow, p_state, p_state
                    )
                    dmg = orig_hp - max(0, scarecrow.hp)
                    round_details.append(f"第{round_num}回合：⚡ {skill_name} → {dmg:,} 伤害")
                    # 扣除MP/HP消耗
                    skill_data = skill_manager.get_skill_data(skill_name)
                    if skill_data:
                        mp_cost = skill_data.get("mpcost", 0)
                        if mp_cost > 0:
                            player.mp = max(0, player.mp - int((player.raw_base_mp or player.max_mp) * mp_cost))
                        hp_cost = skill_data.get("hpcost", 0)
                        if hp_cost > 0:
                            player.hp = max(0, player.hp - int(player.max_hp * hp_cost))
                        if skill_data.get("turncost", 0) > 0:
                            p_state.cooldowns[skill_name] = skill_data["turncost"] + 1
                    used_skill = True
                    total_damage += dmg

            if not used_skill:
                atk_result = cls.execute_attack(player, scarecrow)
                dmg = atk_result["damage"]
                # execute_attack 不自动扣血，手动应用
                scarecrow.hp = max(0, scarecrow.hp - dmg)
                # 连击
                if atk_result["triggered_double"] and scarecrow.hp > 0:
                    dbl = cls.execute_attack(player, scarecrow, is_double_hit=True)
                    if not dbl["dodged"]:
                        scarecrow.hp = max(0, scarecrow.hp - dbl["damage"])
                        dmg += dbl["damage"]
                round_details.append(f"第{round_num}回合：\U0001f5e1️ 普通攻击 → {dmg:,} 伤害")
                total_damage += dmg

            # 稻草人固定反伤1
            player.hp = max(0, player.hp - 1)

        lines = [
            f"\U0001f3af 稻草人练习战（{max_rounds}回合）",
            "━━━━━━━━━━━━━━━",
        ]
        lines.extend(round_details)
        lines.append("━━━━━━━━━━━━━━━")
        lines.append(f"\U0001f4ca 统计：")
        lines.append(f"  总伤害：{total_damage:,}")
        lines.append(f"  平均每回合：{total_damage / max_rounds:,.0f} 伤害")
        lines.append(f"  剩余气血：{player.hp:,}")
        lines.append("━━━━━━━━━━━━━━━")

        return {
            "total_damage": total_damage,
            "combat_log": lines,
            "rounds": max_rounds,
        }

    @classmethod
    def _execute_turn_with_skill(
        cls, attacker: CombatStats, defender: CombatStats,
        skill_name: str, attacker_state, defender_state,
        skill_manager, combat_log: list
    ) -> bool:
        """执行一回合（含技能判定），返回defender是否死亡"""
        from .skill_manager import SkillManager, format_skill_result

        # 封禁检查
        if attacker_state and attacker_state.is_sealed:
            combat_log.append(f"{attacker.name} 被封印，无法行动！")
            return defender.hp <= 0

        # 尝试使用技能
        used_skill = False
        if skill_name and skill_manager and attacker_state:
            can_use, _ = skill_manager.check_skill_usable(
                skill_name, attacker_state, attacker.mp, attacker.hp, attacker.max_hp,
                attacker.raw_base_mp
            )
            if can_use and skill_manager.try_activate_skill(skill_name):
                # 闪避判定（技能也受闪避影响）
                if random.randint(1, 100) <= defender.dodge_rate:
                    combat_log.append(f"{attacker.name} 使用【{skill_name}】，但 {defender.name} 闪避了！")
                    # 技能仍消耗MP/HP和进入冷却
                    skill_data = skill_manager.get_skill_data(skill_name)
                    if skill_data:
                        mp_cost = skill_data.get("mpcost", 0)
                        if mp_cost > 0:
                            attacker.mp = max(0, attacker.mp - int((attacker.raw_base_mp or attacker.max_mp) * mp_cost))
                        hp_cost = skill_data.get("hpcost", 0)
                        if hp_cost > 0:
                            attacker.hp = max(0, attacker.hp - int(attacker.max_hp * hp_cost))
                        if skill_data.get("turncost", 0) > 0:
                            attacker_state.cooldowns[skill_name] = skill_data["turncost"] + 1
                    used_skill = True
                    combat_log.append(f"{defender.name} 剩余 HP: {max(0, defender.hp)}")
                else:
                    # 应用buff到攻击者和防御者
                    orig_atk = attacker.atk
                    orig_def_buff = defender.def_buff
                    attacker.atk = SkillManager.apply_buffs_to_atk(attacker.atk, attacker_state)
                    defender.def_buff = SkillManager.apply_buffs_to_def(
                        defender.def_buff, defender_state
                    )

                    result = skill_manager.execute_skill(
                        skill_name, attacker, defender, attacker_state, defender_state
                    )
                    combat_log.append(format_skill_result(attacker.name, defender.name, result))

                    # 扣除MP/HP
                    skill_data = skill_manager.get_skill_data(skill_name)
                    if skill_data:
                        mp_cost = skill_data.get("mpcost", 0)
                        if mp_cost > 0:
                            attacker.mp = max(0, attacker.mp - int((attacker.raw_base_mp or attacker.max_mp) * mp_cost))
                        hp_cost = skill_data.get("hpcost", 0)
                        if hp_cost > 0:
                            hp_loss = int(attacker.max_hp * hp_cost)
                            attacker.hp = max(0, attacker.hp - hp_loss)
                        if skill_data.get("turncost", 0) > 0:
                            attacker_state.cooldowns[skill_name] = skill_data["turncost"] + 1

                    # 技能造成的伤害也触发吸血/反伤
                    total_dmg = result.get("total_damage", result.get("instant_damage", 0))
                    if total_dmg > 0:
                        if attacker.lifesteal > 0:
                            heal = int(total_dmg * attacker.lifesteal / 100)
                            if heal > 0:
                                attacker.hp = min(attacker.max_hp, attacker.hp + heal)
                        if defender.reflect_pct > 0:
                            reflect = int(total_dmg * defender.reflect_pct / 100)
                            if reflect > 0:
                                attacker.hp = max(0, attacker.hp - reflect)

                    # 恢复原始数值
                    attacker.atk = orig_atk
                    defender.def_buff = orig_def_buff

                    used_skill = True
                    # 辅修功法回合后效果（技能攻击）
                    cls._apply_sub_technique_effects(attacker, defender, total_dmg, combat_log)
                    combat_log.append(f"{defender.name} 剩余 HP: {max(0, defender.hp)}")

        # 未使用技能则普通攻击
        if not used_skill:
            cls._execute_turn(attacker, defender, combat_log)

        return defender.hp <= 0

    @classmethod
    def _execute_turn(cls, attacker: CombatStats, defender: CombatStats, combat_log: list) -> Tuple[str, bool]:
        """执行一个玩家的攻击回合，包含连击"""
        result = cls.execute_attack(attacker, defender)

        if result["dodged"]:
            combat_log.append(f"{attacker.name} 发起攻击，但 {defender.name} 闪避了！")
            return "dodge", False

        # 扣血
        defender.hp = max(0, defender.hp - result["damage"])

        # 攻击日志
        parts = []
        if result["is_crit"]:
            parts.append(f"{attacker.name} 发起会心一击，造成 {result['damage']} 点伤害！")
        else:
            parts.append(f"{attacker.name} 发起攻击，造成 {result['damage']} 点伤害")

        if result["lifesteal_heal"] > 0:
            parts.append(f"吸血回复 {result['lifesteal_heal']} HP")
        if result["reflect_dmg"] > 0:
            parts.append(f"反伤 {result['reflect_dmg']} 伤害")

        combat_log.append("，".join(parts))
        combat_log.append(f"{defender.name} 剩余 HP: {max(0, defender.hp)}")

        # 连击
        if result["triggered_double"] and defender.hp > 0:
            double_result = cls.execute_attack(attacker, defender, is_double_hit=True)
            if not double_result["dodged"]:
                defender.hp = max(0, defender.hp - double_result["damage"])
                combat_log.append(f"{attacker.name} 触发连击！追加 {double_result['damage']} 点伤害")
                combat_log.append(f"{defender.name} 剩余 HP: {max(0, defender.hp)}")
            else:
                combat_log.append(f"{attacker.name} 触发连击，但被闪避！")

        # 辅修功法回合后效果
        cls._apply_sub_technique_effects(attacker, defender, result["damage"], combat_log)

        return "hit", defender.hp <= 0

    @classmethod
    def _apply_sub_technique_effects(cls, attacker: CombatStats, defender: CombatStats,
                                      damage: int, combat_log: list):
        """应用辅修功法的回合后效果"""
        if attacker.sub_buff_type == 0:
            return

        bt = attacker.sub_buff_type
        bv = attacker.sub_buff_value
        bv2 = attacker.sub_buff_value2

        if bt == 4:  # 气血回复
            heal = int(attacker.max_hp * bv / 100)
            attacker.hp = min(attacker.max_hp, attacker.hp + heal)
            combat_log.append(f"{attacker.name} 辅修功法回复 {heal} 气血")
        elif bt == 5:  # 真元回复
            heal = int(attacker.max_mp * bv / 100)
            attacker.mp = min(attacker.max_mp, attacker.mp + heal)
            combat_log.append(f"{attacker.name} 辅修功法回复 {heal} 真元")
        elif bt == 6:  # 气血吸取
            steal = int(damage * bv / 100)
            if steal > 0:
                attacker.hp = min(attacker.max_hp, attacker.hp + steal)
                combat_log.append(f"{attacker.name} 吸取 {steal} 气血")
        elif bt == 7:  # 真元吸取
            steal = int(damage * bv / 100)
            if steal > 0:
                attacker.mp = min(attacker.max_mp, attacker.mp + steal)
                combat_log.append(f"{attacker.name} 吸取 {steal} 真元")
        elif bt == 8:  # 中毒
            poison = int(defender.max_hp * bv / 100)
            if poison > 0:
                defender.hp = max(0, defender.hp - poison)
                combat_log.append(f"{defender.name} 中毒损失 {poison} 气血")
        elif bt == 9:  # 双吸
            hp_steal = int(damage * bv / 100)
            mp_steal = int(damage * bv2 / 100)
            if hp_steal > 0:
                attacker.hp = min(attacker.max_hp, attacker.hp + hp_steal)
            if mp_steal > 0:
                attacker.mp = min(attacker.max_mp, attacker.mp + mp_steal)
            if hp_steal > 0 or mp_steal > 0:
                combat_log.append(f"{attacker.name} 双吸 {hp_steal} 气血 {mp_steal} 真元")

    @classmethod
    def player_vs_boss(
        cls,
        player: CombatStats,
        boss: CombatStats,
        player_skill_name: str = "",
        skill_manager=None,
        boss_level_index: int = 0
    ) -> Dict:
        from .skill_manager import SkillManager, format_skill_result

        combat_log = []
        combat_log.append(f"☆━━━━ Boss战开始 ━━━━☆")
        combat_log.append(f"{player.name} 挑战 {boss.name}")
        combat_log.append(f"{player.name}：HP {player.hp}/{player.max_hp}，ATK {player.atk}，MP {player.mp}/{player.max_mp}")
        combat_log.append(f"{boss.name}：HP {boss.hp}/{boss.max_hp}，ATK {boss.atk}")
        combat_log.append("")

        # ── Boss特殊能力系统 ──
        # 根据 level_index 确定Buff档位
        boss_buff = {
            "atk": 0.0,           # boss_zs: Boss攻击增幅
            "crit": 0.0,          # boss_hx: Boss会心率增幅
            "crit_dmg": 0.0,      # boss_bs: Boss会心伤害增幅
            "reduce_lifesteal": 0.0,  # boss_xx: 降低玩家吸血
            "reduce_atk": 0.0,    # boss_jg: 降低玩家攻击
            "reduce_crit": 0.0,   # boss_jh: 降低玩家会心率
            "reduce_crit_dmg": 0.0,  # boss_jb: 降低玩家会心伤害
        }

        # 档位定义: (atk, crit, crit_dmg, reduce_atk, reduce_crit, reduce_crit_dmg, reduce_ls_min, reduce_ls_max)
        _BOSS_BUFF_TIERS = [
            (0.3, 0.1, 0.5, 0.3, 0.3, 0.5, 0.05, 1.0),   # Tier 2: 神火-天神 (24-33)
            (0.5, 0.25, 0.9, 0.45, 0.45, 0.8, 0.2, 1.0),  # Tier 3: 虚道-遁一 (36-42)
            (0.7, 0.45, 1.3, 0.55, 0.6, 1.0, 0.4, 1.0),   # Tier 4: 至尊-真仙 (45-48)
            (0.9, 0.6, 1.7, 0.62, 0.67, 1.2, 0.6, 1.0),   # Tier 5: 仙王-仙帝 (51-57)
        ]

        # 确定档位
        tier_idx = -1
        if 24 <= boss_level_index <= 33:
            tier_idx = 0
        elif 36 <= boss_level_index <= 42:
            tier_idx = 1
        elif 45 <= boss_level_index <= 48:
            tier_idx = 2
        elif 51 <= boss_level_index <= 57:
            tier_idx = 3

        boss_has_buff = tier_idx >= 0

        if boss_has_buff:
            t = _BOSS_BUFF_TIERS[tier_idx]
            atk_val, crit_val, cdmg_val, r_atk_val, r_crit_val, r_cdmg_val, r_ls_min, r_ls_max = t

            # Slot 1: 进攻型Buff (25% each)
            slot1 = random.randint(1, 100)
            if slot1 <= 25:
                boss_buff["atk"] = atk_val
            elif slot1 <= 50:
                boss_buff["crit"] = crit_val
            elif slot1 <= 75:
                boss_buff["crit_dmg"] = cdmg_val
            else:
                boss_buff["reduce_lifesteal"] = round(random.uniform(r_ls_min, r_ls_max), 2)

            # Slot 2: 削弱型Buff (25% each)
            slot2 = random.randint(1, 100)
            if slot2 <= 25:
                boss_buff["reduce_atk"] = r_atk_val
            elif slot2 <= 50:
                boss_buff["reduce_crit"] = r_crit_val
            elif slot2 <= 75:
                boss_buff["reduce_crit_dmg"] = r_cdmg_val
            else:
                # Slot 2 第4选项: 均匀分配给3个削弱属性
                boss_buff["reduce_atk"] = r_atk_val
                boss_buff["reduce_crit"] = r_crit_val
                boss_buff["reduce_crit_dmg"] = r_cdmg_val

            # 显示Boss Buff信息
            buff_names = []
            if boss_buff["atk"] > 0:
                buff_names.append(f"攻击+{int(boss_buff['atk']*100)}%")
            if boss_buff["crit"] > 0:
                buff_names.append(f"会心+{int(boss_buff['crit']*100)}%")
            if boss_buff["crit_dmg"] > 0:
                buff_names.append(f"会伤+{boss_buff['crit_dmg']:.1f}")
            if boss_buff["reduce_lifesteal"] > 0:
                buff_names.append(f"吸血-{int(boss_buff['reduce_lifesteal']*100)}%")
            if boss_buff["reduce_atk"] > 0:
                buff_names.append(f"降攻-{int(boss_buff['reduce_atk']*100)}%")
            if boss_buff["reduce_crit"] > 0:
                buff_names.append(f"降会心-{int(boss_buff['reduce_crit']*100)}%")
            if boss_buff["reduce_crit_dmg"] > 0:
                buff_names.append(f"降会伤-{boss_buff['reduce_crit_dmg']:.1f}")
            if buff_names:
                combat_log.append(f"⚠ {boss.name} 携带特殊能力：{'、'.join(buff_names)}")
                combat_log.append("")

        # 保存玩家原始属性用于战后恢复
        orig_player_atk = player.atk
        orig_player_crit_rate = player.crit_rate
        orig_player_crit_damage = player.crit_damage
        orig_player_lifesteal = player.lifesteal

        # Excel规则：打怪伤害翻倍（所有伤害直接×2）
        player.atk = player.atk * 2

        # 应用Boss削弱Buff到玩家（临时，仅本次战斗）
        if boss_buff["reduce_atk"] > 0:
            player.atk = int(player.atk * (1 - boss_buff["reduce_atk"]))
        if boss_buff["reduce_crit"] > 0:
            player.crit_rate = max(0, player.crit_rate - int(boss_buff["reduce_crit"] * 100))
        if boss_buff["reduce_crit_dmg"] > 0:
            player.crit_damage = max(1.0, player.crit_damage - boss_buff["reduce_crit_dmg"])
        if boss_buff["reduce_lifesteal"] > 0:
            player.lifesteal = int(player.lifesteal * (1 - boss_buff["reduce_lifesteal"]))

        # 应用Boss进攻Buff到Boss（保存原始值以便战后恢复）
        orig_boss_atk = boss.atk
        orig_boss_crit_rate = boss.crit_rate
        orig_boss_crit_damage = boss.crit_damage
        if boss_buff["atk"] > 0:
            boss.atk = int(boss.atk * (1 + boss_buff["atk"]))
        if boss_buff["crit"] > 0:
            boss.crit_rate = min(100, boss.crit_rate + int(boss_buff["crit"] * 100))
        if boss_buff["crit_dmg"] > 0:
            boss.crit_damage = boss.crit_damage + boss_buff["crit_dmg"]

        has_skill = skill_manager and player_skill_name
        if has_skill:
            p_state = SkillManager.init_combat_state(player.user_id)
            boss_state = SkillManager.init_combat_state(boss.user_id)
        else:
            p_state = boss_state = None

        round_num = 0
        max_rounds = 100
        total_damage_dealt = 0

        try:
            while player.hp > 0 and boss.hp > 0 and round_num < max_rounds:
                round_num += 1
                combat_log.append(f"-- 第 {round_num} 回合 --")

                if has_skill:
                    SkillManager.tick_buffs_and_cooldowns(p_state)
                    SkillManager.tick_buffs_and_cooldowns(boss_state)
                    dot = SkillManager.apply_dot_damage(p_state, player.def_buff)
                    if dot > 0:
                        player.hp = max(0, player.hp - dot)
                        combat_log.append(f"{player.name} 受到持续伤害 {dot}，剩余 HP: {player.hp}")
                    boss_dot = SkillManager.apply_dot_damage(boss_state, boss.def_buff)
                    if boss_dot > 0:
                        boss.hp = max(0, boss.hp - boss_dot)
                        combat_log.append(f"{boss.name} 受到持续伤害 {boss_dot}，剩余 HP: {max(0, boss.hp)}")

                regen = cls._apply_hp_regen(player)
                if regen > 0:
                    combat_log.append(f"{player.name} 回复 {regen} HP")

                if player.hp <= 0:
                    break

                # 玩家攻击Boss（含技能判定）
                used_skill = False
                if has_skill and p_state:
                    if not p_state.is_sealed:
                        can_use, _ = skill_manager.check_skill_usable(
                            player_skill_name, p_state, player.mp, player.hp, player.max_hp,
                            player.raw_base_mp
                        )
                        if can_use and skill_manager.try_activate_skill(player_skill_name):
                            orig_atk = player.atk
                            orig_def_buff = boss.def_buff
                            player.atk = SkillManager.apply_buffs_to_atk(player.atk, p_state)
                            boss.def_buff = SkillManager.apply_buffs_to_def(
                                boss.def_buff, boss_state
                            )

                            result = skill_manager.execute_skill(
                                player_skill_name, player, boss, p_state, boss_state
                            )
                            combat_log.append(format_skill_result(player.name, boss.name, result))

                            sd = skill_manager.get_skill_data(player_skill_name)
                            if sd:
                                mp_cost = sd.get("mpcost", 0)
                                if mp_cost > 0:
                                    player.mp = max(0, player.mp - int((player.raw_base_mp or player.max_mp) * mp_cost))
                                hp_cost = sd.get("hpcost", 0)
                                if hp_cost > 0:
                                    player.hp = max(0, player.hp - int(player.max_hp * hp_cost))
                                if sd.get("turncost", 0) > 0:
                                    p_state.cooldowns[player_skill_name] = sd["turncost"] + 1

                            total_dmg = result.get("total_damage", result.get("instant_damage", 0))
                            total_damage_dealt += total_dmg
                            if total_dmg > 0:
                                if player.lifesteal > 0:
                                    heal = int(total_dmg * player.lifesteal / 100)
                                    if heal > 0:
                                        player.hp = min(player.max_hp, player.hp + heal)
                                if boss.reflect_pct > 0:
                                    reflect = int(total_dmg * boss.reflect_pct / 100)
                                    if reflect > 0:
                                        player.hp = max(0, player.hp - reflect)

                            player.atk = orig_atk
                            boss.def_buff = orig_def_buff
                            used_skill = True
                            combat_log.append(f"{boss.name} 剩余 HP: {max(0, boss.hp)}")
                    else:
                        combat_log.append(f"{player.name} 被封印，无法行动！")

                normal_dmg = 0
                if not used_skill:
                    result = cls.execute_attack(player, boss)
                    if result["dodged"]:
                        combat_log.append(f"{player.name} 攻击未命中")
                    else:
                        # 扣血
                        boss.hp = max(0, boss.hp - result["damage"])
                        normal_dmg = result["damage"]
                        dmg_text = "会心一击" if result["is_crit"] else "攻击"
                        combat_log.append(f"{player.name} 发起{dmg_text}，造成 {result['damage']} 点伤害")
                        total_damage_dealt += result["damage"]
                        if result["lifesteal_heal"] > 0:
                            combat_log.append(f"吸血回复 {result['lifesteal_heal']} HP")
                        if result["triggered_double"]:
                            double = cls.execute_attack(player, boss, is_double_hit=True)
                            if not double["dodged"]:
                                boss.hp = max(0, boss.hp - double["damage"])
                                normal_dmg += double["damage"]
                                combat_log.append(f"连击追加 {double['damage']} 点伤害")
                                total_damage_dealt += double["damage"]

                # 辅修功法回合后效果（技能和普通攻击都生效）
                atk_dmg = total_dmg if used_skill else normal_dmg
                cls._apply_sub_technique_effects(player, boss, atk_dmg, combat_log)
                combat_log.append(f"{boss.name} 剩余 HP: {max(0, boss.hp)}")

                if boss.hp <= 0:
                    break

                # Boss攻击（含特殊能力判定）
                if boss_has_buff:
                    boss_roll = random.randint(1, 100)
                    if boss_roll <= 8:
                        # 紫玄掌: 5x伤害 + 30%玩家当前气血
                        raw_dmg = int(boss.atk * 5)
                        hp_bonus = int(player.hp * 0.3)
                        effective_def = min(0.9, player.def_buff)
                        damage = int((raw_dmg + hp_bonus) * (1 - effective_def))
                        player.hp = max(0, player.hp - damage)
                        combat_log.append(f"🔥 {boss.name}：紫玄掌！！紫星河！！！造成 {damage} 伤害")
                    elif boss_roll <= 16:
                        # 子龙朱雀: 3x伤害，无视50%防御
                        raw_dmg = int(boss.atk * 3)
                        effective_def = min(0.9, player.def_buff) * 0.5
                        damage = int(raw_dmg * (1 - effective_def))
                        player.hp = max(0, player.hp - damage)
                        combat_log.append(f"🐉 {boss.name}：子龙朱雀！！！穿透护甲！造成 {damage} 伤害")
                    else:
                        # 普通攻击（Boss已获得进攻Buff加成）
                        cls._execute_turn(boss, player, combat_log)
                else:
                    # 无特殊能力的Boss：普通攻击
                    cls._execute_turn(boss, player, combat_log)
                combat_log.append("")

        finally:
            # 恢复玩家原始属性（即使异常也必须恢复）
            player.atk = orig_player_atk
            player.crit_rate = orig_player_crit_rate
            player.crit_damage = orig_player_crit_damage
            player.lifesteal = orig_player_lifesteal

            # 恢复Boss原始属性
            boss.atk = orig_boss_atk
            boss.crit_rate = orig_boss_crit_rate
            boss.crit_damage = orig_boss_crit_damage

        if boss.hp <= 0:
            winner = player.user_id
            combat_log.append(f"☆━━━━ {player.name} 击败了 {boss.name}！━━━━☆")
            reward = boss.exp
        elif player.hp <= 0:
            winner = boss.user_id
            combat_log.append(f"☆━━━━ {player.name} 被 {boss.name} 击败！━━━━☆")
            damage_ratio = min(1.0, total_damage_dealt / max(1, boss.max_hp))
            reward = int(boss.exp * damage_ratio)
            combat_log.append(f"虽败犹荣，获得 {reward} 灵石作为奖励")
        else:
            winner = "平局"
            reward = 0
            combat_log.append(f"☆━━━━ 战斗超时，平局！━━━━☆")

        return {
            "winner": winner,
            "combat_log": combat_log,
            "player_final_hp": max(1, player.hp),
            "player_final_mp": max(0, player.mp),
            "boss_final_hp": max(0, boss.hp),
            "reward": reward,
            "rounds": round_num
        }

