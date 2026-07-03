# handlers/dungeon_handlers.py
"""探险副本指令处理器"""

from astrbot.api.event import AstrMessageEvent
from ..managers.dungeon_manager import DungeonManager
from ..data.data_manager import DataBase


class DungeonHandlers:
    def __init__(self, db: DataBase, dungeon_mgr: DungeonManager):
        self.db = db
        self.dungeon_mgr = dungeon_mgr

    async def handle_dungeon_list(self, event: AstrMessageEvent):
        """探险列表"""
        player = await self.db.get_player_by_id(event.get_sender_id())
        if not player:
            yield event.plain_result("道友尚未踏入仙途。")
            return
        success, msg = await self.dungeon_mgr.get_available_dungeons(player)
        yield event.plain_result(msg)

    async def handle_dungeon_enter(self, event: AstrMessageEvent, dungeon_name: str = ""):
        """进入探险"""
        user_id = event.get_sender_id()
        player = await self.db.get_player_by_id(user_id)
        if not player:
            yield event.plain_result("道友尚未踏入仙途。")
            return

        # 从名称匹配探险key
        dungeon_key = ""
        dungeons = self.dungeon_mgr.config_manager.dungeon_config.get("dungeons", [])
        for d in dungeons:
            if dungeon_name in (d.get("key", ""), d.get("name", "")):
                dungeon_key = d["key"]
                break
            # 模糊匹配
            if dungeon_name and dungeon_name in d.get("name", ""):
                dungeon_key = d["key"]
                break

        if not dungeon_key and dungeons:
            # 名称为空时展示列表
            success, msg = await self.dungeon_mgr.get_available_dungeons(player)
            yield event.plain_result(msg)
            return

        if not dungeon_key:
            yield event.plain_result(f"未找到探险「{dungeon_name}」。")
            return

        success, msg = await self.dungeon_mgr.enter_dungeon(user_id, dungeon_key, player)
        yield event.plain_result(msg)

    async def handle_dungeon_advance(self, event: AstrMessageEvent, choice: str = ""):
        """探险前进/选择路径"""
        user_id = event.get_sender_id()
        player = await self.db.get_player_by_id(user_id)
        if not player:
            yield event.plain_result("道友尚未踏入仙途。")
            return

        if not choice:
            # 无参数 - 展示当前地图
            success, msg = await self.dungeon_mgr.show_current_map(user_id)
            yield event.plain_result(msg)
            return

        success, msg = await self.dungeon_mgr.choose_and_advance(user_id, choice, player)
        yield event.plain_result(msg)

    async def handle_dungeon_status(self, event: AstrMessageEvent):
        """探险状态"""
        user_id = event.get_sender_id()
        success, msg = await self.dungeon_mgr.get_status(user_id)
        yield event.plain_result(msg)

    async def handle_dungeon_retreat(self, event: AstrMessageEvent):
        """探险撤离"""
        user_id = event.get_sender_id()
        player = await self.db.get_player_by_id(user_id)
        if not player:
            yield event.plain_result("道友尚未踏入仙途。")
            return
        success, msg = await self.dungeon_mgr.retreat(user_id, player)
        yield event.plain_result(msg)
