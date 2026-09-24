# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AstrBot plugin for a text-based idle cultivation (修仙) game. Python 3.8+, runs inside the AstrBot chatbot framework process. SQLite database via `aiosqlite`, async throughout. Core systems (境界/功法/灵田/炼丹/神通) migrated from nonebot_plugin_xiuxian_2_pmv.

## Commands

**Python 路径**: `E:\python\python.exe`（Git Bash 中使用 `/e/python/python.exe`，`python` / `python3` 命令不可用）

```bash
pip install -r requirements.txt          # runtime deps (Pillow)
pip install -r requirements-dev.txt      # dev deps (pytest, pytest-asyncio, aiosqlite)
pytest                                   # run all tests
pytest tests/test_trade_manager.py       # run single test file
pytest -k "test_name"                    # run specific test
/e/python/python.exe sync_data.py        # sync config/*.json to docs/data/ for website
/e/python/python.exe scripts/rebalance_weapons.py  # rebalance weapon stats
```

No linter/formatter is configured. Follow existing style: `snake_case` functions, `PascalCase` classes, `UPPER_CASE` constants, single-underscore private methods, Chinese docstrings.

## 回答风格

- 对总结、Plan、Task 以及长内容的输出使用中文，优先进行逻辑整理后使用美观的 Table 格式整齐输出；普通内容正常输出。

## Architecture (4 layers)

```
main.py (entry point, 161 command registrations, 9 background tasks)
    |
handlers/ (~30 handler classes — command processing, async generators)
    |
core/ (7 modules: cultivation, breakthrough, combat, equipment, forging, pills, storage)
managers/ (~20 modules: combat, alchemy, spirit_garden, encounter, merchant, sect, boss, rift, trade, bounty, etc.)
    |
data/ (SQLite CRUD: data_manager.py, database_extended.py, migration.py)
```

**Data flow:** AstrBot message → `@filter.command()` route → `@require_whitelist` → handler → `@player_required` → manager logic → aiosqlite → response via async generator.

## Key Patterns

- **`@player_required` decorator** (`handlers/utils.py`): auth check + state enforcement + loan status. Uses `BUSY_STATE_ALLOWED_COMMANDS` whitelist to allow certain commands during busy states. Mutually exclusive states enforced via `UserStatus` enum in `models_extended.py`.
- **`@migration(version=N)` decorator** (`data/migration.py`): register DB migrations. Current version: **v44** (v42/v43 add spirit_farms garden columns + last_harvest_time wild-plot conversion; v44 adds merchant_windows/merchant_goods/merchant_purchases). All migration tasks take `(conn, config_manager)`. Increment `LATEST_DB_VERSION` when adding.
- **`@require_whitelist`**: AstrBot-level group access control, applied at `main.py`.
- **JSON-serialized fields**: complex data (techniques, pill effects, storage items) stored as JSON strings in SQLite TEXT columns, with getter/setter on `Player`/`Item` dataclasses.
- **Transaction safety**: critical ops use `BEGIN IMMEDIATE` with rollback. Trade/consignment use conditional UPDATE for concurrent purchase safety. CRUD methods in `database_extended.py` and `data_manager.py` accept `auto_commit=False` to suppress internal commits when composing multi-step atomic operations. Boss defeat uses CAS pattern (`UPDATE ... WHERE status = 1`, check `rowcount`) via `try_defeat_boss`.
- **Background tasks** (9 in `main.py`): boss spawning, loan checks, bounty expiry, consignment expiry, trade timeout, rift daily broadcast, sect material distribution (11:00 + 12:00 daily), auto sect owner change, wandering merchant scheduler. All use exponential backoff retry.
- **`ConfigManager`** (`config_manager.py`): loads 20+ JSON config files. `get_level_data()` returns unified 58-level realm data (no longer branches on cultivation_type). `game_config` loaded via `_load_config_with_default`.
- **`ActivityTracker`** (`managers/activity_manager.py`): daily activity system with **9 task types** (签到/秘境/悬赏/灵田收获/炼丹/炼金/利息/宗门/触发奇遇), lazy-loaded in `main.py` and injected into consumer modules. Day reset is self-healing via date comparison (no background task needed).
- **State conflict architecture**: Two parallel systems block commands during busy states — (1) `@player_required` decorator checks `user_cd.type` against whitelist, (2) individual handler/manager methods check `user_cd.type != IDLE` directly. Many handlers bypass `@player_required` and do their own state checks.

## Numerical Formulas (Excel-aligned)

All formulas aligned to `修仙.xlsx` design document:

- **HP**: `max(1000, int(experience / 2 * (1 + hp_buff))) * (1 + hp_bonus)`
- **MP**: `max(100, int(experience * (1 + mp_buff))) * (1 + mp_bonus)`
- **ATK**: `max(100, int(experience / 10)) × (atkpractice×0.04+1) × (1+technique) × (1+weapon) × (1+armor) + permanent_buff` — multiplicative stacking, no flat equip bonus
- **Power**: `round(experience × root_speed × realm_spend)` — `realm_spend` from level_config
- **Cultivation exp**: `60 × minutes × root_speed × (1+technique_bonus) × (1+closing_exp_bonus) × (1+land) × (1+permanent_mult) × pill_segment_mult` — no `realm_spend` in cultivation (that factor only applies to Power × closing_realm_mult（v4.3.8：idx≤18 恒 1.0；idx>18 锚定日占比 4.5%→3%，`config_manager.get_closing_realm_mult`）
- **Breakthrough**: base_rate from level_config + failure_accumulation (每次+1%, 仅 level_index < 46 有效, 突破成功即清零) + technique_bonus + breakthrough_number/100 + pill_bonus, clamped to [0, max_rate]. **突破失败无死亡惩罚（v4.3.1 移除）**：失败仅损失修为 0.1%~1%（level_index >= 25 时 1%~5%），`death_protection`（渡厄金丹）可免疫一次修为损失。Major realm transition detected by `is_major_realm_transition()` (`current_level_index % 3 == 0 and current_level_index > 0`, 即圆满突破至下一大境界初期). Realm-specific pills (1400-1421, 15100-15103) only work on major realm transitions. Universal pills (15151-15153) work on any transition. `max_uses` enforced via `permanent_pill_usage` tracking. Pill effects persist across failures (`expiry_time=0`), only consumed on success via `consume_breakthrough_boost_only()`. `get_breakthrough_modifiers` accepts `target_level_index` to filter pill effects by target realm. `calculate_breakthrough_success_rate` does NOT add pill bonus from config (it's already in `temp_bonus` via active effects).
- **Crit damage**: `max(1.5, 1.0 + weapon_crit_damage + technique_crit_damage + impart_burst_per)` — additive delta from 1.0 base
- **Defense**: percentage-based `def_buff` from armor + weapon `damage_reduction` + technique `damage_reduction`, capped at 0.9. No ln-based formula.
- **Damage formula**: `atk × 0.5 × crit_mult × 1.5 × float × (1 - def_buff + armor_pen/100 + sub_break_pct)` — Excel's 0.5 damage halving + 1.5 weapon bonus. `sub_break_pct` from sub-technique buff_type 13. Continuous DOT applies `def_buff` defense: `raw × (1 - def_buff)`.
- **Boss damage**: player ATK ×2 against bosses. Boss buff system: 8 buff types (atk/crit/crit_dmg/reduce_lifesteal + reduce_atk/reduce_crit/reduce_crit_dmg) across 4 tiers. Boss special attacks (紫玄掌 8%, 5x+30%HP; 子龙朱雀 8%, 3x ignore 50% defense; normal 84%). Boss stats restored in try/finally block.
- **Level scaling**: `game_config.json` `level_scaling.bounty_rift_coefficient` (default 0.045) now only scales 悬赏/秘境 **灵石** (linear). 修为 (v4.3.7) uses share-based curve: `exp_reward = share(idx) × exp_needed[idx+1] × exp_scale × pf`, share = piecewise decay (`exp_share_base_decay^idx` for idx≤18, then `× exp_share_slowdown_decay^(idx-18)`), split bounty 67.5% (3/day) / rift 32.5% (1/day) via `bounty_exp_split`/`rift_exp_split`; rift scale by `reward_exp / rift_exp_base_norm`. Shared helpers: `config_manager.get_exp_share_day(idx)` / `get_next_exp_needed(idx)`. Boss 20 tiers cover all 58 levels.
- **Combat stat aggregation**: Two parallel read paths — (1) `Player.get_total_attributes()` for display, (2) `load_equipment_bonus()` + `build_player_combat_stats()` for actual combat. These paths can diverge.

## Realm System (58 levels)

Unified 58-level hierarchy (index 0=江湖好手 → 57=合道境圆满). 19 major realms × 3 sub-stages (初期/中期/圆满) + 1 starter. Stored in `config/level_config.json` with fields: `name`, `exp_needed`, `success_rate`, `spend`.

Realm names (aligned to nonebot `境界.txt`): 洗髓境(1-3), 练气境(4-6), 化灵境(7-9), 筑基境(10-12), 结丹境(13-15), 金丹境(16-18), 紫府境(19-21), 凝婴境(22-24), 元婴境(25-27), 化神境(28-30), 炼虚境(31-33), 出窍境(34-36), 分神境(37-39), 合体境(40-42), 大乘境(43-45), 轮回境(46-48), 渡劫境(49-51), 飞升境(52-54), 合道境(55-57).

v37 removed flat attributes (physical_damage, magic_damage, physical_defense, magic_defense, mental_power) from Player model, Item model, combat system, pill system, and all UI. **v4.3.2 removed the 灵修/体修 dual-path entirely**: `我要修仙` creates a character directly (no path selection), `cultivation_type` DB column / Player field retained only for backward compat (empty value, nothing reads it).

## Data Models

- `Player` (`models.py`): main player dataclass. Equipment slots: `weapon`, `armor`, `main_technique`, `shentong`, `sub_technique`, `furnace`. JSON-serialized fields: `techniques`, `pills_inventory`, `active_pill_effects`, `permanent_pill_gains`, `storage_ring_items`, `daily_activity`, etc. `permanent_pill_gains` has two scopes: `level_{index}` for per-level `_gain` attributes (受境界属性上限限制), `_global` for multiplier effects (cultivation_speed, death_protection — permanent, survive level-up).
- `Item` (`models.py`): equipment/material dataclass. Technique bonus fields: `exp_multiplier`, `breakthrough_bonus`, `atk_bonus`, `hp_bonus`, `mp_bonus`, `crit_rate`, `crit_damage`, `closing_exp_bonus`, `closing_recovery_bonus`, `damage_reduction`, `breakthrough_number`, `dual_cultivation_bonus`, `alchemy_exp_bonus`, `alchemy_count_bonus`, `harvest_bonus`, `random_buff`, `exclusive_weapon_id`. Weapon combat attrs (`crit_rate`, `crit_damage`, `armor_pen`, `lifesteal`, `double_hit`) and armor attrs (`def_buff`, `dodge_rate`, `crit_resist`, `reflect_pct`, `block_value`, `hp_regen_pct`, `atk_bonus`) read from raw config dicts by `combat_manager.load_equipment_bonus()`.
- `UserStatus` enum (`models_extended.py`): `IDLE`, `CULTIVATING`, `ADVENTURING`(deprecated,保留值2兼容DB), `EXPLORING`, `SECT_TASK`, `TRADING`
- `UserCd` (`models_extended.py`): user cooldown/state model with `type`, `create_time`, `scheduled_time`, `extra_data` (JSON)
- `CombatStats` (`managers/combat_manager.py`): combat attributes dataclass with `def_buff` (percentage reduction), `damage_reduction`, and all special attributes. Sub-technique fields: `sub_buff_type`, `sub_buff_value`, `sub_buff_value2`, `sub_break_pct`.

## Game Systems

- **Techniques (功法)**: 79 main techniques in `config/items.json` (type=`main_technique`), across 14 ranks (人阶下品→无上仙法). Synced from nonebot with full field set including `closing_exp_bonus` (闭关经验), `closing_recovery_bonus` (经验保护), `damage_reduction` (减伤), `breakthrough_number` (突破概率), `harvest_bonus` (采集), `alchemy_count_bonus` (出丹数), `alchemy_exp_bonus` (炼丹经验). **v4.4.0 exp bands**: technique exp multipliers are banded randoms (人下 1.00→天上 2.40, center step 14 / bandwidth 18; immortal ranks +0.4 shift), generated via `scripts/reroll_technique_exp.py` with manifest `config/technique_exp_manifest.json` (seed reproducible). 14 修炼特化 techniques get band-top +U(0,0.15) but ATK×0.5 / crit halved / HP×0.7.
- **Spirit Garden (灵植园 v2, `managers/spirit_farm_manager.py`)**: per-plot state machine, lazily derived (no background task). Commands: 灵田(别名 我的灵田)/开垦灵田/灵田开垦(扩展地块, FIELD_UPGRADE_COSTS 350万→1500万, 上限6块)/灵田播种 `<药名> [数量|全部]`/灵田收取/灵田催熟(10万/h, 下限15万)/灵田清理/偷菜 `<@某人>`/护园/升级收取/升级控火. Crop tiers: 5 tiers in `config/garden_crops.json` (凡品 5万/12h → 仙品 500万/48h), matched by herb rank (tier1 rank≥48 … tier5 rank 0-24). Empty plots auto-wild after 24h; wild herbs ripen in 48h, wither 48h after over-ripening. Stealing: 3/day thief, 5/day victim cap, beast interception fine 50万 split 5:5, **no karma impact (pure fun)**. Garden levels 1-5 (sow +5/plot, harvest +10 exp): Lv2 perfect window +6h, Lv3 wild no-wither, Lv4 yield +10%, Lv5 double-chance 10%. Encounter hooks: farm_sow 8%, farm_harvest 10%. Legacy harvest formula (`herb_fields + harvest_level + technique_harvest_bonus`) still applies to wild/legacy plots via 升级收取. 108 herb types in `config/herbs.json` (一品→九品, 12 per grade).
- **Encounter system (奇遇, `managers/encounter_manager.py`)**: 62 events / 138 choices in `config/encounter_config.json` (6 realm segments × 4 rarities). Commands: 奇遇 `<A/B/C>` (reply pending choice, 180s timeout), 奇遇信息 (karma/title/daily count), 奇遇记录. Trigger hooks with per-action probabilities (签到15/出关10/秘境20/悬赏25/Boss30/播种8/收取10) — try_trigger consumes daily count, resolved lazily on `/奇遇`. Rewards: exp = `D_daily × exp_pct% × U(0.6,1.5)` clamped ≤50% of daily cap (expected ratio 15%, configurable); gold = center × U(0.6,1.5) × level_bonus × gold_scale. **Karma** (`Player.karma`, -1000~1000): success roll is `random() >= risk`; karma shifts outcomes and grants ±4%/8% combat/cultivation bonus (core/cultivation_manager). Failed evil actions halve karma delta: `sign(d)×ceil(|d|/2)`. Karma decays -2 per check-in. Legendary encounters broadcast anonymously server-wide. Legendary-tier drops ignore storage-ring pill filter (pills → `pills_inventory`).
- **Wandering merchant (云游商人, `managers/merchant_manager.py`)**: 2-3 deterministic daily windows, 30-60 minutes each; regular slots sell materials/herbs/utility pills, tech slots sell 1-of-1 server-wide techniques/skills/sub-techniques, plus a 15% regular-only bargain slot. Prices use config references × premium or `TECH_BASE_PRICES` (rank 0=60万 → rank 13=5亿), with `MERCHANT.PRICE_SCALE`. Commands: 云游商人/购买商品 `<编号> [数量]`; purchases enforce per-window/daily limits by quantity, CAS stock deduction, delivery routing (pills → `pills_inventory`, others → storage ring), and repeated tech purchases remain allowed for resale. Scheduler is background task #9. Migration v44 adds `merchant_windows`, `merchant_goods`, `merchant_purchases`. First Monte Carlo run is recorded in the design spec and currently flags sink signal D pending real-data calibration.
- **Alchemy (炼丹)**: 寒热调和 system. Commands: 炼丹/配方/装备炼丹炉/卸下炼丹炉. Recipe matching: 主药+药引+辅药 with cold/hot harmony check + elixir_config matching. 48 recipes in `config/alchemy_recipes.json`. Pill count = `1 + fire_control + alchemy_count_bonus + furnace_buff`. Crafted pills → `pills_inventory`. 3 furnaces in `config/furnaces.json` with buff values (+0/+1/+2 pills).
- **Pills (丹药)**: Active pill configs in `config/utility_pills.json` (healing 2000-2008, permanent ATK 2009-2018, breakthrough boost 1400-1421 + 15100-15103 + 15151-15153). Old nonebot pills in `config/pills.json` (legacy data, 29 entries). Healing pills use `heal_hp_pct` effect. Permanent ATK pills store `flat_atk_bonus` in `permanent_pill_gains["_global"]`. Breakthrough boost pills create active effects (`expiry_time=0`, persist indefinitely) with `max_uses` enforcement and `target_level_index` stored in effect dict for filtering. `consume_breakthrough_boost_only()` removes only breakthrough_boost/debuff on success, preserving death_protection. Death_protection effects are one-shot: consumed after protecting once on failure. `get_breakthrough_modifiers(player, target_level_index)` filters active effects by target realm.
- **Shentong (神通)**: 53 active combat skills in `config/skills.json` (aligned to xlsx reference), 4 types (attack/buff/continuous/control). Single equip slot on Player (`shentong` field). Auto-triggers based on `rate` probability, `turncost` cooldown, MP cost (`mpcost` × raw_base_mp). Continuous skills use independent `dot_turns` field for DOT duration. Buff/debuff engine in `managers/skill_manager.py`.
- **Sub-technique (辅修功法)**: 22 combat support techniques in `config/sub_techniques.json`. Single equip slot on Player (`sub_technique` field). 13 buff_types: 1=ATK%, 2=crit_rate, 3=crit_dmg, 4=HP regen, 5=MP regen, 6=HP steal, 7=MP steal, 8=poison, 9=dual steal, 13=armor pierce. buff_type 1/2/3 applied at combat start in `build_player_combat_stats()`. buff_type 4-9 applied per-turn in `_apply_sub_technique_effects()`. buff_type 13 (`sub_break_pct`) applied in `execute_attack()` defense calculation.
- **Combat attributes**: Weapon special: `crit_rate`, `crit_damage` (additive delta), `armor_pen`, `lifesteal`, `double_hit`, `damage_reduction`. Armor special: `def_buff`, `dodge_rate`, `crit_resist`, `reflect_pct`, `block_value`, `hp_regen_pct`, `atk_bonus`.
- **Boss system** (`managers/boss_manager.py`): 20 tiers from 洗髓(Lv0) to 合道(Lv57). Boss buff system: 8 buff types across 4 tiers (atk/crit/crit_dmg/reduce_lifesteal + reduce_atk/reduce_crit/reduce_crit_dmg). Special attacks: 紫玄掌 (8%, 5x+30%HP), 子龙朱雀 (8%, 3x ignore 50% defense), normal (84%). Player ATK ×2 in boss fights. Drop table `BOSS_DROP_TABLE` 4 tiers (`get_drop_tier_for_level`: low idx≤6 / mid ≤12 / high ≤33 / ultra >33) — v4.3.3: no "灵草" (ghost item removed); 灵兽骨 drops in low/mid, 天火熔晶 drops in high/ultra. Rolls: low=1 item, mid=1+50%1, high=2+60/40→1/2, ultra=3+80/60/40/20→1/2/3/4 extras. Drops go to `storage_ring_manager.store_item` (failures silently skipped).
- **Bounty system** (`managers/bounty_manager.py`): 100% drop of technique, skill, or sub-technique on completion. Drop config in `config/bounty_drop_config.json` with `type_rate` weights per rank (14 ranks). Items randomly selected from `gf_list` (功法), `st_list` (神通), `fx_list` (辅修功法). Daily limit: 3 bounties. **Luck tiers** (v4.4.0): high-realm players get rank-weight multipliers — level_index 19+ 天阶以上 ×3, 37+ 仙阶以上 ×20 (`random.choices` auto-normalizes). v4.3.3: fx_list 的"玄清天衍录"已移除（幽灵引用，实为 main_technique）。
- **Rift drops** (`managers/rift_manager.py`): `RIFT_DROP_TABLE` 5 levels (百年灵草, v4.3.3 起无幽灵"灵草"; 4/5 级秘境此前 fallback 到 1 级表已补齐) + `RIFT_PILL_DROP_TABLE` 恢复类丹药 (3%~15% per level) + dynamic equipment. Pill drops enter `pills_inventory` directly (v4.3.3 fix — was blocked by storage ring pill filter), others via `store_item`.
- **Sect system** (`managers/sect_manager.py`): 18 commands. Sect tasks: 5 types (2 HP-cost + 3 stone-cost), randomized, 3/day, 10-min cooldown. Attack practice: 50-level discrete cost table from Excel. Elixir room: 8 levels (黄级→无上), guaranteed 渡厄丹 daily. Member limits per position based on elixir room level. Auto owner change: 7 days offline. Material distribution: 11:00 + 12:00 daily at 1:1 rate.
- **Daily activity system**: 9 daily tasks in `managers/activity_manager.py` (签到/秘境/悬赏/灵田收获/炼丹/炼金/利息/宗门/触发奇遇). Reward: 1x 渡厄丹 at 100 points.
- **Boss enable switch** (v4.3.4): `ACCESS_CONTROL.BOSS_ENABLED` default **true** (was false). Gates the 3 boss commands and the hourly auto-spawn task. `BOSS_ADMINS` (list) allows manual /生成Boss. Challenge failure persists boss HP (world-wide attrition design); defeat uses CAS. **v4.3.6 damage-contribution system**: `boss_damage_log` table (boss_id, user_id, damage, update_time) accumulates per-challenge damage (win or lose). On kill, `_distribute_rewards` gives the killer 30% of stone_reward + 1 guaranteed drop, and splits the rest by damage share among participants with damage ≥ 5% of boss max_hp; drops beyond the guarantee are weight-rolled by damage. Log is cleared after distribution. `CHALLENGE_COOLDOWN=300s` per player per boss (judged from damage_log.update_time — no extra table). Drops enter storage rings; gold written BEFORE store_item calls (object-refresh ordering matters).
- **GM compensation**: `/GM补偿 <物品 数量|物品 数量>`, claim with `/补偿`. Items auto-routed: pills → `pills_inventory`, others → `storage_ring_items`.
- **Storage ring item whitelist** (v4.3.3, `core/storage_ring_manager.py`): `can_store_item` rejects unknown item names via `_get_valid_item_names()` (lazy-cached frozenset from items/herbs/weapons/sub_techniques/skills/storage_rings configs + 融合产物"天罪"). Pills are still rejected separately (they live in `pills_inventory`). When adding a new item source config, extend the whitelist there.
- **Permanent pill system**: `_gain` attributes per `level_{index}` for lifespan/spiritual_qi/blood_qi（受境界上限限制）, `_global` multipliers for cultivation_speed/death_protection（permanent across level-up）.
- **Impart cards**: 105 cards in `config/impart_cards.json` (10 types: atk/hp/mp/crit_rate/crit_damage/closing_exp/alchemy_count/harvest/dual_cultivation/boss_atk). Config loaded but card collection system not yet implemented.

## Deleted Systems (do not re-add)

- **三阁 (Shop/Pavilion)**: NPC shop system removed. `core/shop_manager.py` and `handlers/shop_handler.py` deleted. Player trading via 寄售 (consignment) and 面对面交易 (trade) remains.
- **历练 (Adventure)**: Route-based adventure system removed. `managers/adventure_manager.py` and `handlers/adventure_handlers.py` deleted. `UserStatus.ADVENTURING` enum value retained for DB compatibility.

## Item Type Structure

`config/items.json` contains only two types after cleanup:
- `材料` (19 items): crafting materials for alchemy
- `main_technique` (79 items): techniques/功法 with `price=0` (not purchasable in shop)

`config/weapons.json` contains `weapon` (66) and `armor` (38) types.
`config/skills.json` contains 53 skills (aligned to xlsx reference).
`config/sub_techniques.json` contains 22 sub-techniques (辅修功法) with `buff_type`/`buff`/`buff2`/`break_pct` fields.

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

`BUSY_STATE_ALLOWED_COMMANDS` in `handlers/utils.py` defines commands usable during any busy state. Key categories: basic info, bank ops, inventory, pill usage, storage ring operations, daily activity, rankings, consignment, bounty management, settlement commands, **garden ops (灵田/播种/收取/偷菜/护园), encounter commands (奇遇/奇遇信息/奇遇记录), merchant ops (云游商人/购买商品)**. Matching is exact-prefix and case-sensitive (`text == cmd or text.startswith(cmd + " ")`) — entries are all-Chinese so no case issue today; any future English entry must carry its case variants.

## Design Documentation

Design specs and implementation plans live in `docs/superpowers/`:
- `docs/superpowers/specs/` — feature design documents (e.g., economy-trading, reincarnation system)
- `docs/superpowers/plans/` — implementation plans derived from specs

Planned systems with existing design specs:
- **轮回系统 (Reincarnation)**: `docs/superpowers/specs/2026-07-06-reincarnation-system-design-v2.md` — cross-life progression via `reincarnation_data` table, triggers at 轮回境 (level 46+)

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
- 如有数据库 schema 变更，评估是否需要更新 `data/migration.py` 的版本号
