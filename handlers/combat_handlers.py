# handlers/combat_handlers.py
import re
import time
from astrbot.api.event import AstrMessageEvent
from astrbot.api.all import *
from ..managers.combat_manager import CombatManager, CombatStats, load_equipment_bonus
from ..data.data_manager import DataBase
from .utils import player_required
from ..models import Player
from ..models_extended import UserStatus

# 战斗冷却配置（秒）
DUEL_COOLDOWN = 300  # 决斗冷却5分钟
SPAR_COOLDOWN = 60   # 切磋冷却1分钟

class CombatHandlers:
    def __init__(self, db: DataBase, combat_mgr: CombatManager, config_manager=None):
        self.db = db
        self.combat_mgr = combat_mgr
        self.config_manager = config_manager
    
    async def _get_combat_cooldown(self, user_id: str) -> dict:
        """获取战斗冷却信息"""
        try:
            async with self.db.conn.execute(
                "SELECT last_duel_time, last_spar_time FROM combat_cooldowns WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {"last_duel_time": row[0], "last_spar_time": row[1]}
        except Exception as e:
            from astrbot.api import logger
            logger.warning(f"获取战斗冷却失败: {e}")
        return {"last_duel_time": 0, "last_spar_time": 0}
    
    async def _update_combat_cooldown(self, user_id: str, combat_type: str):
        """更新战斗冷却时间"""
        now = int(time.time())
        try:
            if combat_type == "duel":
                await self.db.conn.execute(
                    """
                    INSERT INTO combat_cooldowns (user_id, last_duel_time, last_spar_time)
                    VALUES (?, ?, 0)
                    ON CONFLICT(user_id) DO UPDATE SET last_duel_time = ?
                    """,
                    (user_id, now, now)
                )
            else:
                await self.db.conn.execute(
                    """
                    INSERT INTO combat_cooldowns (user_id, last_duel_time, last_spar_time)
                    VALUES (?, 0, ?)
                    ON CONFLICT(user_id) DO UPDATE SET last_spar_time = ?
                    """,
                    (user_id, now, now)
                )
            await self.db.conn.commit()
        except Exception as e:
            from astrbot.api import logger
            logger.warning(f"更新战斗冷却失败: {e}")

    async def _get_target_id(self, event: AstrMessageEvent, arg: str) -> str:
        message_chain = []
        if hasattr(event, "message_obj") and event.message_obj:
            message_chain = getattr(event.message_obj, "message", []) or []

        for component in message_chain:
            if isinstance(component, At):
                candidate = None
                for attr in ("qq", "target", "uin", "user_id"):
                    candidate = getattr(component, attr, None)
                    if candidate:
                        break
                if candidate:
                    return str(candidate).lstrip("@")

        if arg:
            cleaned = arg.strip().lstrip("@")
            if cleaned.isdigit():
                return cleaned

        message_text = ""
        if hasattr(event, "get_message_str"):
            message_text = event.get_message_str() or ""
        match = re.search(r'(\d{5,})', message_text)
        if match:
            return match.group(1)
        return None

    def _calculate_equipment_bonus(self, player) -> dict:
        """计算装备提供的属性加成（委托给共享函数）"""
        return load_equipment_bonus(player, self.config_manager)

    async def _prepare_combat_stats(self, user_id: str) -> CombatStats:
        import math
        player = await self.db.get_player_by_id(user_id)
        if not player:
            return None

        # 获取基础属性
        impart_info = await self.db.ext.get_impart_info(user_id)
        hp_buff = impart_info.impart_hp_per if impart_info else 0.0
        mp_buff = impart_info.impart_mp_per if impart_info else 0.0
        atk_buff = impart_info.impart_atk_per if impart_info else 0.0

        # 计算HP/MP（新公式）
        hp, mp = self.combat_mgr.calculate_hp_mp(player.experience, hp_buff, mp_buff)

        # 计算基础攻击力（新公式：exp^0.35）
        base_atk = self.combat_mgr.calculate_base_atk(player.experience)

        # 装备加成
        equip_bonus = self._calculate_equipment_bonus(player)

        # 突破攻击（物伤+法伤）
        breakthrough_atk = player.physical_damage + player.magic_damage

        # 最终ATK = 经验基数*(1+武器%) + 突破攻击 + 武器攻击
        final_atk = int(base_atk * (1 + equip_bonus["atk_pct"] + atk_buff)) + breakthrough_atk + equip_bonus["atk"]

        # 双层防御
        # 第一层：经验基础防御（ln压缩）
        base_def = math.log(player.experience + 1) * 10
        # 第二层：突破防御 + 装备防御（防具+武器）
        equip_def = (player.physical_defense + player.magic_defense) + equip_bonus["defense"]

        # 更新Player对象
        player.hp = hp
        player.mp = mp
        player.atk = final_atk
        await self.db.update_player(player)

        # 会心率：装备 + 传承buff
        crit_rate_buff = int((impart_info.impart_know_per if impart_info else 0) * 100)

        return CombatStats(
            user_id=user_id,
            name=player.user_name if player.user_name else f"道友{user_id}",
            hp=hp,
            max_hp=hp,
            mp=mp,
            max_mp=mp,
            atk=final_atk,
            defense=equip_def,
            base_def=base_def,
            equip_def=equip_def,
            crit_rate=crit_rate_buff + equip_bonus.get("crit_rate", 0),
            exp=player.experience,
            crit_damage=max(1.5, equip_bonus.get("crit_damage", 0)),
            armor_pen=equip_bonus.get("armor_pen", 0),
            lifesteal=equip_bonus.get("lifesteal", 0),
            double_hit=equip_bonus.get("double_hit", 0),
            dodge_rate=equip_bonus.get("dodge_rate", 0),
            crit_resist=equip_bonus.get("crit_resist", 0),
            reflect_pct=equip_bonus.get("reflect_pct", 0),
            block_value=equip_bonus.get("block_value", 0),
            hp_regen_pct=equip_bonus.get("hp_regen_pct", 0.0),
        )

    async def handle_duel(self, event: AstrMessageEvent, target: str):
        """决斗 (消耗气血)"""
        user_id = event.get_sender_id()
        target_id = await self._get_target_id(event, target)
        
        if not target_id:
            yield event.plain_result("❌ 请指定决斗目标")
            return
            
        if user_id == target_id:
            yield event.plain_result("❌ 不能和自己决斗")
            return

        # 检查发起者状态
        user_cd = await self.db.ext.get_user_cd(user_id)
        if user_cd and user_cd.type != UserStatus.IDLE:
            current_status = UserStatus.get_name(user_cd.type)
            yield event.plain_result(f"❌ 你当前正在{current_status}，无法进行战斗！")
            return
        
        # 检查目标状态
        target_cd = await self.db.ext.get_user_cd(target_id)
        if target_cd and target_cd.type != UserStatus.IDLE:
            target_status = UserStatus.get_name(target_cd.type)
            yield event.plain_result(f"❌ 对方当前正在{target_status}，无法进行战斗！")
            return

        # 检查冷却
        now = int(time.time())
        cooldown = await self._get_combat_cooldown(user_id)
        last_duel = cooldown.get("last_duel_time", 0)
        if last_duel and (now - last_duel) < DUEL_COOLDOWN:
            remaining = DUEL_COOLDOWN - (now - last_duel)
            yield event.plain_result(f"❌ 决斗冷却中，还需 {remaining // 60} 分 {remaining % 60} 秒")
            return

        # 获取双方数据
        p1_stats = await self._prepare_combat_stats(user_id)
        p2_stats = await self._prepare_combat_stats(target_id)
        
        if not p1_stats:
            yield event.plain_result("❌ 你还未踏入修仙之路")
            return
        if not p2_stats:
            yield event.plain_result("❌ 对方还未踏入修仙之路")
            return

        # 战斗
        result = self.combat_mgr.player_vs_player(p1_stats, p2_stats, combat_type=2) # 2=决斗
        
        # 结算（更新HP）
        await self.db.ext.update_player_hp_mp(user_id, result['player1_final_hp'], result['player1_final_mp'])
        await self.db.ext.update_player_hp_mp(target_id, result['player2_final_hp'], result['player2_final_mp'])
        
        # 更新冷却
        await self._update_combat_cooldown(user_id, "duel")
        
        # 生成战报
        log = "\n".join(result['combat_log'])
        yield event.plain_result(f"{log}")

    async def handle_spar(self, event: AstrMessageEvent, target: str):
        """切磋 (不消耗气血)"""
        user_id = event.get_sender_id()
        target_id = await self._get_target_id(event, target)
        
        if not target_id:
            yield event.plain_result("❌ 请指定切磋目标")
            return

        if user_id == target_id:
            yield event.plain_result("❌ 不能和自己切磋")
            return

        # 检查发起者状态
        user_cd = await self.db.ext.get_user_cd(user_id)
        if user_cd and user_cd.type != UserStatus.IDLE:
            current_status = UserStatus.get_name(user_cd.type)
            yield event.plain_result(f"❌ 你当前正在{current_status}，无法进行战斗！")
            return
        
        # 检查目标状态
        target_cd = await self.db.ext.get_user_cd(target_id)
        if target_cd and target_cd.type != UserStatus.IDLE:
            target_status = UserStatus.get_name(target_cd.type)
            yield event.plain_result(f"❌ 对方当前正在{target_status}，无法进行战斗！")
            return

        # 检查冷却
        now = int(time.time())
        cooldown = await self._get_combat_cooldown(user_id)
        last_spar = cooldown.get("last_spar_time", 0)
        if last_spar and (now - last_spar) < SPAR_COOLDOWN:
            remaining = SPAR_COOLDOWN - (now - last_spar)
            yield event.plain_result(f"❌ 切磋冷却中，还需 {remaining} 秒")
            return

        p1_stats = await self._prepare_combat_stats(user_id)
        p2_stats = await self._prepare_combat_stats(target_id)
        
        if not p1_stats or not p2_stats:
             yield event.plain_result("❌ 双方都需要踏入修仙之路")
             return

        result = self.combat_mgr.player_vs_player(p1_stats, p2_stats, combat_type=1) # 1=切磋
        
        # 更新冷却
        await self._update_combat_cooldown(user_id, "spar")
        
        log = "\n".join(result['combat_log'])
        yield event.plain_result(f"{log}")
