# handlers/encounter_handler.py
"""奇遇系统命令处理器 — /奇遇 /奇遇信息 /奇遇记录"""
import json
from typing import AsyncGenerator

from astrbot.api.event import AstrMessageEvent

from ..data import DataBase
from ..managers.encounter_manager import EncounterManager
from ..models import Player

__all__ = ["EncounterHandler"]


class EncounterHandler:
    """奇遇系统命令处理器"""

    def __init__(self, db: DataBase, encounter_manager: EncounterManager):
        self.db = db
        self.encounter_mgr = encounter_manager

    async def handle_choose(self, event: AstrMessageEvent, choice: str = "") -> AsyncGenerator:
        """处理 /奇遇 A/B/C 选择回复"""
        user_id = event.get_sender_id()
        player = await self.db.get_player_by_id(user_id)
        if not player:
            yield event.plain_result("❌ 你还未踏入修仙之路！")
            return

        choice = (choice or "").strip()
        if not choice or choice.upper() not in ("A", "B", "C"):
            yield event.plain_result("请使用 /奇遇 A/B/C 回复当前奇遇。")
            return

        result = await self.encounter_mgr.resolve(player, user_id, choice.lower())
        yield event.plain_result(result)

    async def handle_info(self, event: AstrMessageEvent) -> AsyncGenerator:
        """查看奇遇信息（因果值 + 今日次数 + 因果加成说明）"""
        user_id = event.get_sender_id()
        player = await self.db.get_player_by_id(user_id)
        if not player:
            yield event.plain_result("❌ 你还未踏入修仙之路！")
            return

        karma = int(getattr(player, "karma", 0) or 0)
        title = self.encounter_mgr.get_karma_title(karma)
        daily_limit = self.encounter_mgr.settings.get("daily_limit", 3)

        lines = [
            f"☯️ 因果值：{karma}（{title}）",
            "━━━━━━━━━━━━━━━",
            f"今日奇遇：{player.daily_encounter_count}/{daily_limit} 次",
        ]
        if karma <= -500:
            lines.append("⚔️ 因果加成：攻击力 +8%（魔道修士）")
        elif karma <= -100:
            lines.append("⚔️ 因果加成：攻击力 +4%（偏邪）")
        elif karma >= 500:
            lines.append("🧘 因果加成：修炼速度 +8%（正道修士）")
        elif karma >= 100:
            lines.append("🧘 因果加成：修炼速度 +4%（偏正）")
        lines.append("━━━━━━━━━━━━━━━")
        lines.append("💡 因果每日向中立衰减 2 点；善修速，恶强攻")
        yield event.plain_result("\n".join(lines))

    async def handle_history(self, event: AstrMessageEvent) -> AsyncGenerator:
        """查看最近奇遇历史"""
        user_id = event.get_sender_id()
        player = await self.db.get_player_by_id(user_id)
        if not player:
            yield event.plain_result("❌ 你还未踏入修仙之路！")
            return

        history = self.encounter_mgr.get_history(player)
        if not history:
            yield event.plain_result("你还没有经历过任何奇遇。")
            return

        lines = ["📜 奇遇记录（最近10条）", "━━━━━━━━━━━━━━━"]
        for h in reversed(history[-10:]):
            roll = "成功" if h.get("roll") == "success" else "失败"
            lines.append(
                f"【{h.get('name', '未知')}】→ {h.get('choice', '')}（{roll}，因果{int(h.get('karma_delta', 0)):+d}）"
            )
        yield event.plain_result("\n".join(lines))
