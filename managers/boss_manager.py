# managers/boss_manager.py
"""
Boss系统管理器 - 处理Boss生成、战斗、奖励等逻辑
参照NoneBot2插件的xiuxian_boss实现
"""

import random
import time
from typing import Tuple, Dict, Optional, List, TYPE_CHECKING
from ..data.data_manager import DataBase
from ..models_extended import Boss, UserStatus
from ..models import Player
from .combat_manager import CombatManager, CombatStats

if TYPE_CHECKING:
    from ..core import StorageRingManager


class BossManager:
    """Boss系统管理器"""
    
    # Boss境界配置（覆盖58级体系，每3级一个档位）
    # 数值设计：保证有装备时玩家可存活5回合+，Boss靠HP量提供挑战
    BOSS_LEVELS = [
        {"name": "练气", "level_index": 0,  "hp_mult": 1.4,  "atk_mult": 1.4,  "reward_mult": 1.4},
        {"name": "筑基", "level_index": 3,  "hp_mult": 2.1,  "atk_mult": 1.5,  "reward_mult": 2.1},
        {"name": "金丹", "level_index": 6,  "hp_mult": 2.8,  "atk_mult": 1.7,  "reward_mult": 2.8},
        {"name": "元婴", "level_index": 9,  "hp_mult": 3.5,  "atk_mult": 1.7,  "reward_mult": 3.5},
        {"name": "化神", "level_index": 12, "hp_mult": 4.2,  "atk_mult": 1.8,  "reward_mult": 4.2},
        {"name": "炼虚", "level_index": 15, "hp_mult": 4.9,  "atk_mult": 1.8,  "reward_mult": 4.9},
        {"name": "合体", "level_index": 18, "hp_mult": 5.6,  "atk_mult": 1.8,  "reward_mult": 5.6},
        {"name": "大乘", "level_index": 21, "hp_mult": 6.3,  "atk_mult": 2.0,  "reward_mult": 6.3},
        {"name": "神火", "level_index": 24, "hp_mult": 7.0,  "atk_mult": 2.0,  "reward_mult": 7.0},
        {"name": "真一", "level_index": 27, "hp_mult": 7.7,  "atk_mult": 2.0,  "reward_mult": 7.7},
        {"name": "圣祭", "level_index": 30, "hp_mult": 8.4,  "atk_mult": 2.1,  "reward_mult": 8.4},
        {"name": "天神", "level_index": 33, "hp_mult": 9.1,  "atk_mult": 2.1,  "reward_mult": 9.1},
        {"name": "虚道", "level_index": 36, "hp_mult": 9.8,  "atk_mult": 2.1,  "reward_mult": 9.8},
        {"name": "斩我", "level_index": 39, "hp_mult": 10.5, "atk_mult": 2.1,  "reward_mult": 10.5},
        {"name": "混沌", "level_index": 42, "hp_mult": 11.2, "atk_mult": 2.1,  "reward_mult": 11.2},
        {"name": "创世", "level_index": 45, "hp_mult": 12.6, "atk_mult": 2.1,  "reward_mult": 12.6},
        {"name": "金仙", "level_index": 48, "hp_mult": 14.0, "atk_mult": 2.1,  "reward_mult": 14.0},
        {"name": "轮回", "level_index": 51, "hp_mult": 15.4, "atk_mult": 2.2,  "reward_mult": 15.4},
        {"name": "虚神", "level_index": 54, "hp_mult": 15.4, "atk_mult": 2.2,  "reward_mult": 15.4},
        {"name": "仙帝", "level_index": 57, "hp_mult": 16.8, "atk_mult": 2.2,  "reward_mult": 16.8},
    ]
    
    # Boss名称池
    BOSS_NAMES = [
        "血魔", "邪修", "魔头", "妖王", "魔君",
        "异兽", "凶兽", "妖尊", "魔尊", "邪帝",
        "天魔", "地魔", "魔神", "妖神", "邪神"
    ]
    
    # Boss物品掉落表（含锻造材料，高阶Boss掉落的低阶材料数量大幅增加）
    # 档位边界与 get_drop_tier_for_level() 保持一致：
    #   low(≤6)  → 练气~筑基  |  mid(≤12)  → 金丹~化神
    #   high(≤33) → 炼虚~天神  |  ultra(>33) → 虚道~合道
    BOSS_DROP_TABLE = {
        "low": [  # boss_level_index ≤ 6
            {"name": "灵草", "weight": 50, "min": 2, "max": 5},
            {"name": "精铁", "weight": 30, "min": 1, "max": 3},
            {"name": "百年灵草", "weight": 20, "min": 1, "max": 2},
            {"name": "紫金沙", "weight": 10, "min": 1, "max": 1},
        ],
        "mid": [  # boss_level_index ≤ 12
            {"name": "灵草", "weight": 30, "min": 4, "max": 10},
            {"name": "精铁", "weight": 20, "min": 2, "max": 5},
            {"name": "百年灵草", "weight": 15, "min": 2, "max": 4},
            {"name": "紫金沙", "weight": 15, "min": 1, "max": 3},
            {"name": "魔核碎片", "weight": 10, "min": 1, "max": 2},
            {"name": "赤炎石", "weight": 10, "min": 1, "max": 2},
        ],
        "high": [  # boss_level_index ≤ 33
            {"name": "灵草", "weight": 20, "min": 8, "max": 20},
            {"name": "精铁", "weight": 15, "min": 5, "max": 15},
            {"name": "百年灵草", "weight": 10, "min": 5, "max": 10},
            {"name": "紫金沙", "weight": 15, "min": 2, "max": 5},
            {"name": "魔核碎片", "weight": 15, "min": 2, "max": 4},
            {"name": "赤炎石", "weight": 15, "min": 2, "max": 4},
            {"name": "亡者之息", "weight": 10, "min": 1, "max": 3},
            {"name": "幽魂草", "weight": 10, "min": 1, "max": 3},
            {"name": "灵兽骨", "weight": 8, "min": 1, "max": 2},
        ],
        "ultra": [  # boss_level_index > 33
            {"name": "灵草", "weight": 15, "min": 15, "max": 40},
            {"name": "精铁", "weight": 12, "min": 15, "max": 40},
            {"name": "百年灵草", "weight": 10, "min": 10, "max": 30},
            {"name": "亡者之息", "weight": 15, "min": 3, "max": 6},
            {"name": "幽魂草", "weight": 15, "min": 3, "max": 6},
            {"name": "星辉晶砂", "weight": 12, "min": 2, "max": 5},
            {"name": "灵兽骨", "weight": 10, "min": 3, "max": 8},
            {"name": "天火熔晶", "weight": 8, "min": 2, "max": 4},
            {"name": "九幽寒铁", "weight": 8, "min": 2, "max": 4},
            {"name": "玄冰之核", "weight": 8, "min": 1, "max": 3},
            {"name": "月光粉尘", "weight": 8, "min": 1, "max": 3},
            {"name": "龙骨髓", "weight": 5, "min": 1, "max": 2},
            {"name": "妖丹", "weight": 3, "min": 1, "max": 1},
            {"name": "混沌源石", "weight": 3, "min": 1, "max": 1},
        ],
    }
    
    def __init__(self, db: DataBase, combat_mgr: CombatManager, config_manager=None, storage_ring_manager: "StorageRingManager" = None, skill_manager=None):
        self.db = db
        self.combat_mgr = combat_mgr
        self.config_manager = config_manager
        self.storage_ring_manager = storage_ring_manager
        self.skill_manager = skill_manager
        self.config = config_manager.boss_config if config_manager else {}
        self.levels = self.config.get("levels", self.BOSS_LEVELS)
    
    async def spawn_boss(
        self,
        base_exp: int = 100000,
        level_config: Optional[Dict] = None
    ) -> Tuple[bool, str, Optional[Boss]]:
        """
        生成Boss
        
        Args:
            base_exp: 基础修为（用于计算属性）
            level_config: Boss等级配置，如果为None则随机选择
            
        Returns:
            (成功标志, 消息, Boss对象)
        """
        # 检查是否已有存活的Boss
        existing_boss = await self.db.ext.get_active_boss()
        if existing_boss:
            return False, f"❌ 当前已有Boss『{existing_boss.boss_name}』存在！", None
        
        # 选择Boss等级
        if not level_config:
            level_config = random.choice(self.levels)
        
        # 生成Boss名称
        boss_name = random.choice(self.BOSS_NAMES) + f"·{level_config['name']}境"
        
        # 计算Boss属性
        hp_mult = level_config["hp_mult"]
        atk_mult = level_config["atk_mult"]
        reward_mult = level_config["reward_mult"]
        
        # Boss的HP和ATK基于修为计算
        max_hp = int(base_exp * hp_mult // 2)
        atk = int(base_exp * atk_mult // 10)
        
        # 灵石奖励
        stone_reward = int(base_exp * reward_mult // 10)
        
        # Boss防御力（高境界Boss有减伤）
        # 公式: reduction = DEF/(DEF+100), DEF=67→40%, DEF=900→90%
        defense = 0
        if level_config["level_index"] >= 15:  # 炼虚及以上
            defense = random.randint(67, 900)  # 实际减伤 40%~90%
        
        # 创建Boss
        boss = Boss(
            boss_id=0,  # 自动生成
            boss_name=boss_name,
            boss_level=level_config["name"],
            hp=max_hp,
            max_hp=max_hp,
            atk=atk,
            defense=defense,
            stone_reward=stone_reward,
            create_time=int(time.time()),
            status=1  # 1=存活
        )
        
        boss_id = await self.db.ext.create_boss(boss)
        boss.boss_id = boss_id
        
        msg = f"""
👹 Boss降临
━━━━━━━━━━━━━━━

{boss_name}降临世间！

境界：{level_config["name"]}
HP：{max_hp}
ATK：{atk}
防御：{defense}%减伤
奖励：{stone_reward}灵石

快来挑战吧！
        """.strip()
        
        return True, msg, boss
    
    async def challenge_boss(
        self,
        user_id: str
    ) -> Tuple[bool, str, Optional[Dict]]:
        """
        挑战Boss
        
        Args:
            user_id: 挑战者ID
            
        Returns:
            (成功标志, 消息, 战斗结果)
        """
        # 1. 检查玩家
        player = await self.db.get_player_by_id(user_id)
        if not player:
            return False, "❌ 你还未踏入修仙之路！", None
        
        # 2. 检查Boss是否存在
        boss = await self.db.ext.get_active_boss()
        if not boss:
            return False, "❌ 当前没有Boss！", None
        
        # 3. 检查玩家状态
        user_cd = await self.db.ext.get_user_cd(user_id)
        if not user_cd:
            await self.db.ext.create_user_cd(user_id)
            user_cd = await self.db.ext.get_user_cd(user_id)
        
        if user_cd.type != UserStatus.IDLE:
            return False, "❌ 你当前正忙，无法挑战Boss！", None
        
        # 4. 计算玩家战斗属性
        impart_info = await self.db.ext.get_impart_info(user_id)

        # 如果没有初始化战斗属性，先计算并持久化
        if player.hp == 0 or player.mp == 0:
            player_stats = await CombatManager.build_player_combat_stats(player, impart_info, self.config_manager)
            await self.db.update_player(player)
        else:
            # 使用现有属性，仅构建 CombatStats
            player_stats = await CombatManager.build_player_combat_stats(player, impart_info, self.config_manager)
            player_stats.hp = player.hp
            player_stats.mp = player.mp

        # 创建Boss战斗属性（防御转为百分比减伤）
        boss_def_buff = min(0.8, boss.defense / (boss.defense + 100)) if boss.defense > 0 else 0.0
        boss_stats = CombatStats(
            user_id=str(boss.boss_id),
            name=boss.boss_name,
            hp=boss.hp,
            max_hp=boss.max_hp,
            mp=boss.max_hp,  # Boss的MP等于HP
            max_mp=boss.max_hp,
            atk=boss.atk,
            base_def=0,
            equip_def=0,
            def_buff=boss_def_buff,
            crit_rate=30,  # Boss固定30%会心率
            exp=boss.stone_reward  # 奖励存在exp字段
        )
        
        # 查找Boss对应的level_index
        boss_level_index = 0
        for level in self.levels:
            if level["name"] == boss.boss_level:
                boss_level_index = level["level_index"]
                break

        # 5. 开始战斗（含神通支持+Boss特殊能力）
        player_skill = player.shentong if hasattr(player, 'shentong') and player.shentong else ""
        battle_result = self.combat_mgr.player_vs_boss(
            player_stats, boss_stats,
            player_skill_name=player_skill,
            skill_manager=self.skill_manager,
            boss_level_index=boss_level_index
        )
        
        # 6. 处理战斗结果
        winner = battle_result["winner"]
        reward = battle_result["reward"]
        
        if winner == user_id:
            # 玩家胜利 — 乐观锁：仅当Boss仍存活时才发放奖励
            defeated = await self.db.ext.try_defeat_boss(boss.boss_id)
            if not defeated:
                # Boss已被其他玩家击败
                return False, "❌ Boss已被其他玩家抢先击败了！", None

            # 物品掉落
            item_msg = ""
            dropped_items = []
            if self.storage_ring_manager:
                dropped_items = await self._roll_boss_drops(player, boss)
                if dropped_items:
                    item_lines = []
                    for item_name, count in dropped_items:
                        success, _ = await self.storage_ring_manager.store_item(player, item_name, count, silent=True)
                        if success:
                            item_lines.append(f"  · {item_name} x{count}")
                        else:
                            item_lines.append(f"  · {item_name} x{count}（储物戒已满，丢失）")
                    if item_lines:
                        item_msg = "\n\n📦 获得物品：\n" + "\n".join(item_lines)

            # 重新获取玩家数据（store_item 内部已更新了储物戒，需要刷新本地对象）
            player = await self.db.get_player_by_id(user_id) or player
            player.gold += reward

            result_msg = f"""
🎉 挑战成功！
━━━━━━━━━━━━━━━

你成功击败了『{boss.boss_name}』！

战斗回合数：{battle_result['rounds']}
获得灵石：{reward}{item_msg}

{player_stats.name}
HP：{battle_result['player_final_hp']}/{player_stats.max_hp}
            """.strip()
        else:
            # 玩家失败 — 仅当Boss仍存活时更新HP
            boss.hp = battle_result["boss_final_hp"]
            await self.db.ext.update_boss_hp_if_active(boss.boss_id, boss.hp)

            result_msg = f"""
💀 挑战失败
━━━━━━━━━━━━━━━

你被『{boss.boss_name}』击败了！

战斗回合数：{battle_result['rounds']}
安慰奖：{reward}灵石

{boss.boss_name} 剩余HP：{boss.hp}/{boss.max_hp}
            """.strip()

            # 即使失败也给予部分奖励
            if reward > 0:
                player.gold += reward

        # 更新玩家HP/MP
        player.hp = battle_result["player_final_hp"]
        player.mp = battle_result["player_final_mp"]
        await self.db.update_player(player)
        
        # 返回完整战斗日志
        combat_log = "\n".join(battle_result["combat_log"])
        full_msg = combat_log + "\n\n" + result_msg
        
        return True, full_msg, battle_result
    
    async def get_boss_info(self) -> Tuple[bool, str, Optional[Boss]]:
        """
        获取当前Boss信息
        
        Returns:
            (成功标志, 消息, Boss对象)
        """
        boss = await self.db.ext.get_active_boss()
        if not boss:
            return False, "❌ 当前没有Boss！", None
        
        hp_percent = (boss.hp / boss.max_hp) * 100
        
        msg = f"""
👹 当前Boss
━━━━━━━━━━━━━━━

名称：{boss.boss_name}
境界：{boss.boss_level}

HP：{boss.hp}/{boss.max_hp} ({hp_percent:.1f}%)
ATK：{boss.atk}
防御：{boss.defense * 100 // (boss.defense + 100) if boss.defense > 0 else 0}%减伤

奖励：{boss.stone_reward}灵石

使用 /挑战Boss 来挑战！
        """.strip()
        
        return True, msg, boss
    
    async def auto_spawn_boss(self, player_count: int = 0) -> Tuple[bool, str, Optional[Boss]]:
        """
        自动生成Boss（定时任务使用）
        根据服务器玩家数量和平均等级自动调整Boss难度
        
        Args:
            player_count: 玩家数量（用于调整难度）
            
        Returns:
            (成功标志, 消息, Boss对象)
        """
        # 检查是否已有Boss
        existing_boss = await self.db.ext.get_active_boss()
        if existing_boss:
            return False, "当前已有Boss存在", None
        
        # 获取所有玩家的平均等级
        all_players = await self.db.get_all_players()
        if not all_players:
            # 没有玩家，生成低级Boss
            level_config = self.levels[0]
            base_exp = 50000
        else:
            # 计算平均修为
            total_exp = sum(p.experience for p in all_players)
            avg_exp = total_exp // len(all_players) if all_players else 50000

            # 根据平均修为选择Boss等级（用 level_config 的 exp_needed 做阈值）
            level_data = self.config_manager.get_level_data() if self.config_manager else []
            exp_map = {d.get("index", i): d.get("exp_needed", 0) for i, d in enumerate(level_data)}
            for config in reversed(self.levels):
                threshold = exp_map.get(config["level_index"], config["level_index"] * 10000)
                if avg_exp >= threshold:
                    level_config = config
                    break
            else:
                level_config = self.levels[0]
            
            # Boss修为比平均稍高
            base_exp = int(avg_exp * 1.2)
        
        # 生成Boss
        return await self.spawn_boss(base_exp, level_config)
    
    @staticmethod
    def get_drop_tier_for_level(level_index: int) -> str:
        """
        根据等级索引获取掉落档位（与 BOSS_DROP_TABLE 的键一致）

        档位边界：
          - low(≤6)   → 练气~筑基
          - mid(≤12)  → 金丹~化神
          - high(≤33) → 炼虚~天神
          - ultra(>33)→ 虚道~合道
        """
        if level_index <= 6:
            return "low"
        elif level_index <= 12:
            return "mid"
        elif level_index <= 33:
            return "high"
        else:
            return "ultra"

    async def _roll_boss_drops(self, player: Player, boss: Boss) -> List[Tuple[str, int]]:
        """
        根据Boss等级随机掉落物品

        掉落规则:
          - 低档(≤6):   必掉1件
          - 中档(≤12):  必掉1件 + 50%再掉1件
          - 高档(≤33):  必掉2件 + 加权: 60→再掉1件 / 40→再掉2件
          - 超高档(>33): 必掉3件 + 加权: 80→再掉1件 / 60→再掉2件 / 40→再掉3件 / 20→再掉4件

        Args:
            player: 玩家对象
            boss: Boss对象

        Returns:
            掉落物品列表 [(物品名, 数量), ...]
        """
        dropped_items = []

        # 根据Boss等级确定掉落表和掉落规则
        boss_level_index = 0
        for level in self.levels:
            if level["name"] == boss.boss_level:
                boss_level_index = level["level_index"]
                break

        tier = self.get_drop_tier_for_level(boss_level_index)
        drop_table = self.BOSS_DROP_TABLE[tier]

        if tier == "low":  # 练气~筑基 → 低档
            guaranteed = 1
            extra_count = 0  # 无额外

        elif tier == "mid":  # 金丹~化神 → 中档
            guaranteed = 1
            # 50% 固定概率掉1件
            extra_count = 1 if random.randint(1, 100) <= 50 else 0

        elif tier == "high":  # 炼虚~天神 → 高档
            guaranteed = 2
            # 加权选择额外掉落: 60→1件, 40→2件
            extra_count = self._roll_weighted_extra([(60, 1), (40, 2)])

        else:  # ultra → 超高档
            guaranteed = 3
            # 加权选择额外掉落: 80→1件, 60→2件, 40→3件, 20→4件
            extra_count = self._roll_weighted_extra([(80, 1), (60, 2), (40, 3), (20, 4)])

        # 必掉 guaranteed 件
        for _ in range(guaranteed):
            item = self._roll_single_drop(drop_table)
            if item:
                dropped_items.append(item)

        # 额外掉落件
        for _ in range(extra_count):
            item = self._roll_single_drop(drop_table)
            if item:
                dropped_items.append(item)

        return dropped_items

    @staticmethod
    def _roll_weighted_extra(options: List[Tuple[int, int]]) -> int:
        """
        按权重随机选择额外掉落件数

        Args:
            options: [(权重, 掉落件数), ...]

        Returns:
            选中选项的掉落件数
        """
        if not options:
            return 0
        total_weight = sum(w for w, _ in options)
        roll = random.randint(1, total_weight)
        cumulative = 0
        for weight, count in options:
            cumulative += weight
            if roll <= cumulative:
                return count
        return 0

    @staticmethod
    def _roll_single_drop(drop_table: List[Dict]) -> Optional[Tuple[str, int]]:
        """从掉落表中按权重随机选择一件物品"""
        if not drop_table:
            return None
        total_weight = sum(item["weight"] for item in drop_table)
        if total_weight <= 0:
            return None
        roll = random.randint(1, total_weight)
        cumulative = 0
        for item in drop_table:
            cumulative += item["weight"]
            if roll <= cumulative:
                count = random.randint(item["min"], item["max"])
                return (item["name"], count)
        return None
