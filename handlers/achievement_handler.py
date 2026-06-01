# handlers/achievement_handler.py

from astrbot.api.event import AstrMessageEvent
from ..data import DataBase
from ..managers.achievement_manager import AchievementManager
from ..models import Player
from .utils import player_required

CMD_ACHIEVEMENT_LIST = "成就列表"
CMD_EQUIP_ACHIEVEMENT = "装备成就"
CMD_UNEQUIP_ACHIEVEMENT = "卸下成就"

__all__ = ["AchievementHandler"]


class AchievementHandler:
    """成就处理器"""

    def __init__(self, db: DataBase, achievement_manager: AchievementManager):
        self.db = db
        self.achievement_mgr = achievement_manager

    @player_required
    async def handle_list(self, player: Player, event: AstrMessageEvent):
        """展示成就列表"""
        # 自动检查并解锁新成就
        newly_unlocked = self.achievement_mgr.check_and_unlock(player)
        if newly_unlocked:
            await self.db.update_player(player)
            unlock_text = "、".join(newly_unlocked)
            yield event.plain_result(f"🎉 新解锁成就：{unlock_text}")

        result = self.achievement_mgr.format_achievement_list(player)
        yield event.plain_result(result)

    @player_required
    async def handle_equip(self, player: Player, event: AstrMessageEvent, achievement_name: str = ""):
        """装备成就"""
        if not achievement_name or not achievement_name.strip():
            yield event.plain_result("请指定成就名称，如：/装备成就 不屈修士")
            return

        achievement_name = achievement_name.strip()

        # 先自动检查解锁
        newly_unlocked = self.achievement_mgr.check_and_unlock(player)
        if newly_unlocked:
            await self.db.update_player(player)
            unlock_text = "、".join(newly_unlocked)
            yield event.plain_result(f"🎉 新解锁成就：{unlock_text}")

        success, msg = self.achievement_mgr.equip_achievement(player, achievement_name)
        if success:
            await self.db.update_player(player)
        yield event.plain_result(msg)

    @player_required
    async def handle_unequip(self, player: Player, event: AstrMessageEvent):
        """卸下成就"""
        success, msg = self.achievement_mgr.unequip_achievement(player)
        if success:
            await self.db.update_player(player)
        yield event.plain_result(msg)
