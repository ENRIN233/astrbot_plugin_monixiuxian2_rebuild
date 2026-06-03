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
```

No linter/formatter is configured. Follow existing style: `snake_case` functions, `PascalCase` classes, `UPPER_CASE` constants, single-underscore private methods, Chinese docstrings.

## Architecture (4 layers)

```
main.py (entry point, 146 command registrations, 8 background tasks)
    |
handlers/ (28 handler classes — command processing, async generators)
    |
core/ (7 modules: cultivation, equipment, breakthrough, pills, shop, storage, pill_manager)
managers/ (21 modules: combat, sect, boss, rift, trade, consignment, bank, bounty, dual_cultivation, activity, etc.)
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
- **Background tasks** (8 in `main.py`): boss spawning, loan checks, spirit eye spawning, bounty expiry, consignment expiry, trade timeout, rift daily broadcast, pavilion refresh. All use exponential backoff retry.
- **`ConfigManager`** (`config_manager.py`): auto-creates missing config files from `data/default_configs.py` defaults.
- **`ActivityTracker`** (`managers/activity_manager.py`): daily activity system with 10 task types, lazy-loaded in `main.py` and injected into 8 consumer modules. Day reset is self-healing via date comparison (no background task needed).
- **State conflict architecture**: Two parallel systems block commands during busy states — (1) `@player_required` decorator checks `user_cd.type` against whitelist, (2) individual handler/manager methods check `user_cd.type != IDLE` directly. Many handlers (combat, sect, alchemy, adventure, rift, boss) bypass `@player_required` and do their own state checks.
- **Combat system** (`managers/combat_manager.py`): Two-layer defense formula `base_def = ln(exp+1)×10`, `equip_def = ln(equip_def+1)×20`. Skills (`_execute_turn_with_skill`) now check dodge_rate before execution — dodged skills still consume MP/HP and enter cooldown. DOT uses independent `dot_turns` field (separate from `turncost` CD). All 10 equipment special attributes are fully integrated.

## Data Models

- `Player` (`models.py`): main player dataclass with JSON-serialized fields (techniques, equipped items, pills, `active_pill_effects`, `daily_pill_usage`, `daily_activity`, etc.)
- `Item` (`models.py`): equipment/material dataclass with technique bonus fields: `breakthrough_bonus`, `atk_bonus`, `hp_bonus`, `mp_bonus`
- `UserStatus` enum (`models_extended.py`): `IDLE`, `CULTIVATING`, `ADVENTURING`, `EXPLORING`, `SECT_TASK`, `TRADING`
- `UserCd` (`models_extended.py`): user cooldown/state model with `type`, `create_time`, `scheduled_time`, `extra_data` (JSON)
- `CombatStats` (`managers/combat_manager.py`): combat attributes dataclass with all special attributes

## Game Systems

- **Techniques**: 258 main techniques across 9 ranks (凡品→混元先天). Four bonus fields: `exp_multiplier` (1.05–2.75), `breakthrough_bonus` (皇品+ only: 3%~15%), `atk_bonus` (+50~800), `hp_bonus` (+5%~40%), `mp_bonus` (to be populated). Applied in `breakthrough_manager.py`, `combat_manager.py`, displayed in `equipment_handler.py`, `shop_manager.py`, `bounty_handlers.py`.
- **Shentong (神通) system**: 75 active combat skills in `config/skills.json`, 4 types (attack/buff/continuous/control). Single equip slot on Player (`shentong` field). Auto-triggers based on `rate` probability, `turncost` cooldown, and MP cost (`mpcost` as max_mp percentage). Continuous skills use independent `dot_turns` field for DOT duration (longer than `turncost` CD). Skills consume MP + optional HP (`hpcost`). Buff/debuff engine in `managers/skill_manager.py`. Commands: 神通列表/我的神通/装备神通/卸下神通/神通信息. Note: `SkillHandler` is lazily imported in `main.py`, not exported from `handlers/__init__.py`.
- **Combat attributes**: Weapon special: `crit_rate`, `crit_damage`, `armor_pen`, `lifesteal`, `double_hit`. Armor special: `dodge_rate`, `crit_resist`, `reflect_pct`, `block_value`, `hp_regen_pct`. All percentage integers except `crit_damage` (multiplier) and `hp_regen_pct` (float).
- **Sect task system**: Instant completion, 10-minute cooldown stored in `user_cd.extra_data["sect_task_cd"]`, daily limit of 3 tracked via `Player.sect_task` with date-based auto-reset in `extra_data["sect_task_date"]`. Does NOT set `user_cd.type` to busy state.
- **Adventure system**: Configurable routes with risk/reward. `/中断历练` for mid-adventure forced exit (counts as completed but no rewards). `/完成历练` for normal settlement after timer expires.
- **Daily activity system** (v34): 10 daily tasks in `managers/activity_manager.py`. Player fields: `daily_activity` (JSON), `daily_activity_points` (capped at 100), `daily_activity_date`, `daily_activity_rewarded`. Reward: 1x 渡厄丹 at 100 points. Tasks: check_in(+10), adventure(+20×2), rift(+30), bounty(+20×2), shop_buy(+40), harvest(+20), alchemy(+30), smelt(+30), interest(+10), sect(+20).
- **GM compensation**: GM creates package with `/GM补偿 <物品 数量|物品 数量>`. Players claim with `/补偿`. Items auto-routed: pills → `pills_inventory`, others → `storage_ring_items`.
- **Sign-in milestones**: Rewards at 7/14/21/28 consecutive check-in days.

## Busy State Whitelist

`BUSY_STATE_ALLOWED_COMMANDS` in `handlers/utils.py` defines commands usable during any busy state. Key categories: basic info, bank ops, inventory, pill usage, storage ring operations, shop, daily activity, rankings, consignment, bounty management, settlement commands.

## Important Conventions

- All I/O is async. Handlers return `AsyncGenerator` yielding response messages.
- Database: aiosqlite, single file `sqlite3.db`. `DataBase` class handles reconnection.
- Config files in `config/` (14+ JSON files). Use `sync_data.py` to copy to `docs/data/` for website SPA.
- Use `TYPE_CHECKING` imports to avoid circular dependencies.
- Website SPA: 9 ranks only — 凡品, 灵品, 地品, 天品, 皇品, 帝品, 道品, 仙品, 混元先天.
- **`extra_data` JSON field** on `UserCd`: prefer for per-system cooldowns that shouldn't block busy state (e.g. `sect_task_cd`, route keys).
- **ASCII quotes only in Python source**: NEVER use Unicode smart quotes `"` (U+201C) / `"` (U+201D). Prefer Write tool for full-file rewrites on files with Chinese text.
- **`Item` bonus fields**: `breakthrough_bonus` (float), `atk_bonus` (int), `hp_bonus` (float), `mp_bonus` (float). Accumulated in `Player.get_total_attributes()` for main_technique type.

## Release Checklist

When bumping version, update ALL of these (search for old version string):
- `metadata.yaml` — `version:` field
- `handlers/misc_handler.py` — version string in `handle_help` text
- `README.md` — `> **版本:**` line + add changelog entry under `## 📝 更新日志`
- `docs/index.html` — `subtitle` text in sidebar
- `docs/app.js` — command count in `renderCommands()` info-box (if command count changed)

## Deployment

Plugin deploys to `C:\Users\hasu\.astrbot\data\plugins\astrbot_plugin_monixiuxian2\`. After pushing changes, sync with:
```
xcopy /E /Y "E:\Github\astrbot_plugin_monixiuxian2-main" "C:\Users\hasu\.astrbot\data\plugins\astrbot_plugin_monixiuxian2\"
```
Then restart AstrBot. Note: the deployed version can diverge from the repo — always sync after changes.
