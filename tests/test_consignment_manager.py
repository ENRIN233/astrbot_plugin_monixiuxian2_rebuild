import pytest
import json
import time
from astrbot_plugin_monixiuxian2.managers.consignment_manager import ConsignmentManager
from astrbot_plugin_monixiuxian2.data.migration import MIGRATION_TASKS


@pytest.fixture
async def db_with_consignment(memory_db):
    await MIGRATION_TASKS[21](memory_db, config_manager=None)
    await memory_db.execute("""
        CREATE TABLE players (
            user_id TEXT PRIMARY KEY,
            user_name TEXT,
            gold INTEGER NOT NULL DEFAULT 0,
            storage_ring_items TEXT NOT NULL DEFAULT '{}',
            pills_inventory TEXT NOT NULL DEFAULT '{}'
        )
    """)
    yield memory_db


async def add_player(conn, uid, gold=10_000_000, items=None, pills=None):
    items = items or {}
    pills = pills or {}
    await conn.execute(
        "INSERT INTO players (user_id, user_name, gold, storage_ring_items, pills_inventory) "
        "VALUES (?,?,?,?,?)",
        (uid, f"道友{uid}", gold, json.dumps(items), json.dumps(pills)),
    )
    await conn.commit()


@pytest.mark.asyncio
async def test_list_item_fails_without_enough_fee(db_with_consignment):
    await add_player(db_with_consignment, "S", gold=10_000, items={"灵草": 5})
    cm = ConsignmentManager(db_with_consignment)
    with pytest.raises(ValueError, match="灵石不足"):
        await cm.list_item("S", "灵草", "i", "material", price=1_000_000)


@pytest.mark.asyncio
async def test_buy_listing_transfers(db_with_consignment):
    await add_player(db_with_consignment, "S", gold=10_000_000, items={"灵草": 5})
    await add_player(db_with_consignment, "B", gold=2_000_000)
    cm = ConsignmentManager(db_with_consignment)
    lid = await cm.list_item("S", "灵草", "i", "material", price=1_000_000, quantity=2)
    # S 扣手续费 1_000_000 * 2 * 5% = 100_000 -> 9_900_000
    await cm.buy_listing(lid, buyer_id="B")

    async with db_with_consignment.execute("SELECT gold, storage_ring_items FROM players WHERE user_id='S'") as cur:
        s = await cur.fetchone()
    # S 收到 1_000_000 * 2 = 2_000_000 全额
    assert s["gold"] == 9_900_000 + 2_000_000
    async with db_with_consignment.execute("SELECT gold, storage_ring_items FROM players WHERE user_id='B'") as cur:
        b = await cur.fetchone()
    assert b["gold"] == 2_000_000 - 2_000_000
    assert json.loads(b["storage_ring_items"]) == {"灵草": 2}


@pytest.mark.asyncio
async def test_buy_twice_only_first_succeeds(db_with_consignment):
    await add_player(db_with_consignment, "S", gold=10_000_000, items={"灵草": 5})
    await add_player(db_with_consignment, "B1", gold=2_000_000)
    await add_player(db_with_consignment, "B2", gold=2_000_000)
    cm = ConsignmentManager(db_with_consignment)
    lid = await cm.list_item("S", "灵草", "i", "material", price=1_000_000, quantity=2)
    await cm.buy_listing(lid, buyer_id="B1")
    with pytest.raises(ValueError):
        await cm.buy_listing(lid, buyer_id="B2")


@pytest.mark.asyncio
async def test_cancel_listing_returns_item_keeps_fee(db_with_consignment):
    await add_player(db_with_consignment, "S", gold=10_000_000, items={"灵草": 5})
    cm = ConsignmentManager(db_with_consignment)
    lid = await cm.list_item("S", "灵草", "i", "material", price=1_000_000, quantity=2)
    await cm.cancel_listing(lid, user_id="S")

    async with db_with_consignment.execute("SELECT gold, storage_ring_items FROM players WHERE user_id='S'") as cur:
        row = await cur.fetchone()
    # 手续费 = 1_000_000 * 2 * 5% = 100_000，不退
    assert row["gold"] == 10_000_000 - 100_000
    assert json.loads(row["storage_ring_items"]) == {"灵草": 5}


@pytest.mark.asyncio
async def test_expire_old_listings(db_with_consignment):
    await add_player(db_with_consignment, "S", gold=10_000_000, items={"灵草": 5})
    cm = ConsignmentManager(db_with_consignment)
    lid = await cm.list_item("S", "灵草", "i", "material", price=1_000_000, quantity=1,
                              duration_seconds=-1)  # 立即过期
    n = await cm.expire_old_listings()
    assert n >= 1
    async with db_with_consignment.execute("SELECT status FROM consignment_listings WHERE listing_id=?", (lid,)) as cur:
        assert (await cur.fetchone())["status"] == "expired"
    async with db_with_consignment.execute("SELECT storage_ring_items FROM players WHERE user_id='S'") as cur:
        inv = json.loads((await cur.fetchone())[0])
    # 物品退回
    assert inv.get("灵草") == 5
