# 奇遇机缘系统设计文档 (Encounter System Design)

> **项目:** astrbot_plugin_monixiuxian2 — 文字修仙放置游戏插件
> **日期:** 2026-07-07
> **状态:** Draft v2
> **作者:** Claude Code + ENRIN233

---

## 0. 代码库现状分析

### 0.1 异步玩家交互模式（现有参考）

| 模式 | 系统 | 文件 | 说明 |
|------|------|------|------|
| **请求-响应（无超时）** | 探险副本 | `handlers/dungeon_handlers.py` + `managers/dungeon_manager.py` | 玩家输入 `/探险前进 A/B`，立即返回结果。进度存储在 `DungeonRun` 状态机中 |
| **请求-响应（有超时）** | 交易系统 | `managers/trade_manager.py` | 发起交易 → 存储 `expires_at` → 目标 `/接受交易`。后台 `_schedule_trade_check` 清理过期 |
| **请求-响应（惰性超时）** | 双修 | `managers/dual_cultivation_manager.py` | 发起请求 → 存储 `expire_at` → 目标 `/接受双修`。查询时惰性删除过期 |
| **纯定时器** | 秘境 | `managers/rift_manager.py` | `/探索秘境` → 设置 `scheduled_time` → 玩家轮询 `/完成探索` |
| **同步轮询** | 探险副本状态 | `dungeon_manager._advance_tree()` | 玩家输入 → 解析选择 → 展示结果。无效输入循环展示地图 |

**结论:** 代码库中没有 "发送选项 → 等待 N 秒内回复 → 超时处理" 的原生异步超时模式。最适合奇遇的模式是 **请求-存储-回复**（类似交易系统）：触发后存储 pending 状态，玩家通过专用命令回复。

### 0.2 Player 模型当前字段

`models.py` 的 `Player` dataclass 已有字段（截至 v40）：
- 基础字段: `user_id`, `level_index`, `spiritual_root`, `cultivation_type`, `user_name`
- 资源: `lifespan`, `experience`, `gold`, `hp`, `mp`, `atk`, `atkpractice`
- 状态: `state`, `cultivation_start_time`
- 签到: `last_check_in_date`, `monthly_sign_count`, `monthly_sign_month`
- 活跃: `daily_activity` (JSON), `daily_activity_points`, `daily_activity_date`, `daily_activity_rewarded`
- 装备: `weapon`, `armor`, `main_technique`, `techniques` (JSON), `shentong`, `sub_technique`, `furnace`
- 锻造: `equipped_weapon`, `equipped_armor`, `forging_exp`, `forging_level`
- 丹药: `active_pill_effects` (JSON), `permanent_pill_gains` (JSON), `pills_inventory` (JSON) 等
- 储物: `storage_ring`, `storage_ring_items` (JSON)
- 灵修/体修: `spiritual_qi`, `max_spiritual_qi`, `blood_qi`, `max_blood_qi`
- 宗门: `sect_id`, `sect_position`, `sect_contribution` 等
- 成就: `achievement_data` (JSON)
- 银行: `bank_vip_tier`

**需要新增的奇遇字段（4个）：** `karma`, `last_encounter_date`, `daily_encounter_count`, `encounter_history`

### 0.3 当前最新数据库版本

`data/migration.py` 第 8 行: `LATEST_DB_VERSION = 40`
v40 为锻造系统。奇遇系统将使用 v41。

### 0.4 后台任务模式（main.py）

当前 8 个后台任务均使用 `asyncio.create_task()` 启动，`while True + try/except + 指数退避` 模板：
```python
async def _schedule_xxx(self):
    retry_count = 0
    max_retry_delay = 3600
    while True:
        try:
            await self.db.ensure_connection()
            # ...
            retry_count = 0
        except asyncio.CancelledError:
            break
        except Exception as e:
            retry_count += 1
            delay = min(60 * (2 ** retry_count), max_retry_delay)
            await asyncio.sleep(delay)
```

### 0.5 ConfigManager 加载模式（config_manager.py）

`_load_all()` 中使用两种加载方式：
- `_load_json_data(path)` — 加载列表格式 JSON
- `_load_config_with_default(path, DEFAULT_DICT)` — 加载或创建带默认值的配置
- `_load_items_data(path)` — 加载并转为 `{name: item}` 字典

新系统配置加载示例（第 122-136 行）：
```python
self.sect_config = self._load_config_with_default(config_dir / "sect_config.json", SECT_CONFIG)
self.dungeon_config = self._load_config_with_default(config_dir / "dungeon_config.json", DUNGEON_CONFIG)
```

### 0.6 成就条件类型（achievement_manager.py）

当前 `_check_condition` 支持：
`level_up_rate`, `level_index`, `experience`, `gold`, `atkpractice`, `level_index_and_type` (+ `cultivation_type`), `sect_contribution`, `lifespan`

需要新增：`encounter_count`, `karma`

### 0.7 活跃任务定义（activity_manager.py）

当前 8 个任务：
```python
TASK_DEFINITIONS = {
    "check_in": ("每日签到",   10, 1),
    "rift":     ("探索秘境",   30, 1),
    "bounty":   ("完成悬赏",   20, 2),
    "harvest":  ("灵田收获",   20, 1),
    "alchemy":  ("炼丹",       30, 1),
    "smelt":    ("炼金",       30, 1),
    "interest": ("领取利息",   10, 1),
    "sect":     ("宗门贡献",   20, 1),
}
TASK_ORDER = ["check_in", "rift", "bounty", "harvest", "alchemy", "smelt", "interest", "sect"]
```

### 0.8 战斗统计构建入口（combat_manager.py）

`build_player_combat_stats()`（第 170 行）是战斗属性统一入口：
- 第 179-181 行：读取传承加成 (hp/mp/atk)
- 第 234 行：最终 ATK 公式 `final_atk = base * practice * (1+technique) * (1+weapon) * (1+armor) + impart_atk + flat_atk_bonus`
- 第 275-304 行：返回 `CombatStats` 对象

因果值注入点：第 234 行附近新增 `karma_atk_bonus`。

### 0.9 修炼经验公式（cultivation_manager.py）

`calculate_cultivation_exp_with_segments()`（第 341 行）：
- 第 364-371 行：`other_multiplier = root_speed * (1+technique) * (1+closing) * (1+land) * (1+permanent_mult)`
- 第 386 行：`total_exp = int(base_exp * minutes * other_multiplier)`

因果值修炼加成注入点：第 371 行的 `other_multiplier` 乘法链。

### 0.10 广播方法（main.py）

`_broadcast_to_whitelist_groups(message)`（第 622 行）可用于传说级奇遇全服广播。

### 0.11 BUSY_STATE_ALLOWED_COMMANDS（handlers/utils.py）

当前白名单包含可在忙碌状态下执行的命令。奇遇信息查看命令 `/奇遇信息`、`/奇遇记录` 和奇遇选择命令 `/奇遇` 需加入此白名单。

---

## 1. 概述

### 1.1 定义

**奇遇机缘** 是玩家在日常修炼过程中被动触发的随机叙事事件。每个奇遇呈现一段修仙世界的场景描述，玩家做出选择后获得不同结果（奖励/惩罚/因果变化）。

### 1.2 设计目标

| 目标 | 实现方式 |
|------|----------|
| **高耐玩性** | 60+ 事件池，4 稀有度分级，因果偏移影响事件概率 |
| **低疲劳** | 被动触发，无需额外操作，无状态锁定 |
| **主题契合** | 修仙世界观叙事，善恶因果与修炼道路呼应 |
| **系统联动** | 与每日活跃、成就、轮回、广播等系统整合 |
| **低耦合** | 不阻塞玩家正常流程，不占用 UserStatus 状态 |

### 1.3 核心设计决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 触发时机 | **操作完成后异步发送**（作为操作结果的后续消息） | 不阻塞主流程，代码侵入小 |
| 选择模式 | **存状态 + 专用回复命令**（`/奇遇 A`） | 匹配现有 `trade/dualcult` 模式，无需超时循环 |
| 状态存储 | **内存字典**（EncounterManager 中的 pending_encounters） | 超时短（180s），无需数据库 |
| 长期影响 | **善恶因果系统**（Player 模型新增字段持久化） | 角色扮演调味料，影响战斗/修炼/事件概率 |
| 境界门槛 | 全境界可用，按境界分层 | 所有玩家都能体验 |
| 触发频率 | 每日 3 次，概率触发 | 控制节奏，避免疲劳 |
| 稀有广播 | 传说级全服广播（匿名） | 增加社交话题性和 FOMO 感 |
| 状态互斥 | **不使用 UserStatus** | 允许多个系统同时运行 |

---

## 2. 触发机制

### 2.1 触发时机（v2 更新）

**v1 设计问题:** 在操作过程中插入奇遇检查会阻塞主操作流程，且需要复杂的超时等待机制。

**v2 改进:** 操作正常完成后，在主回复发出后，作为附加消息发送奇遇触发。

```python
# 范例：悬赏完成后触发奇遇
@filter.command(CMD_BOUNTY_COMPLETE, "完成悬赏")
@require_whitelist
async def handle_bounty_complete(self, event: AstrMessageEvent, bounty_id: str = ""):
    user_id = event.get_sender_id()
    # 1. 执行主操作
    async for r in self.bounty_handlers.handle_complete_bounty(event, bounty_id):
        yield r
    
    # 2. 尝试触发奇遇（作为额外消息）
    player = await self.db.get_player_by_id(user_id)
    if player:
        encounter_msg = await self.encounter_mgr.try_trigger(player, "bounty_complete")
        if encounter_msg:
            yield event.plain_result(encounter_msg)
```

触发时机与触发概率：

| 操作 | 触发概率 | 调用位置 | 代码整合方式 |
|------|----------|----------|-------------|
| 签到 | 15% | `main.py` `handle_check_in` → 签到回复后 | 在 handler 中 yield 完主结果后调用 |
| 出关 | 10% | `main.py` `handle_end_cultivation` → 出关回复后 | 在 handler 中 yield 完主结果后调用 |
| 秘境探索完成 | 20% | `main.py` `handle_rift_complete` → 探索回复后 | 在 handler 中 yield 完主结果后调用 |
| 悬赏令完成 | 25% | `main.py` `handle_bounty_complete` → 悬赏回复后 | 在 handler 中 yield 完主结果后调用 |
| Boss战斗结束 | 30% | `main.py` `handle_boss_fight` → Boss战斗回复后 | 在 handler 中 yield 完主结果后调用 |
| 探险副本前进 | 15% | `main.py` `handle_dungeon_advance` → 探险回复后 | 在 handler 中 yield 完主结果后调用 |

### 2.2 每日限制

- 每日最多触发 **3 次** 奇遇
- 次日自动重置（通过日期字符串比较，同 `daily_activity` 模式）
- 使用 Player 模型的 `last_encounter_date` 和 `daily_encounter_count` 字段（以 JSON getter/setter 方式管理）

### 2.3 触发流程（v2 更新）

```
玩家执行操作（如完成悬赏令）
    │
    ├─ 主操作处理（正常执行，yield 结果）
    │
    └─ 操作完成后：
        ├─ encounter_mgr.try_trigger(player, "bounty_complete")
        │   ├─ 检查：daily_encounter_count < 3？→ 否 → 返回 None
        │   ├─ 检查：概率检定（random.random() < trigger_pct）→ 未命中 → 返回 None
        │   ├─ 检查：是否有 pending 的奇遇？→ 有 → 返回 None（避免重叠）
        │   ├─ 筛选事件：min_level <= player.level_index <= max_level
        │   ├─ 因果偏移：karma high/low 影响权重
        │   ├─ 加权随机选择事件
        │   ├─ 更新 daily_encounter_count
        │   ├─ 存储 pending_encounter（内存字典，180s 超时）
        │   └─ 返回 奇遇描述文本（含选项）
        │
        ├─ yield event.plain_result(encounter_msg)  # 发送奇遇消息
        │
        └─ 玩家在 180s 内输入 /奇遇 A/B/C
            └─ encounter_mgr.resolve(player, user_id, "A")
                ├─ 检查 pending 是否存在 → 不存在/超时 → 返回失效提示
                ├─ 判定成功/失败（基于 risk 概率）
                ├─ 计算奖励/惩罚
                ├─ 更新 karma
                ├─ 写入 encounter_history
                └─ 返回 结果消息
```

### 2.4 超时与清理

- pending 状态在 `EncounterManager` 中保存在内存字典：`self._pending: Dict[str, dict]`
- 每个 pending 条目包含 `timestamp` 字段
- 超时时间：**180 秒**
- 清理时机：
  - `resolve()` 时惰性检查
  - 新的 `try_trigger()` 时检查（如果同一用户有旧 pending，自动清除）
  - 可选：后台每 5 分钟清理一次过期 pending（同 `_schedule_trade_check`）

```python
# Pending encounter 结构
self._pending = {
    "user_12345": {
        "encounter_id": "mountain_herb_01",
        "encounter": { ... },  # 完整事件数据
        "timestamp": 1718800000
    }
}
```

---

## 3. 事件池设计

### 3.1 事件池规模

初版 **60+** 个奇遇事件，按境界分为 6 个层级：

| 层级 | 适用境界 (level_index) | 事件数 | 特点 |
|------|------------------------|--------|------|
| 凡人期 | 0-9 | 12 | 简单选择，小奖励，教学性质 |
| 筑基期 | 10-18 | 12 | 中等风险，开始有因果影响 |
| 元婴期 | 19-27 | 12 | 复杂分支，显著因果偏移 |
| 化神期 | 28-36 | 10 | 高风险高回报，因果影响大 |
| 大乘期 | 37-45 | 8 | 传说级事件出现 |
| 轮回期 | 46+ | 8+ | 轮回专属事件，因果值决定结局 |

### 3.2 稀有度分级

| 稀有度 | 概率权重 | 特点 | 全服广播 |
|--------|----------|------|----------|
| 普通 (common) | 55% | 基础事件，简单选择 | 否 |
| 稀有 (rare) | 27% | 较好的奖励，有意义的选择 | 否 |
| 史诗 (epic) | 14% | 高价值奖励，重大因果影响 | 否 |
| 传说 (legendary) | 4% | 极稀有，改变命运的选择 | **是**（匿名） |

### 3.3 事件数据结构（v2 更新）

配置文件: `config/encounter_config.json`

```json
{
    "encounters": [
        {
            "id": "mountain_herb_01",
            "name": "山涧灵草",
            "rarity": "common",
            "min_level": 0,
            "max_level": 9,
            "weight": 100,
            "description": "你在山涧修炼时，发现一株散发微光的灵草。旁边有一头低阶妖兽正在打盹。",
            "choices": [
                {
                    "id": "a",
                    "text": "强行采摘",
                    "risk": 0.3,
                    "karma_delta": -5,
                    "cost": {},
                    "success_text": "你趁妖兽不备，迅速采摘了灵草！",
                    "success_rewards": {
                        "gold": [500, 2000],
                        "exp": [1000, 5000],
                        "item_chance": 0.5,
                        "item_pool": ["灵草精华"],
                        "pill_chance": 0,
                        "pill_pool": []
                    },
                    "fail_text": "妖兽被惊醒，你不得不狼狈逃窜，受了些轻伤。",
                    "fail_penalty": {"hp_pct": 0.2}
                },
                {
                    "id": "b",
                    "text": "悄悄绕过",
                    "risk": 0.0,
                    "karma_delta": 0,
                    "cost": {},
                    "success_text": "你小心翼翼地绕过了妖兽，虽然没有收获，但也没有危险。",
                    "success_rewards": {"gold": [100, 300], "exp": [100, 500]},
                    "fail_text": null,
                    "fail_penalty": {}
                },
                {
                    "id": "c",
                    "text": "用灵石引开妖兽",
                    "risk": 0.1,
                    "karma_delta": 3,
                    "cost": {"gold": 500},
                    "success_text": "妖兽被灵石吸引离开，你从容地采摘了灵草。",
                    "success_rewards": {
                        "gold": [1000, 3000],
                        "exp": [2000, 8000],
                        "item_chance": 0.7,
                        "item_pool": ["灵草精华", "矿石碎片"]
                    },
                    "fail_text": "妖兽叼走了灵石却没有离开，你白费了一笔。",
                    "fail_penalty": {}
                }
            ]
        }
    ],
    "trigger_chances": {
        "check_in": 0.15,
        "end_cultivation": 0.10,
        "rift_complete": 0.20,
        "bounty_complete": 0.25,
        "boss_fight": 0.30,
        "dungeon_advance": 0.15
    },
    "settings": {
        "daily_limit": 3,
        "choice_timeout_seconds": 180,
        "karma_event_bias_threshold": 500,
        "karma_event_bias_pct": 25,
        "legendary_broadcast": true
    },
    "karma_settings": {
        "min": -1000,
        "max": 1000,
        "initial": 0,
        "daily_decay": 2,
        "bonuses": {
            "demon": {"min": -1000, "max": -500, "title": "魔道修士", "atk_pct": 0.08},
            "evil": {"min": -499, "max": -100, "title": "偏邪", "atk_pct": 0.04},
            "neutral": {"min": -99, "max": 99, "title": "中立", "atk_pct": 0.0, "cultivation_pct": 0.0},
            "good": {"min": 100, "max": 499, "title": "偏正", "cultivation_pct": 0.04},
            "saint": {"min": 500, "max": 1000, "title": "正道修士", "cultivation_pct": 0.08}
        }
    }
}
```

### 3.4 完整事件表（60+ 事件）

#### 凡人期（level_index 0-9，12 事件）

| ID | 名称 | 稀有度 | 因果范围 | 说明 |
|----|------|--------|----------|------|
| common_01 | 山涧灵草 | common | -5~+3 | 采灵草 vs 绕路 vs 引开妖兽 |
| common_02 | 路遇乞丐 | common | +8~-15 | 施舍灵石 vs 漠然 vs 抢夺 |
| common_03 | 迷途小妖 | common | +5~-5 | 帮助小妖找路 vs 驱赶 |
| common_04 | 古树灵果 | rare | -10~+10 | 摘灵果（有守护兽）vs 等掉落 |
| common_05 | 山洞秘籍 | common | 0~+15 | 捡到残破功法 vs 物归原主 |
| common_06 | 受伤散修 | common | +3~-3 | 赠药 vs 搜身 |
| common_07 | 灵泉之水 | common | 0 | 饮用 +exp vs 装瓶带走 |
| common_08 | 铁矿脉 | rare | -5~+5 | 采一些 vs 留记号标记 |
| common_09 | 渡劫修士 | epic | +20~-10 | 围观感悟 vs 帮助护法 |
| common_10 | 神秘商人 | common | 0 | 购买物品 vs 以物易物 |
| common_11 | 悬崖灵药 | rare | +5~-5 | 冒险采摘 vs 安全采集 |
| common_12 | 兽王幼崽 | common | +10~-3 | 救助 vs 捕获 |

#### 筑基期（level_index 10-18，12 事件）

| ID | 名称 | 稀有度 | 因果范围 | 说明 |
|----|------|--------|----------|------|
| mid_01 | 古修士洞府 | rare | -10~+15 | 破封印 vs 参悟石碑 vs 加固离开 |
| mid_02 | 灵草市场 | common | 0~+5 | 讨价还价 vs 高价收购 |
| mid_03 | 妖兽巢穴 | common | -10~+5 | 端巢穴 vs 绕行 vs 封印 |
| mid_04 | 采药人被困 | common | +5~+20 | 救援（消耗丹药）vs 索取报酬 |
| mid_05 | 灵脉裂缝 | rare | -10~0 | 吸收灵气 vs 修复（+karma）|
| mid_06 | 散修追杀 | epic | +15~-20 | 路见不平 vs 事不关己 |
| mid_07 | 上古遗阵 | common | -5~+10 | 参悟阵法 vs 破坏核心 |
| mid_08 | 炼丹材料 | common | 0~+5 | 采集 vs 购买 |
| mid_09 | 灵兽报恩 | rare | +10~0 | 收留 vs 放生 |
| mid_10 | 神秘石碑 | epic | -15~+20 | 滴血认主 vs 感悟文字 |
| mid_11 | 地下密室 | common | -10~+5 | 探索 vs 报告宗门 |
| mid_12 | 拍卖盛会 | common | 0 | 参与拍卖 vs 观察 |

#### 元婴期（level_index 19-27，12 事件）

| ID | 名称 | 稀有度 | 因果范围 | 说明 |
|----|------|--------|----------|------|
| high_01 | 天降异象 | epic | -15~+20 | 收取陨石 vs 探查 vs 布阵炼化 |
| high_02 | 魂修遗迹 | rare | -20~+10 | 进入 vs 封印 |
| high_03 | 万年灵乳 | rare | -5~+15 | 取一半 vs 全取 vs 留根 |
| high_04 | 魔修偷袭 | common | +5~-10 | 反击 vs 谈判 |
| high_05 | 天道感悟 | epic | 0~+30 | 原地感悟 vs 分享感悟 |
| high_06 | 灵脉之源 | rare | +10~-15 | 守护 vs 抽取 |
| high_07 | 药园秘境 | common | -5~+5 | 收取成熟药材 vs 留种 |
| high_08 | 法宝碎片 | common | 0~-10 | 收取 vs 追查来源 |
| high_09 | 宗门遗迹 | rare | +15~-5 | 探索 vs 清扫 |
| high_10 | 异火奇遇 | epic | -10~+20 | 收服 vs 借助炼丹 |
| high_11 | 古修传承 | legendary | -30~+50 | 接受考验 vs 强夺 |
| high_12 | 符箓大师 | common | 0~+5 | 学习 vs 交易 |

#### 化神期（level_index 28-36，10 事件）

| ID | 名称 | 稀有度 | 因果范围 | 说明 |
|----|------|--------|----------|------|
| peak_01 | 魔修交易 | rare | -30~+25 | 购买禁术 vs 警告 vs 擒拿 |
| peak_02 | 天道碑文 | epic | +10~+30 | 感悟 vs 记录 |
| peak_03 | 域外天魔 | rare | -25~+20 | 力战 vs 谈判 vs 封印 |
| peak_04 | 先天灵宝 | legendary | -40~+30 | 收取 vs 守护（等有缘人）|
| peak_05 | 混沌之气 | epic | -10~+15 | 吸收 vs 炼化 |
| peak_06 | 破碎虚空 | rare | -20~+20 | 进入 vs 修补 |
| peak_07 | 上古战场 | common | -10~+15 | 搜魂 vs 超度 |
| peak_08 | 大道之音 | rare | 0~+25 | 聆听 vs 记录 |
| peak_09 | 灵山宝刹 | epic | +15~+30 | 参佛 vs 取宝 |
| peak_10 | 仙器碎片 | legendary | -30~+50 | 争夺 vs 放弃（得善因）|

#### 大乘期（level_index 37-45，8 事件）

| ID | 名称 | 稀有度 | 因果范围 | 说明 |
|----|------|--------|----------|------|
| trans_01 | 天道考验 | legendary | -50~+50 | 顺应天道 vs 逆天而行 vs 保持本心 |
| trans_02 | 飞升之谜 | epic | 0~+30 | 参悟 vs 传播 |
| trans_03 | 上古封印 | rare | +20~-20 | 加固 vs 解开 |
| trans_04 | 因果追溯 | epic | +30~0 | 追溯前世 vs 斩断因果 |
| trans_05 | 鸿蒙紫气 | legendary | -30~+40 | 收取 vs 守护 |
| trans_06 | 万法归宗 | rare | 0~+15 | 参悟所有 vs 专精一道 |
| trans_07 | 天地大劫 | epic | +30~-30 | 救世 vs 独善 |
| trans_08 | 道果成熟 | rare | +10~+20 | 采摘 vs 分享 |

#### 轮回期（level_index 46+，8 事件）

| ID | 名称 | 稀有度 | 因果范围 | 说明 |
|----|------|--------|----------|------|
| reinc_01 | 前世记忆 | epic | +20~-20 | 追寻 vs 斩断 vs 静观 |
| reinc_02 | 轮回之河 | legendary | +50~-30 | 渡河 vs 修桥 |
| reinc_03 | 因果循环 | rare | +25~-15 | 偿还 vs 讨债 |
| reinc_04 | 业火红莲 | epic | -40~+20 | 渡过 vs 吸收 |
| reinc_05 | 轮回印记 | rare | +10~+30 | 解锁 vs 强化 |
| reinc_06 | 前世因果 | legendary | +40~-50 | 和解 vs 了断 vs 延续 |
| reinc_07 | 轮回之力 | epic | -20~+35 | 借力突破 vs 稳固根基 |
| reinc_08 | 超脱轮回 | legendary | 0~+60 | 寻求超脱之法 vs 守护轮回 |

---

## 4. 善恶因果系统

### 4.1 因果值范围

范围: [-1000, +1000]，初始值 0。

### 4.2 因果称号与效果

| 区间 | 称号 | 战斗效果 | 修炼效果 | 事件偏移 |
|------|------|----------|----------|----------|
| -1000 ~ -500 | 魔道修士 | 攻击力 +8% | — | 高风险事件权重 +25% |
| -499 ~ -100 | 偏邪 | 攻击力 +4% | — | — |
| -99 ~ +99 | 中立 | — | — | — |
| +100 ~ +499 | 偏正 | — | 修炼速度 +4% | — |
| +500 ~ +1000 | 正道修士 | — | 修炼速度 +8% | 正面事件权重 +25% |

### 4.3 因果值获取

| 行为 | 因果变化 | 示例 |
|------|----------|------|
| 强行夺取 | -5 ~ -30 | "强行采摘"选项失败 |
| 见死不救 | -3 ~ -10 | 中性选择中的隐性惩罚 |
| 出手相助 | +3 ~ +15 | 正面选择 |
| 放弃利益救人 | +10 ~ +30 | 牺牲型正面选择 |
| 以灵石解围 | +3 ~ +10 | 消耗资源的正面选择 |
| 中立选择 | 0 | 安全但无因果变化 |

### 4.4 因果值衰减

- 每天自然衰减 **2 点**（向 0 靠拢）
- 衰减在 **每日签到** 时处理（在 `handle_check_in` 末尾调用 `encounter_mgr.apply_karma_decay(player)`）
- 防止极端值永久锁定

### 4.5 因果与轮回联动

- 因果值存储在 Player 模型的 `karma` 字段
- 轮回时因果值 **不重置** — "前世之因，后世之果"
- 因果值影响轮回专属事件的出现概率
- 轮回次数解锁专属奇遇事件：
  - 1 次轮回解锁：前世记忆系列事件 (reinc_01, reinc_03)
  - 5 次轮回解锁：天道轮回系列事件 (reinc_02, reinc_05)
  - 10 次轮回解锁：因果终章系列事件 (reinc_04, reinc_06)

### 4.6 因果对战斗的影响

在 `combat_manager.py` 的 `build_player_combat_stats()` 第 234 行附近注入：

```python
# build_player_combat_stats 第 234 行附近
final_atk = int(base_atk * atk_practice_mult * (1 + technique_atk_bonus) * (1 + equip_bonus["atk_pct"]) * (1 + equip_bonus.get("armor_atk_pct", 0.0))) + int(atk_buff) + flat_atk_bonus

# ── 因果值攻击加成（新增）──
karma = getattr(player, 'karma', 0) or 0
karma_atk_bonus = 0.0
if karma <= -500:
    karma_atk_bonus = 0.08   # 魔道修士 +8% 攻击
elif karma <= -100:
    karma_atk_bonus = 0.04   # 偏邪 +4% 攻击
if karma_atk_bonus > 0:
    final_atk = int(final_atk * (1 + karma_atk_bonus))
```

### 4.7 因果对修炼的影响

在 `cultivation_manager.py` 的 `calculate_cultivation_exp_with_segments()` 第 371 行注入：

```python
# 第 371 行原公式
other_multiplier = root_speed * (1.0 + technique_bonus) * (1.0 + closing_exp_bonus) * (1.0 + land_bonus) * (1.0 + permanent_cultivation_mult)

# ── 因果值修炼加成（新增）──
karma = getattr(player, 'karma', 0) or 0
karma_cultivation_bonus = 0.0
if karma >= 500:
    karma_cultivation_bonus = 0.08   # 正道修士 +8% 修炼速度
elif karma >= 100:
    karma_cultivation_bonus = 0.04   # 偏正 +4%

other_multiplier = root_speed * (1.0 + technique_bonus) * (1.0 + closing_exp_bonus) * (1.0 + land_bonus) * (1.0 + permanent_cultivation_mult) * (1.0 + karma_cultivation_bonus)
```

---

## 5. 交互设计

### 5.1 奇遇触发消息格式

```
🌀 【奇遇·山涧灵草】(普通)
━━━━━━━━━━━━━━━━━━━━
你在山涧修炼时，发现一株散发微光的灵草。
旁边有一头低阶妖兽正在打盹。
━━━━━━━━━━━━━━━━━━━━
请选择（输入 /奇遇 A/B/C）：
A. 强行采摘（风险：30%，因果：-5）
B. 悄悄绕过（风险：无，因果：0）
C. 用灵石引开妖兽（风险：10%，因果：+3，消耗：500灵石）
━━━━━━━━━━━━━━━━━━━━
⏰ 180秒内选择，超时视为放弃。
💡 使用 /奇遇 A 回复
```

### 5.2 选择结果消息格式

**成功时**:
```
✨ 你选择了【强行采摘】
━━━━━━━━━━━━━━━━━━━━
你趁妖兽不备，迅速采摘了灵草！
📦 获得：灵石 ×1,234 | 修为 +3,000 | 灵草精华 ×1
☯️ 因果：-5（当前：-15 | 中立）
```

**失败时**:
```
💀 你选择了【强行采摘】
━━━━━━━━━━━━━━━━━━━━
妖兽被惊醒，你不得不狼狈逃窜，受了些轻伤。
💔 损失：20% 生命值
☯️ 因果：-5（当前：-15 | 中立）
```

**超时时**:
```
⏰ 奇遇超时
━━━━━━━━━━━━━━━━━━━━
你犹豫不决，机会已逝。灵草和妖兽都消失在了山涧深处。
（无惩罚，不消耗今日次数）
```

### 5.3 传说级奇遇广播格式

```
🌟 天降机缘！🌟
━━━━━━━━━━━━━━━━━━━━
某位修士在修炼途中触发了【天道考验】！
天地灵气波动，所有人都感受到了一丝异象...
━━━━━━━━━━━━━━━━━━━━
```

### 5.4 选择超时后的重试

如果玩家在超时后（pending 已过期）输入 `/奇遇 A`，返回：
```
⏰ 此奇遇已超时失效。
机缘已逝，期待下次相遇。
```

### 5.5 因果称号查看

`/奇遇信息` 命令展示：
```
☯️ 因果值：-15（中立）
━━━━━━━━━━━━━━━━━
今日奇遇：0/3 次
上期奇遇：山涧灵草 → 强行采摘（成功）
━━━━━━━━━━━━━━━━━
💡 因果值影响战斗力和修炼速度
```

---

## 6. 系统联动

### 6.1 与每日活跃联动

新增每日任务配置（`TASK_DEFINITIONS`）：
```python
"encounter": ("触发奇遇", 15, 1),  # 1次即可完成，15积分
```

更新 `TASK_ORDER`：
```python
TASK_ORDER = ["check_in", "rift", "bounty", "harvest", "alchemy", "smelt", "interest", "sect", "encounter"]
```

新增 track hook：
```python
# 在 ActivityTracker 中新增
async def track_encounter(self, player: Player):
    """奇遇触发时调用"""
    today = datetime.now().strftime("%Y-%m-%d")
    self._reset_if_new_day(player, today)
    await self._add_progress(player, "encounter")
```

### 6.2 与成就系统联动

新增成就条件类型（`achievement_manager.py` 的 `_check_condition` 新增分支）：

```python
elif cond_type == "encounter_count":
    # 从 encounter_history 统计总次数
    history = json.loads(getattr(player, 'encounter_history', '[]'))
    return len(history) >= value
elif cond_type == "karma":
    karma = getattr(player, 'karma', 0) or 0
    if condition.get("direction") == "positive":
        return karma >= value
    elif condition.get("direction") == "negative":
        return karma <= -value
    return abs(karma) >= value
```

新增成就：

| 成就名 | 条件类型 | 条件值 | 奖励 |
|--------|----------|--------|------|
| 初遇机缘 | `encounter_count` | 1 | 经验 ×5,000 |
| 奇遇连连 | `encounter_count` | 20 | 经验 ×20,000 |
| 命运之子 | `encounter_count` | 50 | 经验 ×50,000 |
| 魔道修士 | `karma` (negative) | 500 | 攻击力永久 +50 |
| 正道修士 | `karma` (positive) | 500 | 修炼速度永久 +2% |

### 6.3 与轮回系统联动

预留联动接口，在轮回时保留 `karma` 字段。当轮回系统（`docs/superpowers/specs/2026-07-06-reincarnation-system-design-v2.md`）实现后：

- 因果值在所有轮回中跨世保留
- 轮回次数（从 `reincarnation_data` 表读取）解锁专属奇遇事件池
- 在 `EncounterManager` 中的事件选择逻辑中，根据轮回次数筛选事件

### 6.4 与广播系统联动

传说级奇遇触发时，在 `main.py` 中调用 `_broadcast_to_whitelist_groups()`：

```python
# 在 yield 奇遇消息之前
if encounter.get("rarity") == "legendary":
    broadcast_msg = (
        f"🌟 天降机缘！🌟\n"
        f"━━━━━━━━━━━━━━━\n"
        f"某位修士触发【{encounter['name']}】！\n"
        f"天地灵气波动..."
    )
    await self._broadcast_to_whitelist_groups(broadcast_msg)
```

### 6.5 与储物戒/丹药背包联动

- 物品奖励 → 调用 `self.storage_ring_mgr.add_item(player, item_name, count, event)` 存入 `storage_ring_items`
- 丹药奖励 → 调用 `pill_manager.add_pill(player, pill_name, count)` 存入 `pills_inventory`
- 灵石奖励 → 直接加到 `player.gold`
- 修为奖励 → 直接加到 `player.experience`
- 生命惩罚 → 设置 `player.hp = max(0, int(player.hp * (1 - hp_pct)))`

### 6.6 与 BUSY_STATE_ALLOWED_COMMANDS 联动

在 `handlers/utils.py` 的 `BUSY_STATE_ALLOWED_COMMANDS` 白名单中新增：

```python
# 奇遇系统（忙碌状态下可选择）
"奇遇",
"奇遇信息",
"奇遇记录",
```

---

## 7. 数据模型

### 7.1 Player 模型新增字段

在 `models.py` 的 `Player` dataclass 中新增（第 169 行附近，`bank_vip_tier` 和 `sleeping_bag_level` 之后）：

```python
# 奇遇/因果系统字段
karma: int = 0                      # 因果值 [-1000, +1000]
last_encounter_date: str = ""       # 上次奇遇触发日期 (YYYY-MM-DD)
daily_encounter_count: int = 0      # 今日奇遇触发次数
encounter_history: str = "[]"       # JSON: 最近10次奇遇记录
```

### 7.2 数据库迁移

新增 migration v41（`data/migration.py`）：

```python
@migration(41)
async def v41_add_encounter_system(conn: aiosqlite.Connection, config_manager: ConfigManager):
    """v41: 奇遇机缘系统 & 善恶因果系统"""
    await conn.execute("ALTER TABLE players ADD COLUMN karma INTEGER DEFAULT 0")
    await conn.execute("ALTER TABLE players ADD COLUMN last_encounter_date TEXT DEFAULT ''")
    await conn.execute("ALTER TABLE players ADD COLUMN daily_encounter_count INTEGER DEFAULT 0")
    await conn.execute("ALTER TABLE players ADD COLUMN encounter_history TEXT DEFAULT '[]'")
```

同时更新 `LATEST_DB_VERSION = 41`。

### 7.3 encounter_history JSON 结构

```json
[
    {
        "id": "mountain_herb_01",
        "name": "山涧灵草",
        "choice": "a",
        "roll": "success",
        "karma_delta": -5,
        "rarity": "common",
        "timestamp": 1718800000
    }
]
```

历史记录最多保留最近 **20 条**（写入时裁剪）。

### 7.4 ConfigManager 扩展

在 `config_manager.py` 的 `_load_all()` 中末尾加载：

```python
# 奇遇系统配置
self.encounter_config = self._load_config_with_default(config_dir / "encounter_config.json", ENCOUNTER_CONFIG_DEFAULT)
self.encounters = self.encounter_config.get("encounters", [])
self.encounter_trigger_chances = self.encounter_config.get("trigger_chances", {})
self.encounter_settings = self.encounter_config.get("settings", {})
self.karma_settings = self.encounter_config.get("karma_settings", {})
```

需要添加 `ENCOUNTER_CONFIG_DEFAULT` 默认配置到 `data/default_configs.py`。

### 7.5 update_player 扩展

在 `data/data_manager.py` 的 `update_player()` SQL UPDATE 语句中末尾新增字段（第 219 行 `forging_level = ?` 之后）：

```python
karma = ?,
last_encounter_date = ?,
daily_encounter_count = ?,
encounter_history = ?,
```

并在 VALUES 元组中对应增加参数。

---

## 8. 代码修改清单

### 8.1 新增文件

| 文件 | 说明 |
|------|------|
| `managers/encounter_manager.py` | 奇遇系统核心逻辑（~300 行） |
| `handlers/encounter_handler.py` | 奇遇选择/信息处理（~100 行） |
| `config/encounter_config.json` | 奇遇事件池 + 设置配置（60+ 事件） |
| `tests/test_encounter_manager.py` | 奇遇系统测试 |

### 8.2 修改文件

| 文件 | 修改内容 |
|------|----------|
| `data/migration.py` | `LATEST_DB_VERSION = 41` + `v41_add_encounter_system` 迁移 |
| `data/data_manager.py` | `update_player()` SQL 新增 4 个字段 |
| `models.py` | Player 新增 4 个字段（`karma`, `last_encounter_date`, `daily_encounter_count`, `encounter_history`） |
| `config_manager.py` | `_load_all()` 中加载 `encounter_config.json` |
| `data/default_configs.py` | 新增 `ENCOUNTER_CONFIG_DEFAULT` 默认配置字典 |
| `handlers/__init__.py` | 导出 `EncounterHandler` |
| `handlers/utils.py` | `BUSY_STATE_ALLOWED_COMMANDS` 加入奇遇相关命令 |
| `main.py` | 初始化 `EncounterManager` + `EncounterHandler`，注册 3 个命令，5 处触发钩子，传说级广播调用 |
| `managers/activity_manager.py` | `TASK_DEFINITIONS` + `TASK_ORDER` + `track_encounter()` |
| `managers/achievement_manager.py` | `_check_condition` 新增 `encounter_count` 和 `karma` 类型 |
| `managers/combat_manager.py` | `build_player_combat_stats()` 新增 karma 攻击加成 |
| `core/cultivation_manager.py` | `calculate_cultivation_exp_with_segments()` 新增 karma 修炼加成 |
| `handlers/misc_handler.py` | 帮助文本新增奇遇指令 |

### 8.3 数据流

```
玩家执行操作（签到/出关/秘境/悬赏/Boss/探险）
    │
    ├─ handler 正常处理操作，yield 主操作结果
    │
    ├─ handler 调用 encounter_mgr.try_trigger(player, action_type)
    │   ├─ 检查每日限制（daily_encounter_count < 3）
    │   ├─ 检查概率（config trigger_chances）
    │   ├─ 检查是否有 pending（避免重叠）
    │   ├─ 加权随机选择事件（含因果偏移）
    │   ├─ 更新 daily_encounter_count
    │   ├─ 存储 pending（内存 dict，180s 超时）
    │   ├─ 活跃度追踪 track_encounter()
    │   └─ 返回 encounter dict 或 None
    │
    ├─ 如果触发：
    │   ├─ 传说级 → broadcast_to_whitelist_groups()
    │   └─ yield 奇遇文本 + 选项
    │
    └─ 玩家在 180s 内回复 /奇遇 A/B/C
        └─ encounter_mgr.resolve(player, user_id, choice_id)
            ├─ 检查 pending 存在且未超时
            ├─ 判定成功/失败（random.random() < risk）
            ├─ 发放奖励/惩罚
            │   ├─ gold → player.gold
            │   ├─ exp → player.experience
            │   ├─ item → storage_ring_mgr.add_item()
            │   ├─ pill → pill_manager.add_pill()
            │   └─ hp_pct → player.hp
            ├─ 更新 karma（钳制到 [-1000, 1000]）
            ├─ 写入 encounter_history（保留最近20条）
            ├─ 清理 pending
            └─ 返回 结果消息
```

---

## 9. 指令清单

| 指令 | 说明 | 参数 | 繁忙状态可用 |
|------|------|------|-------------|
| `/奇遇 A/B/C` | 回复当前奇遇的选择 | 选项ID（A/B/C） | **是** |
| `/奇遇信息` | 查看因果值、今日次数、因果称号 | — | **是** |
| `/奇遇记录` | 查看最近奇遇历史 | — | **是** |

注：奇遇本身不需要指令触发（被动触发），以上为回复和信息查看指令。

### 9.1 main.py 命令注册

```python
# 奇遇系统指令（命令定义）
CMD_ENCOUNTER_CHOOSE = "奇遇"
CMD_ENCOUNTER_INFO = "奇遇信息"
CMD_ENCOUNTER_HISTORY = "奇遇记录"

# 命令注册
@filter.command(CMD_ENCOUNTER_CHOOSE, "回复当前奇遇选择")
@require_whitelist
async def handle_encounter_choose(self, event: AstrMessageEvent, choice: str = ""):
    async for r in self.encounter_handler.handle_choose(event, choice):
        yield r

@filter.command(CMD_ENCOUNTER_INFO, "查看因果值和奇遇信息")
@require_whitelist
async def handle_encounter_info(self, event: AstrMessageEvent):
    async for r in self.encounter_handler.handle_info(event):
        yield r

@filter.command(CMD_ENCOUNTER_HISTORY, "查看奇遇历史记录")
@require_whitelist
async def handle_encounter_history(self, event: AstrMessageEvent):
    async for r in self.encounter_handler.handle_history(event):
        yield r
```

### 9.2 main.py 初始化

```python
# 在 __init__ 方法末尾（第 337 行附近）
from .managers.encounter_manager import EncounterManager
self.encounter_mgr = EncounterManager(self.db, self.config_manager, self.storage_ring_mgr, self.activity_tracker)
self.encounter_handler = EncounterHandler(self.db, self.encounter_mgr)
```

### 9.3 handlers/__init__.py 导出

```python
from .encounter_handler import EncounterHandler
# 加入 __all__
"EncounterHandler",
```

### 9.4 触发钩子实现范例

```python
# ===== 签到后触发奇遇（main.py handle_check_in 末尾）=====
@filter.command(CMD_CHECK_IN, "每日签到领取灵石")
@require_whitelist
async def handle_check_in(self, event: AstrMessageEvent):
    async for r in self.player_handler.handle_check_in(event):
        yield r
    # 签到后尝试触发奇遇
    player = await self.db.get_player_by_id(event.get_sender_id())
    if player:
        msg = await self.encounter_mgr.try_trigger(player, "check_in")
        if msg:
            yield event.plain_result(msg)
```

---

## 10. EncounterManager 核心实现

### 10.1 类结构

`managers/encounter_manager.py`:

```python
class EncounterManager:
    """奇遇机缘系统核心管理器"""

    def __init__(self, db: DataBase, config_manager: ConfigManager, storage_ring_mgr, activity_tracker=None):
        self.db = db
        self.config_manager = config_manager
        self.storage_ring_mgr = storage_ring_mgr
        self.activity_tracker = activity_tracker
        self._pending: Dict[str, dict] = {}  # user_id → pending encounter
        
        # 从配置读取
        self.encounters = config_manager.encounters  # 事件列表
        self.trigger_chances = config_manager.encounter_trigger_chances
        self.settings = config_manager.encounter_settings

    async def try_trigger(self, player: Player, action_type: str) -> Optional[str]:
        """尝试触发奇遇，成功返回奇遇描述文本，失败返回 None"""
        # 1. 检查每日限制
        today = datetime.now().strftime("%Y-%m-%d")
        self._reset_daily_if_new_day(player, today)
        if player.daily_encounter_count >= self.settings.get("daily_limit", 3):
            return None

        # 2. 检查重叠 pending
        if player.user_id in self._pending:
            # 检查是否超时
            pending = self._pending[player.user_id]
            if time.time() - pending["timestamp"] <= self.settings.get("choice_timeout_seconds", 180):
                return None  # 还有未回复的奇遇
            else:
                del self._pending[player.user_id]

        # 3. 概率检定
        trigger_pct = self.trigger_chances.get(action_type, 0.15)
        if random.random() >= trigger_pct:
            return None

        # 4. 选择事件
        encounter = self._select_encounter(player)
        if not encounter:
            return None

        # 5. 更新计数
        player.daily_encounter_count += 1
        player.last_encounter_date = today
        await self.db.update_player(player)

        # 6. 存储 pending
        self._pending[player.user_id] = {
            "encounter": encounter,
            "timestamp": time.time()
        }

        # 7. 活跃度追踪
        if self.activity_tracker:
            try:
                await self.activity_tracker.track_encounter(player)
            except Exception:
                pass

        # 8. 构建显示文本
        return self._build_encounter_message(encounter)

    def _select_encounter(self, player: Player) -> Optional[dict]:
        """根据玩家境界、因果值加权选择事件"""
        # 筛选可用事件
        candidates = [
            e for e in self.encounters
            if e.get("min_level", 0) <= player.level_index <= e.get("max_level", 999)
        ]
        if not candidates:
            return None

        # 稀有度分层选择
        rarity_roll = random.random()
        rarity_order = [
            ("legendary", 0.04),
            ("epic", 0.14),
            ("rare", 0.27),
            ("common", 0.55),
        ]
        # 累积概率分配
        cumulative = 0.0
        selected_rarity = "common"
        for rarity, prob in rarity_order:
            cumulative += prob
            if rarity_roll < cumulative:
                selected_rarity = rarity
                break

        # 按稀有度 + 权重筛选
        pool = [
            e for e in candidates
            if e.get("rarity", "common") == selected_rarity
        ]
        if not pool:
            pool = candidates  # fallback

        # 因果值权重偏移
        karma = player.karma
        bias_threshold = self.settings.get("karma_event_bias_threshold", 500)
        bias_pct = self.settings.get("karma_event_bias_pct", 25) / 100

        weights = []
        for e in pool:
            w = e.get("weight", 100)
            # 高因果值：正面事件权重增加
            if karma >= bias_threshold:
                if self._is_positive_encounter(e):
                    w = int(w * (1 + bias_pct))
            # 低因果值：高风险事件权重增加
            elif karma <= -bias_threshold:
                if any(c.get("karma_delta", 0) <= -5 for c in e.get("choices", [])):
                    w = int(w * (1 + bias_pct))
            weights.append(w)

        return random.choices(pool, weights=weights, k=1)[0]

    async def resolve(self, player: Player, user_id: str, choice_id: str) -> str:
        """处理玩家选择，返回结果消息"""
        # 1. 检查 pending
        pending = self._pending.pop(user_id, None)
        if not pending:
            return "⏰ 你当前没有待回复的奇遇。"

        encounter = pending["encounter"]
        elapsed = time.time() - pending["timestamp"]
        timeout = self.settings.get("choice_timeout_seconds", 180)
        if elapsed > timeout:
            # 超时，不消耗次数（回退 daily_encounter_count）
            player.daily_encounter_count = max(0, player.daily_encounter_count - 1)
            await self.db.update_player(player)
            return f"⏰ 奇遇超时\n━━━━━━━━━━━━━━━\n你犹豫不决，机会已逝。\n（无惩罚，不消耗今日次数）"

        # 2. 查找选择
        choice = None
        for c in encounter.get("choices", []):
            if c["id"] == choice_id.lower():
                choice = c
                break
        if not choice:
            self._pending[user_id] = pending  # 放回
            return f"无效的选择「{choice_id}」。请使用 /奇遇 A/B/C 回复。"

        # 3. 检查消耗
        cost = choice.get("cost", {})
        if cost.get("gold", 0) > player.gold:
            # 灵石不够，放回 pending
            self._pending[user_id] = pending
            return f"灵石不足！需要 {cost['gold']} 灵石，你只有 {player.gold} 灵石。"

        # 4. 扣除消耗
        if cost.get("gold", 0):
            player.gold -= cost["gold"]

        # 5. 判定成功/失败
        risk = choice.get("risk", 0)
        is_success = random.random() >= risk

        # 6. 更新 karma
        karma_delta = choice.get("karma_delta", 0)
        if is_success:
            player.karma = max(-1000, min(1000, player.karma + karma_delta))
        else:
            player.karma = max(-1000, min(1000, player.karma - abs(karma_delta)))

        # 7. 发放奖励/惩罚
        if is_success:
            rewards = choice.get("success_rewards", {})
            await self._apply_rewards(player, rewards)
        else:
            penalty = choice.get("fail_penalty", {})
            await self._apply_penalty(player, penalty)

        # 8. 写入 history
        await self._update_history(player, encounter, choice_id, "success" if is_success else "fail", karma_delta if is_success else -abs(karma_delta))

        await self.db.update_player(player)

        # 9. 构建结果文本
        karma_title = self._get_karma_title(player.karma)
        if is_success:
            text = choice.get("success_text", "你做出了选择。")
            reward_summary = self._build_reward_summary(rewards)
            return (
                f"✨ 你选择了【{choice['text']}】\n"
                f"━━━━━━━━━━━━━━━\n"
                f"{text}\n"
                f"{reward_summary}"
                f"☯️ 因果：{karma_delta:+d}（当前：{player.karma} | {karma_title}）"
            )
        else:
            text = choice.get("fail_text", "事情并没有如你预期的发展。")
            penalty_summary = self._build_penalty_summary(penalty)
            return (
                f"💀 你选择了【{choice['text']}】\n"
                f"━━━━━━━━━━━━━━━\n"
                f"{text}\n"
                f"{penalty_summary}"
                f"☯️ 因果：{-abs(karma_delta):+d}（当前：{player.karma} | {karma_title}）"
            )

    # 辅助方法：_apply_rewards, _apply_penalty, _update_history, 
    #            _build_encounter_message, _get_karma_title 等
```

### 10.2 奖励/惩罚发放实现

```python
async def _apply_rewards(self, player: Player, rewards: dict):
    """发放奖励"""
    # 灵石
    gold_range = rewards.get("gold", [0, 0])
    if gold_range[1] > 0:
        gold = random.randint(gold_range[0], gold_range[1])
        player.gold += gold

    # 修为
    exp_range = rewards.get("exp", [0, 0])
    if exp_range[1] > 0:
        exp = random.randint(exp_range[0], exp_range[1])
        player.experience += exp

    # 物品
    item_chance = rewards.get("item_chance", 0)
    item_pool = rewards.get("item_pool", [])
    if item_pool and random.random() < item_chance:
        item_name = random.choice(item_pool)
        # 通过 storage_ring_mgr 存入
        # TODO: 调用 storage_ring_mgr.add_item(player, item_name, 1)

    # 丹药
    pill_chance = rewards.get("pill_chance", 0)
    pill_pool = rewards.get("pill_pool", [])
    if pill_pool and random.random() < pill_chance:
        pill_name = random.choice(pill_pool)
        # TODO: 调用 pill_manager.add_pill(player, pill_name, 1)

async def _apply_penalty(self, player: Player, penalty: dict):
    """应用惩罚"""
    hp_pct = penalty.get("hp_pct", 0)
    if hp_pct > 0:
        player.hp = max(0, int(player.hp * (1 - hp_pct)))

    # 未来可扩展：灵石损失、buff/debuff 等
```

---

## 11. EncounterHandler 实现

### 11.1 类结构

`handlers/encounter_handler.py`:

```python
class EncounterHandler:
    """奇遇系统命令处理器"""

    def __init__(self, db: DataBase, encounter_mgr):
        self.db = db
        self.encounter_mgr = encounter_mgr

    async def handle_choose(self, event: AstrMessageEvent, choice: str = ""):
        """处理 /奇遇 A/B/C 选择回复"""
        user_id = event.get_sender_id()
        player = await self.db.get_player_by_id(user_id)
        if not player:
            yield event.plain_result("❌ 你还未踏入修仙之路！")
            return

        if not choice or choice.strip().upper() not in ("A", "B", "C"):
            yield event.plain_result("请使用 /奇遇 A/B/C 回复当前奇遇。")
            return

        result = await self.encounter_mgr.resolve(player, user_id, choice.strip().lower())
        yield event.plain_result(result)

    async def handle_info(self, event: AstrMessageEvent):
        """查看奇遇信息（因果值 + 今日次数）"""
        user_id = event.get_sender_id()
        player = await self.db.get_player_by_id(user_id)
        if not player:
            yield event.plain_result("❌ 你还未踏入修仙之路！")
            return

        karma_title = self.encounter_mgr._get_karma_title(player.karma)
        msg = (
            f"☯️ 因果值：{player.karma}/1000（{karma_title}）\n"
            f"━━━━━━━━━━━━━━━\n"
            f"今日奇遇：{player.daily_encounter_count}/3 次\n"
        )
        yield event.plain_result(msg)

    async def handle_history(self, event: AstrMessageEvent):
        """查看奇遇历史记录"""
        user_id = event.get_sender_id()
        player = await self.db.get_player_by_id(user_id)
        if not player:
            yield event.plain_result("❌ 你还未踏入修仙之路！")
            return

        history = self.encounter_mgr._get_history(player)
        if not history:
            yield event.plain_result("你还没有经历过任何奇遇。")
            return

        lines = ["📜 奇遇记录（最近20条）", "━━━━━━━━━━━━━━━"]
        for h in reversed(history[-10:]):  # 显示最近10条
            lines.append(
                f"【{h.get('name', '未知')}】→ "
                f"{'成功' if h.get('roll') == 'success' else '失败'} "
                f"（因果{h.get('karma_delta', 0):+d}）"
            )
        yield event.plain_result("\n".join(lines))
```

---

## 12. 数值平衡

### 12.0 全插件灵石经济现状分析

#### 12.0.1 各模块灵石产出总览

| 系统 | 文件/公式 | 量级 | 境界缩放 | 频率/日 | 稳定性 |
|------|----------|------|----------|---------|--------|
| **签到** | `handlers/player_handler.py:481` 固定值 | **500,000** | ❌ 固定 | 1次 | ✅ 保底 |
| **签到里程碑(7天)** | `handlers/player_handler.py:537` | 5,000,000 | ❌ 固定 | 每7天 | ⚠️ 一次性 |
| **Boss战** | `managers/boss_manager.py:145` `stone_reward=int(base_exp*reward_mult//10)` | 17万~**200万+** | ✅ `avg_exp×1.2×reward_mult(1.4~16.8)` | 不限(1h刷新) | ⚠️ 全服均修 |
| **秘境** | `data/default_configs.py:80-89` + `rift_manager.py:298` (50%概率) | 40万~**1,360万** | ✅ `level_bonus=1+max(0,level-3)×0.045` (0→0.865, 57→3.43) | 1次 | ✅ 硬上限 |
| **悬赏令** | `bounty_manager.py:227-240` `_calculate_reward` | 1万~**50万+** | ✅ `level_bonus×stone_scale×progress_factor` | 3次 | ✅ 硬上限 |
| **探险副本** | `dungeon_config.json` 战斗节点: `(50+depth×20)×bonus`, 矿脉: `200+depth×50`, 宝箱: `100+depth×30` | 5,000~10,000(每日上限) | ✅ depth_tier(×1.0~3.0) | 1次 | ✅ 每日上限 |
| **炼金(卖物品)** | `storage_ring_handler.py:631` `unit_gold=price×0.7` | 不定 | ❌ 物品价格 | 不限 | ⚠️ 看库存 |
| **银行利息** | `bank_manager.py:12` `日利率0.1%~0.4%` | 余额×利率 | ❌ 取决存款 | 1次 | ✅ 被动 |
| **金银阁** | `gambling_handler.py` 公平赌局 | 期望=0 | — | 不限 | — |

#### 12.0.2 境界缩放系数（所有模块通用）

```
game_config.level_scaling.bounty_rift_coefficient = 0.045
level_bonus = 1 + max(0, level_index - 3) × 0.045
```

| level_index | 境界名称 | level_bonus |
|:----------:|---------|:-----------:|
| 0 | 江湖好手 | 0.865 |
| 10 | 筑基境 | 1.315 |
| 20 | 紫府/凝婴 | 1.765 |
| 30 | 化神境 | 2.215 |
| 40 | 合体境 | 2.665 |
| 50 | 渡劫境 | 3.115 |
| 57 | 合道圆满 | 3.430 |

#### 12.0.3 各境界段日均灵石收入估算（典型活跃玩家）

| 境界段 | 签到 | Boss | 秘境(50%) | 悬赏(3次) | 探险 | **日均合计** |
|--------|------|------|-----------|-----------|------|:----------:|
| 凡人(0-9) | 500,000 | —(难打过) | —(不够格) | 1,000~5,000 | ~3,000 | **~504,000~508,000** |
| 筑基(10-18) | 500,000 | ~20万 | ~52万 | 5,000~3万 | ~5,000 | **~73万~106万** |
| 元婴(19-27) | 500,000 | ~50万 | ~115万 | 3万~10万 | ~8,000 | **~104万~176万** |
| 化神(28-36) | 500,000 | ~100万 | ~200万 | 10万~30万 | ~10,000 | **~161万~281万** |
| 大乘+(37-57) | 500,000 | ~200万+ | ~400万+ | 30万~100万 | ~10,000 | **~284万~551万+** |

> **核心发现:** 签到调整后（固定50万/天），低境界玩家有了保底收入，签到占比从~0.05%升至50%+。

#### 12.0.4 灵石消耗端参考

| 消耗项目 | 量级 |
|---------|------|
| 创建宗门 | 10,000 |
| 重铸灵根 | 250,000 |
| 洞天购买 | 10,000~1,000,000 |
| 洞天升级 | 价格×等级×0.5（递增） |
| VIP升级 | 50万(初级→中级) ~ 5,000万(顶级→至尊) |
| 宗门捐献 | 1:10建设度（不限量） |
| 灵田开垦/扩展 | 递增消耗 |

### 12.0.5 奇遇系统灵石设计原则

1. **奇遇是额外收入，远低于主要活动** — 被动触发、不消耗体力/次数，单次应远少于秘境/Boss
2. **复用现有缩放体系** — `bounty_rift_coefficient = 0.045`
3. **稀有度多层** — 普通/稀有/史诗/传说对应不同量级
4. **风险-回报正比** — 高风险选项应是安全选项的 3-5x
5. **不冲击现有经济** — 奇遇日期望值控制在日均总收入的 1-3%

#### 12.0.6 奇遇灵石公式

```
encounter_gold = base_gold × level_bonus × rarity_mult × risk_mult
```

| 参数 | 取值 |
|------|------|
| `base_gold` | 按境界层级设定（见下表） |
| `level_bonus` | `1 + max(0, level_index - 3) × 0.045` |
| `rarity_mult` | common×1.0, rare×2.5, epic×6.0, legendary×15.0 |
| `risk_mult` | 安全×1.0, 风险×2.0~3.0, 高风×3.0~5.0 |

#### 12.0.7 基础灵石表（以事件配置中的 `gold: [min, max]` 为准）

| 境界层级 | base_gold | 安全选项(×1.0) | 风险选项成功(×3.0) | 高风险成功(×5.0) |
|---------|:---------:|:--------------:|:-----------------:|:----------------:|
| 凡人(0-9) | 200 | 100~300 | 500~2,000 | — |
| 筑基(10-18) | 800 | 400~1,200 | 2,000~8,000 | 5,000~15,000 |
| 元婴(19-27) | 3,000 | 1,500~4,500 | 7,500~30,000 | 18,000~60,000 |
| 化神(28-36) | 15,000 | 7,500~22,500 | 37,500~150,000 | 90,000~300,000 |
| 大乘(37-45) | 60,000 | 30,000~90,000 | 150,000~600,000 | 360,000~1,200,000 |
| 轮回(46+) | 250,000 | 125,000~375,000 | 625,000~2,500,000 | 1,500,000~5,000,000 |

#### 12.0.8 不同稀有度的实际期望值（以元婴期 level=20 为例）

| 稀有度 | 概率 | 倍率 | level_bonus | 最终期望 |
|--------|:---:|:----:|:-----------:|:--------:|
| 普通(公共) | 55% | ×1.0 | 1.765 | ~5,300 |
| 稀有(罕见) | 27% | ×2.5 | 1.765 | ~13,200 |
| 史诗(史诗) | 14% | ×6.0 | 1.765 | ~31,800 |
| 传说(传说) | 4% | ×15.0 | 1.765 | ~79,500 |

**传说级奇遇奖励 ≈ 单次悬赏奖励（低境界）或半次Boss奖励（高境界）**，价值感足够，不破坏经济。

#### 12.0.9 奇遇收入占日均总收入的占比验证

| 境界段 | 日均总收入 | 奇遇期望/次(普通) | 3次触发后总占比 | 安全性 |
|-------|:---------:|:-----------------:|:--------------:|:------:|
| 凡人 | ~506,000 | ~175 | **~0.1%** | ✅ 微乎其微 |
| 筑基 | ~90万 | ~1,050 | **~0.4%** | ✅ 可忽略 |
| 元婴 | ~140万 | ~5,300 | **~1.1%** | ✅ 额外彩蛋 |
| 化神 | ~220万 | ~33,200 | **~4.5%** | ✅ 仍远低于Boss |
| 大乘+ | ~420万 | ~206,000 | **~14.7%** | ⚠️ 签到保底后比例下降 |

> **经济安全结论:** 调整签到后奇遇占比进一步降低（因签到贡献了每日的基础收入）。即使全触发传说级 × 3次/天，化神期最多约239,000额外收入，不到日均的11%。**不会颠覆现有经济。**

### 12.1 触发概率期望

假设玩家每天执行以下操作：

| 操作 | 每日次数 | 概率 | 期望触发 |
|------|----------|------|----------|
| 签到 | 1 | 15% | 0.15 |
| 出关 | 1-2 | 10% | 0.10-0.20 |
| 秘境 | 1 | 20% | 0.20 |
| 悬赏 | 1-3 | 25% | 0.25-0.75 |
| Boss | 0-2 | 30% | 0-0.60 |
| 探险 | 2-5 | 15% | 0.30-0.75 |
| **合计** | | | **1.0-2.65** |

→ 活跃玩家每天期望触发 1-3 次，基本能达到每日上限。休闲玩家（只签到+秘境）约 0.35 次/天，需要 3 天触发 1 次。

### 12.2 奖励数值参考（基于全经济分析修正）

各选项的 `rewards.gold` 字段在 encounter_config.json 中用 `[min, max]` 表示**本层级基础值**，乘以 `level_bonus × rarity_mult × risk_mult` 后为实际发放量。

| 境界层级 | 灵石范围(基础值) | 修为范围(基础值) | 物品价值 | HP惩罚 |
|----------|:----------------:|:----------------:|----------|--------|
| 凡人期 (0-9) | 100~300 (安全) / 500~2,000 (风险) | 1,000~5,000 / 3,000~10,000 | 一品材料 | 10-20% |
| 筑基期 (10-18) | 400~1,200 / 2,000~8,000 | 5,000~30,000 / 20,000~100,000 | 二三品材料 | 15-25% |
| 元婴期 (19-27) | 1,500~4,500 / 7,500~30,000 | 30,000~150,000 / 100,000~500,000 | 四五品材料/低阶丹药 | 15-30% |
| 化神期 (28-36) | 7,500~22,500 / 37,500~150,000 | 150,000~800,000 / 500,000~2,000,000 | 六七品材料/中阶丹药 | 20-35% |
| 大乘期 (37-45) | 30,000~90,000 / 150,000~600,000 | 800,000~4,000,000 / 2,000,000~10,000,000 | 八品材料/高阶丹药 | 20-40% |
| 轮回期 (46+) | 125,000~375,000 / 625,000~2,500,000 | 4,000,000~20,000,000 / 10,000,000~50,000,000 | 九品材料/传说装备 | 25-50% |

缩放公式（同悬赏令/秘境 `level_scaling` 模式）：

```python
level_bonus = 1 + max(0, player.level_index - 3) * 0.045
rarity_mult = {"common": 1.0, "rare": 2.5, "epic": 6.0, "legendary": 15.0}
risk_mult = {"safe": 1.0, "risky": 3.0, "high_risk": 5.0}
final_gold = int(random.randint(gold_min, gold_max) * level_bonus * rarity_mult * risk_mult)
```

### 12.3 稀有度分布控制

| 稀有度 | 单事件权重 | 每日期望出现次数 |
|--------|-----------|-----------------|
| common (55%) | 100 | 1.1-1.7 |
| rare (27%) | 60 | 0.5-0.8 |
| epic (14%) | 30 | 0.3-0.4 |
| legendary (4%) | 10 | 0.04-0.1（约10-25天一次） |

---

## 13. 测试策略

### 13.1 单元测试（`tests/test_encounter_manager.py`）

| 测试场景 | 测试方法 | 预期结果 |
|----------|----------|----------|
| 触发概率 | `test_trigger_probability` | 多次调用后统计概率接近配置值 |
| 每日限制 | `test_daily_limit` | 超过 3 次后不再触发 |
| 因果偏移 | `test_karma_bias` | 高因果值玩家更多抽到正面事件 |
| 选择判定 | `test_choice_resolve_success` | risk=0 时必定成功 |
| 选择判定 | `test_choice_resolve_fail` | risk=1.0 时必定失败 |
| 消耗灵石 | `test_choice_cost_gold` | 灵石不足时拒绝并保留 pending |
| pending 超时 | `test_pending_timeout` | 超时后 resolve 返回超时提示 |
| 历史记录 | `test_history_tracking` | 每次 resolve 后写入 history |
| karma 钳制 | `test_karma_clamping` | 不超过 [-1000, 1000] |
| 奖励发放 | `test_reward_distribution` | 灵石/修为/物品正确发放 |

### 13.2 集成测试

| 测试场景 | 说明 |
|----------|------|
| 签到后触发 | 调用 `handle_check_in` 后检查是否收到奇遇消息 |
| 出关后触发 | 调用 `handle_end_cultivation` 后检查 |
| Boss 战斗后触发 | 调用 `handle_boss_fight` 后检查 |
| 多个触发点串联 | 连续进行签到+秘境+Boss，确保每日限制正确 |

---

## 14. 实现优先级

| 阶段 | 内容 | 预计代码量 |
|------|------|-----------|
| **P0** | `encounter_config.json` 编写（60+ 事件，含完整选择分支） | ~1500 行 |
| **P0** | `EncounterManager` 核心逻辑（trigger + select + resolve） | ~300 行 |
| **P0** | `EncounterHandler` 命令处理（choose + info + history） | ~100 行 |
| **P0** | Player 模型 + migration v41 + data_manager 扩展 | ~30 行 |
| **P0** | main.py 初始化 + 命令注册 + 触发钩子（5 处） | ~80 行 |
| **P1** | config_manager + default_configs 加载 | ~20 行 |
| **P1** | combat_manager 因果攻击加成 | ~10 行 |
| **P1** | cultivation_manager 因果修炼加成 | ~5 行 |
| **P1** | activity_manager track_encounter | ~10 行 |
| **P1** | achievement_manager 新条件类型 | ~15 行 |
| **P2** | 传说级广播 + BUSY_STATE_ALLOWED_COMMANDS | ~15 行 |
| **P2** | 单元测试 + 集成测试 | ~200 行 |
| **P2** | misc_handler 帮助文本更新 | ~5 行 |
| **P2** | 因果衰减在签到时的应用 | ~10 行 |

---

## 15. 开放问题

| # | 问题 | 建议方案 | 状态 |
|---|------|----------|------|
| 1 | 奇遇选择是否有"最优解"？ | 设计时确保每个选项都有场景价值（安全/风险/因果的三角权衡） | 设计约束 |
| 2 | 因果值是否应该对其他玩家可见？ | 建议仅自己可见，称号可展示 | 待确认 |
| 3 | 传说级广播是否显示玩家名？ | 建议匿名："某位修士"，保护隐私 | 待确认 |
| 4 | 奇遇事件是否定期扩充？ | 建议每次版本更新新增 5-10 个事件 | 待确认 |
| 5 | pending 超时是否消耗今日次数？ | 不消耗（回退 daily_encounter_count） | 待确认 |
| 6 | 因果值衰减在签到处理 vs 后台任务？ | 签到处理（轻量，无需额外后台任务） | 待确认 |
| 7 | 是否需要持久化 pending 状态？ | 不需要（180s 短超时 + 重启后丢弃可接受）| 已定 |

---

## 附录 A: 与轮回系统的预留集成

当轮回系统（`docs/superpowers/specs/2026-07-06-reincarnation-system-design-v2.md`）实现后，奇遇系统需要以下适配：

```python
# EncounterManager._select_encounter() 中
reincarnation_count = player.reincarnation_count if hasattr(player, 'reincarnation_count') else 0

# 根据轮回次数解锁专属事件池
if reincarnation_count >= 1:
    pool += self._get_reincarnation_events(tier=1)  # 前世记忆
if reincarnation_count >= 5:
    pool += self._get_reincarnation_events(tier=2)  # 天道轮回
if reincarnation_count >= 10:
    pool += self._get_reincarnation_events(tier=3)  # 因果终章

# 轮回时保留 karma
# 在轮回系统的重生逻辑中：new_player.karma = old_player.karma
```
