"""武器评分系统测试（双分数架构：词条评分 + 威力倍率）

覆盖：roll_score 公式、评级分档边界、旧格式 t=0.45、天成 SS、
无词条失败状态、威力倍率与官方战斗公式系数一致、评分幂等性。
设计文档：武器评分系统设计（第九章测试计划 +7 用例）。
"""
import json

# NOTE: 先导入 config_manager 打断 core 包的循环导入链（与 test_fuse.py 同款处理）
from astrbot_plugin_monixiuxian2.config_manager import ConfigManager  # noqa: F401
from astrbot_plugin_monixiuxian2.core.forging_manager import (
    ForgingManager,
    LEGACY_AFFIX_T,
    PERFECT_OVERCAP,
    POWER_DBL_FRAC,
    POWER_PEN_FRAC,
    SCORE_GRADES,
)


def _score(inst: dict) -> dict:
    return ForgingManager.score_instance(inst)


def test_roll_score_formula():
    """① 公式：t_i=(val-min)/(max-min)，score=100×mean(t_i) 四舍五入取整。"""
    # 单条：连击区间 [1,18]，val=9.5 → t=0.5 → 50 分
    inst = {"atk_bonus": 0.1, "affixes": [
        {"name": "连击", "attr": "double_hit", "val": 9.5},
    ]}
    info = _score(inst)
    assert info["breakdown"]["affixes"][0]["t"] == 0.5
    assert info["roll_score"] == 50
    assert info["grade"] == "C"

    # 三条等均值：嗜血 [1,12] val=3.75 → t=0.25；连击/破甲各 t=0.5
    # mean = (0.25+0.5+0.5)/3 = 0.416667 → 42 分
    inst2 = {"atk_bonus": 0.1, "affixes": [
        {"name": "嗜血", "attr": "lifesteal", "val": 3.75},
        {"name": "连击", "attr": "double_hit", "val": 9.5},
        {"name": "破甲", "attr": "armor_pen", "val": 7.0},
    ]}
    info2 = _score(inst2)
    assert info2["roll_score"] == 42
    ts = [a["t"] for a in info2["breakdown"]["affixes"]]
    assert ts == [0.25, 0.5, 0.5]


def test_grade_boundaries():
    """② 分档边界：D<30 / C 30-54 / B 55-69 / A 70-84 / S 85-99 / SS≥100。"""
    expect = [
        (0, "D"), (29.9, "D"),
        (30, "C"), (54.9, "C"),
        (55, "B"), (69.9, "B"),
        (70, "A"), (84.9, "A"),
        (85, "S"), (99.9, "S"),
        (100, "SS"), (115, "SS"),
    ]
    thresholds = [t for t, _ in SCORE_GRADES]
    for score, grade in expect:
        assert ForgingManager.grade_of(score) == grade, f"{score} 应为 {grade}"
    # 分档表单调且覆盖 0 分以下兜底
    assert thresholds == sorted(thresholds, reverse=True)
    assert ForgingManager.grade_of(-5) == "D"


def test_legacy_affix_t045():
    """③ 旧格式固定值词条（val 恰等于旧常数表且无 perfect 键）按 t=0.45。"""
    legacy_affixes = [
        {"name": "嗜血", "attr": "lifesteal", "val": 3},
        {"name": "破甲", "attr": "armor_pen", "val": 5},
        {"name": "连击", "attr": "double_hit", "val": 4},
        {"name": "精准", "attr": "crit_rate", "val": 3},
    ]
    inst = {"atk_bonus": 0.2, "affixes": legacy_affixes}
    info = _score(inst)
    for a in info["breakdown"]["affixes"]:
        assert a["t"] == LEGACY_AFFIX_T
    assert info["roll_score"] == 45  # 旧极品 = 4 条 × 0.45 → C 档
    assert info["grade"] == "C"

    # v3 新 roll 值（≠旧常数）走正常标尺：嗜血 3.5 → (3.5-1)/11 ≈ 0.2273
    inst_v3 = {"atk_bonus": 0.1, "affixes": [
        {"name": "嗜血", "attr": "lifesteal", "val": 3.5},
    ]}
    t = _score(inst_v3)["breakdown"]["affixes"][0]["t"]
    assert abs(t - 2.5 / 11.0) < 1e-9


def test_perfect_affix_ss():
    """④ 天成 t=1.15，单条天成即 115 分 → SS（中品单天成彩蛋成立）。"""
    inst = {"atk_bonus": 0.1, "affixes": [
        {"name": "精准", "attr": "crit_rate", "val": 13.8, "perfect": True},
    ]}
    info = _score(inst)
    assert info["breakdown"]["affixes"][0]["t"] == PERFECT_OVERCAP
    assert info["roll_score"] == 115
    assert info["grade"] == "SS"

    # 天成 + 高 roll 混合：mean(1.15, 15/17) ≈ 1.0162 → 102 → 仍 SS
    inst_mixed = {"atk_bonus": 0.1, "affixes": [
        {"name": "精准", "attr": "crit_rate", "val": 13.8, "perfect": True},
        {"name": "连击", "attr": "double_hit", "val": 16.0},
    ]}
    info_mixed = _score(inst_mixed)
    assert info_mixed["roll_score"] > 100
    assert info_mixed["grade"] == "SS"


def test_no_affix_none():
    """⑤ 无词条 → roll_score/grade 为 None，不崩溃；威力倍率照常（仅模板）。"""
    for affix_field in ("[]", "", "not-json{{", None):
        inst = {"atk_bonus": 0.38, "affixes": affix_field} if affix_field is not None \
            else {"atk_bonus": 0.38}
        info = _score(inst)
        assert info["roll_score"] is None
        assert info["grade"] is None
        assert info["breakdown"]["affixes"] == []
        assert info["power_mult"] == (1 + 0.38)


def test_power_mult_official_chain():
    """⑥ 威力倍率：每个乘数与官方战斗公式手算值一致（含 100%/95% 封顶）。"""
    inst = {
        "template_name": "青竹蜂云剑", "quality": "极品", "quality_mult": 1.5,
        "atk_bonus": 0.38, "crit_rate": 9, "crit_damage": 0.0,
        "armor_pen": 0, "lifesteal": 0, "double_hit": 0,
        "affixes": [
            {"name": "连击", "attr": "double_hit", "val": 12.4},
            {"name": "破甲", "attr": "armor_pen", "val": 9.6},
            {"name": "暴伤", "attr": "crit_damage", "val": 0.28},
            {"name": "嗜血", "attr": "lifesteal", "val": 6.0},
        ],
    }
    p = _score(inst)["breakdown"]["power"]

    # 官方乘数链手算值（与设计文档第四章公式逐项对齐）
    assert p["atk"] == 1 + 0.38
    assert p["crit"] == 1 + 9 / 100 * 0.28          # 暴击期望
    assert p["dbl"] == 1 + 12.4 / 100 * POWER_DBL_FRAC
    assert p["pen"] == 1 + 9.6 * POWER_PEN_FRAC / 100
    assert p["def"] == 1.0
    assert p["dodge"] == 1.0
    assert p["regen"] == 1.0
    assert p["steal"] == 1 + 6.0 / 100
    assert p["A"] == p["atk"] * p["crit"] * p["dbl"] * p["pen"]
    assert p["D"] == p["def"] * p["dodge"] * p["regen"] * p["steal"]
    assert _score(inst)["power_mult"] == p["A"] * p["D"]

    # 封顶口径：暴击 100 / 连击 100 / 闪避 95
    capped = {
        "atk_bonus": 0.0,
        "crit_rate": 150, "crit_damage": 1.0,
        "double_hit": 250, "dodge_rate": 99,
        "affixes": [],
    }
    pc = _score(capped)["breakdown"]["power"]
    assert pc["crit"] == 1 + 100 / 100 * 1.0        # min(crit_rate,100)
    assert pc["dbl"] == 1 + 100 / 100 * POWER_DBL_FRAC  # min(double_hit,100)
    assert pc["dodge"] == 100 / (100 - 95)          # min(dodge,95) → ×20 生存


def test_score_idempotent_and_roundtrip():
    """⑦ 幂等：同实例重复评分结果一致；affixes JSON 字符串/列表两形态同分。"""
    inst = {
        "template_name": "青竹蜂云剑", "quality": "极品",
        "atk_bonus": 0.38, "crit_rate": 9,
        "affixes": [
            {"name": "连击", "attr": "double_hit", "val": 12.4},
            {"name": "暴伤", "attr": "crit_damage", "val": 0.28, "perfect": False},
        ],
    }
    first = _score(inst)
    second = _score(inst)
    assert first == second

    as_json = dict(inst, affixes=json.dumps(inst["affixes"]))
    assert _score(as_json) == first
