# 奇遇机缘系统设计文档 (Encounter System Design)

> **项目:** astrbot_plugin_monixiuxian2 — 文字修仙放置游戏插件
> **日期:** 2026-06-19
> **状态:** Draft
> **作者:** Claude Code + ENRIN233

---

## 1. 概述

### 1.1 定义

**奇遇机缘** 是玩家在日常修炼过程中被动触发的随机叙事事件。每个奇遇呈现一段修仙世界的场景描述，玩家做出选择后获得不同结果（奖励/惩罚/因果变化）。

### 1.2 设计目标

| 目标 | 实现方式 |
|------|----------|
| **高耐玩性** | 50+ 事件池，4 稀有度分级，因果偏移影响事件概率 |
| **低疲劳** | 被动触发，无需额外操作，60秒选择超时 |
| **主题契合** | 修仙世界观叙事，善恶因果与修炼道路呼应 |
| **系统联动** | 与每日活跃、成就、轮回、广播等系统整合 |

### 1.3 核心设计决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 触发方式 | 被动随机触发 | 自然融入游戏流程，惊喜感强 |
| 内容形式 | 叙事选择型 | 文字游戏天然优势，深度体验 |
| 长期影响 | 善恶因果系统 | 角色扮演调味料，影响战斗/修炼/事件概率 |
| 境界门槛 | 全境界可用，按境界分层 | 所有玩家都能体验 |
| 触发频率 | 每日3次，概率触发 | 控制节奏，避免疲劳 |
| 稀有广播 | 传说级全服广播 | 增加社交话题性和FOMO感 |

---

## 2. 触发机制

### 2.1 触发时机

玩家执行以下操作时，系统检查是否触发奇遇：

| 操作 | 触发概率 | 调用位置 |
|------|----------|----------|
| 签到 | 15% | `handlers/player_handler.py` `handle_check_in` |
| 闭关出关 | 10% | `handlers/player_handler.py` `handle_open` |
| 秘境探索完成 | 20% | `handlers/rift_handlers.py` `handle_complete_explore` |
| 悬赏令完成 | 25% | `handlers/bounty_handlers.py` `handle_complete_bounty` |
| Boss战斗结束 | 30% | `handlers/boss_handlers.py` `handle_fight_boss` |
| 探险副本前进 | 15% | `handlers/dungeon_handlers.py` `handle_advance` |

### 2.2 每日限制

- 每日最多触发 **3次** 奇遇
- 次日自动重置（通过日期字符串比较，同 `daily_activity` 模式）
- 存储在 Player 模型的 `last_encounter_date` 和 `daily_encounter_count` 字段

### 2.3 触发流程

```
玩家执行操作（如完成悬赏令）
    │
    ├─ 检查：daily_encounter_count < 3？
    │   ├─ 否 → 不触发，正常返回操作结果
    │   └─ 是 → 进入概率检定
    │
    ├─ 概率检定（random.random() < 触发概率）
    │   ├─ 未命中 → 不触发
    │   └─ 命中 → 选择事件
    │
    ├─ 事件选择：
    │   1. 筛选：min_level <= player.level_index <= max_level
    │   2. 因果偏移：karma >= 500 → 正面事件权重 +25%
    │                  karma <= -500 → 高风险事件权重 +25%
    │   3. 加权随机：按 weight 字段加权选择
    │
    ├─ 发送奇遇文本 + 选项（60秒超时）
    │
    ├─ 玩家回复选项编号 → 执行结果判定
    │
    └─ 更新 daily_encounter_count + karma + 发放奖励
```

---

## 3. 事件池设计

### 3.1 事件池规模

初版 50+ 个奇遇事件，按境界分为 6 个层级：

| 层级 | 适用境界 (level_index) | 事件数 | 特点 |
|------|------------------------|--------|------|
| 凡人期 | 0-9 | 10 | 简单选择，小奖励，教学性质 |
| 筑基期 | 10-18 | 10 | 中等风险，开始有因果影响 |
| 元婴期 | 19-27 | 10 | 复杂分支，显著因果偏移 |
| 化神期 | 28-36 | 8 | 高风险高回报，因果影响大 |
| 大乘期 | 37-45 | 7 | 传说级事件出现 |
| 轮回期 | 46+ | 5+ | 轮回专属事件，因果值决定结局 |

### 3.2 稀有度分级

| 稀有度 | 概率权重 | 特点 | 全服广播 |
|--------|----------|------|----------|
| 普通 (common) | 60% | 基础事件，简单选择 | 否 |
| 稀有 (rare) | 25% | 较好的奖励，有意义的选择 | 否 |
| 史诗 (epic) | 12% | 高价值奖励，重大因果影响 | 否 |
| 传说 (legendary) | 3% | 极稀有，改变命运的选择 | **是** |

### 3.3 事件数据结构

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
                        "item_chance": 0.5,
                        "item_pool": ["灵草精华"]
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
                    "success_rewards": {"gold": [100, 300]},
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
                        "item_chance": 0.7,
                        "item_pool": ["灵草精华", "矿石碎片"]
                    },
                    "fail_text": "妖兽叼走了灵石却没有离开，你白费了一笔。",
                    "fail_penalty": {}
                }
            ]
        }
    ],
    "settings": {
        "daily_limit": 3,
        "choice_timeout_seconds": 60,
        "karma_event_bias_pct": 25,
        "legendary_broadcast": true
    }
}
```

### 3.4 事件示例（各层级各一个）

**凡人期 — 路遇乞丐**
> 你在路边遇到一位衣衫褴褛的老者，他向你乞讨灵石。
> 1. 施舍 200 灵石（因果 +8，有概率获得回报）
> 2. 漠然走过（因果 0）
> 3. 抢夺他的包裹（因果 -15，高概率获得物品）

**筑基期 — 古修士洞府**
> 你发现一处被封印的古修士洞府，封印已经松动。
> 1. 强行破开封印（风险中，因果 -10，高奖励）
> 2. 在洞府外参悟石碑上的功法（风险低，因果 +5，修为奖励）
> 3. 封印加固后离开（因果 +15，无奖励但积累善因）

**元婴期 — 天降异象**
> 天空突然出现一道裂缝，一块散发金光的陨石坠落在你面前。
> 1. 立即收取（风险高，可能触发守护阵法）
> 2. 先探查周围是否有人（风险低，因果 +3）
> 3. 布阵炼化陨石（消耗灵石，风险中，最大收益）

**化神期 — 魔修交易**
> 一位魔修向你兜售禁术功法，价格不菲。
> 1. 购买禁术（因果 -30，获得稀有功法）
> 2. 拒绝并警告（因果 +10，无奖励）
> 3. 出手擒拿魔修（风险高，因果 +25，高奖励）

**大乘期 — 天道考验**
> 你感应到天道意志的注视，一场无形的考验降临。
> 1. 顺应天道（因果 +50，修炼速度永久 +1%）
> 2. 逆天而行（因果 -50，攻击力永久 +1%）
> 3. 保持本心（因果 0，获得天道碎片×1）

**轮回期 — 前世记忆**
> 轮回之中，你隐约看到了前世的记忆碎片。
> 1. 追寻记忆（因果 +20，解锁前世传承加成）
> 2. 斩断因果（因果 -20，获得轮回修为 +100）
> 3. 静观其变（因果 0，修为奖励）

---

## 4. 善恶因果系统

### 4.1 因果值范围

范围: [-1000, +1000]，初始值 0。

### 4.2 因果称号与效果

| 区间 | 称号 | 效果 |
|------|------|------|
| -1000 ~ -500 | 魔道修士 | 战斗攻击力 +8%，遇到高风险高回报事件权重 +25% |
| -499 ~ -100 | 偏邪 | 战斗攻击力 +4% |
| -99 ~ +99 | 中立 | 无额外效果 |
| +100 ~ +499 | 偏正 | 修炼速度 +4% |
| +500 ~ +1000 | 正道修士 | 修炼速度 +8%，遇到正面事件权重 +25% |

### 4.3 因果值获取

| 行为 | 因果变化 | 示例 |
|------|----------|------|
| 强行夺取 | -5 ~ -30 | "强行采摘"选项 |
| 见死不救 | -3 ~ -10 | 中性选择中的隐性惩罚 |
| 出手相助 | +3 ~ +15 | 正面选择 |
| 放弃利益救人 | +10 ~ +30 | 牺牲型正面选择 |
| 以灵石解围 | +3 ~ +10 | 消耗资源的正面选择 |
| 中立选择 | 0 | 安全但无因果变化 |

### 4.4 因果值衰减

- 每天自然衰减 **2 点**（向 0 靠拢）
- 衰减在每日签到时处理
- 防止极端值永久锁定

### 4.5 因果与轮回联动

- 因果值存储在 `reincarnation_data` 表的 `permanent_bonuses.karma` 字段
- 轮回时因果值 **不重置** — "前世之因，后世之果"
- 因果值影响轮回专属事件的出现概率

### 4.6 因果对战斗的影响

在 `combat_manager.py` 的 `build_player_combat_stats` 中应用：

```python
# 获取因果值
karma = player_extra_data.get("karma", 0)
if karma <= -500:
    combat_stats.atk_bonus_pct += 0.08  # 魔道 +8% 攻击
elif karma <= -100:
    combat_stats.atk_bonus_pct += 0.04  # 偏邪 +4% 攻击
elif karma >= 500:
    # 正道效果在修炼速度中应用，不影响战斗
    pass
elif karma >= 100:
    pass
```

### 4.7 因果对修炼的影响

在 `cultivation_manager.py` 的修炼计算中应用：

```python
karma = player_extra_data.get("karma", 0)
karma_bonus = 0.0
if karma >= 500:
    karma_bonus = 0.08  # 正道 +8% 修炼速度
elif karma >= 100:
    karma_bonus = 0.04  # 偏正 +4%
# 魔道不加修炼速度
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
请选择：
1️⃣ 强行采摘（风险：30%，因果：-5）
2️⃣ 悄悄绕过（风险：无，因果：0）
3️⃣ 用灵石引开妖兽（风险：10%，因果：+3，消耗：500灵石）
━━━━━━━━━━━━━━━━━━━━
⏰ 60秒内回复编号，超时视为放弃。
```

### 5.2 选择结果消息格式

**成功时**:
```
✨ 你选择了【强行采摘】
━━━━━━━━━━━━━━━━━━━━
你趁妖兽不备，迅速采摘了灵草！
📦 获得：灵石 ×1,234 | 灵草精华 ×1
☯️ 因果：-5（当前：-15）
```

**失败时**:
```
💀 你选择了【强行采摘】
━━━━━━━━━━━━━━━━━━━━
妖兽被惊醒，你不得不狼狈逃窜，受了些轻伤。
💔 损失：20% 生命值
☯️ 因果：-5（当前：-15）
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
🌟 天降机缘！
某位修士在修炼途中触发了【天道考验】！
天地灵气波动，所有人都感受到了一丝异象...
```

---

## 6. 系统联动

### 6.1 与每日活跃联动

奇遇触发计入每日活跃的"探索"类任务进度。在 `ActivityTracker` 中新增 track hook：

```python
def track_encounter(self, user_id: str):
    """奇遇触发时调用"""
    self._add_progress(user_id, "encounter", 1)
```

新增每日任务配置（`TASK_DEFINITIONS`）：
```python
"encounter": ("触发奇遇", 10, 1),  # 1次即可完成，10积分
```

### 6.2 与成就系统联动

新增成就（`config/achievements.json`）：

| 成就名 | 条件类型 | 条件值 | 奖励 |
|--------|----------|--------|------|
| 初遇机缘 | `encounter_count` | 10 | 经验 ×5000 |
| 奇遇连连 | `encounter_count` | 50 | 经验 ×20000 |
| 命运之子 | `encounter_count` | 100 | 经验 ×50000 |
| 魔道修士 | `karma` | -500 | 攻击力永久 +50 |
| 正道修士 | `karma` | 500 | 修炼速度永久 +2% |

需要在 `achievement_manager.py` 的 `_check_condition` 中新增 `encounter_count` 和 `karma` 条件类型。

### 6.3 与轮回系统联动

- 因果值跨世保留（存储在 `reincarnation_data`）
- 轮回次数解锁专属奇遇事件：
  - 1次轮回解锁：前世记忆系列事件
  - 5次轮回解锁：天道轮回系列事件
  - 10次轮回解锁：因果终章系列事件

### 6.4 与广播系统联动

传说级奇遇触发时调用 `main.py` 的 `_broadcast_to_whitelist_groups()`：

```python
if encounter["rarity"] == "legendary":
    msg = f"🌟 天降机缘！\n某位修士触发了【{encounter['name']}】！\n天地灵气波动..."
    await self.broadcast_func(msg)
```

### 6.5 与储物戒/丹药背包联动

- 物品奖励 → 存入 `storage_ring_items`
- 丹药奖励 → 存入 `pills_inventory`
- 灵石奖励 → 直接加到 `player.gold`
- 修为奖励 → 直接加到 `player.experience`

---

## 7. 数据模型

### 7.1 Player 模型新增字段

在 `models.py` 的 `Player` dataclass 中新增：

```python
last_encounter_date: str = ""       # 上次奇遇触发日期 (YYYY-MM-DD)
daily_encounter_count: int = 0      # 今日奇遇触发次数
karma: int = 0                      # 因果值 [-1000, +1000]
encounter_history: str = "[]"       # JSON: 最近10次奇遇记录
```

### 7.2 数据库迁移

新增 migration v41：

```python
@migration(version=41)
async def add_encounter_fields(db):
    """新增奇遇系统字段"""
    await db.execute(
        "ALTER TABLE players ADD COLUMN last_encounter_date TEXT DEFAULT ''"
    )
    await db.execute(
        "ALTER TABLE players ADD COLUMN daily_encounter_count INTEGER DEFAULT 0"
    )
    await db.execute(
        "ALTER TABLE players ADD COLUMN karma INTEGER DEFAULT 0"
    )
    await db.execute(
        "ALTER TABLE players ADD COLUMN encounter_history TEXT DEFAULT '[]'"
    )
```

### 7.3 encounter_history JSON 结构

```json
[
    {
        "id": "mountain_herb_01",
        "name": "山涧灵草",
        "choice": "a",
        "result": "success",
        "karma_delta": -5,
        "timestamp": 1718800000
    }
]
```

### 7.4 ConfigManager 扩展

在 `config_manager.py` 中新增加载 `encounter_config.json`：

```python
self.encounter_config = self._load_config("encounter_config.json")
self.encounters = self.encounter_config.get("encounters", [])
self.encounter_settings = self.encounter_config.get("settings", {})
```

---

## 8. 代码修改清单

### 8.1 新增文件

| 文件 | 说明 |
|------|------|
| `managers/encounter_manager.py` | 奇遇系统核心逻辑 |
| `handlers/encounter_handler.py` | 奇遇选择处理 |
| `config/encounter_config.json` | 奇遇事件池配置 |
| `tests/test_encounter_manager.py` | 奇遇系统测试 |

### 8.2 修改文件

| 文件 | 修改内容 |
|------|----------|
| `data/migration.py` | 新增 v41 migration |
| `models.py` | Player 新增 4 个字段 |
| `config_manager.py` | 加载 encounter_config.json |
| `handlers/player_handler.py` | 签到/出关时调用奇遇检查 |
| `handlers/rift_handlers.py` | 秘境完成时调用奇遇检查 |
| `handlers/bounty_handlers.py` | 悬赏完成时调用奇遇检查 |
| `handlers/boss_handlers.py` | Boss战斗后调用奇遇检查 |
| `handlers/dungeon_handlers.py` | 探险前进时调用奇遇检查 |
| `handlers/misc_handler.py` | 帮助文本新增奇遇指令 |
| `managers/achievement_manager.py` | 新增 encounter_count/karma 条件 |
| `managers/activity_manager.py` | 新增奇遇每日任务 |
| `main.py` | 注册奇遇相关指令 |
| `combat_manager.py` | 因果值对攻击力的影响 |
| `cultivation_manager.py` | 因果值对修炼速度的影响 |

### 8.3 数据流

```
玩家执行操作（签到/秘境/悬赏/Boss/探险）
    │
    ├─ handler 调用 encounter_manager.try_trigger(player, action_type)
    │   ├─ 检查每日限制
    │   ├─ 概率检定
    │   ├─ 选择事件（含因果偏移）
    │   └─ 返回 encounter dict 或 None
    │
    ├─ 如果触发：
    │   ├─ handler 发送奇遇文本 + 选项
    │   ├─ 等待玩家回复（60秒超时）
    │   ├─ encounter_manager.resolve(player, encounter, choice_id)
    │   │   ├─ 判定成功/失败
    │   │   ├─ 计算奖励/惩罚
    │   │   ├─ 更新 karma
    │   │   ├─ 更新 daily_encounter_count
    │   │   └─ 写入 encounter_history
    │   └─ 发送结果消息
    │
    └─ 如果传说级：broadcast_to_whitelist_groups()
```

---

## 9. 指令清单

| 指令 | 说明 | 权限 |
|------|------|------|
| `/奇遇信息` | 查看今日奇遇次数、因果值、因果称号 | 所有玩家 |
| `/奇遇记录` | 查看最近10次奇遇历史 | 所有玩家 |

注：奇遇本身不需要指令触发（被动触发），以上仅为信息查看指令。

---

## 10. 数值平衡

### 10.1 触发概率期望

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

### 10.2 奖励数值参考

| 境界层级 | 灵石范围 | 修为范围 | 物品价值 |
|----------|----------|----------|----------|
| 凡人期 | 100-3,000 | 1,000-10,000 | 一品材料 |
| 筑基期 | 500-10,000 | 10,000-100,000 | 二三品材料 |
| 元婴期 | 2,000-30,000 | 50,000-500,000 | 四五品材料/低阶丹药 |
| 化神期 | 5,000-80,000 | 200,000-2,000,000 | 六七品材料/中阶丹药 |
| 大乘期 | 20,000-200,000 | 1,000,000-10,000,000 | 八品材料/高阶丹药 |
| 轮回期 | 50,000-500,000 | 5,000,000-50,000,000 | 九品材料/传说装备 |

奖励按 `level_index * level_scaling.bounty_rift_coefficient` 缩放。

---

## 11. 开放问题

| # | 问题 | 建议方案 | 状态 |
|---|------|----------|------|
| 1 | 奇遇选择是否有"最优解"？ | 设计时确保每个选项都有场景价值（安全/风险/因果的三角权衡） | 设计约束 |
| 2 | 因果值是否应该对其他玩家可见？ | 建议仅自己可见，称号可展示 | 待确认 |
| 3 | 传说级广播是否显示玩家名？ | 建议匿名："某位修士"，保护隐私 | 待确认 |
| 4 | 奇遇事件是否定期扩充？ | 建议每次版本更新新增 5-10 个事件 | 待确认 |
| 5 | 超时是否消耗今日次数？ | 建议不消耗（超时=放弃，非失败） | 待确认 |

---

## 附录 A: 触发概率配置

```json
{
    "trigger_chances": {
        "check_in": 0.15,
        "close_cultivation": 0.10,
        "rift_complete": 0.20,
        "bounty_complete": 0.25,
        "boss_fight": 0.30,
        "dungeon_advance": 0.15
    }
}
```

## 附录 B: 因果值配置

```json
{
    "karma_settings": {
        "min": -1000,
        "max": 1000,
        "initial": 0,
        "daily_decay": 2,
        "event_bias_threshold": 500,
        "event_bias_pct": 25,
        "bonuses": {
            "demon": {"min": -1000, "max": -500, "atk_pct": 0.08},
            "evil": {"min": -499, "max": -100, "atk_pct": 0.04},
            "neutral": {"min": -99, "max": 99, "bonus": 0},
            "good": {"min": 100, "max": 499, "cultivation_pct": 0.04},
            "saint": {"min": 500, "max": 1000, "cultivation_pct": 0.08}
        }
    }
}
```
