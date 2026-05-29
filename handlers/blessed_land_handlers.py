# handlers/blessed_land_handlers.py
"""洞天福地处理器"""
from astrbot.api.event import AstrMessageEvent
from ..data import DataBase
from ..managers.blessed_land_manager import BlessedLandManager
from ..models import Player
from .utils import player_required

__all__ = ["BlessedLandHandlers"]


class BlessedLandHandlers:
    """洞天福地处理器"""
    
    def __init__(self, db: DataBase, blessed_land_mgr: BlessedLandManager):
        self.db = db
        self.mgr = blessed_land_mgr
    
    @player_required
    async def handle_blessed_land_info(self, player: Player, event: AstrMessageEvent):
        """查看洞天信息"""
        info = await self.mgr.get_blessed_land_info(player.user_id)
        yield event.plain_result(info)
    
    @player_required
    async def handle_purchase(self, player: Player, event: AstrMessageEvent, land_type: int = 0):
        """购买洞天"""
        if land_type <= 0:
            yield event.plain_result(
                "🏔️ 购买洞天\n"
                "━━━━━━━━━━━━━━━\n"
                "1. 小洞天 - 10,000灵石 (+5%修炼)\n"
                "2. 中洞天 - 50,000灵石 (+10%修炼)\n"
                "3. 大洞天 - 200,000灵石 (+20%修炼)\n"
                "4. 福地 - 500,000灵石 (+30%修炼)\n"
                "5. 洞天福地 - 1,000,000灵石 (+50%修炼)\n"
                "━━━━━━━━━━━━━━━\n"
                "💡 使用 /购买洞天 <编号>"
            )
            return
        
        success, msg = await self.mgr.purchase_blessed_land(player, land_type)
        yield event.plain_result(msg)
    
    @player_required
    async def handle_upgrade(self, player: Player, event: AstrMessageEvent, land_type: int = 0):
        """升级洞天"""
        success, msg = await self.mgr.upgrade_blessed_land(player, land_type)
        yield event.plain_result(msg)
