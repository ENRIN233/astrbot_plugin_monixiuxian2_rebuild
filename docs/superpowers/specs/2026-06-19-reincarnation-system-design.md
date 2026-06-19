# 轮回系统设计文档 (Reincarnation System Design)

> **项目:** astrbot_plugin_monixiuxian2 — 文字修仙放置游戏插件
> **日期:** 2026-06-19
> **状态:** Draft
> **作者:** Claude Code + ENRIN233

---

## 1. 概述

### 1.1 定义

**轮回** 是玩家达到轮回境后的主动成长机制，区别于弃道重修的惩罚性重置。轮回保留部分力量，重新开始修炼旅程，形成"积累→轮回→更强→再积累"的长期循环。

### 1.2 核心理念

| 机制 | 弃道重修 | 轮回 |
|------|----------|------|
| **性质** | 惩罚性重置 | 成长性进化 |
| **门槛** | 无境界要求 | 轮回境 + 轮回丹 |
| **保留** | 无（全删） | 轮回修为、加成、神通、成就 |
| **CD** | 7天 | 无（消耗材料） |
| **定位** | 失误重来 | 核心长期目标 |

### 1.3 设计目标

- **耐玩性**: 轮回次数驱动的渐进式奖励，50+ 次轮回的长期目标
- **低疲劳**: 被动收益为主，关键决策点少而有意义
- **主题契合**: 利用已有的"轮回道果"伏笔代码，自然融入修仙世界观
- **系统联动**: 与突破、炼丹、成就、传承等现有系统深度整合

---

## 2. 现有代码分析

### 2.1 已预留的轮回接口

代码中存在以下为轮回系统预留但尚未激活的设计：

| 伏笔 | 文件位置 | 说明 |
|------|----------|------|
| `轮回道果` 灵根 | `core/cultivation_manager.py:93-95` | 速度配置 `REINCARNATION_SPEED` 已定义，但 `root_pools` 中无对应条目 |
| `真轮回道果` 灵根 | `core/cultivation_manager.py:285-287` | 速度配置 `TRUE_REINCARNATION_SPEED` 已定义，同样不在 `root_pools` 中 |
| `player_skills` 不随弃道删除 | `data/data_manager.py` cascade 逻辑 | 神通数据天然跨世保留 |
| 轮回境 0% 突破率 | `config/level_config.json` index 46-48 | 轮回境无法正常突破，需要特殊机制 |
| 合道境天文数字修为 | `config/level_config.json` index 55-57 | 最高境界修为需求达100万亿，单世不可达 |

### 2.2 关键约束

**突破率墙**: 从大乘境中期 (index 45) 开始，`success_rate = 0.0`。玩家无法通过常规突破到达轮回境。现有的突破辅助手段（突破丹药、level_up_rate 累积）在 0% 基础率下无效。

**→ 设计决策**: 需要一种特殊突破机制（如"天道突破丹"或轮回次数解锁突破率）来跨越 0% 墙。详见第 5 节。

### 2.3 `delete_player_cascade` 行为

当前弃道重修调用的 `delete_player_cascade` 会删除以下表：

```
blessed_lands, spirit_farms, bank_accounts, bank_loans,
bounty_tasks, dual_cultivation, dual_cultivation_requests,
user_cd, buff_info, impart_info, combat_cooldowns,
pending_gifts, players
```

**未清理的表**（已有孤立数据风险）:

```
player_skills, dungeon_runs, gm_compensation_claims,
bank_transactions, trades, consignment_listings, sects
```

**→ 设计决策**: 轮回系统需要一个新的 `reincarnation_delete_player` 方法，而非复用现有的 `delete_player_cascade`。新方法需：
1. 先将需要保留的数据写入 `reincarnation_data` 表
2. 再执行选择性删除（保留 `player_skills`、`reincarnation_data`）
3. 同时修复现有的孤立数据清理问题

---

## 3. 轮回触发与流程

### 3.1 触发条件

| 条件 | 说明 |
|------|------|
| **境界要求** | `level_index >= 46`（轮回境初期） |
| **状态要求** | 空闲状态（非闭关/探索/交易等） |
| **消耗物品** | 1 枚轮回丹（通过炼丹系统炼制） |
| **无贷款** | 无未偿还银行贷款 |
| **指令** | `/轮回` → 展示信息并确认 → 执行 |

### 3.2 执行流程

```
玩家输入 /轮回
    │
    ├─ 检查条件（境界、状态、轮回丹、贷款）
    │
    ├─ 展示轮回预览：
    │   "你即将踏入轮回...
    │    本次轮回将获得: {n} 轮回修为
    │    将保留: 道号、已学神通、轮回修为、轮回加成
    │    将重置: 境界、修为、灵根、装备、丹药...
    │    确认轮回？(输入 轮回 确认)"
    │
    ├─ 玩家输入 "轮回 确认"
    │
    ├─ 执行轮回：
    │   1. 计算本轮轮回修为奖励（基于最高境界）
    │   2. 写入 reincarnation_data（保留数据）
    │   3. 消耗轮回丹
    │   4. 执行 reincarnation_delete_player（选择性删除）
    │   5. 自动创建新角色（继承道号，灵根按保底随机）
    │   6. 应用轮回永久加成
    │   7. 检查里程碑奖励
    │   8. 发送轮回结果报告
    │
    └─ 新一世开始
```

### 3.3 轮回信息查看

指令 `/轮回信息` 展示：

```
🌀 轮回信息
━━━━━━━━━━━━━━━━━━━━
轮回次数: 第 3 次
历史最高境界: 渡劫境圆满
轮回修为余额: 850
累计获得轮回修为: 1,750
━━━━━━━━━━━━━━━━━━━━
本轮最高境界: 轮回境圆满
下次轮回预计获得: 350 轮回修为
━━━━━━━━━━━━━━━━━━━━
永久加成:
  修炼速度: +15%
  突破概率: +3%
  初始生命: +1500
━━━━━━━━━━━━━━━━━━━━
灵根保底: 至少 中品
解锁灵根: 轮回道果 ✓
```

---

## 4. 数据模型

### 4.1 新增表: `reincarnation_data`

```sql
CREATE TABLE IF NOT EXISTS reincarnation_data (
    user_id TEXT PRIMARY KEY,
    reincarnation_count INTEGER DEFAULT 0,
    highest_level_index INTEGER DEFAULT 0,
    reincarnation_currency INTEGER DEFAULT 0,
    total_currency_earned INTEGER DEFAULT 0,
    shop_purchases TEXT DEFAULT '{}',
    permanent_bonuses TEXT DEFAULT '{}',
    preserved_impart TEXT DEFAULT '{}',
    preserved_achievements TEXT DEFAULT '{}',
    preserved_storage_ring TEXT DEFAULT '',
    preserved_bank_vip INTEGER DEFAULT 0,
    last_reincarnation_time INTEGER DEFAULT 0,
    created_at INTEGER DEFAULT 0
);
```

字段说明：

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_id` | TEXT PK | 玩家ID，与 players 表一致 |
| `reincarnation_count` | INTEGER | 轮回次数 |
| `highest_level_index` | INTEGER | 历史最高境界 index |
| `reincarnation_currency` | INTEGER | 当前轮回修为余额 |
| `total_currency_earned` | INTEGER | 累计获得轮回修为（里程碑用） |
| `shop_purchases` | JSON | `{item_id: count}` 轮回商店购买记录 |
| `permanent_bonuses` | JSON | 购买的永久加成详情 |
| `preserved_impart` | JSON | 保留的传承加成百分比 |
| `preserved_achievements` | JSON | 跨世成就解锁记录 |
| `preserved_storage_ring` | TEXT | 保留的储物戒等级名称 |
| `preserved_bank_vip` | INTEGER | 保留的银行VIP等级 |
| `last_reincarnation_time` | INTEGER | 上次轮回的 unix 时间戳 |
| `created_at` | INTEGER | 首次轮回的 unix 时间戳 |

### 4.2 `permanent_bonuses` JSON 结构

```json
{
    "cultivation_speed": 0.15,
    "breakthrough_bonus": 3,
    "initial_hp": 1500,
    "initial_atk": 300,
    "gold_bonus": 0.10,
    "pill_effect_bonus": 0.10,
    "death_protection": 0.95,
    "impart_preserve_ratio": 0.40
}
```

### 4.3 `preserved_impart` JSON 结构

```json
{
    "impart_hp_per": 0.05,
    "impart_mp_per": 0.03,
    "impart_atk_per": 0.02,
    "impart_know_per": 0.01,
    "impart_burst_per": 0.00
}
```

### 4.4 数据库迁移

新增 migration v40：

```python
@migration(version=40)
async def add_reincarnation_table(db):
    """新增轮回系统数据表"""
    await db.execute("""
        CREATE TABLE IF NOT EXISTS reincarnation_data (
            user_id TEXT PRIMARY KEY,
            reincarnation_count INTEGER DEFAULT 0,
            highest_level_index INTEGER DEFAULT 0,
            reincarnation_currency INTEGER DEFAULT 0,
            total_currency_earned INTEGER DEFAULT 0,
            shop_purchases TEXT DEFAULT '{}',
            permanent_bonuses TEXT DEFAULT '{}',
            preserved_impart TEXT DEFAULT '{}',
            preserved_achievements TEXT DEFAULT '{}',
            preserved_storage_ring TEXT DEFAULT '',
            preserved_bank_vip INTEGER DEFAULT 0,
            last_reincarnation_time INTEGER DEFAULT 0,
            created_at INTEGER DEFAULT 0
        )
    """)
```

---

## 5. 轮回保留与重置

### 5.1 保留项（跨世永恒）

| 保留项 | 存储方式 | 说明 |
|--------|----------|------|
| 道号 | 创建新角色时从旧角色读取 | 轮回不改名 |
| 轮回次数 | `reincarnation_data.reincarnation_count` | 核心计数器 |
| 历史最高境界 | `reincarnation_data.highest_level_index` | 里程碑判定用 |
| 轮回修为 | `reincarnation_data.reincarnation_currency` | 轮回专属货币 |
| 轮回商店加成 | `reincarnation_data.permanent_bonuses` | 永久属性加成 |
| 已学神通 | `player_skills` 表（已有，不随弃道删除） | 天然跨世保留 |
| 成就解锁 | `reincarnation_data.preserved_achievements` | 跨世保留 |
| 传承加成 | `reincarnation_data.preserved_impart` | 按比例保留（需购买） |
| 储物戒等级 | `reincarnation_data.preserved_storage_ring` | 保留等级，内容清空 |
| 银行VIP | `reincarnation_data.preserved_bank_vip` | 保留VIP等级 |

### 5.2 重置项（归零重来）

| 重置项 | 说明 |
|--------|------|
| 境界 → 江湖好手 (0) | 从头修炼 |
| 修为/经验 → 0 | 重新积累 |
| 灵石 → 初始值 | 重新赚取 |
| 灵根 → 重新随机（有保底） | 轮回次数影响品质下限 |
| 装备/功法/辅修 → 清空 | 重新获取 |
| 丹药背包/储物戒内容 → 清空 | 重新收集 |
| 永久丹药增益 → 清空 | 重新服用 |
| 宗门 → 退出 | 需重新加入 |
| 洞天福地/灵田 → 清空 | 重新建设 |
| 银行账户/贷款 → 清空 | 重新开始 |

### 5.3 新角色创建时的轮回加成应用

创建新角色后，从 `reincarnation_data` 读取 `permanent_bonuses` 并应用：

```python
# 伪代码 — 在创建新角色后
reinc_data = await db.get_reincarnation_data(user_id)
if reinc_data:
    bonuses = json.loads(reinc_data.permanent_bonuses)
    player.hp += bonuses.get("initial_hp", 0)
    player.atk += bonuses.get("initial_atk", 0)
    # cultivation_speed 和 breakthrough_bonus 在各自计算时读取
    # gold_bonus 在签到/掉落时读取
    # death_protection 在突破时读取
```

---

## 6. 轮回奖励体系

### 6.1 轮回修为计算

每次轮回，根据本轮最高境界获得轮回修为：

| 本轮最高境界 | 基础轮回修为 |
|-------------|-------------|
| 轮回境初期 (46) | 100 |
| 轮回境中期 (47) | 200 |
| 轮回境圆满 (48) | 350 |
| 渡劫境初期 (49) | 500 |
| 渡劫境中期 (50) | 700 |
| 渡劫境圆满 (51) | 1,000 |
| 飞升境初期 (52) | 1,500 |
| 飞升境中期 (53) | 2,200 |
| 飞升境圆满 (54) | 3,000 |
| 合道境初期 (55) | 5,000 |
| 合道境中期 (56) | 8,000 |
| 合道境圆满 (57) | 12,000 |

轮回修为获取倍率（基于里程碑）：

| 轮回次数 | 倍率 |
|----------|------|
| 1-2 | ×1.0 |
| 3-4 | ×1.2 |
| 5-9 | ×1.2 |
| 10-19 | ×1.5 |
| 20-49 | ×1.5 |
| 50+ | ×2.0 |

### 6.2 里程碑奖励

| 轮回次数 | 解锁奖励 |
|----------|----------|
| 第1次 | 解锁 **轮回道果** 灵根（修炼速度 ×1.5） |
| 第3次 | 轮回修为获取 +20% |
| 第5次 | 解锁 **真轮回道果** 灵根（修炼速度 ×2.0） |
| 第10次 | 轮回修为获取 +50%，解锁称号 "十世大能" |
| 第20次 | 解锁 **混沌道果** 灵根（修炼速度 ×2.5），解锁称号 "轮回不灭" |
| 第50次 | 轮回修为获取 +100%，解锁称号 "百世仙尊" |

### 6.3 轮回修为商店

使用轮回修为购买永久加成（跨世不消失）：

| 加成项 | 单价 | 单次效果 | 购买上限 | 满级效果 |
|--------|------|----------|----------|----------|
| 修炼加速 | 100 | 修炼速度 +5% | 20次 | +100% |
| 突破概率 | 150 | 突破基础概率 +1% | 10次 | +10% |
| 生命强化 | 80 | 初始HP +500 | 30次 | +15000 |
| 攻击强化 | 80 | 初始ATK +100 | 30次 | +3000 |
| 灵石加成 | 120 | 灵石获取 +10% | 10次 | +100% |
| 丹药增效 | 200 | 永久丹药效果 +10% | 5次 | +50% |
| 死亡保护 | 300 | 死亡率 ×0.95 | 10次 | ×0.60 |
| 传承保留 | 500 | 轮回时传承保留 +20% | 5次 | 100%保留 |

商店指令：`/轮回商店` → 列出可购买项目；`/轮回购买 <项目名>` → 购买。

---

## 7. 灵根系统集成

### 7.1 灵根保底机制

轮回时重新随机灵根，但轮回次数提升品质下限：

| 轮回次数 | 灵根最低品质 | 对应类别 |
|----------|-------------|----------|
| 0（首次） | 无保底 | 可能抽到凡品 |
| 1-2 | 至少下品 | TRUE (1.0速) |
| 3-4 | 至少中品 | WUXING (1.0速) |
| 5-9 | 至少上品 | VARIANT (1.2速) |
| 10-19 | 至少极品 | HEAVENLY (1.3速) |
| 20+ | 至少仙品 | DRAGON (1.4速) |

### 7.2 轮回道果灵根解锁

代码中已预留 `轮回道果` 和 `真轮回道果` 的速度配置，但不在 `root_pools` 中。需要：

1. 在 `root_pools` 中新增 `REINCARNATION` 和 `TRUE_REINCARNATION` 类别
2. 在 `_get_random_spiritual_root` 中，当轮回次数达标时，**替换**随机灵根为对应道果
3. 里程碑灵根是**确定性解锁**，不参与随机：

```python
# 伪代码 — 轮回后灵根分配
def assign_reincarnation_root(reincarnation_count, root_pools, weights):
    if reincarnation_count >= 20:
        return "混沌道果"  # 确定性
    elif reincarnation_count >= 5:
        return "真轮回道果"  # 确定性
    elif reincarnation_count >= 1:
        return "轮回道果"  # 确定性
    else:
        return random_root_with_floor(root_pools, weights, floor=None)
```

### 7.3 新增灵根配置

在 `_conf_schema.json` 的 `SPIRIT_ROOT_SPEEDS` 中确认已存在：

```json
{
    "REINCARNATION_SPEED": 1.5,
    "TRUE_REINCARNATION_SPEED": 2.0
}
```

需新增 `CHAOS_REINCARNATION_SPEED: 2.5`（用于混沌道果）。

---

## 8. 突破系统集成

### 8.1 0% 突破率墙的解决方案

从大乘境中期 (index 45) 起，`success_rate = 0.0`。设计如下解决方案：

**方案: 轮回次数解锁突破率**

| 境界段 | 基础突破率 | 解锁条件 | 解锁后突破率 |
|--------|-----------|----------|-------------|
| 大乘境初期 (43) | 1% | 无 | 1% |
| 大乘境中期-圆满 (44-45) | 0% | ≥ 0次轮回 | 1% |
| 轮回境 (46-48) | 0% | ≥ 1次轮回 | 1% |
| 渡劫境 (49-51) | 0% | ≥ 1次轮回 | 0.5% |
| 飞升境 (52-54) | 0% | ≥ 3次轮回 | 0.5% |
| 合道境 (55-57) | 0% | ≥ 5次轮回 | 0.1% |

突破率计算公式调整：

```python
# 在 breakthrough_handler.py 中
base_rate = level_config[level_index]["success_rate"]
if base_rate == 0:
    # 检查轮回解锁
    reinc_data = await db.get_reincarnation_data(user_id)
    if not reinc_data:
        return 0  # 未轮回过，无法突破
    required = get_required_reincarnation(level_index)
    if reinc_data.reincarnation_count < required:
        return 0  # 轮回次数不足
    base_rate = get_unlocked_rate(level_index)  # 如 0.01, 0.005, 0.001
# 后续叠加突破丹药、level_up_rate 等加成
```

### 8.2 轮回境的特殊处理

轮回境 (46-48) 有两种"突破"路径：

**路径A: 常规突破**（需要足够轮回次数 + 突破概率加成）
- 消耗修为，尝试突破到下一大境界
- 成功率 = 解锁后基础率 + 突破丹药 + level_up_rate

**路径B: 主动轮回**（在轮回境任意阶段选择）
- 消耗轮回丹，直接进入轮回
- 获得轮回修为（基于当前境界）
- 重新开始

两条路径并存，玩家可选择继续冲高境界（更高轮回修为），或尽早轮回（更快积累轮回次数）。

---

## 9. 炼丹系统集成

### 9.1 轮回丹配方

轮回丹通过炼丹系统炼制，需新增配置：

**新增灵药**（加入 `config/herbs.json`）：

| 灵药名 | 品级 | h_a_c 类型 | 获取途径 |
|--------|------|-----------|----------|
| 天道碎片 | 九品 | 特殊 | 世界Boss概率掉落 |
| 轮回之水 | 八品 | 寒性 | 秘境探索稀有掉落 |
| 涅槃之火 | 八品 | 热性 | 探险副本BOSS层奖励 |
| 万年灵芝 | 九品 | 中性 | 灵田九品收获极稀有 |

**新增配方**（加入 `config/alchemy_recipes.json`）：

```json
{
    "name": "轮回丹",
    "elixir_config": {
        "天道碎片": {"min_power": 3},
        "轮回之水": {"min_power": 2},
        "涅槃之火": {"min_power": 2},
        "万年灵芝": {"min_power": 1}
    },
    "mix_exp": 500,
    "description": "服用后可踏入轮回，保留前世部分力量重新修炼。"
}
```

**关键**: 炼丹系统已完全数据驱动（`alchemy_manager.py` 的 `match_recipe` 和 `check_harmony` 是通用逻辑），新增配方只需修改 JSON 配置文件，无需改代码。

### 9.2 轮回丹使用

轮回丹不通过"服用丹药"指令使用，而是在 `/轮回` 指令执行时自动消耗。这避免了"误服"风险。

---

## 10. 传承系统集成

### 10.1 当前状态

传承系统 (`impart_manager.py`) 的卡牌收集系统尚未实现。`config/impart_cards.json` 定义了 105 张卡牌，但没有获取途径。

### 10.2 轮回与传承的联动

轮回系统为传承提供了跨世价值：

1. **轮回时保留传承**: 如果玩家已购买"传承保留"加成（通过轮回修为商店），轮回时将当前 `impart_info` 的百分比按保留比例存入 `reincarnation_data.preserved_impart`
2. **新角色应用传承**: 创建新角色后，从 `preserved_impart` 读取并写入新角色的 `impart_info`
3. **保留比例**: 基础 0%，每购买一次"传承保留"+20%，5次满级 = 100% 保留

### 10.3 传承卡牌获取（建议）

虽然不在本轮轮回系统范围内，但建议将传承卡牌获取与轮回绑定：

- 轮回时根据最高境界解锁对应品质的卡牌
- 轮回次数里程碑奖励卡牌
- 这样传承系统自然有了实现动力

---

## 11. 成就系统集成

### 11.1 跨世成就保留

成就解锁记录存储到 `reincarnation_data.preserved_achievements`，跨世保留。

新角色创建时，从 `preserved_achievements` 恢复成就解锁状态。

### 11.2 轮回专属成就

新增成就（加入 `config/achievements.json`）：

| 成就名 | 条件类型 | 条件值 | 建议奖励 |
|--------|----------|--------|----------|
| 初入轮回 | `reincarnation_count` | 1 | 轮回修为 +50 |
| 三世轮回 | `reincarnation_count` | 3 | 轮回修为 +200 |
| 十世大能 | `reincarnation_count` | 10 | 轮回修为 +1000 |
| 百世不灭 | `reincarnation_count` | 50 | 轮回修为 +5000 |
| 合道飞升 | `reincarnation_highest_level` | 55 | 轮回修为 +3000 |

需要在 `achievement_manager.py` 的 `_check_condition` 方法中新增 `reincarnation_count` 和 `reincarnation_highest_level` 条件类型。

---

## 12. 每日活跃集成

### 12.1 新增每日任务

在 `managers/activity_manager.py` 中新增：

| 任务ID | 任务名 | 条件 | 积分 |
|--------|--------|------|------|
| `reincarnation_cultivate` | 轮回修炼 | 本轮修为增长 100万 | 15 |
| `reincarnation_break` | 轮回突破 | 本轮突破任意境界 | 20 |

### 12.2 实现方式

在 `ActivityTracker` 的 `TASK_CONFIG` 中新增两个任务条目，在对应的 handler 中调用 `activity_tracker.increment_task(user_id, "reincarnation_cultivate")` 等。

---

## 13. 数值平衡分析

### 13.1 修炼速度影响

| 场景 | 灵根 | 轮回商店 | 丹药 | 总倍率 |
|------|------|----------|------|--------|
| 首次轮回前 | 1.0-1.7 | 0% | 0-15% | 1.0-1.95 |
| 1次轮回后（轮回道果） | 1.5 | 0% | 0-15% | 1.5-1.73 |
| 3次轮回后（轮回道果+商店5次） | 1.5 | +25% | 0-15% | 1.88-2.16 |
| 5次轮回后（真轮回道果+商店10次） | 2.0 | +50% | 0-15% | 3.0-3.45 |
| 10次轮回后（真轮回道果+商店15次） | 2.0 | +75% | 0-15% | 3.5-4.03 |
| 20次轮回后（混沌道果+商店20次） | 2.5 | +100% | 0-15% | 5.0-5.75 |

→ 20次轮回玩家修炼速度约为首次轮回的 3 倍，需要投入数月时间。

### 13.2 时间投入估算

| 阶段 | 预计时间 | 说明 |
|------|----------|------|
| 新手→轮回境初期 | 3-6 周 | 首次轮回前的积累 |
| 收集轮回丹材料 | 3-5 天 | 依赖Boss/秘境掉落 |
| 轮回执行 | 即时 | 消耗轮回丹 |
| 轮回后→轮回境 | 1-3 周 | 有轮回加成，逐渐加速 |
| **单次轮回周期** | **2-4 周**（轮回后） | 随次数递减 |

### 13.3 轮回修为经济

假设玩家平均在渡劫境初期 (49) 轮回，获得 500 基础轮回修为：

| 轮回次数 | 累计修为（含倍率） | 可购买项 |
|----------|-------------------|----------|
| 1 | 500 | 修炼加速×5，或生命强化×6 |
| 3 | 1,700 | 修炼加速×17 |
| 5 | 3,300 | 修炼加速×33 + 突破概率×5 |
| 10 | 9,500 | 大部分商店项可满级 |
| 20 | 24,000 | 全部商店项可满级 |

→ 约 10-15 次轮回可满级商店，之后轮回修为用于里程碑和称号。

---

## 14. 代码修改清单

### 14.1 新增文件

| 文件 | 说明 |
|------|------|
| `managers/reincarnation_manager.py` | 轮回系统核心逻辑 |
| `handlers/reincarnation_handler.py` | 轮回指令处理 |
| `config/reincarnation_config.json` | 轮回配置（修为奖励表、里程碑、商店） |
| `tests/test_reincarnation_manager.py` | 轮回系统测试 |

### 14.2 修改文件

| 文件 | 修改内容 |
|------|----------|
| `data/migration.py` | 新增 v40 migration：创建 `reincarnation_data` 表 |
| `data/data_manager.py` | 新增 `reincarnation_data` CRUD 方法 + `reincarnation_delete_player` 方法 |
| `data/database_extended.py` | 扩展 `DataBaseExtended` 支持轮回数据查询 |
| `handlers/player_handler.py` | 修改 `handle_start_xiuxian` 应用轮回加成；弃道重修保留轮回数据 |
| `core/cultivation_manager.py` | 在 `root_pools` 中激活轮回道果；修改 `_get_random_spiritual_root` 支持保底 |
| `core/breakthrough_manager.py` | 支持 0% 突破率的轮回解锁机制 |
| `managers/achievement_manager.py` | 新增 `reincarnation_count` / `reincarnation_highest_level` 条件类型 |
| `managers/activity_manager.py` | 新增轮回相关每日任务 |
| `config/achievements.json` | 新增轮回专属成就 |
| `config/herbs.json` | 新增轮回丹材料灵药 |
| `config/alchemy_recipes.json` | 新增轮回丹配方 |
| `main.py` | 注册轮回相关指令 |
| `_conf_schema.json` | 新增 `CHAOS_REINCARNATION_SPEED` 配置 |

### 14.3 数据流

```
/main.py 指令注册
    │
    ├─ /轮回 → reincarnation_handler.handle_reincarnation()
    │   ├─ 检查条件 → reincarnation_manager.check_conditions()
    │   ├─ 计算奖励 → reincarnation_manager.calculate_reward()
    │   ├─ 保存数据 → db.save_reincarnation_data()
    │   ├─ 删除角色 → db.reincarnation_delete_player()
    │   ├─ 创建角色 → player_handler.handle_start_xiuxian() (修改版)
    │   └─ 应用加成 → reincarnation_manager.apply_bonuses()
    │
    ├─ /轮回信息 → reincarnation_handler.handle_reincarnation_info()
    │   └─ db.get_reincarnation_data() → 格式化输出
    │
    ├─ /轮回商店 → reincarnation_handler.handle_shop()
    │   └─ db.get_reincarnation_data() → 展示可购买项
    │
    └─ /轮回购买 → reincarnation_handler.handle_purchase()
        └─ reincarnation_manager.purchase_bonus() → 更新 permanent_bonuses
```

---

## 15. 指令清单

| 指令 | 说明 | 权限 |
|------|------|------|
| `/轮回` | 执行轮回（需确认） | 轮回境+ |
| `/轮回信息` | 查看轮回状态 | 所有玩家 |
| `/轮回商店` | 查看轮回修为商店 | 已轮回过 |
| `/轮回购买 <项目>` | 购买永久加成 | 已轮回过 |

---

## 16. 开放问题

| # | 问题 | 建议方案 | 状态 |
|---|------|----------|------|
| 1 | 弃道重修是否保留轮回数据？ | **是** — 弃道只清空角色数据，轮回数据在独立表中不受影响 | 待确认 |
| 2 | 传承卡牌获取系统是否同步实现？ | **否** — 本轮只实现传承保留机制，卡牌获取后续单独实现 | 待确认 |
| 3 | 轮回丹材料是否可交易？ | **是** — 允许玩家间交易，促进经济流通 | 待确认 |
| 4 | 轮回次数是否影响排行榜？ | **新增轮回排行榜** — 按轮回次数排序 | 待确认 |
| 5 | 轮回后宗门贡献是否保留？ | **否** — 宗门相关全部重置 | 待确认 |
| 6 | 混沌道果速度值 2.5 是否过高？ | 需要实际测试，可在配置中调整 | 待确认 |

---

## 附录 A: 轮回修为奖励配置表

```json
{
    "reincarnation_reward_table": {
        "46": 100,
        "47": 200,
        "48": 350,
        "49": 500,
        "50": 700,
        "51": 1000,
        "52": 1500,
        "53": 2200,
        "54": 3000,
        "55": 5000,
        "56": 8000,
        "57": 12000
    },
    "reincarnation_currency_multiplier": {
        "1": 1.0,
        "3": 1.2,
        "5": 1.2,
        "10": 1.5,
        "20": 1.5,
        "50": 2.0
    },
    "root_floor_by_reincarnation_count": {
        "0": null,
        "1": "TRUE",
        "3": "WUXING",
        "5": "VARIANT",
        "10": "HEAVENLY",
        "20": "DRAGON"
    },
    "milestone_roots": {
        "1": "轮回道果",
        "5": "真轮回道果",
        "20": "混沌道果"
    },
    "breakthrough_unlock": {
        "44": {"required_reincarnation": 0, "unlocked_rate": 0.01},
        "45": {"required_reincarnation": 0, "unlocked_rate": 0.01},
        "46": {"required_reincarnation": 1, "unlocked_rate": 0.01},
        "47": {"required_reincarnation": 1, "unlocked_rate": 0.01},
        "48": {"required_reincarnation": 1, "unlocked_rate": 0.01},
        "49": {"required_reincarnation": 1, "unlocked_rate": 0.005},
        "50": {"required_reincarnation": 1, "unlocked_rate": 0.005},
        "51": {"required_reincarnation": 1, "unlocked_rate": 0.005},
        "52": {"required_reincarnation": 3, "unlocked_rate": 0.005},
        "53": {"required_reincarnation": 3, "unlocked_rate": 0.005},
        "54": {"required_reincarnation": 3, "unlocked_rate": 0.005},
        "55": {"required_reincarnation": 5, "unlocked_rate": 0.001},
        "56": {"required_reincarnation": 5, "unlocked_rate": 0.001},
        "57": {"required_reincarnation": 5, "unlocked_rate": 0.001}
    },
    "shop_items": {
        "cultivation_speed": {"cost": 100, "value": 0.05, "max_purchases": 20},
        "breakthrough_bonus": {"cost": 150, "value": 1, "max_purchases": 10},
        "initial_hp": {"cost": 80, "value": 500, "max_purchases": 30},
        "initial_atk": {"cost": 80, "value": 100, "max_purchases": 30},
        "gold_bonus": {"cost": 120, "value": 0.10, "max_purchases": 10},
        "pill_effect_bonus": {"cost": 200, "value": 0.10, "max_purchases": 5},
        "death_protection": {"cost": 300, "value": 0.95, "max_purchases": 10},
        "impart_preserve_ratio": {"cost": 500, "value": 0.20, "max_purchases": 5}
    }
}
```
