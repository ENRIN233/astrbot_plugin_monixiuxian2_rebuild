# models.py

from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional
import json

if TYPE_CHECKING:
    from .config_manager import ConfigManager

@dataclass
class Item:
    """装备物品模型"""

    item_id: str  # 物品唯一ID
    name: str  # 物品名称
    item_type: str  # 装备类型：weapon（武器）、armor（防具）、main_technique（主修心法）
    description: str = ""  # 物品描述

    # 装备品级相关
    rank: str = ""  # 品级：凡品、灵品、地品、天品、皇品、帝品、道品、仙品、混元先天
    required_level_index: int = 0  # 需要的最低境界level_index
    weapon_category: str = ""  # 武器类别：剑、刀、阔刀、琴、匕首、符箓、鼎、棍、枪、笔

    # 装备属性加成
    magic_damage: int = 0  # 法伤加成
    physical_damage: int = 0  # 物伤加成
    magic_defense: int = 0  # 法防加成
    physical_defense: int = 0  # 物防加成
    mental_power: int = 0  # 精神力加成

    # 心法专属属性
    exp_multiplier: float = 0.0  # 修为倍率加成（仅心法有效）
    breakthrough_bonus: float = 0.0  # 突破成功率加成（如 0.02 = +2%）
    atk_bonus: float = 0.0  # 攻击力百分比加成（如 0.3 = +30%）
    hp_bonus: float = 0.0  # 生命值百分比加成（如 0.05 = +5%）
    mp_bonus: float = 0.0  # 真元百分比加成（如 0.05 = +5%）
    crit_rate: int = 0  # 暴击率加成（百分比整数，如 10 = +10%）
    crit_damage: float = 0.0  # 暴击伤害加成（如 0.5 = 暴击倍率+0.5）
    mp_bonus: float = 0.0  # 真元百分比加成（武器有效，如 0.3 = +30%）

    def get_attribute_display(self) -> str:
        """获取属性加成的显示文本"""
        attrs = []
        if self.magic_damage > 0:
            attrs.append(f"法伤+{self.magic_damage}")
        if self.physical_damage > 0:
            attrs.append(f"物伤+{self.physical_damage}")
        if self.magic_defense > 0:
            attrs.append(f"法防+{self.magic_defense}")
        if self.physical_defense > 0:
            attrs.append(f"物防+{self.physical_defense}")
        if self.mental_power > 0:
            attrs.append(f"精神力+{self.mental_power}")
        if self.exp_multiplier > 0:
            attrs.append(f"修为倍率+{self.exp_multiplier:.1%}")
        if self.breakthrough_bonus > 0:
            attrs.append(f"突破成功率+{self.breakthrough_bonus:.1%}")
        if self.atk_bonus > 0:
            attrs.append(f"攻击力+{self.atk_bonus:.0%}")
        if self.hp_bonus > 0:
            attrs.append(f"生命值+{self.hp_bonus:.1%}")
        if self.mp_bonus > 0:
            attrs.append(f"真元+{self.mp_bonus:.1%}")
        if self.crit_rate > 0:
            attrs.append(f"暴击率+{self.crit_rate}%")
        if self.crit_damage > 0:
            attrs.append(f"暴击伤害+{self.crit_damage:.0%}")
        if self.mp_bonus > 0:
            attrs.append(f"真元+{self.mp_bonus:.0%}")
        return "、".join(attrs) if attrs else "无属性加成"

@dataclass
class Player:
    """玩家数据模型 - 完整修仙系统（参照NoneBot2）"""

    user_id: str
    level_index: int = 0
    spiritual_root: str = "未知"
    cultivation_type: str = "灵修"  # 灵修或体修
    user_name: str = ""  # 道号

    # 基础属性
    lifespan: int = 100  # 寿命
    experience: int = 0  # 修为
    gold: int = 0  # 灵石
    state: str = "空闲"
    cultivation_start_time: int = 0  # 闭关开始时间（Unix时间戳，0表示未闭关）
    last_check_in_date: str = ""  # 最后签到日期（格式：YYYY-MM-DD，空字符串表示从未签到）
    monthly_sign_count: int = 0  # 本月累计签到天数
    monthly_sign_month: str = ""  # 累计所属月份（格式：YYYY-MM）

    # 每日活跃度系统
    daily_activity: str = "{}"  # JSON: {"task_id": count}
    daily_activity_points: int = 0  # 当日活跃值（达到100后不再增加）
    daily_activity_date: str = ""  # 活跃度记录日期（YYYY-MM-DD）
    daily_activity_rewarded: int = 0  # 当日是否已领取奖励（0/1）
    level_up_rate: int = 0  # 突破成功率加成

    # 装备栏
    weapon: str = ""  # 武器
    armor: str = ""  # 防具
    main_technique: str = ""  # 主修心法
    techniques: str = "[]"  # 功法列表（JSON字符串，最多3个）
    shentong: str = ""  # 神通（装备的技能名称，单个）

    # 战斗属性（HP/MP/ATK系统）
    hp: int = 0  # 当前气血值
    mp: int = 0  # 当前真元值
    atk: int = 0  # 攻击力
    atkpractice: int = 0  # 攻击修炼等级，每级提升4%攻击力

    # 灵修/体修专用属性
    spiritual_qi: int = 100  # 当前灵气（灵修专用）
    max_spiritual_qi: int = 1000  # 最大灵气容量（灵修专用）
    blood_qi: int = 0  # 当前气血（体修专用）
    max_blood_qi: int = 0  # 最大气血容量（体修专用）
    magic_damage: int = 10  # 法伤
    physical_damage: int = 10  # 物伤
    magic_defense: int = 5  # 法防
    physical_defense: int = 5  # 物防
    mental_power: int = 100  # 精神力

    # 宗门系统字段
    sect_id: int = 0  # 宗门ID（0表示未加入宗门）
    sect_position: int = 4  # 宗门职位：0宗主、1长老、2亲传、3内门、4外门
    sect_contribution: int = 0  # 宗门贡献度
    sect_task: int = 0  # 宗门任务完成次数
    sect_elixir_get: int = 0  # 宗门丹药领取标记（0未领取，1已领取）

    # 洞天福地系统
    blessed_spot_flag: int = 0  # 是否开启洞天福地（0未开启，1已开启）
    blessed_spot_name: str = ""  # 洞天福地名称

    # 丹药系统字段
    active_pill_effects: str = "[]"  # 当前生效的临时丹药效果（JSON字符串）
    permanent_pill_gains: str = "{}"  # 永久丹药累积增益（JSON字符串）
    has_resurrection_pill: str = ""  # 回生丹类型（空字符串=无，"回生丹"=损失15%属性，"涅槃重生丹"=无损失）
    has_debuff_shield: bool = False  # 是否拥有一次负面效果免疫
    pills_inventory: str = "{}"  # 丹药背包（JSON字符串，格式：{pill_id: count}）
    permanent_pill_usage: str = "{}"  # 永久丹药使用次数（JSON字符串，格式：{pill_name: count}）

    # 储物戒系统字段
    storage_ring: str = "基础储物戒"  # 当前装备的储物戒名称
    storage_ring_items: str = "{}"  # 储物戒中的物品（JSON字符串，格式：{item_name: {count, bound}}）

    # Phase 1: 每日限制系统
    daily_pill_usage: str = "{}"  # 每日丹药使用次数（JSON字符串，格式：{pill_id: count}）
    last_daily_reset: str = ""  # 上次每日重置日期（格式：YYYY-MM-DD）

    # 成就系统字段
    achievement_data: str = '{"unlocked": {}, "equipped": ""}'  # 成就数据（JSON字符串）

    # 银行会员系统
    bank_vip_tier: int = 0  # 银行VIP等级（0初级 1中级 2高级 3顶级 4至尊）

    def get_level(self, config_manager: "ConfigManager") -> str:
        """获取境界名称"""
        level_data = config_manager.get_level_data(self.cultivation_type)
        if 0 <= self.level_index < len(level_data):
            return level_data[self.level_index]["level_name"]
        return "未知境界"

    def get_required_exp(self, config_manager: "ConfigManager") -> int:
        """获取突破到下一境界所需的总修为"""
        level_data = config_manager.get_level_data(self.cultivation_type)
        if self.level_index + 1 < len(level_data):
            return level_data[self.level_index + 1].get("exp_needed", 0)
        return 0

    def get_techniques_list(self) -> List[str]:
        """获取功法列表"""
        try:
            return json.loads(self.techniques)
        except json.JSONDecodeError:
            return []

    def set_techniques_list(self, techniques_list: List[str]):
        """设置功法列表"""
        self.techniques = json.dumps(techniques_list, ensure_ascii=False)

    def get_active_pill_effects(self) -> List[dict]:
        """获取当前生效的临时丹药效果列表"""
        try:
            return json.loads(self.active_pill_effects)
        except json.JSONDecodeError:
            return []

    def set_active_pill_effects(self, effects: List[dict]):
        """设置当前生效的临时丹药效果"""
        self.active_pill_effects = json.dumps(effects, ensure_ascii=False)

    def get_permanent_pill_gains(self) -> dict:
        """获取永久丹药累积增益"""
        try:
            return json.loads(self.permanent_pill_gains)
        except json.JSONDecodeError:
            return {}

    def set_permanent_pill_gains(self, gains: dict):
        """设置永久丹药累积增益"""
        self.permanent_pill_gains = json.dumps(gains, ensure_ascii=False)

    def get_pills_inventory(self) -> dict:
        """获取丹药背包"""
        try:
            return json.loads(self.pills_inventory)
        except json.JSONDecodeError:
            return {}

    def set_pills_inventory(self, inventory: dict):
        """设置丹药背包"""
        self.pills_inventory = json.dumps(inventory, ensure_ascii=False)

    def get_permanent_pill_usage(self) -> dict:
        """获取永久丹药使用次数"""
        try:
            return json.loads(self.permanent_pill_usage)
        except json.JSONDecodeError:
            return {}

    def set_permanent_pill_usage(self, usage: dict):
        """设置永久丹药使用次数"""
        self.permanent_pill_usage = json.dumps(usage, ensure_ascii=False)

    def get_daily_pill_usage(self) -> dict:
        """获取每日丹药使用次数"""
        try:
            return json.loads(self.daily_pill_usage)
        except json.JSONDecodeError:
            return {}

    def set_daily_pill_usage(self, usage: dict):
        """设置每日丹药使用次数"""
        self.daily_pill_usage = json.dumps(usage, ensure_ascii=False)

    def get_storage_ring_items(self) -> dict:
        """获取储物戒物品"""
        try:
            return json.loads(self.storage_ring_items)
        except json.JSONDecodeError:
            return {}

    def set_storage_ring_items(self, items: dict):
        """设置储物戒物品"""
        self.storage_ring_items = json.dumps(items, ensure_ascii=False)

    def get_achievement_data(self) -> dict:
        """获取成就数据"""
        try:
            data = json.loads(self.achievement_data)
            if not isinstance(data, dict):
                return {"unlocked": {}, "equipped": ""}
            data.setdefault("unlocked", {})
            data.setdefault("equipped", "")
            return data
        except (json.JSONDecodeError, TypeError):
            return {"unlocked": {}, "equipped": ""}

    def set_achievement_data(self, data: dict):
        """设置成就数据"""
        self.achievement_data = json.dumps(data, ensure_ascii=False)

    def get_daily_activity(self) -> dict:
        """获取每日活跃度进度"""
        try:
            return json.loads(self.daily_activity)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_daily_activity(self, data: dict):
        """设置每日活跃度进度"""
        self.daily_activity = json.dumps(data, ensure_ascii=False)

    def get_total_attributes(self, equipped_items: List[Item], pill_multipliers: Optional[dict] = None, achievement_bonus: Optional[dict] = None) -> dict:
        """计算包含装备加成、成就加成和丹药效果的总属性

        Args:
            equipped_items: 已装备的物品列表
            pill_multipliers: 丹药属性倍率（可选）
            achievement_bonus: 成就属性加成（可选，如 {"physical_damage": 5}）

        Returns:
            包含所有属性的字典
        """
        # 基础属性
        total = {
            "spiritual_qi": self.spiritual_qi,
            "max_spiritual_qi": self.max_spiritual_qi,
            "blood_qi": self.blood_qi,
            "max_blood_qi": self.max_blood_qi,
            "magic_damage": self.magic_damage,
            "physical_damage": self.physical_damage,
            "magic_defense": self.magic_defense,
            "physical_defense": self.physical_defense,
            "mental_power": self.mental_power,
            "exp_multiplier": 0.0,  # 基础修为倍率为0，只来自心法
            "breakthrough_bonus": 0.0,  # 突破成功率加成
            "atk_bonus": 0.0,  # 攻击力百分比加成
            "hp_bonus": 0.0,  # 生命值加成
            "mp_bonus": 0.0,  # 真元加成
            "crit_rate": 0,  # 暴击率加成
            "crit_damage": 0.0,  # 暴击伤害加成
        }

        # 叠加装备属性
        for item in equipped_items:
            total["magic_damage"] += item.magic_damage
            total["physical_damage"] += item.physical_damage
            total["magic_defense"] += item.magic_defense
            total["physical_defense"] += item.physical_defense
            total["mental_power"] += item.mental_power

            # 心法专属属性
            if item.item_type == "main_technique":
                total["exp_multiplier"] += item.exp_multiplier
                total["breakthrough_bonus"] += item.breakthrough_bonus
                total["atk_bonus"] += item.atk_bonus
                total["hp_bonus"] += item.hp_bonus
                total["mp_bonus"] += item.mp_bonus
                total["crit_rate"] += item.crit_rate
                total["crit_damage"] += item.crit_damage

        # 叠加成就加成
        if achievement_bonus:
            for attr, val in achievement_bonus.items():
                if attr in total:
                    total[attr] += val

        # 应用丹药倍率效果
        if pill_multipliers:
            total["physical_damage"] = int(total["physical_damage"] * pill_multipliers.get("physical_damage", 1.0))
            total["magic_damage"] = int(total["magic_damage"] * pill_multipliers.get("magic_damage", 1.0))
            total["physical_defense"] = int(total["physical_defense"] * pill_multipliers.get("physical_defense", 1.0))
            total["magic_defense"] = int(total["magic_defense"] * pill_multipliers.get("magic_defense", 1.0))

        return total
