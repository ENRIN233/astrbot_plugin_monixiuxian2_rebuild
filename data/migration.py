# data/migration.py

import aiosqlite
from typing import Dict, Callable, Awaitable
from astrbot.api import logger
from ..config_manager import ConfigManager

LATEST_DB_VERSION = 27  # v27: 神通系统

MIGRATION_TASKS: Dict[int, Callable[[aiosqlite.Connection, ConfigManager], Awaitable[None]]] = {}

def migration(version: int):
    """注册数据库迁移任务的装饰器"""
    def decorator(func: Callable[[aiosqlite.Connection, ConfigManager], Awaitable[None]]):
        MIGRATION_TASKS[version] = func
        return func
    return decorator

class MigrationManager:
    """数据库迁移管理器"""

    def __init__(self, conn: aiosqlite.Connection, config_manager: ConfigManager):
        self.conn = conn
        self.config_manager = config_manager

    async def migrate(self):
        await self.conn.execute("PRAGMA foreign_keys = ON")
        async with self.conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='db_info'") as cursor:
            if await cursor.fetchone() is None:
                logger.info("未检测到数据库版本，将进行全新安装...")
                await self.conn.execute("BEGIN")
                # 使用最新的建表函数
                await _create_all_tables_v2(self.conn)
                await self.conn.execute("INSERT INTO db_info (version) VALUES (?)", (LATEST_DB_VERSION,))
                await self.conn.commit()
                logger.info(f"数据库已初始化到最新版本: v{LATEST_DB_VERSION}")
                return

        async with self.conn.execute("SELECT version FROM db_info") as cursor:
            row = await cursor.fetchone()
            current_version = row[0] if row else 0

        logger.info(f"当前数据库版本: v{current_version}, 最新版本: v{LATEST_DB_VERSION}")
        if current_version < LATEST_DB_VERSION:
            logger.info("检测到数据库需要升级...")
            for version in sorted(MIGRATION_TASKS.keys()):
                if current_version < version:
                    logger.info(f"正在执行数据库升级: v{current_version} -> v{version} ...")
                    await self.conn.execute("BEGIN")
                    try:
                        await MIGRATION_TASKS[version](self.conn, self.config_manager)
                        await self.conn.execute("UPDATE db_info SET version = ?", (version,))
                        await self.conn.commit()
                        current_version = version
                        logger.info(f"数据库升级成功: v{version}")
                    except Exception as e:
                        await self.conn.rollback()
                        logger.error(f"数据库升级失败: v{version}. 错误: {str(e)}")
                        raise
            logger.info(f"数据库已升级到最新版本: v{LATEST_DB_VERSION}")
        else:
            logger.info("数据库已是最新版本，无需升级。")

        # 完整性修复：检查并补全可能缺失的表和字段
        # （修复旧版 _create_all_tables_v2 遗漏的表/字段）
        await _ensure_table_integrity(self.conn)

async def _ensure_table_integrity(conn: aiosqlite.Connection):
    """检查并补全可能缺失的表和字段（修复旧版 _create_all_tables_v2 遗漏）"""
    async with conn.execute("SELECT name FROM sqlite_master WHERE type='table'") as cursor:
        existing_tables = {row[0] for row in await cursor.fetchall()}

    repaired = []

    if "bounty_tasks" not in existing_tables:
        await conn.execute("""
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
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_bounty_user ON bounty_tasks(user_id)")
        repaired.append("bounty_tasks")

    if "blessed_lands" not in existing_tables:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS blessed_lands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                land_type INTEGER NOT NULL DEFAULT 1,
                land_name TEXT NOT NULL DEFAULT '小洞天',
                level INTEGER NOT NULL DEFAULT 1,
                exp_bonus REAL NOT NULL DEFAULT 0.05,
                gold_per_hour INTEGER NOT NULL DEFAULT 100,
                last_collect_time INTEGER NOT NULL DEFAULT 0,
                UNIQUE(user_id, land_type)
            )
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_blessed_lands_user ON blessed_lands(user_id)")
        repaired.append("blessed_lands")

    if "spirit_farms" not in existing_tables:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS spirit_farms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL UNIQUE,
                level INTEGER NOT NULL DEFAULT 1,
                crops TEXT NOT NULL DEFAULT '[]'
            )
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_spirit_farms_user ON spirit_farms(user_id)")
        repaired.append("spirit_farms")

    if "dual_cultivation" not in existing_tables:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS dual_cultivation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL UNIQUE,
                daily_count INTEGER NOT NULL DEFAULT 0,
                daily_date TEXT NOT NULL DEFAULT ''
            )
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_dual_user ON dual_cultivation(user_id)")
        repaired.append("dual_cultivation")

    if "spirit_eyes" not in existing_tables:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS spirit_eyes (
                eye_id INTEGER PRIMARY KEY AUTOINCREMENT,
                eye_type INTEGER NOT NULL DEFAULT 1,
                eye_name TEXT NOT NULL DEFAULT '下品灵眼',
                exp_per_hour INTEGER NOT NULL DEFAULT 500,
                spawn_time INTEGER NOT NULL,
                owner_id TEXT,
                owner_name TEXT,
                claim_time INTEGER,
                last_collect_time INTEGER
            )
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_spirit_eyes_owner ON spirit_eyes(owner_id)")
        import time
        now = int(time.time())
        for eye in [(1, "下品灵眼", 15, now), (1, "下品灵眼", 15, now), (2, "中品灵眼", 25, now)]:
            await conn.execute(
                "INSERT INTO spirit_eyes (eye_type, eye_name, exp_per_hour, spawn_time) VALUES (?, ?, ?, ?)",
                eye
            )
        repaired.append("spirit_eyes")

    if "dual_cultivation_requests" not in existing_tables:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS dual_cultivation_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_id TEXT NOT NULL,
                from_name TEXT NOT NULL,
                target_id TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL
            )
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_dual_req_target ON dual_cultivation_requests(target_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_dual_req_expires ON dual_cultivation_requests(expires_at)")
        repaired.append("dual_cultivation_requests")

    if "combat_cooldowns" not in existing_tables:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS combat_cooldowns (
                user_id TEXT PRIMARY KEY,
                last_duel_time INTEGER NOT NULL DEFAULT 0,
                last_spar_time INTEGER NOT NULL DEFAULT 0
            )
        """)
        repaired.append("combat_cooldowns")

    # 检查 user_cd 表是否缺少 extra_data 字段
    if "user_cd" in existing_tables:
        async with conn.execute("PRAGMA table_info(user_cd)") as cursor:
            columns = {row[1] for row in await cursor.fetchall()}
        if "extra_data" not in columns:
            try:
                await conn.execute("ALTER TABLE user_cd ADD COLUMN extra_data TEXT NOT NULL DEFAULT '{}'")
                repaired.append("user_cd.extra_data")
            except Exception:
                pass

    # 检查 spirit_eyes 表是否缺少 last_collect_time 字段
    if "spirit_eyes" in existing_tables and "spirit_eyes" not in repaired:
        async with conn.execute("PRAGMA table_info(spirit_eyes)") as cursor:
            columns = {row[1] for row in await cursor.fetchall()}
        if "last_collect_time" not in columns:
            try:
                await conn.execute("ALTER TABLE spirit_eyes ADD COLUMN last_collect_time INTEGER")
                repaired.append("spirit_eyes.last_collect_time")
            except Exception:
                pass

    # 检查 rifts 表是否有数据（新安装时 _create_all_tables_v2 不插入秘境数据）
    if "rifts" in existing_tables and "rifts" not in repaired:
        async with conn.execute("SELECT COUNT(*) FROM rifts") as cursor:
            rift_count = (await cursor.fetchone())[0]
        if rift_count == 0:
            import json
            default_rifts = [
                (1, "青云秘境", 1, 0, json.dumps({"exp": [500, 1500], "gold": [200, 800]})),
                (2, "落日峡谷", 2, 3, json.dumps({"exp": [1500, 4000], "gold": [500, 2000]})),
                (3, "万妖洞", 3, 6, json.dumps({"exp": [3000, 8000], "gold": [1000, 5000]})),
                (4, "玄冰地宫", 4, 10, json.dumps({"exp": [5000, 15000], "gold": [2000, 10000]})),
                (5, "上古遗迹", 5, 15, json.dumps({"exp": [10000, 30000], "gold": [5000, 20000]})),
            ]
            for rift in default_rifts:
                try:
                    await conn.execute(
                        "INSERT OR IGNORE INTO rifts (rift_id, rift_name, rift_level, required_level, rewards) VALUES (?, ?, ?, ?, ?)",
                        rift
                    )
                except Exception:
                    pass
            repaired.append("rifts(默认数据)")

    if repaired:
        await conn.commit()
        logger.info(f"数据库完整性修复完成，已补全: {', '.join(repaired)}")


async def _create_all_tables_v1(conn: aiosqlite.Connection):
    """创建所有表 - v1，只保留玩家基础信息"""

    # 数据库版本信息表
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS db_info (
            version INTEGER NOT NULL
        )
    """)

    # 玩家表 - 只保留基础属性
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS players (
            user_id TEXT PRIMARY KEY,
            level_index INTEGER NOT NULL DEFAULT 0,
            spiritual_root TEXT NOT NULL DEFAULT '未知',
            experience INTEGER NOT NULL DEFAULT 0,
            gold INTEGER NOT NULL DEFAULT 0,
            state TEXT NOT NULL DEFAULT '空闲',
            hp INTEGER NOT NULL DEFAULT 100,
            max_hp INTEGER NOT NULL DEFAULT 100,
            attack INTEGER NOT NULL DEFAULT 10,
            defense INTEGER NOT NULL DEFAULT 5,
            spiritual_power INTEGER NOT NULL DEFAULT 50,
            mental_power INTEGER NOT NULL DEFAULT 50
        )
    """)

    # 创建索引
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_player_level ON players(level_index)")

    logger.info("数据库表已创建完成（v1）")

@migration(2)
async def _migrate_to_v2(conn: aiosqlite.Connection, config_manager: ConfigManager):
    """迁移到v2 - 新属性系统（灵修/体修）"""
    logger.info("开始迁移到v2：新属性系统")

    # 删除旧表并创建新表
    await conn.execute("DROP TABLE IF EXISTS players")
    await _create_all_tables_v2(conn)

    logger.info("v2迁移完成：新属性系统")

@migration(3)
async def _migrate_to_v3(conn: aiosqlite.Connection, config_manager: ConfigManager):
    """迁移到v3 - 添加闭关系统"""
    logger.info("开始迁移到v3：添加闭关系统")

    # 添加 cultivation_start_time 字段
    await conn.execute("ALTER TABLE players ADD COLUMN cultivation_start_time INTEGER NOT NULL DEFAULT 0")

    logger.info("v3迁移完成：闭关系统")

@migration(4)
async def _migrate_to_v4(conn: aiosqlite.Connection, config_manager: ConfigManager):
    """迁移到v4 - 添加签到系统"""
    logger.info("开始迁移到v4：添加签到系统")

    # 添加 last_check_in_date 字段
    await conn.execute("ALTER TABLE players ADD COLUMN last_check_in_date TEXT NOT NULL DEFAULT ''")

    logger.info("v4迁移完成：签到系统")

@migration(5)
async def _migrate_to_v5(conn: aiosqlite.Connection, config_manager: ConfigManager):
    """迁移到v5 - 添加装备系统"""
    logger.info("开始迁移到v5：添加装备系统")

    # 添加装备栏字段
    await conn.execute("ALTER TABLE players ADD COLUMN weapon TEXT NOT NULL DEFAULT ''")
    await conn.execute("ALTER TABLE players ADD COLUMN armor TEXT NOT NULL DEFAULT ''")
    await conn.execute("ALTER TABLE players ADD COLUMN main_technique TEXT NOT NULL DEFAULT ''")
    await conn.execute("ALTER TABLE players ADD COLUMN techniques TEXT NOT NULL DEFAULT '[]'")

    # 添加灵气容量字段
    await conn.execute("ALTER TABLE players ADD COLUMN max_spiritual_qi INTEGER NOT NULL DEFAULT 1000")

    logger.info("v5迁移完成：装备系统")

@migration(6)
async def _migrate_to_v6(conn: aiosqlite.Connection, config_manager: ConfigManager):
    """迁移到v6 - 添加丹药系统"""
    logger.info("开始迁移到v6：添加丹药系统")

    # 添加丹药系统相关字段
    await conn.execute("ALTER TABLE players ADD COLUMN active_pill_effects TEXT NOT NULL DEFAULT '[]'")
    await conn.execute("ALTER TABLE players ADD COLUMN permanent_pill_gains TEXT NOT NULL DEFAULT '{}'")
    await conn.execute("ALTER TABLE players ADD COLUMN has_resurrection_pill INTEGER NOT NULL DEFAULT 0")
    await conn.execute("ALTER TABLE players ADD COLUMN pills_inventory TEXT NOT NULL DEFAULT '{}'")

    logger.info("v6迁移完成：丹药系统")

@migration(7)
async def _migrate_to_v7(conn: aiosqlite.Connection, config_manager: ConfigManager):
    """迁移到v7 - 丹药系统扩展字段"""
    logger.info("开始迁移到v7：丹药系统扩展字段")

    await conn.execute("ALTER TABLE players ADD COLUMN has_debuff_shield INTEGER NOT NULL DEFAULT 0")

    logger.info("v7迁移完成：新增定魂丹护盾字段")

@migration(8)
async def _migrate_to_v8(conn: aiosqlite.Connection, config_manager: ConfigManager):
    """迁移到v8 - 添加商店系统"""
    logger.info("开始迁移到v8：添加商店系统")

    # 创建商店表
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS shop (
            shop_id TEXT PRIMARY KEY,
            last_refresh_time INTEGER NOT NULL DEFAULT 0,
            current_items TEXT NOT NULL DEFAULT '[]'
        )
    """)

    # 插入全局商店数据
    await conn.execute("""
        INSERT OR IGNORE INTO shop (shop_id, last_refresh_time, current_items)
        VALUES ('global', 0, '[]')
    """)

    logger.info("v8迁移完成：商店系统")

@migration(9)
async def _migrate_to_v9(conn: aiosqlite.Connection, config_manager: ConfigManager):
    """迁移到v9 - 添加体修气血系统"""
    logger.info("开始迁移到v9：添加体修气血系统")

    # 添加气血字段
    await conn.execute("ALTER TABLE players ADD COLUMN blood_qi INTEGER NOT NULL DEFAULT 0")
    await conn.execute("ALTER TABLE players ADD COLUMN max_blood_qi INTEGER NOT NULL DEFAULT 0")

    logger.info("v9迁移完成：体修气血系统")

@migration(10)
async def _migrate_to_v10(conn: aiosqlite.Connection, config_manager: ConfigManager):
    """迁移到v10 - 清理废弃字段（equipment_inventory等）"""
    logger.info("开始迁移到v10：清理废弃字段")

    # 获取当前表结构
    async with conn.execute("PRAGMA table_info(players)") as cursor:
        columns = {row[1] for row in await cursor.fetchall()}

    # 定义需要保留的字段（与 Player 模型一致）
    valid_columns = {
        'user_id', 'level_index', 'spiritual_root', 'cultivation_type', 'lifespan',
        'experience', 'gold', 'state', 'cultivation_start_time', 'last_check_in_date',
        'spiritual_qi', 'max_spiritual_qi', 'blood_qi', 'max_blood_qi',
        'magic_damage', 'physical_damage', 'magic_defense', 'physical_defense', 'mental_power',
        'weapon', 'armor', 'main_technique', 'techniques',
        'active_pill_effects', 'permanent_pill_gains', 'has_resurrection_pill', 'has_debuff_shield', 'pills_inventory'
    }

    # 找出需要删除的废弃字段
    deprecated_columns = columns - valid_columns
    if deprecated_columns:
        logger.info(f"发现废弃字段: {deprecated_columns}，将进行清理...")

        # 使用正确的表重建方式（保留约束）
        columns_to_keep = columns & valid_columns
        columns_str = ', '.join(columns_to_keep)

        # 1. 创建新表（带完整约束）
        await conn.execute("""
            CREATE TABLE players_new (
                user_id TEXT PRIMARY KEY,
                level_index INTEGER NOT NULL DEFAULT 0,
                spiritual_root TEXT NOT NULL DEFAULT '未知',
                cultivation_type TEXT NOT NULL DEFAULT '灵修',
                lifespan INTEGER NOT NULL DEFAULT 100,
                experience INTEGER NOT NULL DEFAULT 0,
                gold INTEGER NOT NULL DEFAULT 0,
                state TEXT NOT NULL DEFAULT '空闲',
                cultivation_start_time INTEGER NOT NULL DEFAULT 0,
                last_check_in_date TEXT NOT NULL DEFAULT '',
                spiritual_qi INTEGER NOT NULL DEFAULT 100,
                max_spiritual_qi INTEGER NOT NULL DEFAULT 1000,
                blood_qi INTEGER NOT NULL DEFAULT 0,
                max_blood_qi INTEGER NOT NULL DEFAULT 0,
                magic_damage INTEGER NOT NULL DEFAULT 10,
                physical_damage INTEGER NOT NULL DEFAULT 10,
                magic_defense INTEGER NOT NULL DEFAULT 5,
                physical_defense INTEGER NOT NULL DEFAULT 5,
                mental_power INTEGER NOT NULL DEFAULT 100,
                weapon TEXT NOT NULL DEFAULT '',
                armor TEXT NOT NULL DEFAULT '',
                main_technique TEXT NOT NULL DEFAULT '',
                techniques TEXT NOT NULL DEFAULT '[]',
                active_pill_effects TEXT NOT NULL DEFAULT '[]',
                permanent_pill_gains TEXT NOT NULL DEFAULT '{}',
                has_resurrection_pill INTEGER NOT NULL DEFAULT 0,
                has_debuff_shield INTEGER NOT NULL DEFAULT 0,
                pills_inventory TEXT NOT NULL DEFAULT '{}',
                storage_ring TEXT NOT NULL DEFAULT '基础储物戒',
                storage_ring_items TEXT NOT NULL DEFAULT '{}'
            )
        """)

        # 2. 复制数据
        await conn.execute(f"""
            INSERT INTO players_new ({columns_str})
            SELECT {columns_str} FROM players
        """)

        # 3. 删除旧表
        await conn.execute("DROP TABLE players")

        # 4. 重命名新表
        await conn.execute("ALTER TABLE players_new RENAME TO players")

        # 5. 重建索引
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_player_level ON players(level_index)")

        logger.info(f"已清理废弃字段: {deprecated_columns}")
    else:
        logger.info("没有发现废弃字段，跳过清理")

    logger.info("v10迁移完成：清理废弃字段")


@migration(11)
async def _migrate_to_v11(conn: aiosqlite.Connection, config_manager: ConfigManager):
    """迁移到v11 - 添加储物戒系统"""
    logger.info("开始迁移到v11：添加储物戒系统")

    # 添加储物戒字段
    await conn.execute("ALTER TABLE players ADD COLUMN storage_ring TEXT NOT NULL DEFAULT '基础储物戒'")
    await conn.execute("ALTER TABLE players ADD COLUMN storage_ring_items TEXT NOT NULL DEFAULT '{}'")

    logger.info("v11迁移完成：储物戒系统 - 所有玩家已配备基础储物戒")


async def _create_all_tables_v2(conn: aiosqlite.Connection):
    """创建所有表 - v2版本，完整修仙系统"""

    # 数据库版本信息表
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS db_info (
            version INTEGER NOT NULL
        )
    """)

    # 玩家表 - 完整字段
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS players (
            user_id TEXT PRIMARY KEY,
            user_name TEXT NOT NULL DEFAULT '',
            level_index INTEGER NOT NULL DEFAULT 0,
            cultivation_type TEXT NOT NULL DEFAULT '灵修',
            experience INTEGER NOT NULL DEFAULT 0,
            gold INTEGER NOT NULL DEFAULT 0,
            hp INTEGER NOT NULL DEFAULT 0,
            mp INTEGER NOT NULL DEFAULT 0,
            atk INTEGER NOT NULL DEFAULT 0,
            atkpractice INTEGER NOT NULL DEFAULT 0,
            sect_id INTEGER NOT NULL DEFAULT 0,
            sect_position INTEGER NOT NULL DEFAULT 4,
            sect_contribution INTEGER NOT NULL DEFAULT 0,
            sect_task INTEGER NOT NULL DEFAULT 0,
            sect_elixir_get INTEGER NOT NULL DEFAULT 0,
            blessed_spot_flag INTEGER NOT NULL DEFAULT 0,
            blessed_spot_name TEXT NOT NULL DEFAULT '',
            level_up_rate INTEGER NOT NULL DEFAULT 0,
            
            spiritual_root TEXT NOT NULL DEFAULT '未知',
            lifespan INTEGER NOT NULL DEFAULT 100,
            state TEXT NOT NULL DEFAULT '空闲',
            cultivation_start_time INTEGER NOT NULL DEFAULT 0,
            last_check_in_date TEXT NOT NULL DEFAULT '',
            spiritual_qi INTEGER NOT NULL DEFAULT 100,
            max_spiritual_qi INTEGER NOT NULL DEFAULT 1000,
            blood_qi INTEGER NOT NULL DEFAULT 0,
            max_blood_qi INTEGER NOT NULL DEFAULT 0,
            magic_damage INTEGER NOT NULL DEFAULT 10,
            physical_damage INTEGER NOT NULL DEFAULT 10,
            magic_defense INTEGER NOT NULL DEFAULT 5,
            physical_defense INTEGER NOT NULL DEFAULT 5,
            mental_power INTEGER NOT NULL DEFAULT 100,
            
            weapon TEXT NOT NULL DEFAULT '',
            armor TEXT NOT NULL DEFAULT '',
            main_technique TEXT NOT NULL DEFAULT '',
            techniques TEXT NOT NULL DEFAULT '[]',
            
            active_pill_effects TEXT NOT NULL DEFAULT '[]',
            permanent_pill_gains TEXT NOT NULL DEFAULT '{}',
            has_resurrection_pill INTEGER NOT NULL DEFAULT 0,
            has_debuff_shield INTEGER NOT NULL DEFAULT 0,
            pills_inventory TEXT NOT NULL DEFAULT '{}',
            storage_ring TEXT NOT NULL DEFAULT '基础储物戒',
            storage_ring_items TEXT NOT NULL DEFAULT '{}',

            daily_pill_usage TEXT NOT NULL DEFAULT '{}',
            last_daily_reset TEXT NOT NULL DEFAULT '',
            permanent_pill_usage TEXT NOT NULL DEFAULT '{}',
            shentong TEXT NOT NULL DEFAULT ''
        )
    """)

    # 创建索引
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_player_level ON players(level_index)")

    # 创建商店表
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS shop (
            shop_id TEXT PRIMARY KEY,
            last_refresh_time INTEGER NOT NULL DEFAULT 0,
            current_items TEXT NOT NULL DEFAULT '[]'
        )
    """)
    # 插入全局商店数据
    await conn.execute("""
        INSERT OR IGNORE INTO shop (shop_id, last_refresh_time, current_items)
        VALUES ('global', 0, '[]')
    """)
    
    # 创建宗门表
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS sects (
            sect_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sect_name TEXT NOT NULL UNIQUE,
            sect_owner TEXT NOT NULL,
            sect_scale INTEGER NOT NULL DEFAULT 0,
            sect_used_stone INTEGER NOT NULL DEFAULT 0,
            sect_fairyland INTEGER NOT NULL DEFAULT 0,
            sect_materials INTEGER NOT NULL DEFAULT 0,
            mainbuff TEXT NOT NULL DEFAULT '0',
            secbuff TEXT NOT NULL DEFAULT '0',
            elixir_room_level INTEGER NOT NULL DEFAULT 0
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_sect_owner ON sects(sect_owner)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_sect_scale ON sects(sect_scale DESC)")
    
    # 创建Buff信息表
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS buff_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL UNIQUE,
            main_buff INTEGER NOT NULL DEFAULT 0,
            sec_buff INTEGER NOT NULL DEFAULT 0,
            faqi_buff INTEGER NOT NULL DEFAULT 0,
            fabao_weapon INTEGER NOT NULL DEFAULT 0,
            armor_buff INTEGER NOT NULL DEFAULT 0,
            atk_buff INTEGER NOT NULL DEFAULT 0,
            blessed_spot INTEGER NOT NULL DEFAULT 0,
            sub_buff INTEGER NOT NULL DEFAULT 0
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_buff_user ON buff_info(user_id)")
    
    # 创建Boss表
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS boss (
            boss_id INTEGER PRIMARY KEY AUTOINCREMENT,
            boss_name TEXT NOT NULL,
            boss_level TEXT NOT NULL,
            hp INTEGER NOT NULL,
            max_hp INTEGER NOT NULL,
            atk INTEGER NOT NULL,
            defense INTEGER NOT NULL DEFAULT 0,
            stone_reward INTEGER NOT NULL DEFAULT 0,
            create_time INTEGER NOT NULL DEFAULT 0,
            status INTEGER NOT NULL DEFAULT 1
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_boss_status ON boss(status, create_time DESC)")
    
    # 创建秘境表
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS rifts (
            rift_id INTEGER PRIMARY KEY AUTOINCREMENT,
            rift_name TEXT NOT NULL,
            rift_level INTEGER NOT NULL,
            required_level INTEGER NOT NULL,
            rewards TEXT NOT NULL DEFAULT '{}'
        )
    """)
    
    # 创建传承信息表
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS impart_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL UNIQUE,
            impart_hp_per REAL NOT NULL DEFAULT 0.0,
            impart_mp_per REAL NOT NULL DEFAULT 0.0,
            impart_atk_per REAL NOT NULL DEFAULT 0.0,
            impart_know_per REAL NOT NULL DEFAULT 0.0,
            impart_burst_per REAL NOT NULL DEFAULT 0.0
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_impart_user ON impart_info(user_id)")
    
    # 创建用户CD表
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS user_cd (
            user_id TEXT PRIMARY KEY,
            type INTEGER NOT NULL DEFAULT 0,
            create_time INTEGER NOT NULL DEFAULT 0,
            scheduled_time INTEGER NOT NULL DEFAULT 0,
            extra_data TEXT NOT NULL DEFAULT '{}'
        )
    """)
    
    # 创建赠予请求表
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS pending_gifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            receiver_id TEXT NOT NULL,
            sender_id TEXT NOT NULL,
            sender_name TEXT NOT NULL DEFAULT '',
            item_name TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 1,
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_pending_gifts_receiver ON pending_gifts(receiver_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_pending_gifts_expires ON pending_gifts(expires_at)")
    
    # 创建银行账户表
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS bank_accounts (
            user_id TEXT PRIMARY KEY,
            balance INTEGER NOT NULL DEFAULT 0,
            last_interest_time INTEGER NOT NULL DEFAULT 0
        )
    """)
    
    # 创建银行贷款表
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS bank_loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            principal INTEGER NOT NULL DEFAULT 0,
            interest_rate REAL NOT NULL DEFAULT 0.005,
            borrowed_at INTEGER NOT NULL,
            due_at INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            loan_type TEXT NOT NULL DEFAULT 'normal',
            UNIQUE(user_id, status)
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_bank_loans_user ON bank_loans(user_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_bank_loans_status ON bank_loans(status)")
    
    # 创建银行交易流水表
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS bank_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            trans_type TEXT NOT NULL,
            amount INTEGER NOT NULL,
            balance_after INTEGER NOT NULL DEFAULT 0,
            description TEXT NOT NULL DEFAULT '',
            created_at INTEGER NOT NULL
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_bank_trans_user ON bank_transactions(user_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_bank_trans_time ON bank_transactions(created_at)")

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_a TEXT NOT NULL,
            player_b TEXT NOT NULL,
            player_a_items TEXT NOT NULL DEFAULT '[]',
            player_b_items TEXT NOT NULL DEFAULT '[]',
            player_a_stones INTEGER NOT NULL DEFAULT 0,
            player_b_stones INTEGER NOT NULL DEFAULT 0,
            a_confirmed INTEGER NOT NULL DEFAULT 0,
            b_confirmed INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'trading',
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_player_a ON trades(player_a, status)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_player_b ON trades(player_b, status)")

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS consignment_listings (
            listing_id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            item_name TEXT NOT NULL,
            item_type TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            price INTEGER NOT NULL,
            listed_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            buyer_id TEXT,
            sold_at INTEGER
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_consignment_status ON consignment_listings(status)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_consignment_seller ON consignment_listings(seller_id, status)")

    # 创建悬赏任务表
    await conn.execute("""
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
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_bounty_user ON bounty_tasks(user_id)")

    # 创建洞天福地表
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS blessed_lands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL UNIQUE,
            land_type INTEGER NOT NULL DEFAULT 1,
            land_name TEXT NOT NULL DEFAULT '小洞天',
            level INTEGER NOT NULL DEFAULT 1,
            exp_bonus REAL NOT NULL DEFAULT 0.05,
            gold_per_hour INTEGER NOT NULL DEFAULT 100,
            last_collect_time INTEGER NOT NULL DEFAULT 0
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_blessed_lands_user ON blessed_lands(user_id)")

    # 创建灵田表
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS spirit_farms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL UNIQUE,
            level INTEGER NOT NULL DEFAULT 1,
            crops TEXT NOT NULL DEFAULT '[]'
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_spirit_farms_user ON spirit_farms(user_id)")

    # 创建双修记录表
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS dual_cultivation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL UNIQUE,
            daily_count INTEGER NOT NULL DEFAULT 0,
            daily_date TEXT NOT NULL DEFAULT ''
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_dual_user ON dual_cultivation(user_id)")

    # 创建天地灵眼表
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS spirit_eyes (
            eye_id INTEGER PRIMARY KEY AUTOINCREMENT,
            eye_type INTEGER NOT NULL DEFAULT 1,
            eye_name TEXT NOT NULL DEFAULT '下品灵眼',
            exp_per_hour INTEGER NOT NULL DEFAULT 500,
            spawn_time INTEGER NOT NULL,
            owner_id TEXT,
            owner_name TEXT,
            claim_time INTEGER,
            last_collect_time INTEGER
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_spirit_eyes_owner ON spirit_eyes(owner_id)")

    # 插入初始灵眼（exp_per_hour 存储修炼效率百分比整数）
    import time
    now = int(time.time())
    initial_eyes = [
        (1, "下品灵眼", 15, now),
        (1, "下品灵眼", 15, now),
        (2, "中品灵眼", 25, now),
    ]
    for eye in initial_eyes:
        await conn.execute(
            "INSERT INTO spirit_eyes (eye_type, eye_name, exp_per_hour, spawn_time) VALUES (?, ?, ?, ?)",
            eye
        )

    # 创建双修请求表
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS dual_cultivation_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_id TEXT NOT NULL,
            from_name TEXT NOT NULL,
            target_id TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_dual_req_target ON dual_cultivation_requests(target_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_dual_req_expires ON dual_cultivation_requests(expires_at)")

    # 创建战斗冷却表
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS combat_cooldowns (
            user_id TEXT PRIMARY KEY,
            last_duel_time INTEGER NOT NULL DEFAULT 0,
            last_spar_time INTEGER NOT NULL DEFAULT 0
        )
    """)

    logger.info("数据库表已创建完成（v2 - 完整修仙系统）")


@migration(12)
async def _migrate_to_v12(conn: aiosqlite.Connection, config_manager: ConfigManager):
    """迁移到v12 - 添加完整修仙系统（宗门、Boss、秘境、战斗系统等）"""
    logger.info("开始迁移到v12：添加完整修仙系统")
    
    # 1. 添加Player新字段（战斗属性和宗门）
    logger.info("添加战斗属性字段...")
    await conn.execute("ALTER TABLE players ADD COLUMN user_name TEXT NOT NULL DEFAULT ''")
    await conn.execute("ALTER TABLE players ADD COLUMN level_up_rate INTEGER NOT NULL DEFAULT 0")
    await conn.execute("ALTER TABLE players ADD COLUMN hp INTEGER NOT NULL DEFAULT 0")
    await conn.execute("ALTER TABLE players ADD COLUMN mp INTEGER NOT NULL DEFAULT 0")
    await conn.execute("ALTER TABLE players ADD COLUMN atk INTEGER NOT NULL DEFAULT 0")
    await conn.execute("ALTER TABLE players ADD COLUMN atkpractice INTEGER NOT NULL DEFAULT 0")
    
    logger.info("添加宗门相关字段...")
    await conn.execute("ALTER TABLE players ADD COLUMN sect_id INTEGER NOT NULL DEFAULT 0")
    await conn.execute("ALTER TABLE players ADD COLUMN sect_position INTEGER NOT NULL DEFAULT 4")
    await conn.execute("ALTER TABLE players ADD COLUMN sect_contribution INTEGER NOT NULL DEFAULT 0")
    await conn.execute("ALTER TABLE players ADD COLUMN sect_task INTEGER NOT NULL DEFAULT 0")
    await conn.execute("ALTER TABLE players ADD COLUMN sect_elixir_get INTEGER NOT NULL DEFAULT 0")
    
    logger.info("添加洞天福地字段...")
    await conn.execute("ALTER TABLE players ADD COLUMN blessed_spot_flag INTEGER NOT NULL DEFAULT 0")
    await conn.execute("ALTER TABLE players ADD COLUMN blessed_spot_name TEXT NOT NULL DEFAULT ''")
    
    # 2. 创建新表
    logger.info("创建宗门表...")
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS sects (
            sect_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sect_name TEXT NOT NULL UNIQUE,
            sect_owner TEXT NOT NULL,
            sect_scale INTEGER NOT NULL DEFAULT 0,
            sect_used_stone INTEGER NOT NULL DEFAULT 0,
            sect_fairyland INTEGER NOT NULL DEFAULT 0,
            sect_materials INTEGER NOT NULL DEFAULT 0,
            mainbuff TEXT NOT NULL DEFAULT '0',
            secbuff TEXT NOT NULL DEFAULT '0',
            elixir_room_level INTEGER NOT NULL DEFAULT 0
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_sect_owner ON sects(sect_owner)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_sect_scale ON sects(sect_scale DESC)")
    
    logger.info("创建Buff信息表...")
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS buff_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL UNIQUE,
            main_buff INTEGER NOT NULL DEFAULT 0,
            sec_buff INTEGER NOT NULL DEFAULT 0,
            faqi_buff INTEGER NOT NULL DEFAULT 0,
            fabao_weapon INTEGER NOT NULL DEFAULT 0,
            armor_buff INTEGER NOT NULL DEFAULT 0,
            atk_buff INTEGER NOT NULL DEFAULT 0,
            blessed_spot INTEGER NOT NULL DEFAULT 0,
            sub_buff INTEGER NOT NULL DEFAULT 0
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_buff_user ON buff_info(user_id)")
    
    logger.info("创建Boss表...")
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS boss (
            boss_id INTEGER PRIMARY KEY AUTOINCREMENT,
            boss_name TEXT NOT NULL,
            boss_level TEXT NOT NULL,
            hp INTEGER NOT NULL,
            max_hp INTEGER NOT NULL,
            atk INTEGER NOT NULL,
            defense INTEGER NOT NULL DEFAULT 0,
            stone_reward INTEGER NOT NULL DEFAULT 0,
            create_time INTEGER NOT NULL DEFAULT 0,
            status INTEGER NOT NULL DEFAULT 1
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_boss_status ON boss(status, create_time DESC)")
    
    logger.info("创建秘境表...")
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS rifts (
            rift_id INTEGER PRIMARY KEY AUTOINCREMENT,
            rift_name TEXT NOT NULL,
            rift_level INTEGER NOT NULL,
            required_level INTEGER NOT NULL,
            rewards TEXT NOT NULL DEFAULT '{}'
        )
    """)
    # 插入默认秘境数据
    import json as _json
    _default_rifts = [
        (1, "青云秘境", 1, 0, _json.dumps({"exp": [500, 1500], "gold": [200, 800]})),
        (2, "落日峡谷", 2, 3, _json.dumps({"exp": [1500, 4000], "gold": [500, 2000]})),
        (3, "万妖洞", 3, 6, _json.dumps({"exp": [3000, 8000], "gold": [1000, 5000]})),
        (4, "玄冰地宫", 4, 10, _json.dumps({"exp": [5000, 15000], "gold": [2000, 10000]})),
        (5, "上古遗迹", 5, 15, _json.dumps({"exp": [10000, 30000], "gold": [5000, 20000]})),
    ]
    for _rift in _default_rifts:
        await conn.execute(
            "INSERT OR IGNORE INTO rifts (rift_id, rift_name, rift_level, required_level, rewards) VALUES (?, ?, ?, ?, ?)",
            _rift
        )

    logger.info("创建传承信息表...")
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS impart_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL UNIQUE,
            impart_hp_per REAL NOT NULL DEFAULT 0.0,
            impart_mp_per REAL NOT NULL DEFAULT 0.0,
            impart_atk_per REAL NOT NULL DEFAULT 0.0,
            impart_know_per REAL NOT NULL DEFAULT 0.0,
            impart_burst_per REAL NOT NULL DEFAULT 0.0
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_impart_user ON impart_info(user_id)")
    
    logger.info("创建用户CD表...")
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS user_cd (
            user_id TEXT PRIMARY KEY,
            type INTEGER NOT NULL DEFAULT 0,
            create_time INTEGER NOT NULL DEFAULT 0,
            scheduled_time INTEGER NOT NULL DEFAULT 0
        )
    """)
    
    # 3. 初始化现有用户的扩展数据
    logger.info("为现有用户初始化扩展数据...")
    async with conn.execute("SELECT user_id FROM players") as cursor:
        users = await cursor.fetchall()
        for user in users:
            user_id = user[0]
            # 初始化BuffInfo
            await conn.execute("""
                INSERT OR IGNORE INTO buff_info (user_id) VALUES (?)
            """, (user_id,))
            # 初始化UserCd
            await conn.execute("""
                INSERT OR IGNORE INTO user_cd (user_id) VALUES (?)
            """, (user_id,))
            # 初始化ImpartInfo
            await conn.execute("""
                INSERT OR IGNORE INTO impart_info (user_id) VALUES (?)
            """, (user_id,))
    
    logger.info(f"v12迁移完成：完整修仙系统 - 已为 {len(users)} 个用户初始化扩展数据")


@migration(13)
async def _migrate_to_v13(conn: aiosqlite.Connection, config_manager: ConfigManager):
    """迁移到v13 - Phase 1: 道号系统、每日限制、物品绑定"""
    logger.info("开始迁移到v13：Phase 1 功能增强")
    
    # 1. 添加每日限制字段
    logger.info("添加每日限制字段...")
    try:
        await conn.execute("ALTER TABLE players ADD COLUMN daily_pill_usage TEXT NOT NULL DEFAULT '{}'")
    except:
        pass  # 字段可能已存在
    try:
        await conn.execute("ALTER TABLE players ADD COLUMN last_daily_reset TEXT NOT NULL DEFAULT ''")
    except:
        pass
    
    logger.info("v13迁移完成：Phase 1 功能增强")


@migration(14)
async def _migrate_to_v14(conn: aiosqlite.Connection, config_manager: ConfigManager):
    """迁移到v14 - Phase 2: 灵石银行、悬赏令系统"""
    logger.info("开始迁移到v14：Phase 2 经济与任务系统")
    
    # 1. 创建银行账户表
    logger.info("创建银行账户表...")
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS bank_accounts (
            user_id TEXT PRIMARY KEY,
            balance INTEGER NOT NULL DEFAULT 0,
            last_interest_time INTEGER NOT NULL DEFAULT 0
        )
    """)
    
    # 2. 创建悬赏任务表
    logger.info("创建悬赏任务表...")
    await conn.execute("""
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
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_bounty_user ON bounty_tasks(user_id)")
    
    logger.info("v14迁移完成：Phase 2 经济与任务系统")


@migration(15)
async def _migrate_to_v15(conn: aiosqlite.Connection, config_manager: ConfigManager):
    """迁移到v15 - 添加默认秘境数据"""
    logger.info("开始迁移到v15：添加默认秘境数据")
    
    # 插入默认秘境数据
    import json
    default_rifts = [
        (1, "青云秘境", 1, 0, json.dumps({"exp": [500, 1500], "gold": [200, 800]})),
        (2, "落日峡谷", 2, 3, json.dumps({"exp": [1500, 4000], "gold": [500, 2000]})),
        (3, "万妖洞", 3, 6, json.dumps({"exp": [3000, 8000], "gold": [1000, 5000]})),
        (4, "玄冰地宫", 4, 10, json.dumps({"exp": [5000, 15000], "gold": [2000, 10000]})),
        (5, "上古遗迹", 5, 15, json.dumps({"exp": [10000, 30000], "gold": [5000, 20000]})),
    ]
    
    for rift in default_rifts:
        try:
            await conn.execute(
                "INSERT OR IGNORE INTO rifts (rift_id, rift_name, rift_level, required_level, rewards) VALUES (?, ?, ?, ?, ?)",
                rift
            )
        except:
            pass
    
    await conn.commit()
    logger.info("v15迁移完成：已添加5个默认秘境")


@migration(16)
async def _migrate_to_v16(conn: aiosqlite.Connection, config_manager: ConfigManager):
    """迁移到v16 - Phase 4 扩展功能"""
    logger.info("开始迁移到v16：Phase 4 扩展功能")
    
    # 洞天福地表
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS blessed_lands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL UNIQUE,
            land_type INTEGER NOT NULL DEFAULT 1,
            land_name TEXT NOT NULL DEFAULT '小洞天',
            level INTEGER NOT NULL DEFAULT 1,
            exp_bonus REAL NOT NULL DEFAULT 0.05,
            gold_per_hour INTEGER NOT NULL DEFAULT 100,
            last_collect_time INTEGER NOT NULL DEFAULT 0
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_blessed_lands_user ON blessed_lands(user_id)")
    
    # 灵田表
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS spirit_farms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL UNIQUE,
            level INTEGER NOT NULL DEFAULT 1,
            crops TEXT NOT NULL DEFAULT '[]'
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_spirit_farms_user ON spirit_farms(user_id)")
    
    # 双修记录表
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS dual_cultivation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL UNIQUE,
            daily_count INTEGER NOT NULL DEFAULT 0,
            daily_date TEXT NOT NULL DEFAULT ''
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_dual_user ON dual_cultivation(user_id)")
    
    # 天地灵眼表
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS spirit_eyes (
            eye_id INTEGER PRIMARY KEY AUTOINCREMENT,
            eye_type INTEGER NOT NULL DEFAULT 1,
            eye_name TEXT NOT NULL DEFAULT '下品灵眼',
            exp_per_hour INTEGER NOT NULL DEFAULT 500,
            spawn_time INTEGER NOT NULL,
            owner_id TEXT,
            owner_name TEXT,
            claim_time INTEGER
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_spirit_eyes_owner ON spirit_eyes(owner_id)")
    
    # 插入初始灵眼（exp_per_hour 存储修炼效率百分比整数）
    import time
    now = int(time.time())
    initial_eyes = [
        (1, "下品灵眼", 15, now),
        (1, "下品灵眼", 15, now),
        (2, "中品灵眼", 25, now),
    ]
    for eye in initial_eyes:
        await conn.execute(
            "INSERT INTO spirit_eyes (eye_type, eye_name, exp_per_hour, spawn_time) VALUES (?, ?, ?, ?)",
            eye
        )
    
    await conn.commit()
    logger.info("v16迁移完成：Phase 4 扩展功能（洞天福地、灵田、双修、灵眼）")


@migration(17)
async def _migrate_to_v17(conn: aiosqlite.Connection, config_manager: ConfigManager):
    """迁移到v17 - 赠予请求持久化"""
    logger.info("开始迁移到v17：赠予请求持久化")
    
    # 创建赠予请求表
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS pending_gifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            receiver_id TEXT NOT NULL,
            sender_id TEXT NOT NULL,
            sender_name TEXT NOT NULL DEFAULT '',
            item_name TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 1,
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_pending_gifts_receiver ON pending_gifts(receiver_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_pending_gifts_expires ON pending_gifts(expires_at)")
    
    await conn.commit()
    logger.info("v17迁移完成：赠予请求持久化")


@migration(18)
async def _migrate_to_v18(conn: aiosqlite.Connection, config_manager: ConfigManager):
    """迁移到v18 - 银行贷款与交易流水系统"""
    logger.info("开始迁移到v18：银行贷款与交易流水系统")
    
    # 0. 确保 bank_accounts 表存在（v14可能未正确创建）
    logger.info("确保银行账户表存在...")
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS bank_accounts (
            user_id TEXT PRIMARY KEY,
            balance INTEGER NOT NULL DEFAULT 0,
            last_interest_time INTEGER NOT NULL DEFAULT 0
        )
    """)
    
    # 1. 创建银行贷款表
    logger.info("创建银行贷款表...")
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS bank_loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            principal INTEGER NOT NULL DEFAULT 0,
            interest_rate REAL NOT NULL DEFAULT 0.005,
            borrowed_at INTEGER NOT NULL,
            due_at INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            loan_type TEXT NOT NULL DEFAULT 'normal',
            UNIQUE(user_id, status)
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_bank_loans_user ON bank_loans(user_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_bank_loans_status ON bank_loans(status)")
    
    # 2. 创建银行交易流水表
    logger.info("创建银行交易流水表...")
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS bank_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            trans_type TEXT NOT NULL,
            amount INTEGER NOT NULL,
            balance_after INTEGER NOT NULL DEFAULT 0,
            description TEXT NOT NULL DEFAULT '',
            created_at INTEGER NOT NULL
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_bank_trans_user ON bank_transactions(user_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_bank_trans_time ON bank_transactions(created_at)")
    
    await conn.commit()
    logger.info("v18迁移完成：银行贷款与交易流水系统")


@migration(19)
async def _migrate_to_v19(conn: aiosqlite.Connection, config_manager: ConfigManager):
    """迁移到v19 - 银行系统表完整性修复"""
    logger.info("开始迁移到v19：银行系统表完整性修复")
    
    # 确保 bank_accounts 表存在（修复v14迁移可能跳过的情况）
    logger.info("确保银行账户表存在...")
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS bank_accounts (
            user_id TEXT PRIMARY KEY,
            balance INTEGER NOT NULL DEFAULT 0,
            last_interest_time INTEGER NOT NULL DEFAULT 0
        )
    """)
    
    # 确保 bank_loans 表存在
    logger.info("确保银行贷款表存在...")
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS bank_loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            principal INTEGER NOT NULL DEFAULT 0,
            interest_rate REAL NOT NULL DEFAULT 0.005,
            borrowed_at INTEGER NOT NULL,
            due_at INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            loan_type TEXT NOT NULL DEFAULT 'normal'
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_bank_loans_user ON bank_loans(user_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_bank_loans_status ON bank_loans(status)")
    
    # 确保 bank_transactions 表存在
    logger.info("确保银行交易流水表存在...")
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS bank_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            trans_type TEXT NOT NULL,
            amount INTEGER NOT NULL,
            balance_after INTEGER NOT NULL DEFAULT 0,
            description TEXT NOT NULL DEFAULT '',
            created_at INTEGER NOT NULL
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_bank_trans_user ON bank_transactions(user_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_bank_trans_time ON bank_transactions(created_at)")
    
    await conn.commit()
    logger.info("v19迁移完成：银行系统表完整性修复")


@migration(20)
async def _migrate_to_v20(conn: aiosqlite.Connection, config_manager: ConfigManager):
    """迁移到v20 - 用户CD表添加额外数据字段"""
    logger.info("开始迁移到v20：用户CD表添加额外数据字段")
    
    # 添加extra_data字段用于存储额外信息（如秘境ID、战斗冷却等）
    try:
        await conn.execute("ALTER TABLE user_cd ADD COLUMN extra_data TEXT NOT NULL DEFAULT '{}'")
    except Exception as e:
        logger.warning(f"添加extra_data字段失败（可能已存在）: {e}")
    
    # 添加last_collect_time字段到spirit_eyes表（修复灵眼收取时间计算）
    try:
        await conn.execute("ALTER TABLE spirit_eyes ADD COLUMN last_collect_time INTEGER")
    except Exception as e:
        logger.warning(f"添加last_collect_time字段失败（可能已存在）: {e}")
    
    # 添加双修请求持久化表
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS dual_cultivation_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_id TEXT NOT NULL,
            from_name TEXT NOT NULL,
            target_id TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_dual_req_target ON dual_cultivation_requests(target_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_dual_req_expires ON dual_cultivation_requests(expires_at)")
    
    # 添加战斗冷却表
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS combat_cooldowns (
            user_id TEXT PRIMARY KEY,
            last_duel_time INTEGER NOT NULL DEFAULT 0,
            last_spar_time INTEGER NOT NULL DEFAULT 0
        )
    """)
    
    await conn.commit()
    logger.info("v20迁移完成：用户CD表添加额外数据字段")


@migration(21)
async def _migrate_to_v21(conn: aiosqlite.Connection, config_manager: ConfigManager):
    """迁移到v21 - 玩家交易系统（trades + consignment_listings 表）"""
    logger.info("开始迁移到v21：玩家交易系统")

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_a TEXT NOT NULL,
            player_b TEXT NOT NULL,
            player_a_items TEXT NOT NULL DEFAULT '[]',
            player_b_items TEXT NOT NULL DEFAULT '[]',
            player_a_stones INTEGER NOT NULL DEFAULT 0,
            player_b_stones INTEGER NOT NULL DEFAULT 0,
            a_confirmed INTEGER NOT NULL DEFAULT 0,
            b_confirmed INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'trading',
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_player_a ON trades(player_a, status)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_player_b ON trades(player_b, status)")

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS consignment_listings (
            listing_id INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            item_name TEXT NOT NULL,
            item_type TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            price INTEGER NOT NULL,
            listed_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            buyer_id TEXT,
            sold_at INTEGER
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_consignment_status ON consignment_listings(status)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_consignment_seller ON consignment_listings(seller_id, status)")

    await conn.commit()
    logger.info("v21迁移完成：玩家交易系统")


@migration(22)
async def _migrate_to_v22(conn: aiosqlite.Connection, config_manager: ConfigManager):
    """迁移到v22 - 添加永久丹药服用次数追踪"""
    logger.info("开始迁移到v22：永久丹药服用次数追踪")

    await conn.execute("ALTER TABLE players ADD COLUMN permanent_pill_usage TEXT NOT NULL DEFAULT '{}'")

    await conn.commit()
    logger.info("v22迁移完成：永久丹药服用次数追踪")


@migration(23)
async def _migrate_to_v23(conn: aiosqlite.Connection, config_manager: ConfigManager):
    """迁移到v23 - 双修系统改为每日次数上限（3次/天）"""
    logger.info("开始迁移到v23：双修系统每日次数上限")

    # 添加每日次数字段
    try:
        await conn.execute("ALTER TABLE dual_cultivation ADD COLUMN daily_count INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass
    try:
        await conn.execute("ALTER TABLE dual_cultivation ADD COLUMN daily_date TEXT NOT NULL DEFAULT ''")
    except Exception:
        pass

    # 尝试移除旧的冷却时间字段（SQLite < 3.35.0 不支持 DROP COLUMN，忽略错误）
    try:
        await conn.execute("ALTER TABLE dual_cultivation DROP COLUMN last_dual_time")
    except Exception:
        pass

    await conn.commit()
    logger.info("v23迁移完成：双修系统每日次数上限")


@migration(24)
async def _migrate_to_v24(conn: aiosqlite.Connection, config_manager: ConfigManager):
    """迁移到v24 - 战斗公式重设计 + 突破属性重平衡

    将现有玩家的突破属性从旧值映射到新值范围。
    新公式使用 sqrt(exp)/ln(exp) 替代 exp 直接计算，数值范围完全不同。
    """
    logger.info("开始迁移到v24：战斗公式重设计 + 突破属性重平衡")

    # 旧/新累积目标值（按 level_index 排列）
    # 格式: (level_index, old_phy_dmg, new_phy_dmg, old_phy_def, new_phy_def, old_mp, new_mp, old_ls, new_ls)
    RANK_DATA = [
        (0,  0,      0,      0,      0,      0,      0,      0,      0),
        (10, 90,     100,    45,     50,     450,    200,    60,     60),
        (12, 210,    300,    105,    100,    1050,   600,    90,     90),
        (13, 340,    600,    170,    200,    1700,   1200,   130,    150),
        (16, 1290,   1200,   645,    350,    6450,   2400,   290,    300),
        (22, 15990,  2500,   7995,   500,    79950,  5000,   1200,   800),
        (28, 179990, 4500,   89995,  700,    899950, 9000,   4600,   2500),
        (32, 999990, 7500,   499995, 900,    4999950,15000,  10100,  5000),
        (35, 3499990,12000,  1749995,1200,   17499950,24000, 19100,  10000),
    ]

    def interpolate_stat(level_index, stat_idx_old, stat_idx_new):
        """在两个 rank 边界之间线性插值"""
        for i in range(len(RANK_DATA) - 1):
            li0 = RANK_DATA[i][0]
            li1 = RANK_DATA[i + 1][0]
            if li0 <= level_index <= li1:
                old0, new0 = RANK_DATA[i][stat_idx_old], RANK_DATA[i][stat_idx_new]
                old1, new1 = RANK_DATA[i + 1][stat_idx_old], RANK_DATA[i + 1][stat_idx_new]
                if li1 == li0:
                    pct = 0
                else:
                    pct = (level_index - li0) / (li1 - li0)
                old_val = old0 + pct * (old1 - old0)
                new_val = new0 + pct * (new1 - new0)
                return old_val, new_val
        # 超出范围
        return RANK_DATA[-1][stat_idx_old], RANK_DATA[-1][stat_idx_new]

    def map_value(current_val, level_index, stat_idx_old, stat_idx_new):
        """将当前属性值从旧范围映射到新范围"""
        old_target, new_target = interpolate_stat(level_index, stat_idx_old, stat_idx_new)
        if old_target <= 0:
            return 0
        ratio = current_val / old_target
        return max(0, int(new_target * ratio))

    # 获取所有玩家
    try:
        async with conn.execute("SELECT user_id, level_index, physical_damage, magic_damage, physical_defense, magic_defense, mental_power, lifespan FROM players") as cursor:
            players = await cursor.fetchall()
    except Exception as e:
        logger.warning(f"v24迁移：无法读取玩家数据: {e}")
        return

    migrated = 0
    for row in players:
        user_id, level_idx, phy_dmg, mag_dmg, phy_def, mag_def, mp, ls = row

        new_phy_dmg = map_value(phy_dmg, level_idx, 1, 1)  # old_phy_dmg=col1, new_phy_dmg=col1... wait

        # stat indices: old=(1,3,5,7), new=(2,4,6,8)
        new_phy_dmg = map_value(phy_dmg, level_idx, 1, 2)
        new_mag_dmg = map_value(mag_dmg, level_idx, 1, 2)  # same range as phy_dmg
        new_phy_def = map_value(phy_def, level_idx, 3, 4)
        new_mag_def = map_value(mag_def, level_idx, 3, 4)  # same range as phy_def
        new_mp = map_value(mp, level_idx, 5, 6)
        new_ls = map_value(ls, level_idx, 7, 8)

        await conn.execute(
            """UPDATE players SET physical_damage=?, magic_damage=?, physical_defense=?,
               magic_defense=?, mental_power=?, lifespan=? WHERE user_id=?""",
            (new_phy_dmg, new_mag_dmg, new_phy_def, new_mag_def, new_mp, new_ls, user_id)
        )
        migrated += 1

    await conn.commit()
    logger.info(f"v24迁移完成：已重映射 {migrated} 名玩家的突破属性")


@migration(25)
async def _migrate_to_v25(conn: aiosqlite.Connection, config_manager: ConfigManager):
    """迁移到v25 - 洞天福地可拥有多个（每种各一个）"""
    logger.info("开始迁移到v25：洞天福地多持有")

    # SQLite 不支持直接修改 UNIQUE 约束，需要重建表
    await conn.execute("ALTER TABLE blessed_lands RENAME TO blessed_lands_old")
    await conn.execute("""
        CREATE TABLE blessed_lands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            land_type INTEGER NOT NULL DEFAULT 1,
            land_name TEXT NOT NULL DEFAULT '小洞天',
            level INTEGER NOT NULL DEFAULT 1,
            exp_bonus REAL NOT NULL DEFAULT 0.05,
            gold_per_hour INTEGER NOT NULL DEFAULT 100,
            last_collect_time INTEGER NOT NULL DEFAULT 0,
            UNIQUE(user_id, land_type)
        )
    """)
    await conn.execute("INSERT INTO blessed_lands SELECT * FROM blessed_lands_old")
    await conn.execute("DROP TABLE blessed_lands_old")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_blessed_lands_user ON blessed_lands(user_id)")
    await conn.commit()
    logger.info("v25迁移完成：洞天福地可拥有多个")

@migration(26)
async def _migrate_to_v26(conn: aiosqlite.Connection, config_manager: ConfigManager):
    """迁移到v26 - 灵眼改为修炼效率加成"""
    logger.info("开始迁移到v26：灵眼改为修炼效率加成")

    # 将旧的 exp_per_hour 值映射为新的修炼效率百分比
    # eye_type 1: 500 -> 15%, 2: 2000 -> 25%, 3: 8000 -> 35%, 4: 30000 -> 50%
    await conn.execute("UPDATE spirit_eyes SET exp_per_hour = 15 WHERE eye_type = 1")
    await conn.execute("UPDATE spirit_eyes SET exp_per_hour = 25 WHERE eye_type = 2")
    await conn.execute("UPDATE spirit_eyes SET exp_per_hour = 35 WHERE eye_type = 3")
    await conn.execute("UPDATE spirit_eyes SET exp_per_hour = 50 WHERE eye_type = 4")

    await conn.commit()
    logger.info("v26迁移完成：灵眼已改为修炼效率加成")

@migration(27)
async def _migrate_to_v27(conn: aiosqlite.Connection, config_manager: ConfigManager):
    """迁移到v27 - 添加神通系统"""
    logger.info("开始迁移到v27：神通系统")
    await conn.execute("ALTER TABLE players ADD COLUMN shentong TEXT NOT NULL DEFAULT ''")
    await conn.commit()
    logger.info("v27迁移完成：神通系统")
