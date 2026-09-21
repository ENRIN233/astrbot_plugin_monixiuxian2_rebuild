"""战斗评估（calc_combat_profile）测试

验证：画像分解键完整性、属性敏感度、镜像战口径、战斗指数与排行口径一致、流派分类。
"""
import dataclasses

from astrbot_plugin_monixiuxian2.managers.combat_manager import CombatStats, CombatManager


def make_stats(**kwargs) -> CombatStats:
    defaults = dict(
        user_id="test", name="test",
        hp=50000, max_hp=50000, mp=10000, max_mp=10000,
        atk=5000, base_def=70.0, equip_def=500,
        crit_rate=30, exp=1000000, crit_damage=1.8,
        armor_pen=0, lifesteal=0, double_hit=0,
        dodge_rate=0, crit_resist=0, reflect_pct=0,
        block_value=0, hp_regen_pct=0.0,
    )
    defaults.update(kwargs)
    return CombatStats(**defaults)


def test_profile_keys_complete():
    """画像包含全部分解键且为正数。"""
    s = make_stats()
    p = CombatManager.calc_combat_profile(s, s.max_hp)
    for key in ("edmg_per_hit", "crit_expect", "effective_hp",
                "mirror_rounds", "attack_mult", "defense_mult", "combat_index"):
        assert key in p, f"缺少键 {key}"
        assert p[key] > 0, f"{key} 应为正数"


def test_edmg_matches_execute_attack_expectation():
    """期望刀伤 = atk × 0.75 × E[crit] × 连击 × 破甲（与 execute_attack 的 0.5×1.5 系数一致）。"""
    s = make_stats(atk=8000, crit_rate=40, crit_damage=2.5,
                   double_hit=10, armor_pen=10)
    p = CombatManager.calc_combat_profile(s, s.max_hp)
    crit_expect = 1 + 0.40 * 1.5          # 1.6
    double_mult = 1 + 0.10 * 0.5          # 1.05
    pen_mult = 1 + 10 * 0.85 / 100        # 1.085
    expected = 8000 * 0.75 * crit_expect * double_mult * pen_mult
    assert abs(p["edmg_per_hit"] - expected) < 1e-6


def test_zero_sensitivity():
    """任一词条属性置零，战斗指数必须变化（与 test_combat_power 的零分量原则一致）。"""
    full = make_stats(atk=10000, crit_rate=40, crit_damage=2.0, double_hit=5,
                      armor_pen=10, lifesteal=5, dodge_rate=5, crit_resist=8,
                      reflect_pct=5, block_value=500, hp_regen_pct=1.5)
    base = CombatManager.calc_combat_profile(full, full.max_hp)["combat_index"]
    zeroable = ["armor_pen", "lifesteal", "double_hit", "dodge_rate",
                "crit_rate", "crit_resist", "reflect_pct", "block_value", "hp_regen_pct"]
    for field in zeroable:
        zeroed = dataclasses.replace(full, **{field: 0})
        idx = CombatManager.calc_combat_profile(zeroed, zeroed.max_hp)["combat_index"]
        assert idx != base, f"属性 {field} 置零后战斗指数未变化"
    # crit_damage 置 1.0（无暴击增益）同样必须变化
    no_cd = dataclasses.replace(full, crit_damage=1.0)
    assert CombatManager.calc_combat_profile(no_cd, no_cd.max_hp)["combat_index"] != base


def test_mirror_rounds_consistent():
    """镜像战回合数 = 有效生命 ÷ 期望刀伤（同口径互推）。"""
    s = make_stats()
    p = CombatManager.calc_combat_profile(s, s.max_hp)
    expect = p["effective_hp"] / p["edmg_per_hit"]
    assert abs(p["mirror_rounds"] - expect) < 1e-6


def test_index_matches_combat_power():
    """战斗指数必须与 calc_combat_power 详细分支完全一致（口径统一）。"""
    s = make_stats(atk=9000, hp=65000, max_hp=65000, armor_pen=8,
                   lifesteal=3, dodge_rate=4)
    idx = CombatManager.calc_combat_profile(s, s.max_hp)["combat_index"]
    power = CombatManager.calc_combat_power(s, s.max_hp, s.max_mp)
    assert idx == power


def test_style_mults_direction():
    """爆发流配置 attack_mult 应显著高于 defense_mult；铁壁流相反。"""
    attacker = make_stats(atk=12000, crit_rate=60, crit_damage=2.5, double_hit=10,
                          armor_pen=12)
    pa = CombatManager.calc_combat_profile(attacker, attacker.max_hp)
    assert pa["attack_mult"] > pa["defense_mult"]

    tank = make_stats(atk=4000, def_buff=0.5, dodge_rate=10, crit_resist=20,
                      reflect_pct=10, hp_regen_pct=4.0, block_value=1500,
                      hp=120000, max_hp=120000)
    pt = CombatManager.calc_combat_profile(tank, tank.max_hp)
    assert pt["defense_mult"] > pt["attack_mult"]
