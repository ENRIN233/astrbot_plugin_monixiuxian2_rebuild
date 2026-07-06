# data/database_extended.py
"""
扩展数据库操作类，包含宗门、Boss、秘境等新系统的CRUD方法
"""

import aiosqlite
import json
from contextlib import asynccontextmanager
from dataclasses import fields
from typing import List, Optional, AsyncGenerator
from ..models_extended import (
    Sect, BuffInfo, Boss, Rift, ImpartInfo, UserCd, DungeonRun
)


class DatabaseExtended:
    """数据库扩展操作类"""

    def __init__(self, conn: aiosqlite.Connection):
        self.conn = conn

    @asynccontextmanager
    async def immediate_transaction(self) -> AsyncGenerator[None, None]:
        """BEGIN IMMEDIATE 事务上下文管理器

        所有多步写操作必须使用此上下文管理器包裹，
        确保原子性和高并发下避免死锁（DEFERRED 可能死锁）。

        用法:
            async with db.ext.immediate_transaction():
                await db.conn.execute(...)
        """
        await self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield
            await self.conn.commit()
        except Exception:
            await self.conn.rollback()
            raise
    
    # ===== 宗门系统 CRUD =====
    
    async def create_sect(self, sect: Sect):
        """创建宗门"""
        await self.conn.execute(
            """
            INSERT INTO sects (
                sect_name, sect_owner, sect_scale, sect_used_stone,
                sect_fairyland, sect_materials, mainbuff, secbuff, elixir_room_level
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sect.sect_name, sect.sect_owner, sect.sect_scale,
                sect.sect_used_stone, sect.sect_fairyland, sect.sect_materials,
                sect.mainbuff, sect.secbuff, sect.elixir_room_level
            )
        )
        await self.conn.commit()
        
        # 获取刚插入的sect_id
        async with self.conn.execute("SELECT last_insert_rowid()") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None
    
    async def get_sect_by_id(self, sect_id: int) -> Optional[Sect]:
        """根据ID获取宗门信息"""
        async with self.conn.execute(
            "SELECT * FROM sects WHERE sect_id = ?",
            (sect_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return Sect(**dict(row))
            return None
    
    async def get_sect_by_owner(self, owner_id: str) -> Optional[Sect]:
        """根据宗主ID获取宗门信息"""
        async with self.conn.execute(
            "SELECT * FROM sects WHERE sect_owner = ?",
            (owner_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return Sect(**dict(row))
            return None
    
    async def get_sect_by_name(self, sect_name: str) -> Optional[Sect]:
        """根据宗门名称获取宗门信息"""
        async with self.conn.execute(
            "SELECT * FROM sects WHERE sect_name = ?",
            (sect_name,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return Sect(**dict(row))
            return None
    
    async def update_sect(self, sect: Sect):
        """更新宗门信息"""
        await self.conn.execute(
            """
            UPDATE sects SET
                sect_name = ?, sect_owner = ?, sect_scale = ?, sect_used_stone = ?,
                sect_fairyland = ?, sect_materials = ?, mainbuff = ?, secbuff = ?,
                elixir_room_level = ?
            WHERE sect_id = ?
            """,
            (
                sect.sect_name, sect.sect_owner, sect.sect_scale,
                sect.sect_used_stone, sect.sect_fairyland, sect.sect_materials,
                sect.mainbuff, sect.secbuff, sect.elixir_room_level,
                sect.sect_id
            )
        )
        await self.conn.commit()
    
    async def delete_sect(self, sect_id: int):
        """删除宗门"""
        await self.conn.execute("DELETE FROM sects WHERE sect_id = ?", (sect_id,))
        await self.conn.commit()
    
    async def get_all_sects(self) -> List[Sect]:
        """获取所有宗门"""
        async with self.conn.execute("SELECT * FROM sects ORDER BY sect_scale DESC") as cursor:
            rows = await cursor.fetchall()
            return [Sect(**dict(row)) for row in rows]
    
    async def update_sect_materials(self, sect_id: int, materials: int, operation: int = 1):
        """更新宗门资材
        
        Args:
            sect_id: 宗门ID
            materials: 资材数量
            operation: 1=增加, 2=减少
        """
        if operation == 1:
            await self.conn.execute(
                "UPDATE sects SET sect_materials = sect_materials + ? WHERE sect_id = ?",
                (materials, sect_id)
            )
        else:
            await self.conn.execute(
                "UPDATE sects SET sect_materials = sect_materials - ? WHERE sect_id = ?",
                (materials, sect_id)
            )
        await self.conn.commit()
    
    async def donate_to_sect(self, sect_id: int, stone_num: int):
        """宗门捐献（增加灵石和建设度）"""
        await self.conn.execute(
            """
            UPDATE sects SET 
                sect_used_stone = sect_used_stone + ?,
                sect_scale = sect_scale + ?
            WHERE sect_id = ?
            """,
            (stone_num, stone_num * 10, sect_id)  # 1灵石 = 10建设度
        )
        await self.conn.commit()
    
    # ===== BuffInfo 系统 CRUD =====
    
    async def create_buff_info(self, user_id: str):
        """初始化用户的buff信息"""
        await self.conn.execute(
            """
            INSERT INTO buff_info (
                user_id, main_buff, sec_buff, faqi_buff, fabao_weapon,
                armor_buff, atk_buff, sub_buff
            ) VALUES (?, 0, 0, 0, 0, 0, 0, 0)
            """,
            (user_id,)
        )
        await self.conn.commit()

    async def get_buff_info(self, user_id: str) -> Optional[BuffInfo]:
        """获取用户buff信息"""
        async with self.conn.execute(
            "SELECT * FROM buff_info WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                # 过滤掉 BuffInfo 中不存在的字段（如已废弃的 blessed_spot）
                valid_fields = {f.name for f in fields(BuffInfo)}
                return BuffInfo(**{k: v for k, v in dict(row).items() if k in valid_fields})
            return None
    
    async def update_buff_info(self, buff_info: BuffInfo):
        """更新用户buff信息"""
        await self.conn.execute(
            """
            UPDATE buff_info SET
                main_buff = ?, sec_buff = ?, faqi_buff = ?, fabao_weapon = ?,
                armor_buff = ?, atk_buff = ?, sub_buff = ?
            WHERE user_id = ?
            """,
            (
                buff_info.main_buff, buff_info.sec_buff, buff_info.faqi_buff,
                buff_info.fabao_weapon, buff_info.armor_buff, buff_info.atk_buff,
                buff_info.sub_buff, buff_info.user_id
            )
        )
        await self.conn.commit()
    
    async def update_user_main_buff(self, user_id: str, buff_id: int):
        """更新用户主修功法"""
        await self.conn.execute(
            "UPDATE buff_info SET main_buff = ? WHERE user_id = ?",
            (buff_id, user_id)
        )
        await self.conn.commit()
    
    async def update_user_sec_buff(self, user_id: str, buff_id: int):
        """更新用户辅修功法"""
        await self.conn.execute(
            "UPDATE buff_info SET sec_buff = ? WHERE user_id = ?",
            (buff_id, user_id)
        )
        await self.conn.commit()
    
    # ===== Boss 系统 CRUD =====
    
    async def create_boss(self, boss: Boss) -> int:
        """创建Boss"""
        await self.conn.execute(
            """
            INSERT INTO boss (
                boss_name, boss_level, hp, max_hp, atk, defense,
                stone_reward, create_time, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                boss.boss_name, boss.boss_level, boss.hp, boss.max_hp,
                boss.atk, boss.defense, boss.stone_reward,
                boss.create_time, boss.status
            )
        )
        await self.conn.commit()
        
        async with self.conn.execute("SELECT last_insert_rowid()") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None
    
    async def get_active_boss(self) -> Optional[Boss]:
        """获取当前存活的Boss"""
        async with self.conn.execute(
            "SELECT * FROM boss WHERE status = 1 ORDER BY create_time DESC LIMIT 1"
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return Boss(**dict(row))
            return None
    
    async def get_boss_by_id(self, boss_id: int) -> Optional[Boss]:
        """根据ID获取Boss信息"""
        async with self.conn.execute(
            "SELECT * FROM boss WHERE boss_id = ?",
            (boss_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return Boss(**dict(row))
            return None
    
    async def update_boss(self, boss: Boss):
        """更新Boss信息"""
        await self.conn.execute(
            """
            UPDATE boss SET
                boss_name = ?, boss_level = ?, hp = ?, max_hp = ?, atk = ?,
                defense = ?, stone_reward = ?, status = ?
            WHERE boss_id = ?
            """,
            (
                boss.boss_name, boss.boss_level, boss.hp, boss.max_hp,
                boss.atk, boss.defense, boss.stone_reward, boss.status,
                boss.boss_id
            )
        )
        await self.conn.commit()
    
    async def defeat_boss(self, boss_id: int):
        """标记Boss为已击败"""
        await self.conn.execute(
            "UPDATE boss SET status = 0 WHERE boss_id = ?",
            (boss_id,)
        )
        await self.conn.commit()

    async def update_boss_hp_if_active(self, boss_id: int, hp: int) -> bool:
        """仅当Boss仍存活时更新HP（防止已被击败的Boss被重新激活）

        Returns:
            True if updated, False if boss was already defeated
        """
        cursor = await self.conn.execute(
            "UPDATE boss SET hp = ? WHERE boss_id = ? AND status = 1",
            (hp, boss_id)
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def try_defeat_boss(self, boss_id: int) -> bool:
        """尝试标记Boss为已击败（乐观锁：仅当Boss仍存活时生效）

        Returns:
            True if the boss was successfully defeated (was active), False if already defeated
        """
        cursor = await self.conn.execute(
            "UPDATE boss SET status = 0 WHERE boss_id = ? AND status = 1",
            (boss_id,)
        )
        await self.conn.commit()
        return cursor.rowcount > 0
    
    # ===== 秘境系统 CRUD =====
    
    async def create_rift(self, rift: Rift) -> int:
        """创建秘境"""
        await self.conn.execute(
            """
            INSERT INTO rifts (
                rift_name, rift_level, required_level, rewards
            ) VALUES (?, ?, ?, ?)
            """,
            (rift.rift_name, rift.rift_level, rift.required_level, rift.rewards)
        )
        await self.conn.commit()
        
        async with self.conn.execute("SELECT last_insert_rowid()") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None
    
    async def get_rift_by_id(self, rift_id: int) -> Optional[Rift]:
        """根据ID获取秘境信息"""
        async with self.conn.execute(
            "SELECT * FROM rifts WHERE rift_id = ?",
            (rift_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return Rift(**dict(row))
            return None
    
    async def get_all_rifts(self) -> List[Rift]:
        """获取所有秘境"""
        async with self.conn.execute(
            "SELECT * FROM rifts ORDER BY rift_level ASC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [Rift(**dict(row)) for row in rows]
    
    # ===== 传承系统 CRUD =====
    
    async def create_impart_info(self, user_id: str):
        """初始化用户传承信息"""
        await self.conn.execute(
            """
            INSERT INTO impart_info (
                user_id, impart_hp_per, impart_mp_per, impart_atk_per,
                impart_know_per, impart_burst_per
            ) VALUES (?, 0.0, 0.0, 0.0, 0.0, 0.0)
            """,
            (user_id,)
        )
        await self.conn.commit()
    
    async def get_impart_info(self, user_id: str) -> Optional[ImpartInfo]:
        """获取用户传承信息"""
        async with self.conn.execute(
            "SELECT * FROM impart_info WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return ImpartInfo(**dict(row))
            return None
    
    async def update_impart_info(self, impart: ImpartInfo):
        """更新用户传承信息"""
        await self.conn.execute(
            """
            UPDATE impart_info SET
                impart_hp_per = ?, impart_mp_per = ?, impart_atk_per = ?,
                impart_know_per = ?, impart_burst_per = ?
            WHERE user_id = ?
            """,
            (
                impart.impart_hp_per, impart.impart_mp_per, impart.impart_atk_per,
                impart.impart_know_per, impart.impart_burst_per, impart.user_id
            )
        )
        await self.conn.commit()
    
    # ===== 用户CD系统 CRUD =====
    
    async def create_user_cd(self, user_id: str):
        """初始化用户CD信息"""
        await self.conn.execute(
            """
            INSERT INTO user_cd (user_id, type, create_time, scheduled_time)
            VALUES (?, 0, 0, 0)
            """,
            (user_id,)
        )
        await self.conn.commit()
    
    async def get_user_cd(self, user_id: str) -> Optional[UserCd]:
        """获取用户CD信息"""
        async with self.conn.execute(
            "SELECT * FROM user_cd WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return UserCd(**dict(row))
            return None
    
    async def update_user_cd(self, user_cd: UserCd):
        """更新用户CD信息"""
        await self.conn.execute(
            """
            UPDATE user_cd SET
                type = ?, create_time = ?, scheduled_time = ?, extra_data = ?
            WHERE user_id = ?
            """,
            (user_cd.type, user_cd.create_time, user_cd.scheduled_time, user_cd.extra_data, user_cd.user_id)
        )
        await self.conn.commit()
    
    async def set_user_busy(self, user_id: str, busy_type: int, scheduled_time: int = 0, extra_data: dict = None, auto_commit: bool = True):
        """设置用户忙碌状态

        Args:
            user_id: 用户ID
            busy_type: 0=空闲, 1=闭关, 2=历练, 3=探索秘境
            scheduled_time: 计划完成时间戳
            extra_data: 额外数据（如秘境ID等）
            auto_commit: 是否自动提交（False时由外部事务管理）
        """
        import time
        import json
        extra_json = json.dumps(extra_data or {}, ensure_ascii=False)
        await self.conn.execute(
            """
            UPDATE user_cd SET type = ?, create_time = ?, scheduled_time = ?, extra_data = ?
            WHERE user_id = ?
            """,
            (busy_type, int(time.time()), scheduled_time, extra_json, user_id)
        )
        if auto_commit:
            await self.conn.commit()
    
    async def set_user_free(self, user_id: str):
        """设置用户为空闲状态"""
        await self.set_user_busy(user_id, 0, 0)
    
    # ===== Player扩展字段更新方法 =====
    
    async def update_player_hp_mp(self, user_id: str, hp: int, mp: int, auto_commit: bool = True):
        """更新玩家HP和MP"""
        await self.conn.execute(
            "UPDATE players SET hp = ?, mp = ? WHERE user_id = ?",
            (max(1, hp), max(0, mp), user_id)
        )
        if auto_commit:
            await self.conn.commit()
    
    async def update_player_sect_info(self, user_id: str, sect_id: int, sect_position: int):
        """更新玩家宗门信息"""
        await self.conn.execute(
            "UPDATE players SET sect_id = ?, sect_position = ? WHERE user_id = ?",
            (sect_id, sect_position, user_id)
        )
        await self.conn.commit()
    
    async def update_player_sect_contribution(self, user_id: str, contribution: int):
        """更新玩家宗门贡献度"""
        await self.conn.execute(
            "UPDATE players SET sect_contribution = ? WHERE user_id = ?",
            (contribution, user_id)
        )
        await self.conn.commit()
    
    async def increment_sect_task_count(self, user_id: str, count: int = 1):
        """增加宗门任务完成次数"""
        await self.conn.execute(
            "UPDATE players SET sect_task = sect_task + ? WHERE user_id = ?",
            (count, user_id)
        )
        await self.conn.commit()
    
    async def reset_sect_tasks(self):
        """重置所有用户的宗门任务次数（定时任务）"""
        await self.conn.execute("UPDATE players SET sect_task = 0")
        await self.conn.commit()
    
    async def reset_sect_elixir_get(self):
        """重置所有用户的宗门丹药领取标记（定时任务）"""
        await self.conn.execute("UPDATE players SET sect_elixir_get = 0")
        await self.conn.commit()
    
    async def get_sect_members(self, sect_id: int) -> List:
        """获取宗门所有成员"""
        from ..models import Player
        async with self.conn.execute(
            "SELECT * FROM players WHERE sect_id = ? ORDER BY sect_position ASC, level_index DESC",
            (sect_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            # 简化返回，只返回部分字段
            from dataclasses import fields
            PLAYER_FIELDS = {f.name for f in fields(Player)}
            return [Player(**{k: v for k, v in dict(row).items() if k in PLAYER_FIELDS}) for row in rows]

    async def get_all_sects_summary(self) -> List[dict]:
        """获取所有宗门的摘要信息（用于资材发放和自动换宗主）"""
        async with self.conn.execute(
            "SELECT sect_id, sect_name, sect_owner, sect_scale, sect_materials FROM sects"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def update_sect_name(self, sect_id: int, new_name: str) -> bool:
        """更新宗门名称，返回是否成功（名称重复则失败）"""
        try:
            await self.conn.execute(
                "UPDATE sects SET sect_name = ? WHERE sect_id = ?",
                (new_name, sect_id)
            )
            await self.conn.commit()
            return True
        except Exception:
            return False

    async def update_player_elixir_get(self, user_id: str, value: int = 1):
        """更新玩家丹药领取标记"""
        await self.conn.execute(
            "UPDATE players SET sect_elixir_get = ? WHERE user_id = ?",
            (value, user_id)
        )
        await self.conn.commit()

    async def update_user_atkpractice(self, user_id: str, level: int):
        """更新攻击修炼等级"""
        await self.conn.execute(
            "UPDATE players SET atkpractice = ? WHERE user_id = ?",
            (level, user_id)
        )
        await self.conn.commit()

    # ===== Phase 2: 灵石银行 CRUD =====
    
    async def get_bank_account(self, user_id: str) -> Optional[dict]:
        """获取银行账户信息"""
        async with self.conn.execute(
            "SELECT balance, last_interest_time FROM bank_accounts WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"balance": row[0], "last_interest_time": row[1]}
            return None
    
    async def update_bank_account(self, user_id: str, balance: int, last_interest_time: int, auto_commit: bool = True):
        """更新或创建银行账户"""
        await self.conn.execute(
            """
            INSERT INTO bank_accounts (user_id, balance, last_interest_time)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                balance = excluded.balance,
                last_interest_time = excluded.last_interest_time
            """,
            (user_id, balance, last_interest_time)
        )
        if auto_commit:
            await self.conn.commit()
    
    # ===== Phase 2: 悬赏令系统 CRUD =====
    
    async def ensure_bounty_tables(self):
        """确保悬赏系统表存在（运行时检查）"""
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS bounty_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                bounty_id INTEGER NOT NULL,
                bounty_name TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_count INTEGER NOT NULL,
                current_progress INTEGER NOT NULL DEFAULT 0,
                rewards TEXT NOT NULL DEFAULT '{}',
                start_time INTEGER NOT NULL,
                expire_time INTEGER NOT NULL,
                status INTEGER NOT NULL DEFAULT 1
            )
        """)
        await self.conn.execute("CREATE INDEX IF NOT EXISTS idx_bounty_user ON bounty_tasks(user_id)")
        await self.conn.commit()
    
    async def get_active_bounty(self, user_id: str) -> Optional[dict]:
        """获取用户当前进行中的悬赏任务"""
        await self.ensure_bounty_tables()  # 确保表存在
        async with self.conn.execute(
            "SELECT * FROM bounty_tasks WHERE user_id = ? AND status = 1",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    async def create_bounty(self, user_id: str, bounty_id: int, bounty_name: str, 
                           target_type: str, target_count: int, rewards: str, 
                           expire_time: int):
        """创建悬赏任务"""
        import time
        await self.conn.execute(
            """
            INSERT INTO bounty_tasks (
                user_id, bounty_id, bounty_name, target_type, 
                target_count, current_progress, rewards, 
                start_time, expire_time, status
            ) VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, 1)
            """,
            (user_id, bounty_id, bounty_name, target_type, 
             target_count, rewards, int(time.time()), expire_time)
        )
        await self.conn.commit()
    
    async def get_expired_bounty(self, user_id: str) -> Optional[dict]:
        """获取用户已过期但未领取的悬赏任务"""
        await self.ensure_bounty_tables()
        async with self.conn.execute(
            "SELECT * FROM bounty_tasks WHERE user_id = ? AND status = 3",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def complete_bounty(self, user_id: str) -> bool:
        """完成悬赏任务，返回是否真的有进行中的悬赏被完成"""
        cursor = await self.conn.execute(
            "UPDATE bounty_tasks SET status = 2 WHERE user_id = ? AND status = 1",
            (user_id,)
        )
        await self.conn.commit()
        return cursor.rowcount > 0
    
    async def cancel_bounty(self, user_id: str):
        """取消悬赏任务（含已过期的）"""
        await self.conn.execute(
            "UPDATE bounty_tasks SET status = 0 WHERE user_id = ? AND status IN (1, 3)",
            (user_id,)
        )
        await self.conn.commit()
    
    # ===== 系统配置 CRUD =====
    
    async def ensure_system_config_table(self):
        """确保系统配置表存在"""
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS system_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at INTEGER DEFAULT 0
            )
        """)
        await self.conn.commit()
    
    async def get_system_config(self, key: str) -> Optional[str]:
        """获取系统配置"""
        await self.ensure_system_config_table()
        async with self.conn.execute(
            "SELECT value FROM system_config WHERE key = ?",
            (key,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None
    
    async def set_system_config(self, key: str, value: str):
        """设置系统配置"""
        import time
        await self.ensure_system_config_table()
        await self.conn.execute(
            """
            INSERT INTO system_config (key, value, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = ?
            """,
            (key, value, int(time.time()), value, int(time.time()))
        )
        await self.conn.commit()

    async def clear_system_configs_by_prefix(self, prefix: str) -> int:
        """删除所有以指定前缀开头的系统配置，返回删除条数"""
        await self.ensure_system_config_table()
        async with self.conn.execute(
            "DELETE FROM system_config WHERE key LIKE ?",
            (f"{prefix}%",)
        ) as cursor:
            deleted = cursor.rowcount
        await self.conn.commit()
        return deleted

    # ===== 赠予请求系统 CRUD =====
    
    async def create_pending_gift(self, receiver_id: str, sender_id: str, sender_name: str,
                                   item_name: str, count: int, expires_hours: int = 24,
                                   auto_commit: bool = True) -> int:
        """创建赠予请求

        Args:
            receiver_id: 接收者ID
            sender_id: 发送者ID
            sender_name: 发送者名称
            item_name: 物品名称
            count: 物品数量
            expires_hours: 过期时间（小时），默认24小时
            auto_commit: 是否自动提交（False时由外部事务管理）

        Returns:
            新创建的赠予请求ID
        """
        import time
        now = int(time.time())
        expires_at = now + expires_hours * 3600

        await self.conn.execute(
            """
            INSERT INTO pending_gifts (
                receiver_id, sender_id, sender_name, item_name, count, created_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (receiver_id, sender_id, sender_name, item_name, count, now, expires_at)
        )
        if auto_commit:
            await self.conn.commit()

        async with self.conn.execute("SELECT last_insert_rowid()") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None
    
    async def get_pending_gift(self, receiver_id: str) -> Optional[dict]:
        """获取接收者的待处理赠予请求（最新的一个）"""
        import time
        now = int(time.time())
        
        # 先清理过期的请求
        await self.cleanup_expired_gifts()
        
        async with self.conn.execute(
            """
            SELECT id, receiver_id, sender_id, sender_name, item_name, count, created_at, expires_at
            FROM pending_gifts 
            WHERE receiver_id = ? AND expires_at > ?
            ORDER BY created_at DESC 
            LIMIT 1
            """,
            (receiver_id, now)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "receiver_id": row[1],
                    "sender_id": row[2],
                    "sender_name": row[3],
                    "item_name": row[4],
                    "count": row[5],
                    "created_at": row[6],
                    "expires_at": row[7]
                }
            return None
    
    async def get_all_pending_gifts(self, receiver_id: str) -> List[dict]:
        """获取接收者的所有待处理赠予请求"""
        import time
        now = int(time.time())
        
        async with self.conn.execute(
            """
            SELECT id, receiver_id, sender_id, sender_name, item_name, count, created_at, expires_at
            FROM pending_gifts 
            WHERE receiver_id = ? AND expires_at > ?
            ORDER BY created_at DESC
            """,
            (receiver_id, now)
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "receiver_id": row[1],
                    "sender_id": row[2],
                    "sender_name": row[3],
                    "item_name": row[4],
                    "count": row[5],
                    "created_at": row[6],
                    "expires_at": row[7]
                }
                for row in rows
            ]
    
    async def delete_pending_gift(self, gift_id: int):
        """删除赠予请求"""
        await self.conn.execute(
            "DELETE FROM pending_gifts WHERE id = ?",
            (gift_id,)
        )
        await self.conn.commit()
    
    async def delete_pending_gift_by_receiver(self, receiver_id: str):
        """删除接收者的所有赠予请求"""
        await self.conn.execute(
            "DELETE FROM pending_gifts WHERE receiver_id = ?",
            (receiver_id,)
        )
        await self.conn.commit()
    
    async def cleanup_expired_gifts(self):
        """清理过期的赠予请求"""
        import time
        now = int(time.time())
        await self.conn.execute(
            "DELETE FROM pending_gifts WHERE expires_at < ?",
            (now,)
        )
        await self.conn.commit()

    async def claim_pending_gift(self, gift_id: int, receiver_id: str) -> Optional[dict]:
        """CAS 领取赠予：在事务中原子读取+删除，防止并发领取

        利用 BEGIN IMMEDIATE 的排他锁和 DELETE rowcount 检测竞态：
        - 成功：返回赠予请求内容（item_name, count, sender_id 等）
        - 失败（已被领取/不存在）：返回 None

        Returns:
            赠予请求 dict，如果已被他人领取或不存在则返回 None
        """
        await self.conn.execute("BEGIN IMMEDIATE")
        try:
            cursor = await self.conn.execute(
                "SELECT id, receiver_id, sender_id, sender_name, item_name, count, created_at, expires_at "
                "FROM pending_gifts WHERE id = ? AND receiver_id = ?",
                (gift_id, receiver_id)
            )
            row = await cursor.fetchone()
            if not row:
                await self.conn.rollback()
                return None

            gift = {
                "id": row[0], "receiver_id": row[1], "sender_id": row[2],
                "sender_name": row[3], "item_name": row[4], "count": row[5],
                "created_at": row[6], "expires_at": row[7],
            }

            # 原子删除，通过 rowcount 检测是否已被他人领取
            cursor = await self.conn.execute(
                "DELETE FROM pending_gifts WHERE id = ?", (gift_id,)
            )
            if cursor.rowcount == 0:
                await self.conn.rollback()
                return None

            await self.conn.commit()
            return gift
        except Exception:
            await self.conn.rollback()
            raise

    async def reject_pending_gift(self, gift_id: int, receiver_id: str) -> Optional[dict]:
        """CAS 拒绝赠予：在事务中原子读取+删除，防止并发重复处理

        Returns:
            被拒绝的赠予请求 dict，如果已被处理或不存在则返回 None
        """
        await self.conn.execute("BEGIN IMMEDIATE")
        try:
            cursor = await self.conn.execute(
                "SELECT id, receiver_id, sender_id, sender_name, item_name, count, created_at, expires_at "
                "FROM pending_gifts WHERE id = ? AND receiver_id = ?",
                (gift_id, receiver_id)
            )
            row = await cursor.fetchone()
            if not row:
                await self.conn.rollback()
                return None

            gift = {
                "id": row[0], "receiver_id": row[1], "sender_id": row[2],
                "sender_name": row[3], "item_name": row[4], "count": row[5],
                "created_at": row[6], "expires_at": row[7],
            }

            # 原子删除，检测是否已被处理
            cursor = await self.conn.execute(
                "DELETE FROM pending_gifts WHERE id = ?", (gift_id,)
            )
            if cursor.rowcount == 0:
                await self.conn.rollback()
                return None

            await self.conn.commit()
            return gift
        except Exception:
            await self.conn.rollback()
            raise
    
    # ===== Phase 3: 银行贷款系统 CRUD =====
    
    async def get_active_loan(self, user_id: str) -> Optional[dict]:
        """获取用户当前活跃的贷款"""
        async with self.conn.execute(
            """SELECT id, user_id, principal, interest_rate, borrowed_at, due_at, status, loan_type
               FROM bank_loans WHERE user_id = ? AND status = 'active'""",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "user_id": row[1],
                    "principal": row[2],
                    "interest_rate": row[3],
                    "borrowed_at": row[4],
                    "due_at": row[5],
                    "status": row[6],
                    "loan_type": row[7]
                }
            return None
    
    async def create_loan(self, user_id: str, principal: int, interest_rate: float,
                          borrowed_at: int, due_at: int, loan_type: str = "normal", auto_commit: bool = True) -> int:
        """创建贷款记录"""
        await self.conn.execute(
            """INSERT INTO bank_loans (user_id, principal, interest_rate, borrowed_at, due_at, status, loan_type)
               VALUES (?, ?, ?, ?, ?, 'active', ?)""",
            (user_id, principal, interest_rate, borrowed_at, due_at, loan_type)
        )
        if auto_commit:
            await self.conn.commit()
        async with self.conn.execute("SELECT last_insert_rowid()") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0
    
    async def close_loan(self, loan_id: int, auto_commit: bool = True):
        """关闭贷款（标记为已还清）"""
        await self.conn.execute(
            "UPDATE bank_loans SET status = 'closed' WHERE id = ?",
            (loan_id,)
        )
        if auto_commit:
            await self.conn.commit()
    
    async def mark_loan_overdue(self, loan_id: int, auto_commit: bool = True):
        """标记贷款逾期"""
        await self.conn.execute(
            "UPDATE bank_loans SET status = 'overdue' WHERE id = ?",
            (loan_id,)
        )
        if auto_commit:
            await self.conn.commit()
    
    async def get_overdue_loans(self, current_time: int) -> List[dict]:
        """获取所有逾期贷款"""
        loans = []
        async with self.conn.execute(
            """SELECT id, user_id, principal, interest_rate, borrowed_at, due_at, loan_type
               FROM bank_loans WHERE status = 'active' AND due_at < ?""",
            (current_time,)
        ) as cursor:
            async for row in cursor:
                loans.append({
                    "id": row[0],
                    "user_id": row[1],
                    "principal": row[2],
                    "interest_rate": row[3],
                    "borrowed_at": row[4],
                    "due_at": row[5],
                    "loan_type": row[6]
                })
        return loans
    
    # ===== Phase 3: 银行交易流水 CRUD =====
    
    async def add_bank_transaction(self, user_id: str, trans_type: str, amount: int,
                                    balance_after: int, description: str, created_at: int, auto_commit: bool = True):
        """添加银行交易流水"""
        await self.conn.execute(
            """INSERT INTO bank_transactions (user_id, trans_type, amount, balance_after, description, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, trans_type, amount, balance_after, description, created_at)
        )
        if auto_commit:
            await self.conn.commit()
    
    async def get_bank_transactions(self, user_id: str, limit: int = 20) -> List[dict]:
        """获取用户银行交易流水"""
        transactions = []
        async with self.conn.execute(
            """SELECT id, trans_type, amount, balance_after, description, created_at
               FROM bank_transactions WHERE user_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (user_id, limit)
        ) as cursor:
            async for row in cursor:
                transactions.append({
                    "id": row[0],
                    "trans_type": row[1],
                    "amount": row[2],
                    "balance_after": row[3],
                    "description": row[4],
                    "created_at": row[5]
                })
        return transactions
    
    async def get_deposit_ranking(self, limit: int = 10) -> List[dict]:
        """获取存款排行榜"""
        rankings = []
        async with self.conn.execute(
            """SELECT user_id, balance FROM bank_accounts
               WHERE balance > 0
               ORDER BY balance DESC LIMIT ?""",
            (limit,)
        ) as cursor:
            async for row in cursor:
                rankings.append({
                    "user_id": row[0],
                    "balance": row[1]
                })
        return rankings

    # ===== 玩家神通 CRUD =====

    async def add_player_skill(self, user_id: str, skill_name: str) -> bool:
        """为玩家添加一个神通，返回是否为新获得"""
        import time
        try:
            cursor = await self.conn.execute(
                "INSERT OR IGNORE INTO player_skills (user_id, skill_name, acquired_at) VALUES (?, ?, ?)",
                (user_id, skill_name, int(time.time()))
            )
            await self.conn.commit()
            return cursor.rowcount > 0  # True=新获得, False=已存在
        except Exception:
            return False

    async def remove_player_skill(self, user_id: str, skill_name: str) -> bool:
        """移除玩家的一个神通"""
        cursor = await self.conn.execute(
            "DELETE FROM player_skills WHERE user_id = ? AND skill_name = ?",
            (user_id, skill_name)
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def get_player_skills(self, user_id: str) -> List[str]:
        """获取玩家拥有的所有神通名称"""
        skills = []
        async with self.conn.execute(
            "SELECT skill_name FROM player_skills WHERE user_id = ? ORDER BY acquired_at",
            (user_id,)
        ) as cursor:
            async for row in cursor:
                skills.append(row[0])
        return skills

    async def has_player_skill(self, user_id: str, skill_name: str) -> bool:
        """检查玩家是否拥有指定神通"""
        async with self.conn.execute(
            "SELECT 1 FROM player_skills WHERE user_id = ? AND skill_name = ?",
            (user_id, skill_name)
        ) as cursor:
            return await cursor.fetchone() is not None

    async def get_all_skills_from_db(self) -> List[dict]:
        """从数据库获取所有神通定义"""
        skills = []
        async with self.conn.execute("SELECT * FROM skills ORDER BY skill_type, rank") as cursor:
            async for row in cursor:
                skills.append({
                    "skill_name": row[0],
                    "skill_type": row[1],
                    "rank": row[2],
                    "required_level_index": row[3],
                    "hpcost": row[4],
                    "mpcost": row[5],
                    "turncost": row[6],
                    "rate": row[7],
                    "atkvalue": json.loads(row[8]) if row[8] else [],
                    "bufftype": row[9],
                    "buffvalue": row[10],
                    "success": row[11],
                    "desc": row[12],
                    "price": row[13],
                    "shop_weight": row[14],
                })
        return skills

    # ===== GM补偿系统 CRUD =====

    async def create_compensation(self, items_json: str) -> int:
        """创建新的补偿包，返回 comp_id

        Args:
            items_json: JSON 字符串，格式 {"物品名": 数量, ...}
        """
        import time
        now = int(time.time())
        await self.conn.execute(
            "INSERT INTO gm_compensation (items, created_at) VALUES (?, ?)",
            (items_json, now)
        )
        await self.conn.commit()
        async with self.conn.execute("SELECT last_insert_rowid()") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    async def get_active_compensation(self) -> Optional[dict]:
        """获取当前活跃的补偿包（最新的一条）"""
        async with self.conn.execute(
            "SELECT id, items, created_at FROM gm_compensation ORDER BY id DESC LIMIT 1"
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"id": row[0], "items": row[1], "created_at": row[2]}
        return None

    async def delete_old_compensations(self, current_id: int):
        """删除比 current_id 更旧的补偿包及其领取记录"""
        await self.conn.execute(
            "DELETE FROM gm_compensation_claims WHERE comp_id < ?", (current_id,)
        )
        await self.conn.execute(
            "DELETE FROM gm_compensation WHERE id < ?", (current_id,)
        )
        await self.conn.commit()

    async def has_claimed(self, user_id: str, comp_id: int) -> bool:
        """查询玩家是否已领取指定补偿"""
        async with self.conn.execute(
            "SELECT 1 FROM gm_compensation_claims WHERE user_id = ? AND comp_id = ?",
            (user_id, comp_id)
        ) as cursor:
            return await cursor.fetchone() is not None

    async def claim_compensation(self, user_id: str, comp_id: int) -> bool:
        """记录领取，用 INSERT OR IGNORE 防并发。返回 True 表示首次领取成功。"""
        import time
        now = int(time.time())
        cursor = await self.conn.execute(
            "INSERT OR IGNORE INTO gm_compensation_claims (user_id, comp_id, claimed_at) VALUES (?, ?, ?)",
            (user_id, comp_id, now)
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    # ===== 秘境副本系统 CRUD =====

    async def get_dungeon_run(self, user_id: str) -> Optional[DungeonRun]:
        """获取玩家进行中的副本状态"""
        async with self.conn.execute(
            "SELECT run_data FROM dungeon_runs WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                try:
                    data = json.loads(row[0])
                    return DungeonRun.from_dict(data)
                except Exception:
                    return None
            return None

    async def save_dungeon_run(self, run: DungeonRun, auto_commit: bool = True):
        """保存副本状态（INSERT OR REPLACE）"""
        run_json = json.dumps(run.to_dict(), ensure_ascii=False)
        await self.conn.execute(
            "INSERT OR REPLACE INTO dungeon_runs (user_id, run_data) VALUES (?, ?)",
            (run.user_id, run_json)
        )
        if auto_commit:
            await self.conn.commit()

    async def delete_dungeon_run(self, user_id: str, auto_commit: bool = True):
        """删除副本状态"""
        await self.conn.execute(
            "DELETE FROM dungeon_runs WHERE user_id = ?", (user_id,)
        )
        if auto_commit:
            await self.conn.commit()

    async def get_dungeon_daily_reward(self, user_id: str) -> dict:
        """获取玩家今日秘境奖励累计 {gold: N, exp: N, date: str}"""
        from datetime import date as _date
        today = _date.today().isoformat()
        key = f"dungeon_daily_{user_id}"
        val = await self.get_system_config(key)
        if val:
            try:
                data = json.loads(val)
                if data.get("date") == today:
                    return data
            except Exception:
                pass
        return {"date": today, "gold": 0, "exp": 0}

    async def add_dungeon_daily_reward(self, user_id: str, gold: int = 0, exp: int = 0):
        """累加今日秘境奖励"""
        current = await self.get_dungeon_daily_reward(user_id)
        current["gold"] += gold
        current["exp"] += exp
        key = f"dungeon_daily_{user_id}"
        await self.set_system_config(key, json.dumps(current, ensure_ascii=False))

    # ────────────────────────────────────────────
    # 锻造系统 — weapon_instances DAO
    # ────────────────────────────────────────────

    async def get_player_weapon_instances(self, user_id: str) -> list[dict]:
        """获取玩家的所有武器/防具实例（含装备中的，按创建时间倒序）"""
        async with self.conn.execute(
            "SELECT * FROM weapon_instances WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_weapon_instance(self, instance_id: str) -> dict | None:
        """获取单个武器/防具实例"""
        async with self.conn.execute(
            "SELECT * FROM weapon_instances WHERE instance_id = ?",
            (instance_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def create_weapon_instance(self, user_id: str, data: dict) -> str:
        """创建武器/防具实例，返回 instance_id"""
        import json as _json
        instance_id = data["instance_id"]
        affixes_json = _json.dumps(data.get("affixes", []), ensure_ascii=False)
        await self.conn.execute("""
            INSERT INTO weapon_instances (
                instance_id, user_id, template_name, item_type,
                quality, quality_mult, enhance_level,
                atk_bonus, crit_rate, crit_damage, armor_pen,
                lifesteal, double_hit, damage_reduction, mp_bonus,
                def_buff, dodge_rate, crit_resist, reflect_pct,
                block_value, hp_regen_pct, affixes,
                source_recipe, is_equipped, in_storage
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1)
        """, (
            instance_id, user_id, data["template_name"], data["item_type"],
            data["quality"], data["quality_mult"], data.get("enhance_level", 0),
            data.get("atk_bonus", 0.0), data.get("crit_rate", 0),
            data.get("crit_damage", 0.0), data.get("armor_pen", 0),
            data.get("lifesteal", 0), data.get("double_hit", 0),
            data.get("damage_reduction", 0.0), data.get("mp_bonus", 0.0),
            data.get("def_buff", 0.0), data.get("dodge_rate", 0),
            data.get("crit_resist", 0), data.get("reflect_pct", 0),
            data.get("block_value", 0), data.get("hp_regen_pct", 0.0),
            affixes_json, data.get("source_recipe", ""),
        ))
        await self.conn.commit()
        return instance_id

    async def equip_weapon_instance(self, user_id: str, instance_id: str, item_type: str) -> bool:
        """装备武器/防具实例（按 item_type 仅清除同槽位）

        Args:
            user_id: 玩家ID
            instance_id: 实例ID
            item_type: "weapon" 或 "armor" — 仅清除该槽位，防止卸下另一槽位
        """
        await self.conn.execute("BEGIN IMMEDIATE")
        try:
            # 仅清除该 item_type 的装备状态
            await self.conn.execute(
                "UPDATE weapon_instances SET is_equipped = 0 WHERE user_id = ? AND item_type = ?",
                (user_id, item_type)
            )
            # 装备目标实例
            await self.conn.execute(
                "UPDATE weapon_instances SET is_equipped = 1, in_storage = 0 WHERE instance_id = ? AND user_id = ?",
                (instance_id, user_id)
            )
            if self.conn.total_changes == 0:
                await self.conn.rollback()
                return False
            await self.conn.commit()
            return True
        except Exception:
            await self.conn.rollback()
            raise

    async def unequip_weapon_instance(self, user_id: str, instance_id: str) -> bool:
        """卸下武器实例"""
        await self.conn.execute("""
            UPDATE weapon_instances
            SET is_equipped = 0, in_storage = 1
            WHERE instance_id = ? AND user_id = ?
        """, (instance_id, user_id))
        affected = self.conn.total_changes
        await self.conn.commit()
        return affected > 0

    async def delete_weapon_instance(self, user_id: str, instance_id: str) -> bool:
        """删除武器/防具实例（用于分解等）"""
        await self.conn.execute(
            "DELETE FROM weapon_instances WHERE instance_id = ? AND user_id = ?",
            (instance_id, user_id)
        )
        affected = self.conn.total_changes
        await self.conn.commit()
        return affected > 0
