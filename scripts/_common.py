"""共享工具：备份、品级映射。供 merge_nonebot_data.py 使用。"""
from __future__ import annotations
import json
import shutil
import time
from pathlib import Path
from typing import Any


# ---------- 备份 ----------

def backup_files(files: list[Path], backup_root: Path) -> Path:
    """把 files 列表中存在的文件复制到 backup_root/<timestamp>/ 下，返回时间戳目录路径。"""
    ts = time.strftime("%Y%m%d_%H%M%S")
    dest = backup_root / ts
    dest.mkdir(parents=True, exist_ok=True)
    for f in files:
        if f.exists():
            shutil.copy2(f, dest / f.name)
    return dest


# ---------- JSON IO ----------

def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ---------- 品级映射（nonebot rank 数字 -> astrbot 品级名 + level_index） ----------

RANK_TABLE = [
    # (nonebot_rank_threshold_inclusive, astrbot_rank_name, required_level_index)
    # nonebot rank 越大越低级（数字越小越高级）；表按 threshold 从大到小排列。
    # map_nonebot_rank() 从头遍历，首个 r >= threshold 命中。
    (210, "混元先天", 35),   # rank 215 太极          → 1 件
    (185, "仙品",     32),   # rank 192 太素          → 6 件
    (158, "道品",     28),   # rank 180,167 太初/太易  → 18 件
    (140, "帝品",     22),   # rank 155,142 太阳/紫薇  → 24 件
    (118, "皇品",     16),   # rank 130 离火          → 12 件
    (95,  "天品",     13),   # rank 117,105 灵胚/灵纹  → 24 件
    (82,  "地品",     12),   # rank 92 血淬           → 6 件
    (63,  "灵品",     10),   # rank 80,67 精练/凡铁    → 187 件
    (60,  "凡品",      0),   # rank 60 凡铁/法器      → 37 件
    # ---- rank < 60 的低品级映射 ----
    (53,  "灵品",     10),   # rank 55,54 符器        → 23 件
    (47,  "地品",     12),   # rank 51,48 玄器/法器    → 9 件
    (29,  "天品",     13),   # rank 45,42,...,30 灵器  → 36 件
    (23,  "皇品",     16),   # rank 27,24 宝器        → 7 件
    (11,  "帝品",     22),   # rank 19,...,12 圣器     → 9 件
    (0,   "道品",     28),   # rank -5 极品仙器       → 61 件
    (-9999, "仙品",   32),   # fallback
]

# nonebot 文字等级 -> astrbot 品级（装备 rank 文字 + 功法 rank 文字）
# 注：level_index 使用正确的 AstrBot 值（非旧版 legacy 值）
RANK_TEXT_MAP = {
    # ---- 凡品 ----
    "后天品级": ("凡品", 0),
    "凡铁": ("凡品", 0),
    "先天品级": ("凡品", 0),
    # ---- 灵品 ----
    "下品符器": ("灵品", 10),
    "上品符器": ("灵品", 10),
    "中品符器": ("灵品", 10),
    "神丹品级": ("灵品", 10),
    # ---- 地品 ----
    "下品玄器": ("地品", 12),
    "上品玄器": ("地品", 12),
    "中品玄器": ("地品", 12),
    "虚劫品级": ("地品", 12),
    "生死品级": ("地品", 12),
    # ---- 天品 ----
    "下品灵器": ("天品", 13),
    "上品灵器": ("天品", 13),
    "中品灵器": ("天品", 13),
    "神海品级": ("天品", 13),
    "神劫品级": ("天品", 13),
    # ---- 皇品 ----
    "下品宝器": ("皇品", 16),
    "上品宝器": ("皇品", 16),
    "中品宝器": ("皇品", 16),
    "神极品级": ("皇品", 16),
    "神变品级": ("皇品", 16),
    # ---- 帝品 ----
    "极品宝器": ("帝品", 22),
    "下品圣器": ("帝品", 22),
    "中品圣器": ("帝品", 22),
    "界主品级": ("帝品", 22),
    "天尊品级": ("帝品", 22),
    # ---- 道品 ----
    "上品圣器": ("道品", 28),
    "极品圣器": ("道品", 28),
    "真神品级": ("道品", 28),
    "荒神品级": ("道品", 28),
    # ---- 仙品 ----
    "仙器": ("仙品", 32),
    "仙品": ("仙品", 32),
    "圣人品级": ("仙品", 32),
    "圣人唯一": ("仙品", 32),
    "永恒仙法": ("仙品", 32),
    "永恒仙笈": ("仙品", 32),
    "至圣品级": ("仙品", 32),
    "龙年限定": ("仙品", 32),
    "蛇年限定": ("仙品", 32),
}


def map_nonebot_rank(nb_rank: int | float | str) -> tuple[str, int]:
    """nonebot 的 rank -> (astrbot 品级名, required_level_index)。

    支持：
    - 数字 rank（越大越低级）：按 RANK_TABLE 降序阈值匹配
    - 字符串 rank：先检查 RANK_TEXT_MAP，再尝试转数字
    """
    if isinstance(nb_rank, str):
        stripped = nb_rank.strip()
        if stripped in RANK_TEXT_MAP:
            return RANK_TEXT_MAP[stripped]
        try:
            r = int(float(stripped))
        except (TypeError, ValueError):
            return "凡品", 0
    else:
        try:
            r = int(float(nb_rank))
        except (TypeError, ValueError):
            return "凡品", 0
    for threshold, name, lvl in RANK_TABLE:
        if r >= threshold:
            return name, lvl
    return "仙品", 70


# ---------- 装备百分比 buff -> 绝对值的品级 base 表 ----------
# 数值来自 astrbot 原生装备各品级的属性均值，用于将 nonebot 百分比 buff
# 转换为与原生物品同等量级的绝对值。

EQUIPMENT_BASE_BY_RANK = {
    # 百分比 buff -> 绝对值的基准。按 nonebot 典型 buff 百分比反推，使转换后
    # 典型物品的总属性力 ≈ astrbot 原生同品级武器均值的 80-90%。
    # 凡品基准值显著低于其他品级，因为 nonebot 凡品 buff 幅度远高于高品级。
    "凡品": {"phys": 120,   "magic": 80,   "phys_def": 100,  "magic_def": 80,   "mental": 90},
    "灵品": {"phys": 1700,  "magic": 1000, "phys_def": 1400, "magic_def": 1000, "mental": 1200},
    "地品": {"phys": 1700,  "magic": 1000, "phys_def": 1400, "magic_def": 1000, "mental": 1200},
    "天品": {"phys": 1800,  "magic": 1100, "phys_def": 1400, "magic_def": 1100, "mental": 1300},
    "皇品": {"phys": 2500,  "magic": 1500, "phys_def": 2000, "magic_def": 1500, "mental": 1800},
    "帝品": {"phys": 4000,  "magic": 2400, "phys_def": 3200, "magic_def": 2400, "mental": 2800},
    "道品": {"phys": 6000,  "magic": 3600, "phys_def": 4800, "magic_def": 3600, "mental": 4200},
    "仙品": {"phys": 8600,  "magic": 5200, "phys_def": 6900, "magic_def": 5200, "mental": 6000},
    "混元先天": {"phys": 17200, "magic": 10400,"phys_def": 13800,"magic_def": 10400,"mental": 12000},
}


def convert_pct_to_abs(rank_name: str, pct: float, attr: str) -> int:
    """把 nonebot 百分比 buff 转为 astrbot 绝对值。attr ∈ phys/magic/phys_def/magic_def/mental。"""
    base = EQUIPMENT_BASE_BY_RANK.get(rank_name, EQUIPMENT_BASE_BY_RANK["凡品"])
    try:
        return int(round(base[attr] * float(pct)))
    except (TypeError, ValueError, KeyError):
        return 0

