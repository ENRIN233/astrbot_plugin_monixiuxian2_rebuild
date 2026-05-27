"""即时交易命令处理器。"""
from __future__ import annotations
from astrbot.api.event import AstrMessageEvent
from astrbot.api.message_components import At, Plain
from ..data import DataBase
from ..models import Player
from ..managers import TradeManager
from .utils import player_required


__all__ = ["TradeHandler"]


def _extract_at_target(event: AstrMessageEvent) -> str | None:
    msg = getattr(event.message_obj, "message", []) if hasattr(event, "message_obj") and event.message_obj else []
    for comp in msg:
        if isinstance(comp, At):
            for attr in ("qq", "target", "uin"):
                if hasattr(comp, attr):
                    return str(getattr(comp, attr))
    return None


class TradeHandler:
    def __init__(self, db: DataBase, trade_mgr: TradeManager):
        self.db = db
        self.mgr = trade_mgr

    @player_required
    async def handle_start_trade(self, player: Player, event: AstrMessageEvent, args: str = ""):
        if not event.get_group_id():
            yield event.plain_result("交易只能在群聊中发起")
            return
        target_id = _extract_at_target(event)
        if not target_id:
            yield event.plain_result("请使用 /交易 @某人 发起交易")
            return
        if target_id == player.user_id:
            yield event.plain_result("不能与自己交易")
            return
        target_player = await self.db.get_player_by_id(target_id)
        if not target_player:
            yield event.plain_result("对方还未踏入仙途")
            return
        try:
            tid = await self.mgr.create_trade(player.user_id, target_id)
        except ValueError as e:
            yield event.plain_result(f"交易发起失败：{e}")
            return
        yield event.plain_result(
            f"✅ 已向【{target_player.user_name or target_id}】发起交易请求（编号 {tid}）\n"
            f"等待对方使用 /接受交易 或 /拒绝交易"
        )

    @player_required
    async def handle_accept(self, player: Player, event: AstrMessageEvent):
        trade = await self.mgr.get_active_trade(player.user_id)
        if not trade:
            yield event.plain_result("当前没有待接受的交易请求")
            return
        if trade["status"] != "pending":
            yield event.plain_result("当前没有待接受的交易请求")
            return
        if trade["player_b"] != player.user_id:
            yield event.plain_result("只有交易接收方可以接受交易")
            return
        try:
            await self.mgr.accept_trade(trade["trade_id"], player.user_id)
        except ValueError as e:
            yield event.plain_result(f"接受失败：{e}")
            return
        yield event.plain_result(
            f"✅ 已接受交易 #{trade['trade_id']}\n"
            f"使用 /添加物品 <名称> [数量] 或 /添加灵石 <数量> 放入物品\n"
            f"双方都输入 /确认交易 后完成交易"
        )

    @player_required
    async def handle_reject(self, player: Player, event: AstrMessageEvent):
        trade = await self.mgr.get_active_trade(player.user_id)
        if not trade:
            yield event.plain_result("当前没有待接受的交易请求")
            return
        if trade["status"] != "pending":
            yield event.plain_result("当前没有待接受的交易请求")
            return
        if trade["player_b"] != player.user_id:
            yield event.plain_result("只有交易接收方可以拒绝交易")
            return
        try:
            await self.mgr.reject_trade(trade["trade_id"], player.user_id)
        except ValueError as e:
            yield event.plain_result(f"拒绝失败：{e}")
            return
        yield event.plain_result("已拒绝交易请求")

    @player_required
    async def handle_add_item(self, player: Player, event: AstrMessageEvent, args: str = ""):
        parts = args.strip().split()
        if not parts:
            yield event.plain_result("用法：/添加物品 <名称> [数量]")
            return
        name = parts[0]
        count = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
        trade = await self.mgr.get_active_trade(player.user_id)
        if not trade:
            yield event.plain_result("当前没有进行中的交易")
            return
        if trade["status"] != "trading":
            yield event.plain_result("交易尚未被接受，请等待对方接受")
            return
        try:
            await self.mgr.add_item(trade["trade_id"], player.user_id, name, count)
        except ValueError as e:
            yield event.plain_result(f"添加失败：{e}")
            return
        yield event.plain_result(f"✅ 已放入【{name}】× {count}")

    @player_required
    async def handle_add_stones(self, player: Player, event: AstrMessageEvent, args: str = ""):
        if not args.strip().isdigit():
            yield event.plain_result("用法：/添加灵石 <数量>")
            return
        amount = int(args.strip())
        trade = await self.mgr.get_active_trade(player.user_id)
        if not trade:
            yield event.plain_result("当前没有进行中的交易")
            return
        if trade["status"] != "trading":
            yield event.plain_result("交易尚未被接受，请等待对方接受")
            return
        try:
            await self.mgr.add_stones(trade["trade_id"], player.user_id, amount)
        except ValueError as e:
            yield event.plain_result(f"添加失败：{e}")
            return
        yield event.plain_result(f"✅ 已放入灵石 × {amount:,}")

    @player_required
    async def handle_remove_item(self, player: Player, event: AstrMessageEvent, args: str = ""):
        name = args.strip()
        if not name:
            yield event.plain_result("用法：/移除物品 <名称>")
            return
        trade = await self.mgr.get_active_trade(player.user_id)
        if not trade:
            yield event.plain_result("当前没有进行中的交易")
            return
        if trade["status"] != "trading":
            yield event.plain_result("交易尚未被接受，请等待对方接受")
            return
        try:
            await self.mgr.remove_item(trade["trade_id"], player.user_id, name)
        except ValueError as e:
            yield event.plain_result(f"移除失败：{e}")
            return
        yield event.plain_result(f"✅ 已取回【{name}】")

    @player_required
    async def handle_view_trade(self, player: Player, event: AstrMessageEvent):
        trade = await self.mgr.get_active_trade(player.user_id)
        if not trade:
            yield event.plain_result("当前没有进行中的交易")
            return
        import json
        a_items = json.loads(trade["player_a_items"] or "[]")
        b_items = json.loads(trade["player_b_items"] or "[]")
        a_name = trade["player_a"]
        b_name = trade["player_b"]
        a_items_str = ", ".join(f"{i['name']}×{i['count']}" for i in a_items) or "无"
        b_items_str = ", ".join(f"{i['name']}×{i['count']}" for i in b_items) or "无"
        yield event.plain_result(
            f"📋 交易 #{trade['trade_id']}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"【{a_name}】放入:\n"
            f"  灵石: {trade['player_a_stones']:,}\n"
            f"  物品: {a_items_str}\n"
            f"  确认: {'✅' if trade['a_confirmed'] else '❌'}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"【{b_name}】放入:\n"
            f"  灵石: {trade['player_b_stones']:,}\n"
            f"  物品: {b_items_str}\n"
            f"  确认: {'✅' if trade['b_confirmed'] else '❌'}"
        )

    @player_required
    async def handle_confirm(self, player: Player, event: AstrMessageEvent):
        trade = await self.mgr.get_active_trade(player.user_id)
        if not trade:
            yield event.plain_result("当前没有进行中的交易")
            return
        if trade["status"] != "trading":
            yield event.plain_result("交易尚未被接受，请等待对方接受")
            return
        try:
            completed = await self.mgr.confirm(trade["trade_id"], player.user_id)
        except ValueError as e:
            yield event.plain_result(f"确认失败：{e}")
            return
        if completed:
            yield event.plain_result("🎉 交易完成！双方物品已结算")
        else:
            yield event.plain_result("✅ 已确认。等待对方确认...")

    @player_required
    async def handle_cancel(self, player: Player, event: AstrMessageEvent):
        trade = await self.mgr.get_active_trade(player.user_id)
        if not trade:
            yield event.plain_result("当前没有进行中的交易")
            return
        await self.mgr.cancel(trade["trade_id"], player.user_id)
        yield event.plain_result("已取消交易，物品/灵石已返还")
