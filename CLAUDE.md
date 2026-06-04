# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AstrBot plugin for a text-based idle cultivation (修仙) game. Python 3.8+, runs inside the AstrBot chatbot framework process. SQLite database via `aiosqlite`, async throughout.

## Commands

```bash
pip install -r requirements.txt          # runtime deps (Pillow)
pip install -r requirements-dev.txt      # dev deps (pytest, pytest-asyncio, aiosqlite)
pytest                                   # run all tests
pytest tests/test_trade_manager.py       # run single test file
pytest -k "test_name"                    # run specific test
python sync_data.py                      # sync config/*.json to docs/data/ for website
node -c docs/app.js                      # verify website JS syntax
python scripts/rebalance_weapons.py      # rebalance weapon stats from reference data (scripts/)
```

No linter/formatter is configured. Follow existing style: `snake_case` functions, `PascalCase` classes, `UPPER_CASE` constants, single-underscore private methods, Chinese docstrings.

## 回答风格

- 对总结、Plan、Task 以及长内容的输出使用中文，优先进行逻辑整理后使用美观的 Table 格式整齐输出；普通内容正常输出。

## Architecture (4 layers)

```
main.py (entry point, 152 command registrations, 10 background tasks)
    |
handlers/ (29 handler classes — command processing, async generators)
    |
core/ (6 modules: cultivation, equipment, breakthrough, pills, shop, storage, pill_manager)
managers/ (20 modules: combat, sect, boss, rift, trade, consignment, bank, bounty, dual_cultivation, activity, skill, etc.)
    |
data/ (SQLite CRUD: data_manager.py, database_extended.py, migration.py v34)
```

**Data flow:** AstrBot message → `@filter.command()` route → `@require_whitelist` → handler → `@player_required` → manager logic → aiosqlite → response via async generator.

## Key Patterns

- **`@player_required` decorator** (`handlers/utils.py`): auth check + state enforcement + loan status. Uses `BUSY_STATE_ALLOWED_COMMANDS` whitelist to allow certain commands during busy states. Mutually exclusive states enforced via `UserStatus` enum in `models_extended.py`.
- **`@migration(version=N)` decorator** (`data/migration.py`): register DB migrations. Current version: v34. Increment `LATEST_DB_VERSION` when adding.
- **`@require_whitelist`**: AstrBot-level group access control, applied at `main.py`.
- **JSON-serialized fields**: complex data (techniques, pill effects, storage items) stored as JSON strings in SQLite TEXT columns, with getter/setter on `Player`/`Item` dataclasses.
- **Transaction safety**: critical ops use `BEGIN IMMEDIATE` with rollback. Trade/consignment use conditional UPDATE for concurrent purchase safety.
- **Background tasks** (10 in `main.py`): boss spawning, loan checks, spirit eye spawning, bounty expiry, consignment expiry, trade timeout, rift daily broadcast, pavilion refresh, sect material distribution (daily 12:00), auto sect owner change. All use exponential backoff retry.
- **`ConfigManager`** (`config_manager.py`): auto-creates missing config files from `data/default_configs.py` defaults.
- **`ActivityTracker`** (`managers/activity_manager.py`): daily activity system with 10 task types, lazy-loaded in `main.py` and injected into 8 consumer modules. Day reset is self-healing via date comparison (no background task needed).
- **State conflict architecture**: Two parallel systems block commands during busy states — (1) `@player_required` decorator checks `user_cd.type` against whitelist, (2) individual handler/manager methods check `user_cd.type != IDLE` directly. Many handlers (combat, sect, alchemy, adventure, rift, boss) bypass `@player_required` and do their own state checks.
- **Combat system** (`managers/combat_manager.py`): Two-layer defense formula `base_def = ln(exp+1)×10`, `equip_def = ln(equip_def+1)×20`. Skills (`_execute_turn_with_skill`) check dodge_rate before execution — dodged skills still consume MP/HP and enter cooldown. DOT uses independent `dot_turns` field (separate from `turncost` CD). All 10 equipment special attributes are fully integrated.
- **Combat stat aggregation**: Two parallel read paths — (1) `Player.get_total_attributes()` uses `Item` objects for display/ranking, (2) `load_equipment_bonus()` + `build_player_combat_stats()` reads raw config dicts from `config_manager.weapons_data` for actual combat. These paths can diverge.
- **Crit damage formula**: `max(1.5, 1.0 + weapon_crit_damage + technique_crit_damage)` — weapon/technique `crit_damage` values are additive deltas from the 1.0 base (e.g., 0.56 = 1.56x multiplier). The `max(1.5, ...)` floor ensures minimum 1.5x crit.

## Data Models

- `Player` (`models.py`): main player dataclass with JSON-serialized fields (techniques, equipped items, pills, `active_pill_effects`, `daily_pill_usage`, `daily_activity`, etc.)
- `Item` (`models.py`): equipment/material dataclass. Technique bonus fields: `breakthrough_bonus` (float), `atk_bonus` (float, percentage), `hp_bonus` (float), `mp_bonus` (float). Weapon also uses `mp_bonus` for combat MP scaling. Combat special attrs (`armor_pen`, `lifesteal`, `double_hit`, `dodge_rate`, `crit_resist`, `reflect_pct`, `block_value`, `hp_regen_pct`) are NOT on `Item` — read from raw JSON dicts by `combat_manager.load_equipment_bonus()`.
- `UserStatus` enum (`models_extended.py`): `IDLE`, `CULTIVATING`, `ADVENTURING`, `EXPLORING`, `SECT_TASK`, `TRADING`
- `UserCd` (`models_extended.py`): user cooldown/state model with `type`, `create_time`, `scheduled_time`, `extra_data` (JSON)
- `CombatStats` (`managers/combat_manager.py`): combat attributes dataclass with all special attributes

## Game Systems

- **Techniques**: 258 main techniques across 9 ranks (凡品→混元先天). Bonus fields: `exp_multiplier` (1.05–2.75), `breakthrough_bonus` (皇品+ only: 3%~15%), `atk_bonus` (0.05~2.62), `hp_bonus` (0.04~4.98), `mp_bonus` (0.03~4.19), `crit_rate` (帝品+: 0~34), `crit_damage` (帝品+: 0.0~0.60 additive). Applied in `breakthrough_manager.py`, `combat_manager.py`, displayed in `equipment_handler.py`, `shop_manager.py`, `bounty_handlers.py`.
- **Weapon buff system**: Weapons have percentage-based combat buffs — `atk_bonus` (attack%), `crit_rate` (crit chance%), `crit_damage` (crit damage additive delta), `mp_bonus` (MP%). These are read by `combat_manager.load_equipment_bonus()` directly from raw config dicts. `crit_damage` uses additive system: stored value is delta from 1.0 base (e.g., 0.56 means 1.56x crit). Native weapons follow 3-pattern distribution per rank (attack/crit/mixed). Nonebot-merged weapons matched by `_source_id` to reference data.
- **Shentong (神通) system**: 75 active combat skills in `config/skills.json`, 4 types (attack/buff/continuous/control). Single equip slot on Player (`shentong` field). Auto-triggers based on `rate` probability, `turncost` cooldown, and MP cost (`mpcost` as max_mp percentage). Continuous skills use independent `dot_turns` field for DOT duration (longer than `turncost` CD). Skills consume MP + optional HP (`hpcost`). Buff/debuff engine in `managers/skill_manager.py`. Commands: 神通列表/我的神通/装备神通/卸下神通/神通信息. Note: `SkillHandler` is lazily imported in `main.py`, not exported from `handlers/__init__.py`.
- **Combat attributes**: Weapon special: `crit_rate`, `crit_damage` (additive delta), `armor_pen`, `lifesteal`, `double_hit`. Armor special: `dodge_rate`, `crit_resist`, `reflect_pct`, `block_value`, `hp_regen_pct`. All percentage integers except `crit_damage` (float additive delta) and `hp_regen_pct` (float).
- **Sect system** (`managers/sect_manager.py`): Full-featured sect with 17 commands. **Sect tasks**: instant completion, fixed rewards (contribution +10,000, materials +100,000, scale +50,000), 10-minute cooldown via `extra_data["sect_task_cd"]`, daily limit of 3 via `Player.sect_task` with date auto-reset. Does NOT set `user_cd.type` to busy state. **Attack practice**: up to Lv.50, each level +4% ATK (integrated into `combat_manager.build_player_combat_stats`), costs lingshi + sect scale. **Elixir room**: 5 levels (黄→仙), upgrades cost lingshi + scale, daily pill claim with weighted random by rank from `exp_pills_data`, `pill_rank_max` limits rank ceiling per level. **Auto owner change**: transfers to highest-contributing member after 7 days offline. **Material distribution**: daily at 12:00, `scale × rate` added to `sect_materials`. **Sect rename**: costs 500 contribution.
- **Adventure system**: Configurable routes with risk/reward. `/中断历练` for mid-adventure forced exit (counts as completed but no rewards). `/完成历练` for normal settlement after timer expires.
- **Daily activity system** (v34): 10 daily tasks in `managers/activity_manager.py`. Player fields: `daily_activity` (JSON), `daily_activity_points` (capped at 100), `daily_activity_date`, `daily_activity_rewarded`. Reward: 1x 渡厄丹 at 100 points. Tasks: check_in(+10), adventure(+20×2), rift(+30), bounty(+20×2), shop_buy(+40), harvest(+20), alchemy(+30), smelt(+30), interest(+10), sect(+20).
- **GM compensation**: GM creates package with `/GM补偿 <物品 数量|物品 数量>`. Players claim with `/补偿`. Items auto-routed: pills → `pills_inventory`, others → `storage_ring_items`.
- **Sign-in milestones**: Rewards at 7/14/21/28 consecutive check-in days.

## Busy State Whitelist

`BUSY_STATE_ALLOWED_COMMANDS` in `handlers/utils.py` defines commands usable during any busy state. Key categories: basic info, bank ops, inventory, pill usage, storage ring operations, shop, daily activity, rankings, consignment, bounty management, settlement commands.

## Important Conventions

- All I/O is async. Handlers return `AsyncGenerator` yielding response messages.
- Database: aiosqlite, single file `sqlite3.db`. `DataBase` class handles reconnection.
- Config files in `config/` (15+ JSON files, including `sect_config.json`). Use `sync_data.py` to copy to `docs/data/` for website SPA.
- Use `TYPE_CHECKING` imports to avoid circular dependencies.
- Website SPA: 9 ranks only — 凡品, 灵品, 地品, 天品, 皇品, 帝品, 道品, 仙品, 混元先天.
- **`extra_data` JSON field** on `UserCd`: prefer for per-system cooldowns that shouldn't block busy state (e.g. `sect_task_cd`, route keys).
- **ASCII quotes only in Python source**: NEVER use Unicode smart quotes `"` (U+201C) / `"` (U+201D). Prefer Write tool for full-file rewrites on files with Chinese text.
- **`Item` bonus fields**: `breakthrough_bonus` (float), `atk_bonus` (float, percentage), `hp_bonus` (float), `mp_bonus` (float). Accumulated in `Player.get_total_attributes()` for main_technique type only. Weapon `atk_bonus`/`crit_rate`/`crit_damage`/`mp_bonus` are read by combat_manager from raw config dicts, bypassing the Item model.

## Release Checklist

When bumping version, update ALL of these (search for old version string):
- `metadata.yaml` — `version:` field
- `handlers/misc_handler.py` — version string in `handle_help` text + `/修仙帮助` 命令列表（如有新指令）
- `README.md` — `> **版本:**` line + add changelog entry under `## 📝 更新日志`
- `docs/index.html` — `subtitle` text in sidebar
- `docs/app.js` — command count in `renderCommands()` info-box (if command count changed)
- 如有数据库 schema 变更，评估是否需要更新 `data/migration.py` 的版本号
