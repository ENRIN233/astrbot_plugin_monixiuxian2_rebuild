# managers/skill_manager.py
"""
神通系统管理器 - 处理战斗中技能的触发、执行和buff管理
"""

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ..config_manager import ConfigManager
    from .combat_manager import CombatStats


@dataclass
class ActiveBuff:
    """战斗中生效的buff/debuff"""
    skill_name: str         # 来源技能名
    buff_type: str          # "atk_buff" / "def_buff" / "dot"
    value: float            # 倍率（如 0.4 = +40%）
    remaining_turns: int    # 剩余回合
    base_damage: int = 0    # DOT用：施法时的ATK快照


@dataclass
class CombatSkillState:
    """单次战斗中的技能状态（临时，战斗结束后销毁）"""
    user_id: str
    active_buffs: List[ActiveBuff] = field(default_factory=list)
    cooldowns: Dict[str, int] = field(default_factory=dict)  # {技能名: 剩余冷却}
    is_sealed: bool = False
    seal_remaining_turns: int = 0


SKILL_TYPE_NAMES = {1: "攻击", 2: "持续", 3: "增益", 4: "控制"}


class SkillManager:
    """神通系统管理器"""

    def __init__(self, config_manager: "ConfigManager"):
        self.config_manager = config_manager

    def get_skill_data(self, skill_name: str) -> Optional[dict]:
        """查找神通配置数据"""
        return self.config_manager.skills_data.get(skill_name)

    @staticmethod
    def init_combat_state(user_id: str) -> CombatSkillState:
        """创建战斗初始技能状态"""
        return CombatSkillState(user_id=user_id)

    def check_skill_usable(self, skill_name: str, state: CombatSkillState,
                           caster_mp: int, caster_hp: int, caster_max_hp: int,
                           caster_max_mp: int = 0) -> Tuple[bool, str]:
        """检查技能本回合是否可用

        Returns: (can_use, reason)
        """
        if state.is_sealed:
            return False, "被封印"

        skill_data = self.get_skill_data(skill_name)
        if not skill_data:
            return False, "技能不存在"

        if skill_name in state.cooldowns and state.cooldowns[skill_name] > 0:
            return False, f"冷却中({state.cooldowns[skill_name]}回合)"

        mp_cost = skill_data.get("mpcost", 0)
        if mp_cost > 0:
            mp_needed = int(caster_max_mp * mp_cost) if caster_max_mp > 0 else mp_cost
            if caster_mp < mp_needed:
                return False, "MP不足"

        hp_cost = skill_data.get("hpcost", 0)
        if hp_cost > 0:
            hp_loss = int(caster_max_hp * hp_cost)
            if caster_hp <= hp_loss:
                return False, "HP不足"

        return True, ""

    def try_activate_skill(self, skill_name: str) -> bool:
        """按rate概率掷骰判断是否触发"""
        skill_data = self.get_skill_data(skill_name)
        if not skill_data:
            return False
        rate = skill_data.get("rate", 100)
        return random.randint(1, 100) <= rate

    @staticmethod
    def tick_buffs_and_cooldowns(state: CombatSkillState):
        """每回合开始时调用：递减buff持续、冷却、封禁"""
        # 递减buff持续时间，移除过期buff
        expired = []
        for i, buff in enumerate(state.active_buffs):
            buff.remaining_turns -= 1
            if buff.remaining_turns <= 0:
                expired.append(i)
        for i in reversed(expired):
            state.active_buffs.pop(i)

        # 递减冷却
        expired_cd = []
        for name, turns in state.cooldowns.items():
            state.cooldowns[name] = turns - 1
            if state.cooldowns[name] <= 0:
                expired_cd.append(name)
        for name in expired_cd:
            del state.cooldowns[name]

        # 递减封禁
        if state.is_sealed:
            state.seal_remaining_turns -= 1
            if state.seal_remaining_turns <= 0:
                state.is_sealed = False
                state.seal_remaining_turns = 0

    def execute_skill(self, skill_name: str, caster: "CombatStats",
                      defender: "CombatStats", caster_state: CombatSkillState,
                      defender_state: CombatSkillState) -> dict:
        """执行技能，返回结果字典"""
        skill_data = self.get_skill_data(skill_name)
        if not skill_data:
            return {"type": "error", "skill_name": skill_name}

        stype = skill_data.get("skill_type", 1)
        result = {"skill_name": skill_name, "type": ""}

        if stype == 1:
            result = self._execute_attack_skill(skill_data, caster, defender)
        elif stype == 2:
            result = self._execute_continuous_skill(skill_data, caster, defender, defender_state)
        elif stype == 3:
            result = self._execute_buff_skill(skill_data, caster, caster_state)
        elif stype == 4:
            result = self._execute_control_skill(skill_data, defender_state)

        result["skill_name"] = skill_name
        return result

    def _execute_attack_skill(self, skill_data: dict, caster: "CombatStats",
                              defender: "CombatStats") -> dict:
        """Type 1: 攻击神通 — 多段伤害"""
        atkvalues = skill_data.get("atkvalue", [1.0])
        if not isinstance(atkvalues, list):
            atkvalues = [float(atkvalues)]

        damages = []
        for mult in atkvalues:
            raw_dmg = int(caster.atk * 0.5 * mult * 1.5 * random.uniform(0.95, 1.05))
            # 暴击判定（考虑防御方的抗暴击）
            effective_crit_rate = max(0, caster.crit_rate - defender.crit_resist)
            is_crit = random.randint(1, 100) <= effective_crit_rate
            if is_crit:
                raw_dmg = int(raw_dmg * caster.crit_damage)
            # 双层减伤
            reduced = self._apply_defense(raw_dmg, caster, defender)
            reduced = max(1, reduced)
            # 格挡（非暴击时生效）
            if not is_crit and defender.block_value > 0:
                reduced = max(1, reduced - defender.block_value)
            damages.append(reduced)

        total_damage = sum(damages)
        defender.hp = max(0, defender.hp - total_damage)

        return {
            "type": "attack",
            "hits": len(atkvalues),
            "damages": damages,
            "total_damage": total_damage,
        }

    def _execute_continuous_skill(self, skill_data: dict, caster: "CombatStats",
                                  defender: "CombatStats",
                                  defender_state: CombatSkillState) -> dict:
        """Type 2: 持续神通 — 施加DOT"""
        # 先造成一次即时伤害
        atkvalue = skill_data.get("atkvalue", 0)
        if isinstance(atkvalue, list):
            atkvalue = atkvalue[0] if atkvalue else 0
        instant_dmg = int(caster.atk * 0.5 * float(atkvalue) * 1.5 * random.uniform(0.95, 1.05))
        instant_dmg = max(1, self._apply_defense(instant_dmg, caster, defender))
        defender.hp = max(0, defender.hp - instant_dmg)

        # 施加DOT debuff
        # 优先使用独立的 dot_turns 字段，向后兼容 turncost
        dot_turns = skill_data.get("dot_turns", skill_data.get("turncost", 3))
        dot = ActiveBuff(
            skill_name=skill_data["name"],
            buff_type="dot",
            value=float(atkvalue),
            remaining_turns=dot_turns,
            base_damage=caster.atk,
        )
        # 移除同名DOT（不叠加）
        defender_state.active_buffs = [
            b for b in defender_state.active_buffs
            if not (b.buff_type == "dot" and b.skill_name == skill_data["name"])
        ]
        defender_state.active_buffs.append(dot)

        return {
            "type": "continuous",
            "instant_damage": instant_dmg,
            "dot_turns": dot_turns,
        }

    def _execute_buff_skill(self, skill_data: dict, caster: "CombatStats",
                            state: CombatSkillState) -> dict:
        """Type 3: 增益神通 — 给自己施加ATK/DEF buff"""
        bufftype = skill_data.get("bufftype", 1)
        buffvalue = skill_data.get("buffvalue", 0)
        turns = skill_data.get("turncost", 3)

        buff_type_str = "atk_buff" if bufftype == 1 else "def_buff"
        buff = ActiveBuff(
            skill_name=skill_data["name"],
            buff_type=buff_type_str,
            value=float(buffvalue),
            remaining_turns=turns,
        )
        # 同类型不叠加，只替换
        state.active_buffs = [
            b for b in state.active_buffs if b.buff_type != buff_type_str
        ]
        state.active_buffs.append(buff)

        return {
            "type": "buff",
            "buff_type": buff_type_str,
            "value": buffvalue,
            "turns": turns,
        }

    def _execute_control_skill(self, skill_data: dict,
                               defender_state: CombatSkillState) -> dict:
        """Type 4: 控制神通 — 封禁对方"""
        success_rate = skill_data.get("success", 50)
        turns = skill_data.get("turncost", 2)

        if random.randint(1, 100) <= success_rate:
            defender_state.is_sealed = True
            defender_state.seal_remaining_turns = turns
            return {"type": "control", "success": True, "turns": turns}
        else:
            return {"type": "control", "success": False}

    @staticmethod
    def apply_buffs_to_atk(base_atk: int, state: CombatSkillState) -> int:
        """计算含buff的有效攻击力"""
        mult = 1.0
        for buff in state.active_buffs:
            if buff.buff_type == "atk_buff":
                mult += buff.value
        return int(base_atk * mult)

    @staticmethod
    def apply_buffs_to_def(def_buff: float,
                           state: CombatSkillState) -> float:
        """计算含buff的有效减伤率"""
        mult = 1.0
        for buff in state.active_buffs:
            if buff.buff_type == "def_buff":
                mult += buff.value
        return min(0.9, def_buff * mult)

    @staticmethod
    def apply_dot_damage(state: CombatSkillState, defender_def_buff: float = 0.0) -> int:
        """结算DOT伤害（Excel公式：攻击×神通倍率×(1-减伤率)），返回总伤害值"""
        total = 0
        for buff in state.active_buffs:
            if buff.buff_type == "dot":
                raw = int(buff.base_damage * buff.value)
                total += max(1, int(raw * (1 - defender_def_buff)))
        return total

    @staticmethod
    def _apply_defense(raw_damage: int, attacker: "CombatStats",
                       defender: "CombatStats") -> int:
        """百分比减伤（Excel公式：伤害 × (1 - 减伤率 + 穿甲)）"""
        total_reduction = defender.def_buff - attacker.armor_pen / 100
        return max(1, int(raw_damage * (1 - total_reduction))) if total_reduction != 0 else max(1, raw_damage)


def format_skill_result(attacker_name: str, defender_name: str, result: dict) -> str:
    """将技能执行结果格式化为战斗日志"""
    skill_name = result.get("skill_name", "神通")

    if result["type"] == "attack":
        hits_text = f"{result['hits']}连击" if result["hits"] > 1 else "一击"
        return f"✦ {attacker_name} 施展【{skill_name}】{hits_text}，造成 {result['total_damage']} 点伤害"

    elif result["type"] == "continuous":
        parts = f"✦ {attacker_name} 施展【{skill_name}】，造成 {result['instant_damage']} 点伤害"
        if result.get("dot_turns", 0) > 0:
            parts += f"，{defender_name} 被施加持续伤害（{result['dot_turns']}回合）"
        return parts

    elif result["type"] == "buff":
        buff_name = "攻击力" if result["buff_type"] == "atk_buff" else "防御力"
        pct = int(result["value"] * 100)
        return f"✦ {attacker_name} 施展【{skill_name}】，{buff_name}提升 {pct}%（{result['turns']}回合）"

    elif result["type"] == "control":
        if result["success"]:
            return f"✦ {attacker_name} 施展【{skill_name}】，{defender_name} 被封印（{result['turns']}回合）"
        else:
            return f"✦ {attacker_name} 施展【{skill_name}】，封印失败！"

    return f"✦ {attacker_name} 施展了【{skill_name}】"
