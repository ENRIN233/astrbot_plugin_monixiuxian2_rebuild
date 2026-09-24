# tests/test_merchant_manager.py
"""云游商人测试 — 选品/定价/品阶带锚定/窗口调度/购买限购/CAS 并发/重复放行/入库路由"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import aiosqlite
import pytest

from astrbot_plugin_monixiuxian2.models import Player
from astrbot_plugin_monixiuxian2.managers.merchant_manager import (
    MerchantManager, rank_index_of, rank_for_realm, gen_daily_schedule,
    TECH_BASE_PRICES, RANK_NAMES,
)

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── 测试替身 ──

class MerchantTestDB:
    """内存 sqlite + 玩家存根（提供 conn / update_player / get_player_by_id）"""

    def __init__(self):
        self.conn = None
        self.players = {}

    async def connect(self):
        self.conn = await aiosqlite.connect(":memory:")
        self.conn.row_factory = aiosqlite.Row
        # 与 data/migration.py v44 保持一致
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS merchant_windows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                merchant_name TEXT NOT NULL DEFAULT '',
                opened_at REAL NOT NULL,
                closed_at REAL NOT NULL,
                status INTEGER NOT NULL DEFAULT 0,
                goods_count INTEGER NOT NULL DEFAULT 0
            )
        """)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS merchant_goods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                window_id INTEGER NOT NULL,
                slot_type TEXT NOT NULL DEFAULT 'regular',
                item_kind TEXT NOT NULL DEFAULT 'material',
                item_name TEXT NOT NULL,
                rank_idx INTEGER NOT NULL DEFAULT -1,
                price INTEGER NOT NULL DEFAULT 0,
                stock_total INTEGER NOT NULL DEFAULT 1,
                stock_left INTEGER NOT NULL DEFAULT 1
            )
        """)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS merchant_purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                window_id INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                item_kind TEXT NOT NULL DEFAULT 'material',
                item_name TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                price INTEGER NOT NULL DEFAULT 0,
                total_price INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL
            )
        """)
        await self.conn.commit()

    async def close(self):
        if self.conn:
            await self.conn.close()

    async def update_player(self, player):
        self.players[player.user_id] = player

    async def get_player_by_id(self, uid):
        return self.players.get(uid)


class FakeConfigManager:
    """最小配置替身：材料/药材/丹药/功法/神通/辅修 各含样本"""

    def __init__(self):
        self.items_data = {
            "2001": {"name": "精铁", "type": "材料", "rank": "凡品", "price": 300000},
            "2002": {"name": "百年灵草", "type": "材料", "rank": "凡品", "price": 1500000},
        }
        self.skills_data = {
            "s1": {"name": "天星若雨", "rank": "天阶下品", "required_level_index": 28},
            "s2": {"name": "化尘剑法", "rank": "人阶上品", "required_level_index": 3},
        }
        self.sub_techniques_data = {
            "st1": {"name": "焚天诀", "rank": "仙阶下品"},
            "st2": {"name": "敛息术", "rank": "黄阶下品"},
        }
        self.herbs_data = {
            "恒心草": {"rank": 54},
            "铁线草": {"rank": 30},
        }
        self.utility_pills_data = {
            "p1": {"name": "生骨丹", "price": 100000, "rank": "凡品"},
        }
        self.garden_crops = {"tiers": [
            {"tier": 1, "label": "凡品", "rank_min": 48, "rank_max": 999, "seed_cost": 50000},
            {"tier": 5, "label": "仙品", "rank_min": 0, "rank_max": 23, "seed_cost": 5000000},
        ]}


class FakeStorageRing:
    def __init__(self):
        self.stored = []

    async def store_item(self, player, item_name, count=1, silent=False, **kwargs):
        self.stored.append((player.user_id, item_name, count))
        ring = json.loads(player.storage_ring_items or "{}")
        ring[item_name] = {"count": ring.get(item_name, {}).get("count", 0) + count, "bound": False}
        player.storage_ring_items = json.dumps(ring, ensure_ascii=False)
        return True, "ok"


def make_player(uid="u1", gold=10_000_000_000, level_index=40, techniques=None):
    return Player(
        user_id=uid, user_name=f"道友{uid}", level_index=level_index,
        gold=gold,
        techniques=json.dumps(techniques or [], ensure_ascii=False),
    )


async def make_manager(db=None, **overrides):
    """构建带内存库的 manager；overrides 直接写入 settings"""
    db = db or MerchantTestDB()
    await db.connect()
    mgr = MerchantManager(db, FakeConfigManager(), storage_ring_mgr=FakeStorageRing())
    mgr.settings.update(overrides)
    mgr.broadcasts = []

    async def _collect(msg):
        mgr.broadcasts.append(msg)

    mgr.broadcast_fn = _collect
    return mgr, db


async def insert_open_window(db, merchant="青衫客", now=1000.0, duration=1800.0):
    """直接插入一个开启窗口（绕过随机选品），返回 window_id"""
    cursor = await db.conn.execute(
        "INSERT INTO merchant_windows (merchant_name, opened_at, closed_at, status, goods_count) "
        "VALUES (?, ?, ?, 0, 0)",
        (merchant, now, now + duration),
    )
    await db.conn.commit()
    return cursor.lastrowid


async def insert_goods(db, window_id, name="精铁", kind="material", slot="regular",
                       rank_idx=-1, price=300000, stock=5):
    cursor = await db.conn.execute(
        "INSERT INTO merchant_goods (window_id, slot_type, item_kind, item_name, "
        "rank_idx, price, stock_total, stock_left) VALUES (?,?,?,?,?,?,?,?)",
        (window_id, slot, kind, name, rank_idx, price, stock, stock),
    )
    await db.conn.commit()
    return cursor.lastrowid


async def count_purchases(db, uid, window_id=None, since=0):
    if window_id is not None:
        async with db.conn.execute(
            "SELECT COUNT(*) FROM merchant_purchases WHERE user_id=? AND window_id=?",
            (uid, window_id)) as cur:
            return (await cur.fetchone())[0]
    async with db.conn.execute(
        "SELECT COUNT(*) FROM merchant_purchases WHERE user_id=? AND created_at>=?",
        (uid, since)) as cur:
        return (await cur.fetchone())[0]


NOW = 1_750_000_000.0


# ── 纯逻辑：品阶映射与定价 ──

@pytest.mark.asyncio
async def test_rank_index_aliases():
    assert rank_index_of("无上神通") == 13
    assert rank_index_of("无上仙法") == 13
    assert rank_index_of("仙阶极品") == 12
    assert rank_index_of("不存在的品阶") == -1


@pytest.mark.asyncio
async def test_rank_for_realm_mapping():
    assert rank_for_realm(0) == 0
    assert rank_for_realm(57) == 13
    assert rank_for_realm(-5) == 0
    # 单调不减
    seq = [rank_for_realm(i) for i in range(58)]
    assert seq == sorted(seq)


@pytest.mark.asyncio
async def test_v11_price_table():
    """v1.1 定价锚点：仙下 0.9 亿 / 仙极 2.5 亿 / 无上 5 亿"""
    assert TECH_BASE_PRICES[10] == 90_000_000
    assert TECH_BASE_PRICES[12] == 250_000_000
    assert TECH_BASE_PRICES[13] == 500_000_000
    # 后段加速：仙极→无上 倍率高于 黄下→黄上
    assert TECH_BASE_PRICES[13] / TECH_BASE_PRICES[12] > TECH_BASE_PRICES[3] / TECH_BASE_PRICES[2]


@pytest.mark.asyncio
async def test_price_scale_override():
    """PRICE_SCALE 全局旋钮：scale=2 时修炼位价格翻倍"""
    mgr, db = await make_manager(price_scale=2.0, tech_slots_min=2, tech_slots_max=2,
                                 regular_slots=0, bargain_chance=0.0)
    try:
        _, goods = mgr.generate_goods(top_idx=57, rng=__import__("random").Random(3))
        techs = [g for g in goods if g["slot_type"] == "tech"]
        assert techs, "高境界锚定下应出修炼位"
        for g in techs:
            assert g["price"] >= TECH_BASE_PRICES[g["rank_idx"]] * 2 * 0.99
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_generate_goods_structure():
    """货架结构：常规位库存 3-5、修炼位库存 1、slot 类型合法"""
    mgr, db = await make_manager()
    try:
        for seed in range(30):
            name, goods = mgr.generate_goods(top_idx=40, rng=__import__("random").Random(seed))
            assert name
            assert 3 <= len(goods) <= 6
            for g in goods:
                assert g["slot_type"] in ("regular", "tech", "bargain")
                assert g["price"] > 0
                if g["slot_type"] == "tech":
                    assert g["stock_left"] == 1
                    assert 0 <= g["rank_idx"] <= 13
                elif g["slot_type"] == "regular":
                    assert 3 <= g["stock_left"] <= 5
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_tech_rank_band_anchored_to_server_top():
    """品阶带锚定：低境界服务器不会刷出远超锚定带的品阶（长尾 +2）"""
    mgr, db = await make_manager()
    try:
        top = 10  # 服务器最高只有 10 级
        hi_cap = rank_for_realm(max(0, top - 4)) + 2
        for seed in range(50):
            _, goods = mgr.generate_goods(top_idx=top, rng=__import__("random").Random(seed))
            for g in goods:
                if g["slot_type"] == "tech":
                    assert g["rank_idx"] <= hi_cap
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_tech_pool_empty_rank_fallback():
    """品阶空池就近兜底：池中只有 rank13 时也能选到商品"""
    mgr, db = await make_manager()
    try:
        # FakeConfigManager 神通池 rank 3 与 8；请求 rank 13 应就近命中
        pool = mgr._tech_pool("skill")
        assert pool
        # 构造一个只有高端 rank 池的 manager
        mgr.config_manager.skills_data = {"s9": {"name": "苍寰变", "rank": "无上神通"}}
        rng = __import__("random").Random(1)
        rank_idx = mgr._pick_rank_in_band(57, rng)  # 高境界 → 高 rank
        names_pool = mgr._tech_pool("skill")
        assert 13 in names_pool
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_bargain_slot_never_tech():
    """捡漏位只出常规品（不出功法/神通/辅修）"""
    mgr, db = await make_manager(bargain_chance=1.0, regular_slots=3)
    try:
        for seed in range(30):
            _, goods = mgr.generate_goods(top_idx=50, rng=__import__("random").Random(seed))
            bargains = [g for g in goods if g["slot_type"] == "bargain"]
            assert len(bargains) <= 1
            for g in bargains:
                assert g["item_kind"] in ("material", "herb", "pill")
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_daily_schedule_deterministic():
    """同日期计划确定性（date 作 seed）"""
    slots1 = gen_daily_schedule("2026-09-24", 3, 30, 60, __import__("random").Random("merchant-2026-09-24"))
    slots2 = gen_daily_schedule("2026-09-24", 3, 30, 60, __import__("random").Random("merchant-2026-09-24"))
    assert slots1 == slots2
    assert 1 <= len(slots1) <= 3


# ── 窗口生命周期 ──

@pytest.mark.asyncio
async def test_tick_opens_window_with_broadcast():
    mgr, db = await make_manager()
    try:
        # 强制计划命中当前时刻
        mgr._today_schedule = lambda now: [{"start_ts": NOW, "duration_sec": 1800}]
        messages = await mgr.tick(now=NOW + 1)
        assert len(messages) == 1
        assert "云游商人" in messages[0]
        window = await mgr.get_current_window()
        assert window and window["status"] == 0
        async with db.conn.execute("SELECT COUNT(*) FROM merchant_goods WHERE window_id=?",
                                   (window["id"],)) as cur:
            assert (await cur.fetchone())[0] > 0
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_tick_closes_expired_window():
    mgr, db = await make_manager()
    try:
        wid = await insert_open_window(db, now=NOW, duration=1800)
        await insert_goods(db, wid)
        messages = await mgr.tick(now=NOW + 1801)
        assert messages and "离去" in messages[0]
        window = await mgr.get_current_window()
        assert window is None
        async with db.conn.execute("SELECT status FROM merchant_windows WHERE id=?", (wid,)) as cur:
            assert (await cur.fetchone())[0] == 1
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_tick_disabled():
    mgr, db = await make_manager(enabled=False)
    try:
        await insert_open_window(db, now=NOW, duration=1)
        assert await mgr.tick(now=NOW + 10) == []
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_broadcast_disabled_still_opens():
    """广播关闭：窗口照常开启但无广播消息"""
    mgr, db = await make_manager(broadcast_enabled=False)
    try:
        mgr._today_schedule = lambda now: [{"start_ts": NOW, "duration_sec": 1800}]
        messages = await mgr.tick(now=NOW + 1)
        assert messages == []
        assert await mgr.get_current_window() is not None
    finally:
        await db.close()


# ── 购买 ──

@pytest.mark.asyncio
async def test_buy_regular_success():
    mgr, db = await make_manager()
    try:
        wid = await insert_open_window(db, now=NOW)
        gid = await insert_goods(db, wid, name="精铁", kind="material", price=300000, stock=5)
        player = make_player(gold=1_000_000)
        ok, msg = await mgr.buy(player, gid, 2, now=NOW + 10)
        assert ok
        assert player.gold == 1_000_000 - 600_000
        async with db.conn.execute("SELECT stock_left FROM merchant_goods WHERE id=?", (gid,)) as cur:
            assert (await cur.fetchone())[0] == 3
        assert await count_purchases(db, "u1", wid) == 1
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_buy_cas_concurrent_stock_one():
    """全服唯一 1 件：两人抢购一成一败"""
    mgr, db = await make_manager()
    try:
        wid = await insert_open_window(db, now=NOW)
        gid = await insert_goods(db, wid, name="天星若雨", kind="skill", slot="tech",
                                 rank_idx=8, price=35_000_000, stock=1)
        p1, p2 = make_player("u1"), make_player("u2")
        ok1, _ = await mgr.buy(p1, gid, 1, now=NOW + 10)
        ok2, msg2 = await mgr.buy(p2, gid, 1, now=NOW + 11)
        assert ok1 and not ok2
        assert "手慢" in msg2
        assert p1.gold == 10_000_000_000 - 35_000_000  # 成交方扣款
        assert p2.gold == 10_000_000_000  # 失败方未扣款
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_buy_insufficient_gold():
    mgr, db = await make_manager()
    try:
        wid = await insert_open_window(db, now=NOW)
        gid = await insert_goods(db, wid, price=300000, stock=5)
        player = make_player(gold=100)
        ok, msg = await mgr.buy(player, gid, 1, now=NOW + 10)
        assert not ok and "灵石不足" in msg
        assert player.gold == 100
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_buy_window_limit():
    mgr, db = await make_manager()
    try:
        wid = await insert_open_window(db, now=NOW)
        gid = await insert_goods(db, wid, price=300000, stock=10)
        player = make_player(gold=10_000_000)
        ok1, _ = await mgr.buy(player, gid, 1, now=NOW + 10)
        ok2, _ = await mgr.buy(player, gid, 1, now=NOW + 11)
        ok3, msg3 = await mgr.buy(player, gid, 1, now=NOW + 12)
        assert ok1 and ok2 and not ok3
        assert "每期上限" in msg3
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_buy_daily_limit():
    mgr, db = await make_manager(window_buy_limit=5, daily_buy_limit=1)
    try:
        wid = await insert_open_window(db, now=NOW)
        gid = await insert_goods(db, wid, price=300000, stock=10)
        player = make_player(gold=10_000_000)
        ok1, _ = await mgr.buy(player, gid, 1, now=NOW + 10)
        ok2, msg2 = await mgr.buy(player, gid, 1, now=NOW + 11)
        assert ok1 and not ok2 and "每日上限" in msg2
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_buy_quantity_counts_toward_window_limit():
    """限购按件数统计，单笔购买数量不能绕过每期上限"""
    mgr, db = await make_manager(window_buy_limit=2, daily_buy_limit=10)
    try:
        wid = await insert_open_window(db, now=NOW)
        gid = await insert_goods(db, wid, price=300000, stock=10)
        player = make_player(gold=10_000_000)
        ok1, _ = await mgr.buy(player, gid, 2, now=NOW + 10)
        ok2, msg2 = await mgr.buy(player, gid, 1, now=NOW + 11)
        assert ok1 and not ok2 and "每期上限" in msg2
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_regular_pool_accepts_list_shaped_herbs_data():
    """生产 ConfigManager 的 herbs_data 是列表，常规位仍应能选到药材"""
    mgr, db = await make_manager()
    try:
        mgr.config_manager.herbs_data = [{"name": "灵草", "rank": 50}]
        pools, _ = mgr._pool_regular()
        assert pools["herb"]
        assert pools["herb"][0]["name"] == "灵草"
        assert mgr._regular_ref_price("herb", "灵草") == 100_000
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_buy_tech_window_limit():
    """修炼位每人每期限购 1 件（同窗口两件不同 tech 也拦）"""
    mgr, db = await make_manager(window_buy_limit=5)
    try:
        wid = await insert_open_window(db, now=NOW)
        g1 = await insert_goods(db, wid, name="天星若雨", kind="skill", slot="tech", rank_idx=8, price=1000)
        g2 = await insert_goods(db, wid, name="焚天诀", kind="subtech", slot="tech", rank_idx=10, price=1000)
        player = make_player(gold=10_000_000)
        ok1, _ = await mgr.buy(player, g1, 1, now=NOW + 10)
        ok2, msg2 = await mgr.buy(player, g2, 1, now=NOW + 11)
        assert ok1 and not ok2 and "限购 1 件" in msg2
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_buy_owned_mark_not_blocking():
    """已拥有：不拦截，回执带提示（v1.1 允许重复购买转卖）"""
    mgr, db = await make_manager()
    try:
        wid = await insert_open_window(db, now=NOW)
        gid = await insert_goods(db, wid, name="青元功", kind="tech", slot="tech",
                                 rank_idx=0, price=600_000, stock=1)
        player = make_player(techniques=["青元功"])
        ok, msg = await mgr.buy(player, gid, 1, now=NOW + 10)
        assert ok and "已身怀" in msg
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_pill_delivery_to_pills_inventory():
    """丹药 → 丹药背包（不走储物戒）"""
    mgr, db = await make_manager()
    try:
        wid = await insert_open_window(db, now=NOW)
        gid = await insert_goods(db, wid, name="生骨丹", kind="pill", slot="regular", price=100000, stock=3)
        player = make_player()
        ok, msg = await mgr.buy(player, gid, 2, now=NOW + 10)
        assert ok
        inv = json.loads(player.pills_inventory)
        assert inv["生骨丹"] == 2
        assert "丹药背包" in msg
        assert mgr.storage_ring_mgr.stored == []  # 未走储物戒
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_tech_delivery_to_storage_ring():
    """功法/神通/辅修 → 储物戒（与悬赏掉落路由一致）"""
    mgr, db = await make_manager()
    try:
        wid = await insert_open_window(db, now=NOW)
        gid = await insert_goods(db, wid, name="天星若雨", kind="skill", slot="tech",
                                 rank_idx=8, price=35_000_000, stock=1)
        player = make_player()
        ok, msg = await mgr.buy(player, gid, 1, now=NOW + 10)
        assert ok
        assert mgr.storage_ring_mgr.stored == [("u1", "天星若雨", 1)]
        # 修炼位售出触发全服播报
        assert any("购入" in m for m in mgr.broadcasts)
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_buy_after_window_closed():
    """窗口过期后不可购买"""
    mgr, db = await make_manager()
    try:
        wid = await insert_open_window(db, now=NOW, duration=100)
        gid = await insert_goods(db, wid, price=300000, stock=5)
        player = make_player()
        ok, msg = await mgr.buy(player, gid, 1, now=NOW + 200)
        assert not ok and "不在" in msg
    finally:
        await db.close()
