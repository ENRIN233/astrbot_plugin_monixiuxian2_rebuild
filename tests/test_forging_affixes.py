"""锻造词条随机化 v3 测试

覆盖：品质带权边界、天成超上限、单位感知格式化、不重复抽池、
旧格式兼容、区间表完整性（封顶线安全）。
"""
import random
from unittest.mock import patch

# NOTE: 先导入 config_manager 打断 core 包的循环导入链（与 test_fuse.py 同款处理）
from astrbot_plugin_monixiuxian2.config_manager import ConfigManager  # noqa: F401
from astrbot_plugin_monixiuxian2.core.forging_manager import (
    ForgingManager,
    FORGE_AFFIXES,
    QUALITY_AFFIX_BANDS,
    QUALITY_AFFIX_COUNT,
    PERFECT_CHANCE,
    PERFECT_OVERCAP,
    BAND_MODE_FRAC,
)


def _mgr():
    # _roll_affixes 只依赖 random，无需真实数据库
    return ForgingManager(db=None, db_extended=None, config_manager=None,
                          storage_ring_manager=None)


def test_band_bounds():
    """任意品质 roll 1000 次，非天成词条必须落在对应品质带内。"""
    m = _mgr()
    for quality, (blo, bhi) in QUALITY_AFFIX_BANDS.items():
        count_range = QUALITY_AFFIX_COUNT.get(quality, (0, 0))
        if count_range == (0, 0):
            continue
        for _ in range(1000):
            affixes = m._roll_affixes(quality)
            for a in affixes:
                tpl = next(t for t in FORGE_AFFIXES if t["attr"] == a["attr"])
                lo, hi = float(tpl["min"]), float(tpl["max"])
                if a.get("perfect"):
                    assert a["val"] > hi  # 天成超上限
                    continue
                frac = (a["val"] - lo) / (hi - lo)
                assert blo - 1e-9 <= frac <= bhi + 1e-9, (
                    f"{quality} {a['name']} val={a['val']} 标尺位置 {frac:.3f} "
                    f"越界 [{blo}, {bhi}]"
                )


def test_perfect_overcap():
    """mock 概率必中天成：val == max × 1.15 且携带 perfect 标记。"""
    m = _mgr()
    with patch.object(random, "random", return_value=PERFECT_CHANCE / 2):
        affixes = m._roll_affixes("极品")
    assert affixes, "天成判定应至少产出 1 条词条"
    for a in affixes:
        tpl = next(t for t in FORGE_AFFIXES if t["attr"] == a["attr"])
        assert a["perfect"] is True
        assert abs(a["val"] - float(tpl["max"]) * PERFECT_OVERCAP) < 1e-6


def test_format_affix_val_units():
    """三类单位的格式化：减伤百分比 / 会伤倍率 / 通用百分比。"""
    fmt = ForgingManager.format_affix_val
    assert fmt("def_buff", 0.03) == "+3%减伤"
    assert fmt("def_buff", 0.055) == "+5.5%减伤"
    assert fmt("crit_damage", 0.15) == "会伤+0.15"
    assert fmt("crit_damage", 0.4) == "会伤+0.4"
    assert fmt("lifesteal", 4.6) == "+4.6%"
    assert fmt("hp_regen_pct", 2) == "+2%"
    assert fmt("armor_pen", 10) == "+10%"


def test_no_duplicate_affixes():
    """同一次锻造的词条 attr 不重复。"""
    m = _mgr()
    for _ in range(200):
        for quality in ("中品", "上品", "极品"):
            affixes = m._roll_affixes(quality)
            attrs = [a["attr"] for a in affixes]
            assert len(attrs) == len(set(attrs)), f"{quality} 出现重复词条: {attrs}"


def test_legacy_val_format_compat():
    """旧格式词条（仅 name/attr/val，无 perfect 键）可被格式化器正常处理。"""
    legacy = {"name": "嗜血", "attr": "lifesteal", "val": 3}
    text = ForgingManager.format_affix_val(legacy["attr"], legacy["val"])
    assert text == "+3%"
    legacy_perfect = {"name": "精准", "attr": "crit_rate", "val": 13.8, "perfect": True}
    assert legacy_perfect.get("perfect") is True


def test_affix_table_integrity():
    """区间表完整性：8 词条 min < max、attr 唯一、天成 ×1.15 不触碰战斗端封顶线。"""
    attrs = [t["attr"] for t in FORGE_AFFIXES]
    assert len(attrs) == len(set(attrs)) == 8
    for t in FORGE_AFFIXES:
        assert float(t["min"]) < float(t["max"]), f"{t['name']} 区间非法"
        overcap_val = float(t["max"]) * PERFECT_OVERCAP
        if t["attr"] == "def_buff":
            assert overcap_val < 0.9, "铁壁天成不得触碰 90% 减伤封顶"
        if t["attr"] == "dodge_rate":
            assert overcap_val < 95, "闪避天成不得触碰 95% 封顶"
        if t["attr"] == "crit_rate":
            assert overcap_val <= 100 * 1.15, "精准允许溢出（战斗端 max(0, cr-resist) 天然自限）"


def test_mode_fraction_low_bias():
    """三角分布众数位于区间下段（BAND_MODE_FRAC=0.4）：roll 均值应低于区间中点。"""
    m = _mgr()
    tpl = next(t for t in FORGE_AFFIXES if t["attr"] == "lifesteal")
    lo, hi = float(tpl["min"]), float(tpl["max"])
    vals = []
    for _ in range(4000):
        a = m._roll_affix_value(tpl, (0.20, 0.75))
        if not a.get("perfect"):
            vals.append(a["val"])
    mean = sum(vals) / len(vals)
    assert mean < (lo + hi) / 2, f"上品均值 {mean:.2f} 应低于区间中点 {(lo+hi)/2:.2f}"
