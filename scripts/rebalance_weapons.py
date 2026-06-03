"""
武器数值重构脚本 — 参考 nonebot 法器.json 对齐 weapons.json 全部武器 buff 数值

用法: python scripts/rebalance_weapons.py [--dry-run]

功能:
1. 72 把 nonebot 合并武器: 按 _source_id 精确匹配参考文件,写入 atk_bonus/crit_rate/crit_damage/mp_bonus
2. 141 把原生武器: 按品阶分配标准 buff 基准值
3. 所有武器 crit_damage 从乘法体系转为加法增量体系 (原值 > 1.0 时减 1.0)
4. 确保所有武器有 atk_bonus 字段
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
REF_PATH = Path(r"E:\Github\nonebot_plugin_xiuxian_2_pmv-master\data\xiuxian\装备\法器.json")
WEAPONS_PATH = PROJECT_ROOT / "config" / "weapons.json"


# 参考文件品阶基准 buff (每品阶 3 种: 攻击/暴击/混合)
# key = 品阶名, value = (atk_buff, crit_buff, critatk)
RANK_STANDARD_BUFFS = {
    "灵品":    (0.12, 0.12, 0.0),
    "地品":    (0.16, 0.16, 0.0),
    "天品":    (0.20, 0.20, 0.0),
    "皇品":    (0.24, 0.24, 0.0),
    "帝品":    (0.28, 0.28, 0.0),
    "道品":    (0.32, 0.32, 0.0),
    "仙品":    (0.40, 0.40, 0.0),
    "混元先天": (0.50, 0.50, 0.0),  # 极品仙器下限
}

# 凡品特殊: 参考文件下品符器 buff 为 0.08, 但原生凡品武器基础数值极低
# 使用与灵品相同的 0.12 基准保持平衡
凡品_BUFFS = (0.12, 0.12, 0.0)


def load_reference(path: Path) -> dict:
    """加载参考法器.json, 返回 {source_id_str: ref_entry} 映射"""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {str(k): v for k, v in data.items()}


def apply_ref_buffs(weapon: dict, ref: dict) -> None:
    """从参考条目写入 buff 数值到武器"""
    weapon["atk_bonus"] = float(ref.get("atk_buff", 0) or 0)
    weapon["crit_rate"] = int(float(ref.get("crit_buff", 0) or 0) * 100)
    weapon["crit_damage"] = float(ref.get("critatk", 0) or 0)
    weapon["mp_bonus"] = float(ref.get("mp_buff", 0) or 0)


def apply_native_buffs(weapon: dict, rank_idx: int) -> None:
    """给原生武器按品阶分配标准 atk_bonus/crit_rate, 保留现有 crit_damage 和 mp_bonus。"""
    rank = weapon.get("rank", "凡品")

    if rank == "凡品":
        atk, crit, _cd = 凡品_BUFFS
    elif rank in RANK_STANDARD_BUFFS:
        atk, crit, _cd = RANK_STANDARD_BUFFS[rank]
    else:
        return  # 未知品阶不动

    # 3 种模式按 rank_idx 循环: 0=攻击, 1=暴击, 2=混合
    pattern = rank_idx % 3
    if pattern == 0:
        weapon["atk_bonus"] = atk
        weapon["crit_rate"] = 0
    elif pattern == 1:
        weapon["atk_bonus"] = 0.0
        weapon["crit_rate"] = int(crit * 100)
    else:
        weapon["atk_bonus"] = round(atk / 2, 4)
        weapon["crit_rate"] = int(crit * 100 / 2)

    # 保留现有 crit_damage (已在 convert_crit_damage_additive 中从乘法转为加法)
    # 保留现有 mp_bonus (原生武器通常为 0)


def convert_crit_damage_additive(weapon: dict) -> None:
    """将 crit_damage 从乘法完整倍率转为加法增量。

    当前值 > 1.0 表示完整倍率 (如 1.56 = 156% 伤害),
    需转为增量 (0.56), 因为 combat_manager 新公式为 max(1.5, 1.0 + val).
    当前值 <= 1.0 已经是增量格式, 不动。
    """
    cd = weapon.get("crit_damage", 0)
    if cd and cd > 1.0:
        weapon["crit_damage"] = round(cd - 1.0, 4)


def main():
    dry_run = "--dry-run" in sys.argv

    print(f"加载参考文件: {REF_PATH}")
    ref_map = load_reference(REF_PATH)
    print(f"  参考条目: {len(ref_map)}")

    print(f"加载武器文件: {WEAPONS_PATH}")
    with open(WEAPONS_PATH, encoding="utf-8") as f:
        weapons = json.load(f)
    print(f"  总条目: {len(weapons)}")

    # 按 rank 分组原生武器的 index 计数器
    rank_counters: dict[str, int] = {}

    stats = {
        "nonebot_updated": 0,
        "nonebot_no_ref": 0,
        "native_updated": 0,
        "native_skipped": 0,
        "armor_skipped": 0,
        "crit_converted": 0,
    }

    for weapon in weapons:
        wtype = weapon.get("type", "")

        # 防具跳过 (此次只改武器)
        if wtype == "armor":
            stats["armor_skipped"] += 1
            continue

        if wtype != "weapon":
            continue

        # --- 确保 atk_bonus 字段存在 ---
        if "atk_bonus" not in weapon:
            weapon["atk_bonus"] = 0.0

        # --- crit_damage 乘法转加法 (无论 nonebot 还是原生) ---
        old_cd = weapon.get("crit_damage", 0)
        convert_crit_damage_additive(weapon)
        if old_cd and old_cd > 1.0:
            stats["crit_converted"] += 1

        # --- nonebot 合并武器: 按 _source_id 匹配参考文件 ---
        if weapon.get("_source") == "nonebot" and weapon.get("_source_id"):
            ref_id = str(weapon["_source_id"])
            if ref_id in ref_map:
                apply_ref_buffs(weapon, ref_map[ref_id])
                stats["nonebot_updated"] += 1
            else:
                stats["nonebot_no_ref"] += 1
                print(f"  [WARN] 无参考数据: {weapon.get('name')} (_source_id={ref_id})")
            continue

        # --- 原生武器: 按品阶分配标准 buff ---
        rank = weapon.get("rank", "凡品")
        idx = rank_counters.get(rank, 0)
        rank_counters[rank] = idx + 1
        apply_native_buffs(weapon, idx)
        stats["native_updated"] += 1

    # 输出统计
    print("\n=== 重构统计 ===")
    print(f"  nonebot 武器 (已更新):     {stats['nonebot_updated']}")
    print(f"  nonebot 武器 (无参考数据): {stats['nonebot_no_ref']}")
    print(f"  原生武器 (已更新):         {stats['native_updated']}")
    print(f"  原生武器 (跳过):           {stats['native_skipped']}")
    print(f"  防具 (跳过):               {stats['armor_skipped']}")
    print(f"  crit_damage 乘法→加法:     {stats['crit_converted']}")
    print(f"  原生武器品阶分布:")
    for rank, count in sorted(rank_counters.items(),
                              key=lambda x: ["凡品","灵品","地品","天品","皇品","帝品","道品","仙品","混元先天"].index(x[0]) if x[0] in ["凡品","灵品","地品","天品","皇品","帝品","道品","仙品","混元先天"] else 99):
        print(f"    {rank}: {count}")

    if dry_run:
        print("\n[Dry Run] 不写入文件")
        return

    with open(WEAPONS_PATH, "w", encoding="utf-8") as f:
        json.dump(weapons, f, ensure_ascii=False, indent=2)
    print(f"\n已写入: {WEAPONS_PATH}")


if __name__ == "__main__":
    main()
