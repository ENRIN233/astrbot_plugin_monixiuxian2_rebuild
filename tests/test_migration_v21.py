import pytest
import aiosqlite
from astrbot_plugin_monixiuxian2.data.migration import MIGRATION_TASKS, LATEST_DB_VERSION


@pytest.mark.asyncio
async def test_latest_version_is_29():
    assert LATEST_DB_VERSION == 31
    assert 21 in MIGRATION_TASKS
    assert 22 in MIGRATION_TASKS
    assert 23 in MIGRATION_TASKS
    assert 24 in MIGRATION_TASKS
    assert 25 in MIGRATION_TASKS
    assert 26 in MIGRATION_TASKS
    assert 27 in MIGRATION_TASKS
    assert 28 in MIGRATION_TASKS
    assert 29 in MIGRATION_TASKS
    assert 30 in MIGRATION_TASKS
    assert 31 in MIGRATION_TASKS


@pytest.mark.asyncio
async def test_migration_v21_creates_tables(memory_db):
    # 模拟 v20 已存在
    await memory_db.execute("CREATE TABLE db_info (version INTEGER NOT NULL)")
    await memory_db.execute("INSERT INTO db_info VALUES (20)")
    await memory_db.commit()

    # 直接调用 v21 迁移函数
    await MIGRATION_TASKS[21](memory_db, config_manager=None)
    await memory_db.commit()

    async with memory_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('trades','consignment_listings')"
    ) as cur:
        rows = await cur.fetchall()
    table_names = {r[0] for r in rows}
    assert "trades" in table_names
    assert "consignment_listings" in table_names

    # 验证 trades 表的关键列
    async with memory_db.execute("PRAGMA table_info(trades)") as cur:
        cols = {r[1] for r in await cur.fetchall()}
    for c in ("trade_id", "player_a", "player_b", "player_a_items", "player_b_items",
              "player_a_stones", "player_b_stones", "a_confirmed", "b_confirmed",
              "status", "created_at", "expires_at"):
        assert c in cols, f"missing column: {c}"

    # 验证 consignment_listings
    async with memory_db.execute("PRAGMA table_info(consignment_listings)") as cur:
        cols = {r[1] for r in await cur.fetchall()}
    for c in ("listing_id", "seller_id", "item_id", "item_name", "item_type",
              "quantity", "price", "listed_at", "expires_at", "status",
              "buyer_id", "sold_at"):
        assert c in cols, f"missing column: {c}"
