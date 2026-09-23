# -*- coding: utf-8 -*-
"""闭关双源状态一致性自愈测试（修复假忙碌/假空闲）"""
import asyncio

from astrbot_plugin_monixiuxian2.models import Player
from astrbot_plugin_monixiuxian2.models_extended import UserStatus, UserCd
from astrbot_plugin_monixiuxian2.handlers.utils import _sync_cultivation_state


class FakeExt:
    """内存模拟 user_cd 存取"""

    def __init__(self, user_cd: UserCd = None, fail_get: bool = False):
        self.user_cd = user_cd
        self.fail_get = fail_get
        self.free_calls = 0
        self.busy_calls = []

    async def get_user_cd(self, user_id):
        if self.fail_get:
            raise RuntimeError("db error")
        return self.user_cd

    async def set_user_free(self, user_id):
        self.free_calls += 1
        self.user_cd = UserCd(user_id=user_id, type=UserStatus.IDLE)

    async def set_user_busy(self, user_id, busy_type, scheduled_time=0, extra_data=None, auto_commit=True):
        self.busy_calls.append(busy_type)
        self.user_cd = UserCd(user_id=user_id, type=busy_type)


class FakeDB:
    def __init__(self, ext):
        self.ext = ext


def make_player(state="空闲"):
    return Player(user_id="u1", user_name="t", state=state)


def run(ext, player):
    asyncio.run(_sync_cultivation_state(FakeDB(ext), player))


def test_stale_cd_cultivating_gets_cleared():
    """user_cd 残留闭关 + state 非修炼中 → 清除残留（用户报错现场）"""
    ext = FakeExt(UserCd(user_id="u1", type=UserStatus.CULTIVATING))
    player = make_player("空闲")
    run(ext, player)
    assert ext.free_calls == 1
    assert ext.user_cd.type == UserStatus.IDLE


def test_state_cultivating_without_cd_gets_patched():
    """state=修炼中 但 user_cd 缺失 → 补写 user_cd"""
    ext = FakeExt(None)
    player = make_player("修炼中")
    run(ext, player)
    assert ext.busy_calls == [UserStatus.CULTIVATING]
    assert ext.user_cd.type == UserStatus.CULTIVATING


def test_consistent_cultivating_untouched():
    """双源一致闭关 → 不做任何写操作"""
    ext = FakeExt(UserCd(user_id="u1", type=UserStatus.CULTIVATING))
    player = make_player("修炼中")
    run(ext, player)
    assert ext.free_calls == 0
    assert ext.busy_calls == []


def test_trading_state_not_touched():
    """交易状态（user_cd 权威）不被自愈误清"""
    ext = FakeExt(UserCd(user_id="u1", type=UserStatus.TRADING))
    player = make_player("空闲")
    run(ext, player)
    assert ext.free_calls == 0
    assert ext.busy_calls == []


def test_db_error_silent_pass():
    """get_user_cd 异常时静默通过，不阻塞指令"""
    ext = FakeExt(None, fail_get=True)
    player = make_player("空闲")
    run(ext, player)  # 不应抛异常
    assert ext.free_calls == 0
