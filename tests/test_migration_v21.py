import pytest
import aiosqlite
from astrbot_plugin_monixiuxian2.data.migration import MIGRATION_TASKS, LATEST_DB_VERSION


@pytest.mark.asyncio
async def test_latest_version_is_29():
    assert LATEST_DB_VERSION == len(MIGRATION_TASKS) + 1, (
        f"LATEST_DB_VERSION ({LATEST_DB_VERSION}) "
        f"应比 MIGRATION_TASKS 数量 ({len(MIGRATION_TASKS)}) 大 1 (v1 为初始状态)"
    )
    assert LATEST_DB_VERSION >= 38, f"当前版本 {LATEST_DB_VERSION}，预期至少 38"
    # 确保 v21-当前最新所有迁移任务都已注册
    for v in range(21, LATEST_DB_VERSION + 1):
        assert v in MIGRATION_TASKS, f"迁移 v{v} 未注册"


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
