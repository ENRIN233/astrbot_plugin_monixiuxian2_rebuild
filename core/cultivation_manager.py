# core/cultivation_manager.py
import random
from typing import Dict, Optional

from astrbot.api import AstrBotConfig, logger
from ..config_manager import ConfigManager
from ..models import Player

class CultivationManager:
    """修炼管理器，包含角色生成和闭关修炼功能"""

    def __init__(self, config: AstrBotConfig, config_manager: ConfigManager):
        self.config = config
        self.config_manager = config_manager

        # 灵根名称到配置项键的映射
        self.root_to_config_key = {
            # 废柴系列
            "伪": "PSEUDO_ROOT_SPEED",

            # 多灵根系列 → 真灵根（Excel: 修炼速度 1.0）
            "金木水火": "TRUE_ROOT_SPEED",
            "金木水土": "TRUE_ROOT_SPEED",
            "金木火土": "TRUE_ROOT_SPEED",
            "金水火土": "TRUE_ROOT_SPEED",
            "木水火土": "TRUE_ROOT_SPEED",

            "金木水": "TRUE_ROOT_SPEED",
            "金木火": "TRUE_ROOT_SPEED",
            "金木土": "TRUE_ROOT_SPEED",
            "金水火": "TRUE_ROOT_SPEED",
            "金水土": "TRUE_ROOT_SPEED",
            "金火土": "TRUE_ROOT_SPEED",
            "木水火": "TRUE_ROOT_SPEED",
            "木水土": "TRUE_ROOT_SPEED",
            "木火土": "TRUE_ROOT_SPEED",
            "水火土": "TRUE_ROOT_SPEED",

            "金木": "TRUE_ROOT_SPEED",
            "金水": "TRUE_ROOT_SPEED",
            "金火": "TRUE_ROOT_SPEED",
            "金土": "TRUE_ROOT_SPEED",
            "木水": "TRUE_ROOT_SPEED",
            "木火": "TRUE_ROOT_SPEED",
            "木土": "TRUE_ROOT_SPEED",
            "水火": "TRUE_ROOT_SPEED",
            "水土": "TRUE_ROOT_SPEED",
            "火土": "TRUE_ROOT_SPEED",

            # 五行单灵根
            "金": "WUXING_ROOT_SPEED",
            "木": "WUXING_ROOT_SPEED",
            "水": "WUXING_ROOT_SPEED",
            "火": "WUXING_ROOT_SPEED",
            "土": "WUXING_ROOT_SPEED",

            # 变异灵根
            "雷": "THUNDER_ROOT_SPEED",
            "冰": "ICE_ROOT_SPEED",
            "风": "WIND_ROOT_SPEED",
            "暗": "DARK_ROOT_SPEED",
            "光": "LIGHT_ROOT_SPEED",

            # 天灵根（单属性极致）
            "天金": "HEAVENLY_ROOT_SPEED",
            "天木": "HEAVENLY_ROOT_SPEED",
            "天水": "HEAVENLY_ROOT_SPEED",
            "天火": "HEAVENLY_ROOT_SPEED",
            "天土": "HEAVENLY_ROOT_SPEED",
            "天雷": "HEAVENLY_ROOT_SPEED",

            # 龙灵根
            "空间": "DRAGON_ROOT_SPEED",
            "时间": "DRAGON_ROOT_SPEED",
            "言灵": "DRAGON_ROOT_SPEED",

            # 超灵根
            "日": "SUPER_ROOT_SPEED",
            "月": "SUPER_ROOT_SPEED",

            # 传说级
            "融合": "FUSION_ROOT_SPEED",

            # 神话级
            "混沌": "CHAOS_ROOT_SPEED",

            # 机械核心
            "机械核心": "MECH_CORE_SPEED",

            # 异世界之力
            "异世界之力": "OTHERWORLD_SPEED",

            # 轮回道果
            "轮回道果": "REINCARNATION_SPEED",
            "真轮回道果": "TRUE_REINCARNATION_SPEED"
        }

        # 灵根池定义（按权重类别，与 Excel 对齐）
        self.root_pools = {
            "PSEUDO": ["伪"],
            "TRUE": ["金木水火", "金木水土", "金木火土", "金水火土", "木水火土",
                     "金木水", "金木火", "金木土", "金水火", "金水土", "金火土",
                     "木水火", "木水土", "木火土", "水火土",
                     "金木", "金水", "金火", "金土", "木水", "木火", "木土", "水火", "水土", "火土"],
            "WUXING": ["金", "木", "水", "火", "土"],
            "VARIANT": ["雷", "冰", "风", "暗", "光"],
            "HEAVENLY": ["天金", "天木", "天水", "天火", "天土", "天雷"],
            "DRAGON": ["空间", "时间", "言灵"],
            "SUPER": ["日", "月"],
            "FUSION": ["融合"],
            "CHAOS": ["混沌"],
            "MECH": ["机械核心"],
            "OTHERWORLD": ["异世界之力"]
        }

    def _calculate_base_stats(self, level_index: int, cultivation_type: str = "灵修") -> Dict[str, int]:
        """从境界配置中读取基础属性

        Args:
            level_index: 境界索引
            cultivation_type: 修炼类型，"灵修"或"体修"

        Returns:
            基础属性字典
        """
        level_data = self.config_manager.get_level_data(cultivation_type)
        if 0 <= level_index < len(level_data):
            level_config = level_data[level_index]
            base_lifespan = level_config.get("base_lifespan", 100 + level_index * 50)
            base_max_spiritual_qi = level_config.get("base_max_spiritual_qi", 50 + level_index * 20)
            base_max_blood_qi = level_config.get("base_max_blood_qi", 50 + level_index * 20)

            return {
                "lifespan": base_lifespan,
                "max_spiritual_qi": base_max_spiritual_qi,
                "max_blood_qi": base_max_blood_qi
            }
        else:
            # 回退逻辑，使用默认计算
            return {
                "lifespan": 100 + level_index * 50,
                "max_spiritual_qi": 50 + level_index * 20,
                "max_blood_qi": 50 + level_index * 20
            }

    def _get_random_spiritual_root(self) -> str:
        """基于权重随机抽取灵根（与 Excel 对齐）"""
        weights_config = self.config.get("SPIRIT_ROOT_WEIGHTS", {})

        # 构建权重池
        weight_pool = []

        # 伪灵根 (25%)
        pseudo_weight = weights_config.get("PSEUDO_ROOT_WEIGHT", 2500)
        weight_pool.extend([("PSEUDO", root) for root in self.root_pools["PSEUDO"]] * pseudo_weight)

        # 真灵根 (10%)
        true_weight = weights_config.get("TRUE_ROOT_WEIGHT", 1000)
        weight_pool.extend([("TRUE", root) for root in self.root_pools["TRUE"]] * true_weight)

        # 五行单灵根 (included in 真灵根 probability)
        wuxing_weight = weights_config.get("WUXING_ROOT_WEIGHT", 1000)
        weight_pool.extend([("WUXING", root) for root in self.root_pools["WUXING"]] * wuxing_weight)

        # 变异灵根 (18%)
        variant_weight = weights_config.get("VARIANT_ROOT_WEIGHT", 1800)
        weight_pool.extend([("VARIANT", root) for root in self.root_pools["VARIANT"]] * variant_weight)

        # 天灵根 (18%)
        heavenly_weight = weights_config.get("HEAVENLY_ROOT_WEIGHT", 1800)
        weight_pool.extend([("HEAVENLY", root) for root in self.root_pools["HEAVENLY"]] * heavenly_weight)

        # 龙灵根 (13%)
        dragon_weight = weights_config.get("DRAGON_ROOT_WEIGHT", 1300)
        weight_pool.extend([("DRAGON", root) for root in self.root_pools["DRAGON"]] * dragon_weight)

        # 超灵根 (10%)
        super_weight = weights_config.get("SUPER_ROOT_WEIGHT", 1000)
        weight_pool.extend([("SUPER", root) for root in self.root_pools["SUPER"]] * super_weight)

        # 融合灵根 (6%)
        fusion_weight = weights_config.get("FUSION_ROOT_WEIGHT", 600)
        weight_pool.extend([("FUSION", root) for root in self.root_pools["FUSION"]] * fusion_weight)

        # 混沌灵根 (3%)
        chaos_weight = weights_config.get("CHAOS_ROOT_WEIGHT", 300)
        weight_pool.extend([("CHAOS", root) for root in self.root_pools["CHAOS"]] * chaos_weight)

        # 机械核心 (1%)
        mech_weight = weights_config.get("MECH_ROOT_WEIGHT", 100)
        weight_pool.extend([("MECH", root) for root in self.root_pools["MECH"]] * mech_weight)

        # 异世界之力 (1%)
        otherworld_weight = weights_config.get("OTHERWORLD_ROOT_WEIGHT", 100)
        weight_pool.extend([("OTHERWORLD", root) for root in self.root_pools["OTHERWORLD"]] * otherworld_weight)

        if not weight_pool:
            # 兜底方案：默认返回金灵根
            logger.warning("灵根权重池为空，使用默认金灵根")
            return "金"

        # 随机选择
        _, selected_root = random.choice(weight_pool)
        return selected_root

    def _get_root_description(self, root_name: str) -> str:
        """获取灵根描述"""
        descriptions = {
            "伪": "【废柴】资质低劣，修炼如龟速",

            # 四灵根
            "金木水火": "【凡品】四灵根杂乱，资质平庸",
            "金木水土": "【凡品】四灵根杂乱，资质平庸",
            "金木火土": "【凡品】四灵根杂乱，资质平庸",
            "金水火土": "【凡品】四灵根杂乱，资质平庸",
            "木水火土": "【凡品】四灵根杂乱，资质平庸",

            # 三灵根
            "金木水": "【凡品】三灵根较杂，资质一般",
            "金木火": "【凡品】三灵根较杂，资质一般",
            "金木土": "【凡品】三灵根较杂，资质一般",
            "金水火": "【凡品】三灵根较杂，资质一般",
            "金水土": "【凡品】三灵根较杂，资质一般",
            "金火土": "【凡品】三灵根较杂，资质一般",
            "木水火": "【凡品】三灵根较杂，资质一般",
            "木水土": "【凡品】三灵根较杂，资质一般",
            "木火土": "【凡品】三灵根较杂，资质一般",
            "水火土": "【凡品】三灵根较杂，资质一般",

            # 双灵根
            "金木": "【良品】双灵根，较为常见",
            "金水": "【良品】双灵根，较为常见",
            "金火": "【良品】双灵根，较为常见",
            "金土": "【良品】双灵根，较为常见",
            "木水": "【良品】双灵根，较为常见",
            "木火": "【良品】双灵根，较为常见",
            "木土": "【良品】双灵根，较为常见",
            "水火": "【良品】双灵根，较为常见",
            "水土": "【良品】双灵根，较为常见",
            "火土": "【良品】双灵根，较为常见",

            # 五行单灵根
            "金": "【上品】金之精华，锋锐无双",
            "木": "【上品】木之生机，生生不息",
            "水": "【上品】水之灵韵，柔中带刚",
            "火": "【上品】火之烈焰，霸道无匹",
            "土": "【上品】土之厚重，稳如磐石",

            # 变异灵根
            "雷": "【稀有】天地雷霆，毁灭之力",
            "冰": "【稀有】极寒冰封，万物凝固",
            "风": "【稀有】疾风骤雨，来去无踪",
            "暗": "【稀有】幽暗深邃，诡异莫测",
            "光": "【稀有】神圣光明，普照万物",

            # 天灵根
            "天金": "【极品】天选之子，金之极致",
            "天木": "【极品】天选之子，木之极致",
            "天水": "【极品】天选之子，水之极致",
            "天火": "【极品】天选之子，火之极致",
            "天土": "【极品】天选之子，土之极致",
            "天雷": "【极品】天选之子，雷之极致",

            # 龙灵根
            "空间": "【仙品】掌控空间法则",
            "时间": "【仙品】窥探时间长河",
            "言灵": "【仙品】言出法随",

            # 超灵根
            "日": "【神品】日之精华，至阳至纯",
            "月": "【神品】月之灵华，至阴至柔",

            # 传说级
            "融合": "【传说】五行融合，万法归一",

            # 神话级
            "混沌": "【神话】混沌初开，包罗万象",

            # 机械核心
            "机械核心": "【禁忌】可变式羽翼核心自适应科技战甲",

            # 异世界之力
            "异世界之力": "【超越】直死之魔眼，异界法则",

            # 轮回道果
            "轮回道果": "【超越】轮回千次不灭，只为臻至巅峰",
            "真轮回道果": "【超越】轮回万次不灭，只为超越巅峰"
        }
        return descriptions.get(root_name, "【未知】神秘的灵根")

    def generate_new_player_stats(self, user_id: str, cultivation_type: str = "灵修") -> Player:
        """生成新玩家的初始数据（nonebot 统一初始属性）

        Args:
            user_id: 用户ID
            cultivation_type: 保留参数，不再影响属性（兼容旧接口）
        """
        root = self._get_random_spiritual_root()
        initial_gold = self.config["VALUES"]["INITIAL_GOLD"]

        # nonebot 初始属性：HP=500, MP=1000, ATK=100, 修为=0
        return Player(
            user_id=user_id,
            spiritual_root=f"{root}灵根",
            cultivation_type="灵修",
            lifespan=100,
            experience=0,
            gold=initial_gold,
            spiritual_qi=0,
            max_spiritual_qi=0,
            blood_qi=0,
            max_blood_qi=0,
            hp=500,
            mp=1000,
            atk=100,
        )

    def get_spiritual_root_speed(self, player: Player) -> float:
        """获取玩家灵根的修炼速度倍率

        Args:
            player: 玩家对象

        Returns:
            float: 灵根修炼速度倍率
        """
        # 从 player.spiritual_root 中提取灵根名称（去掉"灵根"两个字）
        root_name = player.spiritual_root.replace("灵根", "")

        # 获取对应的配置键
        config_key = self.root_to_config_key.get(root_name)
        if not config_key:
            logger.warning(f"未找到灵根 {root_name} 的速度配置，使用默认倍率 1.0")
            return 1.0

        # 从配置中获取速度倍率
        speeds_config = self.config.get("SPIRIT_ROOT_SPEEDS", {})
        speed = speeds_config.get(config_key, 1.0)
        return speed

    def calculate_cultivation_exp_with_segments(
        self,
        player: Player,
        start_time: int,
        end_time: int,
        technique_bonus: float = 0.0,
        raw_pill_effects: Optional[list] = None,
        land_bonus: float = 0.0,
        closing_exp_bonus: float = 0.0
    ) -> int:
        """分段计算闭关修为（丹药过期前后的倍率分别计算）

        Args:
            player: 玩家对象
            start_time: 闭关开始时间（Unix时间戳）
            end_time: 出关时间（Unix时间戳）
            technique_bonus: 心法修为倍率加成
            raw_pill_effects: 原始丹药效果列表（含已过期的）
            land_bonus: 洞天福地修炼效率加成

        Returns:
            int: 获得的修为值
        """
        base_exp = self.config["VALUES"].get("BASE_EXP_PER_MINUTE", 60)
        root_speed = self.get_spiritual_root_speed(player)

        # 读取永久丹药修炼倍率加成
        permanent_gains = player.get_permanent_pill_gains()
        permanent_cultivation_mult = permanent_gains.get("_global", {}).get("cultivation_multiplier", 0)

        other_multiplier = root_speed * (1.0 + technique_bonus) * (1.0 + closing_exp_bonus) * (1.0 + land_bonus) * (1.0 + permanent_cultivation_mult)

        # 从丹药效果中提取修炼加成和过期时间
        pill_segments = []  # [(expiry_time, cultivation_multiplier)]
        if raw_pill_effects:
            for effect in raw_pill_effects:
                mul = effect.get("cultivation_multiplier", 0)
                if mul <= 0:
                    continue
                expiry = effect.get("expiry_time", 0)
                pill_segments.append((expiry, mul))

        # 无修炼加成丹药，直接用原始公式
        if not pill_segments:
            minutes = max(0, (end_time - start_time) // 60)
            total_exp = int(base_exp * minutes * other_multiplier)
            logger.info(
                f"玩家 {player.user_id} 闭关 {minutes} 分钟（无丹药分段），"
                f"基础修为 {base_exp}，其他倍率 {other_multiplier:.4f}，"
                f"永久丹药修炼加成 {permanent_cultivation_mult:+.0%}，获得修为 {total_exp}"
            )
            return total_exp

        # 收集切分点：所有有效的丹药过期时间
        cut_points = {start_time, end_time}
        for expiry, _ in pill_segments:
            if expiry > 0 and start_time < expiry < end_time:
                cut_points.add(expiry)

        sorted_points = sorted(cut_points)

        # 逐段计算
        total_exp = 0
        total_minutes = 0
        for i in range(len(sorted_points) - 1):
            seg_start = sorted_points[i]
            seg_end = sorted_points[i + 1]
            seg_minutes = max(0, (seg_end - seg_start) // 60)
            if seg_minutes <= 0:
                continue

            # 计算该段内有效的丹药修炼加成之和
            seg_pill_mul = 1.0
            for expiry, mul in pill_segments:
                # 丹药在此段内有效：无过期 或 过期时间 > 段起点
                if expiry <= 0 or expiry > seg_start:
                    seg_pill_mul += mul

            seg_exp = int(base_exp * seg_minutes * other_multiplier * seg_pill_mul)
            total_exp += seg_exp
            total_minutes += seg_minutes

        logger.info(
            f"玩家 {player.user_id} 分段闭关 {total_minutes} 分钟（{len(sorted_points) - 1} 段），"
            f"获得修为 {total_exp}"
        )
        return total_exp
