# -*- coding: utf-8 -*-
"""功法经验倍率随机分配（区间带模型 v3.1）

- 天阶及以前 10 品阶：按区间带 uniform 随机（--seed 可复跑）
- 仙阶以上 29 个：exp +0.4 平移（与天阶上品上限 240% 衔接）
- 修炼特化 14 个：exp = 品阶上限 + U(0,15)；atk x0.5、暴击减半、hp x0.7
- 生成 config/technique_exp_manifest.json（旧值/新值对照，供测试与审计）

用法：python scripts/reroll_technique_exp.py [--seed 20260922] [--dry]
"""
import argparse
import json
import random
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[1] / "config" / "items.json"
MANIFEST = Path(__file__).resolve().parents[1] / "config" / "technique_exp_manifest.json"

# 品阶区间带（单位：倍，与 items.json 的 exp_multiplier 字段一致；1.00 = +100%）
BANDS = {
    "人阶下品": (1.00, 1.18),
    "人阶上品": (1.14, 1.32),
    "黄阶下品": (1.28, 1.46),
    "黄阶上品": (1.42, 1.60),
    "玄阶下品": (1.56, 1.74),
    "玄阶上品": (1.70, 1.88),
    "地阶下品": (1.84, 2.02),
    "地阶上品": (1.98, 2.16),
    "天阶下品": (2.12, 2.30),
    "天阶上品": (2.22, 2.40),
}
IMMORTAL_SHIFT = 0.4  # 仙阶以上整体平移
SPECIAL_EXTRA_MAX = 0.15  # 特化在品阶上限之上的随机补偿（+15 个百分点）
IMMORTAL_RANKS = {"仙阶下品", "仙阶上品", "仙阶极品", "无上仙法"}

# 修炼特化名单（名字气质偏吐纳/炼气/养生/经文）
SPECIAL_NAMES = {
    "吐纳功法", "冰心诀", "禾山经", "地元炼体功",
    "龟息术", "万木诀", "五藏炼尘功", "混元引气诀",
    "太乙玄功", "太阴六虚功", "玄武吐纳术",
    "无始经", "两仪心经", "混沌经",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260922)
    ap.add_argument("--dry", action="store_true", help="只打印分配结果，不写文件")
    args = ap.parse_args()
    rng = random.Random(args.seed)

    data = json.loads(CONFIG.read_text(encoding="utf-8"))
    techniques = [(k, v) for k, v in data.items() if v.get("type") == "main_technique"]
    assert len(techniques) == 79, f"主修功法数量异常: {len(techniques)}"

    # 先收集仙阶以上各品阶的平移后上限（基于原始值，只加一次 0.4；供特化取值）
    immortal_rank_max = {}
    for _, v in techniques:
        r = v.get("rank", "")
        if r in IMMORTAL_RANKS:
            immortal_rank_max[r] = max(immortal_rank_max.get(r, 0.0), v.get("exp_multiplier", 0.0))
    for r in immortal_rank_max:
        immortal_rank_max[r] = round(immortal_rank_max[r] + IMMORTAL_SHIFT, 2)

    manifest = []
    for key, v in techniques:
        name, rank = v["name"], v.get("rank", "")
        old_exp = v.get("exp_multiplier", 0.0)
        is_special = name in SPECIAL_NAMES

        if rank in BANDS:
            lo, hi = BANDS[rank]
            new_exp = round(hi + rng.uniform(0, SPECIAL_EXTRA_MAX), 2) if is_special else round(rng.uniform(lo, hi), 2)
        elif rank in IMMORTAL_RANKS:
            new_exp = round(old_exp + IMMORTAL_SHIFT, 2)
            if is_special:
                new_exp = round(immortal_rank_max[rank] + rng.uniform(0, SPECIAL_EXTRA_MAX), 2)
        else:
            raise SystemExit(f"未知品阶: {name} ({rank})")

        entry = {
            "id": key, "name": name, "rank": rank, "special": is_special,
            "old_exp": old_exp, "new_exp": new_exp,
        }
        if is_special:
            old_atk = v.get("atk_bonus", 0.0)
            old_cr = v.get("crit_rate", 0)
            old_cd = v.get("crit_damage", 0.0)
            old_hp = v.get("hp_bonus", 0.0)
            v["atk_bonus"] = round(old_atk * 0.5, 3)
            v["crit_rate"] = round(old_cr * 0.5)
            v["crit_damage"] = round(old_cd * 0.5, 2)
            v["hp_bonus"] = round(old_hp * 0.7, 3)
            entry.update({
                "old_atk": old_atk, "new_atk": v["atk_bonus"],
                "old_crit_rate": old_cr, "new_crit_rate": v["crit_rate"],
                "old_crit_damage": old_cd, "new_crit_damage": v["crit_damage"],
                "old_hp": old_hp, "new_hp": v["hp_bonus"],
            })
        v["exp_multiplier"] = new_exp
        manifest.append(entry)

    manifest.sort(key=lambda e: (list(BANDS) + list(IMMORTAL_RANKS)).index(e["rank"]) if e["rank"] in BANDS or e["rank"] in IMMORTAL_RANKS else 99)

    if args.dry:
        for e in manifest:
            tag = " [特化]" if e["special"] else ""
            print(f"{e['rank']:<6} {e['name']:<10} exp {e['old_exp']:.2f} -> {e['new_exp']:.2f}（+{e['new_exp']*100:.0f}%）{tag}")
        return

    CONFIG.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入 {CONFIG.name} 与 {MANIFEST.name}（seed={args.seed}，共 {len(manifest)} 条）")
    for e in manifest:
        tag = " [特化]" if e["special"] else ""
        print(f"{e['rank']:<6} {e['name']:<10} exp {e['old_exp']:.2f} -> {e['new_exp']:.2f}（+{e['new_exp']*100:.0f}%）{tag}")


if __name__ == "__main__":
    main()
