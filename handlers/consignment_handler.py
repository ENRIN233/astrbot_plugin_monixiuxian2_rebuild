"""寄售行命令处理器。"""
from __future__ import annotations
from astrbot.api.event import AstrMessageEvent
from ..data import DataBase
from ..models import Player
from ..managers import ConsignmentManager
from ..config_manager import ConfigManager
from .utils import player_required


__all__ = ["ConsignmentHandler"]


class ConsignmentHandler:
    def __init__(self, db: DataBase, cm: ConsignmentManager, config_manager: ConfigManager):
        self.db = db
        self.mgr = cm
        self.config_manager = config_manager

    def _lookup_item_meta(self, name: str) -> tuple[str, str] | None:
        """返回 (item_id, item_type) 或 None"""
        for source, item_type in [
            (self.config_manager.weapons_data, "weapon"),
            (self.config_manager.items_data, "equipment"),
            (self.config_manager.pills_data, "pill"),
            (self.config_manager.exp_pills_data, "pill"),
            (self.config_manager.utility_pills_data, "pill"),
        ]:
            if name in source:
                entry = source[name]
                return str(entry.get("id", name)), item_type
        return None

    @player_required
    async def handle_list_item(self, player: Player, event: AstrMessageEvent, args: str = ""):
        parts = args.strip().split()
        if len(parts) < 2:
            yield event.plain_result("用法：/寄售 <物品名> <价格> [数量]")
            return
        name = parts[0]
        if not parts[1].isdigit():
            yield event.plain_result("价格必须是正整数")
            return
        price = int(parts[1])
        quantity = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1

        meta = self._lookup_item_meta(name)
        if not meta:
            yield event.plain_result(f"找不到物品【{name}】的配置")
            return
        item_id, item_type = meta

        try:
            lid = await self.mgr.list_item(player.user_id, name, item_id,
                                            item_type, price, quantity)
        except ValueError as e:
            yield event.plain_result(f"上架失败：{e}")
            return
        fee = int(price * quantity * self.mgr.listing_fee_rate)
        yield event.plain_result(
            f"✅ 上架成功（编号 {lid}）\n"
            f"物品：{name} × {quantity}\n"
            f"单价：{price:,} 灵石 | 总价：{price * quantity:,} 灵石\n"
            f"已扣手续费：{fee:,} 灵石（不退还）"
        )

    @player_required
    async def handle_browse(self, player: Player, event: AstrMessageEvent, args: str = ""):
        page = int(args.strip()) if args.strip().isdigit() else 1
        page = max(1, page)
        listings = await self.mgr.list_active(offset=(page - 1) * 10, limit=10)
        if not listings:
            yield event.plain_result("寄售行空空如也")
            return
        lines = [f"🏪 寄售行 第 {page} 页（价格为单价）"]
        for L in listings:
            lines.append(
                f"#{L['listing_id']} 【{L['item_name']}】× {L['quantity']} "
                f"| {L['price']:,} 灵石/个 | 卖家 {L['seller_id']}"
            )
        lines.append("使用 /购买寄售 <编号> 购买")
        yield event.plain_result("\n".join(lines))

    @player_required
    async def handle_buy(self, player: Player, event: AstrMessageEvent, args: str = ""):
        parts = args.strip().split()
        if not parts or not parts[0].isdigit():
            yield event.plain_result("用法：/购买寄售 <编号> [数量]")
            return
        lid = int(parts[0])
        quantity = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
        try:
            result = await self.mgr.buy_listing(lid, player.user_id, quantity)
        except ValueError as e:
            yield event.plain_result(f"购买失败：{e}")
            return
        total = result["price"] * result["bought"]
        yield event.plain_result(
            f"🎉 购买成功\n"
            f"物品：{result['item_name']} × {result['bought']}\n"
            f"单价：{result['price']:,} 灵石 | 花费：{total:,} 灵石"
        )

    @player_required
    async def handle_my(self, player: Player, event: AstrMessageEvent):
        listings = await self.mgr.list_my(player.user_id)
        if not listings:
            yield event.plain_result("你没有正在寄售的物品")
            return
        lines = ["📋 我的寄售"]
        for L in listings:
            lines.append(f"#{L['listing_id']} 【{L['item_name']}】× {L['quantity']} | {L['price']:,} 灵石")
        yield event.plain_result("\n".join(lines))

    @player_required
    async def handle_cancel(self, player: Player, event: AstrMessageEvent, args: str = ""):
        if not args.strip().isdigit():
            yield event.plain_result("用法：/下架寄售 <编号>")
            return
        lid = int(args.strip())
        try:
            await self.mgr.cancel_listing(lid, player.user_id)
        except ValueError as e:
            yield event.plain_result(f"下架失败：{e}")
            return
        yield event.plain_result(f"✅ 已下架 #{lid}（手续费不退）")
