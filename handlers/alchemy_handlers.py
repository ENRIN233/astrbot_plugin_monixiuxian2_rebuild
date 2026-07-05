# handlers/alchemy_handlers.py
"""炼丹处理器 — nonebot 迁移版（寒热调和配方系统 + 炼丹炉）"""
import re
from astrbot.api.event import AstrMessageEvent
from ..managers.alchemy_manager import AlchemyManager
from ..data.data_manager import DataBase
from ..models import Player
from .utils import player_required

__all__ = ["AlchemyHandlers"]


class AlchemyHandlers:
    """炼丹处理器"""

    def __init__(self, db: DataBase, alchemy_mgr: AlchemyManager, config_manager=None):
        self.db = db
        self.alchemy_mgr = alchemy_mgr
        self.config_manager = config_manager

    @player_required
    async def handle_find_recipes(self, player: Player, event: AstrMessageEvent):
        """扫描药材，显示可用配方"""
        success, msg = await self.alchemy_mgr.find_recipes(player)
        yield event.plain_result(msg)

    @player_required
    async def handle_craft(self, player: Player, event: AstrMessageEvent, recipe_text: str = ""):
        """执行炼丹（格式：主药XX N 药引YY N 辅药ZZ N）"""
        if not recipe_text or not recipe_text.strip():
            yield event.plain_result(
                "❌ 请指定配方！\n"
                "格式：/配方 主药<药材名> <数量> 药引<药材名> <数量> 辅药<药材名> <数量>\n"
                "示例：/配方 主药恒心草 2 药引天青花 1 辅药宁心草 3"
            )
            return

        text = recipe_text.strip()

        # 解析格式：主药XX N 药引YY N 辅药ZZ N
        pattern = r"主药(\S+)\s+(\d+)\s+药引(\S+)\s+(\d+)\s+辅药(\S+)\s+(\d+)"
        match = re.search(pattern, text)
        if not match:
            yield event.plain_result(
                "❌ 格式错误！\n"
                "正确格式：/配方 主药<名称> <数量> 药引<名称> <数量> 辅药<名称> <数量>"
            )
            return

        main_name = match.group(1)
        main_count = int(match.group(2))
        catalyst_name = match.group(3)
        catalyst_count = int(match.group(4))
        aux_name = match.group(5)
        aux_count = int(match.group(6))

        # 基本校验
        for name, count in [(main_name, main_count), (catalyst_name, catalyst_count), (aux_name, aux_count)]:
            if count <= 0:
                yield event.plain_result(f"❌ {name} 数量必须大于 0")
                return
            if count > 11:
                yield event.plain_result(f"❌ 单种药材最多使用 11 个")
                return

        success, msg = await self.alchemy_mgr.craft(
            player,
            main_name, main_count,
            catalyst_name, catalyst_count,
            aux_name, aux_count,
        )
        yield event.plain_result(msg)

    @player_required
    async def handle_equip_furnace(self, player: Player, event: AstrMessageEvent, furnace_name: str = ""):
        """装备炼丹炉"""
        if not furnace_name or not furnace_name.strip():
            # 显示当前装备的炉子和可用炉子列表
            current = player.furnace if player.furnace else "无"
            lines = [f"🔥 当前炼丹炉：{current}", "━━━━━━━━━━━━━━━"]
            if self.config_manager and self.config_manager.furnaces_data:
                lines.append("可用炼丹炉：")
                for fid, fdata in self.config_manager.furnaces_data.items():
                    buff = fdata.get("buff", 0)
                    lines.append(f"  {fdata['name']} — 出丹+{buff}（{fdata.get('desc', '')}）")
            lines.append("━━━━━━━━━━━━━━━")
            lines.append("💡 使用 /装备炼丹炉 <炉子名称>")
            yield event.plain_result("\n".join(lines))
            return

        furnace_name = furnace_name.strip()

        # 验证炉子是否存在
        found = False
        if self.config_manager and self.config_manager.furnaces_data:
            for fid, fdata in self.config_manager.furnaces_data.items():
                if fdata.get("name") == furnace_name:
                    found = True
                    break

        if not found:
            yield event.plain_result(f"❌ 未知的炼丹炉：{furnace_name}")
            return

        player.furnace = furnace_name
        await self.db.update_player(player)
        yield event.plain_result(f"🔥 成功装备炼丹炉：{furnace_name}")

    @player_required
    async def handle_unequip_furnace(self, player: Player, event: AstrMessageEvent):
        """卸下炼丹炉"""
        if not player.furnace:
            yield event.plain_result("❌ 你没有装备炼丹炉")
            return

        old_name = player.furnace
        player.furnace = ""
        await self.db.update_player(player)
        yield event.plain_result(f"🔥 已卸下炼丹炉：{old_name}")
