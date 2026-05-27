# managers/combat_manager.py
"""
战斗系统管理器 - 处理HP/MP/ATK系统和战斗逻辑
支持会心、闪避、吸血、反伤、连击、格挡、无视防御、生命回复等属性
"""

import random
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
    defense: int = 0  # 防御力
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
    def calculate_hp_mp(experience: int, hp_buff: float = 0.0, mp_buff: float = 0.0) -> Tuple[int, int]:
        base_hp = experience // 2
        base_mp = experience
        hp = int(base_hp * (1 + hp_buff))
        mp = int(base_mp * (1 + mp_buff))
        return hp, mp

    @staticmethod
    def calculate_atk(experience: int, atkpractice: int = 0, atk_buff: float = 0.0) -> int:
        base_atk = experience // 10
        practice_bonus = atkpractice * 0.04
        total_atk = int(base_atk * (1 + practice_bonus + atk_buff))
        return max(total_atk, 1)

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

        # 4. 无视防御
        effective_def = defender.defense
        if attacker.armor_pen > 0:
            effective_def = int(defender.defense * (1 - attacker.armor_pen / 100))

        # 5. 减伤
        if effective_def > 0:
            reduction = effective_def / (effective_def + 100)
            damage = max(1, int(damage * (1 - reduction)))

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
        combat_type: int = 1
    ) -> Dict:
        combat_log = []
        combat_log.append(f"☆━━━━ 战斗开始 ━━━━☆")
        combat_log.append(f"{player1.name} VS {player2.name}")
        combat_log.append(f"{player1.name}：HP {player1.hp}/{player1.max_hp}，ATK {player1.atk}")
        combat_log.append(f"{player2.name}：HP {player2.hp}/{player2.max_hp}，ATK {player2.atk}")
        combat_log.append("")

        round_num = 0
        max_rounds = 100

        while player1.hp > 0 and player2.hp > 0 and round_num < max_rounds:
            round_num += 1
            combat_log.append(f"-- 第 {round_num} 回合 --")

            # 生命回复
            regen1 = cls._apply_hp_regen(player1)
            regen2 = cls._apply_hp_regen(player2)
            if regen1 > 0:
                combat_log.append(f"{player1.name} 回复 {regen1} HP")
            if regen2 > 0:
                combat_log.append(f"{player2.name} 回复 {regen2} HP")

            # 玩家1攻击玩家2
            attack_log, p1_won = cls._execute_turn(player1, player2, combat_log)
            if player2.hp <= 0:
                break

            # 玩家2攻击玩家1
            attack_log, p2_won = cls._execute_turn(player2, player1, combat_log)
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
        boss: CombatStats
    ) -> Dict:
        combat_log = []
        combat_log.append(f"☆━━━━ Boss战开始 ━━━━☆")
        combat_log.append(f"{player.name} 挑战 {boss.name}")
        combat_log.append(f"{player.name}：HP {player.hp}/{player.max_hp}，ATK {player.atk}")
        combat_log.append(f"{boss.name}：HP {boss.hp}/{boss.max_hp}，ATK {boss.atk}")
        combat_log.append("")

        round_num = 0
        max_rounds = 100
        total_damage_dealt = 0

        while player.hp > 0 and boss.hp > 0 and round_num < max_rounds:
            round_num += 1
            combat_log.append(f"-- 第 {round_num} 回合 --")

            # 玩家生命回复
            regen = cls._apply_hp_regen(player)
            if regen > 0:
                combat_log.append(f"{player.name} 回复 {regen} HP")

            # 玩家攻击Boss（Boss无闪避/反伤/格挡等，只用defense）
            result = cls.execute_attack(player, boss)
            if result["dodged"]:
                combat_log.append(f"{player.name} 攻击未命中")
            else:
                dmg_text = f"会心一击" if result["is_crit"] else "攻击"
                combat_log.append(f"{player.name} 发起{dmg_text}，造成 {result['damage']} 点伤害")
                total_damage_dealt += result["damage"]
                if result["lifesteal_heal"] > 0:
                    combat_log.append(f"吸血回复 {result['lifesteal_heal']} HP")
                # 连击
                if result["triggered_double"]:
                    double = cls.execute_attack(player, boss, is_double_hit=True)
                    if not double["dodged"]:
                        combat_log.append(f"连击追加 {double['damage']} 点伤害")
                        total_damage_dealt += double["damage"]
            combat_log.append(f"{boss.name} 剩余 HP: {max(0, boss.hp)}")

            if boss.hp <= 0:
                break

            # Boss攻击（Boss固定30会心率，无新属性）
            is_boss_crit, boss_damage = cls._legacy_turn_attack(boss.atk, 30)
            boss_damage = cls._legacy_damage_reduction(boss_damage, player.defense)
            # Boss攻击也受玩家闪避/格挡影响
            if random.randint(1, 100) <= player.dodge_rate:
                combat_log.append(f"{boss.name} 攻击被闪避！")
            else:
                if player.block_value > 0 and not is_boss_crit:
                    boss_damage = max(1, boss_damage - player.block_value)
                player.hp -= boss_damage
                if player.reflect_pct > 0:
                    reflect = int(boss_damage * player.reflect_pct / 100)
                    boss.hp -= reflect
                    combat_log.append(f"{boss.name} 攻击造成 {boss_damage} 伤害（反伤 {reflect}）")
                elif is_boss_crit:
                    combat_log.append(f"{boss.name} 会心一击！造成 {boss_damage} 伤害")
                else:
                    combat_log.append(f"{boss.name} 攻击造成 {boss_damage} 伤害")
            combat_log.append(f"{player.name} 剩余 HP: {max(0, player.hp)}")
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

    @staticmethod
    def _legacy_turn_attack(base_atk: int, crit_rate: int = 0, atk_buff: float = 0.0) -> Tuple[bool, int]:
        """Boss攻击用的旧版伤害计算"""
        damage = int(round(random.uniform(0.95, 1.05), 2) * base_atk * (1 + atk_buff))
        is_crit = random.randint(1, 100) <= crit_rate
        if is_crit:
            damage = int(damage * 1.5)
        return is_crit, damage

    @staticmethod
    def _legacy_damage_reduction(damage: int, defense: int = 0) -> int:
        """旧版减伤（Boss用）"""
        if defense <= 0:
            return damage
        reduction_rate = defense / (defense + 100)
        final_damage = int(damage * (1 - reduction_rate))
        return max(1, final_damage)
