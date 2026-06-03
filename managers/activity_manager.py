# managers/activity_manager.py
"""每日活跃度系统管理器"""
from datetime import datetime
from astrbot.api import logger
from ..data import DataBase
from ..models import Player

# 任务定义: (显示名, 活跃值, 目标次数)
TASK_DEFINITIONS = {
    "check_in":  ("每日签到",   10, 1),
    "adventure": ("完成历练",   20, 2),
    "rift":      ("探索秘境",   30, 1),
    "bounty":    ("完成悬赏",   20, 2),
    "shop_buy":  ("商店购买",   40, 1),
    "harvest":   ("灵田收获",   20, 1),
    "alchemy":   ("炼丹",       30, 1),
    "smelt":     ("炼金",       30, 1),
    "interest":  ("领取利息",   10, 1),
    "sect":      ("宗门贡献",   20, 1),
}

# 任务顺序（用于显示）
TASK_ORDER = ["check_in", "adventure", "rift", "bounty", "shop_buy", "harvest", "alchemy", "smelt", "interest", "sect"]

__all__ = ["ActivityTracker", "TASK_DEFINITIONS", "TASK_ORDER"]


class ActivityTracker:
    """每日活跃度管理器"""

    def __init__(self, db: DataBase):
        self.db = db

    def _reset_if_new_day(self, player: Player, today: str) -> bool:
        """如果跨日则重置活跃度数据，返回是否重置过"""
        if player.daily_activity_date != today:
            player.set_daily_activity({})
            player.daily_activity_points = 0
            player.daily_activity_date = today
            player.daily_activity_rewarded = 0
            return True
        return False

    async def _add_progress(self, player: Player, task_id: str) -> bool:
        """增加任务进度，返回是否有变化

        只在活跃值未满100且该任务未完成时计数。
        """
        if player.daily_activity_points >= 100:
            return False

        task_name, points, target = TASK_DEFINITIONS[task_id]
        activity = player.get_daily_activity()
        current = activity.get(task_id, 0)

        if current >= target:
            return False

        activity[task_id] = current + 1
        player.set_daily_activity(activity)

        # 只有任务刚好完成时才加活跃值
        if activity[task_id] >= target:
            player.daily_activity_points = min(100, player.daily_activity_points + points)

        await self.db.update_player(player)
        return True

    # ===== 9个任务钩子 =====

    async def track_check_in(self, player: Player):
        """签到完成"""
        today = datetime.now().strftime("%Y-%m-%d")
        self._reset_if_new_day(player, today)
        await self._add_progress(player, "check_in")

    async def track_adventure(self, player: Player):
        """完成历练"""
        today = datetime.now().strftime("%Y-%m-%d")
        self._reset_if_new_day(player, today)
        await self._add_progress(player, "adventure")

    async def track_rift(self, player: Player):
        """完成秘境探索"""
        today = datetime.now().strftime("%Y-%m-%d")
        self._reset_if_new_day(player, today)
        await self._add_progress(player, "rift")

    async def track_bounty(self, player: Player):
        """完成悬赏"""
        today = datetime.now().strftime("%Y-%m-%d")
        self._reset_if_new_day(player, today)
        await self._add_progress(player, "bounty")

    async def track_shop_buy(self, player: Player):
        """商店购买"""
        today = datetime.now().strftime("%Y-%m-%d")
        self._reset_if_new_day(player, today)
        await self._add_progress(player, "shop_buy")

    async def track_harvest(self, player: Player):
        """灵田收获"""
        today = datetime.now().strftime("%Y-%m-%d")
        self._reset_if_new_day(player, today)
        await self._add_progress(player, "harvest")

    async def track_alchemy(self, player: Player):
        """炼丹"""
        today = datetime.now().strftime("%Y-%m-%d")
        self._reset_if_new_day(player, today)
        await self._add_progress(player, "alchemy")

    async def track_smelt(self, player: Player):
        """炼金"""
        today = datetime.now().strftime("%Y-%m-%d")
        self._reset_if_new_day(player, today)
        await self._add_progress(player, "smelt")

    async def track_interest(self, player: Player):
        """领取利息"""
        today = datetime.now().strftime("%Y-%m-%d")
        self._reset_if_new_day(player, today)
        await self._add_progress(player, "interest")

    async def track_sect(self, player: Player):
        """宗门贡献"""
        today = datetime.now().strftime("%Y-%m-%d")
        self._reset_if_new_day(player, today)
        await self._add_progress(player, "sect")

    # ===== 展示和领奖 =====

    async def get_daily_activity_display(self, player: Player) -> str:
        """获取每日活跃度展示面板"""
        today = datetime.now().strftime("%Y-%m-%d")
        if self._reset_if_new_day(player, today):
            await self.db.update_player(player)

        activity = player.get_daily_activity()
        points = player.daily_activity_points
        lines = [
            f"📊 每日活跃度（今日活跃值：{points}/100）",
            "━━━━━━━━━━━━━━━",
        ]

        for task_id in TASK_ORDER:
            task_name, task_points, target = TASK_DEFINITIONS[task_id]
            current = activity.get(task_id, 0)
            if current >= target:
                status = "✅"
                progress_bar = "█" * 10
            else:
                status = "⬜"
                filled = round(current / target * 10) if target > 0 else 0
                progress_bar = "█" * filled + "░" * (10 - filled)
            lines.append(f"{status} {task_name:<6} +{task_points:<3}({current}/{target}) {progress_bar}")

        lines.append("━━━━━━━━━━━━━━━")
        if points >= 100:
            if player.daily_activity_rewarded:
                lines.append("🎁 今日奖励已领取")
            else:
                lines.append("🎉 所有任务已完成！使用 /活跃奖励 领取渡厄丹")
        else:
            lines.append(f"💡 活跃度达到100后使用 /活跃奖励 领取奖励")

        return "\n".join(lines)

    async def claim_reward(self, player: Player) -> str:
        """领取每日活跃奖励（渡厄丹）"""
        today = datetime.now().strftime("%Y-%m-%d")
        self._reset_if_new_day(player, today)

        if player.daily_activity_points < 100:
            return f"❌ 活跃值不足！当前 {player.daily_activity_points}/100，请完成更多任务。"

        if player.daily_activity_rewarded:
            return "❌ 今日奖励已领取，请明日再来。"

        # 发放渡厄丹
        inventory = player.get_pills_inventory()
        inventory["渡厄丹"] = inventory.get("渡厄丹", 0) + 1
        player.set_pills_inventory(inventory)
        player.daily_activity_rewarded = 1
        await self.db.update_player(player)

        return (
            "🎉 恭喜领取每日活跃奖励！\n"
            "━━━━━━━━━━━━━━━\n"
            "💊 渡厄丹 ×1\n"
            "（使下一次突破丢失的修为减少为0）\n"
            "━━━━━━━━━━━━━━━"
        )
