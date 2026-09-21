"""Sync config JSON files to docs/data/ for GitHub Pages.

Usage: python sync_data.py
"""
import json
import shutil
import os

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "config")
DST = os.path.join(BASE, "docs", "data")

os.makedirs(DST, exist_ok=True)


def _build_level_name_map():
    """Build required_level_index -> display name mapping from level configs."""
    level_map = {}
    level_path = os.path.join(SRC, "level_config.json")
    if os.path.exists(level_path):
        with open(level_path, encoding="utf-8") as f:
            for i, lv in enumerate(json.load(f)):
                level_map[i] = lv.get("name", "未知境界")
    return level_map


def _enrich_weapons(src_path, dst_path):
    """Add required_level_name to each weapon/armor entry."""
    level_map = _build_level_name_map()
    with open(src_path, encoding="utf-8") as f:
        weapons = json.load(f)
    for w in weapons:
        idx = w.get("required_level_index", 0)
        name = level_map.get(idx, f"混元大罗金仙")
        w["required_level_name"] = name
    with open(dst_path, "w", encoding="utf-8") as f:
        json.dump(weapons, f, ensure_ascii=False, indent=2)


def _closing_realm_mult(levels, idx, slow_from, share_mid, share_end, mn):
    """v4.3.8 闭关境界因子（与 config_manager.get_closing_realm_mult 保持一致）。

    idx <= slow_from 恒为 1.0；之后按衰减曲线收敛，并锚定下一级突破需求占比。
    """
    if idx <= slow_from:
        return 1.0
    k = (share_end / share_mid) ** (1.0 / max(1, 57 - slow_from))
    share = max(mn, share_mid * (k ** (idx - slow_from)))
    nxt = min(idx + 1, len(levels) - 1)
    needed = int(levels[nxt].get("exp_needed", 0) or 0)
    if needed <= 0:
        return 1.0
    return share * needed / 86400.0


def _enrich_level_config(src_path, dst_path):
    """Add closing_realm_mult (v4.3.8) to each level entry for the docs site."""
    with open(src_path, encoding="utf-8") as f:
        levels = json.load(f)

    # 参数取自 game_config.json 的 level_scaling（与运行时同源）
    ls = {}
    game_cfg_path = os.path.join(SRC, "game_config.json")
    if os.path.exists(game_cfg_path):
        with open(game_cfg_path, encoding="utf-8") as f:
            ls = json.load(f).get("level_scaling", {})

    slow_from = int(ls.get("exp_share_slowdown_from", 18))
    share_mid = float(ls.get("closing_exp_share_mid", 0.045))
    share_end = float(ls.get("closing_exp_share_end", 0.03))
    mn = float(ls.get("closing_exp_share_min", 0.008))

    for i, lv in enumerate(levels):
        lv["closing_realm_mult"] = round(
            _closing_realm_mult(levels, i, slow_from, share_mid, share_end, mn), 4
        )

    with open(dst_path, "w", encoding="utf-8") as f:
        json.dump(levels, f, ensure_ascii=False, indent=2)


count = 0
for f in os.listdir(SRC):
    if f.endswith(".json"):
        src_path = os.path.join(SRC, f)
        dst_path = os.path.join(DST, f)
        if f == "weapons.json":
            _enrich_weapons(src_path, dst_path)
        elif f == "level_config.json":
            _enrich_level_config(src_path, dst_path)
        else:
            shutil.copy2(src_path, dst_path)
        count += 1
        print(f"  {f}")

print(f"\nSynced {count} files to docs/data/")
