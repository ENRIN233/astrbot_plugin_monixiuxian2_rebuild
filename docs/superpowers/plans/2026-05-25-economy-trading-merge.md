# 经济量级调整 + 玩家交易系统 + nonebot 数据合并 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现三个变更：(A) 将 nonebot 修仙插件的物品数据合并到 astrbot 插件 JSON 配置；(B) 把整个经济体系价格/产出按分层倍率缩放到百万/千万/亿量级；(C) 新增玩家间即时交易和寄售行两套交易系统。

**Architecture:**
- **数据合并** 通过独立脚本 `scripts/merge_nonebot_data.py` 完成（dry-run 支持、自动备份），不影响运行时代码
- **经济缩放** 通过独立脚本 `scripts/rebalance_economy.py` 完成，按品级/价格段查表缩放，运行后产生新 JSON
- **交易系统** 遵循现有 handlers/managers 模式：新增 `TradeManager`、`ConsignmentManager` + 对应 handler，新增 v21 数据库迁移（trades + consignment_listings 表），在 `main.py` 注册命令并启动寄售过期检查后台任务

**Tech Stack:** Python 3.10+、aiosqlite、AstrBot Plugin SDK、pytest（新建测试基础设施）

**前置说明：** 本仓库目前**没有 tests/ 目录**。本计划按 TDD 风格组织，并在 Phase A 第 1 个任务先建立 pytest 基础设施（pytest + pytest-asyncio + 配置）。

---

## File Structure

### 新增文件

| 文件 | 责任 |
|---|---|
| `scripts/__init__.py` | 脚本包标记（空文件，仅用于 import） |
| `scripts/merge_nonebot_data.py` | nonebot 数据合并：读取源 JSON、按规则映射字段、查重、追加写回；支持 --dry-run、自动备份 |
| `scripts/rebalance_economy.py` | 经济缩放：按品级/价格段查表缩放价格 + 产出；支持 --dry-run、自动备份 |
| `scripts/_common.py` | 共享：备份/恢复函数、品级映射常量、缩放常量 |
| `handlers/trade_handler.py` | 即时交易命令处理（8 个命令） |
| `handlers/consignment_handler.py` | 寄售行命令处理（5 个命令） |
| `managers/trade_manager.py` | 即时交易业务逻辑（含托管、超时、原子完成） |
| `managers/consignment_manager.py` | 寄售业务逻辑（上架、购买、过期、下架） |
| `tests/__init__.py` | pytest 包标记 |
| `tests/conftest.py` | pytest 共享 fixtures（in-memory db） |
| `tests/test_merge_nonebot_data.py` | 合并脚本测试 |
| `tests/test_rebalance_economy.py` | 缩放脚本测试 |
| `tests/test_trade_manager.py` | 即时交易业务逻辑测试 |
| `tests/test_consignment_manager.py` | 寄售业务逻辑测试 |
| `pytest.ini` | pytest 配置 |
| `requirements-dev.txt` | dev 依赖（pytest、pytest-asyncio） |

### 修改文件

| 文件 | 改动 |
|---|---|
| `main.py` | 注册 13 个新命令；初始化两个新 manager/handler；启动寄售过期后台任务；terminate 时取消任务 |
| `models_extended.py` | `UserStatus` 枚举新增 `TRADING = 5` |
| `handlers/utils.py` | 在 `BUSY_STATE_ALLOWED_COMMANDS` 加入 `"寄售行"`、`"我的寄售"` |
| `handlers/__init__.py` | 导出 `TradeHandler`、`ConsignmentHandler` |
| `managers/__init__.py` | 导出 `TradeManager`、`ConsignmentManager` |
| `data/migration.py` | 新增 `@migration(21)`：建 `trades`、`consignment_listings` 表 + 索引；`LATEST_DB_VERSION = 21`；`_create_all_tables_v2` 同步包含这两张表 |
| `config/*.json`（10 个文件） | 由 Phase A/B 脚本写入，不需要手改 |

---

## Phase Overview

| Phase | 目标 | 任务数 |
|---|---|---|
| Phase A | nonebot 数据合并 | 任务 1–7 |
| Phase B | 经济量级缩放 | 任务 8–12 |
| Phase C | 玩家交易系统 | 任务 13–22 |
| Phase D | 端到端冒烟验证 | 任务 23 |

---

## Phase A：nonebot 数据合并

### Task 1: 建立测试基础设施 + scripts 骨架

**Files:**
- Create: `pytest.ini`
- Create: `requirements-dev.txt`
- Create: `tests/__init__.py`（空文件）
- Create: `tests/conftest.py`
- Create: `scripts/__init__.py`（空文件）
- Create: `scripts/_common.py`

- [ ] **Step 1: 写 pytest.ini**

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

- [ ] **Step 2: 写 requirements-dev.txt**

```
pytest>=7.0
pytest-asyncio>=0.21
aiosqlite>=0.19
```

- [ ] **Step 3: 创建空 `tests/__init__.py` 和 `scripts/__init__.py`**

两个文件均为 0 字节（用于使目录被识别为 Python 包）。

- [ ] **Step 4: 写 tests/conftest.py（共享 fixtures）**

> **导入策略说明**：本插件的内部模块使用相对导入（如 `from ..config_manager import ...`），从 plugin 根目录直接 `python -m pytest` 会因相对导入失败。conftest.py 通过 **创建一个空的 `__init__.py` 并用 `types.ModuleType` 注册包名** `astrbot_plugin_monixiuxian2` 指向当前 plugin 目录。

```python
import sys
import json
import types
from pathlib import Path
import pytest
import pytest_asyncio
import aiosqlite

# ============== 在导入任何插件代码之前 mock astrbot.* ==============
# 插件依赖 astrbot.api.logger / astrbot.api.event 等，运行时由 AstrBot 提供。
# 测试环境用 stub 替代，避免 ImportError。
def _make_stub(name: str) -> types.ModuleType:
    m = types.ModuleType(name)
    return m

if "astrbot" not in sys.modules:
    astrbot = _make_stub("astrbot")
    astrbot_api = _make_stub("astrbot.api")
    astrbot_api_event = _make_stub("astrbot.api.event")
    astrbot_api_star = _make_stub("astrbot.api.star")
    astrbot_api_message_components = _make_stub("astrbot.api.message_components")

    # logger
    import logging as _logging
    astrbot_api.logger = _logging.getLogger("astrbot_stub")
    astrbot_api.AstrBotConfig = dict  # 简单替代

    # event stubs
    class _AstrMessageEvent: pass
    class _MessageChain:
        def message(self, *a, **k): return self
    class _Filter:
        def command(self, *a, **k):
            def deco(f): return f
            return deco
    astrbot_api_event.AstrMessageEvent = _AstrMessageEvent
    astrbot_api_event.MessageChain = _MessageChain
    astrbot_api_event.filter = _Filter()

    # star stubs
    class _Star: pass
    class _Context: pass
    class _StarTools:
        @staticmethod
        def get_data_dir(name): return Path("/tmp")
    astrbot_api_star.Star = _Star
    astrbot_api_star.Context = _Context
    astrbot_api_star.StarTools = _StarTools

    # message components stubs
    class _At: pass
    class _Plain:
        def __init__(self, text=""): self.text = text
    astrbot_api_message_components.At = _At
    astrbot_api_message_components.Plain = _Plain

    sys.modules["astrbot"] = astrbot
    sys.modules["astrbot.api"] = astrbot_api
    sys.modules["astrbot.api.event"] = astrbot_api_event
    sys.modules["astrbot.api.star"] = astrbot_api_star
    sys.modules["astrbot.api.message_components"] = astrbot_api_message_components

# ============== 把插件目录注册为 astrbot_plugin_monixiuxian2 包 ==============
_PLUGIN_DIR = Path(__file__).resolve().parent.parent
_PLUGIN_NAME = "astrbot_plugin_monixiuxian2"

if _PLUGIN_NAME not in sys.modules:
    pkg = types.ModuleType(_PLUGIN_NAME)
    pkg.__path__ = [str(_PLUGIN_DIR)]  # 作为命名空间包
    sys.modules[_PLUGIN_NAME] = pkg

# scripts 目录直接作为顶层包（无相对导入问题）
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))


@pytest.fixture
def tmp_config_dir(tmp_path):
    """生成一个临时 config 目录"""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


@pytest_asyncio.fixture
async def memory_db():
    """生成内存 SQLite 连接"""
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    yield conn
    await conn.close()


def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))
```

> **导入约定**：
> - `scripts/` 下的模块作为顶层包导入：`from scripts._common import ...`（因 plugin 目录在 sys.path）
> - 内部插件模块通过注册的包名导入：`from astrbot_plugin_monixiuxian2.data.migration import ...`
> - 这样 `migration.py` 中的 `from ..config_manager import ConfigManager` 会解析为 `astrbot_plugin_monixiuxian2.config_manager`，与运行时一致

- [ ] **Step 5: 写 scripts/_common.py**

```python
"""共享工具：备份、品级映射、缩放常量。供 merge_nonebot_data.py 和 rebalance_economy.py 使用。"""
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
    # (nonebot_rank_threshold_inclusive_low, astrbot_rank_name, required_level_index)
    # 注：nonebot rank 越小越高级；表项按 astrbot 品级从低到高排列
    (60, "凡品",   0),
    (50, "灵品",   10),
    (40, "地品",   20),
    (30, "天品",   30),
    (20, "皇品",   40),
    (10, "帝品",   50),
    (0,  "道品",   60),
    (-9999, "仙品", 70),
]


def map_nonebot_rank(nb_rank: int | float | str) -> tuple[str, int]:
    """nonebot 的 rank 数字 -> (astrbot 品级名, required_level_index)。"""
    try:
        r = int(float(nb_rank))
    except (TypeError, ValueError):
        return "凡品", 0
    for threshold, name, lvl in RANK_TABLE:
        if r >= threshold:
            return name, lvl
    return "仙品", 70


# ---------- 装备百分比 buff -> 绝对值的品级 base 表 ----------

EQUIPMENT_BASE_BY_RANK = {
    "凡品": {"phys": 15,    "magic": 10,   "phys_def": 8,    "magic_def": 5,    "mental": 8},
    "灵品": {"phys": 80,    "magic": 60,   "phys_def": 40,   "magic_def": 30,   "mental": 35},
    "地品": {"phys": 200,   "magic": 150,  "phys_def": 100,  "magic_def": 80,   "mental": 80},
    "天品": {"phys": 500,   "magic": 400,  "phys_def": 250,  "magic_def": 200,  "mental": 200},
    "皇品": {"phys": 1000,  "magic": 800,  "phys_def": 500,  "magic_def": 400,  "mental": 400},
    "帝品": {"phys": 2200,  "magic": 1800, "phys_def": 1100, "magic_def": 900,  "mental": 900},
    "道品": {"phys": 5000,  "magic": 4000, "phys_def": 2500, "magic_def": 2000, "mental": 2000},
    "仙品": {"phys": 10000, "magic": 8000, "phys_def": 5000, "magic_def": 4000, "mental": 4000},
    "混元先天": {"phys": 20000, "magic": 16000, "phys_def": 10000, "magic_def": 8000, "mental": 8000},
}


def convert_pct_to_abs(rank_name: str, pct: float, attr: str) -> int:
    """把 nonebot 百分比 buff 转为 astrbot 绝对值。attr ∈ phys/magic/phys_def/magic_def/mental。"""
    base = EQUIPMENT_BASE_BY_RANK.get(rank_name, EQUIPMENT_BASE_BY_RANK["凡品"])
    try:
        return int(round(base[attr] * float(pct)))
    except (TypeError, ValueError, KeyError):
        return 0


# ---------- 经济缩放表（任务 8 后才用，先放这里集中维护） ----------

# 装备/功法：按 astrbot 品级整体缩放
RANK_PRICE_MULTIPLIER = {
    "凡品":   3000,
    "灵品":   500,
    "地品":   100,
    "天品":   80,
    "皇品":   35,
    "帝品":   25,
    "道品":   20,
    "仙品":   20,
    "混元先天": 15,
}

# 无品级字段时按价格段缩放
PRICE_BAND_MULTIPLIER = [
    # (上限不含, 倍率)
    (1_000,        3000),
    (10_000,       500),
    (100_000,      100),
    (1_000_000,    50),
    (10_000_000,   30),
    (100_000_000,  20),
    (10**18,       10),
]


def price_band_mult(price: int) -> int:
    for ceil, mult in PRICE_BAND_MULTIPLIER:
        if price < ceil:
            return mult
    return 10


def round_to_万(value: int) -> int:
    """四舍五入到万位（10000）"""
    return int(round(value / 10000.0)) * 10000
```

- [ ] **Step 6: 验证基础设施可用**

```bash
cd "E:/Github/astrbot_plugin_monixiuxian2-main"
python -m pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

Expected: `no tests ran in X seconds` (没有测试用例但 pytest 启动成功，没有 import 错误)。

- [ ] **Step 7: Commit**

```bash
git add pytest.ini requirements-dev.txt tests/__init__.py tests/conftest.py scripts/__init__.py scripts/_common.py
git commit -m "chore: scaffold pytest infrastructure and scripts/_common"
```

---

### Task 2: nonebot 装备字段映射函数（TDD）

**Files:**
- Modify: `scripts/_common.py`（在文件末尾追加）
- Test: `tests/test_merge_nonebot_data.py`

- [ ] **Step 1: 写失败测试**

`tests/test_merge_nonebot_data.py`:

```python
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
    """nonebot rank 越大越低，rank=99 应该是凡品"""
    name, lvl = map_nonebot_rank(99)
    assert name == "凡品"
    assert lvl == 0


def test_map_nonebot_rank_high_rank_is_xianpin():
    """rank=-50 应该是仙品"""
    name, lvl = map_nonebot_rank(-50)
    assert name == "仙品"
    assert lvl == 70


def test_map_nonebot_rank_mid_range():
    """rank=45 落在地品段"""
    name, lvl = map_nonebot_rank(45)
    assert name == "地品"
    assert lvl == 20


def test_convert_pct_to_abs_basic():
    """凡品 phys base=15，buff=0.5 -> 8"""
    assert convert_pct_to_abs("凡品", 0.5, "phys") == 8


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
    # phys base 灵品=80, atk_buff=0.08 -> 6
    assert out["physical_damage"] == 6
    assert out["_source"] == "nonebot"
    assert out["_source_id"] == "精铁符剑"  # 源 ID 占位，调用方传

```

- [ ] **Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_merge_nonebot_data.py -v
```

Expected: 全部失败，提示 `cannot import name 'convert_equipment_entry'` 或类似。

- [ ] **Step 3: 创建 scripts/merge_nonebot_data.py 骨架（仅放入这些函数让测试通过）**

```python
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


# ============== 单条转换函数 ==============

def convert_equipment_entry(nb_item: dict, new_id: str) -> dict:
    """nonebot 装备条目 -> astrbot weapons.json 单条"""
    rank_name, level_index = map_nonebot_rank(nb_item.get("rank", 60))

    atk = float(nb_item.get("atk_buff", 0) or 0)
    crit = float(nb_item.get("crit_buff", 0) or 0)
    df = float(nb_item.get("def_buff", 0) or 0)
    mp = float(nb_item.get("mp_buff", 0) or 0)

    # 装备类型推断：含 atk_buff/crit_buff 视为 weapon，否则 armor
    is_weapon = atk > 0 or crit > 0
    item_type = "weapon" if is_weapon else "armor"

    description_extra = []
    nb_level = nb_item.get("level", "")
    if nb_level:
        description_extra.append(f"原级别: {nb_level}")
    nb_critatk = nb_item.get("critatk", 0) or 0
    if nb_critatk:
        description_extra.append(f"原爆伤加成: {nb_critatk}")

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
        "price": int(nb_item.get("price", 0) or 0),
        "shop_weight": 500,
        "_source": "nonebot",
        "_source_id": nb_item["name"],  # 由调用方覆盖为原始 ID
    }
    if is_weapon:
        out["weapon_category"] = "剑"  # 缺省类别，nonebot 数据没有这个字段
    return out


def convert_main_technique_entry(nb_item: dict, new_id: str) -> dict:
    """nonebot 主功法 -> astrbot items.json 单条（type=main_technique）"""
    rank_name, level_index = map_nonebot_rank(nb_item.get("rank", "55"))

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
        "price": 0,
        "shop_weight": 500,
        "_source": "nonebot",
        "_source_id": nb_item["name"],
    }


def convert_sub_technique_entry(nb_item: dict, new_id: str) -> dict:
    """nonebot 辅修功法 -> astrbot items.json 单条（type=technique）"""
    rank_name, level_index = map_nonebot_rank(nb_item.get("rank", "55"))

    # 辅修字段类似但更杂，目前先把 buff/buff2 当作百分比加在主属性
    buff = float(nb_item.get("buff", 0) or 0)
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
        "price": 0,
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


# ============== CLI（占位，下一个任务实现） ==============

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="合并 nonebot 修仙数据")
    parser.add_argument("--source", required=True, help="nonebot 的 data/xiuxian 目录")
    parser.add_argument("--target", required=True, help="astrbot config 目录")
    parser.add_argument("--dry-run", action="store_true", help="不写文件，仅打印")
    args = parser.parse_args(argv)
    raise NotImplementedError("main() 在 Task 3 实现")


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 跑测试确认通过**

```bash
python -m pytest tests/test_merge_nonebot_data.py -v
```

Expected: 5 个测试全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add scripts/merge_nonebot_data.py tests/test_merge_nonebot_data.py
git commit -m "feat(scripts): add nonebot entry conversion functions"
```

---

### Task 3: ID 分配 + 同名查重 + 合并入口

**Files:**
- Modify: `scripts/merge_nonebot_data.py`（替换 `main()` 并新增辅助函数）
- Modify: `tests/test_merge_nonebot_data.py`

- [ ] **Step 1: 追加失败测试**

在 `tests/test_merge_nonebot_data.py` 末尾追加：

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

```bash
python -m pytest tests/test_merge_nonebot_data.py -v
```

Expected: 新增 4 个测试 FAIL（import error）。

- [ ] **Step 3: 在 `scripts/merge_nonebot_data.py` 中实现这些函数**

在 `convert_pill_entry` 函数之后、`main()` 之前插入：

```python
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
    next_id = max((int(k) for k in target_dict.keys() if k.isdigit()), default=starting_id - 1) + 1
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
```

- [ ] **Step 4: 跑测试确认通过**

```bash
python -m pytest tests/test_merge_nonebot_data.py -v
```

Expected: 9 个测试全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add scripts/merge_nonebot_data.py tests/test_merge_nonebot_data.py
git commit -m "feat(scripts): add ID allocation and merge orchestration"
```

---

### Task 4: 合并 CLI + 备份 + dry-run

**Files:**
- Modify: `scripts/merge_nonebot_data.py`（实现 `main()`）
- Modify: `tests/test_merge_nonebot_data.py`

- [ ] **Step 1: 追加失败测试**

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

```bash
python -m pytest tests/test_merge_nonebot_data.py::test_main_dry_run_does_not_modify_target -v
```

Expected: FAIL（`NotImplementedError`）

- [ ] **Step 3: 实现 main()**

替换 `scripts/merge_nonebot_data.py` 末尾的 `main()`：

```python
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
```

- [ ] **Step 4: 跑测试确认通过**

```bash
python -m pytest tests/test_merge_nonebot_data.py -v
```

Expected: 11 个测试全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add scripts/merge_nonebot_data.py tests/test_merge_nonebot_data.py
git commit -m "feat(scripts): implement merge CLI with backup and dry-run"
```

---

### Task 5: 对真实 nonebot 数据跑 dry-run 验证

**Files:**
- 仅读，不改

- [ ] **Step 1: 跑 dry-run**

```bash
cd "E:/Github/astrbot_plugin_monixiuxian2-main"
python -m scripts.merge_nonebot_data \
    --source "E:/Github/nonebot_plugin_xiuxian_2_pmv_lunar-master/data/xiuxian" \
    --target "E:/Github/astrbot_plugin_monixiuxian2-main/config" \
    --dry-run
```

Expected: 输出 4 行合并统计，每行 `新增 X / 跳过同名 Y`，数字 > 0；末尾打印 `DRY-RUN: 未写入任何文件`。如果 ERROR，根据错误信息修正代码。

- [ ] **Step 2: 验证目标文件未被修改**

```bash
git status config/
```

Expected: `nothing to commit, working tree clean`（或仅有 docs 等无关变更）。

- [ ] **Step 3: 无需 commit**（仅验证）

---

### Task 6: 正式执行合并

**Files:**
- Modify: `config/weapons.json`、`config/items.json`、`config/utility_pills.json`
- Generated: `config/.backup/<timestamp>/*.json`

- [ ] **Step 1: 跑正式合并**

```bash
cd "E:/Github/astrbot_plugin_monixiuxian2-main"
python -m scripts.merge_nonebot_data \
    --source "E:/Github/nonebot_plugin_xiuxian_2_pmv_lunar-master/data/xiuxian" \
    --target "E:/Github/astrbot_plugin_monixiuxian2-main/config"
```

Expected: 同 Task 5 的统计，末尾 `写入完成`。

- [ ] **Step 2: 验证文件结构合法**

```bash
python -c "import json; [json.load(open(f, encoding='utf-8')) for f in ['config/weapons.json','config/items.json','config/utility_pills.json']]; print('OK')"
```

Expected: `OK`。

- [ ] **Step 3: Commit**

```bash
git add config/weapons.json config/items.json config/utility_pills.json config/.backup/
git commit -m "data: merge nonebot equipment/technique/pill data"
```

---

### Task 7: 验证插件能加载新数据

**Files:**
- 仅运行验证

- [ ] **Step 1: 在 Python 里加载 ConfigManager 检验**

```bash
python -c "
import sys
sys.path.insert(0, 'E:/Github')
from pathlib import Path
from astrbot_plugin_monixiuxian2_main.config_manager import ConfigManager
cm = ConfigManager(Path('E:/Github/astrbot_plugin_monixiuxian2-main'))
print('weapons:', len(cm.weapons_data))
print('items:', len(cm.items_data))
print('utility_pills:', len(cm.utility_pills_data))
"
```

> **如果该 import 路径不可用**（因目录有连字符），换用：

```bash
cd "E:/Github/astrbot_plugin_monixiuxian2-main"
python -c "
import sys; sys.path.insert(0, '.')
from pathlib import Path
import importlib.util
spec = importlib.util.spec_from_file_location('cm', 'config_manager.py')
# 因为 config_manager.py 是相对导入，无法直接 spec 加载；改用 json 直接验证
import json
print('weapons:', len(json.load(open('config/weapons.json', encoding='utf-8'))))
print('items:', len(json.load(open('config/items.json', encoding='utf-8'))))
print('utility_pills:', len(json.load(open('config/utility_pills.json', encoding='utf-8'))))
"
```

Expected: 三个数字都大于合并前的基础数（weapons > 80, items > 67, utility_pills > 50 左右）。

- [ ] **Step 2: 无需 commit**

---

## Phase B：经济量级缩放

### Task 8: 价格缩放函数（TDD）

**Files:**
- Create: `tests/test_rebalance_economy.py`
- Create: `scripts/rebalance_economy.py`

- [ ] **Step 1: 写失败测试**

`tests/test_rebalance_economy.py`:

```python
from scripts.rebalance_economy import (
    scale_equipment_price,
    scale_price_by_band,
    scale_adventure_route,
    scale_bounty_template,
    scale_game_config_bank,
)


def test_scale_equipment_price_fanpin():
    """凡品装备 300 → 300*3000=900000，舍入到万 → 900000"""
    assert scale_equipment_price(300, "凡品") == 900_000


def test_scale_equipment_price_xianpin():
    """仙品装备 1_000_000 × 20 = 20_000_000"""
    assert scale_equipment_price(1_000_000, "仙品") == 20_000_000


def test_scale_equipment_price_unknown_rank_uses_fanpin():
    """未知品级回退到凡品倍率"""
    assert scale_equipment_price(100, "不存在的品级") == 300_000


def test_scale_price_by_band_low():
    assert scale_price_by_band(50) == 50 * 3000  # 150,000 → 舍入到万 = 150,000


def test_scale_price_by_band_mid():
    """price=5000 在 1k-10k 段，倍率 500 → 2_500_000"""
    assert scale_price_by_band(5000) == 2_500_000


def test_scale_price_by_band_huge_caps_at_10x():
    """price=10亿（10**9）→ 倍率 10 → 100亿"""
    assert scale_price_by_band(1_000_000_000) == 10_000_000_000


def test_scale_adventure_route_multiplies_gold_fields():
    route = {
        "key": "scout",
        "base_gold_per_min": 10,
        "level_bonus_gold": 3,
        "base_exp_per_min": 45,  # 不能改
        "completion_bonus": {"gold": 120, "exp": 300},
    }
    out = scale_adventure_route(route, multiplier=3000)
    assert out["base_gold_per_min"] == 30000
    assert out["level_bonus_gold"] == 9000
    assert out["completion_bonus"]["gold"] == 360_000
    # 经验不动
    assert out["base_exp_per_min"] == 45
    assert out["completion_bonus"]["exp"] == 300


def test_scale_bounty_template_multiplies_stone():
    t = {"reward": {"stone": 260, "exp": 2200}}
    out = scale_bounty_template(t, multiplier=3000)
    assert out["reward"]["stone"] == 780_000
    assert out["reward"]["exp"] == 2200  # exp 不动


def test_scale_game_config_bank_multiplies_amounts():
    bank = {
        "daily_interest_rate": 0.001,  # 不动
        "max_deposit": 10_000_000,
        "max_loan_amount": 1_000_000,
        "min_loan_amount": 1_000,
        "loan_interest_rate": 0.005,  # 不动
    }
    out = scale_game_config_bank(bank, multiplier=100)
    assert out["max_deposit"] == 1_000_000_000
    assert out["max_loan_amount"] == 100_000_000
    assert out["min_loan_amount"] == 100_000
    assert out["daily_interest_rate"] == 0.001
    assert out["loan_interest_rate"] == 0.005
```

- [ ] **Step 2: 跑测试确认失败**

```bash
python -m pytest tests/test_rebalance_economy.py -v
```

Expected: import error，全部 FAIL。

- [ ] **Step 3: 实现 scripts/rebalance_economy.py 骨架**

```python
"""按品级倍率缩放经济数值。

用法:
    python -m scripts.rebalance_economy --target <config_dir> --dry-run
    python -m scripts.rebalance_economy --target <config_dir>
"""
from __future__ import annotations
import argparse
import logging
from pathlib import Path
from typing import Any

from ._common import (
    RANK_PRICE_MULTIPLIER,
    PRICE_BAND_MULTIPLIER,
    price_band_mult,
    round_to_万,
    backup_files,
    load_json,
    dump_json,
)

logger = logging.getLogger(__name__)


# 冒险路线倍率（按 key）
ADVENTURE_ROUTE_MULTIPLIER = {
    "scout":   3000,
    "journey": 1500,
    "hunt":    500,
    "peril":   100,
}

# 悬赏难度倍率
BOUNTY_DIFFICULTY_MULTIPLIER = {
    "easy":   3000,
    "normal": 1000,
    "hard":   500,
    "elite":  100,
}


# ============== 价格缩放 ==============

def scale_equipment_price(price: int, rank: str) -> int:
    mult = RANK_PRICE_MULTIPLIER.get(rank, RANK_PRICE_MULTIPLIER["凡品"])
    return round_to_万(price * mult)


def scale_price_by_band(price: int) -> int:
    mult = price_band_mult(price)
    return round_to_万(price * mult)


# ============== 产出缩放 ==============

def scale_adventure_route(route: dict, multiplier: int) -> dict:
    """只放大 gold 字段，exp 字段保持不变。"""
    if "base_gold_per_min" in route:
        route["base_gold_per_min"] = int(route["base_gold_per_min"]) * multiplier
    if "level_bonus_gold" in route:
        route["level_bonus_gold"] = int(route["level_bonus_gold"]) * multiplier
    cb = route.get("completion_bonus") or {}
    if "gold" in cb:
        cb["gold"] = int(cb["gold"]) * multiplier
    return route


def scale_bounty_template(t: dict, multiplier: int) -> dict:
    reward = t.get("reward") or {}
    if "stone" in reward:
        reward["stone"] = int(reward["stone"]) * multiplier
    return t


def scale_game_config_bank(bank: dict, multiplier: int) -> dict:
    for k in ("max_deposit", "max_loan_amount", "min_loan_amount"):
        if k in bank:
            bank[k] = int(bank[k]) * multiplier
    # 突破贷款上限（如果有）
    if "breakthrough_loan_max" in bank:
        bank["breakthrough_loan_max"] = int(bank["breakthrough_loan_max"]) * multiplier
    return bank


# ============== CLI（Task 9 实现） ==============

def main(argv: list[str] | None = None) -> int:
    raise NotImplementedError("Task 9 实现")


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 跑测试确认通过**

```bash
python -m pytest tests/test_rebalance_economy.py -v
```

Expected: 9 个测试全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add scripts/rebalance_economy.py tests/test_rebalance_economy.py
git commit -m "feat(scripts): add economy scaling helper functions"
```

---

### Task 9: 缩放 CLI 实现

**Files:**
- Modify: `scripts/rebalance_economy.py`（实现 `main`）
- Modify: `tests/test_rebalance_economy.py`

- [ ] **Step 1: 追加失败测试**

```python
import subprocess
import sys
from pathlib import Path
from tests.conftest import write_json, read_json


def test_rebalance_main_dry_run(tmp_path):
    target = tmp_path / "config"
    target.mkdir()
    write_json(target / "weapons.json", [
        {"id": "sword_001", "name": "青铜剑", "rank": "凡品", "price": 199},
    ])
    write_json(target / "items.json", {})
    write_json(target / "pills.json", [])
    write_json(target / "exp_pills.json", [])
    write_json(target / "utility_pills.json", [])
    write_json(target / "storage_rings.json", {})
    write_json(target / "adventure_config.json", {"routes": []})
    write_json(target / "bounty_templates.json", {"difficulties": {}, "templates": []})
    write_json(target / "game_config.json", {"bank": {"max_deposit": 10000000}})

    result = subprocess.run(
        [sys.executable, "-m", "scripts.rebalance_economy",
         "--target", str(target), "--dry-run"],
        cwd=str(Path(__file__).resolve().parent.parent),
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    # 文件保持原样
    weapons = read_json(target / "weapons.json")
    assert weapons[0]["price"] == 199


def test_rebalance_main_real_run(tmp_path):
    target = tmp_path / "config"
    target.mkdir()
    write_json(target / "weapons.json", [
        {"id": "sword_001", "name": "青铜剑", "rank": "凡品", "price": 199, "type": "weapon"},
    ])
    write_json(target / "items.json", {})
    write_json(target / "pills.json", [])
    write_json(target / "exp_pills.json", [])
    write_json(target / "utility_pills.json", [])
    write_json(target / "storage_rings.json", {})
    write_json(target / "adventure_config.json", {
        "routes": [{"key": "scout", "base_gold_per_min": 10, "level_bonus_gold": 3,
                    "base_exp_per_min": 45, "completion_bonus": {"gold": 120, "exp": 300}}]
    })
    write_json(target / "bounty_templates.json",
               {"difficulties": {}, "templates": [
                   {"difficulty": "easy", "reward": {"stone": 260, "exp": 2200}}
               ]})
    write_json(target / "game_config.json", {"bank": {"max_deposit": 10000000, "max_loan_amount": 1000000, "min_loan_amount": 1000}})

    result = subprocess.run(
        [sys.executable, "-m", "scripts.rebalance_economy", "--target", str(target)],
        cwd=str(Path(__file__).resolve().parent.parent),
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    weapons = read_json(target / "weapons.json")
    assert weapons[0]["price"] == 600_000  # 199 * 3000 = 597000，舍入到万=600000
    adv = read_json(target / "adventure_config.json")
    assert adv["routes"][0]["base_gold_per_min"] == 30000
    bk = read_json(target / "game_config.json")["bank"]
    assert bk["max_deposit"] == 1_000_000_000
```

- [ ] **Step 2: 跑测试确认失败**

```bash
python -m pytest tests/test_rebalance_economy.py::test_rebalance_main_dry_run -v
```

Expected: FAIL（NotImplementedError）

- [ ] **Step 3: 实现 main()**

替换 `scripts/rebalance_economy.py` 末尾的 `main()`：

```python
def _scale_item_list_or_dict(data, rank_aware: bool) -> int:
    """处理 weapons.json/items.json/pills.json 等：
    rank_aware=True 时按 rank 字段查 RANK_PRICE_MULTIPLIER，否则按价格段。
    """
    changed = 0
    iterable = data.values() if isinstance(data, dict) else data
    for entry in iterable:
        if not isinstance(entry, dict) or "price" not in entry:
            continue
        old = int(entry.get("price", 0) or 0)
        if old <= 0:
            continue
        if rank_aware and "rank" in entry:
            new = scale_equipment_price(old, entry["rank"])
        else:
            new = scale_price_by_band(old)
        if new != old:
            entry["price"] = new
            changed += 1
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="经济量级缩放")
    parser.add_argument("--target", required=True, help="astrbot config 目录")
    parser.add_argument("--dry-run", action="store_true", help="不写文件，仅打印")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    tgt = Path(args.target)
    if not tgt.exists():
        print(f"ERROR: target dir not found: {tgt}")
        return 2

    prefix = "DRY-RUN: " if args.dry_run else ""

    files = [tgt / n for n in (
        "weapons.json", "items.json", "pills.json", "exp_pills.json",
        "utility_pills.json", "storage_rings.json",
        "adventure_config.json", "bounty_templates.json", "game_config.json",
    )]
    if not args.dry_run:
        backup_dest = backup_files(files, backup_root=tgt / ".backup")
        print(f"已备份到 {backup_dest}")

    # 加载
    loaded = {}
    for f in files:
        if f.exists():
            loaded[f.name] = load_json(f)

    # 1) 装备/功法（按 rank）：weapons.json、items.json
    if "weapons.json" in loaded:
        c = _scale_item_list_or_dict(loaded["weapons.json"], rank_aware=True)
        print(f"{prefix}weapons.json 调价: {c} 条")
    if "items.json" in loaded:
        c = _scale_item_list_or_dict(loaded["items.json"], rank_aware=True)
        print(f"{prefix}items.json 调价: {c} 条")

    # 2) 丹药（按价格段）：pills/exp_pills/utility_pills/storage_rings
    for n in ("pills.json", "exp_pills.json", "utility_pills.json", "storage_rings.json"):
        if n in loaded:
            c = _scale_item_list_or_dict(loaded[n], rank_aware=False)
            print(f"{prefix}{n} 调价: {c} 条")

    # 3) 冒险产出
    if "adventure_config.json" in loaded:
        for route in loaded["adventure_config.json"].get("routes", []):
            key = route.get("key", "scout")
            mult = ADVENTURE_ROUTE_MULTIPLIER.get(key, 1000)
            scale_adventure_route(route, mult)
        print(f"{prefix}adventure_config 已缩放")

    # 4) 悬赏奖励
    if "bounty_templates.json" in loaded:
        for t in loaded["bounty_templates.json"].get("templates", []):
            d = t.get("difficulty", "easy")
            mult = BOUNTY_DIFFICULTY_MULTIPLIER.get(d, 1000)
            scale_bounty_template(t, mult)
        print(f"{prefix}bounty_templates 已缩放")

    # 5) 银行限额
    if "game_config.json" in loaded:
        bank = loaded["game_config.json"].get("bank")
        if isinstance(bank, dict):
            scale_game_config_bank(bank, multiplier=100)
        print(f"{prefix}game_config.bank 已缩放")

    if args.dry_run:
        print("DRY-RUN: 未写入任何文件")
        return 0
    for f in files:
        if f.name in loaded:
            dump_json(f, loaded[f.name])
    print("写入完成")
    return 0
```

- [ ] **Step 4: 跑测试确认通过**

```bash
python -m pytest tests/test_rebalance_economy.py -v
```

Expected: 11 个测试全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add scripts/rebalance_economy.py tests/test_rebalance_economy.py
git commit -m "feat(scripts): implement rebalance CLI"
```

---

### Task 10: 对真实 config 跑 dry-run 验证

- [ ] **Step 1: 跑 dry-run**

```bash
cd "E:/Github/astrbot_plugin_monixiuxian2-main"
python -m scripts.rebalance_economy \
    --target "E:/Github/astrbot_plugin_monixiuxian2-main/config" \
    --dry-run
```

Expected: 输出 9 行 `XXX.json 调价: N 条` / 缩放说明，末尾 `DRY-RUN: 未写入任何文件`。

- [ ] **Step 2: 验证未被修改**

```bash
git diff --stat config/
```

Expected: 空输出。

- [ ] **Step 3: 无需 commit**

---

### Task 11: 正式执行缩放

- [ ] **Step 1: 跑正式**

```bash
python -m scripts.rebalance_economy --target "E:/Github/astrbot_plugin_monixiuxian2-main/config"
```

Expected: 同 Task 10 但末尾是 `写入完成`。

- [ ] **Step 2: 抽查几条**

```bash
python -c "
import json
w = json.load(open('config/weapons.json', encoding='utf-8'))
fan = [x for x in w if x.get('rank')=='凡品'][:3]
xian = [x for x in w if x.get('rank')=='仙品'][:3]
print('凡品样本:', [(x['name'], x['price']) for x in fan])
print('仙品样本:', [(x['name'], x['price']) for x in xian])
g = json.load(open('config/game_config.json', encoding='utf-8'))
print('bank:', g.get('bank'))
"
```

Expected: 凡品价格 > 100 万；仙品价格在千万到亿级；`max_deposit` = 10 亿。

- [ ] **Step 3: Commit**

```bash
git add config/
git commit -m "data: rebalance economy to million/billion stone scale"
```

---

### Task 12: 启动插件验证配置可加载

- [ ] **Step 1: 验证 JSON 结构未损坏**

```bash
python -c "
import json
files = ['config/weapons.json','config/items.json','config/pills.json',
        'config/exp_pills.json','config/utility_pills.json','config/storage_rings.json',
        'config/adventure_config.json','config/bounty_templates.json','config/game_config.json']
for f in files:
    json.load(open(f, encoding='utf-8'))
print('all OK')
"
```

Expected: `all OK`。

- [ ] **Step 2: 无需 commit**

---

## Phase C：玩家交易系统

### Task 13: 模型扩展 + 数据库迁移 v21

**Files:**
- Modify: `models_extended.py`
- Modify: `data/migration.py`
- Test: `tests/test_migration_v21.py`

- [ ] **Step 1: 在 `models_extended.py` 的 `UserStatus` 中加 TRADING**

定位 `class UserStatus(IntEnum):`，在 `SECT_TASK = 4` 之后加：

```python
    TRADING = 5        # 交易中
```

同时在 `get_name` 的 `names` 字典中加入：

```python
            cls.TRADING: "交易中",
```

- [ ] **Step 2: 写迁移测试**

`tests/test_migration_v21.py`:

```python
import pytest
import aiosqlite
from astrbot_plugin_monixiuxian2.data.migration import MIGRATION_TASKS, LATEST_DB_VERSION


@pytest.mark.asyncio
async def test_latest_version_is_21():
    assert LATEST_DB_VERSION == 21
    assert 21 in MIGRATION_TASKS


@pytest.mark.asyncio
async def test_migration_v21_creates_tables(memory_db):
    # 模拟 v20 已存在
    await memory_db.execute("CREATE TABLE db_info (version INTEGER NOT NULL)")
    await memory_db.execute("INSERT INTO db_info VALUES (20)")
    await memory_db.commit()

    # 直接调用 v21 迁移函数
    await MIGRATION_TASKS[21](memory_db, config_manager=None)
    await memory_db.commit()

    async with memory_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('trades','consignment_listings')"
    ) as cur:
        rows = await cur.fetchall()
    table_names = {r[0] for r in rows}
    assert "trades" in table_names
    assert "consignment_listings" in table_names

    # 验证 trades 表的关键列
    async with memory_db.execute("PRAGMA table_info(trades)") as cur:
        cols = {r[1] for r in await cur.fetchall()}
    for c in ("trade_id", "player_a", "player_b", "player_a_items", "player_b_items",
              "player_a_stones", "player_b_stones", "a_confirmed", "b_confirmed",
              "status", "created_at", "expires_at"):
        assert c in cols, f"missing column: {c}"

    # 验证 consignment_listings
    async with memory_db.execute("PRAGMA table_info(consignment_listings)") as cur:
        cols = {r[1] for r in await cur.fetchall()}
    for c in ("listing_id", "seller_id", "item_id", "item_name", "item_type",
              "quantity", "price", "listed_at", "expires_at", "status",
              "buyer_id", "sold_at"):
        assert c in cols, f"missing column: {c}"
```

> 注意：该测试用 `from astrbot_plugin_monixiuxian2.data.migration import ...` 即通过 conftest.py 注册的包名导入。如果 import 失败，先验证 conftest.py 中的包注册逻辑（Task 1 已经处理）。

- [ ] **Step 3: 跑测试确认失败**

```bash
python -m pytest tests/test_migration_v21.py -v
```

Expected: AssertionError `LATEST_DB_VERSION == 21` 失败（当前是 20）。

- [ ] **Step 4: 在 `data/migration.py` 中修改 LATEST_DB_VERSION 并追加 v21**

把第 8 行改为：

```python
LATEST_DB_VERSION = 21  # v21: 玩家交易系统（trades + consignment_listings 表）
```

在文件末尾追加：

```python
@migration(21)
async def _migrate_to_v21(conn: aiosqlite.Connection, config_manager: ConfigManager):
    """迁移到v21 - 玩家交易系统（trades + consignment_listings 表）"""
    logger.info("开始迁移到v21：玩家交易系统")

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_a TEXT NOT NULL,
            player_b TEXT NOT NULL,
            player_a_items TEXT NOT NULL DEFAULT '[]',
            player_b_items TEXT NOT NULL DEFAULT '[]',
            player_a_stones INTEGER NOT NULL DEFAULT 0,
            player_b_stones INTEGER NOT NULL DEFAULT 0,
            a_confirmed INTEGER NOT NULL DEFAULT 0,
            b_confirmed INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'trading',
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_player_a ON trades(player_a, status)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_player_b ON trades(player_b, status)")

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS consignment_listings (
            listing_id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            item_name TEXT NOT NULL,
            item_type TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            price INTEGER NOT NULL,
            listed_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            buyer_id TEXT,
            sold_at INTEGER
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_consignment_status ON consignment_listings(status)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_consignment_seller ON consignment_listings(seller_id, status)")

    await conn.commit()
    logger.info("v21迁移完成：玩家交易系统")
```

- [ ] **Step 5: 在 `_create_all_tables_v2` 函数末尾（找到现有的位置）同步加表**

在 `_create_all_tables_v2` 函数里（约在 v17 后追加 pending_gifts 表的相同位置）找一处合适位置加入 trades 和 consignment_listings 的 CREATE TABLE 语句，与上面 v21 迁移中完全一致。这样新装的玩家不需要跑迁移就有这两张表。具体位置：在 `_create_all_tables_v2` 函数最后 `logger.info("数据库表已创建完成（v2）")` 之前插入相同的两段 `CREATE TABLE IF NOT EXISTS trades` 和 `consignment_listings` SQL。

- [ ] **Step 6: 跑测试确认通过**

```bash
python -m pytest tests/test_migration_v21.py -v
```

Expected: 2 个测试全部 PASS。

- [ ] **Step 7: Commit**

```bash
git add models_extended.py data/migration.py tests/test_migration_v21.py
git commit -m "feat(db): add v21 migration for trades and consignment_listings"
```

---

### Task 14: TradeManager 骨架 + 创建交易（TDD）

**Files:**
- Create: `managers/trade_manager.py`
- Create: `tests/test_trade_manager.py`

- [ ] **Step 1: 写失败测试**

`tests/test_trade_manager.py`:

```python
import pytest
import time
import json
from astrbot_plugin_monixiuxian2.managers.trade_manager import TradeManager
from astrbot_plugin_monixiuxian2.data.migration import MIGRATION_TASKS


@pytest.fixture
async def db_with_trades(memory_db):
    """创建 v21 schema 的内存数据库"""
    await MIGRATION_TASKS[21](memory_db, config_manager=None)
    # 同时建 minimal players 表以便 manager 查询
    await memory_db.execute("""
        CREATE TABLE players (
            user_id TEXT PRIMARY KEY,
            user_name TEXT,
            gold INTEGER NOT NULL DEFAULT 0,
            pills_inventory TEXT NOT NULL DEFAULT '{}',
            storage_ring_items TEXT NOT NULL DEFAULT '{}'
        )
    """)
    yield memory_db


async def insert_player(conn, uid, gold=100000, items=None, pills=None):
    items = items or {}
    pills = pills or {}
    await conn.execute(
        "INSERT INTO players (user_id, user_name, gold, pills_inventory, storage_ring_items) "
        "VALUES (?, ?, ?, ?, ?)",
        (uid, f"道友{uid}", gold, json.dumps(pills), json.dumps(items)),
    )
    await conn.commit()


@pytest.mark.asyncio
async def test_create_trade_starts_in_trading_state(db_with_trades):
    await insert_player(db_with_trades, "A")
    await insert_player(db_with_trades, "B")

    tm = TradeManager(db_with_trades)
    trade_id = await tm.create_trade("A", "B", duration_seconds=1800)
    assert trade_id is not None

    async with db_with_trades.execute(
        "SELECT player_a, player_b, status, a_confirmed, b_confirmed FROM trades WHERE trade_id=?",
        (trade_id,)
    ) as cur:
        row = await cur.fetchone()
    assert row["player_a"] == "A"
    assert row["player_b"] == "B"
    assert row["status"] == "trading"
    assert row["a_confirmed"] == 0
    assert row["b_confirmed"] == 0


@pytest.mark.asyncio
async def test_create_trade_fails_when_already_trading(db_with_trades):
    await insert_player(db_with_trades, "A")
    await insert_player(db_with_trades, "B")
    await insert_player(db_with_trades, "C")

    tm = TradeManager(db_with_trades)
    await tm.create_trade("A", "B", duration_seconds=1800)

    with pytest.raises(ValueError, match="已在交易"):
        await tm.create_trade("A", "C", duration_seconds=1800)


@pytest.mark.asyncio
async def test_get_active_trade_for_player(db_with_trades):
    await insert_player(db_with_trades, "A")
    await insert_player(db_with_trades, "B")
    tm = TradeManager(db_with_trades)
    tid = await tm.create_trade("A", "B", duration_seconds=1800)

    found = await tm.get_active_trade("A")
    assert found is not None
    assert found["trade_id"] == tid

    found_b = await tm.get_active_trade("B")
    assert found_b["trade_id"] == tid
```

- [ ] **Step 2: 跑测试确认失败**

```bash
python -m pytest tests/test_trade_manager.py -v
```

Expected: ImportError on `TradeManager`。

- [ ] **Step 3: 实现 `managers/trade_manager.py`**

```python
"""即时交易（面对面）管理器。

职责：
- 创建/获取/取消/确认交易
- 物品/灵石的托管与返还
- 双方都确认后的原子结算

数据模型: trades 表（v21 schema）。
"""
from __future__ import annotations
import time
import json
from typing import Any, Optional


__all__ = ["TradeManager"]


class TradeManager:
    """即时交易业务逻辑。直接接受 aiosqlite.Connection 以便测试。"""

    def __init__(self, conn):
        self.conn = conn

    async def create_trade(self, player_a: str, player_b: str,
                            duration_seconds: int = 1800) -> int:
        """发起一笔交易。任一方已在交易中则抛出 ValueError。"""
        if player_a == player_b:
            raise ValueError("不能与自己交易")
        # 检查双方都不在 trading 状态
        async with self.conn.execute(
            "SELECT trade_id FROM trades WHERE status='trading' AND "
            "(player_a=? OR player_b=? OR player_a=? OR player_b=?)",
            (player_a, player_a, player_b, player_b),
        ) as cur:
            row = await cur.fetchone()
        if row:
            raise ValueError("已在交易中，请先结束当前交易")

        now = int(time.time())
        expires = now + duration_seconds
        cur = await self.conn.execute(
            "INSERT INTO trades (player_a, player_b, created_at, expires_at) "
            "VALUES (?, ?, ?, ?)",
            (player_a, player_b, now, expires),
        )
        await self.conn.commit()
        return cur.lastrowid

    async def get_active_trade(self, user_id: str) -> Optional[dict]:
        """返回该玩家正在进行的交易（无则 None）。"""
        async with self.conn.execute(
            "SELECT * FROM trades WHERE status='trading' AND (player_a=? OR player_b=?)",
            (user_id, user_id),
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None
```

- [ ] **Step 4: 跑测试确认通过**

```bash
python -m pytest tests/test_trade_manager.py -v
```

Expected: 3 个测试全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add managers/trade_manager.py tests/test_trade_manager.py
git commit -m "feat(trade): TradeManager scaffolding with create/get_active"
```

---

### Task 15: 交易物品/灵石托管（add/remove）

> **背包说明**：本插件的物品分两处存储——丹药在 `players.pills_inventory`（dict），其他物品在 `players.storage_ring_items`（dict）。本任务实现一个统一的物品查找/扣除/返还逻辑，**优先从 storage_ring_items 找，找不到再从 pills_inventory 找**；返还时回到原始来源。为了简化设计，在交易托管表 `trades.player_X_items` 的每条目里记录 `source` 字段（"ring" 或 "pill"）。

**Files:**
- Modify: `managers/trade_manager.py`
- Modify: `tests/test_trade_manager.py`

- [ ] **Step 1: 追加失败测试**

```python
@pytest.mark.asyncio
async def test_add_stones_deducts_from_player(db_with_trades):
    await insert_player(db_with_trades, "A", gold=10000)
    await insert_player(db_with_trades, "B")
    tm = TradeManager(db_with_trades)
    tid = await tm.create_trade("A", "B")
    await tm.add_stones(tid, "A", 3000)

    async with db_with_trades.execute("SELECT gold FROM players WHERE user_id='A'") as cur:
        a_gold = (await cur.fetchone())[0]
    assert a_gold == 7000
    async with db_with_trades.execute("SELECT player_a_stones FROM trades WHERE trade_id=?", (tid,)) as cur:
        escrow = (await cur.fetchone())[0]
    assert escrow == 3000


@pytest.mark.asyncio
async def test_add_stones_insufficient_raises(db_with_trades):
    await insert_player(db_with_trades, "A", gold=100)
    await insert_player(db_with_trades, "B")
    tm = TradeManager(db_with_trades)
    tid = await tm.create_trade("A", "B")
    with pytest.raises(ValueError, match="灵石不足"):
        await tm.add_stones(tid, "A", 3000)


@pytest.mark.asyncio
async def test_add_and_remove_item_round_trip(db_with_trades):
    await insert_player(db_with_trades, "A", items={"灵草": 5})
    await insert_player(db_with_trades, "B")
    tm = TradeManager(db_with_trades)
    tid = await tm.create_trade("A", "B")

    await tm.add_item(tid, "A", "灵草", 2)
    # 玩家剩 3，托管 2
    async with db_with_trades.execute(
        "SELECT storage_ring_items FROM players WHERE user_id='A'"
    ) as cur:
        inv = json.loads((await cur.fetchone())[0])
    assert inv == {"灵草": 3}

    await tm.remove_item(tid, "A", "灵草", 2)
    async with db_with_trades.execute(
        "SELECT storage_ring_items FROM players WHERE user_id='A'"
    ) as cur:
        inv = json.loads((await cur.fetchone())[0])
    assert inv == {"灵草": 5}


@pytest.mark.asyncio
async def test_add_pill_from_pills_inventory(db_with_trades):
    """丹药从 pills_inventory 取出，返还时回到 pills_inventory"""
    await insert_player(db_with_trades, "A", pills={"筑基丹": 3})
    await insert_player(db_with_trades, "B")
    tm = TradeManager(db_with_trades)
    tid = await tm.create_trade("A", "B")

    await tm.add_item(tid, "A", "筑基丹", 1)
    async with db_with_trades.execute(
        "SELECT pills_inventory FROM players WHERE user_id='A'"
    ) as cur:
        pills = json.loads((await cur.fetchone())[0])
    assert pills == {"筑基丹": 2}

    await tm.remove_item(tid, "A", "筑基丹")
    async with db_with_trades.execute(
        "SELECT pills_inventory FROM players WHERE user_id='A'"
    ) as cur:
        pills = json.loads((await cur.fetchone())[0])
    assert pills == {"筑基丹": 3}
```

- [ ] **Step 2: 跑测试确认失败**

```bash
python -m pytest tests/test_trade_manager.py -v
```

Expected: 3 个新测试 FAIL（method not found）。

- [ ] **Step 3: 实现 add_stones / add_item / remove_item / remove_stones**

在 `TradeManager` 类末尾追加：

```python
    # ---------- 内部辅助 ----------

    async def _get_trade_or_raise(self, trade_id: int, user_id: str) -> dict:
        async with self.conn.execute(
            "SELECT * FROM trades WHERE trade_id=? AND status='trading'", (trade_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            raise ValueError("交易不存在或已结束")
        if user_id not in (row["player_a"], row["player_b"]):
            raise ValueError("非交易参与者")
        return dict(row)

    def _which_side(self, trade: dict, user_id: str) -> str:
        return "a" if trade["player_a"] == user_id else "b"

    async def _set_confirmation_dirty(self, trade_id: int) -> None:
        """任何添加/移除操作都会清空双方确认（强制重新确认）"""
        await self.conn.execute(
            "UPDATE trades SET a_confirmed=0, b_confirmed=0 WHERE trade_id=?",
            (trade_id,),
        )

    # ---------- 灵石托管 ----------

    async def add_stones(self, trade_id: int, user_id: str, amount: int) -> None:
        if amount <= 0:
            raise ValueError("数量必须为正整数")
        await self.conn.execute("BEGIN IMMEDIATE")
        try:
            trade = await self._get_trade_or_raise(trade_id, user_id)
            side = self._which_side(trade, user_id)
            async with self.conn.execute(
                "SELECT gold FROM players WHERE user_id=?", (user_id,)
            ) as cur:
                row = await cur.fetchone()
            if not row or row[0] < amount:
                raise ValueError("灵石不足")
            await self.conn.execute(
                "UPDATE players SET gold = gold - ? WHERE user_id=?",
                (amount, user_id),
            )
            await self.conn.execute(
                f"UPDATE trades SET player_{side}_stones = player_{side}_stones + ? "
                "WHERE trade_id=?",
                (amount, trade_id),
            )
            await self._set_confirmation_dirty(trade_id)
            await self.conn.commit()
        except Exception:
            await self.conn.rollback()
            raise

    async def remove_stones(self, trade_id: int, user_id: str, amount: int) -> None:
        if amount <= 0:
            raise ValueError("数量必须为正整数")
        await self.conn.execute("BEGIN IMMEDIATE")
        try:
            trade = await self._get_trade_or_raise(trade_id, user_id)
            side = self._which_side(trade, user_id)
            current = trade[f"player_{side}_stones"]
            if current < amount:
                raise ValueError("托管灵石不足")
            await self.conn.execute(
                f"UPDATE trades SET player_{side}_stones = player_{side}_stones - ? "
                "WHERE trade_id=?",
                (amount, trade_id),
            )
            await self.conn.execute(
                "UPDATE players SET gold = gold + ? WHERE user_id=?",
                (amount, user_id),
            )
            await self._set_confirmation_dirty(trade_id)
            await self.conn.commit()
        except Exception:
            await self.conn.rollback()
            raise

    # ---------- 物品托管 ----------

    async def _find_item_source(self, user_id: str, item_name: str) -> tuple[str, dict] | tuple[None, None]:
        """返回 (source, current_inventory_dict)；source ∈ {'ring', 'pill'}"""
        async with self.conn.execute(
            "SELECT storage_ring_items, pills_inventory FROM players WHERE user_id=?",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None, None
        ring = json.loads(row[0] or "{}")
        if item_name in ring:
            return "ring", ring
        pills = json.loads(row[1] or "{}")
        if item_name in pills:
            return "pill", pills
        return None, None

    async def _save_inventory(self, user_id: str, source: str, inv: dict) -> None:
        col = "storage_ring_items" if source == "ring" else "pills_inventory"
        await self.conn.execute(
            f"UPDATE players SET {col}=? WHERE user_id=?",
            (json.dumps(inv, ensure_ascii=False), user_id),
        )

    async def add_item(self, trade_id: int, user_id: str, item_name: str, count: int = 1) -> None:
        if count <= 0:
            raise ValueError("数量必须为正整数")
        await self.conn.execute("BEGIN IMMEDIATE")
        try:
            trade = await self._get_trade_or_raise(trade_id, user_id)
            side = self._which_side(trade, user_id)

            source, inv = await self._find_item_source(user_id, item_name)
            if source is None:
                raise ValueError(f"背包中没有【{item_name}】")
            if inv.get(item_name, 0) < count:
                raise ValueError(f"【{item_name}】数量不足")
            inv[item_name] -= count
            if inv[item_name] == 0:
                del inv[item_name]
            await self._save_inventory(user_id, source, inv)

            items_col = f"player_{side}_items"
            escrow = json.loads(trade[items_col] or "[]")
            # 查找已存在条目合并
            for e in escrow:
                if e["name"] == item_name:
                    e["count"] += count
                    break
            else:
                escrow.append({"name": item_name, "count": count, "source": source})
            await self.conn.execute(
                f"UPDATE trades SET {items_col}=? WHERE trade_id=?",
                (json.dumps(escrow, ensure_ascii=False), trade_id),
            )
            await self._set_confirmation_dirty(trade_id)
            await self.conn.commit()
        except Exception:
            await self.conn.rollback()
            raise

    async def remove_item(self, trade_id: int, user_id: str, item_name: str, count: Optional[int] = None) -> None:
        """count 为 None 时移除全部"""
        await self.conn.execute("BEGIN IMMEDIATE")
        try:
            trade = await self._get_trade_or_raise(trade_id, user_id)
            side = self._which_side(trade, user_id)
            items_col = f"player_{side}_items"

            escrow = json.loads(trade[items_col] or "[]")
            target = next((e for e in escrow if e["name"] == item_name), None)
            if not target:
                raise ValueError(f"交易中未放入【{item_name}】")
            remove_n = target["count"] if count is None else count
            if remove_n > target["count"]:
                raise ValueError("移除数量超过托管数量")
            target["count"] -= remove_n
            escrow = [e for e in escrow if e["count"] > 0]
            await self.conn.execute(
                f"UPDATE trades SET {items_col}=? WHERE trade_id=?",
                (json.dumps(escrow, ensure_ascii=False), trade_id),
            )

            # 返还到玩家原来的库存
            source = target.get("source", "ring")
            await self._return_to_inventory(user_id, item_name, remove_n, source)

            await self._set_confirmation_dirty(trade_id)
            await self.conn.commit()
        except Exception:
            await self.conn.rollback()
            raise

    async def _return_to_inventory(self, user_id: str, item_name: str, count: int, source: str) -> None:
        col = "storage_ring_items" if source == "ring" else "pills_inventory"
        async with self.conn.execute(
            f"SELECT {col} FROM players WHERE user_id=?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return
        inv = json.loads(row[0] or "{}")
        inv[item_name] = inv.get(item_name, 0) + count
        await self.conn.execute(
            f"UPDATE players SET {col}=? WHERE user_id=?",
            (json.dumps(inv, ensure_ascii=False), user_id),
        )
```

- [ ] **Step 4: 跑测试确认通过**

```bash
python -m pytest tests/test_trade_manager.py -v
```

Expected: 全部 6 个测试 PASS。

- [ ] **Step 5: Commit**

```bash
git add managers/trade_manager.py tests/test_trade_manager.py
git commit -m "feat(trade): item and stone escrow with auto-deconfirm on changes"
```

---

### Task 16: 交易确认 + 原子结算 + 取消

**Files:**
- Modify: `managers/trade_manager.py`
- Modify: `tests/test_trade_manager.py`

- [ ] **Step 1: 追加失败测试**

```python
@pytest.mark.asyncio
async def test_confirm_one_side_does_not_complete(db_with_trades):
    await insert_player(db_with_trades, "A", gold=10000)
    await insert_player(db_with_trades, "B")
    tm = TradeManager(db_with_trades)
    tid = await tm.create_trade("A", "B")
    await tm.add_stones(tid, "A", 1000)
    await tm.confirm(tid, "A")

    async with db_with_trades.execute("SELECT status, a_confirmed, b_confirmed FROM trades WHERE trade_id=?", (tid,)) as cur:
        row = await cur.fetchone()
    assert row["status"] == "trading"
    assert row["a_confirmed"] == 1
    assert row["b_confirmed"] == 0


@pytest.mark.asyncio
async def test_both_confirm_completes_and_transfers(db_with_trades):
    await insert_player(db_with_trades, "A", gold=10000, items={"灵草": 3})
    await insert_player(db_with_trades, "B", gold=5000, items={"丹炉": 1})
    tm = TradeManager(db_with_trades)
    tid = await tm.create_trade("A", "B")

    await tm.add_stones(tid, "A", 2000)
    await tm.add_item(tid, "A", "灵草", 2)
    await tm.add_item(tid, "B", "丹炉", 1)

    await tm.confirm(tid, "A")
    await tm.confirm(tid, "B")  # 第二个 confirm 触发结算

    # 交易完成
    async with db_with_trades.execute("SELECT status FROM trades WHERE trade_id=?", (tid,)) as cur:
        assert (await cur.fetchone())["status"] == "completed"
    # A 失去 2000 灵石和 2 灵草，获得 1 丹炉
    async with db_with_trades.execute("SELECT gold, storage_ring_items FROM players WHERE user_id='A'") as cur:
        row = await cur.fetchone()
    assert row["gold"] == 10000 - 2000  # 8000
    assert json.loads(row["storage_ring_items"]) == {"灵草": 1, "丹炉": 1}
    # B 获得 2000 灵石和 2 灵草，失去 1 丹炉
    async with db_with_trades.execute("SELECT gold, storage_ring_items FROM players WHERE user_id='B'") as cur:
        row = await cur.fetchone()
    assert row["gold"] == 5000 + 2000  # 7000
    assert json.loads(row["storage_ring_items"]) == {"灵草": 2}


@pytest.mark.asyncio
async def test_cancel_returns_escrow_to_owners(db_with_trades):
    await insert_player(db_with_trades, "A", gold=10000, items={"灵草": 3})
    await insert_player(db_with_trades, "B", gold=5000)
    tm = TradeManager(db_with_trades)
    tid = await tm.create_trade("A", "B")
    await tm.add_stones(tid, "A", 2000)
    await tm.add_item(tid, "A", "灵草", 2)

    await tm.cancel(tid, "A")

    async with db_with_trades.execute("SELECT status FROM trades WHERE trade_id=?", (tid,)) as cur:
        assert (await cur.fetchone())["status"] == "cancelled"
    async with db_with_trades.execute("SELECT gold, storage_ring_items FROM players WHERE user_id='A'") as cur:
        row = await cur.fetchone()
    assert row["gold"] == 10000
    assert json.loads(row["storage_ring_items"]) == {"灵草": 3}
```

- [ ] **Step 2: 跑测试确认失败**

```bash
python -m pytest tests/test_trade_manager.py -v
```

Expected: 3 个新测试 FAIL。

- [ ] **Step 3: 在 TradeManager 类末尾追加 confirm/cancel/expire**

```python
    # ---------- 确认与结算 ----------

    async def confirm(self, trade_id: int, user_id: str) -> bool:
        """玩家确认交易。返回 True 表示交易已最终结算。"""
        await self.conn.execute("BEGIN IMMEDIATE")
        try:
            trade = await self._get_trade_or_raise(trade_id, user_id)
            side = self._which_side(trade, user_id)
            col = f"{side}_confirmed"
            await self.conn.execute(
                f"UPDATE trades SET {col}=1 WHERE trade_id=?", (trade_id,)
            )
            # 重新查
            async with self.conn.execute(
                "SELECT * FROM trades WHERE trade_id=?", (trade_id,)
            ) as cur:
                trade = dict(await cur.fetchone())
            if trade["a_confirmed"] == 1 and trade["b_confirmed"] == 1:
                await self._settle(trade)
                await self.conn.commit()
                return True
            await self.conn.commit()
            return False
        except Exception:
            await self.conn.rollback()
            raise

    async def _settle(self, trade: dict) -> None:
        """在事务内执行结算：双向转移托管的物品和灵石。"""
        a, b = trade["player_a"], trade["player_b"]
        a_items = json.loads(trade["player_a_items"] or "[]")
        b_items = json.loads(trade["player_b_items"] or "[]")
        a_stones = trade["player_a_stones"]
        b_stones = trade["player_b_stones"]

        # 灵石：a 给 b，b 给 a
        await self.conn.execute(
            "UPDATE players SET gold = gold + ? WHERE user_id=?", (b_stones, a)
        )
        await self.conn.execute(
            "UPDATE players SET gold = gold + ? WHERE user_id=?", (a_stones, b)
        )

        # 物品：a 给 b，b 给 a
        await self._add_items_to_player(b, a_items)
        await self._add_items_to_player(a, b_items)

        await self.conn.execute(
            "UPDATE trades SET status='completed' WHERE trade_id=?",
            (trade["trade_id"],),
        )

    async def _add_items_to_player(self, user_id: str, items: list[dict]) -> None:
        """把交易托管的物品转入接收方背包。
        接收方的物品按 source 字段进入对应库存（ring/pill），缺省视为 ring。
        """
        if not items:
            return
        async with self.conn.execute(
            "SELECT storage_ring_items, pills_inventory FROM players WHERE user_id=?",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return
        ring = json.loads(row[0] or "{}")
        pills = json.loads(row[1] or "{}")
        for item in items:
            target = pills if item.get("source") == "pill" else ring
            target[item["name"]] = target.get(item["name"], 0) + item["count"]
        await self.conn.execute(
            "UPDATE players SET storage_ring_items=?, pills_inventory=? WHERE user_id=?",
            (json.dumps(ring, ensure_ascii=False), json.dumps(pills, ensure_ascii=False), user_id),
        )

    # ---------- 取消 / 过期 ----------

    async def cancel(self, trade_id: int, user_id: str) -> None:
        await self.conn.execute("BEGIN IMMEDIATE")
        try:
            trade = await self._get_trade_or_raise(trade_id, user_id)
            await self._refund_escrow(trade)
            await self.conn.execute(
                "UPDATE trades SET status='cancelled' WHERE trade_id=?",
                (trade_id,),
            )
            await self.conn.commit()
        except Exception:
            await self.conn.rollback()
            raise

    async def expire_overdue_trades(self) -> int:
        """供后台调用：把所有 expires_at < now 的 trading 交易自动取消。返回数量。"""
        now = int(time.time())
        async with self.conn.execute(
            "SELECT * FROM trades WHERE status='trading' AND expires_at < ?", (now,)
        ) as cur:
            rows = [dict(r) for r in await cur.fetchall()]
        for trade in rows:
            await self.conn.execute("BEGIN IMMEDIATE")
            try:
                await self._refund_escrow(trade)
                await self.conn.execute(
                    "UPDATE trades SET status='expired' WHERE trade_id=?",
                    (trade["trade_id"],),
                )
                await self.conn.commit()
            except Exception:
                await self.conn.rollback()
        return len(rows)

    async def _refund_escrow(self, trade: dict) -> None:
        a, b = trade["player_a"], trade["player_b"]
        await self.conn.execute(
            "UPDATE players SET gold = gold + ? WHERE user_id=?",
            (trade["player_a_stones"], a),
        )
        await self.conn.execute(
            "UPDATE players SET gold = gold + ? WHERE user_id=?",
            (trade["player_b_stones"], b),
        )
        await self._add_items_to_player(a, json.loads(trade["player_a_items"] or "[]"))
        await self._add_items_to_player(b, json.loads(trade["player_b_items"] or "[]"))
```

- [ ] **Step 4: 跑测试确认通过**

```bash
python -m pytest tests/test_trade_manager.py -v
```

Expected: 9 个测试全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add managers/trade_manager.py tests/test_trade_manager.py
git commit -m "feat(trade): confirm/cancel/expire with atomic settlement"
```

---

### Task 17: ConsignmentManager（TDD）

**Files:**
- Create: `managers/consignment_manager.py`
- Create: `tests/test_consignment_manager.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
import json
import time
from astrbot_plugin_monixiuxian2.managers.consignment_manager import ConsignmentManager
from astrbot_plugin_monixiuxian2.data.migration import MIGRATION_TASKS


@pytest.fixture
async def db_with_consignment(memory_db):
    await MIGRATION_TASKS[21](memory_db, config_manager=None)
    await memory_db.execute("""
        CREATE TABLE players (
            user_id TEXT PRIMARY KEY,
            user_name TEXT,
            gold INTEGER NOT NULL DEFAULT 0,
            storage_ring_items TEXT NOT NULL DEFAULT '{}',
            pills_inventory TEXT NOT NULL DEFAULT '{}'
        )
    """)
    yield memory_db


async def add_player(conn, uid, gold=10_000_000, items=None, pills=None):
    items = items or {}
    pills = pills or {}
    await conn.execute(
        "INSERT INTO players (user_id, user_name, gold, storage_ring_items, pills_inventory) "
        "VALUES (?,?,?,?,?)",
        (uid, f"道友{uid}", gold, json.dumps(items), json.dumps(pills)),
    )
    await conn.commit()


@pytest.mark.asyncio
async def test_list_item_charges_fee_and_escrows_item(db_with_consignment):
    await add_player(db_with_consignment, "S", gold=10_000_000, items={"灵草": 5})
    cm = ConsignmentManager(db_with_consignment)
    listing_id = await cm.list_item("S", item_name="灵草", item_id="item_001",
                                     item_type="material", price=1_000_000, quantity=2)
    assert listing_id is not None

    async with db_with_consignment.execute("SELECT gold, storage_ring_items FROM players WHERE user_id='S'") as cur:
        row = await cur.fetchone()
    # 手续费 = 1_000_000 * 5% = 50_000；总扣 50_000
    assert row["gold"] == 10_000_000 - 50_000
    assert json.loads(row["storage_ring_items"]) == {"灵草": 3}

    async with db_with_consignment.execute(
        "SELECT * FROM consignment_listings WHERE listing_id=?", (listing_id,)
    ) as cur:
        listing = dict(await cur.fetchone())
    assert listing["item_name"] == "灵草"
    assert listing["price"] == 1_000_000
    assert listing["quantity"] == 2
    assert listing["status"] == "active"


@pytest.mark.asyncio
async def test_list_item_fails_without_enough_fee(db_with_consignment):
    await add_player(db_with_consignment, "S", gold=10_000, items={"灵草": 5})
    cm = ConsignmentManager(db_with_consignment)
    with pytest.raises(ValueError, match="灵石不足"):
        await cm.list_item("S", "灵草", "i", "material", price=1_000_000)


@pytest.mark.asyncio
async def test_buy_listing_transfers(db_with_consignment):
    await add_player(db_with_consignment, "S", gold=10_000_000, items={"灵草": 5})
    await add_player(db_with_consignment, "B", gold=2_000_000)
    cm = ConsignmentManager(db_with_consignment)
    lid = await cm.list_item("S", "灵草", "i", "material", price=1_000_000, quantity=2)
    # S 扣手续费 50000 -> 9_950_000
    await cm.buy_listing(lid, buyer_id="B")

    async with db_with_consignment.execute("SELECT gold, storage_ring_items FROM players WHERE user_id='S'") as cur:
        s = await cur.fetchone()
    # S 收到 1_000_000 全额
    assert s["gold"] == 9_950_000 + 1_000_000
    async with db_with_consignment.execute("SELECT gold, storage_ring_items FROM players WHERE user_id='B'") as cur:
        b = await cur.fetchone()
    assert b["gold"] == 2_000_000 - 1_000_000
    assert json.loads(b["storage_ring_items"]) == {"灵草": 2}


@pytest.mark.asyncio
async def test_buy_twice_only_first_succeeds(db_with_consignment):
    await add_player(db_with_consignment, "S", gold=10_000_000, items={"灵草": 5})
    await add_player(db_with_consignment, "B1", gold=2_000_000)
    await add_player(db_with_consignment, "B2", gold=2_000_000)
    cm = ConsignmentManager(db_with_consignment)
    lid = await cm.list_item("S", "灵草", "i", "material", price=1_000_000, quantity=2)
    await cm.buy_listing(lid, buyer_id="B1")
    with pytest.raises(ValueError):
        await cm.buy_listing(lid, buyer_id="B2")


@pytest.mark.asyncio
async def test_cancel_listing_returns_item_keeps_fee(db_with_consignment):
    await add_player(db_with_consignment, "S", gold=10_000_000, items={"灵草": 5})
    cm = ConsignmentManager(db_with_consignment)
    lid = await cm.list_item("S", "灵草", "i", "material", price=1_000_000, quantity=2)
    await cm.cancel_listing(lid, user_id="S")

    async with db_with_consignment.execute("SELECT gold, storage_ring_items FROM players WHERE user_id='S'") as cur:
        row = await cur.fetchone()
    # 手续费不退
    assert row["gold"] == 10_000_000 - 50_000
    assert json.loads(row["storage_ring_items"]) == {"灵草": 5}


@pytest.mark.asyncio
async def test_expire_old_listings(db_with_consignment):
    await add_player(db_with_consignment, "S", gold=10_000_000, items={"灵草": 5})
    cm = ConsignmentManager(db_with_consignment)
    lid = await cm.list_item("S", "灵草", "i", "material", price=1_000_000, quantity=1,
                              duration_seconds=-1)  # 立即过期
    n = await cm.expire_old_listings()
    assert n >= 1
    async with db_with_consignment.execute("SELECT status FROM consignment_listings WHERE listing_id=?", (lid,)) as cur:
        assert (await cur.fetchone())["status"] == "expired"
    async with db_with_consignment.execute("SELECT storage_ring_items FROM players WHERE user_id='S'") as cur:
        inv = json.loads((await cur.fetchone())[0])
    # 物品退回
    assert inv.get("灵草") == 5
```

- [ ] **Step 2: 跑测试确认失败**

```bash
python -m pytest tests/test_consignment_manager.py -v
```

Expected: ImportError。

- [ ] **Step 3: 实现 `managers/consignment_manager.py`**

```python
"""寄售行业务逻辑。

5% 上架手续费，不退还。
7 天后自动过期，物品退回卖家。
"""
from __future__ import annotations
import time
import json
from typing import Optional


__all__ = ["ConsignmentManager"]

LISTING_FEE_RATE = 0.05
DEFAULT_DURATION = 7 * 24 * 3600


class ConsignmentManager:
    def __init__(self, conn):
        self.conn = conn

    async def list_item(self, seller_id: str, item_name: str, item_id: str,
                         item_type: str, price: int, quantity: int = 1,
                         duration_seconds: int = DEFAULT_DURATION) -> int:
        if price <= 0:
            raise ValueError("价格必须为正整数")
        if quantity <= 0:
            raise ValueError("数量必须为正整数")
        fee = int(price * LISTING_FEE_RATE)

        await self.conn.execute("BEGIN IMMEDIATE")
        try:
            async with self.conn.execute(
                "SELECT gold, storage_ring_items, pills_inventory FROM players WHERE user_id=?",
                (seller_id,)
            ) as cur:
                row = await cur.fetchone()
            if not row:
                raise ValueError("玩家不存在")
            if row[0] < fee:
                raise ValueError(f"灵石不足以支付手续费（需要 {fee:,} 灵石）")
            ring = json.loads(row[1] or "{}")
            pills = json.loads(row[2] or "{}")
            if ring.get(item_name, 0) >= quantity:
                ring[item_name] -= quantity
                if ring[item_name] == 0:
                    del ring[item_name]
                source = "ring"
            elif pills.get(item_name, 0) >= quantity:
                pills[item_name] -= quantity
                if pills[item_name] == 0:
                    del pills[item_name]
                source = "pill"
            else:
                raise ValueError(f"背包中【{item_name}】不足 {quantity} 个")

            # 扣手续费 + 写回背包
            await self.conn.execute(
                "UPDATE players SET gold = gold - ?, storage_ring_items=?, pills_inventory=? WHERE user_id=?",
                (fee, json.dumps(ring, ensure_ascii=False),
                 json.dumps(pills, ensure_ascii=False), seller_id),
            )

            now = int(time.time())
            # item_type 复用作 source 提示：以 'pill_' 前缀或额外列储存。为简化：
            # 把 source 编码进 item_type 字段（pill / 其他）
            effective_type = "pill" if source == "pill" else item_type
            cur = await self.conn.execute(
                "INSERT INTO consignment_listings "
                "(seller_id, item_id, item_name, item_type, quantity, price, "
                " listed_at, expires_at, status) VALUES (?,?,?,?,?,?,?,?, 'active')",
                (seller_id, item_id, item_name, effective_type, quantity, price,
                 now, now + duration_seconds),
            )
            await self.conn.commit()
            return cur.lastrowid
        except Exception:
            await self.conn.rollback()
            raise

    async def buy_listing(self, listing_id: int, buyer_id: str) -> dict:
        await self.conn.execute("BEGIN IMMEDIATE")
        try:
            async with self.conn.execute(
                "SELECT * FROM consignment_listings WHERE listing_id=? AND status='active'",
                (listing_id,),
            ) as cur:
                row = await cur.fetchone()
            if not row:
                raise ValueError("寄售物品不存在或已售出")
            listing = dict(row)
            if listing["seller_id"] == buyer_id:
                raise ValueError("不能购买自己的寄售物品")

            async with self.conn.execute(
                "SELECT gold, storage_ring_items, pills_inventory FROM players WHERE user_id=?",
                (buyer_id,)
            ) as cur:
                buyer = await cur.fetchone()
            if not buyer:
                raise ValueError("买家不存在")
            if buyer[0] < listing["price"]:
                raise ValueError("灵石不足")

            # 扣买家灵石，加卖家灵石
            await self.conn.execute(
                "UPDATE players SET gold = gold - ? WHERE user_id=?",
                (listing["price"], buyer_id),
            )
            await self.conn.execute(
                "UPDATE players SET gold = gold + ? WHERE user_id=?",
                (listing["price"], listing["seller_id"]),
            )
            # 物品进买家对应库存
            if listing["item_type"] == "pill":
                pills = json.loads(buyer[2] or "{}")
                pills[listing["item_name"]] = pills.get(listing["item_name"], 0) + listing["quantity"]
                await self.conn.execute(
                    "UPDATE players SET pills_inventory=? WHERE user_id=?",
                    (json.dumps(pills, ensure_ascii=False), buyer_id),
                )
            else:
                ring = json.loads(buyer[1] or "{}")
                ring[listing["item_name"]] = ring.get(listing["item_name"], 0) + listing["quantity"]
                await self.conn.execute(
                    "UPDATE players SET storage_ring_items=? WHERE user_id=?",
                    (json.dumps(ring, ensure_ascii=False), buyer_id),
                )
            await self.conn.execute(
                "UPDATE consignment_listings SET status='sold', buyer_id=?, sold_at=? "
                "WHERE listing_id=?",
                (buyer_id, int(time.time()), listing_id),
            )
            await self.conn.commit()
            return listing
        except Exception:
            await self.conn.rollback()
            raise

    async def cancel_listing(self, listing_id: int, user_id: str) -> None:
        await self.conn.execute("BEGIN IMMEDIATE")
        try:
            async with self.conn.execute(
                "SELECT * FROM consignment_listings WHERE listing_id=? AND status='active'",
                (listing_id,),
            ) as cur:
                row = await cur.fetchone()
            if not row:
                raise ValueError("寄售物品不存在或已售出")
            if row["seller_id"] != user_id:
                raise ValueError("不能下架他人的寄售物品")
            listing = dict(row)
            await self._return_item(listing)
            await self.conn.execute(
                "UPDATE consignment_listings SET status='cancelled' WHERE listing_id=?",
                (listing_id,),
            )
            await self.conn.commit()
        except Exception:
            await self.conn.rollback()
            raise

    async def expire_old_listings(self) -> int:
        now = int(time.time())
        async with self.conn.execute(
            "SELECT * FROM consignment_listings WHERE status='active' AND expires_at < ?", (now,)
        ) as cur:
            rows = [dict(r) for r in await cur.fetchall()]
        for listing in rows:
            await self.conn.execute("BEGIN IMMEDIATE")
            try:
                await self._return_item(listing)
                await self.conn.execute(
                    "UPDATE consignment_listings SET status='expired' WHERE listing_id=?",
                    (listing["listing_id"],),
                )
                await self.conn.commit()
            except Exception:
                await self.conn.rollback()
        return len(rows)

    async def _return_item(self, listing: dict) -> None:
        col = "pills_inventory" if listing["item_type"] == "pill" else "storage_ring_items"
        async with self.conn.execute(
            f"SELECT {col} FROM players WHERE user_id=?", (listing["seller_id"],)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return
        inv = json.loads(row[0] or "{}")
        inv[listing["item_name"]] = inv.get(listing["item_name"], 0) + listing["quantity"]
        await self.conn.execute(
            f"UPDATE players SET {col}=? WHERE user_id=?",
            (json.dumps(inv, ensure_ascii=False), listing["seller_id"]),
        )

    async def list_active(self, offset: int = 0, limit: int = 10) -> list[dict]:
        async with self.conn.execute(
            "SELECT * FROM consignment_listings WHERE status='active' "
            "ORDER BY listed_at DESC LIMIT ? OFFSET ?", (limit, offset)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def list_my(self, seller_id: str) -> list[dict]:
        async with self.conn.execute(
            "SELECT * FROM consignment_listings WHERE seller_id=? AND status='active'",
            (seller_id,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]
```

- [ ] **Step 4: 跑测试确认通过**

```bash
python -m pytest tests/test_consignment_manager.py -v
```

Expected: 6 个测试 PASS。

- [ ] **Step 5: Commit**

```bash
git add managers/consignment_manager.py tests/test_consignment_manager.py
git commit -m "feat(consignment): listing/buy/cancel/expire manager"
```

---

### Task 18: 导出 managers + 状态白名单更新

**Files:**
- Modify: `managers/__init__.py`
- Modify: `handlers/utils.py`

- [ ] **Step 1: 修改 `managers/__init__.py`**

在 `from .spirit_eye_manager import SpiritEyeManager` 之后追加：

```python
from .trade_manager import TradeManager
from .consignment_manager import ConsignmentManager
```

并在 `__all__` 列表的末尾（`"SpiritEyeManager"` 之后）追加：

```python
    "TradeManager",
    "ConsignmentManager",
```

- [ ] **Step 2: 修改 `handlers/utils.py` 的 BUSY_STATE_ALLOWED_COMMANDS**

在 `# 帮助信息` 之前追加：

```python
    # 寄售行（任何状态下都可浏览/管理寄售）
    "寄售行",
    "我的寄售",
    "购买寄售",
    "下架寄售",
```

- [ ] **Step 3: 验证 import 不报错**

```bash
cd "E:/Github/astrbot_plugin_monixiuxian2-main"
python -c "from managers import TradeManager, ConsignmentManager; print('OK')"
```

Expected: `OK`。

- [ ] **Step 4: Commit**

```bash
git add managers/__init__.py handlers/utils.py
git commit -m "feat: export Trade/Consignment managers and update busy state whitelist"
```

---

### Task 19: TradeHandler 实现

**Files:**
- Create: `handlers/trade_handler.py`
- Modify: `handlers/__init__.py`

- [ ] **Step 1: 创建 `handlers/trade_handler.py`**

```python
"""即时交易命令处理器。"""
from __future__ import annotations
from astrbot.api.event import AstrMessageEvent
from astrbot.api.message_components import At, Plain
from ..data import DataBase
from ..models import Player
from ..managers import TradeManager
from .utils import player_required


__all__ = ["TradeHandler"]


def _extract_at_target(event: AstrMessageEvent) -> str | None:
    msg = getattr(event.message_obj, "message", []) if hasattr(event, "message_obj") and event.message_obj else []
    for comp in msg:
        if isinstance(comp, At):
            for attr in ("qq", "target", "uin"):
                if hasattr(comp, attr):
                    return str(getattr(comp, attr))
    return None


class TradeHandler:
    def __init__(self, db: DataBase, trade_mgr: TradeManager):
        self.db = db
        self.mgr = trade_mgr

    @player_required
    async def handle_start_trade(self, player: Player, event: AstrMessageEvent, args: str = ""):
        target_id = _extract_at_target(event)
        if not target_id:
            yield event.plain_result("请使用 /交易 @某人 发起交易")
            return
        if target_id == player.user_id:
            yield event.plain_result("不能与自己交易")
            return
        target_player = await self.db.get_player_by_id(target_id)
        if not target_player:
            yield event.plain_result("对方还未踏入仙途")
            return
        try:
            tid = await self.mgr.create_trade(player.user_id, target_id)
        except ValueError as e:
            yield event.plain_result(f"交易发起失败：{e}")
            return
        yield event.plain_result(
            f"✅ 已向【{target_player.user_name or target_id}】发起交易（编号 {tid}）\n"
            f"使用 /添加物品 <名称> [数量] 或 /添加灵石 <数量> 放入物品\n"
            f"双方都输入 /确认交易 后完成"
        )

    @player_required
    async def handle_add_item(self, player: Player, event: AstrMessageEvent, args: str = ""):
        parts = args.strip().split()
        if not parts:
            yield event.plain_result("用法：/添加物品 <名称> [数量]")
            return
        name = parts[0]
        count = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
        trade = await self.mgr.get_active_trade(player.user_id)
        if not trade:
            yield event.plain_result("当前没有进行中的交易")
            return
        try:
            await self.mgr.add_item(trade["trade_id"], player.user_id, name, count)
        except ValueError as e:
            yield event.plain_result(f"添加失败：{e}")
            return
        yield event.plain_result(f"✅ 已放入【{name}】× {count}")

    @player_required
    async def handle_add_stones(self, player: Player, event: AstrMessageEvent, args: str = ""):
        if not args.strip().isdigit():
            yield event.plain_result("用法：/添加灵石 <数量>")
            return
        amount = int(args.strip())
        trade = await self.mgr.get_active_trade(player.user_id)
        if not trade:
            yield event.plain_result("当前没有进行中的交易")
            return
        try:
            await self.mgr.add_stones(trade["trade_id"], player.user_id, amount)
        except ValueError as e:
            yield event.plain_result(f"添加失败：{e}")
            return
        yield event.plain_result(f"✅ 已放入灵石 × {amount:,}")

    @player_required
    async def handle_remove_item(self, player: Player, event: AstrMessageEvent, args: str = ""):
        name = args.strip()
        if not name:
            yield event.plain_result("用法：/移除物品 <名称>")
            return
        trade = await self.mgr.get_active_trade(player.user_id)
        if not trade:
            yield event.plain_result("当前没有进行中的交易")
            return
        try:
            await self.mgr.remove_item(trade["trade_id"], player.user_id, name)
        except ValueError as e:
            yield event.plain_result(f"移除失败：{e}")
            return
        yield event.plain_result(f"✅ 已取回【{name}】")

    @player_required
    async def handle_view_trade(self, player: Player, event: AstrMessageEvent):
        trade = await self.mgr.get_active_trade(player.user_id)
        if not trade:
            yield event.plain_result("当前没有进行中的交易")
            return
        import json
        a_items = json.loads(trade["player_a_items"] or "[]")
        b_items = json.loads(trade["player_b_items"] or "[]")
        a_name = trade["player_a"]
        b_name = trade["player_b"]
        yield event.plain_result(
            f"📋 交易 #{trade['trade_id']}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"【{a_name}】放入:\n"
            f"  灵石: {trade['player_a_stones']:,}\n"
            f"  物品: {', '.join(f'{i[\"name\"]}×{i[\"count\"]}' for i in a_items) or '无'}\n"
            f"  确认: {'✅' if trade['a_confirmed'] else '❌'}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"【{b_name}】放入:\n"
            f"  灵石: {trade['player_b_stones']:,}\n"
            f"  物品: {', '.join(f'{i[\"name\"]}×{i[\"count\"]}' for i in b_items) or '无'}\n"
            f"  确认: {'✅' if trade['b_confirmed'] else '❌'}"
        )

    @player_required
    async def handle_confirm(self, player: Player, event: AstrMessageEvent):
        trade = await self.mgr.get_active_trade(player.user_id)
        if not trade:
            yield event.plain_result("当前没有进行中的交易")
            return
        try:
            completed = await self.mgr.confirm(trade["trade_id"], player.user_id)
        except ValueError as e:
            yield event.plain_result(f"确认失败：{e}")
            return
        if completed:
            yield event.plain_result("🎉 交易完成！双方物品已结算")
        else:
            yield event.plain_result("✅ 已确认。等待对方确认...")

    @player_required
    async def handle_cancel(self, player: Player, event: AstrMessageEvent):
        trade = await self.mgr.get_active_trade(player.user_id)
        if not trade:
            yield event.plain_result("当前没有进行中的交易")
            return
        await self.mgr.cancel(trade["trade_id"], player.user_id)
        yield event.plain_result("已取消交易，物品/灵石已返还")
```

- [ ] **Step 2: 在 `handlers/__init__.py` 导出**

在末尾追加：

```python
from .trade_handler import TradeHandler
```

并在 `__all__` 末尾追加 `"TradeHandler"`。

- [ ] **Step 3: 验证 import**

```bash
python -c "from handlers import TradeHandler; print('OK')"
```

Expected: `OK`。

- [ ] **Step 4: Commit**

```bash
git add handlers/trade_handler.py handlers/__init__.py
git commit -m "feat(handlers): TradeHandler with 7 commands"
```

---

### Task 20: ConsignmentHandler 实现

**Files:**
- Create: `handlers/consignment_handler.py`
- Modify: `handlers/__init__.py`

- [ ] **Step 1: 创建 `handlers/consignment_handler.py`**

```python
"""寄售行命令处理器。"""
from __future__ import annotations
from astrbot.api.event import AstrMessageEvent
from ..data import DataBase
from ..models import Player
from ..managers import ConsignmentManager
from ..config_manager import ConfigManager
from .utils import player_required


__all__ = ["ConsignmentHandler"]


class ConsignmentHandler:
    def __init__(self, db: DataBase, cm: ConsignmentManager, config_manager: ConfigManager):
        self.db = db
        self.mgr = cm
        self.config_manager = config_manager

    def _lookup_item_meta(self, name: str) -> tuple[str, str] | None:
        """返回 (item_id, item_type) 或 None"""
        for source, item_type in [
            (self.config_manager.weapons_data, "weapon"),
            (self.config_manager.items_data, "equipment"),
            (self.config_manager.pills_data, "pill"),
            (self.config_manager.exp_pills_data, "pill"),
            (self.config_manager.utility_pills_data, "pill"),
        ]:
            if name in source:
                entry = source[name]
                return str(entry.get("id", name)), item_type
        return None

    @player_required
    async def handle_list_item(self, player: Player, event: AstrMessageEvent, args: str = ""):
        parts = args.strip().split()
        if len(parts) < 2:
            yield event.plain_result("用法：/寄售 <物品名> <价格> [数量]")
            return
        name = parts[0]
        if not parts[1].isdigit():
            yield event.plain_result("价格必须是正整数")
            return
        price = int(parts[1])
        quantity = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1

        meta = self._lookup_item_meta(name)
        if not meta:
            yield event.plain_result(f"找不到物品【{name}】的配置")
            return
        item_id, item_type = meta

        try:
            lid = await self.mgr.list_item(player.user_id, name, item_id,
                                            item_type, price, quantity)
        except ValueError as e:
            yield event.plain_result(f"上架失败：{e}")
            return
        fee = int(price * 0.05)
        yield event.plain_result(
            f"✅ 上架成功（编号 {lid}）\n"
            f"物品：{name} × {quantity}\n"
            f"价格：{price:,} 灵石\n"
            f"已扣手续费：{fee:,} 灵石（不退还）"
        )

    @player_required
    async def handle_browse(self, player: Player, event: AstrMessageEvent, args: str = ""):
        page = int(args.strip()) if args.strip().isdigit() else 1
        page = max(1, page)
        listings = await self.mgr.list_active(offset=(page - 1) * 10, limit=10)
        if not listings:
            yield event.plain_result("寄售行空空如也")
            return
        lines = [f"🏪 寄售行 第 {page} 页"]
        for L in listings:
            lines.append(
                f"#{L['listing_id']} 【{L['item_name']}】× {L['quantity']} "
                f"| {L['price']:,} 灵石 | 卖家 {L['seller_id']}"
            )
        lines.append("使用 /购买寄售 <编号> 购买")
        yield event.plain_result("\n".join(lines))

    @player_required
    async def handle_buy(self, player: Player, event: AstrMessageEvent, args: str = ""):
        if not args.strip().isdigit():
            yield event.plain_result("用法：/购买寄售 <编号>")
            return
        lid = int(args.strip())
        try:
            listing = await self.mgr.buy_listing(lid, player.user_id)
        except ValueError as e:
            yield event.plain_result(f"购买失败：{e}")
            return
        yield event.plain_result(
            f"🎉 购买成功\n"
            f"物品：{listing['item_name']} × {listing['quantity']}\n"
            f"花费：{listing['price']:,} 灵石"
        )

    @player_required
    async def handle_my(self, player: Player, event: AstrMessageEvent):
        listings = await self.mgr.list_my(player.user_id)
        if not listings:
            yield event.plain_result("你没有正在寄售的物品")
            return
        lines = ["📋 我的寄售"]
        for L in listings:
            lines.append(f"#{L['listing_id']} 【{L['item_name']}】× {L['quantity']} | {L['price']:,} 灵石")
        yield event.plain_result("\n".join(lines))

    @player_required
    async def handle_cancel(self, player: Player, event: AstrMessageEvent, args: str = ""):
        if not args.strip().isdigit():
            yield event.plain_result("用法：/下架寄售 <编号>")
            return
        lid = int(args.strip())
        try:
            await self.mgr.cancel_listing(lid, player.user_id)
        except ValueError as e:
            yield event.plain_result(f"下架失败：{e}")
            return
        yield event.plain_result(f"✅ 已下架 #{lid}（手续费不退）")
```

- [ ] **Step 2: 在 `handlers/__init__.py` 导出**

末尾追加：

```python
from .consignment_handler import ConsignmentHandler
```

并在 `__all__` 末尾追加 `"ConsignmentHandler"`。

- [ ] **Step 3: 验证 import**

```bash
python -c "from handlers import ConsignmentHandler; print('OK')"
```

Expected: `OK`。

- [ ] **Step 4: Commit**

```bash
git add handlers/consignment_handler.py handlers/__init__.py
git commit -m "feat(handlers): ConsignmentHandler with 5 commands"
```

---

### Task 21: main.py 注册新命令 + 后台过期任务

**Files:**
- Modify: `main.py`

- [ ] **Step 1: 在 import 行追加 trade/consignment**

把 `from .handlers import (...)` 中的列表末尾加入 `TradeHandler, ConsignmentHandler`：

```python
from .handlers import (
    MiscHandler, PlayerHandler, EquipmentHandler, BreakthroughHandler,
    PillHandler, ShopHandler, StorageRingHandler,
    SectHandlers, BossHandlers, CombatHandlers, RankingHandlers,
    RiftHandlers, AdventureHandlers, AlchemyHandlers, ImpartHandlers,
    NicknameHandler, BankHandlers, BountyHandlers, ImpartPkHandlers,
    BlessedLandHandlers, SpiritFarmHandlers, DualCultivationHandlers, SpiritEyeHandlers,
    TradeHandler, ConsignmentHandler,
)
```

把 `from .managers import (...)` 末尾加入 `TradeManager, ConsignmentManager`：

```python
from .managers import (
    CombatManager, SectManager, BossManager, RiftManager,
    RankingManager, AdventureManager, AlchemyManager, ImpartManager,
    BankManager, BountyManager, ImpartPkManager,
    BlessedLandManager, SpiritFarmManager, DualCultivationManager, SpiritEyeManager,
    TradeManager, ConsignmentManager,
)
```

- [ ] **Step 2: 添加命令常量**

在 `CMD_REBIRTH = "弃道重修"` 之前添加：

```python
# 玩家交易系统
CMD_TRADE_START = "交易"
CMD_TRADE_ADD_ITEM = "添加物品"
CMD_TRADE_ADD_STONES = "添加灵石"
CMD_TRADE_REMOVE_ITEM = "移除物品"
CMD_TRADE_VIEW = "查看交易"
CMD_TRADE_CONFIRM = "确认交易"
CMD_TRADE_CANCEL = "取消交易"

# 寄售行
CMD_CONSIGN_LIST = "寄售"
CMD_CONSIGN_BROWSE = "寄售行"
CMD_CONSIGN_BUY = "购买寄售"
CMD_CONSIGN_MY = "我的寄售"
CMD_CONSIGN_CANCEL = "下架寄售"
```

- [ ] **Step 3: 在 `__init__` 初始化 manager/handler**

在 Phase 4 灵眼初始化（`self.spirit_eye_handlers = ...`）之后追加：

```python
        # 玩家交易系统
        self.trade_mgr = TradeManager(self.db.conn) if self.db.conn else None  # 真正赋值在 initialize()
        self.consignment_mgr = ConsignmentManager(self.db.conn) if self.db.conn else None
        self.trade_handler = None
        self.consignment_handler = None
```

注：由于 `__init__` 时 `self.db.conn` 还是 None（连接在 `initialize` 中建立），所以真正初始化推迟。

在 `self.bounty_check_task = None` 之后追加：

```python
        self.consignment_check_task = None  # 寄售过期检查任务
```

- [ ] **Step 4: 在 `initialize()` 中创建 manager/handler 实例并启动任务**

在 `migration_manager.migrate()` 之后、`logger.info("【修仙插件】已加载。")` 之前追加：

```python
        # 玩家交易系统：在数据库连接后初始化
        self.trade_mgr = TradeManager(self.db.conn)
        self.consignment_mgr = ConsignmentManager(self.db.conn)
        self.trade_handler = TradeHandler(self.db, self.trade_mgr)
        self.consignment_handler = ConsignmentHandler(self.db, self.consignment_mgr, self.config_manager)

        self.consignment_check_task = asyncio.create_task(self._schedule_consignment_check())
```

- [ ] **Step 5: 在 `terminate()` 中取消任务**

在 `if self.bounty_check_task: self.bounty_check_task.cancel()` 之后追加：

```python
        if self.consignment_check_task:
            self.consignment_check_task.cancel()
```

- [ ] **Step 6: 添加 _schedule_consignment_check 方法**

在 `_schedule_bounty_check` 方法之后追加：

```python
    async def _schedule_consignment_check(self):
        """寄售行过期检查任务（每小时检查一次）"""
        while True:
            try:
                await self.db.ensure_connection()
                await asyncio.sleep(3600)
                expired = await self.consignment_mgr.expire_old_listings()
                if expired > 0:
                    logger.info(f"【修仙插件】处理了 {expired} 个过期寄售物品")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"寄售过期检查任务异常: {e}")
                await asyncio.sleep(60)
```

- [ ] **Step 7: 注册 12 个命令**

在文件末尾（最后一个 `@filter.command` 之后）追加：

```python
    @filter.command(CMD_TRADE_START, "发起即时交易")
    @require_whitelist
    async def handle_trade_start(self, event: AstrMessageEvent, args: str = ""):
        async for r in self.trade_handler.handle_start_trade(event, args):
            yield r

    @filter.command(CMD_TRADE_ADD_ITEM, "向交易放入物品")
    @require_whitelist
    async def handle_trade_add_item(self, event: AstrMessageEvent, args: str = ""):
        async for r in self.trade_handler.handle_add_item(event, args):
            yield r

    @filter.command(CMD_TRADE_ADD_STONES, "向交易放入灵石")
    @require_whitelist
    async def handle_trade_add_stones(self, event: AstrMessageEvent, args: str = ""):
        async for r in self.trade_handler.handle_add_stones(event, args):
            yield r

    @filter.command(CMD_TRADE_REMOVE_ITEM, "从交易移除物品")
    @require_whitelist
    async def handle_trade_remove_item(self, event: AstrMessageEvent, args: str = ""):
        async for r in self.trade_handler.handle_remove_item(event, args):
            yield r

    @filter.command(CMD_TRADE_VIEW, "查看当前交易内容")
    @require_whitelist
    async def handle_trade_view(self, event: AstrMessageEvent):
        async for r in self.trade_handler.handle_view_trade(event):
            yield r

    @filter.command(CMD_TRADE_CONFIRM, "确认交易")
    @require_whitelist
    async def handle_trade_confirm(self, event: AstrMessageEvent):
        async for r in self.trade_handler.handle_confirm(event):
            yield r

    @filter.command(CMD_TRADE_CANCEL, "取消交易")
    @require_whitelist
    async def handle_trade_cancel(self, event: AstrMessageEvent):
        async for r in self.trade_handler.handle_cancel(event):
            yield r

    @filter.command(CMD_CONSIGN_LIST, "寄售物品")
    @require_whitelist
    async def handle_consignment_list_item(self, event: AstrMessageEvent, args: str = ""):
        async for r in self.consignment_handler.handle_list_item(event, args):
            yield r

    @filter.command(CMD_CONSIGN_BROWSE, "浏览寄售行")
    @require_whitelist
    async def handle_consignment_browse(self, event: AstrMessageEvent, args: str = ""):
        async for r in self.consignment_handler.handle_browse(event, args):
            yield r

    @filter.command(CMD_CONSIGN_BUY, "购买寄售物品")
    @require_whitelist
    async def handle_consignment_buy(self, event: AstrMessageEvent, args: str = ""):
        async for r in self.consignment_handler.handle_buy(event, args):
            yield r

    @filter.command(CMD_CONSIGN_MY, "查看自己的寄售")
    @require_whitelist
    async def handle_consignment_my(self, event: AstrMessageEvent):
        async for r in self.consignment_handler.handle_my(event):
            yield r

    @filter.command(CMD_CONSIGN_CANCEL, "下架寄售物品")
    @require_whitelist
    async def handle_consignment_cancel(self, event: AstrMessageEvent, args: str = ""):
        async for r in self.consignment_handler.handle_cancel(event, args):
            yield r
```

- [ ] **Step 8: 语法验证**

```bash
python -c "import ast; ast.parse(open('main.py', encoding='utf-8').read()); print('OK')"
```

Expected: `OK`。

- [ ] **Step 9: Commit**

```bash
git add main.py
git commit -m "feat(main): register trade/consignment commands and expiry task"
```

---

### Task 22: 全套单元测试回归

- [ ] **Step 1: 跑完整测试套件**

```bash
cd "E:/Github/astrbot_plugin_monixiuxian2-main"
python -m pytest tests/ -v
```

Expected: 所有测试 PASS（合计应 > 30 个测试用例）。如果有失败：

- import 错误 → 检查 conftest.py 是否需要加 `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))`
- 数据库相关错误 → 检查 fixture 是否清理干净

- [ ] **Step 2: 无需 commit**（如改了 conftest 需 commit）

---

## Phase D：端到端冒烟验证

### Task 23: 在真实运行环境冒烟

**Files:**
- 仅运行 + 截图记录

- [ ] **Step 1: 确认 metadata.yaml 版本号**

```bash
cat metadata.yaml
```

如有需要，把 `version: 3.1.3` 改为 `version: 3.2.0` 并 commit。

- [ ] **Step 2: 部署到 AstrBot 实例（用户手动）**

把整个 `astrbot_plugin_monixiuxian2-main/` 目录放到 AstrBot 的插件目录中，重启 AstrBot。

- [ ] **Step 3: 检查启动日志**

确认日志中出现：

```
当前数据库版本: v20, 最新版本: v21
正在执行数据库升级: v20 -> v21 ...
数据库升级成功: v21
【修仙插件】已加载。
```

如果出现错误，截取日志并修正。

- [ ] **Step 4: 用两个账号冒烟**

由用户在群里依次输入：

1. A 和 B 各 `/我要修仙`
2. A 给自己加灵石和物品（用管理员工具或经过冒险积累）
3. A `/交易 @B` → 期望提示发起成功
4. A `/添加灵石 100000`、`/添加物品 灵草 2`
5. A 和 B 分别 `/查看交易` → 看到内容
6. A 和 B 分别 `/确认交易` → 第二个完成后提示交易完成
7. A 检查 `/我的信息` 灵石减少、物品减少；B 反之
8. A `/寄售 灵草 50000 1` → 检查 5% 手续费已扣
9. B `/寄售行` → 看到列表
10. B `/购买寄售 1` → 检查双方变化

- [ ] **Step 5: 记录冒烟结果**

如全部通过，写一行 commit message 收尾：

```bash
git commit --allow-empty -m "test: e2e smoke verified for trade/consignment/economy"
```

如果有 bug，回到对应 Task 修复后重测。

---

## 自检清单（实现前可逐条核对）

- [ ] Phase A 三个 JSON 仅追加，不修改现有条目（同名跳过保证）
- [ ] Phase B 缩放仅修改 price/reward 数值字段，不动 exp/时间/倍率
- [ ] Phase A、Phase B 的备份在 `config/.backup/<timestamp>/`
- [ ] v21 迁移在 `_create_all_tables_v2` 中也加了相同建表语句（新装机用）
- [ ] `UserStatus.TRADING = 5` 已加，`get_name` 也补了
- [ ] `BUSY_STATE_ALLOWED_COMMANDS` 加了寄售相关 4 个命令
- [ ] 所有交易/寄售的扣减操作都用 `BEGIN IMMEDIATE` 事务
- [ ] 添加/移除物品时清空 a_confirmed/b_confirmed，避免一方偷改后另一方未察觉直接结算
- [ ] main.py 的 manager 初始化延迟到 `initialize()`（因为 db.conn 在 __init__ 时是 None）
- [ ] terminate 取消了 `consignment_check_task`
- [ ] 12 个新命令都加了 `@require_whitelist`
