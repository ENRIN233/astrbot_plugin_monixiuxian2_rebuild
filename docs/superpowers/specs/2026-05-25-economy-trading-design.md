# 经济量级调整 + 玩家交易系统 + nonebot 数据合并 设计文档

日期：2026-05-25
插件：astrbot_plugin_monixiuxian2 (v3.1.3)

---

## 1. 概述

本次修改包含三个独立但关联的变更：

1. **经济量级调整**：将整个经济体系的价格和产出提升到百万/千万/亿量级
2. **玩家交易系统**：新增即时交易（面对面）和寄售行两种交易方式
3. **nonebot 数据合并**：将 `nonebot_plugin_xiuxian_2_pmv_lunar-master/data/xiuxian/` 中与现有系统兼容的物品数据合并到 astrbot 插件的 JSON 配置文件中

> **执行顺序**：先合并数据（变更 3，扩充物品库），再调整经济量级（变更 1，对所有物品包括新合并的统一改价），最后实现交易系统（变更 2）。

---

## 2. 经济量级调整

### 2.1 目标

功法基础价格应在百万灵石量级，高端达到千万和亿级。装备同理。所有灵石产出量同步调整，保持"攒多久买对应品级装备"的时间比例不变。

### 2.2 调整范围

**价格文件（6 个）：**

| 文件 | 内容 |
|------|------|
| `config/items.json` | 装备、功法、丹药、材料的价格 |
| `config/weapons.json` | 武器价格 |
| `config/pills.json` | 突破丹价格 |
| `config/exp_pills.json` | 经验丹价格 |
| `config/utility_pills.json` | 功能丹价格 |
| `config/storage_rings.json` | 储物戒价格 |

**产出文件（3 个）：**

| 文件 | 内容 |
|------|------|
| `config/adventure_config.json` | 冒险收益（base_stone_per_minute, level_bonus_per_minute, completion_bonus） |
| `config/bounty_templates.json` | 悬赏奖励 |
| `config/game_config.json` | BOSS 奖励、银行限额、贷款限额等 |

### 2.3 分层倍率方案

#### 装备/功法（按品级）

| 品级 | 当前价格范围 | 目标价格范围 | 倍率 |
|------|------------|------------|------|
| 凡品 | 100~500 | 100万~150万 | ×3000 |
| 灵品 | 500~8,000 | 150万~200万 | ×250~2000 |
| 地品 | 1,000~18,000 | 200万~400万 | ×22~200 |
| 天品 | 5,000~37,000 | 400万~700万 | ×19~80 |
| 皇品 | 20,000~88,000 | 700万~1500万 | ×17~35 |
| 帝品 | 50,000~240,000 | 1500万~5000万 | ×21~63 |
| 道品 | 100,000~600,000 | 5000万~1亿 | ×17~50 |
| 仙品 | 500,000~1,400,000 | 1亿~3亿 | ×21~20 |
| 混元 | 2,000,000~3,500,000 | 3亿~10亿 | ×15~29 |

#### 丹药/材料/储物戒（按现有价格区段）

无品级字段的物品，按"当前价格段"映射到对应倍率：

| 当前价格段 | 倍率参考 |
|----------|---------|
| 1~999 | ×3000（对齐凡品） |
| 1,000~9,999 | ×500（对齐灵品/地品） |
| 10,000~99,999 | ×100（对齐天品/皇品） |
| 100,000~999,999 | ×50（对齐帝品/道品） |
| 1,000,000~9,999,999 | ×30（对齐仙品） |
| 10,000,000~99,999,999 | ×20（对齐混元） |
| ≥100,000,000 | ×10（顶级突破丹） |

> **说明**：低价物品涨幅大、高价物品涨幅小，结果是整个经济曲线被"压缩"——低端不再可忽略，高端不会膨胀到天文数字。最终所有物品价格落在 100万 ~ 100亿 区间。

#### 应用规则

- 配置文件批量改写：实现一个 Python 脚本读取各 JSON、按规则计算新价格、回写
- **保留有意义的数值精度**：新价格四舍五入到"万"位（×10000 取整），便于游戏内显示
- 脚本与新 JSON 配置一起提交，便于后续重新执行/微调

### 2.4 产出调整

产出按"玩家当前所处阶段对应的物品价格倍率"同比放大，保持时间比例不变。

| 项目 | 字段位置 | 倍率 | 说明 |
|------|---------|------|------|
| 冒险基础灵石/分钟 | `adventure_config.json:routes[].base_stone_per_minute` | ×500~3000（按路线难度递减） | 巡山 ×3000，云游 ×1500，猎魔 ×500，九死 ×100 |
| 冒险等级加成/分钟 | `adventure_config.json:routes[].level_bonus_per_minute` | 同上 | |
| 冒险完成奖励 | `adventure_config.json:routes[].completion_bonus` | 同上 | |
| 悬赏奖励 | `bounty_templates.json:reward_stone` | ×100~3000（按难度等级 F~C 递减） | F 级 ×3000，C 级 ×100 |
| BOSS 奖励 | `game_config.json:boss.stone_reward` 或动态生成 | ×100 | |
| 银行最大存款 | `game_config.json:bank.max_deposit_amount` | ×100 | 10M → 10亿 |
| 贷款最大额 | `game_config.json:bank.max_loan_amount` | ×100 | 1M → 1亿 |
| 贷款最小额 | `game_config.json:bank.min_loan_amount` | ×100 | 1k → 10万 |
| 突破贷款上限 | `game_config.json:bank.breakthrough_loan_max` | ×100 | |
| 灵眼灵石产出 | `game_config.json:spirit_eye.*.exp_per_hour`（若有灵石字段） | ×100 | 若仅产出经验则不调整 |

> **目标产出节奏校验**：低阶玩家做一次巡山（30 分钟）获得 ~60 万灵石，可在 1~2 次内攒够买凡品装备（100~150 万）；高阶玩家做一次九死一生（120 分钟）获得 ~3000 万灵石，攒够买仙品装备（1~3 亿）需 ~10 次。整体保持原有"5~10 次中等冒险攒够同阶段装备"的节奏。

### 2.5 不调整的部分

- 经验值（exp）相关数值不变（只调整灵石经济）
- 倍率（成功率、暴击率等）不变
- 时间参数不变（闭关时长、冒险时长等）
- 突破丹价格已经是百万~百亿量级，**不再额外放大**（避免顶级突破丹突破 1000 亿）
- 经验丹价格在百万级以下的部分按规则放大；千万级以上部分不调整

### 2.6 风险与影响

- **存量玩家影响**：迁移时不修改 `players.gold`、`players.storage_ring_items` 等存量数据，老玩家仍持有旧量级灵石
  - 解决方案：一次性广播迁移说明，建议给所有存量玩家发放"通胀补偿"（一次性灵石 × 100），或忽略让老玩家自然攒
  - **本设计选择"不补偿"**：让老玩家通过冒险逐步赚取新量级灵石。如果用户要求补偿，写一个独立的一次性脚本，不属于本次设计范围
- **银行存量利息**：由于银行限额扩大 ×100，原"已超出新限额上限"的不会出现；如果有玩家旧存款 < 新最小贷款额则无影响
- **配置文件版本**：所有配置 JSON 修改应保留原结构，仅改 price/reward 数值字段

---

## 3. 玩家交易系统

### 3.1 即时交易（面对面交易）

#### 可交易物品范围

交易系统涉及的玩家库存来源：

| 来源 | 可交易 | 说明 |
|------|--------|------|
| `players.gold`（灵石余额） | 是 | 通过 `添加灵石` 命令 |
| `players.pills_inventory` JSON | 是 | 丹药 |
| `players.storage_ring_items` JSON | 是 | 储物戒内物品（装备、功法、材料） |
| `players.weapon/armor/main_technique/techniques`（已装备） | 否 | 已装备物品需先卸下 |
| `players.storage_ring`（储物戒本身） | 否 | 储物戒本身不可交易 |

#### 交易流程

1. A 输入 `交易 @B` 发起交易请求
2. B 收到提示，输入 `接受交易` 或 `拒绝交易`
3. 双方进入"交易中"状态（与闭关/冒险等状态互斥）
4. A/B 分别放入物品：`添加物品 <物品名>` / `添加灵石 <数量>`
   - **关键**：放入的物品/灵石**立即从玩家库存中扣除**，托管到 trades 表中
5. 任一方可 `移除物品 <名称>` 移除已放入的物品（物品/灵石返还到放入者库存）
6. 双方查看交易内容后输入 `确认交易`
7. 两人都确认后，交易自动完成，trades 表中的物品/灵石转移到对方库存
8. **取消交易**或**任一方掉线超时（30 分钟）**：所有托管物品/灵石返还原主

#### 命令列表

| 命令 | 说明 |
|------|------|
| `交易 @某人` | 发起交易 |
| `接受交易` | 接受交易请求 |
| `拒绝交易` | 拒绝交易请求 |
| `添加物品 <名称> [数量]` | 向交易放入物品（可堆叠物品可指定数量，默认 1） |
| `添加灵石 <数量>` | 向交易放入灵石 |
| `移除物品 <名称>` | 从交易移除物品 |
| `查看交易` | 查看当前交易内容 |
| `确认交易` | 确认当前交易 |
| `取消交易` | 取消交易 |

#### 数据库表 `trades`

```sql
CREATE TABLE trades (
    trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_a TEXT NOT NULL,
    player_b TEXT NOT NULL,
    player_a_items TEXT DEFAULT '[]',   -- JSON: [{item_id, item_name, quantity}]
    player_b_items TEXT DEFAULT '[]',
    player_a_stones INTEGER DEFAULT 0,
    player_b_stones INTEGER DEFAULT 0,
    a_confirmed INTEGER DEFAULT 0,      -- 0=未确认, 1=已确认
    b_confirmed INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',       -- pending/trading/completed/cancelled
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3.2 寄售行

#### 可寄售物品范围

与即时交易一致：可寄售丹药、储物戒内物品（装备、功法、材料）。已装备物品需先卸下；储物戒本身不可寄售；灵石本身不可寄售。

#### 手续费机制

- **上架时**：扣除卖家灵石 = 上架价格 × 5%，作为上架手续费
  - 卖家灵石不足时拒绝上架
- **成交时**：买家支付全额价格，卖家收到全额价格（无二次抽成）
- 上架手续费**不退还**（即使物品过期下架或卖家主动下架，手续费已被消耗）

#### 流程

1. 卖家输入 `寄售 <物品名> <价格>` 上架
   - 扣除卖家 5% 上架手续费（灵石）
   - 从卖家库存中扣除该物品，托管到 consignment_listings 表
2. 买家输入 `寄售行 [页码]` 浏览在售物品（分页，每页 10 条）
3. 买家输入 `购买寄售 <编号>` 购买
   - 扣除买家灵石 = 上架价格
   - 灵石全额转入卖家
   - 物品转入买家库存
4. 未售出物品 7 天后自动下架，物品退回卖家库存（手续费不退）
5. 卖家可主动 `下架寄售 <编号>`，物品退回库存（手续费不退）

#### 命令列表

| 命令 | 说明 |
|------|------|
| `寄售 <物品名> <价格> [数量]` | 上架物品，可堆叠物品可指定数量（默认 1） |
| `寄售行 [页码]` | 浏览寄售行 |
| `购买寄售 <编号>` | 购买指定物品 |
| `我的寄售` | 查看自己上架的物品 |
| `下架寄售 <编号>` | 取消上架 |

#### 数据库表 `consignment_listings`

```sql
CREATE TABLE consignment_listings (
    listing_id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id TEXT NOT NULL,
    item_id TEXT NOT NULL,               -- 物品配置 ID
    item_name TEXT NOT NULL,             -- 物品显示名（冗余存储，便于浏览）
    item_type TEXT NOT NULL,             -- weapon/armor/main_technique/technique/pill/material
    quantity INTEGER NOT NULL DEFAULT 1, -- 上架数量（适用于可堆叠物品）
    price INTEGER NOT NULL,              -- 一口价（灵石）
    listed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,       -- listed_at + 7 days
    status TEXT DEFAULT 'active',        -- active/sold/expired/cancelled
    buyer_id TEXT,                       -- 成交时填充
    sold_at TIMESTAMP                    -- 成交时间
);
CREATE INDEX idx_consignment_status ON consignment_listings(status);
CREATE INDEX idx_consignment_seller ON consignment_listings(seller_id, status);
```

> **说明**：装备/功法等单件物品 quantity=1；丹药/材料可 >1（卖方决定一次上架多少）。买家购买时整批一次性成交，不支持拆分购买。

### 3.3 交易限制

无等级、次数、金额限制。所有已注册玩家均可自由交易。

### 3.4 与现有状态的兼容

新增 `UserStatus.TRADING` 状态，加入 `models_extended.py` 的 UserStatus 枚举。

- 正在交易中的玩家不能闭关、冒险、探索副本等（通过 user_cd 表 + status 字段强制）
- 正在闭关/冒险中的玩家不能发起或接受交易（在 trade_handler 中校验 user_cd.type）
- 查看类命令（查看信息、银行余额等）在交易中**仍允许使用**——加入 `BUSY_STATE_ALLOWED_COMMANDS` 白名单
- 寄售行所有命令（`寄售行`、`购买寄售`、`我的寄售` 等）**不需要进入交易状态**，可在任何空闲场景下使用

新增加到 `BUSY_STATE_ALLOWED_COMMANDS` 的命令：
- 寄售行浏览（`寄售行`、`我的寄售`）：忙碌状态下也可查看

新增**不允许**在忙碌状态下使用的命令：
- 即时交易相关命令（`交易`、`接受交易`、`添加物品` 等）只允许在空闲状态发起

---

## 4. nonebot 数据合并

### 4.1 数据源

`E:\Github\nonebot_plugin_xiuxian_2_pmv_lunar-master\data\xiuxian\` 目录下的 JSON 数据（共 ~21,000 行）。

### 4.2 合并范围（"只合并兼容类别"）

只导入能映射到 astrbot 现有数据结构的类别：

| nonebot 文件 | 数量（估） | 合并目标 | 备注 |
|---|---|---|---|
| `丹药/丹药.json`（治疗丹） | ~30 | `utility_pills.json` | 映射为治疗/状态丹 |
| `丹药/炼丹丹药.json`（修为/突破丹） | ~150 | `exp_pills.json` 或 `pills.json` | 按字段判断分流：含 `境界` 字段且为突破型→pills，纯增 exp→exp_pills |
| `装备/法器.json`、`内甲.json`、`防具.json`、`道袍.json`、`道靴.json`、`本命法宝.json`、`辅助法宝.json`、`灵戒.json` | ~400 | `weapons.json` + `items.json`（armor/护甲） | 武器类型→weapons.json，护甲/法宝→items.json |
| `功法/主功法.json` | ~600 | `items.json`（type=main_technique） | |
| `功法/辅修功法.json` | ~160 | `items.json`（type=technique） | |

**明确不导入**（与现有系统不兼容、需额外开发新系统）：
- `丹药/药材.json` —— astrbot 无药材库存系统
- `丹药/天地奇物.json`、`神物.json`、`炼丹炉.json` —— 涉及炼丹辅助系统
- `功法/神通.json` —— astrbot 无主动技能系统
- `装备/套装.json` —— astrbot 无套装系统
- `修炼物品/聚灵旗.json`、`道具.json` —— 涉及位面/识海等额外系统
- `place/地区.json` —— astrbot 无地图系统

### 4.3 ID 处理规则

- **同名物品跳过**：以 `name` 字段做查重 key。astrbot 已有同名物品时丢弃 nonebot 版本（避免破坏现有平衡）
- **不同名追加**：以"现有最大 ID + 1"分配新 ID，与现有命名规则保持一致：
  - weapons.json：`sword_NNN` / `axe_NNN` 等，按武器类型追加（如已有 `sword_032`，新增从 `sword_033` 起）
  - items.json：使用 `NNNN` 数字 ID（dict 形式），从当前最大 +1 开始
  - pills.json / exp_pills.json：使用 `pill_xxx` / `exp_pill_NNN`，按现有命名延续
- **保留 nonebot 原 ID 作为追溯字段**：合并后的条目加入 `"_source_id": "1101"`、`"_source": "nonebot"`，便于后续追溯/回滚

### 4.4 字段映射（自动转换公式）

#### 4.4.1 品级映射（nonebot rank 数字 → astrbot 品级名）

nonebot 的 `rank` 数字越小品级越高（同 astrbot 的"凡品→混元"是越来越高）。基于现有 astrbot 物品的 rank 经验值，建立映射表：

| nonebot rank 范围 | astrbot 品级 | required_level_index |
|---|---|---|
| rank ≥ 60 | 凡品 | 0 |
| 50 ≤ rank < 60 | 灵品 | 10 |
| 40 ≤ rank < 50 | 地品 | 20 |
| 30 ≤ rank < 40 | 天品 | 30 |
| 20 ≤ rank < 30 | 皇品 | 40 |
| 10 ≤ rank < 20 | 帝品 | 50 |
| 0 ≤ rank < 10 | 道品 | 60 |
| rank < 0 | 仙品 | 70 |

> nonebot 中的"后天品级/下品符器/上品符器"等文字 level 字段仅用于显示，作 `description` 字段备份。

#### 4.4.2 装备百分比 buff → astrbot 绝对值

`astrbot` 装备字段：`physical_damage / magic_damage / physical_defense / magic_defense / mental_power`（绝对值）。

公式：`new_value = base_for_rank × nonebot_buff_pct`

其中 `base_for_rank` 是该品级在 astrbot 现有装备中的平均属性值（提前从 weapons.json/items.json 统计）：

| 品级 | base 物伤 | base 法伤 | base 物防 | base 法防 | base 神识 |
|---|---|---|---|---|---|
| 凡品 | 15 | 10 | 8 | 5 | 8 |
| 灵品 | 80 | 60 | 40 | 30 | 35 |
| 地品 | 200 | 150 | 100 | 80 | 80 |
| 天品 | 500 | 400 | 250 | 200 | 200 |
| 皇品 | 1000 | 800 | 500 | 400 | 400 |
| 帝品 | 2200 | 1800 | 1100 | 900 | 900 |
| 道品 | 5000 | 4000 | 2500 | 2000 | 2000 |
| 仙品 | 10000 | 8000 | 5000 | 4000 | 4000 |

> 这些 base 在脚本中作为常量，转换时 `physical_damage = round(base_物伤[品级] × atk_buff)`。

字段对应：

| nonebot 字段 | astrbot 字段 | 说明 |
|---|---|---|
| `atk_buff` | `physical_damage` | 主物伤 |
| `crit_buff` | `mental_power` | 神识/暴击近义 |
| `def_buff` | `physical_defense` | 物防（武器无防御则不填） |
| `mp_buff` | `magic_damage` | 法伤 |
| `critatk` | （并入 mental_power） | 暴击伤害合并神识 |
| `zw` | （丢弃） | 真元，astrbot 未实现 |

#### 4.4.3 功法 buff 映射

astrbot 功法字段（items.json type=main_technique）：`exp_multiplier / spiritual_qi / blood_qi`。

| nonebot 字段 | astrbot 字段 | 转换 |
|---|---|---|
| `hpbuff` | `blood_qi` | 转为绝对值，按品级 base × buff |
| `mpbuff` | `spiritual_qi` | 同上 |
| `exp_buff` | `exp_multiplier` | 1 + exp_buff |
| `atkbuff`/`crit_buff`/`def_buff` 等 | （丢弃或挂在 description） | astrbot 功法不直接挂战斗 buff |

> 功法的 13 个 buff 字段中只有 3 个有对应。其余字段在 `description` 末尾追加 `（原效果：atk+15%, crit+20%）` 作为记录。

#### 4.4.4 丹药字段映射

nonebot 丹药 `buff_type` + `buff`：

| nonebot buff_type | 含义 | astrbot 映射 |
|---|---|---|
| `hp` | 回血 | utility_pills.json，`effect_type=instant`，`effect={"add_hp_pct": buff}` |
| 含"修为/突破"关键词 | exp 类 | exp_pills.json，`exp_gain = buff × base_exp_for_rank` |
| `境界` 字段非空 | 突破丹 | pills.json，`target_level_index` 按 `境界` 字段映射 |

> nonebot 的"境界"字符串（如"凝气境一重"）需建立一张映射到 astrbot 等级 index 的查找表，作为脚本常量。

#### 4.4.5 价格 / 上架权重

- **价格**：保留 nonebot 的 `price` 字段；若缺失则按品级填默认值（凡品 200，灵品 5000，...）；本次合并产出的新价格之后会被「经济量级调整」统一缩放，所以这里**不必精细调价**
- **shop_weight**：所有合并进来的物品默认 `shop_weight=500`（介于现有 1000 和稀有 100 之间），不轻易出现在商店刷新中
- **required_level_index**：按品级查表（见 4.4.1）

### 4.5 合并脚本

新增 `scripts/merge_nonebot_data.py`：

1. 读取 `E:\Github\nonebot_plugin_xiuxian_2_pmv_lunar-master\data\xiuxian\` 下指定 JSON
2. 读取 astrbot `config/` 下目标 JSON
3. 对每条 nonebot 物品：
   - 按 4.4 规则转换字段
   - 按 4.3 规则判定 ID（同名跳过）
   - 追加到目标列表/字典
4. 写回目标 JSON（保持原格式：list 或 dict）
5. 输出合并日志：`新增 X 条 / 跳过同名 Y 条 / 跳过不兼容 Z 条`
6. **支持 dry-run**：`--dry-run` 只输出会发生什么，不写文件

### 4.6 与经济量级调整的协作

合并脚本只负责**数据导入**，**不做价格放大**。所有合并条目最终通过经济量级调整脚本（`rebalance_economy.py`）统一缩放，避免双重调整。

执行顺序：

1. 先跑 `merge_nonebot_data.py`：扩充物品库
2. 再跑 `rebalance_economy.py`：对全部物品（含新合并的）统一放大价格
3. 启动游戏，v21 数据库迁移建立交易表

### 4.7 风险

- **平衡风险**：自动公式转换可能产生明显比同品级现有物品强/弱的条目。**对策**：合并脚本输出"异常值检查"日志（如某物品物伤 > 同品级平均 × 2 即提醒），人工抽检后微调
- **回滚能力**：合并写文件前先备份目标 JSON 到 `config/.backup/<timestamp>/`，便于回滚
- **重复执行**：脚本支持 `_source` 字段去重，再次执行不会重复导入
- **存量数据库**：合并仅修改 JSON 配置，不影响 SQLite 中老玩家持有的物品（老物品 ID 仍指向旧条目）

---

## 5. 架构影响

### 5.1 新增文件

| 文件 | 用途 |
|------|------|
| `handlers/trade_handler.py` | 即时交易命令处理 |
| `handlers/consignment_handler.py` | 寄售行命令处理 |
| `managers/trade_manager.py` | 即时交易业务逻辑 |
| `managers/consignment_manager.py` | 寄售行业务逻辑 |
| `scripts/merge_nonebot_data.py` | nonebot 数据合并脚本（含 dry-run、备份、异常检查） |
| `scripts/rebalance_economy.py` | 经济量级缩放脚本（按规则批量改写 JSON 配置） |
| `config/.backup/<timestamp>/*.json` | 合并/缩放前的自动备份（脚本输出） |

### 5.2 修改文件

| 文件 | 修改内容 |
|------|---------|
| `main.py` | 注册新命令，添加寄售行过期检查的后台任务 |
| `data/migration.py` | 添加 v21 迁移（trades + consignment_listings 表） |
| `handlers/utils.py` | 在状态互斥白名单中添加寄售行查看类命令 |
| `models_extended.py` | UserStatus 枚举新增 `TRADING` |
| `config/items.json` | nonebot 功法/防具/法宝合并 + 价格调整 |
| `config/weapons.json` | nonebot 武器类装备合并 + 价格调整 |
| `config/pills.json` | nonebot 突破丹合并 + 价格调整（仅低于百万的部分） |
| `config/exp_pills.json` | nonebot 修为丹合并 + 价格调整（仅低于千万的部分） |
| `config/utility_pills.json` | nonebot 治疗/状态丹合并 + 价格调整 |
| `config/storage_rings.json` | 价格调整（无 nonebot 数据合并） |
| `config/adventure_config.json` | 产出调整 |
| `config/bounty_templates.json` | 奖励调整 |
| `config/game_config.json` | 银行/贷款限额、BOSS 奖励调整 |

### 5.3 后台任务

新增 1 个后台任务：
- **寄售行过期检查**：每小时检查一次，将过期物品退回卖家

---

## 6. 错误处理

- **即时交易跨群限制**：交易请求只对同一群内的两个玩家有效（通过 `event.get_group_id()` 校验）。私聊场景下不支持发起交易
- **寄售行作用范围**：寄售行为全局共享（不区分群），任意已注册玩家均可浏览/购买
- **交易物品/灵石托管原子性**：放入和移除使用数据库事务（`BEGIN IMMEDIATE`），失败时回滚
- **交易完成时双向转移**：使用单个数据库事务执行"双方库存更新 + trades 表状态更新"，避免中途失败导致物品丢失
- **寄售手续费不足**：上架前检查卖家 gold ≥ price × 5%，不足时拒绝上架
- **重复交易请求**：玩家已处于"交易中"状态时，拒绝发起或接受新的交易请求
- **并发购买寄售物品**：使用 `BEGIN IMMEDIATE` 事务 + `WHERE status='active'` 条件保护，重复购买只允许首个成功
- **交易超时**：双方进入交易状态后 30 分钟未完成，自动取消并返还所有托管物品/灵石
- **数据库迁移**：v21 迁移仅创建表，不修改现有数据；即使迁移失败也不会影响存量数据
- **数据合并冲突**：同名物品跳过；ID 分配按现有命名规则延续；脚本支持 dry-run 预览
- **合并备份**：每次跑合并/缩放脚本前自动备份目标 JSON 到 `config/.backup/<timestamp>/`
