# -*- coding: utf-8 -*-
"""重铸灵根数量参数（多抽生效最稀有）测试"""
import asyncio
import types

from astrbot_plugin_monixiuxian2.models import Player
from astrbot_plugin_monixiuxian2.handlers.player_handler import (
    PlayerHandler, REROLL_ROOT_COST, REROLL_ROOT_MAX_COUNT,
)
from astrbot_plugin_monixiuxian2.core.cultivation_manager import CultivationManager


class FakeDB:
    def __init__(self):
        self.updated = 0

    async def update_player(self, p):
        self.updated += 1


class FakeCM:
    """可控抽取序列 + 固定稀有度表"""

    def __init__(self, sequence):
        self.sequence = list(sequence)
        self.speeds = {
            "伪": 0.0,
            "金木水火": 1.0,
            "天": 1.3,
            "龙": 1.4,
            "混沌": 2.0,
        }

    def _get_random_spiritual_root(self):
        return self.sequence.pop(0) if self.sequence else "金木水火"

    def get_root_speed_by_name(self, name):
        return self.speeds.get(name, 1.0)

    def _get_root_description(self, name):
        return f"desc:{name}"


class FakeEvent:
    def __init__(self):
        self.outputs = []

    def plain_result(self, text):
        self.outputs.append(text)
        return text


def make_player(gold=10_000_000):
    return Player(user_id="u1", user_name="测试", spiritual_root="金木水火灵根", gold=gold)


async def collect(handler_func, fake_self, player, event, count):
    gen = handler_func(fake_self, player, event, count)
    async for _ in gen:
        pass
    return event.outputs


def test_single_draw_unchanged():
    """单抽（不传数量）保持原输出格式"""
    async def run():
        cm = FakeCM(["天"])
        fake_self = types.SimpleNamespace(db=FakeDB(), cultivation_manager=cm)
        player = make_player()
        outs = await collect(PlayerHandler.handle_reroll_root.__wrapped__, fake_self, player, FakeEvent(), "1")
        assert len(outs) == 1
        assert "重铸灵根成功" in outs[0]
        assert "新灵根：天灵根（desc:天）" in outs[0]
        assert f"消耗灵石：{REROLL_ROOT_COST:,}" in outs[0]
        assert player.spiritual_root == "天灵根"
        assert player.gold == 10_000_000 - REROLL_ROOT_COST
    asyncio.run(run())


def test_multi_draw_takes_rarest():
    """多抽：10 次里生效速度倍率最高的灵根，消耗为总额"""
    async def run():
        seq = ["金木水火", "金木水火", "天", "金木水火", "龙", "天", "金木水火", "混沌", "天", "龙"]
        cm = FakeCM(seq)
        fake_self = types.SimpleNamespace(db=FakeDB(), cultivation_manager=cm)
        player = make_player()
        outs = await collect(PlayerHandler.handle_reroll_root.__wrapped__, fake_self, player, FakeEvent(), "10")
        assert len(outs) == 1
        text = outs[0]
        assert f"重铸灵根 ×10" in text
        assert "生效灵根：混沌灵根" in text, f"应生效最稀有的混沌灵根：{text}"
        assert player.spiritual_root == "混沌灵根"
        assert player.gold == 10_000_000 - REROLL_ROOT_COST * 10
        assert "抽取结果：" in text
        # 聚合统计行按稀有度降序：混沌在最前
        stat = text.split("抽取结果：")[1].split("\n")[0]
        assert stat.startswith("混沌灵根×1"), f"统计应按稀有度降序：{stat}"
    asyncio.run(run())


def test_count_capped_at_max():
    """数量超上限自动截断为 10 次"""
    async def run():
        cm = FakeCM(["伪"] * 50)
        fake_self = types.SimpleNamespace(db=FakeDB(), cultivation_manager=cm)
        player = make_player()
        outs = await collect(PlayerHandler.handle_reroll_root.__wrapped__, fake_self, player, FakeEvent(), "99")
        assert "最多连抽 10 次" in outs[0]
        assert player.gold == 10_000_000 - REROLL_ROOT_COST * REROLL_ROOT_MAX_COUNT
    asyncio.run(run())


def test_invalid_count_no_charge():
    """非数字参数：提示且不扣灵石"""
    async def run():
        cm = FakeCM(["天"])
        fake_self = types.SimpleNamespace(db=FakeDB(), cultivation_manager=cm)
        player = make_player()
        outs = await collect(PlayerHandler.handle_reroll_root.__wrapped__, fake_self, player, FakeEvent(), "abc")
        assert "数量参数无效" in outs[0]
        assert player.gold == 10_000_000
        assert player.spiritual_root == "金木水火灵根"
    asyncio.run(run())


def test_insufficient_gold_shows_total():
    """灵石不足：提示按次数的总额，不扣款"""
    async def run():
        cm = FakeCM(["天"] * 5)
        fake_self = types.SimpleNamespace(db=FakeDB(), cultivation_manager=cm)
        player = make_player(gold=300_000)
        outs = await collect(PlayerHandler.handle_reroll_root.__wrapped__, fake_self, player, FakeEvent(), "5")
        assert f"共需 {REROLL_ROOT_COST * 5:,}" in outs[0]
        assert player.gold == 300_000
    asyncio.run(run())


def test_zero_count_treated_as_one():
    """数量 0/负数按 1 次处理"""
    async def run():
        cm = FakeCM(["天"])
        fake_self = types.SimpleNamespace(db=FakeDB(), cultivation_manager=cm)
        player = make_player()
        outs = await collect(PlayerHandler.handle_reroll_root.__wrapped__, fake_self, player, FakeEvent(), "0")
        assert "重铸灵根成功" in outs[0]
        assert player.gold == 10_000_000 - REROLL_ROOT_COST
    asyncio.run(run())


def test_get_root_speed_by_name_real_cm():
    """真实 CultivationManager：按名查速度（含未知名字兜底）"""
    config = {"SPIRIT_ROOT_SPEEDS": {"TRUE_ROOT_SPEED": 1.0, "HEAVENLY_ROOT_SPEED": 1.3, "CHAOS_ROOT_SPEED": 2.0}}
    cm = CultivationManager(config, None)
    assert cm.get_root_speed_by_name("天金") == 1.3
    assert cm.get_root_speed_by_name("混沌") == 2.0
    assert cm.get_root_speed_by_name("金木水火") == 1.0
    assert cm.get_root_speed_by_name("不存在的根") == 1.0  # 兜底
