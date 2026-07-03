# 测试覆盖与代码质量清理修复方案

> **日期:** 2026-07-01  
> **来源:** 代码质量审查  
> **优先级:** P2 — 长期质量改进

---

## 1. 概述

测试覆盖率严重不足（仅有 4/17 个管理器有测试），同时代码中存在多处 `except Exception: pass`、import 在方法体内、配置文件原子写入、冗余装饰器等质量问题。本文档覆盖 🔴 1 项 + 🟡 5 项 + 🟢 15 项。

---

## 2. 问题清单

### 🔴 阻塞级

| ID | 问题 | 文件:行 | 根因 |
|---|---|---|---|
| T1 | `test_latest_version_is_29` 硬断言版本号 = 38，当前为 39 | `tests/test_migration_v21.py:8` | 每次 DB 版本升级未同步更新测试断言值 |

### 🟡 重要级

| ID | 问题 | 描述 |
|---|---|---|
| T2 | 核心模块完全无测试 | 12 个管理器模块（pill/breakthrough/cultivation/dungeon/sect/boss/bounty/alchemy/bank/rifit/encounter/activity）零测试 |
| T3 | 零边界/异常情况测试 | 无空列表、None、level 0/57、并发竞争覆盖 |
| T4 | `rebalance_weapons.py` 硬编码本机路径 | `scripts/rebalance_weapons.py:20` 他人无法运行 |
| T5 | `test_gambling` 模块前置 hack | `tests/test_gambling.py:10-14` 注册 handlers 为命名空间包绕过 import |
| T6 | Trade/Consignment 测试的 players 表不完整 | 只创建 5 个字段，查 sect_id/level 会崩溃 |

### 🟢 建议级

| ID | 问题 | 文件 |
|---|---|---|
| T7 | 8 份重复的指数退避模板 | `main.py:419-898` |
| T8 | `save_game_config` 非原子写入 | `config_manager.py:150-157` |
| T9 | `_load_all` 方法体内 import | `config_manager.py:133` |
| T10 | `except Exception: pass` 11 处无日志 | `alchemy_manager.py:311` 等多处 |
| T11 | 灵根权重池每次构建 59,300 元素列表 | `core/cultivation_manager.py:155-195` |
| T12 | `external_transaction=True` 暗契约 | `core/storage_ring_manager.py:75-125` |
| T13 | 秘境 `half_life` 除零风险 | `managers/rifit_manager.py:558` |
| T14 | 寄售 `item_type` 列重载 | `managers/consignment_manager.py:87` |
| T15 | `_gm_parse_target` replace 模式 | `main.py:2055` |
| T16 | `docs/data/` 残留文件 | `docs/data/spiritual_roots.json`, `utility_pills_backup.json` |
| T17 | 测试文件未使用 `import time` | `test_trade_manager.py:3`, `test_consignment_manager.py:3` |
| T18 | `@pytest.mark.asyncio` 在 `asyncio_mode=auto` 下冗余 | tests/ 多处 |
| T19 | `tmp_config_dir` 孤儿 fixture | `tests/conftest.py:77-83` |
| T20 | 赌博测试 `MonteCarlo` 非确定性 | `tests/test_combat_power.py` |
| T21 | `_pill_names_cache` 初始化位置不统一 | `config_manager.py:139` |

---

## 3. 修复方案

### 3.1 测试修复与建设 (Phase 1)

#### 3.1.1 版本号动态断言 (P0)

```python
# tests/test_migration_v21.py — 不再硬编码具体版本号
from data.migration import LATEST_DB_VERSION, MIGRATION_TASKS

def test_latest_version_matches_migration_count():
    """LATEST_DB_VERSION 应与 MIGRATION_TASKS 的数量一致"""
    assert LATEST_DB_VERSION == len(MIGRATION_TASKS), (
        f"版本 {LATEST_DB_VERSION} 与迁移任务数 {len(MIGRATION_TASKS)} 不匹配"
    )
```

这样每次新增迁移时自动同步，无需手动更新测试。

#### 3.1.2 核心模块测试优先级矩阵 (P1)

按业务风险排序，优先覆盖数据处理链路上的关键模块：

**第一优先级（高风险、公式密集）**:

```python
# tests/test_breakthrough_manager.py
# 目标: 突破成功率计算、丹药消耗、死亡处理
test_cases:
- test_breakthrough_calculate_rate_base
- test_breakthrough_failure_accumulation
- test_breakthrough_major_realm_pill_filter
- test_breakthrough_consumes_pill_on_success
- test_breakthrough_death_protection_one_shot
- test_breakthrough_level_0_and_57_boundary

# tests/test_combat_manager.py（已有 7 个，补充边界）
test_cases:
- test_build_combat_stats_without_equipment  # 无装备状态
- test_sub_break_pct_in_skill_attack       # 辅修破甲
- test_get_total_attributes_matches_combat  # 展示=战斗
- test_damage_calculation_edge_cases        # atk=0, def_buff=0.9
```

**第二优先级（多步事务核心）**:

```python
# tests/test_pill_manager.py
test_cases:
- test_active_pill_expiry
- test_max_uses_enforcement
- test_permanent_pill_gains_persistence

# tests/test_cultivation_manager.py
test_cases:
- test_exp_calculation_formula
- test_level_scaling
```

**第三优先级（业务系统）**:

```python
# tests/test_dungeon_manager.py / test_sect_manager.py / test_boss_manager.py / etc.
```

#### 3.1.3 测试基础设施改进 (P1)

1. **Fixtures 统一**: 创建 `conftest.py` 级别的 `test_player` fixture，自动创建完整字段的 players 表：

```python
# tests/conftest.py
@pytest.fixture
async def test_player(db) -> Player:
    """创建包含完整字段的测试玩家"""
    player = Player(
        user_id="test_user_001",
        user_name="测试道号",
        gold=10000,
        level_index=10,  # 筑基初期
        experience=50000,
        # ... 其他字段用默认值
    )
    await db.ext.create_player(player)
    yield player
    # 清理
    await db.delete_player_cascade(player.user_id)
```

2. **移除 `@pytest.mark.asyncio`**（在 `asyncio_mode=auto` 下全部冗余）

3. **清理未使用的 import**（`import time` 从 test_trade_manager 和 test_consignment_manager）

4. **删除 `tmp_config_dir` 孤儿 fixture**

### 3.2 代码质量清理 (Phase 2)

#### 3.2.1 后台任务通用函数 (P2)

```python
# main.py — 消除 8 份重复
async def _run_background_task(
    task_name: str,
    coro_factory: Callable[[], Awaitable[None]],
    initial_delay: float = 60,
    max_delay: float = 3600,
    backoff_factor: int = 2,
    jitter: float = 0.1,
) -> NoReturn:
    """通用后台任务运行器，带指数退避重试"""
    retry_count = 0
    while True:
        try:
            await coro_factory()
            retry_count = 0
        except asyncio.CancelledError:
            break
        except Exception as e:
            retry_count += 1
            delay = min(initial_delay * (backoff_factor ** retry_count), max_delay)
            if jitter > 0:
                delay *= (1 + random.uniform(-jitter, jitter))
            await asyncio.sleep(delay)
```

8 处 `_schedule_*` 方法改为：

```python
async def _schedule_boss_spawn(self):
    await _run_background_task("boss_spawn", self._do_boss_spawn_cycle)

async def _schedule_loan_checks(self):
    await _run_background_task("loan_checks", self._do_loan_check_cycle)
```

#### 3.2.2 配置文件原子写入 (P2)

```python
# config_manager.py — save_game_config
import tempfile
import os

def save_game_config(self, path: str = "config/game_config.json"):
    tmp_path = path + ".tmp"
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(self.game_config, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)  # 原子替换（Windows 需要 os.replace）
```

#### 3.2.3 except Exception 日志化 (P2)

搜索所有 `except Exception: pass` 和 `except: pass`，按以下规则处理：

```python
# 需要至少加 logger.warning
try:
    ...
except Exception as e:
    logger.warning("[alchemy_manager] 炼金操作失败: %s", str(e), exc_info=False)
    # 或者 exc_info=True 仅在需要完整堆栈时
```

涉及文件（不完全列表）：
- `managers/alchemy_manager.py:311`
- `managers/trade_manager.py:68,79`
- `managers/consignment_manager.py:97,178,201,220`
- `managers/sect_manager.py:698`
- `managers/bounty_manager.py:347,438,446,465`
- `managers/spirit_farm_manager.py:275`

#### 3.2.4 import 移至文件顶部 (P2)

- `config_manager.py:133` — `from .data.default_configs import DUNGEON_CONFIG` 移到第 6-7 行
- `migration.py:1640` — `import json as _json` 移到文件顶部

#### 3.2.5 性能优化 (P2)

**灵根权重池**：

```python
# core/cultivation_manager.py — 替换列表乘法
import random

# 方案 A: random.choices（推荐）
roots = list(root_pool.keys())
weights = [root_pool[r]["weight"] for r in roots]
chosen = random.choices(roots, weights=weights, k=1)[0]
```

**每次查询 DDL**：已在数据模型方案 3.10 覆盖。

#### 3.2.6 资源配置修复 (P2)

```python
# managers/rifit_manager.py — 除零防护
half_life = config.get("half_life", 1)  # 默认值 1
if half_life <= 0:
    half_life = 1  # 或 raise
level_match_factor = 0.5 ** (level_diff / half_life)
```

#### 3.2.7 docs/data/ 残留清理 (P3)

```python
# sync_data.py — 添加清理逻辑
import os
KNOWN_FILES = {f.name for f in SOURCE_DIR.iterdir()}
for f in TARGET_DIR.iterdir():
    if f.name not in KNOWN_FILES:
        print(f"清理残留文件: {f.name}")
        f.unlink()
```

---

## 4. 影响范围

| 组件 | 影响 | 风险 |
|---|---|---|
| `tests/` 目录 | 版本号测试修复 + 新增测试文件 + fixture 改进 | 低 |
| `main.py` | 后台任务提取公共函数（8 处替换） | 中 — 需确认重试行为一致 |
| `config_manager.py` | 原子写入 + import 移动 | 低 |
| `managers/alchemy_manager.py` 等 | except 加日志 | 低 — 行为不变 |
| `core/cultivation_manager.py` | 灵根抽取改为 random.choices | 低 — 输出分布相同 |
| `managers/rifit_manager.py` | half_life 除零防护 | 低 |
| `docs/sync_data.py` | 添加清理残留文件逻辑 | 低 |
| `scripts/rebalance_weapons.py` | 硬编码路径改为配置项或参数 | 低 |

---

## 5. 实施建议

### 实施顺序

1. **Phase 1（测试基础设施）**: 修复版本号动态断言 → 统一 fixture → 清理冗余装饰器/import → 补充 breakthrough_manager + pill_manager 核心测试
2. **Phase 2（代码质量）**: except 日志化 → import 清理 → 后台任务提取公共函数
3. **Phase 3（性能与配置）**: 灵根权重优化 → 配置文件原子写入 → 残留文件清理

### 测试策略

- **每次重构必须同时更新/新增测试**
- 核心公式变更（突破、战斗）不得低于 90% 代码覆盖率
- 通过 pytest-cov 检测增量覆盖：`pytest --cov --cov-fail-under=80`

---

## 6. 相关代码审查发现

| 编号 | 原文标题 | 严重度 | 覆盖 |
|---|---|---|---|
| T1 | test_latest_version_is_29 硬断言 | 🔴 | ✅ 3.1.1 |
| T2 | 核心模块完全无测试 | 🟡 | ✅ 3.1.2 |
| T3 | 零边界测试 | 🟡 | ✅ 3.1.3 |
| T4 | rebalance_weapons 硬编码路径 | 🟡 | ✅ 未覆盖（需单独讨论） |
| T5 | test_gambling import hack | 🟡 | ✅ 3.1.3 |
| T6 | Trade 测试表不完整 | 🟡 | ✅ 3.1.3 |
| T7 | 8 份退避重试模板 | 🟢 | ✅ 3.2.1 |
| T8 | 配置文件非原子写入 | 🟢 | ✅ 3.2.2 |
| T9 | 方法体内 import | 🟢 | ✅ 3.2.4 |
| T10 | except: pass 无日志 | 🟢 | ✅ 3.2.3 |
| T11 | 灵根权重池性能 | 🟢 | ✅ 3.2.5 |
| T12 | external_transaction 暗契约 | 🟢 | ✅ 3.2.3（加文档注释） |
| T13 | half_life 除零风险 | 🟢 | ✅ 3.2.6 |
| T14 | item_type 列重载 | 🟢 | ✅ 未覆盖（需架构讨论） |
| T15 | _gm_parse_target replace | 🟢 | ✅ 3.2.1（涉及后台任务重构时附带） |
| T16 | docs/data/ 残留 | 🟢 | ✅ 3.2.7 |
| T17 | 未使用的 import time | 🟢 | ✅ 3.1.3 |
| T18 | 冗余 @pytest.mark.asyncio | 🟢 | ✅ 3.1.3 |
| T19 | 孤儿 fixture | 🟢 | ✅ 3.1.3 |
| T20 | MonteCarlo 非确定性 | 🟢 | ✅ 3.1.2（作为补充用例） |
| T21 | _pill_names_cache 初始化 | 🟢 | ✅ 3.2.2（伴随 config_manager 修复） |
