# handlers/spirit_farm_handlers.py
"""灵田处理器"""
from astrbot.api.event import AstrMessageEvent
from ..data import DataBase
from ..managers.spirit_farm_manager import SpiritFarmManager
from ..models import Player
from .utils import player_required

__all__ = ["SpiritFarmHandlers"]


class SpiritFarmHandlers:
    """灵田处理器"""
    
    def __init__(self, db: DataBase, farm_mgr: SpiritFarmManager):
        self.db = db
        self.mgr = farm_mgr
    
    @player_required
    async def handle_farm_info(self, player: Player, event: AstrMessageEvent):
        """查看灵田信息"""
        info = await self.mgr.get_farm_info(player.user_id)
        yield event.plain_result(info)
    
    @player_required
    async def handle_create_farm(self, player: Player, event: AstrMessageEvent):
        """开垦灵田"""
        success, msg = await self.mgr.create_farm(player)
        yield event.plain_result(msg)
    
    @player_required
    async def handle_plant(self, player: Player, event: AstrMessageEvent, herb_name: str = "", quantity: int = 1):
        """种植灵草（支持批量）"""
        if not herb_name or not herb_name.strip():
            yield event.plain_result(
                "🌱 可种植的灵草\n"
                "━━━━━━━━━━━━━━━\n"
                "灵草 - 1小时 (修为+500, 灵石+3,000)\n"
                "血灵草 - 2小时 (修为+1,500, 灵石+9,000)\n"
                "冰心草 - 4小时 (修为+4,000, 灵石+24,000)\n"
                "火焰花 - 8小时 (修为+10,000, 灵石+60,000)\n"
                "九叶灵芝 - 24小时 (修为+30,000, 灵石+180,000)\n"
                "天山雪莲 - 24小时 (修为+60,000, 灵石+250,000) [Lv15+ 灵田Lv3]\n"
                "太乙仙草 - 24小时 (修为+120,000, 灵石+400,000) [Lv21+ 灵田Lv4]\n"
                "混沌神莲 - 24小时 (修为+250,000, 灵石+800,000) [Lv27+ 灵田Lv5]\n"
                "━━━━━━━━━━━━━━━\n"
                "💡 使用 /种植 <灵草名> [数量]\n"
                "   例如：/种植 灵草 5"
            )
            return

        herb_name = herb_name.strip()

        # 校验数量
        if quantity <= 0:
            yield event.plain_result("❌ 种植数量必须大于0！")
            return
        if quantity > 100:
            yield event.plain_result("❌ 单次种植数量不能超过100！")
            return

        success, msg = await self.mgr.plant_herb(player, herb_name, quantity)
        yield event.plain_result(msg)
    
    @player_required
    async def handle_harvest(self, player: Player, event: AstrMessageEvent):
        """收获灵草"""
        success, msg = await self.mgr.harvest(player)
        yield event.plain_result(msg)
    
    @player_required
    async def handle_upgrade_farm(self, player: Player, event: AstrMessageEvent):
        """升级灵田"""
        success, msg = await self.mgr.upgrade_farm(player)
        yield event.plain_result(msg)
