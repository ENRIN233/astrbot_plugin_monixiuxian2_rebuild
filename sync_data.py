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
    # Spirit cultivation levels
    level_path = os.path.join(SRC, "level_config.json")
    if os.path.exists(level_path):
        with open(level_path, encoding="utf-8") as f:
            for i, lv in enumerate(json.load(f)):
                level_map[i] = lv.get("level_name", "")
    # Body cultivation levels (merge if name differs)
    body_path = os.path.join(SRC, "body_level_config.json")
    if os.path.exists(body_path):
        with open(body_path, encoding="utf-8") as f:
            for i, lv in enumerate(json.load(f)):
                body_name = lv.get("level_name", "")
                if i in level_map and body_name and body_name != level_map[i]:
                    level_map[i] = level_map[i] + " / " + body_name
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


count = 0
for f in os.listdir(SRC):
    if f.endswith(".json"):
        src_path = os.path.join(SRC, f)
        dst_path = os.path.join(DST, f)
        if f == "weapons.json":
            _enrich_weapons(src_path, dst_path)
        else:
            shutil.copy2(src_path, dst_path)
        count += 1
        print(f"  {f}")

print(f"\nSynced {count} files to docs/data/")
