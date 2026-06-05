"""战力公式验证测试

用蒙特卡洛模拟验证 calc_combat_power 公式是否能准确预测 PvP 胜率。
"""
import math
import random
import dataclasses

from astrbot_plugin_monixiuxian2.managers.combat_manager import CombatStats, CombatManager


# ── 辅助：旧公式（优化前） ──────────────────────────────

def old_calc_combat_power(stats: CombatStats, max_hp: int, max_mp: int) -> int:
    """旧版公式，仅用 9 个属性（缺失 armor_pen/lifesteal/crit_resist/reflect/block）"""
    crit_rate = min(stats.crit_rate, 100)
    crit_mult = 1.0 + crit_rate / 100.0 * max(0.0, stats.crit_damage - 1.0)
    double_mult = 1.0 + min(stats.double_hit, 100) / 100.0 * 0.5
    expected_atk = stats.atk * crit_mult * double_mult

    base_def_mult = (stats.base_def + 500) / 500.0
    equip_def_val = math.log(stats.equip_def + 1) * 20 if stats.equip_def > 0 else 0.0
    equip_def_mult = (equip_def_val + 200) / 200.0
    dodge_mult = 100.0 / max(1, 100 - min(stats.dodge_rate, 95))
    regen_mult = 1.0 + stats.hp_regen_pct / 100.0
    effective_hp = max_hp * base_def_mult * equip_def_mult * dodge_mult * regen_mult

    power = expected_atk * effective_hp
    if power <= 0:
        return 0
    return int(math.log10(power + 1) * 1000)


# ── 蒙特卡洛模拟 ───────────────────────────────────────

def simulate_pvp(stats1: CombatStats, stats2: CombatStats, n: int = 1000) -> float:
    """跑 n 次 PvP 模拟，返回 player1 的胜率。"""
    p1_wins = 0
    for _ in range(n):
        # 每次用独立副本（player_vs_player 会就地修改 HP）
        s1 = dataclasses.replace(stats1)
        s2 = dataclasses.replace(stats2)
        result = CombatManager.player_vs_player(s1, s2, combat_type=1)
        if result["winner"] == stats1.user_id:
            p1_wins += 1
    return p1_wins / n


# ── 测试用 CombatStats 模板 ─────────────────────────────

def make_stats(**kwargs) -> CombatStats:
    """创建 CombatStats，未指定字段用默认值。"""
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


# 高攻输出型（大量暴击/连击，无防御属性）
ATTACKER = make_stats(
    user_id="attacker", name="高攻",
    atk=12000, base_def=60.0, equip_def=200,
    crit_rate=50, crit_damage=2.5, double_hit=8,
    armor_pen=14, lifesteal=6,
    dodge_rate=2, crit_resist=0, reflect_pct=0,
    block_value=0, hp_regen_pct=0.0,
    hp=40000, max_hp=40000,
)

# 坦克型（高防御/格挡/反伤，低攻击）
TANK = make_stats(
    user_id="tank", name="坦克",
    atk=4000, base_def=90.0, equip_def=2000,
    crit_rate=10, crit_damage=1.5, double_hit=0,
    armor_pen=0, lifesteal=0,
    dodge_rate=8, crit_resist=12, reflect_pct=8,
    block_value=1200, hp_regen_pct=2.0,
    hp=120000, max_hp=120000,
)

# 混合型（攻守兼备）
BALANCED = make_stats(
    user_id="balanced", name="均衡",
    atk=8000, base_def=75.0, equip_def=800,
    crit_rate=35, crit_damage=2.0, double_hit=5,
    armor_pen=8, lifesteal=4,
    dodge_rate=5, crit_resist=8, reflect_pct=4,
    block_value=500, hp_regen_pct=1.0,
    hp=70000, max_hp=70000,
)

# 高穿透型（极端 armor_pen，其他一般）
PENETRATOR = make_stats(
    user_id="pen", name="破甲",
    atk=9000, base_def=65.0, equip_def=400,
    crit_rate=30, crit_damage=2.0, double_hit=3,
    armor_pen=14, lifesteal=3,
    dodge_rate=3, crit_resist=3, reflect_pct=0,
    block_value=0, hp_regen_pct=0.5,
    hp=55000, max_hp=55000,
)


# ── 测试用例 ───────────────────────────────────────────

def test_formula_has_no_zero_components():
    """新公式所有 14 项属性都参与计算，不应有乘数为 1.0（即无效果）的属性。"""
    # 构建一个所有属性都有值的 stats
    full = make_stats(
        atk=10000, base_def=80.0, equip_def=1000,
        crit_rate=40, crit_damage=2.0, double_hit=5,
        armor_pen=10, lifesteal=5,
        dodge_rate=5, crit_resist=8, reflect_pct=5,
        block_value=500, hp_regen_pct=1.5,
        hp=80000, max_hp=80000,
    )
    # 逐个置零属性，验证新公式输出会变化
    base_power = CombatManager.calc_combat_power(full, full.max_hp, full.max_mp)

    zeroable_fields = [
        "armor_pen", "lifesteal", "crit_resist", "reflect_pct",
        "block_value", "hp_regen_pct", "dodge_rate", "double_hit",
        "crit_rate", "crit_damage",
    ]
    for field in zeroable_fields:
        zeroed = dataclasses.replace(full, **{field: 0 if field != "crit_damage" else 1.0})
        power = CombatManager.calc_combat_power(zeroed, zeroed.max_hp, zeroed.max_mp)
        assert power != base_power, f"属性 {field} 置零后战力未变化，说明该属性未参与计算"


def test_high_power_wins_pvp():
    """高战力方在 PvP 模拟中应有较高胜率。

    对于攻击型 vs 坦克型，新公式应比旧公式更准确地预测结果。
    """
    pairs = [
        (ATTACKER, TANK, "高攻 vs 坦克"),
        (BALANCED, TANK, "均衡 vs 坦克"),
        (PENETRATOR, TANK, "破甲 vs 坦克"),
        (ATTACKER, BALANCED, "高攻 vs 均衡"),
    ]

    old_high_win_total = 0
    new_high_win_total = 0
    total_pairs = len(pairs)

    for s1, s2, label in pairs:
        p1_winrate = simulate_pvp(s1, s2, n=800)

        old_p1 = old_calc_combat_power(s1, s1.max_hp, s1.max_mp)
        old_p2 = old_calc_combat_power(s2, s2.max_hp, s2.max_mp)
        new_p1 = CombatManager.calc_combat_power(s1, s1.max_hp, s1.max_mp)
        new_p2 = CombatManager.calc_combat_power(s2, s2.max_hp, s2.max_mp)

        actual_higher = s1.user_id if p1_winrate > 0.5 else s2.user_id
        old_higher = s1.user_id if old_p1 > old_p2 else s2.user_id
        new_higher = s1.user_id if new_p1 > new_p2 else s2.user_id

        old_correct = old_higher == actual_higher
        new_correct = new_higher == actual_higher

        if old_correct:
            old_high_win_total += 1
        if new_correct:
            new_high_win_total += 1

        print(f"\n  {label}:")
        print(f"    p1_winrate: {p1_winrate:.1%}")
        print(f"    old: {s1.name}={old_p1:,} / {s2.name}={old_p2:,} -> {'OK' if old_correct else 'MISS'}")
        print(f"    new: {s1.name}={new_p1:,} / {s2.name}={new_p2:,} -> {'OK' if new_correct else 'MISS'}")

    print(f"\n  总计: 旧公式 {old_high_win_total}/{total_pairs} 正确, "
          f"新公式 {new_high_win_total}/{total_pairs} 正确")

    # 新公式至少不比旧公式差
    assert new_high_win_total >= old_high_win_total, \
        f"新公式准确率 ({new_high_win_total}) 低于旧公式 ({old_high_win_total})"


def test_armor_pen_matters():
    """有 armor_pen 的玩家战力应高于无 armor_pen 的同属性玩家。"""
    base = make_stats(atk=8000, hp=60000, max_hp=60000)
    with_pen = dataclasses.replace(base, armor_pen=14)

    base_power = CombatManager.calc_combat_power(base, base.max_hp, base.max_mp)
    pen_power = CombatManager.calc_combat_power(with_pen, with_pen.max_hp, with_pen.max_mp)

    assert pen_power > base_power, f"armor_pen=14 未提升战力: {pen_power} vs {base_power}"
    print(f"\n  armor_pen 效果: 无={base_power:,} → 有={pen_power:,} (Δ={pen_power - base_power:,})")


def test_crit_resist_matters():
    """有 crit_resist 的玩家战力应高于无 crit_resist 的同属性玩家。"""
    base = make_stats(hp=60000, max_hp=60000)
    with_resist = dataclasses.replace(base, crit_resist=12)

    base_power = CombatManager.calc_combat_power(base, base.max_hp, base.max_mp)
    resist_power = CombatManager.calc_combat_power(with_resist, with_resist.max_hp, with_resist.max_mp)

    assert resist_power > base_power, f"crit_resist=12 未提升战力: {resist_power} vs {base_power}"
    print(f"\n  crit_resist 效果: 无={base_power:,} → 有={resist_power:,} (Δ={resist_power - base_power:,})")


def test_block_value_matters():
    """有 block_value 的玩家战力应高于无 block_value 的同属性玩家。"""
    base = make_stats(hp=60000, max_hp=60000)
    with_block = dataclasses.replace(base, block_value=1000)

    base_power = CombatManager.calc_combat_power(base, base.max_hp, base.max_mp)
    block_power = CombatManager.calc_combat_power(with_block, with_block.max_hp, with_block.max_mp)

    assert block_power > base_power, f"block_value=1000 未提升战力: {block_power} vs {base_power}"
    print(f"\n  block_value 效果: 无={base_power:,} → 有={block_power:,} (Δ={block_power - base_power:,})")


def test_lifesteal_matters():
    """有 lifesteal 的玩家战力应高于无 lifesteal 的同属性玩家。"""
    base = make_stats(hp=60000, max_hp=60000)
    with_ls = dataclasses.replace(base, lifesteal=8)

    base_power = CombatManager.calc_combat_power(base, base.max_hp, base.max_mp)
    ls_power = CombatManager.calc_combat_power(with_ls, with_ls.max_hp, with_ls.max_mp)

    assert ls_power > base_power, f"lifesteal=8 未提升战力: {ls_power} vs {base_power}"
    print(f"\n  lifesteal 效果: 无={base_power:,} → 有={ls_power:,} (Δ={ls_power - base_power:,})")


def test_reflect_matters():
    """有 reflect_pct 的玩家战力应高于无 reflect_pct 的同属性玩家。"""
    base = make_stats(hp=60000, max_hp=60000)
    with_ref = dataclasses.replace(base, reflect_pct=8)

    base_power = CombatManager.calc_combat_power(base, base.max_hp, base.max_mp)
    ref_power = CombatManager.calc_combat_power(with_ref, with_ref.max_hp, with_ref.max_mp)

    assert ref_power > base_power, f"reflect_pct=8 未提升战力: {ref_power} vs {base_power}"
    print(f"\n  reflect_pct 效果: 无={base_power:,} → 有={ref_power:,} (Δ={ref_power - base_power:,})")


if __name__ == "__main__":
    # 手动运行时执行蒙特卡洛模拟（耗时较长）
    print("=" * 50)
    print("战力公式蒙特卡洛验证")
    print("=" * 50)

    test_formula_has_no_zero_components()
    test_armor_pen_matters()
    test_crit_resist_matters()
    test_block_value_matters()
    test_lifesteal_matters()
    test_reflect_matters()
    test_high_power_wins_pvp()

    print("\n" + "=" * 50)
    print("全部测试通过！")
    print("=" * 50)
