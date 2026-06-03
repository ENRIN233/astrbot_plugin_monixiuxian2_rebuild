import sys
import types
from pathlib import Path

import pytest

# handlers/__init__.py 会 eager 导入全部 handler，其中 storage_ring_handler
# 依赖测试环境未 stub 的 astrbot.api.all。这里把 handlers 预注册为命名空间包，
# 跳过那条重型 __init__，直接导入纯逻辑模块（gambling_handler 仅依赖已 stub 的 astrbot.api.event）。
_HANDLERS_PKG = "astrbot_plugin_monixiuxian2.handlers"
if _HANDLERS_PKG not in sys.modules:
    _h = types.ModuleType(_HANDLERS_PKG)
    _h.__path__ = [str(Path(__file__).resolve().parent.parent / "handlers")]
    sys.modules[_HANDLERS_PKG] = _h

from astrbot_plugin_monixiuxian2.handlers.gambling_handler import resolve_bet


# 大：骰点 >= 4 胜，1 倍
@pytest.mark.parametrize("roll,expected_win", [
    (1, False), (2, False), (3, False), (4, True), (5, True), (6, True),
])
def test_big(roll, expected_win):
    won, mult = resolve_bet(roll, "大", 0)
    assert won is expected_win
    assert mult == (1 if expected_win else 0)


# 小：骰点 <= 3 胜，1 倍
@pytest.mark.parametrize("roll,expected_win", [
    (1, True), (2, True), (3, True), (4, False), (5, False), (6, False),
])
def test_small(roll, expected_win):
    won, mult = resolve_bet(roll, "小", 0)
    assert won is expected_win
    assert mult == (1 if expected_win else 0)


# 奇：单数(1/3/5) 胜，1 倍
@pytest.mark.parametrize("roll,expected_win", [
    (1, True), (2, False), (3, True), (4, False), (5, True), (6, False),
])
def test_odd(roll, expected_win):
    won, mult = resolve_bet(roll, "奇", 0)
    assert won is expected_win
    assert mult == (1 if expected_win else 0)


# 偶：双数(2/4/6) 胜，1 倍
@pytest.mark.parametrize("roll,expected_win", [
    (1, False), (2, True), (3, False), (4, True), (5, False), (6, True),
])
def test_even(roll, expected_win):
    won, mult = resolve_bet(roll, "偶", 0)
    assert won is expected_win
    assert mult == (1 if expected_win else 0)


# 猜：骰点 == 猜测点数 胜，5 倍
@pytest.mark.parametrize("roll", [1, 2, 3, 4, 5, 6])
def test_guess_hit(roll):
    won, mult = resolve_bet(roll, "猜", roll)
    assert won is True
    assert mult == 5


@pytest.mark.parametrize("roll,guess", [
    (1, 2), (3, 4), (6, 1), (5, 6),
])
def test_guess_miss(roll, guess):
    won, mult = resolve_bet(roll, "猜", guess)
    assert won is False
    assert mult == 0


# 非法模式：判负
def test_invalid_mode():
    won, mult = resolve_bet(4, "x", 0)
    assert won is False
    assert mult == 0
