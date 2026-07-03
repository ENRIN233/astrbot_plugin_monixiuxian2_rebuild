# handlers/spirit_farm_handlers.py
"""灵田处理器 — nonebot 迁移版"""
from astrbot.api.event import AstrMessageEvent
from ..data import DataBase
from ..managers.spirit_farm_manager import SpiritFarmManager
from ..models import Player
from .utils import player_required

__all__ = ["SpiritFarmHandlers"]


class SpiritFarmHandlers:
    """灵田处理器"""

    def __init__(self, db: DataBase, farm_mgr: SpiritFarmManager, config_manager=None):
        self.db = db
        self.mgr = farm_mgr
        self.config_manager = config_manager

    @player_required
    async def handle_farm_info(self, player: Player, event: AstrMessageEvent):
        """查看灵田信息"""
        info = await self.mgr.get_farm_info(player.user_id, self.config_manager)
        yield event.plain_result(info)

    @player_required
    async def handle_create_farm(self, player: Player, event: AstrMessageEvent):
        """开垦灵田"""
        success, msg = await self.mgr.create_farm(player)
        yield event.plain_result(msg)

    @player_required
    async def handle_upgrade_fields(self, player: Player, event: AstrMessageEvent):
        """扩展灵田数量"""
        success, msg = await self.mgr.upgrade_fields(player)
        yield event.plain_result(msg)

    @player_required
    async def handle_harvest(self, player: Player, event: AstrMessageEvent):
        """收取药材"""
        success, msg = await self.mgr.harvest(player, self.config_manager)
        yield event.plain_result(msg)

    @player_required
    async def handle_upgrade_harvest(self, player: Player, event: AstrMessageEvent):
        """升级收取等级"""
        success, msg = await self.mgr.upgrade_harvest_level(player)
        yield event.plain_result(msg)

    @player_required
    async def handle_upgrade_fire_control(self, player: Player, event: AstrMessageEvent):
        """升级丹药控火"""
        success, msg = await self.mgr.upgrade_fire_control(player)
        yield event.plain_result(msg)
