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
data/ (SQLite CRUD: data_manager.py, database_extended.py, migration.py v33)
```

**Data flow:** AstrBot message → `@filter.command()` route → `@require_whitelist` → handler → `@player_required` → manager logic → aiosqlite → response via async generator.

## Key Patterns

- **`@player_required` decorator** (`handlers/utils.py`): auth check + state enforcement + loan status. Uses `BUSY_STATE_ALLOWED_COMMANDS` whitelist to allow certain commands during busy states. Mutually exclusive states enforced via `UserStatus` enum in `models_extended.py`.
- **`@migration(version=N)` decorator** (`data/migration.py`): register DB migrations. Current version: v33. Increment `LATEST_DB_VERSION` when adding.
- **`@require_whitelist`**: AstrBot-level group access control, applied at `main.py`.
- **JSON-serialized fields**: complex data (techniques, pill effects, storage items) stored as JSON strings in SQLite TEXT columns, with getter/setter on `Player`/`Item` dataclasses.
- **Transaction safety**: critical ops use `BEGIN IMMEDIATE` with rollback. Trade/consignment use conditional UPDATE for concurrent purchase safety.
- **Background tasks** (8 in `main.py`): boss spawning, loan checks, spirit eye spawning, bounty expiry, consignment expiry, trade timeout, rift daily broadcast, pavilion refresh. All use exponential backoff retry.
- **`ConfigManager`** (`config_manager.py`): auto-creates missing config files from `data/default_configs.py` defaults.
- **`ActivityTracker`** (`managers/activity_manager.py`): daily activity system with 10 task types, lazy-loaded in `main.py` and injected into 8 consumer modules. Day reset is self-healing via date comparison (no background task needed).
- **State conflict architecture**: Two parallel systems block commands during busy states — (1) `@player_required` decorator checks `user_cd.type` against whitelist, (2) individual handler/manager methods check `user_cd.type != IDLE` directly. Many handlers (combat, sect, alchemy, adventure, rift, boss) bypass `@player_required` and do their own state checks.

## Data Models

- `Player` (`models.py`): main player dataclass with JSON-serialized fields (techniques, equipped items, pills, `active_pill_effects`, `daily_pill_usage`, `daily_activity`, etc.)
- `Item` (`models.py`): equipment/material dataclass
- `UserStatus` enum (`models_extended.py`): `IDLE`, `CULTIVATING`, `ADVENTURING`, `EXPLORING`, `SECT_TASK`, `TRADING`
- `UserCd` (`models_extended.py`): user cooldown/state model with `type`, `create_time`, `scheduled_time`, `extra_data` (JSON)
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
- **Shentong (神通) system**: 87 active combat skills in `config/skills.json`, 4 types (attack/buff/continuous/control). Single equip slot on Player (`shentong` field). Auto-triggers in combat based on `rate` probability, `turncost` cooldown, and MP cost. Skills consume MP (first MP consumer). Buff/debuff engine in `managers/skill_manager.py` (`ActiveBuff`, `CombatSkillState`). Combat integration in `managers/combat_manager.py` (`_execute_turn_with_skill`). Commands: 神通列表/我的神通/装备神通/卸下神通/神通信息. Note: `SkillHandler` is NOT exported from `handlers/__init__.py` — lazily imported in `main.py`.
- **GM compensation system**: GM creates a global compensation package with `/GM补偿 <物品 数量|物品 数量>` (items separated by `|`). Players claim with `/补偿`, once per package. New GM package replaces the old one, resetting claim eligibility. Items auto-routed: pills → `pills_inventory`, others → `storage_ring_items`. DB tables: `gm_compensation`, `gm_compensation_claims`. CRUD in `data/database_extended.py`, logic in `handlers/gm_handlers.py`.
- **Daily activity system** (v33): 10 daily tasks tracked in `managers/activity_manager.py` (`ActivityTracker`). Player fields: `daily_activity` (JSON progress), `daily_activity_points` (capped at 100), `daily_activity_date` (YYYY-MM-DD for self-healing day reset), `daily_activity_rewarded`. Points awarded only when a task reaches its target count. Reward: 1x 渡厄丹 at 100 points. Tasks: check_in(+10), adventure(+20×2), rift(+30), bounty(+20×2), shop_buy(+40), harvest(+20), alchemy(+30), smelt(+30), interest(+10), sect(+20).
- **Sect task system**: Instant completion, 10-minute cooldown stored in `user_cd.extra_data["sect_task_cd"]`, daily limit of 3 tracked via `Player.sect_task` with date-based auto-reset in `extra_data["sect_task_date"]`. Does NOT set `user_cd.type` to busy (fixes historical stuck-state bug).
- **Adventure system**: Configurable routes with risk/reward. `/中断历练` for mid-adventure forced exit (counts as completed but no rewards). `/完成历练` for normal settlement after timer expires. Route fatigue cooldowns tracked per-user in memory.
- **Scarecrow practice**: `/稻草人` for testing combat damage without PvP.
- **Sign-in milestones**: Rewards at 7/14/21/28 consecutive check-in days.

## Busy State Whitelist

`BUSY_STATE_ALLOWED_COMMANDS` in `handlers/utils.py` defines commands usable during any busy state (闭关/历练/秘境/交易). Key categories: basic info (我的信息/签到), bank operations, inventory viewing, pill usage (`服用丹药`/`丹药信息`), storage ring operations (存入/取出/炼金/etc.), shop (`购买`), daily activity (每日活跃/活跃奖励), rankings, consignment browsing, bounty management, and settlement commands (出关/中断历练/完成探索).

## Important Conventions

- All I/O is async. Handlers return `AsyncGenerator` yielding response messages.
- Database: aiosqlite, single file `sqlite3.db`. `DataBase` class handles reconnection.
- Config files live in `config/` (14+ JSON files). System configs auto-created from defaults on first run. Use `sync_data.py` to copy to `docs/data/` for the website SPA.
- Use `TYPE_CHECKING` imports to avoid circular dependencies.
- Website SPA (`docs/app.js`): reads from `docs/data/*.json`. All 9 ranks are: 凡品, 灵品, 地品, 天品, 皇品, 帝品, 道品, 仙品, 混元先天. Do NOT include 珍品/圣品/神品.
- **`Item` dataclass bonus fields** (`models.py`): `breakthrough_bonus` (float, e.g. 0.02), `atk_bonus` (int, flat), `hp_bonus` (float, e.g. 0.05). Added to `Item` class and accumulated in `Player.get_total_attributes()` for main_technique type items.
- **ASCII quotes only in Python source**: All Python string literals MUST use standard ASCII double quotes `"` (U+0022). NEVER use Unicode smart quotes `"` (U+201C) / `"` (U+201D) — they cause `SyntaxError: invalid character '"' (U+201C)`. The Edit tool preserves existing Unicode characters and the Read tool displays them identically to ASCII quotes, so edits are blind to the difference. When modifying files containing Chinese text with quoted strings (e.g. `misc_handler.py`), prefer the Write tool for full-file rewrites over targeted Edit to avoid accidentally preserving smart quotes.
- **`extra_data` JSON field**: Used by `UserCd` for per-system cooldown storage (e.g. `sect_task_cd`, `sect_task_date`, route keys for adventures). Prefer `extra_data` over repurposing `type`/`scheduled_time` when adding cooldowns that shouldn't block the user's busy state.

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
