# -*- coding: utf-8 -*-
"""Item 模型防具战斗属性回归测试（修复 Item.__init__() unexpected def_buff）"""
from astrbot_plugin_monixiuxian2.models import Item
from astrbot_plugin_monixiuxian2.core.equipment_manager import EquipmentManager

# 带 6 个防具战斗属性的物品配置（用户报错现场：parse_item_from_name 构造 Item 时传 def_buff）
ARMOR_CONFIG = {
    "玄龟甲": {
        "id": "armor_001",
        "type": "armor",
        "description": "玄龟壳炼制的护甲",
        "rank": "灵品",
        "def_buff": 0.08,
        "dodge_rate": 5,
        "crit_resist": 10,
        "reflect_pct": 3,
        "block_value": 6,
        "hp_regen_pct": 0.02,
    }
}


def test_item_accepts_defense_attributes():
    """Item 构造接受全部防具战斗属性（不再 TypeError）"""
    item = Item(
        item_id="armor_001", name="玄龟甲", item_type="armor",
        def_buff=0.08, dodge_rate=5, crit_resist=10,
        reflect_pct=3, block_value=6, hp_regen_pct=0.02,
    )
    assert item.def_buff == 0.08
    assert item.dodge_rate == 5
    assert item.crit_resist == 10
    assert item.reflect_pct == 3
    assert item.block_value == 6
    assert item.hp_regen_pct == 0.02


def test_item_defaults_unchanged():
    """既有字段默认值不变（回归锁）"""
    item = Item(item_id="w1", name="铁剑", item_type="weapon")
    assert item.def_buff == 0.0
    assert item.dodge_rate == 0
    assert item.crit_resist == 0
    assert item.reflect_pct == 0
    assert item.block_value == 0
    assert item.hp_regen_pct == 0.0
    assert item.armor_pen == 0
    assert item.lifesteal == 0
    assert item.double_hit == 0


def test_parse_item_from_name_with_defense_attrs():
    """parse_item_from_name 构造带防具属性的物品不再炸（用户报错现场复现）"""
    mgr = EquipmentManager(None, None)
    item = mgr.parse_item_from_name("玄龟甲", ARMOR_CONFIG)
    assert item is not None
    assert item.item_type == "armor"
    assert item.def_buff == 0.08
    assert item.hp_regen_pct == 0.02


def test_display_shows_defense_attrs():
    """属性展示包含防具战斗属性"""
    item = Item(
        item_id="armor_001", name="玄龟甲", item_type="armor",
        def_buff=0.08, dodge_rate=5, hp_regen_pct=0.02,
    )
    text = item.get_attribute_display()
    assert "减伤+8%" in text
    assert "闪避+5%" in text
    assert "回血+2%/回合" in text
