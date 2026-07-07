# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AstrBot plugin for a text-based idle cultivation (修仙) game. Python 3.8+, runs inside the AstrBot chatbot framework process. SQLite database via `aiosqlite`, async throughout. Core systems (境界/功法/灵田/炼丹/神通) migrated from nonebot_plugin_xiuxian_2_pmv. Reference data: nonebot `data/xiuxian/` directory + `修仙_神通.txt`.

## Commands

**Python 路径**: `E:\python\python.exe`（Git Bash 中使用 `/e/python/python.exe`，`python` / `python3` 命令不可用）

```bash
pip install -r requirements.txt          # runtime deps (Pillow)
pip install -r requirements-dev.txt      # dev deps (pytest, pytest-asyncio, aiosqlite)
pytest                                   # run all tests
pytest tests/test_trade_manager.py       # run single test file
pytest -k "test_name"                    # run specific test
/e/python/python.exe sync_data.py        # sync config/*.json to docs/data/ for website
node -c docs/app.js                      # verify website JS syntax
/e/python/python.exe scripts/rebalance_weapons.py  # rebalance weapon stats
```

No linter/formatter is configured. Follow existing style: `snake_case` functions, `PascalCase` classes, `UPPER_CASE` constants, single-underscore private methods, Chinese docstrings.

## 回答风格

- 对总结、Plan、Task 以及长内容的输出使用中文，优先进行逻辑整理后使用美观的 Table 格式整齐输出；普通内容正常输出。

## Architecture (4 layers)

```
main.py (entry point, ~145 command registrations, 8 background tasks)
    |
handlers/ (~28 handler classes — command processing, async generators)
    |
core/ (5 modules: cultivation, equipment, breakthrough, pills, storage)
managers/ (~20 modules: combat, alchemy, spirit_farm, sect, boss, rift, trade, bounty, etc.)
    |
data/ (SQLite CRUD: data_manager.py, database_extended.py, migration.py)
```

**Data flow:** AstrBot message → `@filter.command()` route → `@require_whitelist` → handler → `@player_required` → manager logic → aiosqlite → response via async generator.

## Key Patterns

- **`@player_required` decorator** (`handlers/utils.py`): auth check + state enforcement + loan status. Uses `BUSY_STATE_ALLOWED_COMMANDS` whitelist to allow certain commands during busy states. Mutually exclusive states enforced via `UserStatus` enum in `models_extended.py`.
- **`@migration(version=N)` decorator** (`data/migration.py`): register DB migrations. Current version: v39. Increment `LATEST_DB_VERSION` when adding.
- **`@require_whitelist`**: AstrBot-level group access control, applied at `main.py`.
- **JSON-serialized fields**: complex data (techniques, pill effects, storage items) stored as JSON strings in SQLite TEXT columns, with getter/setter on `Player`/`Item` dataclasses.
- **Transaction safety**: critical ops use `BEGIN IMMEDIATE` with rollback. Trade/consignment use conditional UPDATE for concurrent purchase safety. CRUD methods in `database_extended.py` and `data_manager.py` accept `auto_commit=False` to suppress internal commits when composing multi-step atomic operations. Boss defeat uses CAS pattern (`UPDATE ... WHERE status = 1`, check `rowcount`) via `try_defeat_boss`.
- **Background tasks** (8 in `main.py`): boss spawning, loan checks, bounty expiry, consignment expiry, trade timeout, rift daily broadcast, sect material distribution (11:00 + 12:00 daily), auto sect owner change. All use exponential backoff retry.
- **`ConfigManager`** (`config_manager.py`): loads 20+ JSON config files. `get_level_data()` returns unified 58-level realm data (no longer branches on cultivation_type). `game_config` loaded via `_load_config_with_default`.
- **`ActivityTracker`** (`managers/activity_manager.py`): daily activity system with 8 task types (签到/秘境/悬赏/灵田/炼丹/炼金/利息/宗门), lazy-loaded in `main.py` and injected into consumer modules. Day reset is self-healing via date comparison (no background task needed).
- **State conflict architecture**: Two parallel systems block commands during busy states — (1) `@player_required` decorator checks `user_cd.type` against whitelist, (2) individual handler/manager methods check `user_cd.type != IDLE` directly. Many handlers bypass `@player_required` and do their own state checks.

## Numerical Formulas (Excel-aligned)

All formulas aligned to `修仙.xlsx` design document:

- **HP**: `max(1000, int(experience / 2 * (1 + hp_buff))) * (1 + hp_bonus)`
- **MP**: `max(100, int(experience * (1 + mp_buff))) * (1 + mp_bonus)`
- **ATK**: `max(100, int(experience / 10)) × (atkpractice×0.04+1) × (1+technique) × (1+weapon) × (1+armor) + permanent_buff` — multiplicative stacking, no flat equip bonus
- **Power**: `round(experience × root_speed × realm_spend)` — `realm_spend` from level_config
- **Cultivation exp**: `60 × minutes × root_speed × realm_spend × (1+technique_bonus) × (1+closing_exp_bonus) × pill × (1+land) × (1+permanent_mult)`
- **Breakthrough**: base_rate from level_config + failure_accumulation (每次+1%, 无上限) + technique_bonus + breakthrough_number/100 + pill_bonus, clamped to [0, max_rate]. Major realm transition detected by `is_major_realm_transition()` (level_index % 3 == 2). Realm-specific pills (1400-1421, 15100-15103) only work on major realm transitions. Universal pills (15151-15153) work on any transition. `max_uses` enforced via `permanent_pill_usage` tracking. Pill effects persist across failures (`expiry_time=0`), only consumed on success via `consume_breakthrough_boost_only()`. `death_protection` effects are one-shot: consumed after first failure protection. `get_breakthrough_modifiers` accepts `target_level_index` to filter pill effects by target realm. `calculate_breakthrough_success_rate` does NOT add pill bonus from config (it's already in `temp_bonus` via active effects).
- **Crit damage**: `max(1.5, 1.0 + weapon_crit_damage + technique_crit_damage + impart_burst_per)` — additive delta from 1.0 base
- **Defense**: percentage-based `def_buff` from armor + weapon `damage_reduction` + technique `damage_reduction`, capped at 0.9. No ln-based formula.
- **Damage formula**: `atk × 0.5 × crit_mult × 1.5 × float × (1 - def_buff + armor_pen/100 + sub_break_pct)` — Excel's 0.5 damage halving + 1.5 weapon bonus. `sub_break_pct` from sub-technique buff_type 13. Continuous DOT applies `def_buff` defense: `raw × (1 - def_buff)`.
- **Boss damage**: player ATK ×2 against bosses. Boss buff system: 8 buff types (atk/crit/crit_dmg/reduce_lifesteal + reduce_atk/reduce_crit/reduce_crit_dmg) across 4 tiers. Boss special attacks (紫玄掌 8%, 5x+30%HP; 子龙朱雀 8%, 3x ignore 50% defense; normal 84%). Boss stats restored in try/finally block.
- **Level scaling**: `game_config.json` `level_scaling.bounty_rift_coefficient` (default 0.045) controls悬赏令/秘境 level bonus. Boss 20 tiers cover all 58 levels.
- **Combat stat aggregation**: Two parallel read paths — (1) `Player.get_total_attributes()` for display, (2) `load_equipment_bonus()` + `build_player_combat_stats()` for actual combat. These paths can diverge.

## Realm System (58 levels)

Unified 58-level hierarchy (index 0=江湖好手 → 57=合道境圆满). 19 major realms × 3 sub-stages (初期/中期/圆满) + 1 starter. Stored in `config/level_config.json` with fields: `name`, `exp_needed`, `success_rate`, `spend`.

Realm names (aligned to nonebot `境界.txt`): 洗髓境(1-3), 练气境(4-6), 化灵境(7-9), 筑基境(10-12), 结丹境(13-15), 金丹境(16-18), 紫府境(19-21), 凝婴境(22-24), 元婴境(25-27), 化神境(28-30), 炼虚境(31-33), 出窍境(34-36), 分神境(37-39), 合体境(40-42), 大乘境(43-45), 轮回境(46-48), 渡劫境(49-51), 飞升境(52-54), 合道境(55-57).

v37 removed flat attributes (physical_damage, magic_damage, physical_defense, magic_defense, mental_power) from Player model, Item model, combat system, pill system, and all UI. `cultivation_type` field retained for backward compatibility but no longer affects logic.

## Data Models

- `Player` (`models.py`): main player dataclass. Equipment slots: `weapon`, `armor`, `main_technique`, `shentong`, `sub_technique`, `furnace`. JSON-serialized fields: `techniques`, `pills_inventory`, `active_pill_effects`, `permanent_pill_gains`, `storage_ring_items`, `daily_activity`, etc. `permanent_pill_gains` has two scopes: `level_{index}` for per-level `_gain` attributes (受境界属性上限限制), `_global` for multiplier effects (cultivation_speed, death_protection — permanent, survive level-up).
- `Item` (`models.py`): equipment/material dataclass. Technique bonus fields: `exp_multiplier`, `breakthrough_bonus`, `atk_bonus`, `hp_bonus`, `mp_bonus`, `crit_rate`, `crit_damage`, `closing_exp_bonus`, `closing_recovery_bonus`, `damage_reduction`, `breakthrough_number`, `dual_cultivation_bonus`, `alchemy_exp_bonus`, `alchemy_count_bonus`, `harvest_bonus`, `random_buff`, `exclusive_weapon_id`. Weapon combat attrs (`crit_rate`, `crit_damage`, `armor_pen`, `lifesteal`, `double_hit`) and armor attrs (`def_buff`, `dodge_rate`, `crit_resist`, `reflect_pct`, `block_value`, `hp_regen_pct`, `atk_bonus`) read from raw config dicts by `combat_manager.load_equipment_bonus()`.
- `UserStatus` enum (`models_extended.py`): `IDLE`, `CULTIVATING`, `ADVENTURING`(deprecated,保留值2兼容DB), `EXPLORING`, `SECT_TASK`, `TRADING`
- `UserCd` (`models_extended.py`): user cooldown/state model with `type`, `create_time`, `scheduled_time`, `extra_data` (JSON)
- `CombatStats` (`managers/combat_manager.py`): combat attributes dataclass with `def_buff` (percentage reduction), `damage_reduction`, and all special attributes. Sub-technique fields: `sub_buff_type`, `sub_buff_value`, `sub_buff_value2`, `sub_break_pct`.

## Game Systems

- **Techniques (功法)**: 79 main techniques in `config/items.json` (type=`main_technique`), across 14 ranks (人阶下品→无上仙法). Synced from nonebot with full field set including `closing_exp_bonus` (闭关经验), `closing_recovery_bonus` (经验保护), `damage_reduction` (减伤), `breakthrough_number` (突破概率), `harvest_bonus` (采集), `alchemy_count_bonus` (出丹数), `alchemy_exp_bonus` (炼丹经验).
- **Spirit Farm (灵田)**: Harvest-on-cooldown model. Commands: 灵田/开垦灵田/灵田开垦/灵田收取/升级收取/升级控火. Harvest formula: `num = herb_fields + harvest_level + technique_harvest_bonus`. Cooldown: `48h × (1 - 0.05×speed)`. 108 herb types in `config/herbs.json` (一品→九品, 12 per grade).
- **Alchemy (炼丹)**: 寒热调和 system. Commands: 炼丹/配方/装备炼丹炉/卸下炼丹炉. Recipe matching: 主药+药引+辅药 with cold/hot harmony check + elixir_config matching. 49 recipes in `config/alchemy_recipes.json`. Pill count = `1 + fire_control + alchemy_count_bonus + furnace_buff`. Crafted pills → `pills_inventory`. 3 furnaces in `config/furnaces.json` with buff values (+0/+1/+2 pills).
- **Pills (丹药)**: Active pill configs in `config/utility_pills.json` (healing 2000-2008, permanent ATK 2009-2018, breakthrough boost 1400-1421 + 15100-15103 + 15151-15153). Old nonebot pills in `config/pills.json` (now empty). Healing pills use `heal_hp_pct` effect. Permanent ATK pills store `flat_atk_bonus` in `permanent_pill_gains["_global"]`. Breakthrough boost pills create active effects (`expiry_time=0`, persist indefinitely) with `max_uses` enforcement and `target_level_index` stored in effect dict for filtering. `consume_breakthrough_boost_only()` removes only breakthrough_boost/debuff on success, preserving death_protection. Death_protection effects are one-shot: consumed after protecting once on failure. `get_breakthrough_modifiers(player, target_level_index)` filters active effects by target realm.
- **Shentong (神通)**: 53 active combat skills in `config/skills.json` (aligned to xlsx reference), 4 types (attack/buff/continuous/control). Single equip slot on Player (`shentong` field). Auto-triggers based on `rate` probability, `turncost` cooldown, MP cost (`mpcost` × raw_base_mp). Continuous skills use independent `dot_turns` field for DOT duration. Buff/debuff engine in `managers/skill_manager.py`.
- **Sub-technique (辅修功法)**: 23 combat support techniques in `config/sub_techniques.json`. Single equip slot on Player (`sub_technique` field). 13 buff_types: 1=ATK%, 2=crit_rate, 3=crit_dmg, 4=HP regen, 5=MP regen, 6=HP steal, 7=MP steal, 8=poison, 9=dual steal, 13=armor pierce. buff_type 1/2/3 applied at combat start in `build_player_combat_stats()`. buff_type 4-9 applied per-turn in `_apply_sub_technique_effects()`. buff_type 13 (`sub_break_pct`) applied in `execute_attack()` defense calculation.
- **Combat attributes**: Weapon special: `crit_rate`, `crit_damage` (additive delta), `armor_pen`, `lifesteal`, `double_hit`, `damage_reduction`. Armor special: `def_buff`, `dodge_rate`, `crit_resist`, `reflect_pct`, `block_value`, `hp_regen_pct`, `atk_bonus`.
- **Boss system** (`managers/boss_manager.py`): 20 tiers from 洗髓(Lv0) to 合道(Lv57). Boss buff system: 8 buff types across 4 tiers (atk/crit/crit_dmg/reduce_lifesteal + reduce_atk/reduce_crit/reduce_crit_dmg). Special attacks: 紫玄掌 (8%, 5x+30%HP), 子龙朱雀 (8%, 3x ignore 50% defense), normal (84%). Player ATK ×2 in boss fights.
- **Bounty system** (`managers/bounty_manager.py`): 100% drop of technique, skill, or sub-technique on completion. Drop config in `config/bounty_drop_config.json` with `type_rate` weights per rank (14 ranks). Items randomly selected from `gf_list` (功法), `st_list` (神通), `fx_list` (辅修功法). Daily limit: 3 bounties.
- **Sect system** (`managers/sect_manager.py`): 18 commands. Sect tasks: 5 types (2 HP-cost + 3 stone-cost), randomized, 3/day, 10-min cooldown. Attack practice: 50-level discrete cost table from Excel. Elixir room: 8 levels (黄级→无上), guaranteed 渡厄丹 daily. Member limits per position based on elixir room level. Auto owner change: 7 days offline. Material distribution: 11:00 + 12:00 daily at 1:1 rate.
- **Daily activity system**: 8 daily tasks in `managers/activity_manager.py` (签到/秘境/悬赏/灵田/炼丹/炼金/利息/宗门). Reward: 1x 渡厄丹 at 100 points.
- **GM compensation**: `/GM补偿 <物品 数量|物品 数量>`, claim with `/补偿`. Items auto-routed: pills → `pills_inventory`, others → `storage_ring_items`.
- **Permanent pill system**: `_gain` attributes per `level_{index}` for lifespan/spiritual_qi/blood_qi（受境界上限限制）, `_global` multipliers for cultivation_speed/death_protection（permanent across level-up）.
- **Impart cards**: 105 cards in `config/impart_cards.json` (10 types: atk/hp/mp/crit_rate/crit_damage/closing_exp/alchemy_count/harvest/dual_cultivation/boss_atk). Config loaded but card collection system not yet implemented.

## Deleted Systems (do not re-add)

- **三阁 (Shop/Pavilion)**: NPC shop system removed. `core/shop_manager.py` and `handlers/shop_handler.py` deleted. Player trading via 寄售 (consignment) and 面对面交易 (trade) remains.
- **历练 (Adventure)**: Route-based adventure system removed. `managers/adventure_manager.py` and `handlers/adventure_handlers.py` deleted. `UserStatus.ADVENTURING` enum value retained for DB compatibility.

## Item Type Structure

`config/items.json` contains only two types after cleanup:
- `材料` (14 items): crafting materials for alchemy
- `main_technique` (79 items): techniques/功法 with `price=0` (not purchasable in shop)

`config/weapons.json` contains `weapon` (66) and `armor` (38) types.
`config/skills.json` contains 53 skills (aligned to xlsx reference).
`config/sub_techniques.json` contains 23 sub-techniques (辅修功法) with `buff_type`/`buff`/`buff2`/`break_pct` fields.

## Rank Name Systems

Three distinct rank naming conventions (all aligned to nonebot):
- **武器**: 下品符器 → 上品符器 → 下品法器 → 上品法器 → 下品纯阳法器 → 上品纯阳法器 → 下品通天法器 → 上品通天法器 → 下品仙器 → 上品仙器 → 极品仙器 → 无上仙器 (12 tiers)
- **防具**: 下品符器 → 上品符器 → 下品玄器 → 上品玄器 → 下品纯阳 → 上品纯阳 → 下品通天 → 上品通天 → 下品仙器 → 上品仙器 → 极品仙器 → 无上仙器 (12 tiers)
- **心法/神通/辅修功法**: 人阶下品 → 人阶上品 → 黄阶下品 → 黄阶上品 → 玄阶下品 → 玄阶上品 → 地阶下品 → 地阶上品 → 天阶下品 → 天阶上品 → 仙阶下品 → 仙阶上品 → 仙阶极品 → 无上仙法/无上神通 (14 tiers)

## Spiritual Root System (11 types)

| Type | Roots | Speed | Weight |
|---|---|---|---|
| PSEUDO (凡品) | 伪 | 0 | 2500 |
| TRUE (下品) | 多灵根组合 (25种) | 1.0 | 1000 |
| WUXING (中品) | 金/木/水/火/土 | 1.0 | 1000 |
| VARIANT (上品) | 雷/冰/风/暗/光 | 1.2 | 1800 |
| HEAVENLY (极品) | 天金/天木/天水/天火/天土/天雷 | 1.3 | 1800 |
| DRAGON (仙品) | 空间/时间/言灵 | 1.4 | 1300 |
| SUPER (神品) | 日/月 | 1.5 | 1000 |
| FUSION (传说) | 融合 | 1.7 | 600 |
| CHAOS (神话) | 混沌 | 2.0 | 300 |
| MECH (禁忌) | 机械核心 | 2.3 | 100 |
| OTHERWORLD (超越) | 异世界之力 | 2.5 | 100 |

Speeds configured in `_conf_schema.json` `SPIRIT_ROOT_SPEEDS`. Weights in `SPIRIT_ROOT_WEIGHTS`. Root pools in `core/cultivation_manager.py` `root_pools` dict.

## Busy State Whitelist

`BUSY_STATE_ALLOWED_COMMANDS` in `handlers/utils.py` defines commands usable during any busy state. Key categories: basic info, bank ops, inventory, pill usage, storage ring operations, daily activity, rankings, consignment, bounty management, settlement commands.

## Design Documentation

Design specs and implementation plans live in `docs/superpowers/`:
- `docs/superpowers/specs/` — feature design documents (e.g., economy-trading, reincarnation system)
- `docs/superpowers/plans/` — implementation plans derived from specs

Planned systems with existing design specs:
- **轮回系统 (Reincarnation)**: `docs/superpowers/specs/2026-06-19-reincarnation-system-design.md` — cross-life progression via `reincarnation_data` table, triggers at 轮回境 (level 46+)

## Important Conventions

- All I/O is async. Handlers return `AsyncGenerator` yielding response messages.
- Database: aiosqlite, single file `sqlite3.db`. `DataBase` class handles reconnection.
- Config files in `config/` (20+ JSON files). Use `sync_data.py` to copy to `docs/data/` for website SPA.
- Use `TYPE_CHECKING` imports to avoid circular dependencies.
- **`extra_data` JSON field** on `UserCd`: prefer for per-system cooldowns that shouldn't block busy state.
- **ASCII quotes only in Python source**: NEVER use Unicode smart quotes `"` / `"`. Prefer Write tool for full-file rewrites on files with Chinese text.
- **`Item` bonus fields**: Weapon `atk_bonus`/`crit_rate`/`crit_damage`/`mp_bonus`/`damage_reduction` are read by combat_manager from raw config dicts, bypassing the Item model.

## Release Checklist

When bumping version, update ALL of these (search for old version string):
- `metadata.yaml` — `version:` field
- `handlers/misc_handler.py` — version string in `handle_help` text + `/修仙帮助` 命令列表
- `README.md` — `> **版本:**` line + add changelog entry under `## 📝 更新日志`
- `docs/index.html` — `subtitle` text in sidebar
- `docs/app.js` — command count in `renderCommands()` info-box (if command count changed)
- 如有数据库 schema 变更，评估是否需要更新 `data/migration.py` 的版本号
