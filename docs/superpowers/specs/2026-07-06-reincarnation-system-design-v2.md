# 轮回系统设计文档 v2.0 (Reincarnation System Design)

> **项目:** astrbot_plugin_monixiuxian2 — 文字修仙放置游戏插件
> **日期:** 2026-07-06（v1 原始日期: 2026-06-19）
> **状态:** Draft
> **版本:** v2.0
> **作者:** Claude Code + ENRIN233

---

## 1. 概述

### 1.1 定义

**轮回** 是玩家达到轮回境后的主动成长机制，区别于弃道重修的惩罚性重置。轮回保留部分力量，重新开始修炼旅程，形成"积累→轮回→更强→再积累"的长期循环。

### 1.2 核心理念

| 机制 | 弃道重修 | 轮回 |
|------|----------|------|
| **性质** | 惩罚性重置 | 成长性进化 |
| **门槛** | 无境界要求 | 轮回境(46级) + 轮回丹 |
| **保留** | 无（全删） | 轮回修为、道果、神通、成就 |
| **CD** | 7天 | 无（消耗材料） |
| **定位** | 失误重来 | 核心长期目标 |

### 1.3 设计目标

- **耐玩性**: 轮回次数驱动的渐进式奖励，50+ 次轮回的长期目标
- **低疲劳**: 被动收益为主，关键决策点少而有意义
- **主题契合**: 利用已有的"轮回道果"伏笔（`REINCARNATION_SPEED=4.0`、`TRUE_REINCARNATION_SPEED=5.0`），自然融入修仙世界观
- **系统联动**: 与突破、炼丹、锻造、成就、传承等现有系统深度整合

---

## 2. 现有代码分析（v2 更新）

### 2.1 关键变化对比（2026-06-19 → 2026-07-06）

| 项目 | v1 设计假设 | 实际现状（v2） | 影响 |
|------|-----------|--------------|------|
| **DB最新版本** | 未确定 | **v40（锻造系统）** | 轮回需为 **v41** |
| **REINCARNATION_SPEED** | 假设 1.5 | 配置为 **4.0** | 轮回道果速度极高，需下调或保留为高价值 |
| **TRUE_REINCARNATION_SPEED** | 假设 2.0 | 配置为 **5.0** | 同理，真轮回道果速度极高 |
| **0%突破率墙** | 大乘境中期起全0% | **仅合道境圆满(57)为0%**，其余1% | 突破解锁设计需彻底重做 |
| **突破上限** | 未提及 | 合体境+上限 **10%**（`get_max_breakthrough_rate`） | 轮回商店的突破概率加成设计需考虑上限 |
| **失败累积** | 未提及 | 轮回境46+ **已失效**（代码已实现） | 轮回后突破更依赖轮回商店和丹药加成 |
| **delete_player_cascade** | 存在孤立数据风险 | **已全面处理**（含player_skills/weapon_instances） | 简化设计，保留列表调整即可 |
| **锻造系统** | 不存在 | **v40已添加**完整锻造系统 | 轮回需处理 `weapon_instances` 降级保留 |
| **_CHAOS_REINCARNATION_SPEED_** | 需新增 | 仍**不存在** | 需在 `_conf_schema.json` 新增 |
| **轮回根在 root_pools** | 需加入 | 仍**不在** root_pools | 保持确定性解锁，不进入随机池 |

### 2.2 当前突破率现状（关键发现）

从 `config/level_config.json` 分析，高境界段的实际 `success_rate`：

| 境界段 | Index | 当前 success_rate | 突破上限 (get_max_breakthrough_rate) |
|--------|-------|:-----------------:|:------------------------------------:|
| 合体境(初期~圆满) | 40-42 | 0.01 (1%) | 10% |
| 大乘境(初期~圆满) | 43-45 | 0.01 (1%) | 10% |
| 轮回境(初期~圆满) | 46-48 | 0.01 (1%) | 10% |
| 渡劫境(初期~圆满) | 49-51 | 0.01 (1%) | 10% |
| 飞升境(初期~圆满) | 52-54 | 0.01 (1%) | 10% |
| 合道境(初期~中期) | 55-56 | 0.01 (1%) | 10% |
| **合道境圆满** | **57** | **0.0 (0%)** | **10%** |

**核心结论**: 
- 仅合道境圆满(57)是真正的0%墙，需要特殊突破手段（如轮回次数解锁）
- 其他高境界段的1%基础率 + 丹药/心法加成 → 实际可达约3%-8%，无需特殊处理
- 但突破上限10%意味着即使用满所有加成（丹药+心法+失败累积），也不可能达到更高
- 轮回后失败累积失效(46+) → 突破依赖变得不同

### 2.3 已有轮回伏笔代码

| 伏笔 | 位置 | 当前状态 |
|------|------|---------|
| `轮回道果`→`REINCARNATION_SPEED`(4.0) | `cultivation_manager.py:93-94`, `_conf_schema.json:156` | 已定义速度，**不在** root_pools |
| `真轮回道果`→`TRUE_REINCARNATION_SPEED`(5.0) | `cultivation_manager.py:95`, `_conf_schema.json:162` | 已定义速度，**不在** root_pools |
| 轮回道果/真轮回道果 描述 | `cultivation_manager.py:285-287` | "轮回千次不灭，只为臻至巅峰" |
| 轮回境 突破上限 | `breakthrough_manager.py:33-34` | get_max_breakthrough_rate: >=40级上限10% |
| 轮回境后失败累积失效 | `breakthrough_manager.py:119-127` | `player.level_index < 46` 判断已实现 |
| 轮回境 BOSS 模板 | `managers/boss_manager.py:42` | name="轮回", level_index=51 |
| 装备"轮回诀" | `config/items.json` index 1718 | 已有物品定义 |
| 技能"炙炎轮回" | `config/skills.json` index 351 | 已有技能定义 |

---

## 3. 轮回触发与流程

### 3.1 触发条件

| 条件 | 说明 |
|------|------|
| **境界要求** | `player.level_index >= 46`（轮回境初期） |
| **状态要求** | 空闲状态（非闭关/探索/交易等） |
| **消耗物品** | 1 枚轮回丹（通过炼丹系统炼制，非服用丹药指令直接消耗） |
| **无贷款** | 无未偿还银行贷款 |
| **指令** | `/轮回` → 展示信息并确认 → 执行 |

### 3.2 执行流程

```
玩家输入 /轮回
    │
    ├─ 检查条件（境界、状态、轮回丹、贷款）
    │
    ├─ 展示轮回预览：
    │   "🌀 轮回预览
    │    ━━━━━━━━━━━━━━━━━━━━
    │    你即将踏入轮回...
    │    
    │    本次轮回将获得: {n} 轮回修为
    │    历史最高境界: {highest_level}
    │    轮回次数: 第 {n+1} 次
    │    
    │    ✓ 将保留: 道号、已学神通、轮回数据
    │    ✓ 有条件保留: 锻造武器(前3把)、储物戒等级
    │    ✗ 将重置: 境界、修为、灵石、丹药、装备、宗门...
    │    ━━━━━━━━━━━━━━━━━━━━
    │    确认轮回？(输入 轮回确认)"
    │
    ├─ 玩家输入 "轮回确认"
    │
    ├─ 执行轮回（事务保护 BEGIN IMMEDIATE）：
    │   1. 计算本轮轮回修为奖励（基于最高境界+次数倍率）
    │   2. 读取 player_skills 写入 reincarnation_data.preserved_skills
    │   3. 评估锻造武器保留（品质最高/装备中的前3把写入 preserved_weapons）
    │   4. 消耗轮回丹（从 pills_inventory 扣除）
    │   5. 插入重写 reincarnation_data 表
    │   6. 设置前 player 数据快照到 reincarnation_data.snapshot
    │   7. 执行 reincarnation_delete_player（选择性删除）
    │   8. 自动创建新角色（继承道号，灵根按里程碑确定性分配）
    │   9. 恢复 player_skills / 保留的锻造武器 / 传承加成
    │  10. 应用轮回永久加成（读取 permanent_bonuses 写入 player）
    │  11. 检查里程碑奖励（解锁新灵根/称号）
    │  12. 删除 reincarnation_data.snapshot（完成轮回）
    │  13. 发送轮回结果报告
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
  修炼速度: +15% (进度 3/20)
  突破概率: +3% (进度 2/10)
  初始生命: +1500 (进度 3/30)
  攻击强化: +300 (进度 3/30)
  灵石加成: +20% (进度 2/10)
━━━━━━━━━━━━━━━━━━━━
灵根: 轮回道果 ✓
解锁灵根进度: 真轮回道果(需5次) ⌛
锻造武器保留: 可保留 3 件
```

### 3.4 轮回排行榜

新增 `/轮回排行` 指令，按轮回次数倒序排名：

```
🌀 轮回排行
━━━━━━━━━━━━━━━━━━━━
No.1  飞升大能  轮回 12 次  最高: 飞升境圆满
No.2  轮回尊者  轮回 8 次   最高: 渡劫境中期
No.3  仙途行者  轮回 5 次   最高: 轮回境圆满
...
━━━━━━━━━━━━━━━━━━━━
你的轮回: 第 3 次 (排名第 7)
```

---

## 4. 数据模型（v2 更新）

### 4.1 `reincarnation_data` 表

```sql
CREATE TABLE IF NOT EXISTS reincarnation_data (
    user_id TEXT PRIMARY KEY,
    reincarnation_count INTEGER DEFAULT 0,
    highest_level_index INTEGER DEFAULT 0,
    reincarnation_currency INTEGER DEFAULT 0,
    total_currency_earned INTEGER DEFAULT 0,
    shop_purchases TEXT DEFAULT '{}',
    permanent_bonuses TEXT DEFAULT '{}',
    preserved_skills TEXT DEFAULT '[]',
    preserved_weapons TEXT DEFAULT '[]',
    preserved_achievements TEXT DEFAULT '{}',
    preserved_storage_ring TEXT DEFAULT '',
    preserved_bank_vip INTEGER DEFAULT 0,
    last_reincarnation_time INTEGER DEFAULT 0,
    first_reincarnation_time INTEGER DEFAULT 0,
    snapshot TEXT DEFAULT '{}',
    created_at INTEGER DEFAULT 0
);
```

#### 字段变更说明（v1 → v2）

| 字段 | v1 | v2（更新） | 原因 |
|------|-----|------------|------|
| `preserved_impart` | JSON 字段 | **移除** | 传承保留与轮回商店解耦（见 §10） |
| `preserved_skills` | 隐含（通过保留表数据） | **显式 JSON 数组**, 存储 `["skill_name", ...]` | 确保神通跨世保留的确定性 |
| `preserved_weapons` | 不存在 | **新增** `["instance_id", ...]` | 轮回可保留前N把锻造武器（见 §14） |
| `snapshot` | 不存在 | **新增** 轮回前玩家数据快照 | 轮回确认后的"反悔"机制 |
| `first_reincarnation_time` | 不存在 | **新增** | 记录首次轮回时间，计算轮回周期 |

### 4.2 `permanent_bonuses` JSON 结构（v2 更新）

```json
{
    "cultivation_speed": {"level": 3, "value": 0.15},
    "breakthrough_bonus": {"level": 2, "value": 2},
    "initial_hp": {"level": 3, "value": 1500},
    "initial_atk": {"level": 3, "value": 300},
    "gold_bonus": {"level": 2, "value": 0.20},
    "pill_effect_bonus": {"level": 1, "value": 0.10},
    "death_protection": {"level": 1, "value": 0.95},
    "breakthrough_limit_break": {"level": 0, "value": 0}
}
```

结构变更：改用 `{"level": N, "value": V}` 格式，支持按等级显示进度。

### 4.3 `shop_purchases` JSON 结构

```json
{
    "cultivation_speed": 3,
    "breakthrough_bonus": 2,
    "initial_hp": 3,
    "initial_atk": 3,
    "gold_bonus": 2,
    "pill_effect_bonus": 1,
    "death_protection": 1,
    "breakthrough_limit_break": 0
}
```

记录每个商店项目的总购买次数。

### 4.4 数据库迁移

新增 migration **v41**（v40 已被锻造系统占用）：

```python
@migration(version=41)
async def v41_add_reincarnation_table(db, config_manager):
    """v41: 轮回系统 — reincarnation_data 表"""
    await db.execute("""
        CREATE TABLE IF NOT EXISTS reincarnation_data (
            user_id TEXT PRIMARY KEY,
            reincarnation_count INTEGER DEFAULT 0,
            highest_level_index INTEGER DEFAULT 0,
            reincarnation_currency INTEGER DEFAULT 0,
            total_currency_earned INTEGER DEFAULT 0,
            shop_purchases TEXT DEFAULT '{}',
            permanent_bonuses TEXT DEFAULT '{}',
            preserved_skills TEXT DEFAULT '[]',
            preserved_weapons TEXT DEFAULT '[]',
            preserved_achievements TEXT DEFAULT '{}',
            preserved_storage_ring TEXT DEFAULT '',
            preserved_bank_vip INTEGER DEFAULT 0,
            last_reincarnation_time INTEGER DEFAULT 0,
            first_reincarnation_time INTEGER DEFAULT 0,
            snapshot TEXT DEFAULT '{}',
            created_at INTEGER DEFAULT 0
        )
    """)
    await db.commit()
```

---

## 5. 轮回保留与重置

### 5.1 保留项（跨世永恒）

| 保留项 | 存储方式 | 说明 |
|--------|----------|------|
| 道号 | 新角色创建时从旧角色读取 | 轮回不改名 |
| 轮回次数 | `reincarnation_data.reincarnation_count` | 核心计数器 |
| 历史最高境界 | `reincarnation_data.highest_level_index` | 里程碑判定用 |
| 轮回修为 | `reincarnation_data.reincarnation_currency` | 轮回专属货币（跨世） |
| 轮回商店加成 | `reincarnation_data.permanent_bonuses` | 已购买的永久属性加成 |
| 已学神通 | 写入 `reincarnation_data.preserved_skills` 再恢复 | 神通跨世保留（确保不丢失） |
| 锻造武器 | `reincarnation_data.preserved_weapons`（最多3把） | 保留装备中/最高品质的武器 |
| 成就解锁 | `reincarnation_data.preserved_achievements` | 跨世成就解锁记录 |
| 储物戒等级 | `reincarnation_data.preserved_storage_ring` | 保留储物戒等级，内容清空 |
| 银行VIP | `reincarnation_data.preserved_bank_vip` | 保留VIP等级 |

### 5.2 重置项（归零重来）

| 重置项 | 说明 |
|--------|------|
| 境界 → 江湖好手 (0) | 从头修炼 |
| 修为/经验 → 0 | 重新积累 |
| 灵石 → 初始值（500） | 重新赚取 |
| 灵根 → 按里程碑确定性分配 | 轮回次数决定品质 |
| 装备/功法/辅修 → 清空 | 重新获取 |
| 丹药背包/储物戒内容 → 清空 | 重新收集 |
| 永久丹药增益 → 清空 | 重新服用（跨世可再服用） |
| 宗门 → 退出 | 需重新加入 |
| 洞天福地/灵田 → 清空 | 重新建设 |
| 银行账户/贷款 → 清空 | 重新开始 |
| 锻造经验/等级 → 重置为1 | 重新提升锻造等级 |
| 已装备的锻造武器 → 卸下 | 武器本身保留在武器库中 |

### 5.3 `reincarnation_delete_player` 方法

不同于 `delete_player_cascade`（硬删除全部关联数据），轮回需要一个新的删除方法：

```python
async def reincarnation_delete_player(self, user_id: str):
    """轮回级联删除（保留轮回数据和神通）
    
    与 delete_player_cascade 的区别：
    - 不删 player_skills（轮回后恢复）
    - 不删 weapon_instances（保留前3把）
    - 不删 reincarnation_data（核心数据）
    """
    await self.conn.execute("BEGIN IMMEDIATE")
    try:
        tables = [
            ("DELETE FROM dungeon_runs WHERE user_id = ?", (user_id,)),
            ("UPDATE trades SET status = 'cancelled' WHERE (initiator_id = ? OR target_id = ?) AND status = 'pending'",
             (user_id, user_id)),
            ("DELETE FROM consignment_listings WHERE seller_id = ?", (user_id,)),
            ("DELETE FROM gm_compensation_claims WHERE user_id = ?", (user_id,)),
            ("DELETE FROM blessed_lands WHERE user_id = ?", (user_id,)),
            ("DELETE FROM spirit_farms WHERE user_id = ?", (user_id,)),
            ("DELETE FROM bank_accounts WHERE user_id = ?", (user_id,)),
            ("UPDATE bank_loans SET status = 'bad_debt' WHERE user_id = ? AND status = 'active'", (user_id,)),
            ("DELETE FROM bounty_tasks WHERE user_id = ?", (user_id,)),
            ("DELETE FROM dual_cultivation WHERE user_id = ?", (user_id,)),
            ("DELETE FROM dual_cultivation_requests FROM user_id = ? OR target_id = ?", (user_id, user_id)),
            ("DELETE FROM user_cd WHERE user_id = ?", (user_id,)),
            ("DELETE FROM buff_info WHERE user_id = ?", (user_id,)),
            ("DELETE FROM combat_cooldowns WHERE user_id = ?", (user_id,)),
            ("DELETE FROM pending_gifts WHERE sender_id = ? OR receiver_id = ?", (user_id, user_id)),
            ("DELETE FROM player_buffs WHERE user_id = ?", (user_id,)),
            ("DELETE FROM player_daily_activity WHERE user_id = ?", (user_id,)),
            ("DELETE FROM achievement_progress WHERE user_id = ?", (user_id,)),
            # 不删 player_skills（轮回后恢复）
            # 不删 weapon_instances（保留前3把）
            # 只删除非保留的 weapons（排除 preserved_weapons 中的）
            # players 表最后删除
            ("DELETE FROM players WHERE user_id = ?", (user_id,)),
        ]
        for sql, params in tables:
            await self.conn.execute(sql, params)
        await self.conn.commit()
    except Exception:
        await self.conn.rollback()
        raise
```

### 5.4 新角色创建时的轮回加成应用

```python
# 在 create_player 后调用
async def apply_reincarnation_bonuses(self, player: Player):
    reinc_data = await self.db.get_reincarnation_data(player.user_id)
    if not reinc_data:
        return

    bonuses = json.loads(reinc_data.permanent_bonuses)

    # 初始属性加成（直接加到 player 上）
    player.hp += bonuses.get("initial_hp", {}).get("value", 0)
    player.atk += bonuses.get("initial_atk", {}).get("value", 0)

    # cultivation_speed 不直接写 player，在修炼计算时读取
    # breakthrough_bonus 在突破率计算时读取
    # gold_bonus 在签到/掉落时读取
    # death_protection 在突破死亡时读取

    # 恢复神通
    preserved_skills = json.loads(reinc_data.preserved_skills)
    for skill_name in preserved_skills:
        await self.db.add_player_skill(player.user_id, skill_name)

    # 恢复银行VIP等级
    if reinc_data.preserved_bank_vip > 0:
        player.bank_vip_tier = reinc_data.preserved_bank_vip
```

---

## 6. 轮回奖励体系

### 6.1 轮回修为计算

每次轮回，根据本轮最高境界获得轮回修为：

| 本轮最高境界 | level_index | 基础轮回修为 |
|-------------|:-----------:|:------------:|
| 轮回境初期 | 46 | 100 |
| 轮回境中期 | 47 | 200 |
| 轮回境圆满 | 48 | 350 |
| 渡劫境初期 | 49 | 500 |
| 渡劫境中期 | 50 | 700 |
| 渡劫境圆满 | 51 | 1,000 |
| 飞升境初期 | 52 | 1,500 |
| 飞升境中期 | 53 | 2,200 |
| 飞升境圆满 | 54 | 3,000 |
| 合道境初期 | 55 | 5,000 |
| 合道境中期 | 56 | 8,000 |
| 合道境圆满 | 57 | 12,000 |

**奖励公式**:
```
最终奖励 = base_reward × milestone_multiplier × (1 + max(0, (reincarnation_count - 1) * 0.01))
```

其中 `milestone_multiplier` 由里程碑倍率表决定：

| 轮回次数 | 倍率 |
|----------|:----:|
| 1-2 | ×1.0 |
| 3-4 | ×1.2 |
| 5-9 | ×1.3 |
| 10-19 | ×1.5 |
| 20-49 | ×1.8 |
| 50+ | ×2.0 |

同时有一个**小成长倍率**：每次轮回多获得 1% 的基础奖励，鼓励持续轮回。

### 6.2 里程碑奖励

| 轮回次数 | 解锁奖励 |
|----------|----------|
| 第 1 次 | 解锁 **轮回道果** 灵根（修炼速度 ×4.0） |
| 第 3 次 | 轮回修为获取 +20%（里程碑倍率从 ×1.0 → ×1.2） |
| 第 5 次 | 解锁 **真轮回道果** 灵根（修炼速度 ×5.0） |
| 第 10 次 | 轮回修为获取 +50%，解锁称号 "十世大能" |
| 第 20 次 | 解锁 **混沌道果** 灵根（修炼速度 ×6.0），解锁称号 "轮回不灭" |
| 第 50 次 | 轮回修为获取 +100%，解锁称号 "百世仙尊" |

> **设计说明**: REINCARNATION_SPEED 配置值为 4.0，为保持平衡，轮回道果速度设为 4.0（而非旧版设计的 1.5）。这在修炼速度上已经是超越级的加成，加上轮回商店的加速，后期修炼速度会极快。若测试中速度过快，可在 `_conf_schema.json` 中调低配置值。

### 6.3 轮回修为商店

使用轮回修为购买永久加成（跨世不消失）：

| 加成项 | ID | 单价 | 单次效果 | 购买上限 | 满级效果 |
|--------|-----|:----:|:--------:|:--------:|:--------:|
| 修炼加速 | `cultivation_speed` | 100 | 修炼速度 +5% | 20 次 | +100% |
| 突破概率 | `breakthrough_bonus` | 150 | 突破基础率 +1% | 10 次 | +10% |
| 生命强化 | `initial_hp` | 80 | 初始HP +500 | 30 次 | +15000 |
| 攻击强化 | `initial_atk` | 80 | 初始ATK +100 | 30 次 | +3000 |
| 灵石加成 | `gold_bonus` | 120 | 灵石获取 +10% | 10 次 | +100% |
| 丹药增效 | `pill_effect_bonus` | 200 | 永久丹药效果 +10% | 5 次 | +50% |
| 死亡保护 | `death_protection` | 300 | 死亡率 ×0.95 | 10 次 | ×0.60 |
| 突破极限 | `breakthrough_limit_break` | 500 | 突破上限 +2% | 5 次 | +10% |

**V2 新增商品**: **突破极限**（`breakthrough_limit_break`）
- 功能：每级 +2% 突破成功率上限
- 作用：突破合体境后（上限10%），购买此加成可提升上限至 20%
- 与经济平衡：高级境界1%基础率 + 10%上限 → 全部加成后可达15% + 突破极限10% → 最高约20-25%

商店指令：
- `/轮回商店` — 列出可购买项目及当前等级
- `/轮回购买 <项目ID>` — 扣除轮回修为，提升加成等级

---

## 7. 灵根系统集成

### 7.1 灵根里程碑分配（v2 更新）

轮回时灵根**不再随机分配**，改为**确定性分配**。轮回次数决定了灵根品质：

| 轮回次数 | 获得灵根 | 速度倍率 |
|----------|---------|:--------:|
| 0（首次轮回前） | 常规随机（同创建角色） | 按现有随机池 |
| 1-4 次 | **轮回道果** | ×4.0 |
| 5-19 次 | **真轮回道果** | ×5.0 |
| 20+ 次 | **混沌道果** | ×6.0（需新增） |

> **变更理由**: 旧版设计混合了"灵根保底+里程碑解锁"两个机制，过于复杂。新版直接按里程碑**替换**灵根，实现简单、预期明确、玩家感受好。

### 7.2 新增混沌道果配置

需要新增以下配置：

**在 `_conf_schema.json` 的 `SPIRIT_ROOT_SPEEDS` 中**：

```json
"CHAOS_REINCARNATION_SPEED": {
    "description": "混沌道果",
    "type": "float",
    "default": 6.0,
    "hint": "轮回万次不灭，混沌之中证得无上道果。"
}
```

**在 `core/cultivation_manager.py` 中**：

```python
"混沌道果": "CHAOS_REINCARNATION_SPEED",

# 描述
"混沌道果": "【混沌】轮回万次不灭，混沌之中证得无上道果"
```

### 7.3 灵根分配逻辑

```python
def assign_reincarnation_root(reincarnation_count: int) -> str:
    """按轮回次数确定性分配灵根"""
    if reincarnation_count >= 20:
        return "混沌道果"
    elif reincarnation_count >= 5:
        return "真轮回道果"
    elif reincarnation_count >= 1:
        return "轮回道果"  # v1 里程碑
    # 首次创建不在此方法内
    return self._get_random_spiritual_root()  # 常规随机（不会走到）
```

轮回灵根**不进入** `root_pools`（旧设计中的 `REINCARNATION`/`TRUE_REINCARNATION` 类别无需添加），保持确定性。

---

## 8. 突破系统集成

### 8.1 0% 突破率墙的解决方案

唯一 0% 墙在 **合道境圆满 (index 57)**。解决方案：

```python
# 在 calculate_breakthrough_success_rate 中
base_rate = level_data[next_level_index].get("success_rate", 0.5)

# 特殊处理：合道境圆满的 0% 率
if base_rate == 0 and next_level_index == 57:
    # 检查是否有轮回数据
    reinc_data = await self.db.get_reincarnation_data(player.user_id)
    if not reinc_data or reinc_data.reincarnation_count < 5:
        return 0.0, "合道境圆满需要至少 5 次轮回才能尝试突破！"
    # 解锁基础率（受上限影响，实际最高 10% + 突破极限加成）
    base_rate = 0.01  # 解锁到 1%
```

**设计理由**: 
- 合道境圆满（57级）是**最终境界**，只有轮回 5 次以上的玩家才可尝试
- 解锁后 1% 基础率，配合心法+丹药+突破极限加成，理论上限约 15-20%
- 这不是硬锁定，而是"**门槛**"——轮回够多次自然解锁
- 合道境圆满突破后应触发特殊事件（TODO: 后续版本扩展飞升系统）

### 8.2 突破概率上限优化

`get_max_breakthrough_rate` 对合体境(40)以上限制 **10%**。轮回商店新增的 `breakthrough_limit_break` 可突破此上限：

```python
def get_max_breakthrough_rate(target_level_index, reinc_data=None):
    base_max = 0.10 if target_level_index >= 40 else (0.25 if target_level_index >= 25 else 1.0)
    
    # 轮回突破极限加成
    if reinc_data:
        bonuses = json.loads(reinc_data.permanent_bonuses)
        limit_break_level = bonuses.get("breakthrough_limit_break", {}).get("level", 0)
        base_max += limit_break_level * 0.02  # 每级 +2% 上限
    
    return min(base_max, 0.50)  # 硬上限 50%
```

### 8.3 轮回境后的突破困境

轮回境后（level >= 46），原有机制会失效：
1. **失败累积失效**（已实现）：46级后 `level_up_rate` 不再增长
2. **突破上限 10%**（已实现）：合体境起限制

这使得轮回后玩家的突破更加依赖：
- **心法加成**（最高约 10-15%）：挑选带突破概率的心法
- **破境丹**（最高约 5-10%）：通用丹+境界丹叠加
- **轮回商店**（突破概率 +10%）：需要10次购买（1500轮回修为）
- **突破极限**（上限 +10%）：需要5次购买（2500轮回修为）

**结论**: 轮回5次后，通过上述组合，高级境界的实际突破率可达约 **15%-20%**。

---

## 9. 炼丹系统集成

### 9.1 轮回丹配方

轮回丹通过炼丹系统炼制（通用 `match_recipe` 仅需配置即可）：

**新增灵药**（加入 `config/herbs.json`）：

| 灵药名 | 品级 | h_a_c 类型 | 获取途径 |
|--------|:----:|:----------:|----------|
| 天道碎片 | 九品 | 特殊(0) | 世界Boss概率掉落（ultra档位） |
| 轮回之水 | 八品 | 寒性(-1) | 秘境稀有掉落（rift level 5） |
| 涅槃之火 | 八品 | 热性(+1) | 探险副本BOSS层奖励或悬赏 |

**新增配方**（加入 `config/alchemy_recipes.json`）：

```json
{
    "name": "轮回丹",
    "elixir_config": {
        "天道碎片": {"min_power": 1},
        "轮回之水": {"min_power": 2},
        "涅槃之火": {"min_power": 2}
    },
    "mix_exp": 500,
    "description": "服下此丹，可踏入轮回，保留前世部分力量重新修炼。"
}
```

**关键**: 炼丹系统的 `match_recipe` 和 `check_harmony` 已是通用逻辑，新增配方只需修改 JSON 配置文件，无需改代码。

### 9.2 轮回丹使用

- 轮回丹不通过"服用丹药"指令使用
- 在 `/轮回` 指令执行时，从 `pills_inventory` 自动检测并消耗
- 这一设计避免了"误服"轮回丹

### 9.3 轮回丹材料获取

| 材料 | 稳定获取 | 效率获取 | 难度 |
|------|---------|---------|:----:|
| 轮回之水 | 秘境5级（日一次） | 探险副本选择寒性节点 | 中 |
| 涅槃之火 | 世界Boss（ultra档位） | 探险副本BOSS层 | 中 |
| 天道碎片 | 世界Boss 5%概率 | ultra Boss 3%概率 | 高 |

**设计目标**: 玩家约需 **3-7 天** 收集一份轮回丹材料，每次轮回后重新收集。玩家可以选择冲高境界（需要更多时间）或快速轮回（消耗轮回丹更快）。

---

## 10. 传承系统集成

### 10.1 当前状态

- 传承系统 (`impart_manager.py`) 提供 5 个属性的百分比加成（`impart_hp_per`/`impart_mp_per`/`impart_atk_per`/`impart_know_per`/`impart_burst_per`）
- `config/impart_cards.json` 定义了 105 张卡牌，但**收集系统未实现**
- 传承通过 PvP 对战（传承挑战）获得

### 10.2 轮回与传承的联动（v2 精简方案）

v1 设计将传承保留作为轮回商店的付费商品（传承保留×5级=100%保留）。**v2 简化方案**：

**传承不再在轮回时保留**。原因：

1. 传承通过 PvP 获取，重新获取有明确途径
2. 低等级玩家保留高额传承加成会破坏前期平衡
3. 轮回的核心价值是灵根和突破解锁，传承保留不是必要功能

**替代方案**: 轮回次数**增加传承获取上限**：
- 每次轮回后，传承卡牌的每日获取上限 +1
- 轮回次数提升卡牌掉落品质上限
- 这样既体现轮回的价值，又不增加保留逻辑的复杂度

---

## 11. 成就系统集成

### 11.1 跨世成就保留

将成就解锁记录写入 `reincarnation_data.preserved_achievements`。

```python
# 轮回时保存
reinc_data.preserved_achievements = json.dumps(player.achievement_data["unlocked"])

# 新角色创建时恢复
player_achievement_data = json.loads(player.achievement_data)
player_achievement_data["unlocked"] = json.loads(reinc_data.preserved_achievements)
player.set_achievement_data(player_achievement_data)
```

### 11.2 新增条件类型

在 `managers/achievement_manager.py` 的 `_check_condition` 中新增：

```python
elif cond_type == "reincarnation_count":
    return self._check_reincarnation_condition(player.user_id, value)

elif cond_type == "reincarnation_highest_level":
    return self._check_reincarnation_highest_level(player.user_id, value)
```

同时需要在 `AchievementManager` 中注入数据库访问能力（或通过构造函数传入 `db`）。

### 11.3 轮回专属成就

| 成就ID | 成就名 | 条件类型 | 条件值 | 建议奖励 |
|--------|-------|:--------:|:------:|:--------:|
| `first_reincarnation` | 初入轮回 | reincarnation_count >= 1 | 1 | 轮回修为 +50 |
| `three_reincarnations` | 三世轮回 | reincarnation_count >= 3 | 3 | 轮回修为 +200 |
| `ten_reincarnations` | 十世大能 | reincarnation_count >= 10 | 10 | 轮回修为 +1000 |
| `fifty_reincarnations` | 百世不灭 | reincarnation_count >= 50 | 50 | 轮回修为 +5000 |
| `highest_dutie` | 合道飞升 | reincarnation_highest_level >= 55 | 55 | 轮回修为 +3000 |

---

## 12. 每日活跃集成

在 `managers/activity_manager.py` 的 `TASK_DEFINITIONS` 中新增：

| 任务ID | 任务名 | 条件 | 活跃值 |
|--------|-------|------|:------:|
| `reincarnation_cultivate` | 轮回修炼 | 本轮修为增长达 100万 | 15 |
| `reincarnation_break` | 轮回突破 | 本轮突破任意境界 | 20 |

**实现方式**: 在 `cultivation_manager.py` 的修炼结束时和 `breakthrough_manager.py` 突破成功后调用 `activity_tracker.increment_task(user_id, "reincarnation_cultivate")` 等。

---

## 13. 数值平衡分析（v2 更新）

### 13.1 修炼速度影响

| 场景 | 灵根速度 | 商店速度加成 | 其他加成 | 总倍率 |
|------|:--------:|:-----------:|:--------:|:------:|
| 首次轮回前（最优） | 2.5（异世界） | 0% | 0-25% | 2.5-3.13 |
| **1次轮回后**（轮回道果） | **4.0** | 0% | 0-25% | **4.0-5.0** |
| 3次轮回后（轮回道果+商店5次） | 4.0 | +25% | 0-25% | 5.0-6.25 |
| **5次轮回后**（真轮回道果+商店10次） | **5.0** | +50% | 0-25% | **7.5-9.38** |
| 10次轮回后（真轮回道果+商店15次） | 5.0 | +75% | 0-25% | 8.75-10.94 |
| **20次轮回后**（混沌道果+商店20次） | **6.0** | +100% | 0-25% | **12.0-15.0** |

> **v2 对比 v1**: 由于灵根速度从 1.5/2.0/2.5 大幅提升到 4.0/5.0/6.0，高速阶段比 v1 快了 2-3 倍。这有助于缩短后期"修炼-突破-轮回"循环周期。

### 13.2 时间投入估算

| 阶段 | 预计时间（v2） | 说明 |
|------|:-------------:|------|
| 新手→轮回境初期 | 2-4 周 | 首次轮回前积累 |
| 收集轮回丹材料 | 3-7 天 | Boss/秘境/副本 |
| 轮回后→轮回境（第1次） | 1-2 周 | 轮回道果4.0速加速 |
| 轮回后→轮回境（第5次后） | 3-5 天 | 真轮回道果+商店加速 |
| 轮回后→轮回境（第20次后） | 1-2 天 | 混沌道果+商店满加速 |
| **单次轮回周期** | **前期 2-4 周 → 后期 1-3 天** | 随次数递减 |

### 13.3 轮回修为经济

假设玩家平均在渡劫境初期（49级，500基础修为）轮回：

| 轮回次数 | 累计修为（含倍率） | 可购买项 |
|:--------:|:-----------------:|---------|
| 1 | 500 | 修炼加速×5 / 生命强化×6 |
| 3 | 1,700（×1.2倍率） | 修炼加速×15+突破概率×2 |
| 5 | 3,650（×1.3倍率） | 修炼加速×满+突破概率×5 |
| 10 | 10,250（×1.5倍率） | 大部分商店满级 |
| 20 | 28,000（×1.8倍率） | 全部商店满级 |
| 50 | 70,000（×2倍率） | 满级后修为溢出（用于称号） |

---

## 14. 锻造系统集成

### 14.1 轮回时的武器保留

锻造系统（v40）添加了 `weapon_instances` 表，玩家通过锻造获得武器。轮回时：

**保留规则**:
- 从 `weapon_instances` 中筛选出装备中的 + 品质最高的武器，**最多保留 3 把**
- 保留的武器 instance_id 写入 `reincarnation_data.preserved_weapons`
- 其他武器随轮回删除
- 保留的武器 `is_equipped` 设为 0、`in_storage` 设为 1

**筛选算法**:
```python
def select_preserved_weapons(weapons: list) -> list:
    """选择最多 3 把保留的武器"""
    # 优先级1: 装备槽中的武器（最多2把：武器+防具）
    equipped = [w for w in weapons if w.is_equipped]
    # 优先级2: 品质最高的武器
    quality_order = {"极品": 4, "上品": 3, "中品": 2, "下品": 1}
    unequipped = sorted(
        [w for w in weapons if not w.is_equipped],
        key=lambda w: quality_order.get(w.quality, 0),
        reverse=True
    )
    preserved = equipped + unequipped
    return [w.instance_id for w in preserved[:3]]
```

### 14.2 轮回后的锻造恢复

```python
# 创建新角色后执行
async def restore_preserved_weapons(self, user_id: str, preserved_ids: list):
    """恢复保留的锻造武器"""
    for instance_id in preserved_ids:
        await self.db_extended.update_weapon_instance_status(
            instance_id, user_id, is_equipped=0, in_storage=1
        )
```

---

## 15. 指令清单

| 指令 | 说明 | 权限 | handler 方法 |
|------|------|------|-------------|
| `/轮回` | 执行轮回（需确认） | 轮回境+ | `handle_reincarnation()` |
| `/轮回确认` | 确认执行轮回 | 轮回预览状态 | `handle_reincarnation_confirm()` |
| `/轮回信息` | 查看轮回状态 | 所有玩家 | `handle_reincarnation_info()` |
| `/轮回商店` | 查看轮回商店 | 已轮回过 | `handle_reincarnation_shop()` |
| `/轮回购买 <项目ID>` | 购买永久加成 | 已轮回过 | `handle_reincarnation_purchase()` |
| `/轮回排行` | 轮回次数排行榜 | 所有玩家 | `handle_reincarnation_rank()` |

---

## 16. 代码修改清单

### 16.1 新增文件

| 文件 | 说明 |
|------|------|
| `managers/reincarnation_manager.py` | 轮回系统核心逻辑（条件检查、奖励计算、加成应用、里程碑判定） |
| `handlers/reincarnation_handler.py` | 轮回指令处理（/轮回 /轮回信息 /轮回商店 /轮回购买 /轮回排行） |
| `config/reincarnation_config.json` | 轮回配置（修为奖励表、里程碑、商店物品） |
| `tests/test_reincarnation_manager.py` | 轮回系统测试 |

### 16.2 修改文件

| 文件 | 修改内容 |
|------|----------|
| `data/migration.py` | 新增 **v41 migration**：创建 `reincarnation_data` 表 |
| `data/data_manager.py` | 新增 `reincarnation_data` CRUD 方法（get/upsert/delete）+ `reincarnation_delete_player` 方法 |
| `data/database_extended.py` | 扩展 `DatabaseExtended` 支持轮回数据查询 |
| `handlers/player_handler.py` | 修改 `handle_start_xiuxian` 在角色创建后应用轮回加成；弃道重修保留轮回数据 |
| `core/cultivation_manager.py` | 新增 `CHAOS_REINCARNATION_SPEED` 映射；新增 `assign_reincarnation_root()` 方法；新增混沌道果描述 |
| `core/breakthrough_manager.py` | 合道境圆满(57) 0% 率特殊处理；`get_max_breakthrough_rate` 支持轮回突破极限加成 |
| `handlers/breakthrough_handler.py` | 突破信息展示支持轮回解锁提示 |
| `managers/achievement_manager.py` | 新增 `reincarnation_count` / `reincarnation_highest_level` 条件类型；注入 db 用于检查 |
| `managers/activity_manager.py` | 新增 2 个轮回相关每日任务 |
| `config/achievements.json` | 新增 5 个轮回专属成就 |
| `config/herbs.json` | 新增 3 个轮回丹材料（天道碎片、轮回之水、涅槃之火）|
| `config/alchemy_recipes.json` | 新增 1 个轮回丹配方 |
| `_conf_schema.json` | 新增 `CHAOS_REINCARNATION_SPEED` 配置（默认 6.0） |
| `main.py` | 注册 6 个轮回指令；初始化 `ReincarnationManager`；注入 `db_extended` 到轮回管理器 |

### 16.3 数据流

```
/main.py 指令注册
    │
    ├─ /轮回 → reincarnation_handler.handle_reincarnation()
    │   ├─ 检查条件 → reincarnation_manager.check_conditions()
    │   ├─ 计算奖励 → reincarnation_manager.calculate_reward()
    │   ├─ 保存数据 → db.upsert_reincarnation_data()
    │   ├─ 删除角色 → db.reincarnation_delete_player()
    │   ├─ 创建角色 → player_handler.handle_start_xiuxian() → apply_reincarnation_bonuses()
    │   └─ 发送结果
    │
    ├─ /轮回信息 → reincarnation_handler.handle_reincarnation_info()
    │   └─ db.get_reincarnation_data() → 格式化输出
    │
    ├─ /轮回商店 → reincarnation_handler.handle_reincarnation_shop()
    │   └─ db.get_reincarnation_data() → 展示可购买项及当前等级
    │
    ├─ /轮回购买 → reincarnation_handler.handle_reincarnation_purchase()
    │   └─ reincarnation_manager.purchase_bonus() → 更新 permanent_bonuses
    │
    └─ /轮回排行 → reincarnation_handler.handle_reincarnation_rank()
        └─ db.get_all_reincarnation_data() → 排序展示
```

---

## 17. 配置列表（`config/reincarnation_config.json`）

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
        "5": 1.3,
        "10": 1.5,
        "20": 1.8,
        "50": 2.0
    },
    "milestone_roots": {
        "1": "轮回道果",
        "5": "真轮回道果",
        "20": "混沌道果"
    },
    "shop_items": {
        "cultivation_speed": {"name": "修炼加速", "cost": 100, "value": 0.05, "max_purchases": 20},
        "breakthrough_bonus": {"name": "突破概率", "cost": 150, "value": 1, "max_purchases": 10},
        "initial_hp": {"name": "生命强化", "cost": 80, "value": 500, "max_purchases": 30},
        "initial_atk": {"name": "攻击强化", "cost": 80, "value": 100, "max_purchases": 30},
        "gold_bonus": {"name": "灵石加成", "cost": 120, "value": 0.10, "max_purchases": 10},
        "pill_effect_bonus": {"name": "丹药增效", "cost": 200, "value": 0.10, "max_purchases": 5},
        "death_protection": {"name": "死亡保护", "cost": 300, "value": 0.95, "max_purchases": 10},
        "breakthrough_limit_break": {"name": "突破极限", "cost": 500, "value": 2, "max_purchases": 5}
    },
    "breakthrough_unlock": {
        "57": {"required_reincarnation": 5, "unlocked_rate": 0.01}
    },
    "max_preserved_weapons": 3
}
```

---

## 18. 开放问题

| # | 问题 | 建议方案 | 状态 |
|---|------|----------|------|
| 1 | 弃道重修是否保留轮回数据？ | **是** — 弃道只清空角色数据，轮回数据在独立表中不受影响 | ✅ 已确认 |
| 2 | 传承卡牌收集系统是否同步实现？ | **否** — 仅实现轮回后传承获取上限增加，卡牌系统后续单独实现 | ✅ 已确认 |
| 3 | 轮回丹材料是否可交易？ | **是** — 允许玩家间交易，促进经济流通 | ✅ 已确认 |
| 4 | 轮回次数是否影响排行榜？ | **新增轮回排行榜** — 按轮回次数排序 | ✅ 已确认 |
| 5 | 轮回后宗门贡献是否保留？ | **否** — 宗门相关全部重置 | ✅ 已确认 |
| 6 | 混沌道果速度 6.0 是否过高？ | 可在 `_conf_schema.json` 中调低配置值，不影响代码逻辑 | ⚠️ 待测试 |
| 7 | 锻造武器的保留数量 3 把是否合理？ | 保留装备槽2把+1把备用，可配置调整 | ⚠️ 待确认 |
| 8 | 轮回次数是否需要硬上限？ | **否** — 50次后继续轮回仍有小成长倍率（每次+1%），但不设上限 | ✅ 已确认 |

---

## 附录 A: ReincarnationManager 核心接口

```python
class ReincarnationManager:
    def __init__(self, db, db_extended, config_manager, cultivation_manager):
        ...

    async def check_conditions(self, player: Player) -> Tuple[bool, str]:
        """检查轮回条件（境界、状态、轮回丹、贷款）"""

    async def calculate_reward(self, highest_level_index: int, reincarnation_count: int) -> int:
        """计算轮回修为奖励"""

    async def get_reincarnation_data(self, user_id: str) -> Optional[dict]:
        """获取轮回数据"""

    async def upsert_reincarnation_data(self, user_id: str, data: dict):
        """更新轮回数据（事务内调用）"""

    async def purchase_bonus(self, user_id: str, item_id: str) -> Tuple[bool, str]:
        """购买轮回商店加成"""

    async def check_milestones(self, reincarnation_count: int) -> List[str]:
        """检查是否达成里程碑"""

    async def apply_bonuses(self, player: Player):
        """创建新角色后应用轮回加成"""

    def assign_reincarnation_root(self, reincarnation_count: int) -> str:
        """按轮回次数分配灵根"""

    def select_preserved_weapons(self, weapons: list) -> list:
        """选择保留的锻造武器"""

    async def execute_reincarnation(self, player: Player) -> Tuple[bool, str]:
        """执行轮回（事务保护）"""

    async def generate_reincarnation_report(self, player: Player, reward: int, milestones: list) -> str:
        """生成轮回结果报告"""

    def get_shop_items(self) -> dict:
        """获取轮回商店物品列表"""

    async def get_reincarnation_ranking(self) -> List[dict]:
        """获取轮回排行榜数据"""
```
