# 更新战斗力计算公式

## Context

当前战力公式（2处，代码完全相同）：
```python
combat_power = base_atk + breakthrough_atk + breakthrough_def + mental_power // 10
```

问题：
- `mental_power` 不影响战斗，纯展示属性却计入战力
- 缺失装备加成（武器 ATK/防具防御/10种特殊属性）
- 缺失心法加成（atk_bonus/hp_bonus 等百分比乘区）
- 缺失传承加成（impart_atk_per/impart_hp_per）
- 防御直接加进攻击，没有走实际的对数减伤曲线

## 新公式设计

新公式 = **期望每回合伤害 × 有效生命值**，取 log 压缩到友好数值。

### 攻击端

```
期望ATK = final_atk × crit_mult × double_mult
```

其中：
- `final_atk`：直接复用 `build_player_combat_stats` 的计算（含修为基础、突破加成、装备、心法、传承）
- `crit_mult = 1 + crit_rate/100 × (crit_damage - 1.0)`
  - 暴击率来源：传承(know×100) + 武器 + 心法
  - 暴击伤害来源：武器 + 心法，下限 1.5
- `double_mult = 1 + double_hit/100 × 0.5`
  - 连击来源：武器

### 防御端（有效生命值）

```
effective_hp = max_hp × def_mult × dodge_mult × regen_mult
```

其中：
- `max_hp`：复用 `calculate_hp_mp`（含传承、心法乘区）
- `def_mult = (base_def+500)/500 × (equip_def+200)/200`
  - `base_def = ln(experience+1)×10`
  - `equip_def = ln(raw_equip_def+1)×20`
  - `raw_equip_def = 突破双防 + 装备双防`
- `dodge_mult = 100 / max(1, 100 - dodge_rate)`
  - 闪避来源：防具
- `regen_mult = 1 + hp_regen_pct/100`
  - 回复来源：防具

### 最终战力

```python
combat_power = int(math.log10(expected_atk * effective_hp + 1) * 1000)
```

log10 压缩让结果在万~十万级别，不会出现数十亿的吓人数字，但保留相对排序。

### 不纳入战力的因素

以下在实际战斗中存在影响，但属于"概率/条件效果"，不适合纳入线性战力分：
- armor_pen（破甲）：取决于对手防御，无固定值
- lifesteal（吸血）：取决于造成的伤害
- reflect_pct（反伤）：取决于受到的伤害
- block_value（格挡）：被暴击无视，场景依赖

## 实现计划

### Step 1：`managers/comat_manager.py` — 新增 `calc_combat_power` 静态方法

```python
@staticmethod
def calc_combat_power(combat_stats: CombatStats, max_hp: int, max_mp: int) -> int:
    """从 CombatStats 计算战力评分"""
```

只接收 CombatStats + HP/MP 数值（已由调用方算好），无外部依赖。

### Step 2：`handlers/player_handler.py` — 替换战力计算（~行150-154）

用 `CombatManager.calc_combat_power(stats, stats.max_hp, stats.max_mp)` 替换旧公式。

需要：
- 调用 `CombatManager.build_player_combat_stats(player, impart_info, config_manager)` 构建 CombatStats
- 获取 `impart_info`：player_handler 已有 access（通过 `db.ext.get_impart_info`）
- 不含丹药临时效果（ranking 侧也不含，保持一致）

### Step 3：`managers/ranking_manager.py` — 替换战力计算（~行122-125）

同样用 `CombatManager.calc_combat_power(stats, hp, mp)` 替换。

需要：
- 遍历所有玩家时构建 CombatStats
- 获取 `impart_info`：ranking_manager 需要新增 `db.ext.get_impart_info` 调用

### Step 4：清理无用引用

`player_handler.py` 中删除旧的 `base_atk/breakthrough_atk/breakthrough_def/combat_power` 局部变量。

## 修改文件

| 文件 | 改动 |
|---|---|
| `managers/combat_manager.py` | 新增 `calc_combat_power` 静态方法 |
| `handlers/player_handler.py` | 替换战力计算逻辑（行150-154），新增 CombatStats 构建 |
| `managers/ranking_manager.py` | 替换战力计算逻辑（行122-125），新增 CombatStats 构建 + impart 查询 |

## 验证

1. `pytest tests/` — 确认无回归
2. 对比修改前后同一玩家的战力数值变化趋势（log10 压缩后应保持合理排序）
3. 排行榜排序方向：修为高 + 装备好的玩家应该排前面
