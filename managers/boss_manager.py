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

    # ── v4.3.6 伤害贡献与挑战成本参数 ──
    # [PLACEHOLDER] 以下数值未经 playtest 校准，按 10-50 人在线规模预估
    CHALLENGE_COOLDOWN = 300          # 每人对同一Boss的挑战冷却（秒），防无限磨血
    DAMAGE_SHARE_THRESHOLD = 0.05     # 伤害占Boss最大HP ≥5% 才算有效参与者（可分灵石/参与掉落roll）
    KILLER_STONE_SHARE = 0.30         # 击杀者灵石保底占比，其余按伤害占比分配
    KILLER_DROP_GUARANTEE = 1         # 击杀者保底掉落件数

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
    # v4.3.3: 移除幽灵物品"灵草"（items.json 中不存在，旧历练体系残留），
    #         权重让给锻造材料；灵兽骨下沉至 low/mid 档（解锁修士袍配方），
    #         天火熔晶下沉至 high 档（弥合 Lv5 配方中期断层）。
    BOSS_DROP_TABLE = {
        "low": [  # boss_level_index ≤ 6
            {"name": "精铁", "weight": 42, "min": 1, "max": 3},
            {"name": "百年灵草", "weight": 28, "min": 1, "max": 2},
            {"name": "紫金沙", "weight": 10, "min": 1, "max": 1},
            {"name": "灵兽骨", "weight": 10, "min": 1, "max": 1},
        ],
        "mid": [  # boss_level_index ≤ 12
            {"name": "精铁", "weight": 22, "min": 2, "max": 5},
            {"name": "百年灵草", "weight": 16, "min": 2, "max": 4},
            {"name": "紫金沙", "weight": 16, "min": 1, "max": 3},
            {"name": "魔核碎片", "weight": 13, "min": 1, "max": 2},
            {"name": "赤炎石", "weight": 13, "min": 1, "max": 2},
            {"name": "灵兽骨", "weight": 10, "min": 1, "max": 2},
        ],
        "high": [  # boss_level_index ≤ 33
            {"name": "精铁", "weight": 15, "min": 5, "max": 15},
            {"name": "百年灵草", "weight": 10, "min": 5, "max": 10},
            {"name": "紫金沙", "weight": 15, "min": 2, "max": 5},
            {"name": "魔核碎片", "weight": 15, "min": 2, "max": 4},
            {"name": "赤炎石", "weight": 15, "min": 2, "max": 4},
            {"name": "亡者之息", "weight": 11, "min": 1, "max": 3},
            {"name": "幽魂草", "weight": 11, "min": 1, "max": 3},
            {"name": "灵兽骨", "weight": 10, "min": 1, "max": 2},
            {"name": "天火熔晶", "weight": 7, "min": 1, "max": 2},
        ],
        "ultra": [  # boss_level_index > 33
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

        # 3.5 挑战冷却检查（v4.3.6）：以 boss_damage_log.update_time 作为上次挑战时间
        damage_log = await self.db.ext.get_boss_damage_log(boss.boss_id)
        import time as _time
        now_ts = int(_time.time())
        my_prev = next((row for row in damage_log if row[0] == user_id), None)
        if my_prev and (now_ts - my_prev[2]) < self.CHALLENGE_COOLDOWN:
            remain = self.CHALLENGE_COOLDOWN - (now_ts - my_prev[2])
            return False, f"⏳ 挑战冷却中，还需等待 {remain // 60 + (1 if remain % 60 else 0)} 分钟。", None

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
        boss_hp_before = boss.hp
        battle_result = self.combat_mgr.player_vs_boss(
            player_stats, boss_stats,
            player_skill_name=player_skill,
            skill_manager=self.skill_manager,
            boss_level_index=boss_level_index
        )

        # 6. 处理战斗结果
        winner = battle_result["winner"]
        reward = battle_result["reward"]
        my_damage = max(0, boss_hp_before - battle_result["boss_final_hp"])
        battle_result["my_damage"] = my_damage

        # 6a. 记录伤害贡献（v4.3.6，胜负都记；update_time 兼作冷却时间戳）
        await self.db.ext.add_boss_damage(boss.boss_id, user_id, my_damage, now_ts)

        if winner == user_id:
            # 玩家胜利 — 乐观锁：仅当Boss仍存活时才发放奖励
            defeated = await self.db.ext.try_defeat_boss(boss.boss_id)
            if not defeated:
                # Boss已被其他玩家击败
                return False, "❌ Boss已被其他玩家抢先击败了！", None

            # 伤害贡献加权分配（v4.3.6）：击杀者保底 + 按伤害占比分配给有效参与者
            my_stone, my_drops, top_names = await self._distribute_rewards(
                boss, user_id, damage_log
            )
            battle_result["boss_top"] = top_names  # [(user_id, damage)] 供全服公告

            # 分配后刷新外层对象：_distribute_rewards 内部已写库（灵石/储物戒），
            # 下方 HP/MP 更新必须基于最新对象，否则旧 gold 会覆盖分配结果
            player = await self.db.get_player_by_id(user_id) or player

            top_desc = ""
            if top_names:
                top_desc = "\n\n🏆 贡献榜 TOP3：\n" + "\n".join(
                    f"  {i + 1}. {name} — {dmg:,} 伤害"
                    for i, (name, dmg) in enumerate(top_names)
                )

            drop_desc = ""
            if my_drops:
                drop_desc = "\n📦 你分得物品：\n" + "\n".join(f"  · {x}" for x in my_drops)

            result_msg = f"""
🎉 挑战成功！
━━━━━━━━━━━━━━━

你成功击败了『{boss.boss_name}』！

战斗回合数：{battle_result['rounds']}
本轮伤害：{my_damage:,}
分得灵石：{my_stone:,}{drop_desc}{top_desc}

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
本轮伤害：{my_damage:,}（已计入贡献榜）
安慰奖：{reward}灵石

{boss.boss_name} 剩余HP：{boss.hp}/{boss.max_hp}
距离击杀还差 {boss.hp:,} 点伤害
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

    async def _distribute_rewards(
        self, boss: Boss, killer_id: str, damage_log: list
    ) -> Tuple[int, list, list]:
        """按伤害贡献加权分配灵石与掉落（v4.3.6）

        规则：
          - 灵石：击杀者保底 KILLER_STONE_SHARE，其余按伤害占比分配给
            伤害 ≥ max_hp * DAMAGE_SHARE_THRESHOLD 的有效参与者
          - 掉落：击杀者保底 KILLER_DROP_GUARANTEE 件，剩余件数按伤害占比
            加权随机分配给所有有效参与者（含击杀者）

        Args:
            boss: 已被击杀的Boss对象
            killer_id: 击杀者ID
            damage_log: 击杀前读取的伤害贡献列表 [(user_id, damage, update_time)]

        Returns:
            (击杀者分得灵石, 击杀者分得物品描述列表, 贡献TOP3 [(user_id, damage)])
        """
        damage_log = damage_log or await self.db.ext.get_boss_damage_log(boss.boss_id)
        threshold = max(1, int(boss.max_hp * self.DAMAGE_SHARE_THRESHOLD))
        eligible = [(uid, dmg) for uid, dmg, _ in damage_log if dmg >= threshold]
        if not eligible:
            # 兜底：无人达标时全部归击杀者
            eligible = [(killer_id, 1)]
        eligible_total = sum(d for _, d in eligible) or 1

        # ── 灵石分配 ──
        killer_stone = int(boss.stone_reward * self.KILLER_STONE_SHARE)
        pool_stone = boss.stone_reward - killer_stone
        stone_gain = {}
        for uid, dmg in eligible:
            stone_gain[uid] = stone_gain.get(uid, 0) + pool_stone * dmg // eligible_total
        stone_gain[killer_id] = stone_gain.get(killer_id, 0) + killer_stone

        # ── 掉落分配 ──
        drops = await self._roll_boss_drops(None, boss)
        drop_gain = {}
        for name, cnt in drops[: self.KILLER_DROP_GUARANTEE]:
            drop_gain.setdefault(killer_id, []).append((name, cnt))
        w_total = float(eligible_total)
        for name, cnt in drops[self.KILLER_DROP_GUARANTEE:]:
            roll = random.uniform(0, w_total)
            acc = 0.0
            for uid, dmg in eligible:
                acc += dmg
                if roll <= acc:
                    drop_gain.setdefault(uid, []).append((name, cnt))
                    break

        # ── 入库 ──
        # 顺序关键：先写 gold 再 store_item（store_item 内部会重新读取最新玩家
        # 对象并整行 update，若 gold 写在其后且用旧对象，会吞掉储物戒写入）
        my_stone = 0
        my_drops = []
        for uid in sorted(set(list(stone_gain.keys()) + list(drop_gain.keys()))):
            stones = stone_gain.get(uid, 0)
            got_items = drop_gain.get(uid, [])
            if stones <= 0 and not got_items:
                continue
            p = await self.db.get_player_by_id(uid)
            if not p:
                continue
            if stones > 0:
                p.gold += stones
                await self.db.update_player(p)
            got_desc = []
            for name, cnt in got_items:
                if self.storage_ring_manager:
                    ok, _ = await self.storage_ring_manager.store_item(p, name, cnt, silent=True)
                    got_desc.append(f"{name} x{cnt}" + ("" if ok else "（储物戒已满，丢失）"))
                else:
                    got_desc.append(f"{name} x{cnt}")
            if uid == killer_id:
                my_stone = stones
                my_drops = got_desc

        # ── 贡献TOP3（按ID回查名字由调用方/公告层处理，这里返回ID）──
        top_names = [(uid, dmg) for uid, dmg, _ in damage_log[:3]]

        # ── 清理伤害日志（防膨胀；击杀分配完毕后记录失效）──
        await self.db.ext.clear_boss_damage_log(boss.boss_id)
        return my_stone, my_drops, top_names
    
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

        # 贡献榜 TOP3（v4.3.6）
        top_lines = ""
        damage_log = await self.db.ext.get_boss_damage_log(boss.boss_id)
        if damage_log:
            top_lines = "\n🏆 当前贡献榜 TOP3：\n"
            for i, (uid, dmg, _) in enumerate(damage_log[:3]):
                p = await self.db.get_player_by_id(uid)
                name = (p.user_name if p and p.user_name else f"道友{uid[:6]}")
                top_lines += f"  {i + 1}. {name} — {dmg:,} 伤害\n"
            threshold = max(1, int(boss.max_hp * self.DAMAGE_SHARE_THRESHOLD))
            top_lines += f"（伤害≥{threshold:,} 可参与击杀奖励分配）\n"

        msg = f"""
👹 当前Boss
━━━━━━━━━━━━━━━

名称：{boss.boss_name}
境界：{boss.boss_level}

HP：{boss.hp}/{boss.max_hp} ({hp_percent:.1f}%)
ATK：{boss.atk}
防御：{boss.defense * 100 // (boss.defense + 100) if boss.defense > 0 else 0}%减伤

奖励：{boss.stone_reward}灵石
{top_lines}
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
