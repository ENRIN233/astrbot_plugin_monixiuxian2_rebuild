import pytest
import time
import json
from astrbot_plugin_monixiuxian2.managers.trade_manager import TradeManager
from astrbot_plugin_monixiuxian2.data.migration import MIGRATION_TASKS


@pytest.fixture
async def db_with_trades(memory_db):
    """创建 v21 schema 的内存数据库"""
    await MIGRATION_TASKS[21](memory_db, config_manager=None)
    # 同时建 minimal players 表以便 manager 查询
    await memory_db.execute("""
        CREATE TABLE players (
            user_id TEXT PRIMARY KEY,
            user_name TEXT,
            gold INTEGER NOT NULL DEFAULT 0,
            pills_inventory TEXT NOT NULL DEFAULT '{}',
            storage_ring_items TEXT NOT NULL DEFAULT '{}'
        )
    """)
    yield memory_db


async def insert_player(conn, uid, gold=100000, items=None, pills=None):
    items = items or {}
    pills = pills or {}
    await conn.execute(
        "INSERT INTO players (user_id, user_name, gold, pills_inventory, storage_ring_items) "
        "VALUES (?, ?, ?, ?, ?)",
        (uid, f"道友{uid}", gold, json.dumps(pills), json.dumps(items)),
    )
    await conn.commit()


@pytest.mark.asyncio
async def test_create_trade_starts_in_pending_state(db_with_trades):
    await insert_player(db_with_trades, "A")
    await insert_player(db_with_trades, "B")

    tm = TradeManager(db_with_trades)
    trade_id = await tm.create_trade("A", "B", duration_seconds=1800)
    assert trade_id is not None

    async with db_with_trades.execute(
        "SELECT player_a, player_b, status, a_confirmed, b_confirmed FROM trades WHERE trade_id=?",
        (trade_id,)
    ) as cur:
        row = await cur.fetchone()
    assert row["player_a"] == "A"
    assert row["player_b"] == "B"
    assert row["status"] == "pending"
    assert row["a_confirmed"] == 0
    assert row["b_confirmed"] == 0


@pytest.mark.asyncio
async def test_accept_trade_transitions_to_trading(db_with_trades):
    await insert_player(db_with_trades, "A")
    await insert_player(db_with_trades, "B")

    tm = TradeManager(db_with_trades)
    trade_id = await tm.create_trade("A", "B", duration_seconds=1800)
    await tm.accept_trade(trade_id, "B")

    async with db_with_trades.execute(
        "SELECT status FROM trades WHERE trade_id=?", (trade_id,)
    ) as cur:
        row = await cur.fetchone()
    assert row["status"] == "trading"


@pytest.mark.asyncio
async def test_accept_trade_rejects_wrong_user(db_with_trades):
    await insert_player(db_with_trades, "A")
    await insert_player(db_with_trades, "B")

    tm = TradeManager(db_with_trades)
    trade_id = await tm.create_trade("A", "B")
    with pytest.raises(ValueError, match="接收方"):
        await tm.accept_trade(trade_id, "A")


@pytest.mark.asyncio
async def test_reject_trade_sets_cancelled(db_with_trades):
    await insert_player(db_with_trades, "A")
    await insert_player(db_with_trades, "B")

    tm = TradeManager(db_with_trades)
    trade_id = await tm.create_trade("A", "B")
    await tm.reject_trade(trade_id, "B")

    async with db_with_trades.execute(
        "SELECT status FROM trades WHERE trade_id=?", (trade_id,)
    ) as cur:
        row = await cur.fetchone()
    assert row["status"] == "cancelled"


@pytest.mark.asyncio
async def test_create_trade_fails_when_already_trading(db_with_trades):
    await insert_player(db_with_trades, "A")
    await insert_player(db_with_trades, "B")
    await insert_player(db_with_trades, "C")

    tm = TradeManager(db_with_trades)
    await tm.create_trade("A", "B", duration_seconds=1800)

    with pytest.raises(ValueError, match="已在交易"):
        await tm.create_trade("A", "C", duration_seconds=1800)


@pytest.mark.asyncio
async def test_get_active_trade_for_player(db_with_trades):
    await insert_player(db_with_trades, "A")
    await insert_player(db_with_trades, "B")
    tm = TradeManager(db_with_trades)
    tid = await tm.create_trade("A", "B", duration_seconds=1800)

    found = await tm.get_active_trade("A")
    assert found is not None
    assert found["trade_id"] == tid

    found_b = await tm.get_active_trade("B")
    assert found_b["trade_id"] == tid


@pytest.mark.asyncio
async def test_add_stones_deducts_from_player(db_with_trades):
    await insert_player(db_with_trades, "A", gold=10000)
    await insert_player(db_with_trades, "B")
    tm = TradeManager(db_with_trades)
    tid = await tm.create_trade("A", "B")
    await tm.accept_trade(tid, "B")
    await tm.add_stones(tid, "A", 3000)

    async with db_with_trades.execute("SELECT gold FROM players WHERE user_id='A'") as cur:
        a_gold = (await cur.fetchone())[0]
    assert a_gold == 7000
    async with db_with_trades.execute("SELECT player_a_stones FROM trades WHERE trade_id=?", (tid,)) as cur:
        escrow = (await cur.fetchone())[0]
    assert escrow == 3000


@pytest.mark.asyncio
async def test_add_stones_insufficient_raises(db_with_trades):
    await insert_player(db_with_trades, "A", gold=100)
    await insert_player(db_with_trades, "B")
    tm = TradeManager(db_with_trades)
    tid = await tm.create_trade("A", "B")
    await tm.accept_trade(tid, "B")
    with pytest.raises(ValueError, match="灵石不足"):
        await tm.add_stones(tid, "A", 3000)


@pytest.mark.asyncio
async def test_add_and_remove_item_round_trip(db_with_trades):
    await insert_player(db_with_trades, "A", items={"灵草": 5})
    await insert_player(db_with_trades, "B")
    tm = TradeManager(db_with_trades)
    tid = await tm.create_trade("A", "B")
    await tm.accept_trade(tid, "B")

    await tm.add_item(tid, "A", "灵草", 2)
    # 玩家剩 3，托管 2
    async with db_with_trades.execute(
        "SELECT storage_ring_items FROM players WHERE user_id='A'"
    ) as cur:
        inv = json.loads((await cur.fetchone())[0])
    assert inv == {"灵草": 3}

    await tm.remove_item(tid, "A", "灵草", 2)
    async with db_with_trades.execute(
        "SELECT storage_ring_items FROM players WHERE user_id='A'"
    ) as cur:
        inv = json.loads((await cur.fetchone())[0])
    assert inv == {"灵草": 5}


@pytest.mark.asyncio
async def test_add_pill_from_pills_inventory(db_with_trades):
    """丹药从 pills_inventory 取出，返还时回到 pills_inventory"""
    await insert_player(db_with_trades, "A", pills={"筑基丹": 3})
    await insert_player(db_with_trades, "B")
    tm = TradeManager(db_with_trades)
    tid = await tm.create_trade("A", "B")
    await tm.accept_trade(tid, "B")

    await tm.add_item(tid, "A", "筑基丹", 1)
    async with db_with_trades.execute(
        "SELECT pills_inventory FROM players WHERE user_id='A'"
    ) as cur:
        pills = json.loads((await cur.fetchone())[0])
    assert pills == {"筑基丹": 2}

    await tm.remove_item(tid, "A", "筑基丹")
    async with db_with_trades.execute(
        "SELECT pills_inventory FROM players WHERE user_id='A'"
    ) as cur:
        pills = json.loads((await cur.fetchone())[0])
    assert pills == {"筑基丹": 3}


@pytest.mark.asyncio
async def test_confirm_one_side_does_not_complete(db_with_trades):
    await insert_player(db_with_trades, "A", gold=10000)
    await insert_player(db_with_trades, "B")
    tm = TradeManager(db_with_trades)
    tid = await tm.create_trade("A", "B")
    await tm.accept_trade(tid, "B")
    await tm.add_stones(tid, "A", 1000)
    await tm.confirm(tid, "A")

    async with db_with_trades.execute("SELECT status, a_confirmed, b_confirmed FROM trades WHERE trade_id=?", (tid,)) as cur:
        row = await cur.fetchone()
    assert row["status"] == "trading"
    assert row["a_confirmed"] == 1
    assert row["b_confirmed"] == 0


@pytest.mark.asyncio
async def test_both_confirm_completes_and_transfers(db_with_trades):
    await insert_player(db_with_trades, "A", gold=10000, items={"灵草": 3})
    await insert_player(db_with_trades, "B", gold=5000, items={"丹炉": 1})
    tm = TradeManager(db_with_trades)
    tid = await tm.create_trade("A", "B")
    await tm.accept_trade(tid, "B")

    await tm.add_stones(tid, "A", 2000)
    await tm.add_item(tid, "A", "灵草", 2)
    await tm.add_item(tid, "B", "丹炉", 1)

    await tm.confirm(tid, "A")
    await tm.confirm(tid, "B")  # 第二个 confirm 触发结算

    # 交易完成
    async with db_with_trades.execute("SELECT status FROM trades WHERE trade_id=?", (tid,)) as cur:
        assert (await cur.fetchone())["status"] == "completed"
    # A 失去 2000 灵石和 2 灵草，获得 1 丹炉
    async with db_with_trades.execute("SELECT gold, storage_ring_items FROM players WHERE user_id='A'") as cur:
        row = await cur.fetchone()
    assert row["gold"] == 10000 - 2000  # 8000
    assert json.loads(row["storage_ring_items"]) == {"灵草": 1, "丹炉": 1}
    # B 获得 2000 灵石和 2 灵草，失去 1 丹炉
    async with db_with_trades.execute("SELECT gold, storage_ring_items FROM players WHERE user_id='B'") as cur:
        row = await cur.fetchone()
    assert row["gold"] == 5000 + 2000  # 7000
    assert json.loads(row["storage_ring_items"]) == {"灵草": 2}


@pytest.mark.asyncio
async def test_cancel_returns_escrow_to_owners(db_with_trades):
    await insert_player(db_with_trades, "A", gold=10000, items={"灵草": 3})
    await insert_player(db_with_trades, "B", gold=5000)
    tm = TradeManager(db_with_trades)
    tid = await tm.create_trade("A", "B")
    await tm.accept_trade(tid, "B")
    await tm.add_stones(tid, "A", 2000)
    await tm.add_item(tid, "A", "灵草", 2)

    await tm.cancel(tid, "A")

    async with db_with_trades.execute("SELECT status FROM trades WHERE trade_id=?", (tid,)) as cur:
        assert (await cur.fetchone())["status"] == "cancelled"
    async with db_with_trades.execute("SELECT gold, storage_ring_items FROM players WHERE user_id='A'") as cur:
        row = await cur.fetchone()
    assert row["gold"] == 10000
    assert json.loads(row["storage_ring_items"]) == {"灵草": 3}
