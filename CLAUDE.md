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
main.py (entry point, 121 command registrations, 5 background tasks)
    |
handlers/ (26 handler classes — command processing, async generators)
    |
core/ (7 modules: cultivation, equipment, breakthrough, pills, shop, storage, pill_manager)
managers/ (18 modules: combat, sect, boss, rift, trade, consignment, bank, bounty, dual_cultivation, etc.)
    |
data/ (SQLite CRUD: data_manager.py, database_extended.py, migration.py v28)
```

**Data flow:** AstrBot message → `@filter.command()` route → `@require_whitelist` → handler → `@player_required` → manager logic → aiosqlite → response via async generator.

## Key Patterns

- **`@player_required` decorator** (`handlers/utils.py`): auth check + state enforcement + loan status. Used by most command handlers. Mutually exclusive states enforced via `UserStatus` enum in `models_extended.py`.
- **`@migration(version=N)` decorator** (`data/migration.py`): register DB migrations. Current version: v28. Increment `LATEST_DB_VERSION` when adding.
- **`@require_whitelist`**: AstrBot-level group access control, applied at `main.py`.
- **JSON-serialized fields**: complex data (techniques, pill effects, storage items) stored as JSON strings in SQLite TEXT columns, with getter/setter on `Player`/`Item` dataclasses.
- **Transaction safety**: critical ops use `BEGIN IMMEDIATE` with rollback. Trade/consignment use conditional UPDATE for concurrent purchase safety.
- **Background tasks** (5 in `main.py`): boss spawning, loan checks, spirit eye spawning, bounty expiry, consignment expiry. All use exponential backoff retry.
- **`ConfigManager`** (`config_manager.py`): auto-creates missing config files from `data/default_configs.py` defaults.

## Data Models

- `Player` (`models.py`): main player dataclass with JSON-serialized fields (techniques, equipped items, pills, `active_pill_effects`, `daily_pill_usage`, etc.)
- `Item` (`models.py`): equipment/material dataclass
- `UserStatus` enum (`models_extended.py`): `IDLE`, `CULTIVATING`, `ADVENTURING`, `EXPLORING`, `SECT_TASK`, `TRADING`
- `CombatStats` (`managers/combat_manager.py`): combat attributes dataclass

## Game Systems (recent changes)

- **Spirit eye**: provides cultivation efficiency bonus (+15%/25%/35%/50%), not passive exp income. Stored as `cultivation_bonus` percentage.
- **Dual cultivation**: both players gain 1% of the SUM of both players' experience. Dragon Tiger Pill doubles this to 2%.
- **Techniques**: 258 main techniques across 9 ranks (凡品→混元先天), `exp_multiplier` range 1.05–2.75. Main techniques provide 3 bonuses: `breakthrough_bonus` (success rate, 皇品+ only: 3%~15%), `atk_bonus` (flat ATK +50~800), `hp_bonus` (HP +5%~40%). Applied in `breakthrough_manager.py`, `combat_manager.py`, and displayed in `equipment_handler.py`, `shop_manager.py`, `bounty_handlers.py`.
- **Batch pill consumption**: `/服用丹药 <name> [qty]` — respects inventory, daily limits (dual cultivation pills: 2/day), lifetime limits (permanent pills: 2/type), and 30% attribute caps. Implemented in `core/pill_manager.py`.
- **Batch planting**: `/种植 <herb> [qty]` — respects available farm slots. Implemented in `managers/spirit_farm_manager.py`.
- **Bounty system**: 3 daily bounties, pre-rolled technique rewards with dynamic drop rates.
- **Equipment special attributes**: `dodge_rate`, `crit_resist`, `reflect_pct`, `block_value`, `hp_regen_pct` (percentage integers, NOT 0-1 decimals).
- **Weapon combat attributes**: `crit_rate`, `armor_pen`, `double_hit`, `lifesteal` are percentage integers (e.g., 3 = 3%). `crit_damage` is a multiplier (e.g., 1.73 = 173%). `atk_bonus` is a decimal (e.g., 0.18 = 18%).
- **Shentong (神通) system**: 87 active combat skills in `config/skills.json`, 4 types (attack/buff/continuous/control). Single equip slot on Player (`shentong` field). Auto-triggers in combat based on `rate` probability, `turncost` cooldown, and MP cost. Skills consume MP (first MP consumer). Buff/debuff engine in `managers/skill_manager.py` (`ActiveBuff`, `CombatSkillState`). Combat integration in `managers/combat_manager.py` (`_execute_turn_with_skill`). Commands: 神通列表/我的神通/装备神通/卸下神通/神通信息.

## Important Conventions

- All I/O is async. Handlers return `AsyncGenerator` yielding response messages.
- Database: aiosqlite, single file `sqlite3.db`. `DataBase` class handles reconnection.
- Config files live in `config/` (13 JSON files). System configs auto-created from defaults on first run. Use `sync_data.py` to copy to `docs/data/` for the website SPA.
- Use `TYPE_CHECKING` imports to avoid circular dependencies.
- Website SPA (`docs/app.js`): reads from `docs/data/*.json`. All 9 ranks are: 凡品, 灵品, 地品, 天品, 皇品, 帝品, 道品, 仙品, 混元先天. Do NOT include 珍品/圣品/神品.
- **`Item` dataclass bonus fields** (`models.py`): `breakthrough_bonus` (float, e.g. 0.02), `atk_bonus` (int, flat), `hp_bonus` (float, e.g. 0.05). Added to `Item` class and accumulated in `Player.get_total_attributes()` for main_technique type items.

## Release Checklist

When bumping version: update `metadata.yaml`, `handlers/misc_handler.py` (version string in help text), and `README.md`.
