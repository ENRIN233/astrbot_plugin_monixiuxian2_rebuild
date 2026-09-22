# -*- coding: utf-8 -*-
"""功法经验倍率随机分配（区间带模型 v3.1）测试"""
import json
from pathlib import Path

from scripts.reroll_technique_exp import (
    BANDS, IMMORTAL_RANKS, IMMORTAL_SHIFT, SPECIAL_EXTRA_MAX, SPECIAL_NAMES,
)

ROOT = Path(__file__).resolve().parent.parent
ITEMS = json.loads((ROOT / "config" / "items.json").read_text(encoding="utf-8"))
MANIFEST = json.loads((ROOT / "config" / "technique_exp_manifest.json").read_text(encoding="utf-8"))
BY_NAME = {e["name"]: e for e in MANIFEST}


def _item(name):
    for v in ITEMS.values():
        if v.get("name") == name:
            return v
    raise AssertionError(f"items.json 缺少 {name}")


def test_manifest_covers_all_techniques():
    """manifest 覆盖全部 79 个主修功法，且 14 个特化"""
    assert len(MANIFEST) == 79
    specials = [e for e in MANIFEST if e["special"]]
    assert len(specials) == 14
    assert {e["name"] for e in specials} == SPECIAL_NAMES


def test_band_techniques_within_bands():
    """天阶及以前非特化：exp 落在品阶区间内"""
    for e in MANIFEST:
        if e["rank"] in BANDS and not e["special"]:
            lo, hi = BANDS[e["rank"]]
            assert lo <= e["new_exp"] <= hi, f"{e['name']} exp {e['new_exp']} 不在 [{lo},{hi}]"


def test_special_at_band_ceiling():
    """特化：exp = 品阶上限 + [0, 0.15]"""
    for e in MANIFEST:
        if not e["special"]:
            continue
        if e["rank"] in BANDS:
            ceiling = BANDS[e["rank"]][1]
        else:
            ceiling = max(
                (x["old_exp"] for x in MANIFEST if x["rank"] == e["rank"]),
                default=0.0,
            ) + IMMORTAL_SHIFT
        assert ceiling <= e["new_exp"] <= ceiling + SPECIAL_EXTRA_MAX + 0.001, \
            f"特化 {e['name']} exp {e['new_exp']} 不在 [{ceiling},{ceiling + SPECIAL_EXTRA_MAX}]"


def test_immortal_shift_exact():
    """仙阶以上非特化：exp = 原值 + 0.4（精确平移）"""
    for e in MANIFEST:
        if e["rank"] in IMMORTAL_RANKS and not e["special"]:
            assert abs(e["new_exp"] - (e["old_exp"] + IMMORTAL_SHIFT)) < 1e-9, \
                f"{e['name']} 平移误差"
            assert abs(_item(e["name"])["exp_multiplier"] - e["new_exp"]) < 1e-9


def test_special_combat_template():
    """特化战斗模板：atk x0.5、暴击减半、hp x0.7"""
    for e in MANIFEST:
        if not e["special"]:
            continue
        item = _item(e["name"])
        assert item["atk_bonus"] == e["new_atk"]
        assert item["crit_rate"] == e["new_crit_rate"]
        assert item["crit_damage"] == e["new_crit_damage"]
        assert item["hp_bonus"] == e["new_hp"]
        assert abs(item["atk_bonus"] - e["old_atk"] * 0.5) < 1e-9
        assert item["crit_rate"] == round(e["old_crit_rate"] * 0.5)
        # crit_damage 经 round(2) 舍入，容差 0.006
        assert abs(item["crit_damage"] - e["old_crit_damage"] * 0.5) <= 0.006
        assert abs(item["hp_bonus"] - e["old_hp"] * 0.7) < 1e-9


def test_global_bounds():
    """边界锁：天阶及以前非特化最低 >= 1.00、最高 <= 2.40；特化可破带上限 +0.15；仙下 >= 2.40"""
    for e in MANIFEST:
        if e["rank"] in BANDS:
            assert e["new_exp"] >= 1.00
            ceiling = 2.40 + (SPECIAL_EXTRA_MAX if e["special"] else 0.0)
            assert e["new_exp"] <= ceiling + 0.001, f"{e['name']} exp {e['new_exp']} 超出 {ceiling}"
        if e["rank"] == "仙阶下品":
            assert e["new_exp"] >= 2.40


def test_items_match_manifest():
    """items.json 与 manifest 一致（写入完整性）"""
    for e in MANIFEST:
        assert _item(e["name"])["exp_multiplier"] == e["new_exp"]
