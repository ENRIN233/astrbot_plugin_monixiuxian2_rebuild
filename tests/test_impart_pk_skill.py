# -*- coding: utf-8 -*-
"""传承PK神通接入测试：challenge_impart 必须把双方装备的神通传进战斗引擎（与切磋/决斗同口径）"""
import asyncio
from types import SimpleNamespace

import pytest

from astrbot_plugin_monixiuxian2.managers.combat_manager import CombatManager, CombatStats
from astrbot_plugin_monixiuxian2.managers.impart_pk_manager import ImpartPkManager
from astrbot_plugin_monixiuxian2.managers.skill_manager import SkillManager


def _make_stats(user_id, name):
    return CombatStats(user_id=user_id, name=name, hp=1000, max_hp=1000,
                       mp=100, max_mp=100, atk=100)


class _FakeExt:
    async def get_impart_info(self, user_id):
        return None

    async def update_impart_info(self, info):
        pass


class _FakeDB:
    def __init__(self):
        self.ext = _FakeExt()

    async def update_player(self, player):
        pass


class _FakeCombatMgr:
    def __init__(self):
        self.captured_kwargs = None

    def player_vs_player(self, p1, p2, **kwargs):
        self.captured_kwargs = kwargs
        return {
            "winner": p1.user_id,
            "combat_log": ["回合日志"],
            "player1_final_hp": 1, "player1_final_mp": 1,
            "player2_final_hp": 1, "player2_final_mp": 1,
            "rounds": 1,
        }


class _FakeConfig:
    skills_data = {}


@pytest.fixture()
def patched_build(monkeypatch):
    """替换重装备查询的属性构建，聚焦神通传参逻辑"""
    async def fake_build(player, impart, config_manager):
        return _make_stats(player.user_id, player.name)
    monkeypatch.setattr(CombatManager, "build_player_combat_stats", fake_build)


def test_skill_manager_built_from_config():
    """config_manager 存在时构造 SkillManager，否则为 None"""
    mgr = ImpartPkManager(_FakeDB(), _FakeCombatMgr(), _FakeConfig())
    assert isinstance(mgr.skill_manager, SkillManager)

    mgr_none = ImpartPkManager(_FakeDB(), _FakeCombatMgr(), None)
    assert mgr_none.skill_manager is None


def test_challenge_impart_passes_both_skills(patched_build):
    """双方装备的神通名称应原样传入 player_vs_player"""
    fake_combat = _FakeCombatMgr()
    mgr = ImpartPkManager(_FakeDB(), fake_combat, _FakeConfig())
    attacker = SimpleNamespace(user_id="a", name="甲", shentong="三昧真火", experience=1000)
    defender = SimpleNamespace(user_id="b", name="乙", shentong="截脉", impart_atk_per=0.1)

    wins, log, rewards = asyncio.run(mgr.challenge_impart(attacker, defender))

    assert wins is True
    assert fake_combat.captured_kwargs["combat_type"] == 1
    assert fake_combat.captured_kwargs["p1_skill_name"] == "三昧真火"
    assert fake_combat.captured_kwargs["p2_skill_name"] == "截脉"
    assert isinstance(fake_combat.captured_kwargs["skill_manager"], SkillManager)


def test_challenge_impart_empty_shentong_is_safe(patched_build):
    """未装备神通（空串/缺失属性）时传空串，引擎按纯攻防处理"""
    fake_combat = _FakeCombatMgr()
    mgr = ImpartPkManager(_FakeDB(), fake_combat, _FakeConfig())
    attacker = SimpleNamespace(user_id="a", name="甲", shentong="", experience=1000)
    defender = SimpleNamespace(user_id="b", name="乙")  # 连 shentong 属性都没有

    asyncio.run(mgr.challenge_impart(attacker, defender))

    assert fake_combat.captured_kwargs["p1_skill_name"] == ""
    assert fake_combat.captured_kwargs["p2_skill_name"] == ""


def test_engine_accepts_impart_skills_end_to_end():
    """端到端冒烟：真实引擎 + 真实 SkillManager，传承PK口径的神通战斗可完整跑通"""
    skill_mgr = SkillManager(_FakeConfig())
    # _FakeConfig.skills_data 为空 → 神通不可用（get_skill_data 返回 None），应退化为普通攻击
    s1 = _make_stats("a", "甲")
    s2 = _make_stats("b", "乙")
    result = CombatManager.player_vs_player(
        s1, s2, combat_type=1,
        p1_skill_name="不存在的神通", p2_skill_name="",
        skill_manager=skill_mgr,
    )
    assert result["winner"] in ("a", "b", "平局")
    assert result["rounds"] >= 1
