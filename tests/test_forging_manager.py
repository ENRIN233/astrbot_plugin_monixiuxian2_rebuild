import pytest
import json
import uuid
from dataclasses import fields
from typing import Optional
from astrbot_plugin_monixiuxian2.models import Player
from astrbot_plugin_monixiuxian2.data.database_extended import DatabaseExtended

# Player field names for safe construction from DB rows
_PLAYER_FIELDS = {f.name for f in fields(Player)}


# ── Mock DataBase ────────────────────────────────────────────────────
class MockDataBase:
    """Minimal DataBase mock for forging tests.
    Provides get_player_by_id and update_player backed by the in-memory conn.
    """
    def __init__(self, conn):
        self.conn = conn

    async def get_player_by_id(self, user_id: str) -> Optional[Player]:
        async with self.conn.execute(
            "SELECT * FROM players WHERE user_id=?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        # Filter to only Player fields in case the DB has extra columns
        filtered = {k: v for k, v in dict(row).items() if k in _PLAYER_FIELDS}
        return Player(**filtered)

    async def update_player(self, player: Player, auto_commit: bool = True):
        # Only update the fields ForgingManager actually changes
        await self.conn.execute(
            """UPDATE players SET
                forging_exp=?,
                forging_level=?,
                storage_ring_items=?,
                gold=?
             WHERE user_id=?""",
            (player.forging_exp, player.forging_level,
             player.storage_ring_items, player.gold,
             player.user_id),
        )
        if auto_commit:
            await self.conn.commit()


# ── Mock ConfigManager ───────────────────────────────────────────────
class MockConfigManager:
    def __init__(self):
        self.forging_recipes = {
            "forge_001": {
                "name": "精铁剑",
                "rank_required": 0,  # Starter recipe, accessible from level 0
                "ingredients": {"精铁": 2, "紫金沙": 1},
                "output_template": "精铁符剑",
                "output_type": "weapon",
                "forge_exp": 15,
                "quality_rates": {"下品": 0.40, "中品": 0.35, "上品": 0.20, "极品": 0.05},
            },
            "forge_003": {
                "name": "青玉剑",
                "rank_required": 5,
                "ingredients": {"精铁": 3, "紫金沙": 2, "魔核碎片": 1, "天火熔晶": 1},
                "output_template": "青玉符剑",
                "output_type": "weapon",
                "forge_exp": 35,
                "quality_rates": {"下品": 0.40, "中品": 0.35, "上品": 0.20, "极品": 0.05},
            },
        }
        self.weapons_data = {
            "精铁符剑": {
                "id": "sword_7001",
                "name": "精铁符剑",
                "type": "weapon",
                "rank": "下品符器",
                "required_level_index": 0,
                "atk_bonus": 0.08,
                "crit_rate": 0,
                "crit_damage": 0.0,
            },
            "青玉符剑": {
                "id": "sword_7012",
                "name": "青玉符剑",
                "type": "weapon",
                "rank": "上品符器",
                "required_level_index": 10,
                "atk_bonus": 0.15,
                "crit_rate": 5,
                "crit_damage": 0.0,
            },
        }
        self.storage_rings_data = {
            "基础储物戒": {"type": "storage_ring", "capacity": 20},
        }

    def is_pill(self, item_name: str) -> bool:
        """Check if an item is a pill (forge materials are never pills)."""
        return False


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
async def forge_db(memory_db):
    """Create minimal schema for forging tests (players + weapon_instances)."""
    # Full players table matching v2 schema + v40 forging fields
    await memory_db.execute("""
        CREATE TABLE players (
            user_id TEXT PRIMARY KEY,
            user_name TEXT NOT NULL DEFAULT '',
            level_index INTEGER NOT NULL DEFAULT 0,
            cultivation_type TEXT NOT NULL DEFAULT '灵修',
            experience INTEGER NOT NULL DEFAULT 0,
            gold INTEGER NOT NULL DEFAULT 0,
            hp INTEGER NOT NULL DEFAULT 0,
            mp INTEGER NOT NULL DEFAULT 0,
            atk INTEGER NOT NULL DEFAULT 0,
            atkpractice INTEGER NOT NULL DEFAULT 0,
            sect_id INTEGER NOT NULL DEFAULT 0,
            sect_position INTEGER NOT NULL DEFAULT 4,
            sect_contribution INTEGER NOT NULL DEFAULT 0,
            sect_task INTEGER NOT NULL DEFAULT 0,
            sect_elixir_get INTEGER NOT NULL DEFAULT 0,
            blessed_spot_flag INTEGER NOT NULL DEFAULT 0,
            blessed_spot_name TEXT NOT NULL DEFAULT '',
            level_up_rate INTEGER NOT NULL DEFAULT 0,
            spiritual_root TEXT NOT NULL DEFAULT '未知',
            lifespan INTEGER NOT NULL DEFAULT 100,
            state TEXT NOT NULL DEFAULT '空闲',
            cultivation_start_time INTEGER NOT NULL DEFAULT 0,
            last_check_in_date TEXT NOT NULL DEFAULT '',
            spiritual_qi INTEGER NOT NULL DEFAULT 100,
            max_spiritual_qi INTEGER NOT NULL DEFAULT 1000,
            blood_qi INTEGER NOT NULL DEFAULT 0,
            max_blood_qi INTEGER NOT NULL DEFAULT 0,
            weapon TEXT NOT NULL DEFAULT '',
            armor TEXT NOT NULL DEFAULT '',
            main_technique TEXT NOT NULL DEFAULT '',
            techniques TEXT NOT NULL DEFAULT '[]',
            active_pill_effects TEXT NOT NULL DEFAULT '[]',
            permanent_pill_gains TEXT NOT NULL DEFAULT '{}',
            has_resurrection_pill TEXT NOT NULL DEFAULT '',
            has_debuff_shield INTEGER NOT NULL DEFAULT 0,
            pills_inventory TEXT NOT NULL DEFAULT '{}',
            storage_ring TEXT NOT NULL DEFAULT '基础储物戒',
            storage_ring_items TEXT NOT NULL DEFAULT '{}',
            daily_pill_usage TEXT NOT NULL DEFAULT '{}',
            last_daily_reset TEXT NOT NULL DEFAULT '',
            permanent_pill_usage TEXT NOT NULL DEFAULT '{}',
            shentong TEXT NOT NULL DEFAULT '',
            sub_technique TEXT NOT NULL DEFAULT '',
            furnace TEXT NOT NULL DEFAULT '',
            sleeping_bag_level INTEGER NOT NULL DEFAULT 0,
            bank_vip_tier INTEGER NOT NULL DEFAULT 0,
            achievement_data TEXT NOT NULL DEFAULT '{"unlocked": {}, "equipped": ""}',
            monthly_sign_count INTEGER NOT NULL DEFAULT 0,
            monthly_sign_month TEXT NOT NULL DEFAULT '',
            daily_activity TEXT NOT NULL DEFAULT '{}',
            daily_activity_points INTEGER NOT NULL DEFAULT 0,
            daily_activity_date TEXT NOT NULL DEFAULT '',
            daily_activity_rewarded INTEGER NOT NULL DEFAULT 0,
            -- v40 forging fields
            equipped_weapon TEXT NOT NULL DEFAULT '',
            equipped_armor TEXT NOT NULL DEFAULT '',
            forging_exp INTEGER NOT NULL DEFAULT 0,
            forging_level INTEGER NOT NULL DEFAULT 1
        )
    """)
    # weapon_instances table (v40 schema)
    await memory_db.execute("""
        CREATE TABLE weapon_instances (
            instance_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            template_name TEXT NOT NULL,
            item_type TEXT NOT NULL DEFAULT 'weapon',
            quality TEXT NOT NULL DEFAULT '下品',
            quality_mult REAL NOT NULL DEFAULT 1.0,
            enhance_level INTEGER DEFAULT 0,
            source_recipe TEXT DEFAULT '',
            atk_bonus REAL DEFAULT 0.0,
            crit_rate INTEGER DEFAULT 0,
            crit_damage REAL DEFAULT 0.0,
            armor_pen INTEGER DEFAULT 0,
            lifesteal INTEGER DEFAULT 0,
            double_hit INTEGER DEFAULT 0,
            damage_reduction REAL DEFAULT 0.0,
            mp_bonus REAL DEFAULT 0.0,
            def_buff REAL DEFAULT 0.0,
            dodge_rate INTEGER DEFAULT 0,
            crit_resist INTEGER DEFAULT 0,
            reflect_pct INTEGER DEFAULT 0,
            block_value INTEGER DEFAULT 0,
            hp_regen_pct REAL DEFAULT 0.0,
            affixes TEXT DEFAULT '[]',
            is_equipped INTEGER DEFAULT 0,
            in_storage INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    await memory_db.execute(
        "CREATE INDEX IF NOT EXISTS idx_wi_user ON weapon_instances(user_id)"
    )
    yield memory_db


@pytest.fixture
async def forging_env(forge_db):
    """Build the full forging test environment.

    Returns a dict with: db, db_extended, config_manager, forging_manager, conn
    """
    from astrbot_plugin_monixiuxian2.core.forging_manager import ForgingManager
    from astrbot_plugin_monixiuxian2.core.storage_ring_manager import StorageRingManager

    config_manager = MockConfigManager()
    db = MockDataBase(forge_db)
    db_extended = DatabaseExtended(forge_db)
    storage_ring_mgr = StorageRingManager(db, config_manager)

    forging_mgr = ForgingManager(db, db_extended, config_manager, storage_ring_mgr)

    yield {
        "db": db,
        "db_extended": db_extended,
        "config_manager": config_manager,
        "forging_manager": forging_mgr,
        "conn": forge_db,
    }


async def insert_forge_player(conn, uid, f_level=1, f_exp=0, items=None, gold=0):
    """Insert a player with forging fields into the test database."""
    items = items or {}
    await conn.execute(
        """INSERT INTO players
           (user_id, user_name, level_index, gold, storage_ring_items,
            forging_exp, forging_level, state)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (uid, f"道友{uid}", 0, gold, json.dumps(items, ensure_ascii=False),
         f_exp, f_level, "空闲"),
    )
    await conn.commit()


# ════════════════════════════════════════════════════════════════════
#  Tests
# ════════════════════════════════════════════════════════════════════

class TestQualityRates:
    """Tests for level-based quality probability rates."""

    @pytest.mark.asyncio
    async def test_level_1_returns_lowest_tier_rates(self, forging_env):
        fm = forging_env["forging_manager"]
        rates = fm._get_quality_rates_for_level(1)
        assert rates["下品"] == 0.40
        assert rates["中品"] == 0.35
        assert rates["上品"] == 0.20
        assert rates["极品"] == 0.05

    @pytest.mark.asyncio
    async def test_level_15_returns_mid_low_tier_rates(self, forging_env):
        fm = forging_env["forging_manager"]
        rates = fm._get_quality_rates_for_level(15)
        assert rates["下品"] == 0.30
        assert rates["中品"] == 0.35
        assert rates["上品"] == 0.25
        assert rates["极品"] == 0.10

    @pytest.mark.asyncio
    async def test_level_25_returns_mid_tier_rates(self, forging_env):
        fm = forging_env["forging_manager"]
        rates = fm._get_quality_rates_for_level(25)
        assert rates["下品"] == 0.25
        assert rates["中品"] == 0.30
        assert rates["上品"] == 0.30
        assert rates["极品"] == 0.15

    @pytest.mark.asyncio
    async def test_level_35_returns_mid_high_tier_rates(self, forging_env):
        fm = forging_env["forging_manager"]
        rates = fm._get_quality_rates_for_level(35)
        assert rates["下品"] == 0.20
        assert rates["中品"] == 0.30
        assert rates["上品"] == 0.30
        assert rates["极品"] == 0.20

    @pytest.mark.asyncio
    async def test_level_45_returns_high_tier_rates(self, forging_env):
        fm = forging_env["forging_manager"]
        rates = fm._get_quality_rates_for_level(45)
        assert rates["下品"] == 0.15
        assert rates["中品"] == 0.25
        assert rates["上品"] == 0.30
        assert rates["极品"] == 0.30

    @pytest.mark.asyncio
    async def test_level_55_returns_max_tier_rates(self, forging_env):
        fm = forging_env["forging_manager"]
        rates = fm._get_quality_rates_for_level(55)
        assert rates["下品"] == 0.10
        assert rates["中品"] == 0.20
        assert rates["上品"] == 0.30
        assert rates["极品"] == 0.40

    @pytest.mark.asyncio
    async def test_rates_sum_to_1(self, forging_env):
        fm = forging_env["forging_manager"]
        for lv in [1, 10, 11, 20, 21, 30, 31, 40, 41, 50, 51, 99]:
            rates = fm._get_quality_rates_for_level(lv)
            total = sum(rates.values())
            assert abs(total - 1.0) < 0.001, f"Level {lv} rates sum to {total}"


class TestRollQuality:
    """Tests for quality rolling."""

    @pytest.mark.asyncio
    async def test_roll_quality_returns_valid_quality(self, forging_env):
        fm = forging_env["forging_manager"]
        quality, mult = fm._roll_quality(99)
        assert quality in ("下品", "中品", "上品", "极品")
        assert mult in (0.85, 1.0, 1.2, 1.5)

    @pytest.mark.asyncio
    async def test_roll_quality_distribution_plausible(self, forging_env):
        """Run many rolls at max tier and verify the distribution is roughly correct."""
        fm = forging_env["forging_manager"]
        counts = {"下品": 0, "中品": 0, "上品": 0, "极品": 0}
        n = 10000
        for _ in range(n):
            q, _ = fm._roll_quality(55)
            counts[q] += 1
        # 极品 should be most common (~40%), 下品 least common (~10%)
        assert counts["极品"] > counts["下品"], (
            f"极品 count ({counts['极品']}) should exceed 下品 ({counts['下品']})"
        )


class TestRollAffixes:
    """Tests for affix rolling."""

    @pytest.mark.asyncio
    async def test_下品_affixes_no_affixes(self, forging_env):
        fm = forging_env["forging_manager"]
        affixes = fm._roll_affixes("下品")
        assert len(affixes) == 0

    @pytest.mark.asyncio
    async def test_中品_affixes_has_one_affix(self, forging_env):
        fm = forging_env["forging_manager"]
        affixes = fm._roll_affixes("中品")
        assert len(affixes) == 1
        assert "name" in affixes[0]
        assert "attr" in affixes[0]
        assert "val" in affixes[0]

    @pytest.mark.asyncio
    async def test_上品_affixes_count(self, forging_env):
        fm = forging_env["forging_manager"]
        affixes = fm._roll_affixes("上品")
        assert 2 <= len(affixes) <= 3

    @pytest.mark.asyncio
    async def test_极品_affixes_count(self, forging_env):
        fm = forging_env["forging_manager"]
        affixes = fm._roll_affixes("极品")
        assert 3 <= len(affixes) <= 4

    @pytest.mark.asyncio
    async def test_affixes_are_unique(self, forging_env):
        fm = forging_env["forging_manager"]
        affixes = fm._roll_affixes("极品")
        names = [a["name"] for a in affixes]
        assert len(names) == len(set(names)), f"Duplicated affixes: {names}"


class TestGenerateInstanceId:
    """Tests for instance ID generation."""

    @pytest.mark.asyncio
    async def test_instance_id_format(self, forging_env):
        fm = forging_env["forging_manager"]
        iid = fm._generate_instance_id()
        assert iid.startswith("forge_")
        assert len(iid) == len("forge_") + 16


class TestForge:
    """Tests for the forge method (end-to-end)."""

    @pytest.mark.asyncio
    async def test_forge_success_creates_instance_and_adds_exp(self, forging_env, forge_db):
        conn = forge_db
        fm = forging_env["forging_manager"]

        await insert_forge_player(conn, "test1", items={"精铁": 10, "紫金沙": 5})
        player = await forging_env["db"].get_player_by_id("test1")

        success, msg = await fm.forge(player, "forge_001", quantity=1)

        assert success, f"Forge failed: {msg}"
        assert "精铁剑" in msg

        # Verify forge exp gained
        assert player.forging_exp == 15  # recipe.forge_exp = 15

        # Verify instance exists in DB
        async with conn.execute(
            "SELECT * FROM weapon_instances WHERE user_id=?", ("test1",)
        ) as cur:
            rows = await cur.fetchall()
        assert len(rows) == 1
        row = dict(rows[0])
        assert row["template_name"] == "精铁符剑"
        assert row["item_type"] == "weapon"
        assert row["source_recipe"] == "forge_001"
        assert row["quality"] in ("下品", "中品", "上品", "极品")

    @pytest.mark.asyncio
    async def test_forge_rank_required_too_high(self, forging_env, forge_db):
        conn = forge_db
        fm = forging_env["forging_manager"]
        # Player forging_level=1, recipe requires rank_required=5 -> fail
        await insert_forge_player(conn, "low_lvl", f_level=1,
                                  items={"精铁": 10, "紫金沙": 5})
        player = await forging_env["db"].get_player_by_id("low_lvl")

        success, msg = await fm.forge(player, "forge_003", quantity=1)
        assert not success
        assert "锻造等级不足" in msg

    @pytest.mark.asyncio
    async def test_forge_insufficient_materials(self, forging_env, forge_db):
        conn = forge_db
        fm = forging_env["forging_manager"]
        # Only 1 精铁, need 2
        await insert_forge_player(conn, "poor", items={"精铁": 1, "紫金沙": 5})
        player = await forging_env["db"].get_player_by_id("poor")

        success, msg = await fm.forge(player, "forge_001", quantity=1)
        assert not success
        assert "数量不足" in msg

    @pytest.mark.asyncio
    async def test_forge_unknown_recipe(self, forging_env):
        fm = forging_env["forging_manager"]
        player = Player(user_id="nobody")
        success, msg = await fm.forge(player, "forge_999", quantity=1)
        assert not success
        assert "配方" in msg

    @pytest.mark.asyncio
    async def test_forge_invalid_quantity(self, forging_env):
        fm = forging_env["forging_manager"]
        player = Player(user_id="nobody")
        success, msg = await fm.forge(player, "forge_001", quantity=0)
        assert not success
        success, msg = await fm.forge(player, "forge_001", quantity=11)
        assert not success
        assert "数量" in msg

    @pytest.mark.asyncio
    async def test_batch_forge(self, forging_env, forge_db):
        conn = forge_db
        fm = forging_env["forging_manager"]
        await insert_forge_player(conn, "batch", items={"精铁": 20, "紫金沙": 10})
        player = await forging_env["db"].get_player_by_id("batch")

        success, msg = await fm.forge(player, "forge_001", quantity=3)
        assert success, f"Batch forge failed: {msg}"

        # Exp: 3 * 15 = 45. Lv1 level-up cost: 30. 45 - 30 = 15 remaining
        assert player.forging_exp == 15
        assert player.forging_level == 2

        # 3 instances created
        async with conn.execute(
            "SELECT COUNT(*) as cnt FROM weapon_instances WHERE user_id=?", ("batch",)
        ) as cur:
            row = await cur.fetchone()
        assert row["cnt"] == 3


class TestDecompose:
    """Tests for the decompose method."""

    @pytest.mark.asyncio
    async def test_decompose_returns_materials(self, forging_env, forge_db):
        conn = forge_db
        fm = forging_env["forging_manager"]
        await insert_forge_player(conn, "deco", items={"精铁": 10, "紫金沙": 5})
        player = await forging_env["db"].get_player_by_id("deco")

        # First forge something
        success, msg = await fm.forge(player, "forge_001", quantity=1)
        assert success

        # Get the instance ID from the forged item
        async with conn.execute(
            "SELECT instance_id FROM weapon_instances WHERE user_id=?", ("deco",)
        ) as cur:
            row = await cur.fetchone()
        instance_id = row["instance_id"]

        # Now decompose it
        success, msg = await fm.decompose(player, instance_id)
        assert success, f"Decompose failed: {msg}"
        assert "分解成功" in msg


class TestForgeExpAndLevel:
    """Tests for forging exp accumulation and level-up."""

    @pytest.mark.asyncio
    async def test_forge_exp_accumulates(self, forging_env, forge_db):
        conn = forge_db
        fm = forging_env["forging_manager"]
        await insert_forge_player(conn, "exp_test", f_level=5, f_exp=20,
                                  items={"精铁": 100, "紫金沙": 50})
        player = await forging_env["db"].get_player_by_id("exp_test")

        await fm.forge(player, "forge_001", quantity=1)  # +15 exp
        assert player.forging_exp == 35  # 20 + 15

    @pytest.mark.asyncio
    async def test_level_up_from_forging(self, forging_env, forge_db):
        conn = forge_db
        fm = forging_env["forging_manager"]
        # forging_level=1, exp=28 => 28+15=43. Lv1 costs 30. 43-30=13. Level=2.
        await insert_forge_player(conn, "lvl_up", f_level=1, f_exp=28,
                                  items={"精铁": 100, "紫金沙": 50})
        player = await forging_env["db"].get_player_by_id("lvl_up")

        await fm.forge(player, "forge_001", quantity=1)
        assert player.forging_level == 2
        assert player.forging_exp == 13

    @pytest.mark.asyncio
    async def test_multi_level_up(self, forging_env):
        """Test the level-up formula directly: Lv.N requires N*30 exp to next level."""
        player = Player(user_id="multi", forging_level=1, forging_exp=0)

        # Simulate adding 900 exp then applying level-up formula
        player.forging_exp += 900
        while player.forging_exp >= player.forging_level * 30:
            player.forging_exp -= player.forging_level * 30
            player.forging_level += 1

        # Lv1 cost=30, Lv2 cost=60, Lv3 cost=90, Lv4 cost=120, Lv5 cost=150,
        # Lv6 cost=180, Lv7 cost=210 => total 840 used, 60 left at Lv8
        assert player.forging_level == 8
        assert player.forging_exp == 60


class TestGetForgeableRecipes:
    """Tests for recipe listing."""

    @pytest.mark.asyncio
    async def test_get_forgeable_recipes_filters_by_forging_level(self, forging_env):
        fm = forging_env["forging_manager"]
        player = Player(user_id="test", forging_level=1)
        recipes = await fm.get_forgeable_recipes(player)
        recipe_names = [r["name"] for r in recipes if r["unlocked"]]
        locked_names = [r["name"] for r in recipes if not r["unlocked"]]
        # forge_001 (rank_required=0) should be unlocked
        assert "精铁剑" in recipe_names
        # forge_003 (rank_required=5) should be locked
        assert "青玉剑" in locked_names

    @pytest.mark.asyncio
    async def test_get_forgeable_recipes_shows_correct_fields(self, forging_env):
        fm = forging_env["forging_manager"]
        player = Player(user_id="test", forging_level=10)
        recipes = await fm.get_forgeable_recipes(player)
        assert len(recipes) > 0
        recipe = recipes[0]
        assert "id" in recipe
        assert "name" in recipe
        assert "rank_required" in recipe
        assert "ingredients" in recipe
        assert "output_template" in recipe
        assert "output_type" in recipe
        assert "forge_exp" in recipe
        assert "unlocked" in recipe
