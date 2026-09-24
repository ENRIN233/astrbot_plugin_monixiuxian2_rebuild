"""云游商人命令处理器 — /云游商人 /购买商品"""
from typing import AsyncGenerator

from astrbot.api.event import AstrMessageEvent

from ..data import DataBase
from ..managers.merchant_manager import MerchantManager, RANK_NAMES

__all__ = ["MerchantHandler"]

_KIND_LABEL = {"tech": "功法", "skill": "神通", "subtech": "辅修",
               "material": "材料", "herb": "药材", "pill": "丹药"}


def _rank_label(rank_idx: int) -> str:
    if 0 <= rank_idx < len(RANK_NAMES):
        return RANK_NAMES[rank_idx]
    return ""


def _kind_label(kind: str) -> str:
    return _KIND_LABEL.get(kind, "秘宝")


class MerchantHandler:
    """云游商人命令处理器"""

    def __init__(self, db: DataBase, merchant_mgr: MerchantManager):
        self.db = db
        self.merchant_mgr = merchant_mgr

    async def handle_view(self, event: AstrMessageEvent) -> AsyncGenerator:
        """/云游商人 查看本期货架"""
        user_id = event.get_sender_id()
        player = await self.db.get_player_by_id(user_id)
        if not player:
            yield event.plain_result("❌ 你还未踏入修仙之路！")
            return

        if not self.merchant_mgr.enabled:
            yield event.plain_result("🧳 云游商人系统已关闭。")
            return

        window, goods = await self.merchant_mgr.list_goods()
        if not window:
            yield event.plain_result(
                "🧳 云游商人不在。\n"
                "他行踪不定，每日出现 2-3 次，来时全服自有公告。"
            )
            return

        remaining = max(1, int(window["closed_at"]) - int(window["opened_at"])) // 60
        lines = [
            f"🧳 云游商人·{window['merchant_name']} 的货摊（约 {remaining} 分钟后离开）",
            "━━━━━━━━━━━━━━━",
        ]
        for g in goods:
            prefix = "⭐" if g["slot_type"] == "tech" else ("💰" if g["slot_type"] == "bargain" else "▫️")
            owned = await self.merchant_mgr._owned_mark(player, g["item_kind"], g["item_name"])
            mark = "（已拥有）" if owned else ""
            stock = "" if g["slot_type"] == "tech" else f" ×{g['stock_left']}"
            rank = _rank_label(g["rank_idx"])
            rank_part = f"{rank}" if rank and g["slot_type"] == "tech" else ""
            lines.append(
                f"{prefix} [{g['id']}] {rank_part}{_kind_label(g['item_kind'])}·{g['item_name']}"
                f"{mark} — {g['price']:,} 灵石{stock}"
            )
        lines.append("━━━━━━━━━━━━━━━")
        lines.append("💡 /购买商品 <编号> [数量] 购买（每期 2 件/每日 4 件，⭐ 全服仅 1 件）")
        yield event.plain_result("\n".join(lines))

    async def handle_buy(self, event: AstrMessageEvent, goods_id: str = "",
                         quantity: str = "1") -> AsyncGenerator:
        """/购买商品 <编号> [数量]"""
        user_id = event.get_sender_id()
        player = await self.db.get_player_by_id(user_id)
        if not player:
            yield event.plain_result("❌ 你还未踏入修仙之路！")
            return

        if not self.merchant_mgr.enabled:
            yield event.plain_result("🧳 云游商人系统已关闭。")
            return

        try:
            gid = int(str(goods_id).strip())
        except (TypeError, ValueError):
            yield event.plain_result("用法：/购买商品 <编号> [数量]，编号见 /云游商人 货架。")
            return
        try:
            qty = max(1, min(99, int(str(quantity).strip() or "1")))
        except (TypeError, ValueError):
            qty = 1

        ok, msg = await self.merchant_mgr.buy(player, gid, qty)
        yield event.plain_result(msg)
