"""把 nonebot_plugin_xiuxian_2_pmv_lunar 的物品数据合并到本插件的 JSON 配置中。

用法:
    python -m scripts.merge_nonebot_data --source <nonebot_data_dir> --dry-run
    python -m scripts.merge_nonebot_data --source <nonebot_data_dir>

设计原则:
- 同名物品跳过；不同名追加并重新分配 ID
- 不可映射的字段在 description 中保留备注
- 执行前自动备份目标 JSON 到 config/.backup/<timestamp>/
"""
from __future__ import annotations
import argparse
import json
import logging
from pathlib import Path
from typing import Any

from ._common import (
    RANK_TABLE,
    map_nonebot_rank,
    convert_pct_to_abs,
    backup_files,
    load_json,
    dump_json,
    EQUIPMENT_BASE_BY_RANK,
)

logger = logging.getLogger(__name__)


# ---------- 装备属性下限（按品级和类型） ----------
# 防止百分比 buff 过低或为零时，转换出的物品属性全为 0。
# 设为目标均值的 ~40-60%，保证下限保护不会把所有物品拉到同一水平。
_WEAPON_FLOOR = {
    "凡品":   {"physical_damage": 10,  "magic_damage": 0,  "physical_defense": 0,  "magic_defense": 0, "mental_power": 5},
    "灵品":   {"physical_damage": 50,  "magic_damage": 10, "physical_defense": 10, "magic_defense": 0, "mental_power": 20},
    "地品":   {"physical_damage": 100, "magic_damage": 25, "physical_defense": 25, "magic_defense": 10, "mental_power": 40},
    "天品":   {"physical_damage": 200, "magic_damage": 50, "physical_defense": 50, "magic_defense": 20, "mental_power": 80},
    "皇品":   {"physical_damage": 400, "magic_damage": 100,"physical_defense": 100,"magic_defense": 40, "mental_power": 160},
    "帝品":   {"physical_damage": 800, "magic_damage": 200,"physical_defense": 200,"magic_defense": 80, "mental_power": 320},
    "道品":   {"physical_damage": 1600,"magic_damage": 400,"physical_defense": 400,"magic_defense": 160,"mental_power": 640},
    "仙品":   {"physical_damage": 3200,"magic_damage": 800,"physical_defense": 800,"magic_defense": 320,"mental_power": 1280},
    "混元先天": {"physical_damage": 6400,"magic_damage":1600,"physical_defense":1600,"magic_defense": 640,"mental_power": 2560},
}

_ARMOR_FLOOR = {
    "凡品":   {"physical_damage": 0,  "magic_damage": 0,  "physical_defense": 12,  "magic_defense": 8, "mental_power": 0},
    "灵品":   {"physical_damage": 5,  "magic_damage": 5,  "physical_defense": 60,  "magic_defense": 30, "mental_power": 10},
    "地品":   {"physical_damage": 10, "magic_damage": 10, "physical_defense": 120, "magic_defense": 60, "mental_power": 20},
    "天品":   {"physical_damage": 20, "magic_damage": 15, "physical_defense": 240, "magic_defense": 120,"mental_power": 40},
    "皇品":   {"physical_damage": 40, "magic_damage": 30, "physical_defense": 480, "magic_defense": 240,"mental_power": 80},
    "帝品":   {"physical_damage": 80, "magic_damage": 60, "physical_defense": 960, "magic_defense": 480,"mental_power": 160},
    "道品":   {"physical_damage": 160,"magic_damage": 120,"physical_defense": 1920,"magic_defense": 960,"mental_power": 320},
    "仙品":   {"physical_damage": 320,"magic_damage": 240,"physical_defense": 3840,"magic_defense":1920,"mental_power": 640},
    "混元先天": {"physical_damage": 640,"magic_damage": 480,"physical_defense": 7680,"magic_defense":3840,"mental_power":1280},
}

_EQUIP_FLOOR_KEYS = ("physical_damage", "magic_damage", "physical_defense", "magic_defense", "mental_power")


def _apply_equipment_floor(out: dict, rank_name: str, is_weapon: bool) -> None:
    """确保转换后装备的每项属性不低于对应品级下限。"""
    floor = (_WEAPON_FLOOR if is_weapon else _ARMOR_FLOOR).get(rank_name)
    if not floor:
        return
    for k in _EQUIP_FLOOR_KEYS:
        if out.get(k, 0) < floor[k]:
            out[k] = floor[k]


# ============== 单条转换函数 ==============

def convert_equipment_entry(nb_item: dict, new_id: str) -> dict:
    """nonebot 装备条目 -> astrbot weapons.json 单条

    支持两种格式：
    - 旧格式（法器级）：atk_buff/crit_buff/def_buff/mp_buff（百分比浮点）
    - 新格式（凡铁级）：buff: {"攻击": X} / {"生命": X} 等（百分比 buff）

    buff 键映射：
      攻击     -> atk (物理攻击)
      生命     -> df  (物理防御，视为血量加成转防御)
      会心率   -> crit (精神力/暴击)
      抗会心率 -> df   (叠加到防御)
      神魂伤害 -> mp   (法术伤害)
      神魂抵抗 -> df   (叠加到防御)
    """
    rank_name, level_index = map_nonebot_rank(nb_item.get("rank", 60))

    atk = float(nb_item.get("atk_buff", 0) or 0)
    crit = float(nb_item.get("crit_buff", 0) or 0)
    df = float(nb_item.get("def_buff", 0) or 0)
    mp = float(nb_item.get("mp_buff", 0) or 0)

    # 处理 buff 字典格式（覆盖多种属性键）
    buff_dict = nb_item.get("buff", {}) or {}
    if isinstance(buff_dict, dict):
        atk  += float(buff_dict.get("攻击", 0) or 0)
        df   += float(buff_dict.get("生命", 0) or 0)
        crit += float(buff_dict.get("会心率", 0) or 0)
        df   += float(buff_dict.get("抗会心率", 0) or 0)
        mp   += float(buff_dict.get("神魂伤害", 0) or 0)
        df   += float(buff_dict.get("神魂抵抗", 0) or 0)

    # 装备类型推断：含 atk/crit 视为 weapon，否则 armor
    is_weapon = atk > 0 or crit > 0
    item_type = "weapon" if is_weapon else "armor"

    description_extra = []
    nb_level = nb_item.get("level", "")
    if nb_level:
        description_extra.append(f"原级别: {nb_level}")
    nb_critatk = nb_item.get("critatk", 0) or 0
    if nb_critatk:
        description_extra.append(f"原爆伤加成: {nb_critatk}")
    if buff_dict:
        description_extra.append(f"原buff: {buff_dict}")

    out: dict[str, Any] = {
        "id": new_id,
        "name": nb_item["name"],
        "type": item_type,
        "rank": rank_name,
        "required_level_index": level_index,
        "description": "；".join(description_extra) if description_extra else "",
        "physical_damage": convert_pct_to_abs(rank_name, atk, "phys"),
        "magic_damage": convert_pct_to_abs(rank_name, mp, "magic"),
        "physical_defense": convert_pct_to_abs(rank_name, df, "phys_def"),
        "magic_defense": 0,
        "mental_power": convert_pct_to_abs(rank_name, crit, "mental"),
        "price": 0,  # 先占位，下方按战力计算
        "shop_weight": 500,
        "_source": "nonebot",
        "_source_id": nb_item["name"],
    }
    if is_weapon:
        out["weapon_category"] = "剑"

    # 属性下限保护：防止百分比过低导致属性全为 0
    _apply_equipment_floor(out, rank_name, is_weapon)

    # 按战力直接定价（终态价格，无需后续缩放）
    total_power = sum(out.get(k, 0) or 0 for k in _EQUIP_FLOOR_KEYS)
    price_per_power = {
        "凡品": 13890, "灵品": 37035, "地品": 61039, "天品": 78740,
        "皇品": 76610, "帝品": 116740, "道品": 184733, "仙品": 335207,
        "混元先天": 309740,
    }
    bpp = price_per_power.get(rank_name, 13890)
    out["price"] = max(int(total_power * bpp), 1)  # 最低 1，避免 0 价格
    return out


def convert_main_technique_entry(nb_item: dict, new_id: str) -> dict:
    """nonebot 主功法 -> astrbot items.json 单条（type=main_technique）"""
    rank_name, level_index = map_nonebot_rank(nb_item.get("rank", "后天品级"))

    hp = float(nb_item.get("hpbuff", 0) or 0)
    mp = float(nb_item.get("mpbuff", 0) or 0)
    atk = float(nb_item.get("atkbuff", 0) or 0)
    exp_buff = float(nb_item.get("exp_buff", 0) or 0)

    # 把多余字段记入 description
    extra = []
    for k in ("ratebuff", "crit_buff", "def_buff", "dan_exp", "dan_buff",
              "reap_buff", "critatk", "two_buff", "clo_exp", "clo_rs",
              "random_buff", "ew"):
        v = nb_item.get(k, 0)
        if v:
            extra.append(f"{k}={v}")
    desc_extra = ("（原效果: " + ", ".join(extra) + "）") if extra else ""

    # 按 exp_multiplier 定价：exp_multiplier 1.0 ~ 1.7 映射到对应品级的价格区间
    # 基准：凡品主功法价格约 100万，exp_multiplier 越高越贵
    # 品阶基础价格（终态价格）
    # 凡品50-100万 灵品150-300万 地品450-700万 天品1000-3000万
    # 皇品5250-9188万 帝品上限2亿 道品4-7亿 仙品14-16.4亿 混元先天20亿
    base_price_by_rank = {
        "凡品": 167, "灵品": 3000, "地品": 45000, "天品": 125000,
        "皇品": 1500000, "帝品": 4190000, "道品": 20000000, "仙品": 40000000,
        "混元先天": 133333334,
    }
    base = base_price_by_rank.get(rank_name, 3000000)
    # exp_multiplier 加成系数：1.0→1.0, 1.5→2.0, 1.7→2.5
    price_mult = 1.0 + (exp_buff * 1.5)
    price = int(base * price_mult)

    return {
        "id": new_id,
        "name": nb_item["name"],
        "type": "main_technique",
        "rank": rank_name,
        "required_level_index": level_index,
        "description": (nb_item.get("desc", "") or "") + desc_extra,
        "exp_multiplier": 1.0 + exp_buff,
        "spiritual_qi": convert_pct_to_abs(rank_name, mp, "magic"),
        "blood_qi": convert_pct_to_abs(rank_name, hp, "phys"),
        "price": price,
        "shop_weight": 500,
        "_source": "nonebot",
        "_source_id": nb_item["name"],
    }


def convert_sub_technique_entry(nb_item: dict, new_id: str) -> dict:
    """nonebot 辅修功法 -> astrbot items.json 单条（type=technique）"""
    rank_name, level_index = map_nonebot_rank(nb_item.get("rank", "后天品级"))

    # 辅修字段类似但更杂，目前先把 buff/buff2 当作百分比加在主属性
    buff = float(nb_item.get("buff", 0) or 0)

    # 辅修功法价格：比主功法低约 1/3
    # 辅修功法基础价格（终态价格）
    base_price_by_rank = {
        "凡品": 500, "灵品": 3000, "地品": 45000, "天品": 125000,
        "皇品": 1500000, "帝品": 4000000, "道品": 20000000, "仙品": 53333334,
        "混元先天": 133333334,
    }
    price = base_price_by_rank.get(rank_name, 2000000)

    return {
        "id": new_id,
        "name": nb_item["name"],
        "type": "technique",
        "rank": rank_name,
        "required_level_index": level_index,
        "description": nb_item.get("desc", "") or "",
        "exp_multiplier": 1.0 + buff * 0.01,
        "spiritual_qi": 0,
        "blood_qi": 0,
        "price": price,
        "shop_weight": 500,
        "_source": "nonebot",
        "_source_id": nb_item["name"],
    }


def convert_pill_entry(nb_item: dict, new_id: str) -> dict:
    """nonebot 丹药 -> astrbot utility_pills.json 单条（buff_type='hp' 为回血丹示例）"""
    rank_name, level_index = map_nonebot_rank(nb_item.get("rank", 60))
    return {
        "id": new_id,
        "name": nb_item["name"],
        "description": nb_item.get("desc", "") or "",
        "rank": rank_name,
        "subtype": "healing" if nb_item.get("buff_type") == "hp" else "buff",
        "required_level_index": level_index,
        "price": int(nb_item.get("price", 0) or 0),
        "effect_type": "instant",
        "effect": {"heal_hp_pct": float(nb_item.get("buff", 0) or 0)},
        "shop_weight": 500,
        "_source": "nonebot",
        "_source_id": nb_item["name"],
    }


# ============== ID 分配 ==============

def allocate_next_id(existing_entries: list[dict] | dict, prefix: str, width: int = 3) -> str:
    """根据 existing 中以 prefix 开头的 id，分配下一个未使用的 id。"""
    used_numbers: list[int] = []
    iterable = existing_entries.values() if isinstance(existing_entries, dict) else existing_entries
    for entry in iterable:
        eid = entry.get("id", "") if isinstance(entry, dict) else ""
        if isinstance(eid, str) and eid.startswith(prefix):
            tail = eid[len(prefix):]
            if tail.isdigit():
                used_numbers.append(int(tail))
    next_n = (max(used_numbers) + 1) if used_numbers else 1
    return f"{prefix}{next_n:0{width}d}"


# ============== 合并入口 ==============

def merge_entries_into_list(
    target_list: list[dict],
    new_entries: list[dict],
    id_prefix: str,
    converter,
) -> dict:
    """把 nonebot 条目合并到 list 形式的 JSON（如 weapons.json/pills.json）。"""
    existing_names = {e.get("name") for e in target_list if isinstance(e, dict)}
    stats = {"added": 0, "skipped_duplicate": 0}
    for nb in new_entries:
        if nb.get("name") in existing_names:
            stats["skipped_duplicate"] += 1
            continue
        new_id = allocate_next_id(target_list, prefix=id_prefix)
        converted = converter(nb, new_id)
        # 让 converter 写的 _source_id 保留原始 nonebot id，如果传进来了
        if "_source_id" in nb:
            converted["_source_id"] = nb["_source_id"]
        target_list.append(converted)
        existing_names.add(nb["name"])
        stats["added"] += 1
    return stats


def merge_entries_into_dict(
    target_dict: dict[str, dict],
    new_entries: list[dict],
    starting_id: int,
    converter,
) -> dict:
    """把 nonebot 条目合并到 dict 形式的 JSON（如 items.json）。"""
    existing_names = {v.get("name") for v in target_dict.values() if isinstance(v, dict)}
    max_existing = max((int(k) for k in target_dict.keys() if k.isdigit()), default=0)
    next_id = max(max_existing + 1, starting_id)
    stats = {"added": 0, "skipped_duplicate": 0}
    for nb in new_entries:
        if nb.get("name") in existing_names:
            stats["skipped_duplicate"] += 1
            continue
        sid = str(next_id)
        converted = converter(nb, next_id)
        if "_source_id" in nb:
            converted["_source_id"] = nb["_source_id"]
        target_dict[sid] = converted
        existing_names.add(nb["name"])
        next_id += 1
        stats["added"] += 1
    return stats


# ============== CLI ==============

def _load_source_dir(source_root: Path, rel: str) -> dict[str, dict]:
    """读取一个 nonebot JSON 文件，返回带 _source_id 注入的条目列表（用 dict 形式：原 id -> 条目）"""
    p = source_root / rel
    if not p.exists():
        return {}
    data = load_json(p)
    if not isinstance(data, dict):
        return {}
    out: dict[str, dict] = {}
    for src_id, entry in data.items():
        if isinstance(entry, dict) and entry.get("name"):
            entry["_source_id"] = src_id
            out[src_id] = entry
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="合并 nonebot 修仙数据")
    parser.add_argument("--source", required=True, help="nonebot 的 data/xiuxian 目录")
    parser.add_argument("--target", required=True, help="astrbot config 目录")
    parser.add_argument("--dry-run", action="store_true", help="不写文件，仅打印")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    src = Path(args.source)
    tgt = Path(args.target)
    if not src.exists():
        print(f"ERROR: source dir not found: {src}")
        return 2
    if not tgt.exists():
        print(f"ERROR: target dir not found: {tgt}")
        return 2

    prefix = "DRY-RUN: " if args.dry_run else ""

    # 备份目标文件（dry-run 不备份）
    files_to_backup = [tgt / "weapons.json", tgt / "items.json", tgt / "utility_pills.json"]
    if not args.dry_run:
        backup_dest = backup_files(files_to_backup, backup_root=tgt / ".backup")
        print(f"已备份到 {backup_dest}")

    # 1) 装备 -> weapons.json（list）
    weapons = load_json(tgt / "weapons.json") if (tgt / "weapons.json").exists() else []
    eq_files = ["法器.json", "内甲.json", "防具.json", "道袍.json", "道靴.json",
                "本命法宝.json", "辅助法宝.json", "灵戒.json"]
    eq_entries: list[dict] = []
    for f in eq_files:
        for src_id, entry in _load_source_dir(src, f"装备/{f}").items():
            eq_entries.append(entry)
    eq_stats = merge_entries_into_list(weapons, eq_entries, "sword_", convert_equipment_entry)

    # 2) 主功法 -> items.json（dict）
    items = load_json(tgt / "items.json") if (tgt / "items.json").exists() else {}
    main_tech_entries = list(_load_source_dir(src, "功法/主功法.json").values())
    mt_stats = merge_entries_into_dict(items, main_tech_entries, starting_id=5000,
                                       converter=convert_main_technique_entry)

    # 3) 辅修功法 -> items.json
    sub_tech_entries = list(_load_source_dir(src, "功法/辅修功法.json").values())
    st_stats = merge_entries_into_dict(items, sub_tech_entries, starting_id=6000,
                                       converter=convert_sub_technique_entry)

    # 4) 治疗丹 -> utility_pills.json（list）
    util_pills = load_json(tgt / "utility_pills.json") if (tgt / "utility_pills.json").exists() else []
    pill_entries = list(_load_source_dir(src, "丹药/丹药.json").values())
    pill_stats = merge_entries_into_list(util_pills, pill_entries, "util_",
                                         convert_pill_entry)

    print(f"{prefix}装备合并: 新增 {eq_stats['added']} / 跳过同名 {eq_stats['skipped_duplicate']}")
    print(f"{prefix}主功法合并: 新增 {mt_stats['added']} / 跳过同名 {mt_stats['skipped_duplicate']}")
    print(f"{prefix}辅修功法合并: 新增 {st_stats['added']} / 跳过同名 {st_stats['skipped_duplicate']}")
    print(f"{prefix}治疗丹合并: 新增 {pill_stats['added']} / 跳过同名 {pill_stats['skipped_duplicate']}")

    if args.dry_run:
        print("DRY-RUN: 未写入任何文件")
        return 0

    dump_json(tgt / "weapons.json", weapons)
    dump_json(tgt / "items.json", items)
    dump_json(tgt / "utility_pills.json", util_pills)
    print("写入完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
