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
    bonus = {"atk": 0, "atk_pct": 0.0, "defense": 0}
    for attr in WEAPON_SPECIAL_ATTRS + ARMOR_SPECIAL_ATTRS:
        bonus[attr] = 0 if attr not in ('crit_damage', 'hp_regen_pct') else 0.0

    if not config_manager:
        return bonus

    # 武器
    if player.weapon and player.weapon in config_manager.weapons_data:
        wdata = config_manager.weapons_data[player.weapon]
        bonus["atk_pct"] += wdata.get("atk_bonus", 0.0)
        bonus["atk"] += wdata.get("physical_damage", 0)
        bonus["atk"] += wdata.get("magic_damage", 0)
        bonus["defense"] += wdata.get("physical_defense", 0)
        bonus["defense"] += wdata.get("magic_defense", 0)
        for attr in WEAPON_SPECIAL_ATTRS:
            val = wdata.get(attr, 0)
            if val:
                bonus[attr] += val

    # 防具（在 weapons_data 中）
    if player.armor:
        adata = None
        if player.armor in config_manager.weapons_data:
            adata = config_manager.weapons_data[player.armor]
        elif player.armor in config_manager.items_data:
            adata = config_manager.items_data[player.armor]
        if adata:
            bonus["defense"] += adata.get("physical_defense", 0)
            bonus["defense"] += adata.get("magic_defense", 0)
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
    base_def: float = 0.0  # 经验基础防御（用于双层减伤第一层）
    equip_def: int = 0  # 装备+突破防御（用于双层减伤第二层）
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


class CombatManager:
    """战斗系统管理器"""

    @staticmethod
    def calculate_hp_mp(experience: int, hp_buff: float = 0.0, mp_buff: float = 0.0, hp_bonus: float = 0.0) -> Tuple[int, int]:
        base_hp = max(200, int(max(0, experience) ** 0.50 * 2 * (1 + hp_buff)) + 200)
        # 应用心法生命加成
        hp = int(base_hp * (1 + hp_bonus))
        mp = max(10, int(max(0, experience) ** 0.50 * 1 * (1 + mp_buff)))
        return hp, mp

    @staticmethod
    def calculate_base_atk(experience: int) -> int:
        """计算经验基础攻击力（不含装备/突破加成）"""
        return max(1, int(max(0, experience) ** 0.42))

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
        technique_atk_bonus = 0
        if player.main_technique:
            items_data = config_manager.items_data
            technique_data = items_data.get(player.main_technique)
            if technique_data:
                technique_hp_bonus = technique_data.get("hp_bonus", 0.0)
                technique_atk_bonus = technique_data.get("atk_bonus", 0)

        hp, mp = cls.calculate_hp_mp(player.experience, hp_buff, mp_buff, technique_hp_bonus)
        base_atk = cls.calculate_base_atk(player.experience)

        equip_bonus = load_equipment_bonus(player, config_manager)

        breakthrough_atk = player.physical_damage + player.magic_damage
        # 添加心法攻击加成
        final_atk = int(base_atk * (1 + equip_bonus["atk_pct"] + atk_buff)) + breakthrough_atk + equip_bonus["atk"] + technique_atk_bonus

        base_def = math.log(player.experience + 1) * 10
        equip_def = (player.physical_defense + player.magic_defense) + equip_bonus["defense"]

        player.hp = hp
        player.mp = mp
        player.atk = final_atk

        crit_rate = int((impart_info.impart_know_per if impart_info else 0) * 100) + equip_bonus.get("crit_rate", 0)

        return CombatStats(
            user_id=player.user_id,
            name=player.user_name if player.user_name else f"道友{player.user_id}",
            hp=hp,
            max_hp=hp,
            mp=mp,
            max_mp=mp,
            atk=final_atk,
            base_def=base_def,
            equip_def=equip_def,
            crit_rate=crit_rate,
            exp=player.experience,
            crit_damage=max(1.5, equip_bonus.get("crit_damage", 0)),
            armor_pen=equip_bonus.get("armor_pen", 0),
            lifesteal=equip_bonus.get("lifesteal", 0),
            double_hit=equip_bonus.get("double_hit", 0),
            dodge_rate=equip_bonus.get("dodge_rate", 0),
            crit_resist=equip_bonus.get("crit_resist", 0),
            reflect_pct=equip_bonus.get("reflect_pct", 0),
            block_value=equip_bonus.get("block_value", 0),
            hp_regen_pct=equip_bonus.get("hp_regen_pct", 0.0),
        )

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

        # 3. 伤害计算
        crit_mult = attacker.crit_damage if is_crit else 1.0
        damage = int(round(random.uniform(0.95, 1.05), 2) * attacker.atk * crit_mult)
        if is_double_hit:
            damage = damage // 2  # 连击伤害减半

        # 4. 双层减伤
        base_def = defender.base_def  # ln(exp+1) * 10
        equip_def = math.log(defender.equip_def + 1) * 20 if defender.equip_def > 0 else 0
        # 穿甲影响装备防御层
        if attacker.armor_pen > 0:
            equip_def = equip_def * (1 - attacker.armor_pen / 100)
        base_reduction = base_def / (base_def + 500) if base_def > 0 else 0
        equip_reduction = equip_def / (equip_def + 200) if equip_def > 0 else 0
        total_reduction = 1 - (1 - base_reduction) * (1 - equip_reduction)
        if total_reduction > 0:
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
                # DOT结算
                dot1 = SkillManager.apply_dot_damage(p1_state)
                if dot1 > 0:
                    player1.hp = max(0, player1.hp - dot1)
                    combat_log.append(f"{player1.name} 受到持续伤害 {dot1}，剩余 HP: {player1.hp}")
                dot2 = SkillManager.apply_dot_damage(p2_state)
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
            player1_final_mp = player1.mp
            player2_final_hp = max(1, player2.hp) if player2.hp > 0 else 1
            player2_final_mp = player2.mp

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
                attacker.max_mp
            )
            if can_use and skill_manager.try_activate_skill(skill_name):
                # 应用buff到攻击者和防御者
                orig_atk = attacker.atk
                orig_def_base = defender.base_def
                orig_def_equip = defender.equip_def
                attacker.atk = SkillManager.apply_buffs_to_atk(attacker.atk, attacker_state)
                defender.base_def, defender.equip_def = SkillManager.apply_buffs_to_def(
                    defender.base_def, defender.equip_def, defender_state
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
                        attacker.mp -= int(attacker.max_mp * mp_cost)
                    hp_cost = skill_data.get("hpcost", 0)
                    if hp_cost > 0:
                        hp_loss = int(attacker.max_hp * hp_cost)
                        attacker.hp = max(0, attacker.hp - hp_loss)
                    if skill_data.get("turncost", 0) > 0:
                        attacker_state.cooldowns[skill_name] = skill_data["turncost"]

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
                defender.base_def = orig_def_base
                defender.equip_def = orig_def_equip

                used_skill = True
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
                combat_log.append(f"{attacker.name} 触发连击！追加 {double_result['damage']} 点伤害")
                combat_log.append(f"{defender.name} 剩余 HP: {max(0, defender.hp)}")
            else:
                combat_log.append(f"{attacker.name} 触发连击，但被闪避！")

        return "hit", defender.hp <= 0

    @classmethod
    def player_vs_boss(
        cls,
        player: CombatStats,
        boss: CombatStats,
        player_skill_name: str = "",
        skill_manager=None
    ) -> Dict:
        from .skill_manager import SkillManager, format_skill_result

        combat_log = []
        combat_log.append(f"☆━━━━ Boss战开始 ━━━━☆")
        combat_log.append(f"{player.name} 挑战 {boss.name}")
        combat_log.append(f"{player.name}：HP {player.hp}/{player.max_hp}，ATK {player.atk}，MP {player.mp}/{player.max_mp}")
        combat_log.append(f"{boss.name}：HP {boss.hp}/{boss.max_hp}，ATK {boss.atk}")
        combat_log.append("")

        has_skill = skill_manager and player_skill_name
        if has_skill:
            p_state = SkillManager.init_combat_state(player.user_id)
            boss_state = SkillManager.init_combat_state(boss.user_id)
        else:
            p_state = boss_state = None

        round_num = 0
        max_rounds = 100
        total_damage_dealt = 0

        while player.hp > 0 and boss.hp > 0 and round_num < max_rounds:
            round_num += 1
            combat_log.append(f"-- 第 {round_num} 回合 --")

            if has_skill:
                SkillManager.tick_buffs_and_cooldowns(p_state)
                SkillManager.tick_buffs_and_cooldowns(boss_state)
                dot = SkillManager.apply_dot_damage(p_state)
                if dot > 0:
                    player.hp = max(0, player.hp - dot)
                    combat_log.append(f"{player.name} 受到持续伤害 {dot}，剩余 HP: {player.hp}")

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
                        player.max_mp
                    )
                    if can_use and skill_manager.try_activate_skill(player_skill_name):
                        orig_atk = player.atk
                        orig_def_base = boss.base_def
                        orig_def_equip = boss.equip_def
                        player.atk = SkillManager.apply_buffs_to_atk(player.atk, p_state)
                        boss.base_def, boss.equip_def = SkillManager.apply_buffs_to_def(
                            boss.base_def, boss.equip_def, boss_state
                        )

                        result = skill_manager.execute_skill(
                            player_skill_name, player, boss, p_state, boss_state
                        )
                        combat_log.append(format_skill_result(player.name, boss.name, result))

                        sd = skill_manager.get_skill_data(player_skill_name)
                        if sd:
                            mp_cost = sd.get("mpcost", 0)
                            if mp_cost > 0:
                                player.mp -= int(player.max_mp * mp_cost)
                            hp_cost = sd.get("hpcost", 0)
                            if hp_cost > 0:
                                player.hp = max(0, player.hp - int(player.max_hp * hp_cost))
                            if sd.get("turncost", 0) > 0:
                                p_state.cooldowns[player_skill_name] = sd["turncost"]

                        total_dmg = result.get("total_damage", result.get("instant_damage", 0))
                        total_damage_dealt += total_dmg
                        if total_dmg > 0 and player.lifesteal > 0:
                            heal = int(total_dmg * player.lifesteal / 100)
                            if heal > 0:
                                player.hp = min(player.max_hp, player.hp + heal)

                        player.atk = orig_atk
                        boss.base_def = orig_def_base
                        boss.equip_def = orig_def_equip
                        used_skill = True
                        combat_log.append(f"{boss.name} 剩余 HP: {max(0, boss.hp)}")
                else:
                    combat_log.append(f"{player.name} 被封印，无法行动！")

            if not used_skill:
                result = cls.execute_attack(player, boss)
                if result["dodged"]:
                    combat_log.append(f"{player.name} 攻击未命中")
                else:
                    dmg_text = "会心一击" if result["is_crit"] else "攻击"
                    combat_log.append(f"{player.name} 发起{dmg_text}，造成 {result['damage']} 点伤害")
                    total_damage_dealt += result["damage"]
                    if result["lifesteal_heal"] > 0:
                        combat_log.append(f"吸血回复 {result['lifesteal_heal']} HP")
                    if result["triggered_double"]:
                        double = cls.execute_attack(player, boss, is_double_hit=True)
                        if not double["dodged"]:
                            combat_log.append(f"连击追加 {double['damage']} 点伤害")
                            total_damage_dealt += double["damage"]
                combat_log.append(f"{boss.name} 剩余 HP: {max(0, boss.hp)}")

            if boss.hp <= 0:
                break

            # Boss攻击
            cls._execute_turn(boss, player, combat_log)
            combat_log.append("")

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
            "player_final_mp": player.mp,
            "boss_final_hp": max(0, boss.hp),
            "reward": reward,
            "rounds": round_num
        }

