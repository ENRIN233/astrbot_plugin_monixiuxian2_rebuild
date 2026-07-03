# handlers/bounty_handlers.py
"""悬赏令处理器"""
from astrbot.api.event import AstrMessageEvent
from ..data import DataBase
from ..managers.bounty_manager import BountyManager
from ..models import Player
from .utils import player_required

__all__ = ["BountyHandlers"]

class BountyHandlers:
    """悬赏令处理器"""
    
    def __init__(self, db: DataBase, bounty_mgr: BountyManager):
        self.db = db
        self.bounty_mgr = bounty_mgr
    
    @player_required
    async def handle_bounty_list(self, player: Player, event: AstrMessageEvent):
        """显示悬赏列表"""
        # 检查今日是否已达上限
        daily_count = await self.bounty_mgr.get_daily_bounty_count(player.user_id)
        if daily_count >= self.bounty_mgr.DAILY_BOUNTY_LIMIT:
            yield event.plain_result(
                f"📜 悬赏令\n"
                f"━━━━━━━━━━━━━━━\n"
                f"你今日已完成 {daily_count}/{self.bounty_mgr.DAILY_BOUNTY_LIMIT} 次悬赏\n"
                f"今日委托已全部完成，明日再来！\n"
                f"━━━━━━━━━━━━━━━\n"
                f"💡 可使用 /悬赏状态 查看当前悬赏进度"
            )
            return

        bounties = await self.bounty_mgr.get_bounty_list(player)

        lines = ["📜 悬赏令 · 今日委托", "━━━━━━━━━━━━━━━"]
        for i, b in enumerate(bounties, 1):
            reward = b.get("reward", {})
            drop = b.get("drop_reward")
            line = (
                f"[{i}] {b['name']}（{b.get('difficulty_name', '未知')}·{b.get('category', '任务')}）\n"
                f"  - 时限：{b.get('time_limit', 0) // 60} 分钟（到时限后自动完成）\n"
                f"  - 奖励：{reward.get('stone', 0):,} 灵石 + {reward.get('exp', 0):,} 修为"
            )
            if drop:
                dt = drop.get("type", "main_technique")
                if dt == "skill":
                    drop_type = "神通"
                elif dt == "sub_technique":
                    drop_type = "辅修功法"
                else:
                    drop_type = "功法"
                line += f"\n  - {drop_type}掉落：【{drop.get('rank', '')}】{drop['name']}"
            line += f"\n  - 说明：{b.get('description', '')}"
            lines.append(line)
        lines.append("━━━━━━━━━━━━━━━")

        yield event.plain_result("\n".join(lines))
    
    @player_required
    async def handle_accept_bounty(self, player: Player, event: AstrMessageEvent, bounty_id: int = 0):
        """接取悬赏"""
        if bounty_id <= 0:
            yield event.plain_result("❌ 请指定悬赏编号，例如：/接取悬赏 1")
            return
        
        success, msg = await self.bounty_mgr.accept_bounty(player, bounty_id)
        prefix = "✅" if success else "❌"
        yield event.plain_result(f"{prefix} {msg}")
    
    @player_required
    async def handle_bounty_status(self, player: Player, event: AstrMessageEvent):
        """查看悬赏状态"""
        success, msg = await self.bounty_mgr.check_bounty_status(player)
        yield event.plain_result(msg)
    
    @player_required
    async def handle_complete_bounty(self, player: Player, event: AstrMessageEvent):
        """完成悬赏"""
        success, msg = await self.bounty_mgr.complete_bounty(player)
        prefix = "✅" if success else "❌"
        yield event.plain_result(f"{prefix} {msg}")
    
    @player_required
    async def handle_abandon_bounty(self, player: Player, event: AstrMessageEvent):
        """放弃悬赏"""
        success, msg = await self.bounty_mgr.abandon_bounty(player)
        prefix = "✅" if success else "❌"
        yield event.plain_result(f"{prefix} {msg}")
