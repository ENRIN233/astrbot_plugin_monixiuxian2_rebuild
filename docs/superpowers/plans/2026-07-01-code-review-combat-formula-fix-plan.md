# 战斗系统公式对齐修复方案

> **日期:** 2026-07-01  
> **来源:** 代码质量审查  
> **优先级:** P1 — 影响游戏战斗平衡

---

## 1. 概述

战斗系统存在**两个核心问题**：

1. **辅修功法破甲（`buff_type 13`）对神通攻击无效** — `skill_manager._apply_defense` 缺少 `sub_break_pct`，神通流玩家辅修破甲完全无用
2. **两个战斗属性路径不一致** — `get_total_attributes()`（显示）与 `build_player_combat_stats()`（实际战斗）对装备属性的解读存在差异，玩家看到的数据与实际不符

---

## 2. 问题清单

### 2.1 辅修破甲对神通无效 (🔴 CRIT-11)

**涉及文件**: `managers/skill_manager.py:284` vs `managers/combat_manager.py:326`

```python
# skill_manager._apply_defense() — 神通伤害防御计算
total_reduction = defender.def_buff - attacker.armor_pen / 100
# 缺少: - attacker.sub_break_pct

# combat_manager.execute_attack() — 普通攻击防御计算  
total_reduction = defender.def_buff - attacker.armor_pen / 100 - attacker.sub_break_pct
# 完整: ✅ 包含 sub_break_pct
```

**根因**: `skill_manager.py` 在 `_apply_defense()` 中遗漏了 `sub_break_pct` 字段。该字段来自辅修功法的 `buff_type 13`（破甲），在 `build_player_combat_stats()` 中被正确解析并存储在 `CombatStats.sub_break_pct` 中，但在神通伤害计算时未传入。

### 2.2 属性展示与战斗不一致 (🟡 MAJ-15)

**涉及文件**: `models.py:304-364` vs `managers/combat_manager.py:124-236`

`get_total_attributes()` 展示时缺失以下战斗实际使用的属性：

| 缺失属性 | 来源 | 影响 |
|---|---|---|
| `armor_pen` | 武器 | 破甲值不显示 |
| `lifesteal` | 武器 | 吸血不显示 |
| `double_hit` | 武器 | 连击不显示 |
| `dodge_rate` | 防具 | 闪避不显示 |
| `crit_resist` | 防具 | 抗暴不显示 |
| `reflect_pct` | 防具 | 反伤不显示 |
| `block_value` | 防具 | 格挡不显示 |
| `hp_regen_pct` | 防具 | 回血不显示 |
| `damage_reduction` | 武器/防具/功法 | 减伤不显示 |
| `def_buff` | 防具 | 防御百分比不显示 |
| 辅修功法 buff (%) | 辅修 | 攻/暴/暴伤加成不显示 |
| 永久丹药 `flat_atk_bonus` | 丹药 `_global` | 永久攻击不显示 |

### 2.3 装备 Item 创建漏读字段 (🟡 MAJ-16)

**涉及文件**: `handlers/equipment_handler.py:187-204`

`handle_equip_item` 创建 Item 实例时未从配置读取：
- `breakthrough_bonus`, `hp_bonus`, `closing_exp_bonus`, `closing_recovery_bonus`
- `damage_reduction`, `breakthrough_number`, `dual_cultivation_bonus`
- `alchemy_exp_bonus`, `alchemy_count_bonus`, `harvest_bonus`

这些字段在 `get_total_attributes()` 中基于 Item 模型字段进行展示，漏读导致"战力榜"等技术属性显示不全。

---

## 3. 修复方案

### 3.1 修复辅修破甲对神通无效 (P0)

**修改 `managers/skill_manager.py` 中的 `_apply_defense`**:

```python
# skill_manager.py — 修复前
def _apply_defense(damage: float, attacker: CombatStats, defender: CombatStats) -> float:
    total_reduction = defender.def_buff - attacker.armor_pen / 100
    return max(damage * (1 - total_reduction), 0)

# skill_manager.py — 修复后
def _apply_defense(damage: float, attacker: CombatStats, defender: CombatStats) -> float:
    total_reduction = defender.def_buff - attacker.armor_pen / 100 - attacker.sub_break_pct
    return max(damage * (1 - max(total_reduction, 0)), 0)  # 额外保护: cap at 0 防止负减伤变增伤
```

**需要同时验证**: `combat_manager.py:326` 的 `execute_attack` 中已有 `sub_break_pct`，确保两处的 `sub_break_pct` 来自同一个 `CombatStats` 字段。

### 3.2 对齐属性展示路径 (P1)

**方案 A（推荐）**: `get_total_attributes()` 改为调用 `build_player_combat_stats()` 的结果进行展示，确保显示 = 战斗实际。

```python
# models.py — get_total_attributes
def get_total_attributes(self) -> Dict[str, Any]:
    # 委托给 combat_manager 的战斗统计
    from managers.combat_manager import build_player_combat_stats
    stats = build_player_combat_stats(self)
    return {
        "atk": stats.atk,
        "hp": stats.hp,
        "mp": stats.mp,
        "crit_rate": stats.crit_rate,
        "crit_damage": stats.crit_damage,
        "armor_pen": stats.armor_pen,
        "def_buff": stats.def_buff,
        "damage_reduction": stats.damage_reduction,
        "lifesteal": stats.lifesteal,
        "double_hit": stats.double_hit,
        "dodge_rate": stats.dodge_rate,
        "crit_resist": stats.crit_resist,
        "reflect_pct": stats.reflect_pct,
        "block_value": stats.block_value,
        "hp_regen_pct": stats.hp_regen_pct,
        # ... 辅助功法加成 ...
    }
```

**方案 B（轻量）**: 手工补齐缺失字段。维护成本高，不推荐。

### 3.3 补齐 EquipmentHandler 读取字段 (P2)

```python
# handlers/equipment_handler.py
EQUIPMENT_FIELDS = [
    "atk_bonus", "hp_bonus", "mp_bonus",
    "crit_rate", "crit_damage",
    "breakthrough_bonus", "closing_exp_bonus", "closing_recovery_bonus",
    "damage_reduction", "breakthrough_number", "dual_cultivation_bonus",
    "alchemy_exp_bonus", "alchemy_count_bonus", "harvest_bonus",
    "armor_pen", "lifesteal", "double_hit",  # 武器专属
    "def_buff", "dodge_rate", "crit_resist", "reflect_pct", "block_value", "hp_regen_pct",  # 防具专属
    "exclusive_weapon_id",
]

def _read_item_config(self, config: dict) -> Item:
    fields = {}
    for field in EQUIPMENT_FIELDS:
        if field in config:
            fields[field] = config[field]
    return Item(**fields)
```

### 3.4 增加公式验证测试 (P1)

```python
# tests/test_combat_formula.py

def test_sub_break_pct_applied_in_skill_attack():
    """辅修破甲应同时作用于神通和普攻"""
    attacker = CombatStats(atk=1000, armor_pen=0, sub_break_pct=0.2)
    defender = CombatStats(def_buff=0.5)
    
    # 普攻
    normal_dmg = execute_attack(attacker, defender, ...)
    # 神通
    skill_dmg = apply_skill_damage(attacker, defender, ...)
    
    # sub_break_pct 应 +20% 破甲，等价于提升伤害
    # 普攻和神通的减伤效果应一致
    assert abs(normal_dmg - skill_dmg) < epsilon

def test_equipment_display_matches_combat():
    """属性展示值应与战斗实际值一致"""
    player = create_test_player()
    display = player.get_total_attributes()
    combat_stats = build_player_combat_stats(player)
    
    assert display["atk"] == combat_stats.atk
    assert display["def_buff"] == combat_stats.def_buff
    assert display["armor_pen"] == combat_stats.armor_pen
    # ...
```

---

## 4. 影响范围

| 组件 | 影响 | 风险 |
|---|---|---|
| `managers/skill_manager.py` | `_apply_defense` 一行改动 | 低 — 与普攻公式对齐 |
| `managers/combat_manager.py` | 新增 `max(total_reduction, 0)` cap | 低 — 防止负减伤 |
| `models.py` | `get_total_attributes` 可能完全重写 | 中 — 影响所有装备展示 |
| `handlers/equipment_handler.py` | Item 创建补齐字段 | 低 — 不影响战斗 |
| `tests/` | 新增公式对齐测试 | 无风险 |

---

## 5. 实施建议

1. **立即修复**: `skill_manager._apply_defense` 补 `sub_break_pct` + 添加 `max(..., 0)` cap（3 行代码）
2. **短期**: 完善 `get_total_attributes` 缺失字段（方案 B 更快，先对齐显示）
3. **中长期**: 完全委托给 `build_player_combat_stats`（方案 A，消除双路径）
4. **同步**: 补齐 EquipmentHandler 创建 Item 时的字段读取

---

## 6. 相关代码审查发现

| 编号 | 原文标题 | 严重度 | 覆盖 |
|---|---|---|---|
| CRIT-11 | 辅修功法破甲对技能攻击无效 | 🔴 | ✅ 3.1 |
| MAJ-15 | 双战斗属性路径不一致 | 🟡 | ✅ 3.2 |
| MAJ-16 | handle_equip_item 漏读字段 | 🟡 | ✅ 3.3 |
