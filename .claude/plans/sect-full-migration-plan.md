# 宗门系统完整迁移计划

## 概述

将 NoneBot2 参考实现中的宗门高级功能迁移到 AstrBot 插件，并修复已知 bug。

**迁移范围：**
- 🔧 Bug 修复 × 3
- 🆕 新增功能 × 5（攻击修炼、丹房系统、资材发放、自动换宗主、宗门改名）
- 📦 新增命令 × 5，新增后台任务 × 2

**数值设计原则：** 基于 AstrBot 经济体系自定义平衡数值（参考：中期玩家日收入 1-3M 灵石，突破丹 2.5-6M）

---

## 一、Bug 修复

### 1. `perform_sect_task` 全服重置 bug
**文件：** `managers/sect_manager.py:511-514`
**问题：** 跨日检测时调用 `reset_sect_tasks()` 会重置**全服**所有玩家的 `sect_task`
**修复：** 移除 `reset_sect_tasks()` 调用，仅重置当前玩家的 `sect_task = 0`

### 2. `donate_to_sect` scale_ratio 未生效
**文件：** `managers/sect_manager.py:239`
**问题：** 硬编码 `* 10` 而非读取 `self.config.get("scale_ratio", 10)`
**修复：** `scale_gained = stone_amount * self.config.get("scale_ratio", 10)`

### 3. `handle_owner_death` 未接入
**文件：** `managers/sect_manager.py:562`
**问题：** 方法存在但无任何调用点
**修复：** AstrBot 的战斗系统中"死亡"仅表示战斗失败（HP ≤ 0），并非角色永久死亡，因此不适合在战斗中调用。保留此方法作为 GM 管理工具（如删除玩家账号时调用），并在 `handlers/gm_handlers.py` 的玩家删除流程中添加调用。如果当前没有删除玩家的功能，则暂不接入，方法保留备用。

---

## 二、新增配置

**文件：** `data/default_configs.py`

在 `SECT_CONFIG` 中新增以下子配置（所有数值已针对 AstrBot 经济体系平衡）：

```python
SECT_CONFIG = {
    # ... 现有配置保持不变 ...
    
    # 攻击修炼配置
    "practice": {
        "base_cost": 50000,           # 1级灵石成本
        "cost_growth": 1.25,          # 每级成本增长系数
        "atk_per_level": 0.04,        # 每级攻击力提升百分比
        "max_level": 50,              # 最大修炼等级
        "construction_per_level": 5000 # 每级所需宗门建设度（5000建设度解锁1级上限）
    },
    
    # 丹房配置
    "elixir_room": {
        "claim_contribution_required": 100,  # 领取丹药最低贡献
        "levels": {
            "1": {"name": "黄级丹房", "upgrade_cost_scale": 50000,  "upgrade_cost_stone": 50000,
                   "daily_pills": 1, "pill_rank_max": 1},
            "2": {"name": "玄级丹房", "upgrade_cost_scale": 100000, "upgrade_cost_stone": 100000,
                   "daily_pills": 2, "pill_rank_max": 2},
            "3": {"name": "地级丹房", "upgrade_cost_scale": 200000, "upgrade_cost_stone": 200000,
                   "daily_pills": 3, "pill_rank_max": 3},
            "4": {"name": "天级丹房", "upgrade_cost_scale": 400000, "upgrade_cost_stone": 400000,
                   "daily_pills": 4, "pill_rank_max": 4},
            "5": {"name": "仙级丹房", "upgrade_cost_scale": 800000, "upgrade_cost_stone": 800000,
                   "daily_pills": 5, "pill_rank_max": 5}
        },
        "maintenance_cost_per_level": 5000  # 每级每日维护费（资材）
    },
    
    # 资材发放配置
    "material_distribution": {
        "hour": 12,         # 每日发放时间
        "rate": 0.1         # 倍率：建设度 × rate = 发放资材
    },
    
    # 自动换宗主配置
    "auto_owner_change": {
        "inactive_days": 7  # 宗主离线天数触发自动传位
    },
    
    # 宗门改名配置
    "rename": {
        "cost_contribution": 500  # 改名消耗贡献度
    }
}
```

**数值平衡说明：**
- 攻击修炼：50K 起步 × 1.25^n 增长，50级总消耗约 50M 灵石，对中期玩家约 2-3 周完成
- 丹房：升级消耗 50K-800K 建设度 + 灵石，需要宗门集体捐献
- 资材发放：建设度 × 0.1，一个 10 万建设度的宗门每天获 1 万资材
- 丹药领取：给 1-5 枚丹药，品阶不高于玩家当前境界

---

## 三、新增数据库方法

**文件：** `data/database_extended.py`

新增 5 个方法：

| 方法 | 用途 |
|------|------|
| `update_sect_name(sect_id, new_name)` | 宗门改名（需检查唯一性） |
| `get_all_sects_summary()` | 获取所有宗门的 (sect_id, sect_scale, sect_owner) 用于资材发放和自动换宗主 |
| `update_player_elixir_get(user_id, value)` | 更新玩家丹药领取标记 |
| `update_user_atkpractice(user_id, level)` | 更新攻击修炼等级 |

---

## 四、新增 Manager 方法

**文件：** `managers/sect_manager.py`

### 4.1 `upgrade_practice(user_id, count=1)` — 升级攻击修炼
- 检查：有宗门、非外门弟子、等级未达上限
- 上限 = `sect_scale // construction_per_level`（受宗门建设度约束）
- 成本：灵石 `base_cost * cost_growth^level`（逐级累加）+ 资材 `灵石成本 * 10`
- 扣除灵石和资材，增加 `player.atkpractice`

### 4.2 `upgrade_elixir_room(user_id)` — 建设丹房（宗主专属）
- 检查：宗主权限、丹房未满级
- 扣除建设度 + 宗门灵石，增加 `elixir_room_level`

### 4.3 `claim_sect_pill(user_id)` — 领取丹药
- 检查：有宗门、非外门、丹房已建、贡献达标、今日未领
- 根据丹房等级发放丹药（1-5 枚，可配置）
- 丹药选择逻辑：从 `config_manager.exp_pills_data` 中筛选 `level_index <= player.level_index` 的经验丹，随机选取。若无合适丹药，降级为发放渡厄丹（保底）
- 设置 `sect_elixir_get = 1`

### 4.4 `rename_sect(user_id, new_name)` — 宗门改名
- 检查：宗主权限、名称合规、贡献足够
- 扣除贡献度，更新宗门名称

### 4.5 `get_my_practice_info(user_id)` — 查看修炼信息
- 返回当前修炼等级、上限、下次升级成本

---

## 五、新增 Handler 方法

**文件：** `handlers/sect_handlers.py`

| 方法 | 命令 | 繁忙状态 |
|------|------|----------|
| `handle_upgrade_practice` | `升级修炼` | 需要空闲 |
| `handle_upgrade_elixir_room` | `丹房建设` | 需要空闲 |
| `handle_claim_sect_pill` | `领取丹药` | 允许（类似签到） |
| `handle_rename_sect` | `宗门改名` | 需要空闲 |
| `handle_practice_info` | `修炼信息` | 允许（只读） |

---

## 六、后台任务

**文件：** `main.py`

### 6.1 资材发放任务 `_schedule_sect_material_distribution`
- 每日定时（可配置小时），遍历所有宗门
- `sect_materials += int(sect_scale * rate)`
- 使用 `_safe_schedule_daily(hour)` 模式

### 6.2 自动换宗主任务 `_schedule_auto_sect_owner_change`
- 每小时检查一次
- 遍历所有宗主，检查 `last_check_in_date` 是否超过 `inactive_days` 天
- 超期则按职位 → 贡献排序选择新宗主，调用已有的 `transfer_ownership` 逻辑

---

## 七、命令注册

**文件：** `main.py`

新增常量：
```python
CMD_UPGRADE_PRACTICE = "升级修炼"
CMD_SECT_ELIXIR_ROOM = "丹房建设"
CMD_SECT_ELIXIR_GET = "领取丹药"
CMD_SECT_RENAME = "宗门改名"
CMD_PRACTICE_INFO = "修炼信息"
```

注册 5 个新命令，对应 handler 方法。

---

## 八、战斗系统集成

**文件：** `managers/combat_manager.py:148`

在 `build_player_combat_stats` 的攻击计算中加入 `atkpractice` 加成：

```python
# 现有：
final_atk = int(base_atk * (1 + equip_bonus["atk_pct"] + atk_buff + technique_atk_bonus)) + breakthrough_atk + equip_bonus["atk"]

# 修改为：
atk_practice_bonus = player.atkpractice * 0.04  # 每级 4%
final_atk = int(base_atk * (1 + equip_bonus["atk_pct"] + atk_buff + technique_atk_bonus + atk_practice_bonus)) + breakthrough_atk + equip_bonus["atk"]
```

---

## 九、UI 更新

### 9.1 宗门菜单
**文件：** `handlers/misc_handler.py`

在 `handle_menu_sect` 中增加新命令说明：
```
⚔️ 修炼
· 升级修炼 [次数] — 升级攻击修炼等级
· 修炼信息 — 查看修炼状态

🧪 丹房
· 丹房建设 — 建设/升级宗门丹房（宗主）
· 领取丹药 — 每日领取宗门丹药

👑 宗主操作（新增）
· 宗门改名 <新名称> — 修改宗门名称
```

### 9.2 宗门信息增强
**文件：** `managers/sect_manager.py` `get_sect_info()`

在宗门信息中增加丹房等级和修炼上限显示。

### 9.3 繁忙状态白名单
**文件：** `handlers/utils.py`

在 `BUSY_STATE_ALLOWED_COMMANDS` 中添加 `"领取丹药"` 和 `"修炼信息"`（只读操作）。

---

## 十、文件修改清单

| 文件 | 改动类型 | 改动量 |
|------|----------|--------|
| `data/default_configs.py` | 扩展 SECT_CONFIG | 小 |
| `data/database_extended.py` | 新增 4 个方法 | 中 |
| `managers/sect_manager.py` | 新增 5 个方法 + 修复 2 个 bug + 增强 get_sect_info | 大 |
| `handlers/sect_handlers.py` | 新增 5 个 handler 方法 | 中 |
| `handlers/misc_handler.py` | 更新宗门菜单 | 小 |
| `handlers/utils.py` | 添加白名单命令 | 小 |
| `managers/combat_manager.py` | 1 行 atkpractice 集成 | 小 |
| `main.py` | 注册 5 个命令 + 2 个后台任务 + 常量定义 | 中 |
| `config/sect_config.json` | 自动更新（ConfigManager 会在下次加载时合并新默认值） | 无 |

**总计：** 9 个文件修改，约 400-500 行新增代码

---

## 十一、实现顺序

1. **Phase 1：Bug 修复** — 修复 3 个已知 bug（5 分钟）
2. **Phase 2：配置扩展** — 更新 `default_configs.py`（5 分钟）
3. **Phase 3：数据库层** — 新增 DB 方法（10 分钟）
4. **Phase 4：Manager 核心逻辑** — 5 个新方法 + 2 个 bug 修复（30 分钟）
5. **Phase 5：Handler 层** — 5 个新 handler（15 分钟）
6. **Phase 6：命令注册 + 后台任务** — `main.py` 改动（15 分钟）
7. **Phase 7：战斗集成 + UI** — combat_manager + misc_handler + utils（10 分钟）
8. **Phase 8：测试验证** — pytest 运行确认无语法错误（5 分钟）

---

## 十二、风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 经济数值失衡 | 丹药过于容易获取或修炼成本过高 | 通过配置文件可调，不硬编码 |
| ConfigManager 新旧配置合并 | 用户已有 sect_config.json 缺少新字段 | `_load_config_with_default` 会自动补充缺失键 |
| 丹药发放逻辑依赖已有丹药数据 | `exp_pills_data` 为空则无法发放 | 降级为固定发放渡厄丹 |
| atkpractice 影响战力平衡 | 50 级 × 4% = 200% 攻击加成过高 | 通过配置可调，初始建议上限 25 级（100%） |
