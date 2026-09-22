# tests/test_spirit_garden.py
"""灵植园 v2 测试 — 地块状态机/播种数量/偷菜限额/灵兽拦截/催熟计费/因果零接触"""
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import aiosqlite
import pytest

from astrbot_plugin_monixiuxian2.models import Player
from astrbot_plugin_monixiuxian2.managers.spirit_farm_manager import SpiritFarmManager

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── 测试替身 ──

class FarmTestDB:
    """内存 sqlite + 玩家存根（提供 conn 与 update_player/get_player_by_id）"""

    def __init__(self):
        self.conn = None
        self.players = {}

    async def connect(self):
        self.conn = await aiosqlite.connect(":memory:")
        self.conn.row_factory = aiosqlite.Row

    async def close(self):
        await self.conn.close()

    async def update_player(self, player):
        self.players[player.user_id] = player

    async def get_player_by_id(self, uid):
        return self.players.get(uid)


class FakeConfigManager:
    def __init__(self):
        with open(os.path.join(_BASE, "config", "garden_crops.json"), encoding="utf-8") as f:
            self.garden_crops = json.load(f)
        self.herbs_data = {
            "恒心草": {"rank": 54, "harvest_bonus": 0},
            "凝血草": {"rank": 48, "harvest_bonus": 0},
            "紫猴花": {"rank": 42, "harvest_bonus": 0},
            "血莲精": {"rank": 36, "harvest_bonus": 0},
            "太清玄灵草": {"rank": 30, "harvest_bonus": 0},
            "木灵三针花": {"rank": 27, "harvest_bonus": 0},
            "离火梧桐芝": {"rank": 24, "harvest_bonus": 0},
        }


class FakeStorageRing:
    def __init__(self):
        self.stored = []

    async def store_item(self, player, item_name, count=1, silent=False, **kwargs):
        self.stored.append((player.user_id, item_name, count))
        return True, "ok"


def make_player(uid="u1", level_index=13, gold=99_999_999, main_technique=""):
    return Player(user_id=uid, user_name=f"修士{uid}", level_index=level_index,
                  spiritual_root="金灵根", gold=gold, main_technique=main_technique)


async def make_setup(level_index=13, fields=3, garden_level=1):
    """返回 (db, mgr, player, farm已创建)"""
    db = FarmTestDB()
    await db.connect()
    cm = FakeConfigManager()
    mgr = SpiritFarmManager(db, cm, storage_ring_manager=FakeStorageRing())
    player = make_player("u1", level_index=level_index)
    await mgr.create_farm(player)
    if fields != 1:
        # 直接扩到指定块数（跳过升级费）
        await mgr._update_farm(player.user_id, herb_fields=fields)
    if garden_level != 1:
        await mgr._update_farm(player.user_id, garden_level=garden_level)
    return db, mgr, player


def force_plot(mgr, db, player, slot, *, mode="planted", herb="恒心草", planted_at=None,
               growth_hours=12, perfect_window_hours=24, wither_step_pct=25,
               yield_min=1, yield_max=1, yield_stolen=0, garden_level=1):
    """直接写一块地块（测试辅助）"""
    now_str = planted_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    plot = {"slot": slot, "mode": mode, "herb_id": herb, "herb_name": herb,
            "planted_at": now_str, "growth_hours": growth_hours,
            "perfect_window_hours": perfect_window_hours, "wither_step_pct": wither_step_pct,
            "yield_min": yield_min, "yield_max": yield_max, "yield_stolen": yield_stolen}
    return plot


async def load_plots(mgr, uid):
    farm = await mgr.get_user_farm(uid)
    return json.loads(farm["plots"] or "[]"), farm


# ── 地块状态推导 ──

def test_derive_state_stages():
    async def run():
        db, mgr, player = await make_setup()
        now = datetime.now()
        plot_base = {"slot": 1, "herb_name": "恒心草"}
        # 生长中：1h 前种 12h 作物
        p = dict(plot_base, mode="planted", planted_at=(now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
                 growth_hours=12, perfect_window_hours=24, wither_step_pct=25)
        st = mgr._derive_plot_state(p, 1, now)
        assert st["state"] == "growing"
        # 成熟：13h 前种（12h + 完美窗 24h 内）
        p["planted_at"] = (now - timedelta(hours=13)).strftime("%Y-%m-%d %H:%M:%S")
        st = mgr._derive_plot_state(p, 1, now)
        assert st["state"] == "mature" and st["wither_mult"] == 1.0
        # 过熟：40h 前（12+24=36h 完美期已过 4h → 0 个完整 12h 档 → 仍 100%）
        p["planted_at"] = (now - timedelta(hours=40)).strftime("%Y-%m-%d %H:%M:%S")
        st = mgr._derive_plot_state(p, 1, now)
        assert st["state"] == "mature"
        # 过熟 48h（完美期后 12h → 减 25%）
        p["planted_at"] = (now - timedelta(hours=12 + 24 + 12)).strftime("%Y-%m-%d %H:%M:%S")
        st = mgr._derive_plot_state(p, 1, now)
        assert st["state"] == "overripe" and st["wither_mult"] == 0.75
        # 枯死：12+24+48+1 h 前
        p["planted_at"] = (now - timedelta(hours=12 + 24 + 48 + 1)).strftime("%Y-%m-%d %H:%M:%S")
        st = mgr._derive_plot_state(p, 1, now)
        assert st["state"] == "dead"
        await db.close()
    asyncio.run(run())


def test_wither_floor():
    async def run():
        db, mgr, player = await make_setup()
        now = datetime.now()
        p = {"slot": 1, "mode": "planted", "herb_name": "恒心草",
             "planted_at": (now - timedelta(hours=12 + 24 + 36)).strftime("%Y-%m-%d %H:%M:%S"),
             "growth_hours": 12, "perfect_window_hours": 24, "wither_step_pct": 25}
        st = mgr._derive_plot_state(p, 1, now)
        # 过熟 36h → 3 档 ×25% = −75% → 下限 40%
        assert st["wither_mult"] == 0.40
        await db.close()
    asyncio.run(run())


def test_wild_immune_wither_at_garden_lv3():
    async def run():
        db, mgr, player = await make_setup(garden_level=3)
        now = datetime.now()
        p = {"slot": 1, "mode": "wild", "herb_name": "恒心草",
             "planted_at": (now - timedelta(hours=12 + 24 + 48 + 10)).strftime("%Y-%m-%d %H:%M:%S"),
             "growth_hours": 12, "perfect_window_hours": 24, "wither_step_pct": 25}
        st = mgr._derive_plot_state(p, 3, now)
        assert st["state"] == "mature" and not st["dead"], "园圃 Lv3 野生免疫枯萎"
        # 同条件园圃 Lv1 应枯死
        st1 = mgr._derive_plot_state(p, 1, now)
        assert st1["dead"]
        await db.close()
    asyncio.run(run())


# ── 播种数量参数（v1.2 定案）──

def test_sow_with_count():
    async def run():
        db, mgr, player = await make_setup(fields=3, garden_level=5)
        before_gold = player.gold
        ok, msg = await mgr.sow(player, "恒心草", "3")
        assert ok, msg
        # 一档种子 5 万 × 3
        assert player.gold == before_gold - 150000
        plots, farm = await load_plots(mgr, "u1")
        planted = [p for p in plots if p["mode"] == "planted"]
        assert len(planted) == 3
        # 园圃经验每块 +5
        assert farm["garden_exp"] == 15
        await db.close()
    asyncio.run(run())


def test_sow_count_capped_by_empty_slots():
    async def run():
        db, mgr, player = await make_setup(fields=3, garden_level=5)
        ok, msg = await mgr.sow(player, "恒心草", "99")
        assert ok
        assert "空地不足" in msg and "3 块" in msg
        plots, _ = await load_plots(mgr, "u1")
        assert len([p for p in plots if p["mode"] == "planted"]) == 3
        await db.close()
    asyncio.run(run())


def test_sow_all_keyword():
    async def run():
        db, mgr, player = await make_setup(fields=2, garden_level=5)
        ok, msg = await mgr.sow(player, "恒心草", "全部")
        assert ok
        plots, _ = await load_plots(mgr, "u1")
        assert len([p for p in plots if p["mode"] == "planted"]) == 2
        await db.close()
    asyncio.run(run())


def test_sow_garden_level_gate():
    async def run():
        db, mgr, player = await make_setup(fields=2, garden_level=1)
        # 紫猴花 rank 42 = 二档，园圃 Lv1 只能一档
        ok, msg = await mgr.sow(player, "紫猴花", "1")
        assert not ok and "园圃" in msg
        # 升园圃到 Lv2 后可种
        await mgr._update_farm("u1", garden_level=2)
        # 境界门槛：level_index=13 阈值 40，rank42 >= 40 ✓
        ok, msg = await mgr.sow(player, "紫猴花", "1")
        assert ok, msg
        await db.close()
    asyncio.run(run())


def test_sow_realm_gate():
    async def run():
        db, mgr, player = await make_setup(fields=2, garden_level=5)
        # level_index=13 阈值 40；血莲精 rank 36 < 40 → 拒
        ok, msg = await mgr.sow(player, "血莲精", "1")
        assert not ok and "境界" in msg
        await db.close()
    asyncio.run(run())


# ── 收取与被偷保底 ──

def test_harvest_mature_and_steal_floor():
    async def run():
        db, mgr, player = await make_setup(fields=2, garden_level=5)
        # 两块：一块产量1已成熟被偷1株；一块产量3成熟
        now_str = (datetime.now() - timedelta(hours=13)).strftime("%Y-%m-%d %H:%M:%S")
        plots = [
            force_plot(mgr, db, player, 1, herb="恒心草", planted_at=now_str, growth_hours=12, yield_min=1, yield_max=1, yield_stolen=1),
            force_plot(mgr, db, player, 2, herb="凝血草", planted_at=now_str, growth_hours=12, yield_min=3, yield_max=3),
        ]
        await mgr._save_plots("u1", plots)
        ok, msg = await mgr.harvest(player, None)
        assert ok, msg
        sr = mgr.storage_ring_manager
        got = {(n, c) for _, n, c in sr.stored}
        # 被偷保底：产量1 −1 → 保底 1
        assert ("恒心草", 1) in got, f"产量保底失效: {got}"
        assert ("凝血草", 3) in got
        # 收取后地块回空地
        plots2, farm = await load_plots(mgr, "u1")
        assert all(p["mode"] == "empty" for p in plots2)
        assert farm["garden_exp"] == 10  # 收取 +10
        await db.close()
    asyncio.run(run())


def test_harvest_no_mature():
    async def run():
        db, mgr, player = await make_setup(fields=1, garden_level=5)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # 刚种，生长中
        plots = [force_plot(mgr, db, player, 1, planted_at=now_str, growth_hours=12)]
        await mgr._save_plots("u1", plots)
        ok, msg = await mgr.harvest(player, None)
        assert not ok and "没有成熟" in msg
        await db.close()
    asyncio.run(run())


# ── 偷菜（v1.2：不接入因果）──

def test_steal_basic_and_limit():
    async def run():
        db, mgr, player = await make_setup(fields=2, garden_level=5)
        thief = make_player("u2", level_index=13, gold=10_000_000)
        await mgr.create_farm(thief)
        # 给失主一块成熟地
        now_str = (datetime.now() - timedelta(hours=13)).strftime("%Y-%m-%d %H:%M:%S")
        plots = [force_plot(mgr, db, player, 1, herb="凝血草", planted_at=now_str, growth_hours=12)]
        await mgr._save_plots("u1", plots)

        # 偷 3 次（上限）
        for i in range(3):
            ok, msg = await mgr.steal(thief, player)
            assert ok, msg
        # 第 4 次被拒
        ok, msg = await mgr.steal(thief, player)
        assert not ok and "次数已用完" in msg
        # 失主被偷计数 3
        _, tfarm = await load_plots(mgr, "u1")
        assert tfarm["steal_in_count"] == 3
        # 恩怨簿有记录
        grudge = json.loads(tfarm["grudge_log"])
        assert grudge and grudge[-1]["thief_id"] == "u2"
        # 因果零接触（v1.2 定案）
        assert player.karma == 0 and thief.karma == 0
        await db.close()
    asyncio.run(run())


def test_steal_victim_daily_cap():
    async def run():
        db, mgr, player = await make_setup(fields=2, garden_level=5)
        now_str = (datetime.now() - timedelta(hours=13)).strftime("%Y-%m-%d %H:%M:%S")
        plots = [force_plot(mgr, db, player, 1, herb="凝血草", planted_at=now_str, growth_hours=12)]
        await mgr._save_plots("u1", plots)
        # 直接把被偷计数拉满
        today = datetime.now().strftime("%Y-%m-%d")
        await mgr._update_farm("u1", steal_in_date=today, steal_in_count=5)
        thief = make_player("u2")
        await mgr.create_farm(thief)
        ok, msg = await mgr.steal(thief, player)
        assert not ok and "封闭" in msg
        await db.close()
    asyncio.run(run())


def test_steal_no_mature():
    async def run():
        db, mgr, player = await make_setup(fields=1, garden_level=5)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        plots = [force_plot(mgr, db, player, 1, planted_at=now_str, growth_hours=12)]  # 生长中
        await mgr._save_plots("u1", plots)
        thief = make_player("u2")
        await mgr.create_farm(thief)
        ok, msg = await mgr.steal(thief, player)
        assert not ok and "没有成熟" in msg
        await db.close()
    asyncio.run(run())


def test_steal_no_karma_change():
    async def run():
        db, mgr, player = await make_setup(fields=1, garden_level=5)
        player.karma = -300  # 预置因果
        now_str = (datetime.now() - timedelta(hours=13)).strftime("%Y-%m-%d %H:%M:%S")
        plots = [force_plot(mgr, db, player, 1, herb="凝血草", planted_at=now_str, growth_hours=12)]
        await mgr._save_plots("u1", plots)
        thief = make_player("u2")
        thief.karma = 200
        await mgr.create_farm(thief)
        await mgr.steal(thief, player)
        assert player.karma == -300 and thief.karma == 200, "偷菜不应改动因果（v1.2 定案）"
        await db.close()
    asyncio.run(run())


def test_steal_disabled_by_webui():
    async def run():
        db = FarmTestDB()
        await db.connect()
        cm = FakeConfigManager()
        mgr = SpiritFarmManager(db, cm, storage_ring_manager=FakeStorageRing(),
                                astrbot_config={"GARDEN": {"STEAL_ENABLED": False,
                                                           "STEAL_LIMIT_THIEF": 5,
                                                           "STEAL_FINE": 100000}})
        player = make_player("u1")
        thief = make_player("u2")
        await mgr.create_farm(player)
        await mgr.create_farm(thief)
        assert mgr.steal_enabled is False
        assert mgr.crops_cfg["steal_limit_thief"] == 5
        assert mgr.crops_cfg["steal_fine"] == 100000
        ok, msg = await mgr.steal(thief, player)
        assert not ok and "关闭" in msg
        await db.close()
    asyncio.run(run())


# ── 灵兽拦截 ──

def test_beast_catch_and_fine_split():
    async def run():
        db, mgr, player = await make_setup(fields=1, garden_level=5)
        player.karma = 0
        now_str = (datetime.now() - timedelta(hours=13)).strftime("%Y-%m-%d %H:%M:%S")
        plots = [force_plot(mgr, db, player, 1, herb="凝血草", planted_at=now_str, growth_hours=12)]
        await mgr._save_plots("u1", plots)
        # 失主养灵犬 Lv1
        await mgr._update_farm("u1", beast_level=1)
        thief = make_player("u2", gold=10_000_000)
        await mgr.create_farm(thief)

        import random as _r
        # 100% 拦截
        _r.random = lambda: 0.0
        thief_gold_before = thief.gold
        player_gold_before = player.gold
        ok, msg = await mgr.steal(thief, player)
        assert ok and "逮住" in msg
        assert thief.gold == thief_gold_before - 500000
        assert player.gold == player_gold_before + 250000, "失主应分得罚款 50%"
        # 因果零接触
        assert player.karma == 0 and thief.karma == 0
        await db.close()
    asyncio.run(run())


def test_beast_never_catches_at_zero_rate():
    async def run():
        db, mgr, player = await make_setup(fields=1, garden_level=5)
        now_str = (datetime.now() - timedelta(hours=13)).strftime("%Y-%m-%d %H:%M:%S")
        plots = [force_plot(mgr, db, player, 1, herb="凝血草", planted_at=now_str, growth_hours=12)]
        await mgr._save_plots("u1", plots)
        thief = make_player("u2")
        await mgr.create_farm(thief)
        import random as _r
        _r.random = lambda: 0.0  # 若拦截率>0 必拦；无兽应为 0% → 正常偷到
        ok, msg = await mgr.steal(thief, player)
        assert ok and "偷得" in msg
        await db.close()
    asyncio.run(run())


# ── 催熟计费 ──

def test_ripen_cost_floor_and_hours():
    async def run():
        db, mgr, player = await make_setup(fields=1, garden_level=5)
        # 剩余 1.5h（12h 作物种了 10.5h）→ ceil(1.5)=2h ×10万 = 20 万
        now_str = (datetime.now() - timedelta(hours=10.5)).strftime("%Y-%m-%d %H:%M:%S")
        plots = [force_plot(mgr, db, player, 1, planted_at=now_str, growth_hours=12)]
        await mgr._save_plots("u1", plots)
        ok, msg = await mgr.force_ripen(player)
        assert ok, msg
        assert "200,000" in msg
        # 收取可收
        ok, _ = await mgr.harvest(player, None)
        assert ok
        await db.close()
    asyncio.run(run())


def test_ripen_cost_min():
    async def run():
        db, mgr, player = await make_setup(fields=1, garden_level=5)
        # 剩余 0.2h → ceil=1h → 10万，但下限 15 万
        now_str = (datetime.now() - timedelta(hours=11.8)).strftime("%Y-%m-%d %H:%M:%S")
        plots = [force_plot(mgr, db, player, 1, planted_at=now_str, growth_hours=12)]
        await mgr._save_plots("u1", plots)
        ok, msg = await mgr.force_ripen(player)
        assert ok and "150,000" in msg
        await db.close()
    asyncio.run(run())


# ── 野生自动生长 ──

def test_empty_auto_wild_after_24h():
    async def run():
        db, mgr, player = await make_setup(fields=1, garden_level=5)
        # 收取后产生空地（planted_at=now）→ 未满 24h 不转化
        plots = [{"slot": 1, "mode": "empty", "planted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}]
        await mgr._save_plots("u1", plots)
        farm = await mgr.get_user_farm("u1")
        refreshed = mgr._refresh_plots(farm, player)
        assert refreshed[0]["mode"] == "empty"
        # 25h 前的空地 → 自动转野生
        plots[0]["planted_at"] = (datetime.now() - timedelta(hours=25)).strftime("%Y-%m-%d %H:%M:%S")
        await mgr._save_plots("u1", plots)
        farm = await mgr.get_user_farm("u1")
        refreshed = mgr._refresh_plots(farm, player)
        assert refreshed[0]["mode"] == "wild", "空地 24h 后应自动野生"
        assert refreshed[0]["growth_hours"] == 48
        await db.close()
    asyncio.run(run())


# ── 园圃等级 ──

def test_garden_level_up():
    async def run():
        db, mgr, player = await make_setup(fields=6, garden_level=1)
        # 播 6 块 ×5 exp = 30 → 仍 Lv1；再模拟到 200+
        await mgr.sow(player, "恒心草", "全部")
        _, farm = await load_plots(mgr, "u1")
        assert farm["garden_exp"] == 30 and farm["garden_level"] == 1
        await mgr._update_farm("u1", garden_exp=200)
        level = mgr._level_from_exp(200)
        assert level == 2
        level = mgr._level_from_exp(3000)
        assert level == 5
        await db.close()
    asyncio.run(run())


# ── 护园灵兽购买 ──

def test_beast_buy_and_upgrade():
    async def run():
        db, mgr, player = await make_setup()
        try:
            gold_base = player.gold  # create_farm 已扣 200 万开垦费
            ok, msg = await mgr.buy_or_upgrade_beast(player)
            assert ok and "灵犬 Lv.1" in msg
            assert player.gold == gold_base - 3_000_000
            ok, msg = await mgr.buy_or_upgrade_beast(player)
            assert ok and "守园鹤 Lv.2" in msg
            ok, msg = await mgr.buy_or_upgrade_beast(player)
            assert ok and "灵猿 Lv.3" in msg
            ok, msg = await mgr.buy_or_upgrade_beast(player)
            assert not ok and "最高等级" in msg
        finally:
            await db.close()
    asyncio.run(run())
