# 秘境副本系统实现计划

## Context

在现有修仙插件中新增肉鸽(Roguelike)副本玩法。玩家进入秘境后，以 1-2-2 分支地图推进深度，每3步为一个周期（选一次路 → 自动走两步），通过战斗/宝箱/篝火等节点获取奖励，最终击败BOSS结算。每日无限参与但奖励有上限。

## 拓扑结构

```
[合并点] ─┬─ A ─→ A2 ─→ A3 ─┬─ [合并点]
          └─ B ─→ B2 ─→ B3 ─┘
           ↑选一次    自动走2步
```

## 实现步骤

### 1. 配置文件 `config/dungeon_config.json`

定义秘境列表、节点池、战斗模板、掉落表、每日奖励上限。

### 2. 数据模型

**models_extended.py** 新增:
- `DungeonNode` dataclass (step, node_type, label, detail, generated, result)
- `DungeonCycle` dataclass (cycle_index, depth_start, path_a[3], path_b[3])
- `DungeonRun` dataclass (user_id, dungeon_key, depth, stamina, max_stamina, hp, max_hp, overdraft_count, inventory, log, current_cycle, chosen_path, step_in_cycle, state)

**models.py** Player 新增:
- `sleeping_bag_level: int = 0`

### 3. 数据库迁移 v35

- `CREATE TABLE dungeon_runs` — 存储进行中的副本状态（JSON序列化整个DungeonRun）
- `ALTER TABLE players ADD COLUMN sleeping_bag_level INTEGER DEFAULT 0`
- `_ensure_table_integrity` 添加 dungeon_runs 表检查

### 4. database_extended.py — CRUD方法

- `get_dungeon_run(user_id)` / `save_dungeon_run(run)` / `delete_dungeon_run(user_id)`
- `get_dungeon_daily_reward(user_id)` / `set_dungeon_daily_reward(user_id, amount)` — system_config 存储

### 5. managers/dungeon_manager.py — 核心逻辑 (~600行)

- `get_available_dungeons(player)` — 返回玩家可进入的秘境列表
- `enter_dungeon(user_id, dungeon_key, player, config_manager)` — 初始化副本
- `generate_cycle(run, config)` — 生成一个 1-2-2 周期地图
- `show_map(run)` — 渲染文字地图预览
- `choose_path(user_id, choice)` — A/B选择 → 自动走3步
- `_process_node(run, node)` — 处理单个节点事件
- `_dungeon_combat(player_stats, monster_stats)` — 复用 combat_manager 的简化战斗
- `_resolve_cycle_rewards(run)` — 结算一个周期的奖励
- `get_status(user_id)` — 副本状态面板
- `retreat(user_id, player)` — 主动撤离 + 结算
- `settle_dungeon(run, player, victory)` — 最终结算（写入数据库）
- `_check_daily_reward_cap(user_id)` — 每日奖励上限检查

### 6. handlers/dungeon_handlers.py — 指令处理

- `handle_dungeon_list` — /秘境 列表
- `handle_dungeon_enter` — /进入秘境 <名称>
- `handle_dungeon_advance` — /秘境前进 [A/B]
- `handle_dungeon_status` — /秘境状态
- `handle_dungeon_retreat` — /秘境撤离

### 7. 注册与集成

**main.py:**
- 导入 DungeonHandler + DungeonManager
- 实例化并注册5个命令
- 注册常量

**handlers/utils.py:**
- `BUSY_STATE_ALLOWED_COMMANDS` 新增: `秘境状态`, `秘境前进`, `秘境撤离`, `秘境背包`
- `COMMAND_FOOTERS` 新增秘境相关提示

**handlers/__init__.py / managers/__init__.py:**
- 新增导出

**data/default_configs.py:**
- 新增 dungeon_config 默认配置

## 关键文件

| 文件 | 操作 |
|------|------|
| `config/dungeon_config.json` | 新建 |
| `models.py` | 修改 Player 新增字段 |
| `models_extended.py` | 修改 新增3个dataclass |
| `data/migration.py` | 修改 v35 |
| `data/database_extended.py` | 修改 新增CRUD |
| `data/data_manager.py` | 修改 Player字段读写 |
| `data/default_configs.py` | 修改 默认配置 |
| `managers/dungeon_manager.py` | 新建 ~600行 |
| `handlers/dungeon_handlers.py` | 新建 ~100行 |
| `handlers/utils.py` | 修改 白名单 |
| `handlers/__init__.py` | 修改 导出 |
| `managers/__init__.py` | 修改 导出 |
| `main.py` | 修改 注册命令 |

## 验证方式

1. `/e/python/python.exe -c "from managers.dungeon_manager import DungeonManager"` — 语法检查
2. `node -c docs/app.js` — 确保不影响已有功能
3. 运行 `pytest` — 确保现有测试通过
