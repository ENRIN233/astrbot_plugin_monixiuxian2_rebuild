# managers/rift_manager.py
"""
秘境系统管理器 - 每日随机开放一个秘境，限时10:00-21:00，每人每日一次
"""

import random
import time
from datetime import datetime
from typing import Tuple, List, Optional, Dict, TYPE_CHECKING
from ..data.data_manager import DataBase
from ..models_extended import Rift, UserStatus
from ..models import Player

if TYPE_CHECKING:
    from ..core import StorageRingManager


class RiftManager:
    """秘境系统管理器"""

    DEFAULT_OPEN_HOUR_START = 10
    DEFAULT_OPEN_HOUR_END = 21

    # 秘境物品掉落表（按秘境等级分组）
    RIFT_DROP_TABLE = {
        1: [  # 低级秘境
            {"name": "灵草", "weight": 50, "min": 2, "max": 5},
        ],
        2: [  # 中级秘境
            {"name": "灵草", "weight": 50, "min": 3, "max": 7},
        ],
        3: [  # 高级秘境
            {"name": "灵草", "weight": 50, "min": 5, "max": 12},
        ],
    }

    # 秘境稀有丹药掉落表（按秘境等级分组，低概率掉落功能丹）
    RIFT_PILL_DROP_TABLE = {
        1: [  # 低级秘境 - 3%概率掉落
            {"name": "修炼加速丹", "weight": 70, "min": 1, "max": 1},
            {"name": "小爆发丹", "weight": 30, "min": 1, "max": 1},
        ],
        2: [  # 中级秘境 - 5%概率掉落
            {"name": "灵气加速丹", "weight": 40, "min": 1, "max": 1},
            {"name": "狂暴丹", "weight": 30, "min": 1, "max": 1},
            {"name": "幸运丹", "weight": 10, "min": 1, "max": 1},
        ],
        3: [  # 高级秘境 - 10%概率掉落
            {"name": "天道加速丹", "weight": 30, "min": 1, "max": 1},
            {"name": "狂暴丹·改", "weight": 30, "min": 1, "max": 1},
            {"name": "天命幸运丹", "weight": 20, "min": 1, "max": 1},
            {"name": "雷霆丹", "weight": 20, "min": 1, "max": 1},
        ],
    }

    # 秘境丹药掉落概率（百分比）
    RIFT_PILL_DROP_CHANCE = {
        1: 3,   # 低级秘境 3%
        2: 5,   # 中级秘境 5%
        3: 10,  # 高级秘境 10%
    }

    # 品级→参考等级映射（用于动态装备掉落）
    RANK_LEVEL_MAP = {
        "凡品": 0, "灵品": 10, "地品": 12, "天品": 13,
        "皇品": 16, "帝品": 22, "道品": 28, "仙品": 32, "混元先天": 35,
    }

    # 品级排序（从低到高）
    RANK_ORDER = ["凡品", "灵品", "地品", "天品", "皇品", "帝品", "道品", "仙品", "混元先天"]
    DEFAULT_EQUIP_DROP_CHANCE = {1: 2, 2: 5, 3: 10, 4: 15, 5: 20}  # 各秘境等级的装备掉落概率(%)
    DEFAULT_EQUIP_MAX_LEVEL = {1: 12, 2: 22, 3: 35, 4: 35, 5: 35}  # 各秘境等级允许的最高装备等级
    DEFAULT_LEVEL_MATCH_HALF_LIFE = 5.0                 # 等级匹配半衰期
    DEFAULT_WEAPON_ARMOR_RATIO = 50                     # 武器掉落占比(%)
    DEFAULT_RANK_BASE_WEIGHT = {                        # 品级基础权重（控制各品级掉落概率分布）
        "凡品": 1000, "灵品": 300, "地品": 100, "天品": 30,
        "皇品": 10, "帝品": 3, "道品": 1, "仙品": 0.3, "混元先天": 0.1,
    }

    def __init__(self, db: DataBase, config_manager=None, storage_ring_manager: "StorageRingManager" = None):
        self.db = db
        self.config_manager = config_manager
        self.storage_ring_manager = storage_ring_manager
        self.config = config_manager.rift_config if config_manager else {}
        self.open_hour_start = self.config.get("open_hour_start", self.DEFAULT_OPEN_HOUR_START)
        self.open_hour_end = self.config.get("open_hour_end", self.DEFAULT_OPEN_HOUR_END)
        self.rift_defs = self.config.get("rifts", [])

        # 加载装备掉落配置
        game_config = config_manager.game_config if config_manager else {}
        rift_game_cfg = game_config.get("rift", {})
        equip_cfg = rift_game_cfg.get("equipment_drop", {})
        self.equip_drop_chance = {int(k): v for k, v in equip_cfg.get("drop_chance", self.DEFAULT_EQUIP_DROP_CHANCE).items()}
        self.equip_max_level = {int(k): v for k, v in equip_cfg.get("max_item_level", self.DEFAULT_EQUIP_MAX_LEVEL).items()}
        self.equip_level_match_half_life = equip_cfg.get("level_match_half_life", self.DEFAULT_LEVEL_MATCH_HALF_LIFE)
        self.weapon_armor_ratio = equip_cfg.get("weapon_armor_ratio", self.DEFAULT_WEAPON_ARMOR_RATIO)
        self.rank_level_map = equip_cfg.get("rank_level_map", self.RANK_LEVEL_MAP)
        self.rank_base_weight = equip_cfg.get("rank_base_weight", self.DEFAULT_RANK_BASE_WEIGHT)

        # 武器/防具数据引用
        self.weapons_data = config_manager.weapons_data if config_manager else {}
        self._only_weapons = {}  # type=="weapon" 的子集
        self.armors_data = {}    # type=="armor" 的子集
        if self.weapons_data:
            for name, data in self.weapons_data.items():
                if data.get("type") == "armor":
                    self.armors_data[name] = data
                elif data.get("type") == "weapon":
                    self._only_weapons[name] = data

    # -------- 时间与每日秘境 --------

    def _get_today_str(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def _is_open_now(self) -> bool:
        now = datetime.now()
        return self.open_hour_start <= now.hour < self.open_hour_end

    def _open_remaining_minutes(self) -> int:
        now = datetime.now()
        if now.hour >= self.open_hour_end:
            return 0
        end_ts = now.replace(hour=self.open_hour_end, minute=0, second=0, microsecond=0)
        return max(0, int((end_ts - now).total_seconds()) // 60)

    async def _get_today_rift(self) -> Optional[Dict]:
        """获取今天开放的秘境定义，不存在则随机选一个"""
        if not self.rift_defs:
            return None
        today = self._get_today_str()
        stored = await self.db.ext.get_system_config("rift_today")
        if stored:
            parts = stored.split("|")
            if len(parts) == 2 and parts[0] == today:
                rift_id = int(parts[1])
                for r in self.rift_defs:
                    if r["id"] == rift_id:
                        return r
        # 加权随机选一个（spawn_weight 越高越容易被选中）
        weights = [r.get("spawn_weight", 1) for r in self.rift_defs]
        chosen = random.choices(self.rift_defs, weights=weights, k=1)[0]
        await self.db.ext.set_system_config("rift_today", f"{today}|{chosen['id']}")
        return chosen

    async def _check_daily_used(self, user_id: str) -> bool:
        """检查玩家今天是否已探索过"""
        today = self._get_today_str()
        key = f"rift_daily_{user_id}"
        val = await self.db.ext.get_system_config(key)
        return val == today

    async def _mark_daily_used(self, user_id: str):
        today = self._get_today_str()
        await self.db.ext.set_system_config(f"rift_daily_{user_id}", today)

    # -------- GM 指令 --------

    async def force_refresh_rift(self) -> Tuple[bool, str, Optional[Dict]]:
        """GM强制刷新秘境：重置所有玩家探索次数并重新选秘境"""
        # 清除所有玩家的每日探索标记
        cleared = await self.db.ext.clear_system_configs_by_prefix("rift_daily_")

        # 清除今日秘境记录，强制重新选取
        await self.db.ext.set_system_config("rift_today", "")

        # 重新选取今日秘境
        rift_def = await self._get_today_rift()
        if not rift_def:
            return False, "❌ 未配置秘境数据，刷新失败。", None

        rift = await self.db.ext.get_rift_by_id(rift_def["id"])
        rift_name = rift.rift_name if rift else rift_def.get("name", "未知秘境")
        duration = rift_def.get("duration", 1800)

        msg = (
            f"✅ 秘境已强制刷新！\n"
            f"━━━━━━━━━━━━━━━\n"
            f"今日秘境：【{rift_name}】\n"
            f"探索时长：{duration // 60} 分钟\n"
            f"已重置 {cleared} 名玩家的探索次数\n"
            f"━━━━━━━━━━━━━━━\n"
            f"⏰ 开放时间：10:00 ~ 21:00"
        )
        return True, msg, rift_def

    # -------- 指令处理 --------

    async def enter_rift(self, user_id: str) -> Tuple[bool, str]:
        """进入秘境"""
        # 检查开放时间
        if not self._is_open_now():
            return False, f"❌ 秘境未开放！开放时间：{self.open_hour_start}:00 ~ {self.open_hour_end}:00"

        # 检查用户
        player = await self.db.get_player_by_id(user_id)
        if not player:
            return False, "❌ 你还未踏入修仙之路！"

        # 检查每日次数
        if await self._check_daily_used(user_id):
            return False, "❌ 你今日已经探索过秘境了，明日再来。"

        # 立即标记已使用（防止并发重复进入，失败时回滚）
        await self._mark_daily_used(user_id)
        entry_success = False
        try:
            # 检查用户状态
            user_cd = await self.db.ext.get_user_cd(user_id)
            if not user_cd:
                await self.db.ext.create_user_cd(user_id)
                user_cd = await self.db.ext.get_user_cd(user_id)

            if user_cd.type != UserStatus.IDLE:
                return False, f"❌ 你当前正{UserStatus.get_name(user_cd.type)}，无法探索秘境！"

            # 获取今日开放的秘境
            today_rift = await self._get_today_rift()
            if not today_rift:
                return False, "❌ 未配置秘境数据，请联系管理员。"

            rift_id = today_rift["id"]
            rift = await self.db.ext.get_rift_by_id(rift_id)
            if not rift:
                return False, "❌ 秘境数据异常！"

            # 设置探索状态
            duration = today_rift.get("duration", 1800)
            scheduled_time = int(time.time()) + duration
            extra_data = {"rift_id": rift_id, "rift_level": rift.rift_level}
            await self.db.ext.set_user_busy(user_id, UserStatus.EXPLORING, scheduled_time, extra_data)
            entry_success = True

            return True, f"✨ 你进入了『{rift.rift_name}』！探索需要 {duration // 60} 分钟。\n使用 /完成探索 领取奖励"
        finally:
            if not entry_success:
                # 校验失败，回滚每日标记
                await self.db.ext.set_system_config(f"rift_daily_{user_id}", "")

    async def finish_exploration(self, user_id: str) -> Tuple[bool, str, Optional[Dict]]:
        """完成秘境探索"""
        player = await self.db.get_player_by_id(user_id)
        if not player:
            return False, "❌ 你还未踏入修仙之路！", None

        user_cd = await self.db.ext.get_user_cd(user_id)
        if not user_cd or user_cd.type != UserStatus.EXPLORING:
            return False, "❌ 你当前不在探索秘境！", None

        current_time = int(time.time())
        if current_time < user_cd.scheduled_time:
            remaining = user_cd.scheduled_time - current_time
            minutes = remaining // 60
            return False, f"❌ 探索尚未完成！还需要 {minutes} 分钟。", None

        extra_data = user_cd.get_extra_data() if hasattr(user_cd, 'get_extra_data') else {}
        rift_id = extra_data.get("rift_id", 0)
        rift_level = extra_data.get("rift_level", 1)

        rift = await self.db.ext.get_rift_by_id(rift_id) if rift_id else None
        rift_name = rift.rift_name if rift else "未知秘境"

        # 查找秘境配置（获取灵石/修为奖励基数）
        rift_def = None
        for r in self.rift_defs:
            if r["id"] == rift_id:
                rift_def = r
                break

        # 灵石/修为奖励（50% 独立概率，等级动态缩放）
        reward_lines = []
        got_stone = False
        got_exp = False
        if rift_def:
            level_bonus = 1 + max(0, player.level_index - 3) * 0.06
            base_stone = rift_def.get("reward_stone", 0)
            base_exp = rift_def.get("reward_exp", 0)

            if base_stone > 0 and random.randint(1, 100) <= 50:
                stone_reward = int(base_stone * level_bonus)
                player.gold += stone_reward
                got_stone = True
                reward_lines.append(f"  💰 灵石 +{stone_reward:,}")

            if base_exp > 0 and random.randint(1, 100) <= 50:
                exp_reward = int(base_exp * level_bonus)
                player.experience += exp_reward
                got_exp = True
                reward_lines.append(f"  ✨ 修为 +{exp_reward:,}")

            if reward_lines:
                await self.db.update_player(player)

        # 奖励文案
        if got_stone and got_exp:
            reward_desc = random.choice([
                "你在秘境深处发现了一处灵脉，灵气化作灵石与修为涌入体内！",
                "击杀妖兽后，你从其巢穴中搜刮到大量灵石，同时领悟了新的修炼感悟。",
                "你破解了一道远古禁制，灵石与传承之力同时涌入体内！",
            ])
        elif got_stone:
            reward_desc = random.choice([
                "你在岩壁裂缝中发现了一簇灵石矿脉，小心开采后收获颇丰。",
                "击败妖兽后，你从其腹中发现了大量灵石。",
                "你偶然触发了一处藏宝机关，灵石散落一地！",
            ])
        elif got_exp:
            reward_desc = random.choice([
                "你在秘境中偶遇一处灵气浓郁之地，打坐片刻后修为大增！",
                "你破解了石壁上的功法残篇，领悟良多，修为有所精进。",
                "秘境中残留的上古意志与你产生了共鸣，修为突飞猛进！",
            ])
        else:
            reward_desc = random.choice([
                "秘境内危机四伏，你小心翼翼地探索了一番，虽未获得实质性收获，但积累了宝贵的战斗经验。",
                "你仔细搜寻了每一个角落，可惜此地灵脉枯竭，并无灵石与修为上的收获。",
                "这片区域似乎早已被前人搜刮一空，你只得空手而归。",
            ])

        # 随机事件
        events = [
            {"desc": "你发现了一处灵泉，修为大增！", "item_chance": 70},
            {"desc": "你在秘境中击败了一只妖兽！", "item_chance": 80},
            {"desc": "你找到了一个隐藏的宝箱！", "item_chance": 100},
            {"desc": "你领悟了一些修炼心得。", "item_chance": 40},
            {"desc": "你在秘境中遇到了前辈留下的传承！", "item_chance": 90}
        ]
        event = random.choice(events)

        # 物品掉落
        dropped_items = []
        item_msg = ""
        try:
            dropped_items = await self._roll_rift_drops(player, rift_level, event["item_chance"])
            if dropped_items:
                # 按类型分组用于文案展示
                pill_items = [(n, c) for n, c in dropped_items if self._is_pill_item(n)]
                equip_items = [(n, c) for n, c in dropped_items if not self._is_pill_item(n) and self._is_equipment_item(n)]
                other_items = [(n, c) for n, c in dropped_items if not self._is_pill_item(n) and not self._is_equipment_item(n)]

                item_lines = []

                # 丹药文案
                if pill_items:
                    pill_desc = random.choice([
                        "  你发现了一个被藤蔓覆盖的玉瓶，打开后药香扑鼻——",
                        "  在一处坍塌的丹房废墟中，你找到了几枚尚有药力的丹药——",
                        "  击败守护妖兽后，你从其巢穴深处翻出了几瓶丹药——",
                    ])
                    item_lines.append(pill_desc)

                # 装备文案
                if equip_items:
                    equip_desc = random.choice([
                        "  一道光芒闪过，你从阵法残留中取出了一件宝物——",
                        "  你拨开尘封已久的石棺，其中赫然躺着一件法器——",
                        "  秘境深处的器灵将一件珍品托付于你——",
                    ])
                    item_lines.append(equip_desc)

                # 统一存入储物戒
                all_items = pill_items + equip_items + other_items
                for item_name, count in all_items:
                    rank = self._get_item_rank(item_name)
                    rank_label = f"({rank})" if rank else ""
                    is_equip = self._is_equipment_item(item_name)
                    prefix = "  · ⚔️ " if is_equip else "  · "
                    if self.storage_ring_manager:
                        success, _ = await self.storage_ring_manager.store_item(player, item_name, count, silent=True)
                        if success:
                            item_lines.append(f"{prefix}{item_name}{rank_label} x{count}")
                        else:
                            item_lines.append(f"{prefix}{item_name}{rank_label} x{count}（储物戒已满，丢失）")
                    else:
                        item_lines.append(f"{prefix}{item_name}{rank_label} x{count}（无法存储）")

                if item_lines:
                    item_msg = "\n\n📦 获得物品：\n" + "\n".join(item_lines)
        finally:
            # 无论掉落处理是否异常，都必须释放玩家状态
            await self.db.ext.set_user_free(user_id)

        reward_msg = "\n\n🎁 探索奖励：\n" + "\n".join(reward_lines) if reward_lines else ""

        msg = (
            f"🌀 探索完成 - {rift_name}\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"{reward_desc}{reward_msg}{item_msg}"
        )

        reward_data = {
            "event": reward_desc,
            "items": dropped_items,
            "rift_name": rift_name
        }
        return True, msg, reward_data

    async def exit_rift(self, user_id: str) -> Tuple[bool, str]:
        """退出秘境"""
        player = await self.db.get_player_by_id(user_id)
        if not player:
            return False, "❌ 你还未踏入修仙之路！"

        user_cd = await self.db.ext.get_user_cd(user_id)
        if not user_cd or user_cd.type != UserStatus.EXPLORING:
            return False, "❌ 你当前不在探索秘境！"

        await self.db.ext.set_user_free(user_id)
        return True, "✅ 你已退出秘境，本次探索未获得任何奖励。"

    # -------- 内部工具 --------

    def _is_pill_item(self, item_name: str) -> bool:
        if self.config_manager and hasattr(self.config_manager, 'is_pill'):
            return self.config_manager.is_pill(item_name)
        return False

    def _is_equipment_item(self, item_name: str) -> bool:
        """判断是否为装备类物品（武器或防具）"""
        return item_name in self.weapons_data

    def _get_item_rank(self, item_name: str) -> str:
        """获取装备的品级"""
        data = self.weapons_data.get(item_name)
        return data.get("rank", "") if data else ""

    async def _roll_rift_drops(self, player: Player, rift_level: int, item_chance: int) -> List[Tuple[str, int]]:
        dropped_items = []
        if random.randint(1, 100) > item_chance:
            return dropped_items

        drop_table = self.RIFT_DROP_TABLE.get(rift_level, self.RIFT_DROP_TABLE[1])
        total_weight = sum(item["weight"] for item in drop_table)
        roll = random.randint(1, total_weight)

        current_weight = 0
        for item in drop_table:
            current_weight += item["weight"]
            if roll <= current_weight:
                count = random.randint(item["min"], item["max"])
                dropped_items.append((item["name"], count))
                break

        if rift_level >= 2 and random.randint(1, 100) <= 50:
            roll = random.randint(1, total_weight)
            current_weight = 0
            for item in drop_table:
                current_weight += item["weight"]
                if roll <= current_weight:
                    count = random.randint(item["min"], item["max"])
                    dropped_items.append((item["name"], count))
                    break

        pill_drops = self._roll_pill_drops(rift_level)
        if pill_drops:
            dropped_items.extend(pill_drops)

        # 装备掉落（独立于材料和丹药）
        equip_drops = self._roll_equipment_drops(player, rift_level)
        if equip_drops:
            dropped_items.extend(equip_drops)

        return dropped_items

    def _roll_pill_drops(self, rift_level: int) -> List[Tuple[str, int]]:
        dropped_pills = []
        pill_chance = self.RIFT_PILL_DROP_CHANCE.get(rift_level, 3)
        if random.randint(1, 100) > pill_chance:
            return dropped_pills

        pill_table = self.RIFT_PILL_DROP_TABLE.get(rift_level, self.RIFT_PILL_DROP_TABLE[1])
        total_weight = sum(item["weight"] for item in pill_table)
        roll = random.randint(1, total_weight)

        current_weight = 0
        for item in pill_table:
            current_weight += item["weight"]
            if roll <= current_weight:
                count = random.randint(item["min"], item["max"])
                dropped_pills.append((item["name"], count))
                break
        return dropped_pills

    def _get_rank_level(self, rank: str) -> int:
        """获取品级对应的参考等级"""
        return self.rank_level_map.get(rank, 0)

    def _roll_equipment_drops(self, player: Player, rift_level: int) -> List[Tuple[str, int]]:
        """秘境装备掉落roll：先判定武器/防具，再从合格池加权随机选"""
        equip_chance = self.equip_drop_chance.get(rift_level, 0)
        if random.randint(1, 100) > equip_chance:
            return []

        max_level = self.equip_max_level.get(rift_level, 0)
        player_level = player.level_index
        half_life = self.equip_level_match_half_life

        # 判定武器还是防具
        if random.randint(1, 100) <= self.weapon_armor_ratio:
            item_source = self._only_weapons
        else:
            item_source = self.armors_data

        # 获取玩家所属品级
        player_rank = self._get_player_rank(player_level)
        player_rank_idx = self.RANK_ORDER.index(player_rank) if player_rank in self.RANK_ORDER else 0

        # 筛选合格装备
        candidates = []
        for name, item_cfg in item_source.items():
            rank = item_cfg.get("rank", "凡品")
            rank_level = self._get_rank_level(rank)
            # 秘境等级上限过滤
            if rank_level > max_level:
                continue
            # 使用品级基础权重（避免 nonebot 物品的 shop_weight=500 破坏分布）
            rank_weight = self.rank_base_weight.get(rank, 1.0)
            if rank_weight <= 0:
                continue
            # 计算动态权重因子
            item_rank_idx = self.RANK_ORDER.index(rank) if rank in self.RANK_ORDER else 0
            rank_gap = item_rank_idx - player_rank_idx  # 正数=装备品级更高
            if rank_gap <= 0:
                # 同品级或更低：用指数衰减
                level_diff = player_level - rank_level
                level_match_factor = 0.5 ** (level_diff / half_life)
            elif rank_gap == 1:
                # 高1个品级：固定0.1
                level_match_factor = 0.1
            else:
                # 高2个及以上品级：固定0.01
                level_match_factor = 0.01

            adjusted_weight = rank_weight * level_match_factor
            if adjusted_weight > 0.001:
                candidates.append((name, adjusted_weight))

        if not candidates:
            return []

        # 加权随机选取
        total_weight = sum(w for _, w in candidates)
        roll = random.uniform(0, total_weight)
        cumulative = 0.0
        for name, weight in candidates:
            cumulative += weight
            if roll <= cumulative:
                return [(name, 1)]

        return [(candidates[-1][0], 1)]

    def _get_player_rank(self, player_level: int) -> str:
        """获取玩家所属品级名称"""
        sorted_ranks = sorted(self.rank_level_map.items(), key=lambda x: x[1], reverse=True)
        for rank, level in sorted_ranks:
            if player_level >= level:
                return rank
        return "凡品"
