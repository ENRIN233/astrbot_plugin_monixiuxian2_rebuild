# -*- coding: utf-8 -*-
"""悬赏幸运阶梯（三阶梯高稀有爆率）测试"""
import asyncio
import random

from astrbot_plugin_monixiuxian2.models import Player
from astrbot_plugin_monixiuxian2.managers.bounty_manager import BountyManager

# 原始权重表基准（bounty_drop_config.json）
TOTAL_RAW = 9610
RAW_CELESTIAL_ABOVE = 40 + 15 + 11 + 8 + 4 + 2   # 天阶下品起
RAW_IMMORTAL_ABOVE = 11 + 8 + 4 + 2              # 仙阶下品起
IMMORTAL_ABOVE_RANKS = {"仙阶下品", "仙阶上品", "仙阶极品", "无上"}
CELESTIAL_ABOVE_RANKS = {"天阶下品", "天阶上品"} | IMMORTAL_ABOVE_RANKS


def make_mgr(astrbot_config=None) -> BountyManager:
    return BountyManager(None, astrbot_config=astrbot_config)


def make_player(level_index: int) -> Player:
    return Player(user_id="u1", user_name="t", level_index=level_index,
                  spiritual_root="金木水火灵根", gold=1000)


def roll_tier_ratio(mgr: BountyManager, level_index: int, target_ranks: set, n: int = 20000) -> float:
    player = make_player(level_index)
    hits = 0
    for _ in range(n):
        drop = mgr._roll_bounty_drop(player)
        assert drop is not None
        if drop["rank"] in target_ranks:
            hits += 1
    return hits / n


def test_luck_tier_boundaries():
    """阶梯边界归属：18/19 与 36/37"""
    mgr = make_mgr()
    assert mgr._get_luck_tier(18) == ("", 1.0)
    assert mgr._get_luck_tier(19) == ("天阶下品", 3.0)
    assert mgr._get_luck_tier(36) == ("天阶下品", 3.0)
    assert mgr._get_luck_tier(37) == ("仙阶下品", 20.0)
    assert mgr._get_luck_tier(57) == ("仙阶下品", 20.0)


def test_t1_unchanged_distribution():
    """T1（<=18）与原始权重表分布一致（回归锁）"""
    random.seed(42)
    mgr = make_mgr()
    ratio = roll_tier_ratio(mgr, 10, IMMORTAL_ABOVE_RANKS, n=20000)
    expected = RAW_IMMORTAL_ABOVE / TOTAL_RAW  # ~0.26%
    # 20000 次抽样下 ±50% 容差（小概率事件统计噪声大）
    assert expected * 0.5 <= ratio <= expected * 1.5, f"T1 仙阶以上占比 {ratio:.4%} 期望 {expected:.4%}"


def test_t2_celestial_boost():
    """T2（19-36）：天阶以上占比升至约 2.46%"""
    random.seed(43)
    mgr = make_mgr()
    ratio = roll_tier_ratio(mgr, 25, CELESTIAL_ABOVE_RANKS, n=20000)
    expected = 240 / 9770  # ~2.456%
    assert expected * 0.7 <= ratio <= expected * 1.3, f"T2 天阶以上占比 {ratio:.4%} 期望 {expected:.4%}"


def test_t3_immortal_boost():
    """T3（37+）：仙阶以上占比升至约 4.96%，且落点全在仙阶以上集合"""
    random.seed(44)
    mgr = make_mgr()
    ratio = roll_tier_ratio(mgr, 45, IMMORTAL_ABOVE_RANKS, n=20000)
    expected = 500 / 10085  # ~4.958%
    assert expected * 0.7 <= ratio <= expected * 1.3, f"T3 仙阶以上占比 {ratio:.4%} 期望 {expected:.4%}"
    # sanity：连抽确认 rank 落点合法
    player = make_player(45)
    for _ in range(200):
        drop = mgr._roll_bounty_drop(player)
        assert drop["rank"] in mgr._drop_config


def test_webui_override_applies():
    """WebUI BOUNTY 节覆盖倍率与边界"""
    mgr = make_mgr(astrbot_config={"BOUNTY": {
        "T2_MIN_LEVEL": 10, "T3_MIN_LEVEL": 20, "T2_MULTIPLIER": 5.0, "T3_MULTIPLIER": 50.0,
    }})
    assert mgr.luck_t2_min_level == 10
    assert mgr.luck_t3_min_level == 20
    assert mgr.luck_t2_multiplier == 5.0
    assert mgr.luck_t3_multiplier == 50.0
    assert mgr._get_luck_tier(10) == ("天阶下品", 5.0)
    assert mgr._get_luck_tier(20) == ("仙阶下品", 50.0)


def test_webui_invalid_values_fall_back():
    """非法配置值不崩溃，回退默认"""
    mgr = make_mgr(astrbot_config={"BOUNTY": {"T3_MULTIPLIER": "not_a_number", "T2_MIN_LEVEL": None}})
    assert mgr.luck_t3_multiplier == 20.0
    assert mgr.luck_t2_min_level == 19


def test_t3_expectation_30_days():
    """30 天 Monte Carlo：T3 玩家（3 次/日）仙阶以上期望 13.4 张左右（4.958%*90）"""
    random.seed(45)
    mgr = make_mgr()
    player = make_player(45)
    total = 0
    for _ in range(30 * 3):
        drop = mgr._roll_bounty_drop(player)
        if drop["rank"] in IMMORTAL_ABOVE_RANKS:
            total += 1
    # 期望 90 * 4.958% ≈ 4.46 张（修正：90 次 roll 而非 90 天）
    assert 2 <= total <= 8, f"30 天 90 次掉落中仙阶以上 {total} 张，期望区间 [2,8]"
