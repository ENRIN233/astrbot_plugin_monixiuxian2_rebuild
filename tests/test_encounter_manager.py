# tests/test_encounter_manager.py
"""奇遇机缘系统测试 — 触发/结算/因果减半/修为占比/灵石乘链/超时"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from astrbot_plugin_monixiuxian2.models import Player
from astrbot_plugin_monixiuxian2.managers.encounter_manager import (
    EncounterManager, _level_bonus, _tier_key, TIER_HERBS,
)


# ── 测试替身 ──

class FakeDB:
    def __init__(self):
        self.updates = 0

    async def update_player(self, player):
        self.updates += 1


class FakeConfigManager:
    """最小配置管理器替身：直接加载真实 encounter_config.json"""

    def __init__(self, config_path=None):
        path = config_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config", "encounter_config.json",
        )
        with open(path, encoding="utf-8") as f:
            self.encounter_config = json.load(f)
        self.encounter_load_count = len(self.encounter_config.get("encounters", []))

    def get_closing_realm_mult(self, level_index):
        return 1.0 if level_index <= 18 else 2.0


class FakeStorageRing:
    def __init__(self):
        self.stored = []

    async def store_item(self, player, item_name, count=1, silent=False, **kwargs):
        self.stored.append((player.user_id, item_name, count))
        return True, "ok"


def make_player(level_index=5, gold=1000000, karma=0):
    return Player(
        user_id="test_user",
        user_name="测试修士",
        level_index=level_index,
        spiritual_root="金灵根",
        gold=gold,
        karma=karma,
    )


def make_manager(db=None, cfg=None):
    db = db or FakeDB()
    cm = cfg or FakeConfigManager()
    mgr = EncounterManager(db, cm, storage_ring_mgr=FakeStorageRing())
    return mgr, db, cm


# ── 配置加载 ──

def test_config_loads_62_events():
    mgr, _, cm = make_manager()
    assert cm.encounter_load_count == 62, f"应有62个事件，实际{cm.encounter_load_count}"
    assert len(mgr.encounters) == 62
    ids = [e["id"] for e in mgr.encounters]
    assert len(ids) == len(set(ids)), "事件ID不应重复"


# ── 段位与抽取 ──

def test_tier_key_mapping():
    assert _tier_key(0) == (0, 9)
    assert _tier_key(9) == (0, 9)
    assert _tier_key(10) == (10, 18)
    assert _tier_key(27) == (19, 27)
    assert _tier_key(28) == (28, 36)
    assert _tier_key(57) == (46, 57)


def test_select_encounter_respects_tier():
    mgr, _, _ = make_manager()
    for _ in range(50):
        enc = mgr._select_encounter(make_player(level_index=5))
        assert enc is not None
        assert enc["min_level"] <= 5 <= enc["max_level"], f"凡人段抽到 {enc['id']}"
    for _ in range(50):
        enc = mgr._select_encounter(make_player(level_index=30))
        assert enc["min_level"] <= 30 <= enc["max_level"]


def test_select_encounter_rarity_pool_valid():
    mgr, _, _ = make_manager()
    player = make_player(level_index=23)
    for _ in range(200):
        enc = mgr._select_encounter(player)
        assert enc["rarity"] in ("common", "rare", "epic", "legendary")


# ── 触发与每日限制 ──

def test_try_trigger_daily_limit():
    async def run():
        mgr, db, _ = make_manager()
        player = make_player()
        # 模拟今天已触发 3 次（日期与次数必须一致，否则会被新日重置）
        from datetime import datetime
        player.last_encounter_date = datetime.now().strftime("%Y-%m-%d")
        player.daily_encounter_count = 3
        result = await mgr.try_trigger(player, "check_in")
        assert result is None, "达到每日上限后不应触发"
    asyncio.run(run())


def test_try_trigger_respects_probability(monkeypatch=None):
    async def run():
        mgr, db, _ = make_manager()
        player = make_player()
        # 强制概率必中：把 trigger_chances 改为 1.0
        mgr.trigger_chances["check_in"] = 1.0
        msg = await mgr.try_trigger(player, "check_in")
        assert msg is not None and "奇遇" in msg
        assert player.daily_encounter_count == 1
        assert player.user_id in mgr._pending
    asyncio.run(run())


def test_try_trigger_zero_probability():
    async def run():
        mgr, db, _ = make_manager()
        player = make_player()
        mgr.trigger_chances["check_in"] = 0.0
        result = await mgr.try_trigger(player, "check_in")
        assert result is None
        assert player.daily_encounter_count == 0
    asyncio.run(run())


def test_pending_blocks_new_trigger():
    async def run():
        mgr, db, _ = make_manager()
        player = make_player()
        mgr.trigger_chances["check_in"] = 1.0
        await mgr.try_trigger(player, "check_in")
        msg2 = await mgr.try_trigger(player, "boss_fight")
        assert msg2 is None, "有待回复奇遇时不应触发新奇遇"
        assert player.daily_encounter_count == 1, "被阻止的触发不应消耗次数"
    asyncio.run(run())


# ── 因果结算（v3 规则：成败同向、失败减半）──

def _force_choice(mgr, player, encounter_id, choice_id):
    """直接构造 pending，绕过概率"""
    enc = next(e for e in mgr.encounters if e["id"] == encounter_id)
    mgr._pending[player.user_id] = {"encounter": enc, "timestamp": __import__("time").time()}
    return enc, next(c for c in enc["choices"] if c["id"] == choice_id)


def test_karma_success_full_delta():
    async def run():
        mgr, db, _ = make_manager()
        player = make_player(karma=0)
        enc, choice = _force_choice(mgr, player, "common_01", "a")  # -5, risk 0.30
        # mock 成功
        import random as _r
        _r.random = lambda: 0.99  # >= risk -> 成功
        result = await mgr.resolve(player, player.user_id, "a")
        assert player.karma == -5, f"成功应全额-5，实际{player.karma}"
        assert "因果：-5" in result
    asyncio.run(run())


def test_karma_fail_halved_negative():
    async def run():
        mgr, db, _ = make_manager()
        player = make_player(karma=0)
        _force_choice(mgr, player, "common_01", "a")  # delta -5
        import random as _r
        _r.random = lambda: 0.0  # < risk -> 失败
        result = await mgr.resolve(player, player.user_id, "a")
        assert player.karma == -3, f"失败应减半-3，实际{player.karma}"
        assert "因果：-3" in result
    asyncio.run(run())


def test_karma_fail_halved_positive():
    async def run():
        mgr, db, _ = make_manager()
        player = make_player(karma=0)
        # common_02 A 施舍 karma+8 risk 0 -> 必成功；改用 mid_04 A (+15, risk 0.25)
        _force_choice(mgr, player, "mid_04", "a")
        import random as _r
        _r.random = lambda: 0.0  # 失败
        await mgr.resolve(player, player.user_id, "a")
        assert player.karma == 8, f"善行失败应半额+8，实际{player.karma}"
    asyncio.run(run())


def test_karma_zero_delta_stays_zero():
    async def run():
        mgr, db, _ = make_manager()
        player = make_player(karma=0)
        _force_choice(mgr, player, "common_01", "b")  # delta 0
        import random as _r
        _r.random = lambda: 0.99
        await mgr.resolve(player, player.user_id, "b")
        assert player.karma == 0
    asyncio.run(run())


def test_karma_clamped():
    async def run():
        mgr, db, _ = make_manager()
        player = make_player(karma=-998)
        _force_choice(mgr, player, "common_01", "a")  # -5
        import random as _r
        _r.random = lambda: 0.99  # 成功 -5
        await mgr.resolve(player, player.user_id, "a")
        assert player.karma == -1000, "因果不应低于-1000"
    asyncio.run(run())


# ── 灵石乘链 ──

def test_gold_reward_chain():
    async def run():
        mgr, db, _ = make_manager()
        player = make_player(level_index=5, gold=0)  # 凡人 level_bonus = 1.09
        _force_choice(mgr, player, "common_01", "b")  # B 绕过: gold_center 5000, risk 0
        import random as _r
        _r.random = lambda: 0.99
        _r.uniform = lambda a, b: 1.0  # 区间取上界，便于计算
        await mgr.resolve(player, player.user_id, "b")
        expected = int(5000 * 1.0 * _level_bonus(5) * 1.0)
        assert player.gold == expected, f"灵石应={expected}，实际{player.gold}"
    asyncio.run(run())


def test_gold_scale_knob():
    async def run():
        mgr, db, _ = make_manager()
        mgr.settings["gold_scale"] = 0.5
        player = make_player(level_index=5, gold=0)
        _force_choice(mgr, player, "common_01", "b")
        import random as _r
        _r.random = lambda: 0.99
        _r.uniform = lambda a, b: 1.0
        await mgr.resolve(player, player.user_id, "b")
        expected = int(5000 * _level_bonus(5) * 0.5)
        assert player.gold == expected, f"gold_scale 0.5 应生效，实际{player.gold}"
    asyncio.run(run())


# ── 修为占比锁定 ──

def test_daily_exp_base_bare_player():
    mgr, _, cm = make_manager()
    # idx<=18: 86400（无 cultivation_manager，realm_mult=1.0）
    p = make_player(level_index=5)
    assert mgr.get_daily_exp_base(p) == 86400.0
    # idx=23: 86400 × realm_mult(23)=2.0（fake 配置）
    p2 = make_player(level_index=23)
    assert mgr.get_daily_exp_base(p2) == 86400.0 * 2.0


def test_exp_reward_ratio_and_clamp():
    async def run():
        mgr, db, _ = make_manager()
        player = make_player(level_index=23, gold=0)  # 元婴段，fake realm_mult=2.0
        d = mgr.get_daily_exp_base(player)  # 86400*2 = 172800
        # high_11 A（传说 48.1%）：48.1% × 1.5 = 72.15% > 50% → 触发 clamp
        before = player.experience
        _force_choice(mgr, player, "high_11", "a")
        import random as _r
        _r.random = lambda: 0.99  # 成功
        _r.uniform = lambda a, b: 1.5  # 区间上界 -> 应触发 clamp
        await mgr.resolve(player, player.user_id, "a")
        gained = player.experience - before
        assert gained == int(d * 0.5), f"clamp 50% 应生效: {gained} vs {int(d*0.5)}"
    asyncio.run(run())


def test_exp_reward_no_clamp_normal():
    async def run():
        mgr, db, _ = make_manager()
        player = make_player(level_index=5, gold=0)
        d = mgr.get_daily_exp_base(player)
        _force_choice(mgr, player, "common_01", "b")  # exp_pct 1.7
        import random as _r
        _r.random = lambda: 0.99
        _r.uniform = lambda a, b: 1.0
        before = player.experience
        await mgr.resolve(player, player.user_id, "b")
        gained = player.experience - before
        assert gained == int(d * 0.017 * 1.0), f"修为应=D×1.7%={int(d*0.017)}，实际{gained}"
    asyncio.run(run())


# ── 超时与消耗 ──

def test_resolve_timeout_refunds_daily_count():
    async def run():
        mgr, db, _ = make_manager()
        player = make_player()
        mgr.trigger_chances["check_in"] = 1.0
        await mgr.try_trigger(player, "check_in")
        assert player.daily_encounter_count == 1
        # 伪造超时
        mgr._pending[player.user_id]["timestamp"] -= 9999
        result = await mgr.resolve(player, player.user_id, "a")
        assert "超时" in result
        assert player.daily_encounter_count == 0, "超时应回退今日次数"
    asyncio.run(run())


def test_cost_insufficient_keeps_pending():
    async def run():
        mgr, db, _ = make_manager()
        player = make_player(level_index=5, gold=100)
        _force_choice(mgr, player, "common_01", "c")  # 消耗 5000
        import random as _r
        _r.random = lambda: 0.99
        result = await mgr.resolve(player, player.user_id, "c")
        assert "灵石不足" in result
        assert player.user_id in mgr._pending, "灵石不足应放回 pending 供改选"
        assert player.gold == 100
    asyncio.run(run())


def test_cost_deducted_on_success():
    async def run():
        mgr, db, _ = make_manager()
        player = make_player(level_index=5, gold=100000)
        _force_choice(mgr, player, "common_01", "c")  # 消耗 5000, gold_center 8000
        import random as _r
        _r.random = lambda: 0.99
        _r.uniform = lambda a, b: 1.0
        await mgr.resolve(player, player.user_id, "c")
        expected_gold = 100000 - 5000 + int(8000 * _level_bonus(5))
        assert player.gold == expected_gold, f"应扣除5000并发奖励，实际{player.gold}"
    asyncio.run(run())


# ── 物品池解析 ──

def test_pool_resolution_by_tier():
    async def run():
        mgr, db, _ = make_manager()
        player = make_player(level_index=23)  # 元婴段
        _force_choice(mgr, player, "high_07", "a")  # item_chance 0.7, @herbs
        import random as _r
        _r.random = lambda: 0.5  # 成功；item_chance 掷 0.5 < 0.7 命中
        _r.uniform = lambda a, b: 1.0
        # random.choice 由池内随机——只要 store_item 收到的名字在元婴药材池即可
        await mgr.resolve(player, player.user_id, "a")
        sr = mgr.storage_ring_mgr
        if sr.stored:
            _, item_name, _ = sr.stored[-1]
            valid = set(TIER_HERBS[(19, 27)])
            assert item_name in valid, f"元婴段应掉元婴药材，实际{item_name}"
    asyncio.run(run())


# ── 因果称号与衰减 ──

def test_karma_title():
    mgr, _, _ = make_manager()
    assert mgr.get_karma_title(0) == "中立"
    assert mgr.get_karma_title(-500) == "魔道修士"
    assert mgr.get_karma_title(-100) == "偏邪"
    assert mgr.get_karma_title(100) == "偏正"
    assert mgr.get_karma_title(500) == "正道修士"


def test_karma_decay_toward_zero():
    async def run():
        mgr, db, _ = make_manager()
        p1 = make_player(karma=-501)
        await mgr.apply_karma_decay(p1)
        assert p1.karma == -499
        p2 = make_player(karma=501)
        await mgr.apply_karma_decay(p2)
        assert p2.karma == 499
        p3 = make_player(karma=1)
        await mgr.apply_karma_decay(p3)
        assert p3.karma == 0, "衰减不应越过0"
    asyncio.run(run())


# ── WebUI 配置覆盖（_conf_schema.json ENCOUNTER 节）──

def test_webui_overrides_settings():
    async def run():
        webui = {"ENCOUNTER": {
            "ENABLED": True,
            "DAILY_LIMIT": 5,
            "CHOICE_TIMEOUT_SECONDS": 300,
            "EXP_RATIO": 0.10,
            "GOLD_SCALE": 0.8,
            "LEGENDARY_BROADCAST": False,
            "KARMA_DAILY_DECAY": 5,
            "TRIGGER_CHECK_IN": 0.5,
            "TRIGGER_FARM_SOW": 0.01,
        }}
        mgr, db, _ = make_manager()
        mgr._apply_webui_overrides(webui)
        assert mgr.settings["daily_limit"] == 5
        assert mgr.settings["choice_timeout_seconds"] == 300
        assert mgr.settings["exp_ratio"] == 0.10
        assert mgr.settings["gold_scale"] == 0.8
        assert mgr.settings["legendary_broadcast"] is False
        assert mgr.karma_settings["daily_decay"] == 5
        assert mgr.trigger_chances["check_in"] == 0.5
        assert mgr.trigger_chances["farm_sow"] == 0.01
    asyncio.run(run())


def test_enabled_false_blocks_trigger():
    async def run():
        mgr, db, _ = make_manager()
        mgr.enabled = False
        mgr.trigger_chances["check_in"] = 1.0
        player = make_player()
        result = await mgr.try_trigger(player, "check_in")
        assert result is None, "总开关关闭后不应触发奇遇"
        assert player.daily_encounter_count == 0
    asyncio.run(run())


# ── 端到端冒烟 ──

def test_end_to_end_flow():
    async def run():
        mgr, db, _ = make_manager()
        player = make_player(level_index=23, gold=500000)
        mgr.trigger_chances["rift_complete"] = 1.0
        msg = await mgr.try_trigger(player, "rift_complete")
        assert msg and "奇遇·" in msg
        # 回复一个合法选项
        import random as _r
        _r.random = lambda: 0.99
        result = await mgr.resolve(player, player.user_id, "a")
        assert ("✨" in result) or ("💀" in result)
        assert "☯️ 因果：" in result
        history = json.loads(player.encounter_history)
        assert len(history) == 1
        assert history[0]["rarity"] in ("common", "rare", "epic", "legendary")
    asyncio.run(run())


def test_history_capped_at_20():
    async def run():
        mgr, db, _ = make_manager()
        player = make_player(level_index=5, gold=9999999)
        for i in range(25):
            enc = next(e for e in mgr.encounters if e["id"] == "common_01")
            mgr._pending[player.user_id] = {"encounter": enc, "timestamp": __import__("time").time()}
            import random as _r
            _r.random = lambda: 0.99
            await mgr.resolve(player, player.user_id, "b")
        history = json.loads(player.encounter_history)
        assert len(history) <= 20, "历史最多保留20条"
    asyncio.run(run())
