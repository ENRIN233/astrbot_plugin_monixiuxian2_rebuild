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

    # 心法专属属性
    exp_multiplier: float = 0.0  # 修为倍率加成（仅心法有效）
    breakthrough_bonus: float = 0.0  # 突破成功率加成（如 0.02 = +2%）
    atk_bonus: float = 0.0  # 攻击力百分比加成（如 0.3 = +30%）
    hp_bonus: float = 0.0  # 生命值百分比加成（如 0.05 = +5%）
    mp_bonus: float = 0.0  # 真元百分比加成（如 0.05 = +5%）
    crit_rate: int = 0  # 暴击率加成（百分比整数，如 10 = +10%）
    crit_damage: float = 0.0  # 暴击伤害加成（如 0.5 = 暴击倍率+0.5）

    # 心法专属属性（nonebot同步）
    closing_exp_bonus: float = 0.0  # 闭关经验加成（如 0.5 = +50%）
    closing_recovery_bonus: float = 0.0  # 闭关气血回复加成（如 0.5 = +50%）
    damage_reduction: float = 0.0  # 减伤率（如 0.1 = 10%减伤）
    breakthrough_number: float = 0.0  # 突破概率增加（百分比，如 3 = +3%）
    dual_cultivation_bonus: int = 0  # 每日双修次数增加
    alchemy_exp_bonus: int = 0  # 炼丹经验加成（每颗丹药）
    alchemy_count_bonus: int = 0  # 炼丹出丹数加成
    harvest_bonus: int = 0  # 采集数量加成
    random_buff: int = 0  # 随机战斗增益（1=启用）
    exclusive_weapon_id: int = 0  # 专属武器匹配ID

    # 武器战斗属性
    armor_pen: int = 0  # 穿透（百分比整数）
    lifesteal: int = 0  # 吸血（百分比整数）
    double_hit: int = 0  # 连击（百分比整数）

    def get_attribute_display(self) -> str:
        """获取属性加成的显示文本（武器只显示战斗属性）"""
        attrs = []
        if self.item_type == "weapon":
            # 武器：只显示战斗属性
            if self.atk_bonus > 0:
                attrs.append(f"攻击力+{self.atk_bonus:.0%}")
            if self.crit_rate > 0:
                attrs.append(f"暴击率+{self.crit_rate}%")
            if self.crit_damage > 0:
                attrs.append(f"暴击伤害+{self.crit_damage:.0%}")
            if self.mp_bonus > 0:
                attrs.append(f"真元+{self.mp_bonus:.0%}")
            if self.armor_pen > 0:
                attrs.append(f"穿透+{self.armor_pen}%")
            if self.lifesteal > 0:
                attrs.append(f"吸血+{self.lifesteal}%")
            if self.double_hit > 0:
                attrs.append(f"连击+{self.double_hit}%")
        else:
            # 非武器：显示心法属性
            if self.exp_multiplier > 0:
                attrs.append(f"修为倍率+{self.exp_multiplier:.1%}")
            if self.breakthrough_bonus > 0:
                attrs.append(f"突破成功率+{self.breakthrough_bonus:.1%}")
            if self.atk_bonus > 0:
                attrs.append(f"攻击力+{self.atk_bonus:.0%}")
            if self.hp_bonus > 0:
                attrs.append(f"生命值+{self.hp_bonus:.1%}")
            if self.mp_bonus > 0:
                attrs.append(f"真元+{self.mp_bonus:.0%}")
            if self.crit_rate > 0:
                attrs.append(f"暴击率+{self.crit_rate}%")
            if self.crit_damage > 0:
                attrs.append(f"暴击伤害+{self.crit_damage:.0%}")
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
    sub_technique: str = ""  # 辅修功法（装备的辅修功法名称，单个）
    furnace: str = ""  # 装备的炼丹炉名称

    # 锻造系统字段
    equipped_weapon: str = ""  # 当前装备的武器实例ID（如"forge_xxx"），空=未装备
    equipped_armor: str = ""  # 当前装备的防具实例ID
    forging_exp: int = 0  # 锻造经验
    forging_level: int = 1  # 锻造等级

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

    # 宗门系统字段
    sect_id: int = 0  # 宗门ID（0表示未加入宗门）
    sect_position: int = 4  # 宗门职位：0宗主、1长老、2亲传、3内门、4外门
    sect_contribution: int = 0  # 宗门贡献度
    sect_task: int = 0  # 宗门任务完成次数
    sect_elixir_get: int = 0  # 宗门丹药领取标记（0未领取，1已领取）

    # 丹药系统字段
    active_pill_effects: str = "[]"  # 当前生效的临时丹药效果（JSON字符串）
    permanent_pill_gains: str = "{}"  # 永久丹药累积增益（JSON字符串）
    has_resurrection_pill: str = ""  # 回生丹类型（空字符串=无，"回生丹"=损失15%属性，"涅槃重生丹"=无损失）
    has_debuff_shield: bool = False  # 是否拥有一次负面效果免疫
    pills_inventory: str = "{}"  # 丹药背包（JSON字符串，格式：{pill_name: count}）
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

    # 秘境副本系统
    sleeping_bag_level: int = 0  # 睡袋等级（0~5），影响秘境篝火回灵力

    def get_level(self, config_manager: "ConfigManager") -> str:
        """获取境界名称"""
        level_data = config_manager.get_level_data()
        if 0 <= self.level_index < len(level_data):
            return level_data[self.level_index].get("name", level_data[self.level_index].get("level_name", "未知境界"))
        return "未知境界"

    def get_required_exp(self, config_manager: "ConfigManager") -> int:
        """获取突破到下一境界所需的总修为"""
        level_data = config_manager.get_level_data()
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
        """获取永久丹药累积增益（自动迁移旧的按境界存储的倍率到全局）"""
        try:
            gains = json.loads(self.permanent_pill_gains)
        except json.JSONDecodeError:
            return {}

        # 自动迁移：将旧的按境界存储的倍率字段搬到 _global
        mult_keys = [
            "cultivation_multiplier",
            "death_protection_multiplier",
        ]
        migrated = False
        if "_global" not in gains:
            gains["_global"] = {}
        for key, value in list(gains.items()):
            if key.startswith("level_") and isinstance(value, dict):
                for mk in mult_keys:
                    if mk in value and mk not in gains["_global"]:
                        gains["_global"][mk] = value[mk]
                        migrated = True
        if migrated:
            self.permanent_pill_gains = json.dumps(gains, ensure_ascii=False)

        return gains

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

        此路径与 build_player_combat_stats（实际战斗）保持一致。
        所有新增的战斗属性（armor_pen、lifesteal 等）均从武器/防具配置中读取。

        Args:
            equipped_items: 已装备的物品列表（含武器、防具、心法、神通）
            pill_multipliers: 丹药属性倍率（可选）
            achievement_bonus: 成就属性加成（可选）

        Returns:
            包含所有属性的字典
        """
        # 基础属性
        total = {
            "spiritual_qi": self.spiritual_qi,
            "max_spiritual_qi": self.max_spiritual_qi,
            "blood_qi": self.blood_qi,
            "max_blood_qi": self.max_blood_qi,
            "exp_multiplier": 0.0,  # 基础修为倍率，只来自心法
            "breakthrough_bonus": 0.0,  # 突破成功率加成
            "atk_bonus": 0.0,  # 攻击力百分比加成
            "hp_bonus": 0.0,  # 生命值加成
            "mp_bonus": 0.0,  # 真元加成
            "crit_rate": 0,  # 暴击率加成
            "crit_damage": 0.0,  # 暴击伤害加成
            "closing_exp_bonus": 0.0,  # 闭关经验加成
            "closing_recovery_bonus": 0.0,  # 闭关回复加成
            "damage_reduction": 0.0,  # 减伤率
            "breakthrough_number": 0.0,  # 突破概率数值
            "dual_cultivation_bonus": 0,  # 双修次数
            "alchemy_exp_bonus": 0,  # 炼丹经验
            "alchemy_count_bonus": 0,  # 出丹数
            "harvest_bonus": 0,  # 采集加成
            # 战斗属性（与 build_player_combat_stats 对齐）
            "armor_pen": 0,  # 穿透（武器）
            "lifesteal": 0,  # 吸血（武器）
            "double_hit": 0,  # 连击（武器）
            "def_buff": 0.0,  # 百分比减伤（防具）
            "dodge_rate": 0,  # 闪避率（防具）
            "crit_resist": 0,  # 暴击抵抗（防具）
            "reflect_pct": 0,  # 反伤（防具）
            "block_value": 0,  # 格挡值（防具）
            "hp_regen_pct": 0.0,  # 回血百分比（防具）
        }

        # 叠加装备属性
        for item in equipped_items:
            # 心法专属属性
            if item.item_type == "main_technique":
                total["exp_multiplier"] += item.exp_multiplier
                total["breakthrough_bonus"] += item.breakthrough_bonus
                total["atk_bonus"] += item.atk_bonus
                total["hp_bonus"] += item.hp_bonus
                total["mp_bonus"] += item.mp_bonus
                total["crit_rate"] += item.crit_rate
                total["crit_damage"] += item.crit_damage
                total["closing_exp_bonus"] += item.closing_exp_bonus
                total["closing_recovery_bonus"] += item.closing_recovery_bonus
                total["damage_reduction"] += item.damage_reduction
                total["breakthrough_number"] += item.breakthrough_number
                total["dual_cultivation_bonus"] += item.dual_cultivation_bonus
                total["alchemy_exp_bonus"] += item.alchemy_exp_bonus
                total["alchemy_count_bonus"] += item.alchemy_count_bonus
                total["harvest_bonus"] += item.harvest_bonus

            # 武器战斗属性
            if item.item_type == "weapon":
                total["atk_bonus"] += item.atk_bonus
                total["mp_bonus"] += item.mp_bonus
                total["crit_rate"] += item.crit_rate
                total["crit_damage"] += item.crit_damage
                total["armor_pen"] += item.armor_pen
                total["lifesteal"] += item.lifesteal
                total["double_hit"] += item.double_hit
                total["damage_reduction"] += item.damage_reduction

            # 防具战斗属性
            if item.item_type == "armor":
                total["def_buff"] += item.def_buff
                total["atk_bonus"] += item.atk_bonus
                total["dodge_rate"] += item.dodge_rate
                total["crit_resist"] += item.crit_resist
                total["reflect_pct"] += item.reflect_pct
                total["block_value"] += item.block_value
                total["hp_regen_pct"] += item.hp_regen_pct

        # 叠加成就加成
        if achievement_bonus:
            for attr, val in achievement_bonus.items():
                if attr in total:
                    total[attr] += val

        return total
