# data/data_manager.py

import aiosqlite
import json
from dataclasses import fields
from pathlib import Path
from typing import Tuple, List, Optional
from astrbot.api import logger
from ..models import Player
from .database_extended import DatabaseExtended

# 获取 Player 模型的所有字段名（用于过滤数据库中的多余字段，作为迁移未完成时的兼容）
PLAYER_FIELDS = {f.name for f in fields(Player)}

class DataBase:
    """数据库管理类，提供基础玩家操作"""

    def __init__(self, db_file: str = "xiuxian_data_lite.db"):
        self.db_path = Path(db_file)
        self.conn: aiosqlite.Connection = None
        self.ext: Optional[DatabaseExtended] = None  # 扩展操作类

    async def connect(self):
        """连接数据库"""
        self.conn = await aiosqlite.connect(self.db_path)
        self.conn.row_factory = aiosqlite.Row
        self.ext = DatabaseExtended(self.conn)  # 初始化扩展操作

    async def close(self):
        """关闭数据库连接"""
        if self.conn:
            try:
                await self.conn.close()
            finally:
                self.conn = None
                self.ext = None

    async def reconnect(self):
        """重连数据库（用于连接意外断开时）"""
        await self.close()
        await self.connect()

    def _connection_alive(self) -> bool:
        """检测底层aiosqlite连接是否仍然可用"""
        if not self.conn:
            return False
        # aiosqlite Connection 在 close 后会将 _connection 置为 None
        return getattr(self.conn, "_connection", None) is not None

    async def ensure_connection(self):
        """确保数据库连接可用，必要时自动重连"""
        if self._connection_alive():
            return
        logger.warning("[database] 检测到数据库连接断开，正在自动重连...")
        await self.reconnect()

    async def create_player(self, player: Player):
        """创建新玩家"""
        await self.conn.execute(
            """
            INSERT INTO players (
                user_id, level_index, spiritual_root,cultivation_type, user_name, lifespan,
                experience, gold, state, cultivation_start_time, last_check_in_date,
                monthly_sign_count, monthly_sign_month, level_up_rate,
                weapon, armor, main_technique, techniques,
                hp, mp, atk, atkpractice,
                spiritual_qi, max_spiritual_qi, blood_qi, max_blood_qi,
                sect_id, sect_position, sect_contribution, sect_task, sect_elixir_get,
                active_pill_effects, permanent_pill_gains, has_resurrection_pill, has_debuff_shield, pills_inventory,
                storage_ring, storage_ring_items,
                daily_pill_usage, last_daily_reset, shentong, sub_technique,
                permanent_pill_usage, achievement_data, bank_vip_tier,
                daily_activity, daily_activity_points, daily_activity_date, daily_activity_rewarded,
                sleeping_bag_level,
                equipped_weapon, equipped_armor, forging_exp, forging_level
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                player.user_id,
                player.level_index,
                player.spiritual_root,
                player.cultivation_type,
                player.user_name,
                player.lifespan,
                player.experience,
                player.gold,
                player.state,
                player.cultivation_start_time,
                player.last_check_in_date,
                player.monthly_sign_count,
                player.monthly_sign_month,
                player.level_up_rate,
                player.weapon,
                player.armor,
                player.main_technique,
                player.techniques,
                player.hp,
                player.mp,
                player.atk,
                player.atkpractice,
                player.spiritual_qi,
                player.max_spiritual_qi,
                player.blood_qi,
                player.max_blood_qi,
                player.sect_id,
                player.sect_position,
                player.sect_contribution,
                player.sect_task,
                player.sect_elixir_get,
                player.active_pill_effects,
                player.permanent_pill_gains,
                player.has_resurrection_pill,
                int(player.has_debuff_shield),
                player.pills_inventory,
                player.storage_ring,
                player.storage_ring_items,
                player.daily_pill_usage,
                player.last_daily_reset,
                player.shentong,
                player.sub_technique,
                player.permanent_pill_usage,
                player.achievement_data,
                player.bank_vip_tier,
                player.daily_activity,
                player.daily_activity_points,
                player.daily_activity_date,
                player.daily_activity_rewarded,
                player.sleeping_bag_level,
                player.equipped_weapon,
                player.equipped_armor,
                player.forging_exp,
                player.forging_level
            )
        )
        await self.conn.commit()

    async def get_player_by_id(self, user_id: str) -> Optional[Player]:
        """根据用户ID获取玩家信息"""
        async with self.conn.execute(
            "SELECT * FROM players WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                # 过滤掉 Player 模型中不存在的字段（兼容旧数据库/迁移未完成的情况）
                filtered_data = {k: v for k, v in dict(row).items() if k in PLAYER_FIELDS}
                return Player(**filtered_data)
            return None

    async def get_player_by_name(self, user_name: str) -> Optional[Player]:
        """根据道号获取玩家信息"""
        async with self.conn.execute(
            "SELECT * FROM players WHERE user_name = ?",
            (user_name,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                filtered_data = {k: v for k, v in dict(row).items() if k in PLAYER_FIELDS}
                return Player(**filtered_data)
            return None

    async def update_player(self, player: Player, auto_commit: bool = True):
        """更新玩家信息"""
        await self.conn.execute(
            """
            UPDATE players SET
                level_index = ?,
                spiritual_root = ?,
                cultivation_type = ?,
                user_name = ?,
                lifespan = ?,
                experience = ?,
                gold = ?,
                state = ?,
                cultivation_start_time = ?,
                last_check_in_date = ?,
                monthly_sign_count = ?,
                monthly_sign_month = ?,
                level_up_rate = ?,
                weapon = ?,
                armor = ?,
                main_technique = ?,
                techniques = ?,
                shentong = ?,
                hp = ?,
                mp = ?,
                atk = ?,
                atkpractice = ?,
                spiritual_qi = ?,
                max_spiritual_qi = ?,
                blood_qi = ?,
                max_blood_qi = ?,
                sect_id = ?,
                sect_position = ?,
                sect_contribution = ?,
                sect_task = ?,
                sect_elixir_get = ?,
                active_pill_effects = ?,
                permanent_pill_gains = ?,
                has_resurrection_pill = ?,
                has_debuff_shield = ?,
                pills_inventory = ?,
                storage_ring = ?,
                storage_ring_items = ?,
                daily_pill_usage = ?,
                last_daily_reset = ?,
                sub_technique = ?,
                permanent_pill_usage = ?,
                achievement_data = ?,
                bank_vip_tier = ?,
                daily_activity = ?,
                daily_activity_points = ?,
                daily_activity_date = ?,
                daily_activity_rewarded = ?,
                sleeping_bag_level = ?,
                equipped_weapon = ?,
                equipped_armor = ?,
                forging_exp = ?,
                forging_level = ?
            WHERE user_id = ?
            """,
            (
                player.level_index,
                player.spiritual_root,
                player.cultivation_type,
                player.user_name,
                player.lifespan,
                player.experience,
                player.gold,
                player.state,
                player.cultivation_start_time,
                player.last_check_in_date,
                player.monthly_sign_count,
                player.monthly_sign_month,
                player.level_up_rate,
                player.weapon,
                player.armor,
                player.main_technique,
                player.techniques,
                player.shentong,
                player.hp,
                player.mp,
                player.atk,
                player.atkpractice,
                player.spiritual_qi,
                player.max_spiritual_qi,
                player.blood_qi,
                player.max_blood_qi,
                player.sect_id,
                player.sect_position,
                player.sect_contribution,
                player.sect_task,
                player.sect_elixir_get,
                player.active_pill_effects,
                player.permanent_pill_gains,
                player.has_resurrection_pill,
                int(player.has_debuff_shield),
                player.pills_inventory,
                player.storage_ring,
                player.storage_ring_items,
                player.daily_pill_usage,
                player.last_daily_reset,
                player.sub_technique,
                player.permanent_pill_usage,
                player.achievement_data,
                player.bank_vip_tier,
                player.daily_activity,
                player.daily_activity_points,
                player.daily_activity_date,
                player.daily_activity_rewarded,
                player.sleeping_bag_level,
                player.equipped_weapon,
                player.equipped_armor,
                player.forging_exp,
                player.forging_level,
                player.user_id
            )
        )
        if auto_commit:
            await self.conn.commit()

    async def delete_player(self, user_id: str):
        """删除玩家"""
        await self.conn.execute(
            "DELETE FROM players WHERE user_id = ?",
            (user_id,)
        )
        await self.conn.commit()

    async def delete_player_cascade(self, user_id: str):
        """级联删除玩家及所有关联数据（事务保护）

        使用 BEGIN IMMEDIATE 确保原子性：
        - 任何一条 SQL 失败则整体回滚
        - 补全所有关联表（含 player_skills, dungeon_runs, trades, consignment_listings, gm_compensation_claims）
        """
        await self.conn.execute("BEGIN IMMEDIATE")
        try:
            tables = [
                ("DELETE FROM player_skills WHERE user_id = ?", (user_id,)),
                ("DELETE FROM dungeon_runs WHERE user_id = ?", (user_id,)),
                ("UPDATE trades SET status = 'cancelled' WHERE (initiator_id = ? OR target_id = ?) AND status = 'pending'",
                 (user_id, user_id)),
                ("DELETE FROM consignment_listings WHERE seller_id = ?", (user_id,)),
                ("DELETE FROM gm_compensation_claims WHERE user_id = ?", (user_id,)),
                ("DELETE FROM blessed_lands WHERE user_id = ?", (user_id,)),
                ("DELETE FROM spirit_farms WHERE user_id = ?", (user_id,)),
                ("DELETE FROM bank_accounts WHERE user_id = ?", (user_id,)),
                ("UPDATE bank_loans SET status = 'bad_debt' WHERE user_id = ? AND status = 'active'", (user_id,)),
                ("DELETE FROM bounty_tasks WHERE user_id = ?", (user_id,)),
                ("DELETE FROM dual_cultivation WHERE user_id = ?", (user_id,)),
                ("DELETE FROM dual_cultivation_requests WHERE from_id = ? OR target_id = ?", (user_id, user_id)),
                ("DELETE FROM user_cd WHERE user_id = ?", (user_id,)),
                ("DELETE FROM buff_info WHERE user_id = ?", (user_id,)),
                ("DELETE FROM impart_info WHERE user_id = ?", (user_id,)),
                ("DELETE FROM combat_cooldowns WHERE user_id = ?", (user_id,)),
                ("DELETE FROM pending_gifts WHERE sender_id = ? OR receiver_id = ?", (user_id, user_id)),
                ("DELETE FROM player_buffs WHERE user_id = ?", (user_id,)),
                ("DELETE FROM player_daily_activity WHERE user_id = ?", (user_id,)),
                ("DELETE FROM achievement_progress WHERE user_id = ?", (user_id,)),
                ("DELETE FROM weapon_instances WHERE user_id = ?", (user_id,)),
                # players 表最后删除
                ("DELETE FROM players WHERE user_id = ?", (user_id,)),
            ]
            for sql, params in tables:
                await self.conn.execute(sql, params)

            await self.conn.commit()
        except Exception:
            await self.conn.rollback()
            raise

    async def get_all_players(self):
        """获取所有玩家"""
        async with self.conn.execute("SELECT * FROM players") as cursor:
            rows = await cursor.fetchall()
            # 过滤掉 Player 模型中不存在的字段（兼容旧数据库/迁移未完成的情况）
            return [Player(**{k: v for k, v in dict(row).items() if k in PLAYER_FIELDS}) for row in rows]

