import asyncio
from functools import wraps
from pathlib import Path
from astrbot.api import logger, AstrBotConfig
from astrbot.api.all import At
from astrbot.api.star import Context, Star, StarTools
from astrbot.api.event import AstrMessageEvent, filter
from .data import DataBase, MigrationManager
from .config_manager import ConfigManager
from .handlers import (
    MiscHandler, PlayerHandler, EquipmentHandler, BreakthroughHandler,
    PillHandler, ShopHandler, StorageRingHandler,
    SectHandlers, BossHandlers, CombatHandlers, RankingHandlers,
    RiftHandlers, AdventureHandlers, AlchemyHandlers, ImpartHandlers,
    NicknameHandler, BankHandlers, BountyHandlers, ImpartPkHandlers,
    BlessedLandHandlers, SpiritFarmHandlers, DualCultivationHandlers, SpiritEyeHandlers,
    TradeHandler, ConsignmentHandler, GMHandlers, AchievementHandler,
    GamblingHandler,
)
from .handlers.utils import get_related_commands_footer
from .managers import (
    CombatManager, SectManager, BossManager, RiftManager,
    RankingManager, AdventureManager, AlchemyManager, ImpartManager,
    BankManager, BountyManager, ImpartPkManager,
    BlessedLandManager, SpiritFarmManager, DualCultivationManager, SpiritEyeManager,
    TradeManager, ConsignmentManager, AchievementManager,
)


def require_whitelist(func):
    """装饰器：检查群聊白名单权限"""
    @wraps(func)
    async def wrapper(self, event: AstrMessageEvent, *args, **kwargs):
        if not self._check_access(event):
            await self._send_access_denied_message(event)
            return
        async for result in func(self, event, *args, **kwargs):
            yield result
    return wrapper

# 指令定义
CMD_HELP = "修仙帮助"
CMD_START_XIUXIAN = "我要修仙"
CMD_PLAYER_INFO = "我的信息"
CMD_START_CULTIVATION = "闭关"
CMD_END_CULTIVATION = "出关"
CMD_CHECK_IN = "签到"
CMD_DAILY_ACTIVITY = "每日活跃"
CMD_ACTIVITY_REWARD = "活跃奖励"
CMD_SHOW_EQUIPMENT = "我的装备"
CMD_EQUIP_ITEM = "装备"
CMD_UNEQUIP_ITEM = "卸下"
CMD_BREAKTHROUGH = "突破"
CMD_BREAKTHROUGH_INFO = "突破信息"
CMD_USE_PILL = "服用丹药"
CMD_SHOW_PILLS = "丹药背包"
CMD_PILL_INFO = "丹药信息"
CMD_PILL_PAVILION = "丹阁"
CMD_WEAPON_PAVILION = "器阁"
CMD_TREASURE_PAVILION = "百宝阁"
CMD_ITEM_INFO = "物品信息"
CMD_VIEW_ITEM = "查看"
CMD_BUY = "购买"
CMD_STORAGE_RING = "储物戒"
CMD_STORE_ITEM = "存入"
CMD_RETRIEVE_ITEM = "取出"
CMD_UPGRADE_RING = "更换储物戒"
CMD_DISCARD_ITEM = "丢弃"
CMD_GIFT_ITEM = "赠予"
CMD_ACCEPT_GIFT = "接收"
CMD_REJECT_GIFT = "拒绝"
CMD_SEARCH_ITEM = "搜索物品"
CMD_RETRIEVE_ALL = "取出所有"

# 宗门系统指令
CMD_CREATE_SECT = "创建宗门"
CMD_JOIN_SECT = "加入宗门"
CMD_LEAVE_SECT = "退出宗门"
CMD_MY_SECT = "我的宗门"
CMD_SECT_LIST = "宗门列表"
CMD_SECT_DONATE = "宗门捐献"
CMD_SECT_KICK = "踢出成员"
CMD_SECT_TRANSFER = "宗主传位"
CMD_SECT_TASK = "宗门任务"
CMD_SECT_POSITION = "职位变更"
CMD_UPGRADE_PRACTICE = "升级修炼"
CMD_SECT_ELIXIR_ROOM = "丹房建设"
CMD_SECT_ELIXIR_GET = "领取丹药"
CMD_SECT_RENAME = "宗门改名"
CMD_PRACTICE_INFO = "修炼信息"

# Boss系统指令
CMD_BOSS_INFO = "世界Boss"
CMD_BOSS_FIGHT = "挑战Boss"
CMD_SPAWN_BOSS = "生成Boss"

# 排行榜指令
CMD_RANK_LEVEL = "境界排行"
CMD_RANK_POWER = "战力排行"
CMD_RANK_WEALTH = "灵石排行"
CMD_RANK_SECT = "宗门排行"
CMD_RANK_DEPOSIT = "存款排行"
CMD_RANK_CONTRIBUTION = "贡献排行"

# 战斗指令
CMD_DUEL = "决斗"
CMD_SPAR = "切磋"
CMD_SCARECROW = "稻草人"

# 秘境系统指令
CMD_RIFT_EXPLORE = "探索秘境"
CMD_RIFT_COMPLETE = "完成探索"
CMD_RIFT_EXIT = "退出秘境"

# 历练系统指令
CMD_ADVENTURE_START = "开始历练"
CMD_ADVENTURE_COMPLETE = "完成历练"
CMD_ADVENTURE_ABORT = "中断历练"
CMD_ADVENTURE_STATUS = "历练状态"
CMD_ADVENTURE_INFO = "历练信息"

# 炼丹系统指令
CMD_ALCHEMY_RECIPES = "丹药配方"
CMD_ALCHEMY_CRAFT = "炼丹"

# 传承系统指令
CMD_IMPART_INFO = "传承信息"

# Phase 1: 道号系统
CMD_CHANGE_NICKNAME = "改道号"

# Phase 2: 灵石银行
CMD_BANK_INFO = "银行信息"
CMD_BANK_DEPOSIT = "存灵石"
CMD_BANK_WITHDRAW = "取灵石"
CMD_BANK_INTEREST = "领取利息"
CMD_BANK_LOAN = "贷款"
CMD_BANK_REPAY = "还款"
CMD_BANK_TRANSACTIONS = "银行流水"
CMD_BANK_BREAKTHROUGH_LOAN = "突破贷款"
CMD_UPGRADE_VIP = "升级会员"
CMD_GAMBLING = "金银阁"

# Phase 2: 悬赏令
CMD_BOUNTY_LIST = "悬赏令"
CMD_BOUNTY_ACCEPT = "接取悬赏"
CMD_BOUNTY_STATUS = "悬赏状态"
CMD_BOUNTY_COMPLETE = "完成悬赏"
CMD_BOUNTY_ABANDON = "放弃悬赏"

# Phase 3: 传承PK
CMD_IMPART_CHALLENGE = "传承挑战"
CMD_IMPART_RANKING = "传承排行"

# Phase 4: 洞天福地
CMD_BLESSED_LAND_INFO = "我的洞天"
CMD_BLESSED_LAND_BUY = "购买洞天"
CMD_BLESSED_LAND_UPGRADE = "升级洞天"

# Phase 4: 灵田
CMD_SPIRIT_FARM_INFO = "我的灵田"
CMD_SPIRIT_FARM_CREATE = "开垦灵田"
CMD_SPIRIT_FARM_PLANT = "种植"
CMD_SPIRIT_FARM_HARVEST = "收获"
CMD_SPIRIT_FARM_UPGRADE = "升级灵田"

# Phase 4: 双修
CMD_DUAL_CULT_REQUEST = "双修"
CMD_DUAL_CULT_ACCEPT = "接受双修"
CMD_DUAL_CULT_REJECT = "拒绝双修"

# Phase 4: 灵眼
CMD_SPIRIT_EYE_INFO = "灵眼信息"
CMD_SPIRIT_EYE_CLAIM = "抢占灵眼"
CMD_SPIRIT_EYE_RELEASE = "释放灵眼"

# 玩家交易系统
CMD_TRADE_START = "交易"
CMD_TRADE_ACCEPT = "接受交易"
CMD_TRADE_REJECT = "拒绝交易"
CMD_TRADE_ADD_ITEM = "添加物品"
CMD_TRADE_ADD_STONES = "添加灵石"
CMD_TRADE_REMOVE_ITEM = "移除物品"
CMD_TRADE_REMOVE_STONES = "移除灵石"
CMD_TRADE_VIEW = "查看交易"
CMD_TRADE_CONFIRM = "确认交易"
CMD_TRADE_CANCEL = "取消交易"

# 寄售行
CMD_CONSIGN_LIST = "寄售"
CMD_CONSIGN_BROWSE = "寄售行"
CMD_CONSIGN_BUY = "购买寄售"
CMD_CONSIGN_MY = "我的寄售"
CMD_CONSIGN_CANCEL = "下架寄售"

CMD_REBIRTH = "弃道重修"
CMD_REROLL_ROOT = "重铸灵根"

# 管理员指令
CMD_DISABLE_ITEM = "禁用物品"
CMD_ENABLE_ITEM = "启用物品"
CMD_LIST_DISABLED = "禁用列表"

# GM指令
CMD_GM_HELP = "GM指令帮助"
CMD_GM_ADD_GOLD = "GM加灵石"
CMD_GM_SUB_GOLD = "GM扣灵石"
CMD_GM_ADD_EXP = "GM加修为"
CMD_GM_SET_LEVEL = "GM设置境界"
CMD_GM_ADD_ITEM = "GM加物品"
CMD_GM_SUB_ITEM = "GM扣物品"
CMD_GM_ADD_PILL = "GM加丹药"
CMD_GM_SUB_PILL = "GM扣丹药"
CMD_GM_VIEW_PLAYER = "GM查看玩家"
CMD_GM_REFRESH_RIFT = "GM刷新秘境"
CMD_GM_COMPENSATION = "GM补偿"

# 玩家指令
CMD_COMPENSATION = "补偿"
CMD_ACHIEVEMENT_LIST = "成就列表"
CMD_EQUIP_ACHIEVEMENT = "装备成就"
CMD_UNEQUIP_ACHIEVEMENT = "卸下成就"

# 菜单系统
CMD_MENU = "菜单"
CMD_MENU_BASICS = "基础"
CMD_MENU_CULTIVATION = "修炼"
CMD_MENU_ITEMS = "物品"
CMD_MENU_EXPLORE = "探索"
CMD_MENU_SECT = "宗门"
CMD_MENU_COMBAT = "战斗"
CMD_MENU_RANKING = "排行"
CMD_MENU_SHOP = "商店"
CMD_MENU_TRADE = "玩家交易"
CMD_MENU_BANK = "银行"

class XiuXianPlugin(Star):
    """修仙插件 - 文字修仙游戏"""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        _current_dir = Path(__file__).parent
        self.config_manager = ConfigManager(_current_dir)

        files_config = self.config.get("FILES", {})
        db_filename = files_config.get("DATABASE_FILE", "xiuxian_data_v2.db")
        plugin_data_path = StarTools.get_data_dir("astrbot_plugin_monixiuxian2")
        plugin_data_path.mkdir(parents=True, exist_ok=True)
        db_path = plugin_data_path / db_filename
        self.db = DataBase(str(db_path))

        # 初始化活跃度追踪器
        from .managers.activity_manager import ActivityTracker
        self.activity_tracker = ActivityTracker(self.db)

        self.misc_handler = MiscHandler(self.db)
        self.spirit_eye_mgr = SpiritEyeManager(self.db)
        self.achievement_mgr = AchievementManager(self.config_manager)
        self.player_handler = PlayerHandler(self.db, self.config, self.config_manager, self.spirit_eye_mgr, self.achievement_mgr, self.activity_tracker)
        self.equipment_handler = EquipmentHandler(self.db, self.config_manager)
        self.breakthrough_handler = BreakthroughHandler(self.db, self.config_manager, self.config)
        self.pill_handler = PillHandler(self.db, self.config_manager)
        self.shop_handler = ShopHandler(self.db, self.config, self.config_manager, self.activity_tracker)
        self.storage_ring_handler = StorageRingHandler(self.db, self.config_manager, self.activity_tracker)
        
        # 初始化核心管理器
        from .core import StorageRingManager
        self.storage_ring_mgr = StorageRingManager(self.db, self.config_manager)
        
        self.combat_mgr = CombatManager()
        from .managers.skill_manager import SkillManager
        self.skill_mgr = SkillManager(self.config_manager)
        self.sect_mgr = SectManager(self.db, self.config_manager, self.activity_tracker)
        self.boss_mgr = BossManager(self.db, self.combat_mgr, self.config_manager, self.storage_ring_mgr, self.skill_mgr)
        self.rift_mgr = RiftManager(self.db, self.config_manager, self.storage_ring_mgr)
        self.rank_mgr = RankingManager(self.db, self.combat_mgr, self.config_manager)
        self.adventure_mgr = AdventureManager(self.db, self.storage_ring_mgr)
        self.alchemy_mgr = AlchemyManager(self.db, self.config_manager, self.storage_ring_mgr, self.activity_tracker)
        self.impart_mgr = ImpartManager(self.db)

        # 初始化新功能处理器
        self.sect_handlers = SectHandlers(self.db, self.sect_mgr)
        self.boss_handlers = BossHandlers(self.db, self.boss_mgr)
        self.combat_handlers = CombatHandlers(self.db, self.combat_mgr, self.config_manager, self.skill_mgr)
        self.ranking_handlers = RankingHandlers(self.db, self.rank_mgr)
        self.rift_handlers = RiftHandlers(self.db, self.rift_mgr)
        self.adventure_handlers = AdventureHandlers(self.db, self.adventure_mgr)
        self.alchemy_handlers = AlchemyHandlers(self.db, self.alchemy_mgr)
        self.impart_handlers = ImpartHandlers(self.db, self.impart_mgr)
        self.nickname_handler = NicknameHandler(self.db)  # Phase 1
        
        # Phase 2: 灵石银行和悬赏令
        self.bank_mgr = BankManager(self.db, self.config_manager.game_config, self.activity_tracker)
        self.bounty_mgr = BountyManager(self.db, self.storage_ring_mgr, self.config_manager.items_data, self.config_manager.skills_data, self.activity_tracker)
        self.bank_handlers = BankHandlers(self.db, self.bank_mgr)
        self.gambling_handler = GamblingHandler(self.db)
        self.bounty_handlers = BountyHandlers(self.db, self.bounty_mgr)
        
        # Phase 3: 传承PK
        self.impart_pk_mgr = ImpartPkManager(self.db, self.combat_mgr, self.config_manager)
        self.impart_pk_handlers = ImpartPkHandlers(self.db, self.impart_pk_mgr)
        
        # Phase 4: 扩展功能
        self.blessed_land_mgr = BlessedLandManager(self.db)
        self.blessed_land_handlers = BlessedLandHandlers(self.db, self.blessed_land_mgr)
        self.spirit_farm_mgr = SpiritFarmManager(self.db, self.storage_ring_mgr, self.activity_tracker)
        self.spirit_farm_handlers = SpiritFarmHandlers(self.db, self.spirit_farm_mgr)
        self.dual_cult_mgr = DualCultivationManager(self.db, self.pill_handler.pill_manager)
        self.dual_cult_handlers = DualCultivationHandlers(self.db, self.dual_cult_mgr)
        self.spirit_eye_handlers = SpiritEyeHandlers(self.db, self.spirit_eye_mgr)

        # 神通系统
        from .handlers.skill_handler import SkillHandler
        self.skill_handler = SkillHandler(
            self.db, self.config_manager, self.skill_mgr,
            self.equipment_handler.equipment_manager,
            self.equipment_handler.storage_ring_manager
        )

        # 玩家交易系统：manager 在 initialize() 中创建（需要 db.conn）
        self.trade_mgr = None
        self.consignment_mgr = None
        self.trade_handler = None
        self.consignment_handler = None
        self.gm_handlers = GMHandlers(self.db, self.config_manager)
        self.achievement_handler = AchievementHandler(self.db, self.achievement_mgr)
        
        self.boss_task = None # Boss生成任务
        self.loan_check_task = None # 贷款逾期检查任务
        self.spirit_eye_task = None # 灵眼生成任务
        self.bounty_check_task = None  # 悬赏过期检查任务
        self.consignment_check_task = None  # 寄售过期检查任务
        self.trade_check_task = None  # 交易超时检查任务
        self.rift_daily_task = None  # 秘境每日广播任务
        self.pavilion_refresh_task = None  # 商铺自动刷新任务
        self.sect_material_task = None  # 宗门资材发放任务
        self.sect_owner_change_task = None  # 自动换宗主任务

        access_control_config = self.config.get("ACCESS_CONTROL", {})
        self.whitelist_groups = [str(g) for g in access_control_config.get("WHITELIST_GROUPS", [])]
        self.boss_admins = [str(a) for a in access_control_config.get("BOSS_ADMINS", [])]
        self.boss_enabled = bool(access_control_config.get("BOSS_ENABLED", False))

        logger.info(f"【修仙插件】XiuXianPlugin 初始化完成，数据库路径: {db_path}")

    def _check_access(self, event: AstrMessageEvent) -> bool:
        """检查访问权限，支持群聊白名单控制"""
        # 如果没有配置白名单，允许所有访问
        if not self.whitelist_groups:
            return True

        # 获取群组ID，私聊时为None
        group_id = event.get_group_id()

        # 如果是私聊，允许访问
        if not group_id:
            return True

        # 检查群组是否在白名单中
        if str(group_id) in self.whitelist_groups:
            return True

        return False

    def _check_boss_admin(self, event: AstrMessageEvent) -> bool:
        """检查是否为Boss管理员"""
        if not self.boss_admins:
            return False
        sender_id = str(event.get_sender_id())
        return sender_id in self.boss_admins

    async def _send_access_denied_message(self, event: AstrMessageEvent):
        """发送访问被拒绝的提示消息"""
        try:
            await event.send("抱歉，此群聊未在修仙插件的白名单中，无法使用相关功能。")
        except:
            # 如果发送失败，静默处理
            pass

    async def initialize(self):
        await self.db.connect()
        migration_manager = MigrationManager(self.db.conn, self.config_manager)
        await migration_manager.migrate()

        # 玩家交易系统：在数据库连接后初始化
        trade_config = self.config.get("TRADE", {})
        self.trade_mgr = TradeManager(self.db, config=trade_config)
        self.consignment_mgr = ConsignmentManager(self.db, config=trade_config)
        self.trade_handler = TradeHandler(self.db, self.trade_mgr)
        self.consignment_handler = ConsignmentHandler(self.db, self.consignment_mgr, self.config_manager)

        # 确保系统配置表存在
        await self.db.ext.ensure_system_config_table()
        
        # 启动定时任务
        if self.boss_enabled:
            self.boss_task = asyncio.create_task(self._schedule_boss_spawn())
        else:
            logger.info("【修仙插件】Boss系统已禁用，跳过Boss定时生成")
        self.loan_check_task = asyncio.create_task(self._schedule_loan_check())
        self.spirit_eye_task = asyncio.create_task(self._schedule_spirit_eye_spawn())
        self.bounty_check_task = asyncio.create_task(self._schedule_bounty_check())
        self.consignment_check_task = asyncio.create_task(self._schedule_consignment_check())
        self.trade_check_task = asyncio.create_task(self._schedule_trade_check())
        self.rift_daily_task = asyncio.create_task(self._schedule_rift_daily())
        self.pavilion_refresh_task = asyncio.create_task(self._schedule_pavilion_refresh())
        self.sect_material_task = asyncio.create_task(self._schedule_sect_material_distribution())
        self.sect_owner_change_task = asyncio.create_task(self._schedule_auto_sect_owner_change())
        
        logger.info("【修仙插件】已加载。")

    async def terminate(self):
        if self.boss_task:
            self.boss_task.cancel()
        if self.loan_check_task:
            self.loan_check_task.cancel()
        if self.spirit_eye_task:
            self.spirit_eye_task.cancel()
        if self.bounty_check_task:
            self.bounty_check_task.cancel()
        if self.consignment_check_task:
            self.consignment_check_task.cancel()
        if self.trade_check_task:
            self.trade_check_task.cancel()
        if self.rift_daily_task:
            self.rift_daily_task.cancel()
        if self.pavilion_refresh_task:
            self.pavilion_refresh_task.cancel()
        if self.sect_material_task:
            self.sect_material_task.cancel()
        if self.sect_owner_change_task:
            self.sect_owner_change_task.cancel()
        await self.db.close()
        logger.info("【修仙插件】已卸载。")
        
    async def _schedule_boss_spawn(self):
        """Boss定时生成任务（支持持久化和指数退避）"""
        import time
        
        retry_count = 0
        max_retry_delay = 3600
        
        while True:
            try:
                await self.db.ensure_connection()
                interval = self.config_manager.boss_config.get("spawn_interval", 3600)
                
                # 检查是否有存储的下次刷新时间
                next_spawn_str = await self.db.ext.get_system_config("boss_next_spawn_time")
                current_time = int(time.time())
                
                if next_spawn_str:
                    next_spawn_time = int(next_spawn_str)
                    remaining = next_spawn_time - current_time
                    if remaining > 0:
                        logger.info(f"【修仙插件】Boss将在 {remaining} 秒后刷新")
                        await asyncio.sleep(remaining)
                else:
                    next_spawn_time = current_time + interval
                    await self.db.ext.set_system_config("boss_next_spawn_time", str(next_spawn_time))
                    await asyncio.sleep(interval)
                
                # 尝试生成Boss
                if self.boss_mgr:
                    success, msg, boss = await self.boss_mgr.auto_spawn_boss()
                    if success and boss:
                        logger.info(f"【修仙插件】自动生成Boss: {boss.boss_name}")
                        await self._broadcast_boss_spawn(boss)
                
                # 设置下次刷新时间
                next_spawn_time = int(time.time()) + interval
                await self.db.ext.set_system_config("boss_next_spawn_time", str(next_spawn_time))
                
                # 成功后重置重试计数
                retry_count = 0
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Boss生成任务异常: {e}")
                retry_count += 1
                delay = min(60 * (2 ** retry_count), max_retry_delay)
                logger.info(f"【修仙插件】Boss任务将在 {delay} 秒后重试（第{retry_count}次）")
                await asyncio.sleep(delay)

    async def _broadcast_boss_spawn(self, boss):
        """广播Boss刷新消息到所有白名单群聊"""
        from astrbot.api.event import MessageChain
        
        if not self.whitelist_groups:
            logger.debug("【修仙插件】未配置白名单群聊，跳过Boss广播")
            return
        
        # 构建广播消息
        broadcast_msg = (
            f"👹 世界Boss降临！\n"
            f"━━━━━━━━━━━━━━━\n"
            f"名称：{boss.boss_name}\n"
            f"境界：{boss.boss_level}\n"
            f"血量：{boss.hp}/{boss.max_hp}\n"
            f"攻击：{boss.atk}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💰 击败奖励：{boss.stone_reward} 灵石\n"
            f"⚔️ 发送「挑战Boss」参与讨伐！"
        )
        
        message_chain = MessageChain().message(broadcast_msg)
        
        # 获取所有平台实例
        try:
            platforms = self.context.platform_manager.get_insts()
            for platform in platforms:
                platform_name = platform.meta().name if hasattr(platform, 'meta') and callable(platform.meta) else "unknown"
                for group_id in self.whitelist_groups:
                    # 构建 unified_msg_origin: platform_name:message_type:session_id
                    umo = f"{platform_name}:GroupMessage:{group_id}"
                    try:
                        await self.context.send_message(umo, message_chain)
                        logger.debug(f"【修仙插件】Boss广播已发送到群 {group_id}")
                    except Exception as e:
                        logger.warning(f"【修仙插件】Boss广播发送失败 (群{group_id}): {e}")
        except Exception as e:
            logger.error(f"【修仙插件】Boss广播异常: {e}")

    async def _broadcast_boss_defeat(self, player_name: str, battle_result: dict):
        """广播Boss被击杀消息到所有白名单群聊"""
        from astrbot.api.event import MessageChain
        
        if not self.whitelist_groups:
            return
        
        reward = battle_result.get("reward", 0)
        rounds = battle_result.get("rounds", 0)
        
        broadcast_msg = (
            f"🎉 世界Boss已被击杀！\n"
            f"━━━━━━━━━━━━━━━\n"
            f"击杀者：{player_name}\n"
            f"战斗回合：{rounds}\n"
            f"获得奖励：{reward} 灵石\n"
            f"━━━━━━━━━━━━━━━\n"
            f"恭喜大侠！下一只Boss即将刷新..."
        )
        
        message_chain = MessageChain().message(broadcast_msg)
        
        try:
            platforms = self.context.platform_manager.get_insts()
            for platform in platforms:
                platform_name = platform.meta().name if hasattr(platform, 'meta') and callable(platform.meta) else "unknown"
                for group_id in self.whitelist_groups:
                    umo = f"{platform_name}:GroupMessage:{group_id}"
                    try:
                        await self.context.send_message(umo, message_chain)
                    except Exception as e:
                        logger.warning(f"【修仙插件】Boss击杀广播发送失败 (群{group_id}): {e}")
        except Exception as e:
            logger.error(f"【修仙插件】Boss击杀广播异常: {e}")

    async def _schedule_rift_daily(self):
        """秘境每日定时广播任务 - 每天10:00自动选择并广播今日秘境"""
        from datetime import datetime, timedelta

        retry_count = 0
        max_retry_delay = 3600

        while True:
            try:
                await self.db.ensure_connection()

                # 计算距离下一个10:00的秒数
                now = datetime.now()
                target_today = now.replace(hour=10, minute=0, second=0, microsecond=0)
                if now >= target_today:
                    target = target_today + timedelta(days=1)
                else:
                    target = target_today

                delta = (target - now).total_seconds()
                logger.info(f"【修仙插件】秘境广播将在 {int(delta)} 秒后（{target.strftime('%Y-%m-%d %H:%M')}）执行")
                await asyncio.sleep(delta)

                # 选中今日秘境并广播
                rift_def = await self.rift_mgr._get_today_rift()
                if rift_def:
                    logger.info(f"【修仙插件】今日秘境已开放: {rift_def['name']}")
                    await self._broadcast_rift_open(rift_def)
                else:
                    logger.warning("【修仙插件】秘境广播失败：未配置秘境数据")

                retry_count = 0

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"秘境广播任务异常: {e}")
                retry_count += 1
                delay = min(60 * (2 ** retry_count), max_retry_delay)
                logger.info(f"【修仙插件】秘境广播任务将在 {delay} 秒后重试（第{retry_count}次）")
                await asyncio.sleep(delay)

    async def _broadcast_to_whitelist_groups(self, message: str):
        """向所有白名单群发送消息（公共广播方法）"""
        from astrbot.api.event import MessageChain

        if not self.whitelist_groups:
            return

        message_chain = MessageChain().message(message)
        try:
            platforms = self.context.platform_manager.get_insts()
            for platform in platforms:
                platform_name = platform.meta().name if hasattr(platform, 'meta') and callable(platform.meta) else "unknown"
                for group_id in self.whitelist_groups:
                    umo = f"{platform_name}:GroupMessage:{group_id}"
                    try:
                        await self.context.send_message(umo, message_chain)
                    except Exception as e:
                        logger.warning(f"【修仙插件】广播发送失败 (群{group_id}): {e}")
                    await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"【修仙插件】广播异常: {e}")

    async def _broadcast_rift_open(self, rift_def: dict):
        """广播秘境开放消息到所有白名单群聊"""
        rift_name = rift_def.get("name", "未知秘境")
        duration = rift_def.get("duration", 1800)

        broadcast_msg = (
            f"🌀 秘境已开放！\n"
            f"━━━━━━━━━━━━━━━\n"
            f"今日秘境：【{rift_name}】\n"
            f"探索时长：{duration // 60} 分钟\n"
            f"每人每日限探索 1 次\n"
            f"━━━━━━━━━━━━━━━\n"
            f"⏰ 开放时间：10:00 ~ 21:00\n"
            f"💡 使用 /探索秘境 进入"
        )
        await self._broadcast_to_whitelist_groups(broadcast_msg)

    async def _schedule_loan_check(self):
        """贷款逾期检查定时任务（每小时检查一次，支持指数退避）"""
        import time
        
        retry_count = 0
        max_retry_delay = 3600
        
        while True:
            try:
                await self.db.ensure_connection()
                # 每小时检查一次逾期贷款
                await asyncio.sleep(3600)
                
                # 处理逾期贷款
                processed = await self.bank_mgr.check_and_process_overdue_loans()
                
                if processed:
                    logger.info(f"【修仙插件】处理了 {len(processed)} 笔逾期贷款")
                    # 广播逾期玩家被追杀的消息
                    for loan_info in processed:
                        if loan_info.get("death"):
                            await self._broadcast_loan_death(loan_info)
                
                # 成功后重置重试计数
                retry_count = 0
                            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"贷款检查任务异常: {e}")
                retry_count += 1
                delay = min(60 * (2 ** retry_count), max_retry_delay)
                logger.info(f"【修仙插件】贷款检查任务将在 {delay} 秒后重试（第{retry_count}次）")
                await asyncio.sleep(delay)

    async def _broadcast_loan_death(self, loan_info: dict):
        """广播贷款逾期玩家被追杀的消息"""
        player_name = loan_info.get("player_name", "某修士")
        principal = loan_info.get("principal", 0)

        broadcast_msg = (
            f"💀 银行追杀公告 💀\n"
            f"━━━━━━━━━━━━━━━\n"
            f"修士【{player_name}】因贷款逾期未还\n"
            f"欠款：{principal:,} 灵石\n"
            f"已被灵石银行追杀致死！\n"
            f"━━━━━━━━━━━━━━━\n"
            f"⚠️ 借贷有风险，还款需及时！"
        )
        await self._broadcast_to_whitelist_groups(broadcast_msg)

    async def _schedule_spirit_eye_spawn(self):
        """灵眼生成定时任务（每2小时生成一个，支持指数退避）"""
        import time
        
        retry_count = 0
        max_retry_delay = 3600
        
        while True:
            try:
                await self.db.ensure_connection()
                # 每4小时生成一个灵眼
                spawn_interval = 14400
                
                # 检查是否有存储的下次刷新时间
                next_spawn_str = await self.db.ext.get_system_config("spirit_eye_next_spawn_time")
                current_time = int(time.time())
                
                if next_spawn_str:
                    next_spawn_time = int(next_spawn_str)
                    remaining = next_spawn_time - current_time
                    if remaining > 0:
                        logger.info(f"【修仙插件】灵眼将在 {remaining} 秒后刷新")
                        await asyncio.sleep(remaining)
                else:
                    next_spawn_time = current_time + spawn_interval
                    await self.db.ext.set_system_config("spirit_eye_next_spawn_time", str(next_spawn_time))
                    await asyncio.sleep(spawn_interval)
                
                # 生成灵眼
                success, msg = await self.spirit_eye_mgr.spawn_spirit_eye()
                if success:
                    logger.info(f"【修仙插件】{msg}")
                    await self._broadcast_spirit_eye_spawn(msg)

                # 清理超过4小时未被抢占的灵眼
                cleaned = await self.spirit_eye_mgr.cleanup_expired_eyes()
                if cleaned > 0:
                    logger.info(f"【修仙插件】清理了 {cleaned} 个过期灵眼")

                # 设置下次刷新时间
                next_spawn_time = int(time.time()) + spawn_interval
                await self.db.ext.set_system_config("spirit_eye_next_spawn_time", str(next_spawn_time))
                
                # 成功后重置重试计数
                retry_count = 0
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"灵眼生成任务异常: {e}")
                retry_count += 1
                delay = min(60 * (2 ** retry_count), max_retry_delay)
                logger.info(f"【修仙插件】灵眼任务将在 {delay} 秒后重试（第{retry_count}次）")
                await asyncio.sleep(delay)

    async def _schedule_bounty_check(self):
        """悬赏过期检查定时任务（每30分钟检查一次）"""
        while True:
            try:
                await self.db.ensure_connection()
                await asyncio.sleep(1800)  # 30分钟
                expired = await self.bounty_mgr.check_and_expire_bounties()
                if expired > 0:
                    logger.info(f"【修仙插件】处理了 {expired} 个过期悬赏任务")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"悬赏检查任务异常: {e}")
                await asyncio.sleep(60)

    async def _schedule_consignment_check(self):
        """寄售行过期检查任务（每小时检查一次，可通过 TRADE.CONSIGNMENT_CHECK_INTERVAL_SECONDS 调整）"""
        interval = int(self.config.get("TRADE", {}).get("CONSIGNMENT_CHECK_INTERVAL_SECONDS", 3600))
        while True:
            try:
                await self.db.ensure_connection()
                await asyncio.sleep(interval)
                expired = await self.consignment_mgr.expire_old_listings()
                if expired > 0:
                    logger.info(f"【修仙插件】处理了 {expired} 个过期寄售物品")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"寄售过期检查任务异常: {e}")
                await asyncio.sleep(60)

    async def _schedule_trade_check(self):
        """交易超时检查任务（每 5 分钟检查一次，可通过 TRADE.TRADE_CHECK_INTERVAL_SECONDS 调整）"""
        interval = int(self.config.get("TRADE", {}).get("TRADE_CHECK_INTERVAL_SECONDS", 300))
        while True:
            try:
                await self.db.ensure_connection()
                await asyncio.sleep(interval)
                expired = await self.trade_mgr.expire_overdue_trades()
                if expired > 0:
                    logger.info(f"【修仙插件】处理了 {expired} 个超时交易")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"交易超时检查任务异常: {e}")
                await asyncio.sleep(60)

    async def _broadcast_spirit_eye_spawn(self, msg: str):
        """广播灵眼刷新消息"""
        broadcast_msg = f"👁️ {msg}\n💡 使用 /灵眼信息 查看详情"
        await self._broadcast_to_whitelist_groups(broadcast_msg)

    async def _broadcast_pavilion_refresh(self, shop_name: str, items: list, offers: list = None):
        """广播商铺刷新消息"""
        if not items:
            return
        item_names = [item.get("name", "未知") for item in items[:8]]
        summary = "、".join(item_names)
        if len(items) > 8:
            summary += f"等{len(items)}件"
        cmd_name = shop_name.replace("阁", "阁")  # 丹阁→丹阁, 器阁→器阁, 百宝阁→百宝阁
        broadcast_msg = (
            f"🏪 【{shop_name}】新货上架！\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📦 本次上架：{summary}\n"
        )
        if offers:
            offer_names = []
            for o in offers:
                disc_pct = int((1.0 - o.get('discount', 1.0)) * 100)
                offer_names.append(f"{o['name']} [{disc_pct}%折]")
            broadcast_msg += f"🔥 限时特价：{'、'.join(offer_names)}\n"
        broadcast_msg += f"💡 输入 /{cmd_name} 查看详情"
        await self._broadcast_to_whitelist_groups(broadcast_msg)

    async def _init_pavilions_if_empty(self):
        """首次启动时初始化商铺（如果数据库中无数据）"""
        pavilions = [
            ("pill_pavilion", self.shop_handler.shop_manager.get_pills_for_display,
             self.config.get("PAVILION_PILL_COUNT", 10), "丹阁"),
            ("weapon_pavilion", self.shop_handler.shop_manager.get_weapons_for_display,
             self.config.get("PAVILION_WEAPON_COUNT", 10), "器阁"),
            ("treasure_pavilion", self.shop_handler.shop_manager.get_all_items_for_display,
             self.config.get("PAVILION_TREASURE_COUNT", 15), "百宝阁"),
        ]
        for pavilion_id, item_getter, count, display_name in pavilions:
            _, current_items = await self.shop_handler.db.get_shop_data(pavilion_id)
            if not current_items:
                import time as _time
                new_items = self.shop_handler.shop_manager.generate_pavilion_items(item_getter, count)
                offer_count = self.config.get("LIMITED_OFFER_COUNT", 2)
                offer_discount = self.config.get("LIMITED_OFFER_DISCOUNT", 0.7)
                self.shop_handler.shop_manager.mark_limited_offers(new_items, offer_count, offer_discount)
                await self.shop_handler.db.update_shop_data(pavilion_id, int(_time.time()), new_items)
                logger.info(f"【修仙插件】{display_name}首次初始化，生成 {len(new_items)} 件商品")

    async def _schedule_pavilion_refresh(self):
        """定时自动刷新丹阁/器阁/百宝阁，刷新后群聊广播"""
        import time
        retry_count = 0
        max_retry_delay = 3600

        # 首次启动时初始化空商铺
        try:
            await self._init_pavilions_if_empty()
        except Exception as e:
            logger.error(f"【修仙插件】商铺初始化异常: {e}")

        while True:
            try:
                await self.db.ensure_connection()
                refresh_hours = self.config.get("PAVILION_REFRESH_HOURS", 6)
                if refresh_hours <= 0:
                    await asyncio.sleep(3600)
                    continue

                # 计算距下一个刷新周期的时间
                # 读取任意一个商铺的 last_refresh 来对齐周期
                last_refresh, _ = await self.shop_handler.db.get_shop_data("pill_pavilion")
                current_time = int(time.time())
                if last_refresh and last_refresh > 0:
                    next_refresh = last_refresh + refresh_hours * 3600
                    remaining = next_refresh - current_time
                    if remaining > 0:
                        await asyncio.sleep(remaining)
                else:
                    # 无历史记录，立即刷新
                    pass

                # 检查并刷新每个商铺
                pavilions = [
                    ("pill_pavilion", self.shop_handler.shop_manager.get_pills_for_display,
                     self.config.get("PAVILION_PILL_COUNT", 10), "丹阁"),
                    ("weapon_pavilion", self.shop_handler.shop_manager.get_weapons_for_display,
                     self.config.get("PAVILION_WEAPON_COUNT", 10), "器阁"),
                    ("treasure_pavilion", self.shop_handler.shop_manager.get_all_items_for_display,
                     self.config.get("PAVILION_TREASURE_COUNT", 15), "百宝阁"),
                ]

                for pavilion_id, item_getter, count, display_name in pavilions:
                    last_refresh, current_items = await self.shop_handler.db.get_shop_data(pavilion_id)
                    if not current_items or self.shop_handler.shop_manager.should_refresh_shop(last_refresh, refresh_hours):
                        new_items = self.shop_handler.shop_manager.generate_pavilion_items(item_getter, count)
                        # 标记限时特价商品
                        offer_count = self.config.get("LIMITED_OFFER_COUNT", 2)
                        offer_discount = self.config.get("LIMITED_OFFER_DISCOUNT", 0.7)
                        offers = self.shop_handler.shop_manager.mark_limited_offers(new_items, offer_count, offer_discount)
                        await self.shop_handler.db.update_shop_data(pavilion_id, int(time.time()), new_items)
                        await self._broadcast_pavilion_refresh(display_name, new_items, offers)
                        logger.info(f"【修仙插件】{display_name}自动刷新，{len(new_items)} 件商品，{len(offers)} 件限时特价")

                retry_count = 0

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"【修仙插件】商铺刷新任务异常: {e}")
                retry_count += 1
                delay = min(60 * (2 ** retry_count), max_retry_delay)
                logger.info(f"【修仙插件】商铺刷新任务将在 {delay} 秒后重试（第{retry_count}次）")
                await asyncio.sleep(delay)

    async def _schedule_sect_material_distribution(self):
        """每日定时发放宗门资材（根据建设度 × 倍率）"""
        import time as _time
        retry_count = 0
        max_retry_delay = 3600

        while True:
            try:
                sect_config = self.config_manager.sect_config if hasattr(self, 'config_manager') else {}
                dist_config = sect_config.get("material_distribution", {})
                target_hour = dist_config.get("hour", 12)
                rate = dist_config.get("rate", 0.1)

                # 计算到下一个目标小时的等待时间
                now = _time.localtime()
                current_hour = now.tm_hour
                current_min = now.tm_min
                current_sec = now.tm_sec

                if current_hour < target_hour:
                    wait_seconds = (target_hour - current_hour) * 3600 - current_min * 60 - current_sec
                elif current_hour == target_hour and current_min == 0 and current_sec < 30:
                    wait_seconds = 0  # 刚好在目标时间，立即执行
                else:
                    wait_seconds = (24 - current_hour + target_hour) * 3600 - current_min * 60 - current_sec

                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)

                await self.db.ensure_connection()
                sects = await self.db.ext.get_all_sects_summary()
                for s in sects:
                    materials_gain = int(s["sect_scale"] * rate)
                    if materials_gain > 0:
                        await self.db.ext.update_sect_materials(s["sect_id"], materials_gain, operation=1)
                logger.info(f"【修仙插件】宗门资材发放完成，共 {len(sects)} 个宗门")

                retry_count = 0
                # 等待到下一个周期（24小时后）
                await asyncio.sleep(86400 - 60)  # 减去60秒避免漂移

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"【修仙插件】宗门资材发放异常: {e}")
                retry_count += 1
                delay = min(60 * (2 ** retry_count), max_retry_delay)
                await asyncio.sleep(delay)

    async def _schedule_auto_sect_owner_change(self):
        """定期检查不活跃宗主并自动传位"""
        import time as _time
        from datetime import datetime, timedelta
        retry_count = 0
        max_retry_delay = 3600

        while True:
            try:
                sect_config = self.config_manager.sect_config if hasattr(self, 'config_manager') else {}
                owner_config = sect_config.get("auto_owner_change", {})
                inactive_days = owner_config.get("inactive_days", 7)

                await asyncio.sleep(3600)  # 每小时检查一次

                await self.db.ensure_connection()
                sects = await self.db.ext.get_all_sects_summary()
                today = datetime.now()

                for s in sects:
                    owner_id = s["sect_owner"]
                    owner = await self.db.get_player_by_id(owner_id)
                    if not owner:
                        continue

                    last_date_str = owner.last_check_in_date
                    if not last_date_str:
                        continue

                    try:
                        last_date = datetime.strptime(last_date_str, "%Y-%m-%d")
                    except ValueError:
                        continue

                    if (today - last_date).days < inactive_days:
                        continue

                    # 宗主不活跃，寻找继承者
                    members = await self.db.ext.get_sect_members(s["sect_id"])
                    candidates = [m for m in members if m.user_id != owner_id]
                    if not candidates:
                        continue

                    # 按职位（升序）→ 贡献（降序）排序
                    candidates.sort(key=lambda m: (m.sect_position, -m.sect_contribution))
                    new_owner = candidates[0]

                    # 执行传位
                    await self.db.ext.update_player_sect_info(new_owner.user_id, s["sect_id"], 0)
                    await self.db.ext.update_player_sect_info(owner_id, s["sect_id"], 1)
                    s_obj = await self.db.ext.get_sect_by_id(s["sect_id"])
                    if s_obj:
                        s_obj.sect_owner = new_owner.user_id
                        await self.db.ext.update_sect(s_obj)

                    logger.info(
                        f"【修仙插件】宗主自动传位：{s['sect_name']} 宗主 {owner.user_name} 离线超 {inactive_days} 天，"
                        f"由 {new_owner.user_name} 继任"
                    )

                retry_count = 0

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"【修仙插件】自动换宗主任务异常: {e}")
                retry_count += 1
                delay = min(60 * (2 ** retry_count), max_retry_delay)
                await asyncio.sleep(delay)

    @filter.command(CMD_HELP, "显示帮助信息")
    @require_whitelist
    async def handle_help(self, event: AstrMessageEvent):
        async for r in self.misc_handler.handle_help(event):
            yield r
        footer = get_related_commands_footer("修仙帮助")
        if footer:
            yield event.plain_result(footer)

    @filter.command(CMD_MENU, "显示功能菜单")
    @require_whitelist
    async def handle_menu(self, event: AstrMessageEvent):
        async for r in self.misc_handler.handle_menu(event):
            yield r

    @filter.command(CMD_MENU_BASICS, "基础功能菜单")
    @require_whitelist
    async def handle_menu_basics(self, event: AstrMessageEvent):
        async for r in self.misc_handler.handle_menu_basics(event):
            yield r

    @filter.command(CMD_MENU_CULTIVATION, "修炼功能菜单")
    @require_whitelist
    async def handle_menu_cultivation(self, event: AstrMessageEvent):
        async for r in self.misc_handler.handle_menu_cultivation(event):
            yield r

    @filter.command(CMD_MENU_ITEMS, "物品功能菜单")
    @require_whitelist
    async def handle_menu_items(self, event: AstrMessageEvent):
        async for r in self.misc_handler.handle_menu_items(event):
            yield r

    @filter.command(CMD_MENU_EXPLORE, "探索功能菜单")
    @require_whitelist
    async def handle_menu_explore(self, event: AstrMessageEvent):
        async for r in self.misc_handler.handle_menu_explore(event):
            yield r

    @filter.command(CMD_MENU_SECT, "宗门功能菜单")
    @require_whitelist
    async def handle_menu_sect(self, event: AstrMessageEvent):
        async for r in self.misc_handler.handle_menu_sect(event):
            yield r

    @filter.command(CMD_MENU_COMBAT, "战斗功能菜单")
    @require_whitelist
    async def handle_menu_combat(self, event: AstrMessageEvent):
        async for r in self.misc_handler.handle_menu_combat(event):
            yield r

    @filter.command(CMD_MENU_RANKING, "排行功能菜单")
    @require_whitelist
    async def handle_menu_ranking(self, event: AstrMessageEvent):
        async for r in self.misc_handler.handle_menu_ranking(event):
            yield r

    @filter.command(CMD_MENU_TRADE, "玩家交易菜单")
    @require_whitelist
    async def handle_menu_trade(self, event: AstrMessageEvent):
        async for r in self.misc_handler.handle_menu_trade(event):
            yield r

    @filter.command(CMD_MENU_BANK, "灵石银行菜单")
    @require_whitelist
    async def handle_menu_bank(self, event: AstrMessageEvent):
        async for r in self.misc_handler.handle_menu_bank(event):
            yield r

    @filter.command(CMD_MENU_SHOP, "商店功能菜单")
    @require_whitelist
    async def handle_menu_shop(self, event: AstrMessageEvent):
        async for r in self.misc_handler.handle_menu_shop(event):
            yield r

    @filter.command(CMD_COMPENSATION, "领取GM补偿")
    @require_whitelist
    async def handle_compensation(self, event: AstrMessageEvent):
        user_id = str(event.get_sender_id())
        msg = await self.gm_handlers.handle_claim_compensation(user_id)
        yield event.plain_result(msg)

    @filter.command(CMD_ACHIEVEMENT_LIST, "查看成就列表")
    @require_whitelist
    async def handle_achievement_list(self, event: AstrMessageEvent):
        async for r in self.achievement_handler.handle_list(event):
            yield r

    @filter.command(CMD_EQUIP_ACHIEVEMENT, "装备成就 [名称]")
    @require_whitelist
    async def handle_equip_achievement(self, event: AstrMessageEvent, achievement_name: str = ""):
        async for r in self.achievement_handler.handle_equip(event, achievement_name):
            yield r

    @filter.command(CMD_UNEQUIP_ACHIEVEMENT, "卸下当前装备的成就")
    @require_whitelist
    async def handle_unequip_achievement(self, event: AstrMessageEvent):
        async for r in self.achievement_handler.handle_unequip(event):
            yield r

    @filter.command(CMD_START_XIUXIAN, "开始你的修仙之路")
    @require_whitelist
    async def handle_start_xiuxian(self, event: AstrMessageEvent, cultivation_type: str = ""):
        async for r in self.player_handler.handle_start_xiuxian(event, cultivation_type):
            yield r

    @filter.command(CMD_PLAYER_INFO, "查看你的角色信息")
    @require_whitelist
    async def handle_player_info(self, event: AstrMessageEvent):
        async for r in self.player_handler.handle_player_info(event):
            yield r

    @filter.command(CMD_REBIRTH, "弃道重修（7天一次）")
    @require_whitelist
    async def handle_rebirth(self, event: AstrMessageEvent, confirm: str = ""):
        async for r in self.player_handler.handle_rebirth(event, confirm):
            yield r

    @filter.command(CMD_REROLL_ROOT, "重铸灵根（25万灵石）")
    @require_whitelist
    async def handle_reroll_root(self, event: AstrMessageEvent):
        async for r in self.player_handler.handle_reroll_root(event):
            yield r

    @filter.command(CMD_START_CULTIVATION, "开始闭关修炼")
    @require_whitelist
    async def handle_start_cultivation(self, event: AstrMessageEvent):
        async for r in self.player_handler.handle_start_cultivation(event):
            yield r

    @filter.command(CMD_END_CULTIVATION, "结束闭关修炼")
    @require_whitelist
    async def handle_end_cultivation(self, event: AstrMessageEvent):
        async for r in self.player_handler.handle_end_cultivation(event):
            yield r

    @filter.command(CMD_CHECK_IN, "每日签到领取灵石")
    @require_whitelist
    async def handle_check_in(self, event: AstrMessageEvent):
        async for r in self.player_handler.handle_check_in(event):
            yield r

    @filter.command(CMD_DAILY_ACTIVITY, "查看每日活跃度任务进度")
    @require_whitelist
    async def handle_daily_activity(self, event: AstrMessageEvent):
        user_id = event.get_sender_id()
        player = await self.db.get_player_by_id(user_id)
        if not player:
            yield event.plain_result("❌ 你还未踏入修仙之路！请先使用「我要修仙」创建角色。")
            return
        result = await self.activity_tracker.get_daily_activity_display(player)
        yield event.plain_result(result)

    @filter.command(CMD_ACTIVITY_REWARD, "领取每日活跃奖励")
    @require_whitelist
    async def handle_activity_reward(self, event: AstrMessageEvent):
        user_id = event.get_sender_id()
        player = await self.db.get_player_by_id(user_id)
        if not player:
            yield event.plain_result("❌ 你还未踏入修仙之路！请先使用「我要修仙」创建角色。")
            return
        result = await self.activity_tracker.claim_reward(player)
        yield event.plain_result(result)

    @filter.command(CMD_SHOW_EQUIPMENT, "查看已装备的物品")
    @require_whitelist
    async def handle_show_equipment(self, event: AstrMessageEvent):
        async for r in self.equipment_handler.handle_show_equipment(event):
            yield r

    @filter.command(CMD_EQUIP_ITEM, "装备物品")
    @require_whitelist
    async def handle_equip_item(self, event: AstrMessageEvent, item_name: str = ""):
        async for r in self.equipment_handler.handle_equip_item(event, item_name):
            yield r

    @filter.command(CMD_UNEQUIP_ITEM, "卸下装备")
    @require_whitelist
    async def handle_unequip_item(self, event: AstrMessageEvent, slot_or_name: str = ""):
        async for r in self.equipment_handler.handle_unequip_item(event, slot_or_name):
            yield r

    @filter.command(CMD_BREAKTHROUGH_INFO, "查看突破信息")
    @require_whitelist
    async def handle_breakthrough_info(self, event: AstrMessageEvent):
        async for r in self.breakthrough_handler.handle_breakthrough_info(event):
            yield r

    @filter.command(CMD_BREAKTHROUGH, "尝试突破境界")
    @require_whitelist
    async def handle_breakthrough(self, event: AstrMessageEvent, pill_name: str = ""):
        async for r in self.breakthrough_handler.handle_breakthrough(event, pill_name):
            yield r

    @filter.command(CMD_USE_PILL, "服用丹药 [数量]")
    @require_whitelist
    async def handle_use_pill(self, event: AstrMessageEvent, pill_name: str = "", quantity: int = 1):
        async for r in self.pill_handler.handle_use_pill(event, pill_name, quantity):
            yield r

    @filter.command(CMD_SHOW_PILLS, "查看丹药背包")
    @require_whitelist
    async def handle_show_pills(self, event: AstrMessageEvent):
        # 丹药背包已合并到储物戒，统一显示
        async for r in self.storage_ring_handler.handle_storage_ring(event):
            yield r

    @filter.command(CMD_PILL_INFO, "查看丹药信息")
    @require_whitelist
    async def handle_pill_info(self, event: AstrMessageEvent, pill_name: str = ""):
        async for r in self.pill_handler.handle_pill_info(event, pill_name):
            yield r

    @filter.command(CMD_PILL_PAVILION, "查看丹阁丹药")
    @require_whitelist
    async def handle_pill_pavilion(self, event: AstrMessageEvent):
        async for r in self.shop_handler.handle_pill_pavilion(event):
            yield r
        footer = get_related_commands_footer("丹阁")
        if footer:
            yield event.plain_result(footer)

    @filter.command(CMD_WEAPON_PAVILION, "查看器阁武器")
    @require_whitelist
    async def handle_weapon_pavilion(self, event: AstrMessageEvent):
        async for r in self.shop_handler.handle_weapon_pavilion(event):
            yield r

    @filter.command(CMD_TREASURE_PAVILION, "查看百宝阁物品")
    @require_whitelist
    async def handle_treasure_pavilion(self, event: AstrMessageEvent):
        async for r in self.shop_handler.handle_treasure_pavilion(event):
            yield r

    @filter.command(CMD_ITEM_INFO, "查看物品详细效果")
    @require_whitelist
    async def handle_item_info(self, event: AstrMessageEvent, item_name: str = ""):
        async for r in self.shop_handler.handle_item_info(event, item_name):
            yield r

    @filter.command(CMD_VIEW_ITEM, "查看物品详细信息")
    @require_whitelist
    async def handle_view_item(self, event: AstrMessageEvent, item_name: str = ""):
        async for r in self.shop_handler.handle_view_item(event, item_name):
            yield r

    @filter.command(CMD_BUY, "购买物品")
    @require_whitelist
    async def handle_buy(self, event: AstrMessageEvent, item_name: str = ""):
        async for r in self.shop_handler.handle_buy(event, item_name):
            yield r

    @filter.command(CMD_STORAGE_RING, "查看储物戒信息")
    @require_whitelist
    async def handle_storage_ring(self, event: AstrMessageEvent):
        async for r in self.storage_ring_handler.handle_storage_ring(event):
            yield r

    @filter.command(CMD_UPGRADE_RING, "升级储物戒")
    @require_whitelist
    async def handle_upgrade_ring(self, event: AstrMessageEvent, ring_name: str = ""):
        async for r in self.storage_ring_handler.handle_upgrade_ring(event, ring_name):
            yield r

    @filter.command(CMD_DISCARD_ITEM, "丢弃储物戒中的物品")
    @require_whitelist
    async def handle_discard_item(self, event: AstrMessageEvent, args: str = ""):
        async for r in self.storage_ring_handler.handle_discard_item(event, args):
            yield r

    @filter.command(CMD_GIFT_ITEM, "赠予物品给其他玩家")
    @require_whitelist
    async def handle_gift_item(self, event: AstrMessageEvent, args: str = ""):
        async for r in self.storage_ring_handler.handle_gift_item(event, args):
            yield r

    @filter.command(CMD_ACCEPT_GIFT, "接收赠予的物品")
    @require_whitelist
    async def handle_accept_gift(self, event: AstrMessageEvent):
        async for r in self.storage_ring_handler.handle_accept_gift(event):
            yield r

    @filter.command(CMD_REJECT_GIFT, "拒绝赠予的物品")
    @require_whitelist
    async def handle_reject_gift(self, event: AstrMessageEvent):
        async for r in self.storage_ring_handler.handle_reject_gift(event):
            yield r

    @filter.command(CMD_SEARCH_ITEM, "搜索储物戒物品")
    @require_whitelist
    async def handle_search_item(self, event: AstrMessageEvent, keyword: str = ""):
        async for r in self.storage_ring_handler.handle_search_item(event, keyword):
            yield r

    @filter.command("炼金", "将储物戒物品转化为灵石")
    @require_whitelist
    async def handle_alchemy_transmute(self, event: AstrMessageEvent, item_name: str = "", count: int = 1):
        async for r in self.storage_ring_handler.handle_alchemy_transmute(event, item_name, count):
            yield r

    # ===== 宗门系统指令 =====

    @filter.command(CMD_CREATE_SECT, "创建宗门")
    @require_whitelist
    async def handle_create_sect(self, event: AstrMessageEvent, name: str = ""):
        if not name:
            yield event.plain_result(f"请输入宗门名称，例如：/{CMD_CREATE_SECT} 逍遥门")
            return
        async for r in self.sect_handlers.handle_create_sect(event, name):
            yield r

    @filter.command(CMD_JOIN_SECT, "加入宗门")
    @require_whitelist
    async def handle_join_sect(self, event: AstrMessageEvent, name: str = ""):
        if not name:
            yield event.plain_result(f"请输入要加入的宗门名称，例如：/{CMD_JOIN_SECT} 逍遥门")
            return
        async for r in self.sect_handlers.handle_join_sect(event, name):
            yield r

    @filter.command(CMD_LEAVE_SECT, "退出当前宗门")
    @require_whitelist
    async def handle_leave_sect(self, event: AstrMessageEvent):
        async for r in self.sect_handlers.handle_leave_sect(event):
            yield r

    @filter.command(CMD_MY_SECT, "查看我的宗门信息")
    @require_whitelist
    async def handle_my_sect(self, event: AstrMessageEvent):
        async for r in self.sect_handlers.handle_my_sect(event):
            yield r

    @filter.command(CMD_SECT_TASK, "执行宗门任务")
    @require_whitelist
    async def handle_sect_task(self, event: AstrMessageEvent):
        async for r in self.sect_handlers.handle_sect_task(event):
            yield r

    @filter.command(CMD_SECT_LIST, "查看宗门列表")
    @require_whitelist
    async def handle_sect_list(self, event: AstrMessageEvent):
        async for r in self.sect_handlers.handle_sect_list(event):
            yield r

    @filter.command(CMD_SECT_DONATE, "宗门捐献")
    @require_whitelist
    async def handle_sect_donate(self, event: AstrMessageEvent, amount: int = 0):
        if amount <= 0:
             yield event.plain_result(f"请输入捐献数量，例如：/{CMD_SECT_DONATE} 1000")
             return
        async for r in self.sect_handlers.handle_donate(event, amount):
            yield r

    @filter.command(CMD_SECT_KICK, "踢出宗门成员")
    @require_whitelist
    async def handle_sect_kick(self, event: AstrMessageEvent, target: str = ""):
        async for r in self.sect_handlers.handle_kick_member(event, target):
            yield r

    @filter.command(CMD_SECT_TRANSFER, "宗主传位")
    @require_whitelist
    async def handle_sect_transfer(self, event: AstrMessageEvent, target: str = ""):
        async for r in self.sect_handlers.handle_transfer(event, target):
            yield r

    @filter.command(CMD_SECT_POSITION, "变更成员职位")
    @require_whitelist
    async def handle_sect_position(self, event: AstrMessageEvent, args: str = ""):
        """职位变更 @某人 <职位ID(0-4)> 或 职位变更 <QQ号> <职位ID>"""
        import re as _re
        # ---- 提取目标用户ID ----
        target_id = None
        # 尝试从消息链 At 组件提取
        if hasattr(event, "message_obj") and event.message_obj:
            for comp in getattr(event.message_obj, "message", []) or []:
                if isinstance(comp, At):
                    for attr in ("qq", "target", "uin", "user_id"):
                        val = getattr(comp, attr, None)
                        if val:
                            target_id = str(val).lstrip("@")
                            break
                    if target_id:
                        break
        # 从原始消息文本提取（主路径：支持 @QQ号 / 纯QQ号 / CQ码）
        if not target_id:
            raw = (event.get_message_str() if hasattr(event, "get_message_str") else "") or ""
            # 剥离命令前缀（/职位变更 或 职位变更）
            text = raw.lstrip("/").strip()
            if text.startswith(CMD_SECT_POSITION):
                text = text[len(CMD_SECT_POSITION):].strip()
            # CQ码格式 [CQ:at,qq=12345]
            m = _re.search(r'\[CQ:at,qq=(\d+)\]', text)
            if m:
                target_id = m.group(1)
            else:
                # @数字 或 纯数字（5位以上）
                m = _re.search(r'@?(\d{5,12})', text)
                if m:
                    target_id = m.group(1)
        # ---- 提取职位ID ----
        position = -1
        raw = (event.get_message_str() if hasattr(event, "get_message_str") else "") or args
        text = raw.lstrip("/").strip()
        if text.startswith(CMD_SECT_POSITION):
            text = text[len(CMD_SECT_POSITION):].strip()
        m = _re.search(r'(?<!\d)([0-4])(?!\d)', text)
        if m:
            position = int(m.group(1))
        # ---- 校验 ----
        if not target_id or position < 0:
            yield event.plain_result(
                f"用法：/{CMD_SECT_POSITION} @某人 <职位ID>\n"
                f"　　：/{CMD_SECT_POSITION} <QQ号> <职位ID>\n"
                f"职位ID：0宗主 1副宗主 2长老 3内门弟子 4外门弟子"
            )
            return
        async for r in self.sect_handlers.handle_position_change(event, target_id, position):
            yield r

    @filter.command(CMD_UPGRADE_PRACTICE, "升级攻击修炼等级")
    @require_whitelist
    async def handle_upgrade_practice(self, event: AstrMessageEvent, count: int = 1):
        async for r in self.sect_handlers.handle_upgrade_practice(event, count):
            yield r

    @filter.command(CMD_PRACTICE_INFO, "查看攻击修炼信息")
    @require_whitelist
    async def handle_practice_info(self, event: AstrMessageEvent):
        async for r in self.sect_handlers.handle_practice_info(event):
            yield r

    @filter.command(CMD_SECT_ELIXIR_ROOM, "建设/升级宗门丹房")
    @require_whitelist
    async def handle_sect_elixir_room(self, event: AstrMessageEvent):
        async for r in self.sect_handlers.handle_upgrade_elixir_room(event):
            yield r

    @filter.command(CMD_SECT_ELIXIR_GET, "领取宗门丹药")
    @require_whitelist
    async def handle_sect_elixir_get(self, event: AstrMessageEvent):
        async for r in self.sect_handlers.handle_claim_sect_pill(event):
            yield r

    @filter.command(CMD_SECT_RENAME, "修改宗门名称")
    @require_whitelist
    async def handle_sect_rename(self, event: AstrMessageEvent, new_name: str = ""):
        if not new_name:
            yield event.plain_result(f"请输入新名称，例如：/{CMD_SECT_RENAME} 逍遥门")
            return
        async for r in self.sect_handlers.handle_rename_sect(event, new_name):
            yield r

    # ===== Boss系统指令 =====

    @filter.command(CMD_BOSS_INFO, "查看世界Boss状态")
    @require_whitelist
    async def handle_boss_info(self, event: AstrMessageEvent):
        if not self.boss_enabled:
            yield event.plain_result("❌ Boss系统已禁用。")
            return
        async for r in self.boss_handlers.handle_boss_info(event):
            yield r
        footer = get_related_commands_footer("世界Boss")
        if footer:
            yield event.plain_result(footer)

    @filter.command(CMD_BOSS_FIGHT, "挑战世界Boss")
    @require_whitelist
    async def handle_boss_fight(self, event: AstrMessageEvent):
        if not self.boss_enabled:
            yield event.plain_result("❌ Boss系统已禁用。")
            return
        user_id = event.get_sender_id()
        success, msg, battle_result = await self.boss_handlers.handle_boss_fight(user_id)
        yield event.plain_result(msg)
        
        if success and battle_result and battle_result.get("winner") == user_id:
            player = await self.db.get_player_by_id(user_id)
            player_name = player.user_name if player and player.user_name else f"道友{str(user_id)[:6]}"
            await self._broadcast_boss_defeat(player_name, battle_result)

    @filter.command(CMD_SPAWN_BOSS, "生成世界Boss(管理员)")
    @require_whitelist
    async def handle_spawn_boss(self, event: AstrMessageEvent):
        if not self.boss_enabled:
            yield event.plain_result("❌ Boss系统已禁用。")
            return
        if not self._check_boss_admin(event):
            yield event.plain_result("❌ 你没有权限生成Boss！此指令仅限管理员使用。")
            return
        
        success, msg, boss = await self.boss_handlers.handle_spawn_boss()
        yield event.plain_result(msg)
        
        if success and boss:
            await self._broadcast_boss_spawn(boss)

    # ===== 排行榜指令 =====

    @filter.command(CMD_RANK_LEVEL, "查看境界排行榜")
    @require_whitelist
    async def handle_rank_level(self, event: AstrMessageEvent):
        async for r in self.ranking_handlers.handle_rank_level(event):
            yield r
        footer = get_related_commands_footer("境界排行")
        if footer:
            yield event.plain_result(footer)

    @filter.command(CMD_RANK_POWER, "查看战力排行榜")
    @require_whitelist
    async def handle_rank_power(self, event: AstrMessageEvent):
        async for r in self.ranking_handlers.handle_rank_power(event):
            yield r

    @filter.command(CMD_RANK_WEALTH, "查看财富排行榜")
    @require_whitelist
    async def handle_rank_wealth(self, event: AstrMessageEvent):
        async for r in self.ranking_handlers.handle_rank_wealth(event):
            yield r

    @filter.command(CMD_RANK_SECT, "查看宗门排行榜")
    @require_whitelist
    async def handle_rank_sect(self, event: AstrMessageEvent):
        async for r in self.ranking_handlers.handle_rank_sect(event):
            yield r

    @filter.command(CMD_RANK_DEPOSIT, "查看存款排行榜")
    @require_whitelist
    async def handle_rank_deposit(self, event: AstrMessageEvent):
        async for r in self.ranking_handlers.handle_rank_deposit(event):
            yield r

    @filter.command(CMD_RANK_CONTRIBUTION, "查看宗门贡献排行榜")
    @require_whitelist
    async def handle_rank_contribution(self, event: AstrMessageEvent):
        async for r in self.ranking_handlers.handle_rank_sect_contribution(event):
            yield r

    # ===== 战斗指令 =====

    @filter.command(CMD_DUEL, "与其他玩家决斗(消耗气血)")
    @require_whitelist
    async def handle_duel(self, event: AstrMessageEvent, target: str = ""):
        async for r in self.combat_handlers.handle_duel(event, target):
            yield r
        footer = get_related_commands_footer("决斗")
        if footer:
            yield event.plain_result(footer)
            
    @filter.command(CMD_SPAR, "与其他玩家切磋(无消耗)")
    @require_whitelist
    async def handle_spar(self, event: AstrMessageEvent, target: str = ""):
        async for r in self.combat_handlers.handle_spar(event, target):
            yield r

    @filter.command(CMD_SCARECROW, "稻草人练习(固定1伤害/次)")
    @require_whitelist
    async def handle_scarecrow(self, event: AstrMessageEvent):
        async for r in self.combat_handlers.handle_scarecrow(event):
            yield r

    # ===== 神通指令 =====

    @filter.command("神通列表", "查看所有神通")
    @require_whitelist
    async def handle_skill_list(self, event: AstrMessageEvent):
        async for r in self.skill_handler.handle_skill_list(event):
            yield r
        footer = get_related_commands_footer("神通列表")
        if footer:
            yield event.plain_result(footer)

    @filter.command("我的神通", "查看已装备神通")
    @require_whitelist
    async def handle_my_skill(self, event: AstrMessageEvent):
        async for r in self.skill_handler.handle_my_skill(event):
            yield r

    @filter.command("装备神通", "装备神通 [名称]")
    @require_whitelist
    async def handle_equip_skill(self, event: AstrMessageEvent, skill_name: str = ""):
        async for r in self.skill_handler.handle_equip_skill(event, skill_name):
            yield r

    @filter.command("卸下神通", "卸下当前神通")
    @require_whitelist
    async def handle_unequip_skill(self, event: AstrMessageEvent):
        async for r in self.skill_handler.handle_unequip_skill(event):
            yield r

    @filter.command("神通信息", "查看神通详情 [名称]")
    @require_whitelist
    async def handle_skill_info(self, event: AstrMessageEvent, skill_name: str = ""):
        async for r in self.skill_handler.handle_skill_info(event, skill_name):
            yield r

    # ===== 秘境指令 =====
    @filter.command(CMD_RIFT_EXPLORE, "探索秘境")
    @require_whitelist
    async def handle_rift_explore(self, event: AstrMessageEvent):
        async for r in self.rift_handlers.handle_rift_explore(event):
            yield r
        footer = get_related_commands_footer("探索秘境")
        if footer:
            yield event.plain_result(footer)

    @filter.command(CMD_RIFT_COMPLETE, "完成秘境探索")
    @require_whitelist
    async def handle_rift_complete(self, event: AstrMessageEvent):
        user_id = event.get_sender_id()
        success, msg, reward_data = await self.rift_mgr.finish_exploration(user_id)

        if success:
            player = await self.db.get_player_by_id(user_id)
            if player:
                await self.activity_tracker.track_rift(player)

        yield event.plain_result(msg)

    @filter.command(CMD_RIFT_EXIT, "退出秘境")
    @require_whitelist
    async def handle_rift_exit(self, event: AstrMessageEvent):
        async for r in self.rift_handlers.handle_rift_exit(event):
            yield r

    # ===== 历练指令 =====
    @filter.command(CMD_ADVENTURE_START, "开始历练")
    @require_whitelist
    async def handle_adventure_start(self, event: AstrMessageEvent, route: str = ""):
        async for r in self.adventure_handlers.handle_start_adventure(event, route):
            yield r

    @filter.command(CMD_ADVENTURE_COMPLETE, "完成历练")
    @require_whitelist
    async def handle_adventure_complete(self, event: AstrMessageEvent):
        user_id = event.get_sender_id()
        success, msg, reward_data = await self.adventure_mgr.finish_adventure(user_id)

        if success:
            player = await self.db.get_player_by_id(user_id)
            if player:
                await self.activity_tracker.track_adventure(player)

        yield event.plain_result(msg)

    @filter.command(CMD_ADVENTURE_ABORT, "中断历练（中途退出，无奖励）")
    @require_whitelist
    async def handle_adventure_abort(self, event: AstrMessageEvent):
        user_id = event.get_sender_id()
        success, msg = await self.adventure_mgr.abort_adventure(user_id)

        if success:
            player = await self.db.get_player_by_id(user_id)
            if player:
                await self.activity_tracker.track_adventure(player)

        yield event.plain_result(msg)

    @filter.command(CMD_ADVENTURE_STATUS, "查看历练状态")
    @require_whitelist
    async def handle_adventure_status(self, event: AstrMessageEvent):
        async for r in self.adventure_handlers.handle_adventure_status(event):
            yield r

    @filter.command(CMD_ADVENTURE_INFO, "查看历练系统说明")
    @require_whitelist
    async def handle_adventure_info(self, event: AstrMessageEvent):
        async for r in self.adventure_handlers.handle_adventure_info(event):
            yield r
        footer = get_related_commands_footer("历练信息")
        if footer:
            yield event.plain_result(footer)

    # ===== 炼丹指令 =====
    @filter.command(CMD_ALCHEMY_RECIPES, "查看丹药配方")
    @require_whitelist
    async def handle_alchemy_recipes(self, event: AstrMessageEvent):
        async for r in self.alchemy_handlers.handle_recipes(event):
            yield r
        footer = get_related_commands_footer("丹药配方")
        if footer:
            yield event.plain_result(footer)

    @filter.command(CMD_ALCHEMY_CRAFT, "炼制丹药")
    @require_whitelist
    async def handle_alchemy_craft(self, event: AstrMessageEvent, pill_id: int = 0):
        async for r in self.alchemy_handlers.handle_craft(event, pill_id):
            yield r

    # ===== 传承指令 =====
    @filter.command(CMD_IMPART_INFO, "查看传承信息")
    @require_whitelist
    async def handle_impart_info(self, event: AstrMessageEvent):
        async for r in self.impart_handlers.handle_impart_info(event):
            yield r

    # ===== Phase 1: 道号系统 =====
    @filter.command(CMD_CHANGE_NICKNAME, "修改道号")
    @require_whitelist
    async def handle_change_nickname(self, event: AstrMessageEvent, new_name: str = ""):
        async for r in self.nickname_handler.handle_change_nickname(event, new_name):
            yield r

    # ===== Phase 2: 灵石银行 =====
    @filter.command(CMD_BANK_INFO, "查看银行信息")
    @require_whitelist
    async def handle_bank_info(self, event: AstrMessageEvent):
        async for r in self.bank_handlers.handle_bank_info(event):
            yield r

    @filter.command(CMD_BANK_DEPOSIT, "存入灵石")
    @require_whitelist
    async def handle_bank_deposit(self, event: AstrMessageEvent, amount: int = 0):
        async for r in self.bank_handlers.handle_deposit(event, amount):
            yield r

    @filter.command(CMD_BANK_WITHDRAW, "取出灵石")
    @require_whitelist
    async def handle_bank_withdraw(self, event: AstrMessageEvent, amount: int = 0):
        async for r in self.bank_handlers.handle_withdraw(event, amount):
            yield r

    @filter.command(CMD_BANK_INTEREST, "领取利息")
    @require_whitelist
    async def handle_bank_interest(self, event: AstrMessageEvent):
        async for r in self.bank_handlers.handle_claim_interest(event):
            yield r

    @filter.command(CMD_BANK_LOAN, "申请贷款")
    @require_whitelist
    async def handle_bank_loan(self, event: AstrMessageEvent, amount: int = 0):
        async for r in self.bank_handlers.handle_loan(event, amount):
            yield r

    @filter.command(CMD_BANK_REPAY, "偿还贷款")
    @require_whitelist
    async def handle_bank_repay(self, event: AstrMessageEvent):
        async for r in self.bank_handlers.handle_repay(event):
            yield r

    @filter.command(CMD_BANK_TRANSACTIONS, "查看银行流水")
    @require_whitelist
    async def handle_bank_transactions(self, event: AstrMessageEvent):
        async for r in self.bank_handlers.handle_transactions(event):
            yield r

    @filter.command(CMD_BANK_BREAKTHROUGH_LOAN, "申请突破贷款")
    @require_whitelist
    async def handle_bank_breakthrough_loan(self, event: AstrMessageEvent, amount: int = 0):
        async for r in self.bank_handlers.handle_breakthrough_loan(event, amount):
            yield r

    @filter.command(CMD_UPGRADE_VIP, "升级银行会员等级")
    @require_whitelist
    async def handle_upgrade_vip(self, event: AstrMessageEvent):
        async for r in self.bank_handlers.handle_upgrade_vip(event):
            yield r

    # ===== 金银阁赌坊 =====
    @filter.command(CMD_GAMBLING, "金银阁赌坊")
    @require_whitelist
    async def handle_gambling(self, event: AstrMessageEvent):
        async for r in self.gambling_handler.handle_gambling(event):
            yield r

    # ===== Phase 2: 悬赏令 =====
    @filter.command(CMD_BOUNTY_LIST, "查看悬赏任务")
    @require_whitelist
    async def handle_bounty_list(self, event: AstrMessageEvent):
        async for r in self.bounty_handlers.handle_bounty_list(event):
            yield r

    @filter.command(CMD_BOUNTY_ACCEPT, "接取悬赏任务")
    @require_whitelist
    async def handle_bounty_accept(self, event: AstrMessageEvent, bounty_id: int = 0):
        async for r in self.bounty_handlers.handle_accept_bounty(event, bounty_id):
            yield r

    @filter.command(CMD_BOUNTY_STATUS, "查看悬赏状态")
    @require_whitelist
    async def handle_bounty_status(self, event: AstrMessageEvent):
        async for r in self.bounty_handlers.handle_bounty_status(event):
            yield r

    @filter.command(CMD_BOUNTY_COMPLETE, "完成悬赏任务")
    @require_whitelist
    async def handle_bounty_complete(self, event: AstrMessageEvent):
        async for r in self.bounty_handlers.handle_complete_bounty(event):
            yield r

    @filter.command(CMD_BOUNTY_ABANDON, "放弃悬赏任务")
    @require_whitelist
    async def handle_bounty_abandon(self, event: AstrMessageEvent):
        async for r in self.bounty_handlers.handle_abandon_bounty(event):
            yield r

    # ===== Phase 3: 传承PK =====
    @filter.command(CMD_IMPART_CHALLENGE, "发起传承挑战")
    @require_whitelist
    async def handle_impart_challenge(self, event: AstrMessageEvent, target: str = ""):
        async for r in self.impart_pk_handlers.handle_impart_challenge(event, target):
            yield r
        footer = get_related_commands_footer("传承挑战")
        if footer:
            yield event.plain_result(footer)

    @filter.command(CMD_IMPART_RANKING, "查看传承排行")
    @require_whitelist
    async def handle_impart_ranking(self, event: AstrMessageEvent):
        async for r in self.impart_pk_handlers.handle_impart_ranking(event):
            yield r

    # ===== Phase 4: 洞天福地 =====
    @filter.command(CMD_BLESSED_LAND_INFO, "查看洞天信息")
    @require_whitelist
    async def handle_blessed_land_info(self, event: AstrMessageEvent):
        async for r in self.blessed_land_handlers.handle_blessed_land_info(event):
            yield r

    @filter.command(CMD_BLESSED_LAND_BUY, "购买洞天")
    @require_whitelist
    async def handle_blessed_land_buy(self, event: AstrMessageEvent, land_type: int = 0):
        async for r in self.blessed_land_handlers.handle_purchase(event, land_type):
            yield r

    @filter.command(CMD_BLESSED_LAND_UPGRADE, "升级洞天")
    @require_whitelist
    async def handle_blessed_land_upgrade(self, event: AstrMessageEvent, land_type: int = 0):
        async for r in self.blessed_land_handlers.handle_upgrade(event, land_type):
            yield r

    # ===== Phase 4: 灵田 =====
    @filter.command(CMD_SPIRIT_FARM_INFO, "查看灵田")
    @require_whitelist
    async def handle_spirit_farm_info(self, event: AstrMessageEvent):
        async for r in self.spirit_farm_handlers.handle_farm_info(event):
            yield r

    @filter.command(CMD_SPIRIT_FARM_CREATE, "开垦灵田")
    @require_whitelist
    async def handle_spirit_farm_create(self, event: AstrMessageEvent):
        async for r in self.spirit_farm_handlers.handle_create_farm(event):
            yield r

    @filter.command(CMD_SPIRIT_FARM_PLANT, "种植灵草 [数量]")
    @require_whitelist
    async def handle_spirit_farm_plant(self, event: AstrMessageEvent, herb_name: str = "", quantity: int = 1):
        async for r in self.spirit_farm_handlers.handle_plant(event, herb_name, quantity):
            yield r

    @filter.command(CMD_SPIRIT_FARM_HARVEST, "收获灵草")
    @require_whitelist
    async def handle_spirit_farm_harvest(self, event: AstrMessageEvent):
        async for r in self.spirit_farm_handlers.handle_harvest(event):
            yield r

    @filter.command(CMD_SPIRIT_FARM_UPGRADE, "升级灵田")
    @require_whitelist
    async def handle_spirit_farm_upgrade(self, event: AstrMessageEvent):
        async for r in self.spirit_farm_handlers.handle_upgrade_farm(event):
            yield r

    # ===== Phase 4: 双修 =====
    @filter.command(CMD_DUAL_CULT_REQUEST, "发起双修")
    @require_whitelist
    async def handle_dual_cult_request(self, event: AstrMessageEvent, target: str = ""):
        async for r in self.dual_cult_handlers.handle_dual_request(event, target):
            yield r

    @filter.command(CMD_DUAL_CULT_ACCEPT, "接受双修")
    @require_whitelist
    async def handle_dual_cult_accept(self, event: AstrMessageEvent):
        async for r in self.dual_cult_handlers.handle_accept(event):
            yield r

    @filter.command(CMD_DUAL_CULT_REJECT, "拒绝双修")
    @require_whitelist
    async def handle_dual_cult_reject(self, event: AstrMessageEvent):
        async for r in self.dual_cult_handlers.handle_reject(event):
            yield r

    # ===== Phase 4: 天地灵眼 =====
    @filter.command(CMD_SPIRIT_EYE_INFO, "查看灵眼")
    @require_whitelist
    async def handle_spirit_eye_info(self, event: AstrMessageEvent):
        async for r in self.spirit_eye_handlers.handle_spirit_eye_info(event):
            yield r

    @filter.command(CMD_SPIRIT_EYE_CLAIM, "抢占灵眼")
    @require_whitelist
    async def handle_spirit_eye_claim(self, event: AstrMessageEvent, eye_id: int = 0):
        async for r in self.spirit_eye_handlers.handle_claim(event, eye_id):
            yield r

    @filter.command(CMD_SPIRIT_EYE_RELEASE, "释放灵眼")
    @require_whitelist
    async def handle_spirit_eye_release(self, event: AstrMessageEvent):
        async for r in self.spirit_eye_handlers.handle_release(event):
            yield r

    @filter.command(CMD_TRADE_START, "发起即时交易")
    @require_whitelist
    async def handle_trade_start(self, event: AstrMessageEvent, args: str = ""):
        async for r in self.trade_handler.handle_start_trade(event, args):
            yield r

    @filter.command(CMD_TRADE_ACCEPT, "接受交易请求")
    @require_whitelist
    async def handle_trade_accept(self, event: AstrMessageEvent):
        async for r in self.trade_handler.handle_accept(event):
            yield r

    @filter.command(CMD_TRADE_REJECT, "拒绝交易请求")
    @require_whitelist
    async def handle_trade_reject(self, event: AstrMessageEvent):
        async for r in self.trade_handler.handle_reject(event):
            yield r

    @filter.command(CMD_TRADE_ADD_ITEM, "向交易放入物品")
    @require_whitelist
    async def handle_trade_add_item(self, event: AstrMessageEvent, args: str = ""):
        async for r in self.trade_handler.handle_add_item(event, args):
            yield r

    @filter.command(CMD_TRADE_ADD_STONES, "向交易放入灵石")
    @require_whitelist
    async def handle_trade_add_stones(self, event: AstrMessageEvent, args: str = ""):
        async for r in self.trade_handler.handle_add_stones(event, args):
            yield r

    @filter.command(CMD_TRADE_REMOVE_ITEM, "从交易移除物品")
    @require_whitelist
    async def handle_trade_remove_item(self, event: AstrMessageEvent, args: str = ""):
        async for r in self.trade_handler.handle_remove_item(event, args):
            yield r

    @filter.command(CMD_TRADE_REMOVE_STONES, "从交易移除灵石")
    @require_whitelist
    async def handle_trade_remove_stones(self, event: AstrMessageEvent, args: str = ""):
        async for r in self.trade_handler.handle_remove_stones(event, args):
            yield r

    @filter.command(CMD_TRADE_VIEW, "查看当前交易内容")
    @require_whitelist
    async def handle_trade_view(self, event: AstrMessageEvent):
        async for r in self.trade_handler.handle_view_trade(event):
            yield r

    @filter.command(CMD_TRADE_CONFIRM, "确认交易")
    @require_whitelist
    async def handle_trade_confirm(self, event: AstrMessageEvent):
        async for r in self.trade_handler.handle_confirm(event):
            yield r

    @filter.command(CMD_TRADE_CANCEL, "取消交易")
    @require_whitelist
    async def handle_trade_cancel(self, event: AstrMessageEvent):
        async for r in self.trade_handler.handle_cancel(event):
            yield r

    @filter.command(CMD_CONSIGN_LIST, "寄售物品")
    @require_whitelist
    async def handle_consignment_list_item(self, event: AstrMessageEvent, args: str = ""):
        async for r in self.consignment_handler.handle_list_item(event, args):
            yield r

    @filter.command(CMD_CONSIGN_BROWSE, "浏览寄售行")
    @require_whitelist
    async def handle_consignment_browse(self, event: AstrMessageEvent, args: str = ""):
        async for r in self.consignment_handler.handle_browse(event, args):
            yield r

    @filter.command(CMD_CONSIGN_BUY, "购买寄售物品")
    @require_whitelist
    async def handle_consignment_buy(self, event: AstrMessageEvent, args: str = ""):
        async for r in self.consignment_handler.handle_buy(event, args):
            yield r

    @filter.command(CMD_CONSIGN_MY, "查看自己的寄售")
    @require_whitelist
    async def handle_consignment_my(self, event: AstrMessageEvent):
        async for r in self.consignment_handler.handle_my(event):
            yield r

    @filter.command(CMD_CONSIGN_CANCEL, "下架寄售物品")
    @require_whitelist
    async def handle_consignment_cancel(self, event: AstrMessageEvent, args: str = ""):
        async for r in self.consignment_handler.handle_cancel(event, args):
            yield r

    # ===== 物品禁用管理指令（管理员） =====

    @filter.command(CMD_DISABLE_ITEM, "禁用物品（管理员）")
    @require_whitelist
    async def handle_disable_item(self, event: AstrMessageEvent, item_name: str = ""):
        if not self._check_boss_admin(event):
            yield event.plain_result("❌ 你没有权限！此指令仅限管理员使用。")
            return
        if not item_name:
            yield event.plain_result("用法：禁用物品 <物品名称>")
            return

        disabled = self.config_manager.game_config.get('disabled_items', [])
        if item_name in disabled:
            yield event.plain_result(f"⚠️ 「{item_name}」已在禁用列表中。")
            return

        disabled.append(item_name)
        self.config_manager.game_config['disabled_items'] = disabled
        self.config_manager.save_game_config()
        yield event.plain_result(f"✅ 已禁用「{item_name}」，商店将不再刷新该物品。")

    @filter.command(CMD_ENABLE_ITEM, "启用物品（管理员）")
    @require_whitelist
    async def handle_enable_item(self, event: AstrMessageEvent, item_name: str = ""):
        if not self._check_boss_admin(event):
            yield event.plain_result("❌ 你没有权限！此指令仅限管理员使用。")
            return
        if not item_name:
            yield event.plain_result("用法：启用物品 <物品名称>")
            return

        disabled = self.config_manager.game_config.get('disabled_items', [])
        if item_name not in disabled:
            yield event.plain_result(f"⚠️ 「{item_name}」不在禁用列表中。")
            return

        disabled.remove(item_name)
        self.config_manager.game_config['disabled_items'] = disabled
        self.config_manager.save_game_config()
        yield event.plain_result(f"✅ 已启用「{item_name}」，下次商店刷新时会出现。")

    @filter.command(CMD_LIST_DISABLED, "查看禁用物品列表")
    @require_whitelist
    async def handle_list_disabled(self, event: AstrMessageEvent):
        disabled = self.config_manager.game_config.get('disabled_items', [])
        if not disabled:
            yield event.plain_result("📋 禁用列表为空，所有物品均可正常刷新。")
            return
        lines = [f"📋 禁用物品列表（共 {len(disabled)} 项）："]
        for i, name in enumerate(disabled, 1):
            lines.append(f"  {i}. {name}")
        yield event.plain_result("\n".join(lines))

    # ===== GM管理员指令 =====

    @filter.command(CMD_GM_HELP, "GM指令帮助")
    async def handle_gm_help(self, event: AstrMessageEvent):
        if not self._check_boss_admin(event):
            yield event.plain_result("❌ 你没有权限！此指令仅限管理员使用。")
            return
        msg = await self.gm_handlers.handle_help()
        yield event.plain_result(msg)

    @filter.command(CMD_GM_ADD_GOLD, "GM增加灵石")
    async def handle_gm_add_gold(self, event: AstrMessageEvent, args: str = ""):
        if not self._check_boss_admin(event):
            yield event.plain_result("❌ 你没有权限！此指令仅限管理员使用。")
            return
        target_id, extra = self._gm_parse_target(args, event)
        msg = await self.gm_handlers.handle_add_gold(target_id, extra)
        yield event.plain_result(msg)

    @filter.command(CMD_GM_SUB_GOLD, "GM扣除灵石")
    async def handle_gm_sub_gold(self, event: AstrMessageEvent, args: str = ""):
        if not self._check_boss_admin(event):
            yield event.plain_result("❌ 你没有权限！此指令仅限管理员使用。")
            return
        target_id, extra = self._gm_parse_target(args, event)
        msg = await self.gm_handlers.handle_sub_gold(target_id, extra)
        yield event.plain_result(msg)

    @filter.command(CMD_GM_ADD_EXP, "GM增加修为")
    async def handle_gm_add_exp(self, event: AstrMessageEvent, args: str = ""):
        if not self._check_boss_admin(event):
            yield event.plain_result("❌ 你没有权限！此指令仅限管理员使用。")
            return
        target_id, extra = self._gm_parse_target(args, event)
        msg = await self.gm_handlers.handle_add_exp(target_id, extra)
        yield event.plain_result(msg)

    @filter.command(CMD_GM_SET_LEVEL, "GM设置境界")
    async def handle_gm_set_level(self, event: AstrMessageEvent, args: str = ""):
        if not self._check_boss_admin(event):
            yield event.plain_result("❌ 你没有权限！此指令仅限管理员使用。")
            return
        target_id, extra = self._gm_parse_target(args, event)
        msg = await self.gm_handlers.handle_set_level(target_id, extra)
        yield event.plain_result(msg)

    @filter.command(CMD_GM_ADD_ITEM, "GM添加物品")
    async def handle_gm_add_item(self, event: AstrMessageEvent, args: str = ""):
        if not self._check_boss_admin(event):
            yield event.plain_result("❌ 你没有权限！此指令仅限管理员使用。")
            return
        target_id, extra = self._gm_parse_target(args, event)
        msg = await self.gm_handlers.handle_add_item(target_id, extra)
        yield event.plain_result(msg)

    @filter.command(CMD_GM_SUB_ITEM, "GM扣除物品")
    async def handle_gm_sub_item(self, event: AstrMessageEvent, args: str = ""):
        if not self._check_boss_admin(event):
            yield event.plain_result("❌ 你没有权限！此指令仅限管理员使用。")
            return
        target_id, extra = self._gm_parse_target(args, event)
        msg = await self.gm_handlers.handle_sub_item(target_id, extra)
        yield event.plain_result(msg)

    @filter.command(CMD_GM_ADD_PILL, "GM添加丹药")
    async def handle_gm_add_pill(self, event: AstrMessageEvent, args: str = ""):
        if not self._check_boss_admin(event):
            yield event.plain_result("❌ 你没有权限！此指令仅限管理员使用。")
            return
        target_id, extra = self._gm_parse_target(args, event)
        msg = await self.gm_handlers.handle_add_pill(target_id, extra)
        yield event.plain_result(msg)

    @filter.command(CMD_GM_SUB_PILL, "GM扣除丹药")
    async def handle_gm_sub_pill(self, event: AstrMessageEvent, args: str = ""):
        if not self._check_boss_admin(event):
            yield event.plain_result("❌ 你没有权限！此指令仅限管理员使用。")
            return
        target_id, extra = self._gm_parse_target(args, event)
        msg = await self.gm_handlers.handle_sub_pill(target_id, extra)
        yield event.plain_result(msg)

    @filter.command(CMD_GM_VIEW_PLAYER, "GM查看玩家")
    async def handle_gm_view_player(self, event: AstrMessageEvent, args: str = ""):
        if not self._check_boss_admin(event):
            yield event.plain_result("❌ 你没有权限！此指令仅限管理员使用。")
            return
        target_id, extra = self._gm_parse_target(args, event)
        msg = await self.gm_handlers.handle_view_player(target_id)
        yield event.plain_result(msg)

    @filter.command(CMD_GM_REFRESH_RIFT, "GM强制刷新秘境")
    async def handle_gm_refresh_rift(self, event: AstrMessageEvent):
        if not self._check_boss_admin(event):
            yield event.plain_result("❌ 你没有权限！此指令仅限管理员使用。")
            return
        success, msg, rift_def = await self.rift_mgr.force_refresh_rift()
        yield event.plain_result(msg)
        if success and rift_def:
            await self._broadcast_rift_open(rift_def)

    @filter.command(CMD_GM_COMPENSATION, "GM创建全服补偿包")
    async def handle_gm_compensation(self, event: AstrMessageEvent, args: str = ""):
        if not self._check_boss_admin(event):
            yield event.plain_result("❌ 你没有权限！此指令仅限管理员使用。")
            return
        # 从完整消息提取参数，避免args只含第一个词的问题
        import re
        full_msg = args
        if event and hasattr(event, "get_message_str"):
            raw = event.get_message_str() or ""
            m = re.match(r'\S+\s+(.*)', raw, re.DOTALL)
            if m:
                full_msg = m.group(1).strip()
            elif raw:
                # 正则未匹配（可能框架已去掉指令前缀），直接用原始消息
                full_msg = raw.strip()
        msg = await self.gm_handlers.handle_create_compensation(full_msg)
        yield event.plain_result(msg)

    def _gm_parse_target(self, args: str, event: AstrMessageEvent = None) -> tuple:
        """从GM指令参数中解析目标QQ号和剩余参数。
        与 handle_sect_position 完全相同的解析逻辑：
        1. 消息链 At 组件（增强）
        2. get_message_str() 原始文本 → 剥离命令前缀 → CQ码/@数字/纯数字
        """
        import re
        raw = ""
        if event:
            if hasattr(event, "get_message_str"):
                raw = (event.get_message_str() or "").strip()
            if not raw:
                raw = args or ""
        else:
            raw = args or ""
        # 剥离命令前缀（第一个词：如 GM加灵石）
        m_prefix = re.match(r'\S+\s+(.*)', raw, re.DOTALL)
        text = m_prefix.group(1).strip() if m_prefix else raw.strip()
        # ---- 尝试从消息链 At 组件提取（增强路径） ----
        target_id = None
        if event and hasattr(event, "message_obj") and event.message_obj:
            message_chain = getattr(event.message_obj, "message", []) or []
            for component in message_chain:
                if isinstance(component, At):
                    for attr in ("qq", "target", "uin", "user_id"):
                        val = getattr(component, attr, None)
                        if val:
                            target_id = str(val).lstrip("@")
                            break
                    if target_id:
                        break
        # ---- 主路径：从剥离前缀后的文本提取 ----
        if not target_id:
            # CQ码格式 [CQ:at,qq=12345]
            at_match = re.search(r'\[CQ:at,qq=(\d+)\]', text)
            if at_match:
                target_id = at_match.group(1)
                extra = re.sub(r'\[CQ:at,qq=\d+\]', '', text).strip()
                return target_id, extra
            # @数字 或 纯数字QQ号（5位以上）
            num_match = re.search(r'@?(\d{5,12})', text)
            if num_match:
                target_id = num_match.group(1)
                extra = text[num_match.end():].strip()
                return target_id, extra
            return "", text.strip()
        # At 组件命中时，extra 从剥离前缀后的文本中移除目标ID得到
        extra = text.replace(target_id, "", 1).lstrip().strip()
        return target_id, extra
