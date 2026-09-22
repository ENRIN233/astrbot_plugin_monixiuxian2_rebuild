# handlers/spirit_farm_handlers.py
"""灵植园处理器 — v2（播种/催熟/清理/偷菜/护园）"""
import re

from astrbot.api.all import At
from astrbot.api.event import AstrMessageEvent
from ..data import DataBase
from ..managers.spirit_farm_manager import SpiritFarmManager
from ..models import Player
from .utils import player_required

__all__ = ["SpiritFarmHandlers"]


class SpiritFarmHandlers:
    """灵植园处理器"""

    def __init__(self, db: DataBase, farm_mgr: SpiritFarmManager, config_manager=None):
        self.db = db
        self.mgr = farm_mgr
        self.config_manager = config_manager

    @player_required
    async def handle_farm_info(self, player: Player, event: AstrMessageEvent):
        """查看灵田信息（v2 地块矩阵视图）"""
        info = await self.mgr.get_farm_info(player.user_id, self.config_manager, player=player)
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
        """收取药材（收全部成熟地块）"""
        success, msg = await self.mgr.harvest(player, self.config_manager)
        yield event.plain_result(msg)

    @player_required
    async def handle_sow(self, player: Player, event: AstrMessageEvent, herb_name: str = "", count: str = "1"):
        """播种：/灵田播种 <药名> [数量|全部]"""
        success, msg = await self.mgr.sow(player, herb_name, count)
        yield event.plain_result(msg)

    @player_required
    async def handle_ripen(self, player: Player, event: AstrMessageEvent):
        """催熟全部生长中灵植"""
        success, msg = await self.mgr.force_ripen(player)
        yield event.plain_result(msg)

    @player_required
    async def handle_clear(self, player: Player, event: AstrMessageEvent):
        """清理枯死地块"""
        success, msg = await self.mgr.clear_dead_plots(player)
        yield event.plain_result(msg)

    @player_required
    async def handle_steal(self, player: Player, event: AstrMessageEvent, target: str = ""):
        """偷菜：/偷菜 @某人"""
        target_id = self._extract_user_id(target, event)
        if not target_id:
            yield event.plain_result(
                "🌙 偷菜系统\n"
                "━━━━━━━━━━━━━━━\n"
                "偷取群友灵田里的成熟灵植，每次 1 株！\n"
                "每日偷 3 次；对方被偷 5 次后灵气封闭。\n"
                "对方若有护园灵兽，可能被当场逮住罚款！\n"
                "━━━━━━━━━━━━━━━\n"
                "💡 使用 /偷菜 @某人"
            )
            return
        target_player = await self.db.get_player_by_id(target_id)
        if not target_player:
            yield event.plain_result("❌ 对方还未踏入修仙之路，偷不得。")
            return
        success, msg = await self.mgr.steal(player, target_player)
        yield event.plain_result(msg)

    @player_required
    async def handle_beast(self, player: Player, event: AstrMessageEvent, action: str = ""):
        """护园灵兽：/护园 查看；/护园 升级"""
        if action and ("升级" in action or "招募" in action or "购买" in action):
            success, msg = await self.mgr.buy_or_upgrade_beast(player)
            yield event.plain_result(msg)
            return
        # 查看模式：复用 /灵田 视图（含灵兽行）
        info = await self.mgr.get_farm_info(player.user_id, self.config_manager, player=player)
        yield event.plain_result(info)

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

    def _extract_user_id(self, msg: str, event: AstrMessageEvent = None) -> str:
        """提取用户ID（支持At组件和纯数字QQ号，与双修系统同款）"""
        if event and hasattr(event, "message_obj") and event.message_obj:
            message_chain = getattr(event.message_obj, "message", []) or []
            for component in message_chain:
                if isinstance(component, At):
                    for attr in ("qq", "target", "uin", "user_id"):
                        val = getattr(component, attr, None)
                        if val:
                            return str(val).lstrip("@")
        msg = (msg or "").strip()
        if msg:
            match = re.search(r"(\d{5,})", msg)
            if match:
                return match.group(1)
        return ""
