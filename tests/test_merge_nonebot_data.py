from scripts._common import (
    map_nonebot_rank,
    convert_pct_to_abs,
)
from scripts.merge_nonebot_data import (
    convert_equipment_entry,
    convert_main_technique_entry,
    convert_sub_technique_entry,
    convert_pill_entry,
)


def test_map_nonebot_rank_low_rank_is_fanpin():
    """nonebot rank 越大越低，rank=99 落在天品段（99 >= 95）"""
    name, lvl = map_nonebot_rank(99)
    assert name == "天品"
    assert lvl == 13


def test_map_nonebot_rank_high_rank_is_xianpin():
    """rank=-50 应该是仙品（fallback: -50 >= -9999 且不匹配其他阈值）"""
    name, lvl = map_nonebot_rank(-50)
    assert name == "仙品"
    assert lvl == 32


def test_map_nonebot_rank_mid_range():
    """rank=45 落在天品段（45 >= 29）"""
    name, lvl = map_nonebot_rank(45)
    assert name == "天品"
    assert lvl == 13


def test_map_nonebot_rank_upper_range_distribution():
    """验证 rank 60-215 区间的品级分布"""
    cases = {
        215: ("混元先天", 35),
        192: ("仙品", 32),
        180: ("道品", 28),
        167: ("道品", 28),
        155: ("帝品", 22),
        142: ("帝品", 22),
        130: ("皇品", 16),
        117: ("天品", 13),
        105: ("天品", 13),
        92:  ("地品", 12),
        80:  ("灵品", 10),
        67:  ("灵品", 10),
        60:  ("凡品", 0),
    }
    for rank, expected in cases.items():
        assert map_nonebot_rank(rank) == expected, f"rank={rank}"


def test_map_nonebot_rank_technique_text_ranks():
    """验证功法文字 rank 映射"""
    cases = {
        "后天品级": ("凡品", 0),
        "先天品级": ("凡品", 0),
        "神丹品级": ("灵品", 10),
        "虚劫品级": ("地品", 12),
        "神海品级": ("天品", 13),
        "神极品级": ("皇品", 16),
        "界主品级": ("帝品", 22),
        "真神品级": ("道品", 28),
        "圣人唯一": ("仙品", 32),
        "永恒仙法": ("仙品", 32),
        "至圣品级": ("仙品", 32),
        "龙年限定": ("仙品", 32),
    }
    for rank, expected in cases.items():
        assert map_nonebot_rank(rank) == expected, f"rank={rank}"


def test_convert_pct_to_abs_basic():
    """凡品 phys base=120，buff=0.5 -> 60"""
    assert convert_pct_to_abs("凡品", 0.5, "phys") == 60


def test_convert_equipment_entry_basic():
    """nonebot 武器条目转换为 astrbot weapons.json 格式"""
    nb_item = {
        "name": "精铁符剑",
        "atk_buff": 0.08,
        "crit_buff": 0,
        "def_buff": 0,
        "critatk": 0,
        "zw": 0,
        "mp_buff": 0,
        "rank": 54,
        "level": "下品符器",
        "type": "装备",
    }
    out = convert_equipment_entry(nb_item, new_id="sword_999")
    assert out["id"] == "sword_999"
    assert out["name"] == "精铁符剑"
    assert out["type"] == "weapon"
    assert out["rank"] == "灵品"  # rank=54 -> 灵品
    assert out["required_level_index"] == 10
    # phys base 灵品=1700, atk_buff=0.08 -> 136
    assert out["physical_damage"] == 136
    assert out["_source"] == "nonebot"
    assert out["_source_id"] == "精铁符剑"  # 源 ID 占位，调用方传


from scripts.merge_nonebot_data import (
    allocate_next_id,
    merge_entries_into_list,
    merge_entries_into_dict,
)


def test_allocate_next_id_with_existing_sword_ids():
    existing = [{"id": "sword_001"}, {"id": "sword_003"}, {"id": "axe_001"}]
    assert allocate_next_id(existing, prefix="sword_", width=3) == "sword_004"


def test_allocate_next_id_empty():
    assert allocate_next_id([], prefix="exp_pill_", width=3) == "exp_pill_001"


def test_merge_entries_into_list_skips_duplicate_names():
    existing = [{"id": "sword_001", "name": "青铜剑"}]
    new_entries = [
        {"name": "青铜剑", "atk_buff": 0.1, "rank": 60},  # 同名，应跳过
        {"name": "玄铁剑", "atk_buff": 0.15, "rank": 50}, # 新增
    ]
    stats = merge_entries_into_list(
        target_list=existing,
        new_entries=new_entries,
        id_prefix="sword_",
        converter=lambda nb, nid: {"id": nid, "name": nb["name"], "_source": "nonebot"},
    )
    assert stats["added"] == 1
    assert stats["skipped_duplicate"] == 1
    assert len(existing) == 2
    assert existing[1]["name"] == "玄铁剑"
    assert existing[1]["id"] == "sword_002"


def test_merge_entries_into_dict_skips_duplicate_names():
    existing = {"1001": {"name": "一品气血丹"}}
    new_entries = [
        {"name": "一品气血丹"},
        {"name": "生骨丹"},
    ]
    stats = merge_entries_into_dict(
        target_dict=existing,
        new_entries=new_entries,
        starting_id=1100,
        converter=lambda nb, nid: {"id": str(nid), "name": nb["name"], "_source": "nonebot"},
    )
    assert stats["added"] == 1
    assert stats["skipped_duplicate"] == 1
    assert "1100" in existing
    assert existing["1100"]["name"] == "生骨丹"


import subprocess
import sys
from pathlib import Path

from tests.conftest import write_json, read_json


def test_main_dry_run_does_not_modify_target(tmp_path):
    """--dry-run 不应写文件，且应输出统计行"""
    source = tmp_path / "source"
    (source / "装备").mkdir(parents=True)
    (source / "丹药").mkdir(parents=True)
    (source / "功法").mkdir(parents=True)

    write_json(source / "装备" / "法器.json", {
        "7001": {"name": "精铁符剑", "atk_buff": 0.08, "rank": 54, "level": "下品符器", "type": "装备"}
    })
    write_json(source / "丹药" / "丹药.json", {
        "1101": {"name": "生骨丹", "buff_type": "hp", "buff": 0.05, "price": 100, "rank": 56}
    })
    write_json(source / "功法" / "主功法.json", {
        "9001": {"name": "吐纳功法", "hpbuff": 0.2, "atkbuff": 0.1, "rank": "55"}
    })
    write_json(source / "功法" / "辅修功法.json", {})

    target = tmp_path / "config"
    target.mkdir()
    write_json(target / "weapons.json", [])
    write_json(target / "items.json", {})
    write_json(target / "utility_pills.json", [])

    result = subprocess.run(
        [sys.executable, "-m", "scripts.merge_nonebot_data",
         "--source", str(source), "--target", str(target), "--dry-run"],
        cwd=str(Path(__file__).resolve().parent.parent),
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    # 文件保持空
    assert read_json(target / "weapons.json") == []
    assert read_json(target / "items.json") == {}
    assert read_json(target / "utility_pills.json") == []
    # 输出统计
    assert "DRY-RUN" in result.stdout or "dry-run" in result.stdout.lower()


def test_main_real_run_writes_files_and_backup(tmp_path):
    source = tmp_path / "source"
    (source / "装备").mkdir(parents=True)
    (source / "丹药").mkdir(parents=True)
    (source / "功法").mkdir(parents=True)
    write_json(source / "装备" / "法器.json", {
        "7001": {"name": "精铁符剑", "atk_buff": 0.08, "rank": 54, "level": "下品符器", "type": "装备"}
    })
    write_json(source / "丹药" / "丹药.json", {})
    write_json(source / "功法" / "主功法.json", {})
    write_json(source / "功法" / "辅修功法.json", {})

    target = tmp_path / "config"
    target.mkdir()
    write_json(target / "weapons.json", [])
    write_json(target / "items.json", {})
    write_json(target / "utility_pills.json", [])

    result = subprocess.run(
        [sys.executable, "-m", "scripts.merge_nonebot_data",
         "--source", str(source), "--target", str(target)],
        cwd=str(Path(__file__).resolve().parent.parent),
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    weapons = read_json(target / "weapons.json")
    assert len(weapons) == 1
    assert weapons[0]["name"] == "精铁符剑"
    # 自动备份
    backup_dir = target / ".backup"
    assert backup_dir.exists()
    timestamps = list(backup_dir.iterdir())
    assert len(timestamps) >= 1
