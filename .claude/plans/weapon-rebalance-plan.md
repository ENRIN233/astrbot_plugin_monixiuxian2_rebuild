# 武器数值重构计划

## 目标

参考原版 nonebot 插件法器.json 的百分比 buff 体系，对本插件全部 213 把武器进行品阶对齐数值改动。

---

## 数据概况

| 分组 | 数量 | 来源标识 | 特点 |
|------|------|---------|------|
| Nonebot 合并武器 | **72 把** | `_source: "nonebot"` | 有 `_source_id`，可精确匹配参考文件 |
| 原生武器 | **141 把** | `_source: "native"` 或无标识 | 无参考文件对应，按品阶基准分配 |
| **合计** | **213 把** | | |

### 参考文件覆盖情况

参考文件共 62 把法器，其中 **72 把 nonebot 武器全部有 `_source_id` 匹配**，无重复、无遗漏。
参考文件多余的条目（7004-7010 等）在 weapons.json 中不存在，可忽略。

### 品阶映射差异（重要！）

合并脚本的品阶映射与参考文件的"原始品阶名"存在系统性差异：

| 武器 | 参考文件原始品阶 | 参考 rank 数值 | weapons.json 当前品阶 |
|------|----------------|---------------|---------------------|
| 7081-7083 (陨仙/惊雷/承影) | 下品仙器 | 27 | **皇品** |
| 7091-7093 (无影剑/风云幡/青竹蜂云剑) | 上品仙器 | 24 | **皇品** |
| 7095-7097 (鸿钧棍/龙渊剑/青龙偃月刀) | 极品仙器 | 13~15 | **帝品** |
| 7098-7099 (原罪/无罪) | 极品仙器 | 15~19 | **帝品/仙品** |
| 11001-11014 (归墟剑~灵魄玉) | 极品仙器 | -5 | **仙品** |
| 15453-15466 (无始钟~少姜) | 无上仙器 | -5 | **仙品** |
| 13001-13004 (轩辕剑~天上天下无双刀) | 无上仙器 | -5 | **帝品** |
| 7090 (东皇钟), 7094 (灭神戟) | 无上仙器 | 12 | **天品** |
| 8000 (射日弓) | 无上仙器 | 12 | **帝品** |

**决策**：以参考文件的 buff 数值为基准，保持 weapons.json 当前品阶（rank）不变。
即：7081 陨仙保持"皇品"但其 atk_bonus/crit_rate 用参考文件"下品仙器"对应的 0.40/40 值。

---

## 参考映射规则

| 参考字段 | 含义 | 映射到 weapons.json | 说明 |
|---------|------|-------------------|------|
| `atk_buff` | 攻击力加成% | `atk_bonus` (float) | 如 0.08 → 0.08 |
| `crit_buff` | 暴击率% | `crit_rate` (int) | 如 0.08 → 8 |
| `critatk` | 暴击伤害% | `crit_damage` (float) | 如 0.4 → 0.4（**加法增量**，非完整乘数） |
| `def_buff` | 防御% | 不映射 | 参考文件中绝大多数为 0，无对应字段 |
| `mp_buff` | 法力% | `mp_bonus` (float) **新增** | 参考文件中绝大多数为 0，仅少数无上仙器有值 |

### 品阶基准数值（参考文件）

| 品阶 | atk_buff | crit_buff | 混合(atk+crit) | critatk |
|------|----------|-----------|----------------|---------|
| 下品符器 | 0.08 | 0.08 | 0.04+0.04 | 0 |
| 上品符器 | 0.12 | 0.12 | 0.06+0.06 | 0 |
| 下品法器 | 0.16 | 0.16 | 0.08+0.08 | 0 |
| 上品法器 | 0.20 | 0.20 | 0.10+0.10 | 0 |
| 下品纯阳法器 | 0.24 | 0.24 | 0.12+0.12 | 0 |
| 上品纯阳法器 | 0.28 | 0.28 | 0.14+0.14 | 0 |
| 下品通天法器 | 0.32 | 0.32 | 0.16+0.16 | 0 |
| 上品通天法器 | 0.36 | 0.36 | 0.18+0.18 | 0 |
| 下品仙器 | 0.40 | 0.40 | 0.20+0.20 | 0 |
| 上品仙器 | 0.48 | 0.48 | 0.24+0.24 | 0 |
| 极品仙器 | 0.50~0.70 | 0.50~0.70 | 特殊 | 0~0.5 |
| 无上仙器 | 0.40~1.0 | 0.50~1.0 | 特殊 | 0~2.0 |

---

## 改动范围

### 步骤 1：数据层 — `models.py`

**文件**: `models.py`

1. `Item` dataclass（行 11-38）新增字段：
   ```python
   mp_bonus: float = 0.0  # 真元百分比加成（武器有效，如 0.3 = +30%）
   ```

2. `get_attribute_display()`（行 40-67）新增显示：
   ```python
   if self.mp_bonus > 0:
       attrs.append(f"真元+{self.mp_bonus:.0%}")
   ```

### 步骤 2：战斗层 — `managers/combat_manager.py`

**文件**: `managers/combat_manager.py`

**2a. 暴击伤害公式修正（行 167）**

将 crit_damage 从"完整乘数"改为"加法增量"体系：
```python
# 当前（完整乘数）:
crit_damage=max(1.5, equip_bonus.get("crit_damage", 0) + technique_crit_damage),
# 改为（加法增量 + 基础 1.0）:
crit_damage=max(1.5, 1.0 + equip_bonus.get("crit_damage", 0) + technique_crit_damage),
```

同步修正行 193 的战力计算公式：
```python
# 当前:
crit_mult = 1.0 + crit_rate / 100.0 * max(0.0, stats.crit_damage - 1.0)
# 改为（stats.crit_damage 已包含 1.0 基础，需减去）:
crit_mult = 1.0 + crit_rate / 100.0 * max(0.0, stats.crit_damage - 1.0)
```
注意：行 193 公式无需修改——`stats.crit_damage - 1.0` 自然提取了增量部分。

**2b. 武器 mp_bonus 读取 — `load_equipment_bonus()`（行 18-55）**

初始化新增 `mp_pct`：
```python
bonus = {"atk": 0, "atk_pct": 0.0, "defense": 0, "mp_pct": 0.0}
```
武器读取新增：
```python
bonus["mp_pct"] += wdata.get("mp_bonus", 0.0)
```

**2c. mp_bonus 应用 — `build_player_combat_stats()`（行 137 附近）**

在 `calculate_hp_mp()` 调用后乘算：
```python
hp, mp = cls.calculate_hp_mp(player.experience, hp_buff, mp_buff, technique_hp_bonus, technique_mp_bonus)
# 新增：武器 mp_bonus
mp = int(mp * (1 + equip_bonus.get("mp_pct", 0.0)))
```

### 步骤 3：数据文件 — `config/weapons.json`

**全部 213 把武器更新。** 用 Python 脚本（`scripts/rebalance_weapons.py`）自动化处理：

**3a. Nonebot 合并武器（72 把）— 按 _source_id 精确匹配参考文件**

脚本读取参考文件，按 `_source_id` 查找对应条目，直接写入：
```python
atk_bonus = ref["atk_buff"]                    # 直接用百分比
crit_rate = int(ref["crit_buff"] * 100)         # 0.08 → 8
crit_damage = ref["critatk"]                    # 直接用加法增量
mp_bonus = ref["mp_buff"]                       # 直接用百分比
```

**3b. 原生武器（141 把）— 按品阶标准分配 buff**

每个品阶统一应用参考文件的基准值。每个品阶内的武器按 3 种模式分配（参考原版每品阶3把的设计）：

**分配模式**（以每个品阶内的 _oddN/_evenN/_thirdN 位置决定）：

| 模式 | atk_bonus | crit_rate | crit_damage | mp_bonus |
|------|-----------|-----------|-------------|----------|
| 攻击型（每品阶第1把） | 品阶 atk_buff | 0 | 0 | 0 |
| 暴击型（每品阶第2把） | 0 | 品阶 crit_buff×100 | 0 | 0 |
| 混合型（每品阶第3把） | 品阶 atk_buff/2 | 品阶 crit_buff/2×100 | 0 | 0 |

原生武器品阶→参考 buff 映射：
- 凡品 (_001, _002): atk=0.08, crit=8
- 灵品 (_003, _004): atk=0.12, crit=12
- 地品 (_005): atk=0.16, crit=16
- 天品 (_006): atk=0.20, crit=20
- 皇品 (_007): atk=0.24, crit=24
- 帝品 (_008): atk=0.28, crit=28
- 道品 (_009): atk=0.32, crit=32
- 仙品 (_010): atk=0.40, crit=40
- 混元先天 (_011, _012): atk=0.50, crit=50（取极品仙器下限）

**原生武器 crit_damage 从乘法转加法**（新公式 `max(1.5, 1.0+val)` 保持效果不变）：
- 天品 sword_006: 1.56 → 0.56
- 皇品: 1.73 → 0.73, 1.69 → 0.69, 1.64 → 0.64, ...
- 帝品: 1.68 → 0.68, 1.58 → 0.58, 1.81 → 0.81, ...
- 道品: 1.78 → 0.78
- 混元先天: 2.34 → 1.34, 2.38 → 1.38, 2.5 → 1.5, 2.13 → 1.13

**flat stats (physical_damage 等) 不变**：原生武器的扁平数值已经过精心平衡，仅更新百分比 buff 字段。

### 步骤 4：显示层更新

**4a. `handlers/equipment_handler.py`（行 82-97 区域）**

`handle_show_equipment` 中，新增武器 mp_bonus 的显示。
由于 `get_total_attributes()` 只对 main_technique 汇总 mp_bonus，需从 weapons_data 补充读取：
```python
# 在 equip display 区域末尾，额外读取武器 mp_bonus
if player.weapon and config_manager:
    wdata = config_manager.weapons_data.get(player.weapon)
    if wdata and wdata.get("mp_bonus", 0) > 0:
        equipment_lines.append(f"💧 真元 +{wdata['mp_bonus']:.0%}\n")
```

**4b. `core/shop_manager.py` — `_get_item_effect_short()`（行 486-566）**

在武器类型 `item_type in ['weapon', 'armor', 'accessory']` 分支中，新增战斗属性显示：
```python
if data.get('atk_bonus', 0) > 0:
    effects.append(f"攻击+{data['atk_bonus']:.0%}")
if data.get('crit_rate', 0) > 0:
    effects.append(f"暴击率+{data['crit_rate']}%")
if data.get('crit_damage', 0) > 0:
    effects.append(f"暴伤+{data['crit_damage']:.0%}")
if data.get('mp_bonus', 0) > 0:
    effects.append(f"真元+{data['mp_bonus']:.0%}")
```

**4c. `core/shop_manager.py` — `get_item_details_full()`（行 728-897）**

在武器详情显示中，新增战斗属性段落（`weapon_category` 显示之后）：
```python
combat_attrs = []
for key, label, fmt in [
    ('atk_bonus', '攻击力', '{:.0%}'),
    ('crit_rate', '暴击率', '+{}%'),
    ('crit_damage', '暴伤', '+{:.0%}'),
    ('mp_bonus', '真元', '+{:.0%}'),
]:
    val = data.get(key, 0)
    if val:
        combat_attrs.append(f"{label}{fmt.format(val)}")
if combat_attrs:
    details.append(f"战斗属性：{'、'.join(combat_attrs)}")
```

### 步骤 5：网页端更新

**5a. `docs/app.js`**

- `showWeaponDetail()`（行 755-795）：新增 `mp_bonus` 字段展示
- 武器表格 `renderWeapons()`（行 686-698）：特殊属性列加入 `mp_bonus`
- 战斗属性表格（行 963-996）：列中加入 `mp_bonus`

**5b. 重新生成 `docs/data/weapons.json`**

```bash
python sync_data.py
```

---

## 执行顺序

1. `models.py` — 新增 mp_bonus 字段 + display
2. `managers/combat_manager.py` — crit_damage 公式修正 + 武器 mp_bonus 读取/应用
3. `scripts/rebalance_weapons.py` — 编写自动更新脚本
4. 运行脚本 → 更新 `config/weapons.json`
5. `handlers/equipment_handler.py` — 装备显示补 mp_bonus
6. `core/shop_manager.py` — 商店/查看显示补战斗属性
7. `docs/app.js` — 网页端补 mp_bonus
8. `python sync_data.py` — 重新生成 docs/data/
9. `pytest` — 运行测试
10. 部署 + 重启 AstrBot

---

## 验证清单

- [ ] 公式 `max(1.5, 1.0 + weapon_crit + tech_crit)` 正确
  - 原生天品（原1.56→0.56）：`1.0+0.56=1.56`，效果不变
  - 极品仙器 critatk=0.4：`1.0+0.4=1.4`
  - 无上仙器 critatk=2.0（原罪）：`1.0+2.0=3.0`
- [ ] 72 把 nonebot 武器的 _source_id 全部命中参考文件
- [ ] 141 把原生武器全部获得对应品阶 buff
- [ ] mp_bonus 在装备/商店/查看三个路径可见
- [ ] mp_bonus 在战斗中正确乘算 MP
- [ ] `python sync_data.py` 无报错
- [ ] `pytest` 全通过
- [ ] 网页端显示正常（武器详情含 mp_bonus）
