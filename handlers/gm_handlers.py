# handlers/gm_handlers.py
"""GM管理员指令处理器"""
import re
from typing import Tuple
from astrbot.api.event import AstrMessageEvent
from ..data import DataBase
from ..models import Player

__all__ = ["GMHandlers"]


class GMHandlers:
    """GM管理员指令处理器"""

    def __init__(self, db: DataBase, config_manager=None):
        self.db = db
        self.config_manager = config_manager

    def _extract_user_id(self, msg: str) -> str:
        """提取目标用户ID（支持@和纯数字QQ号）"""
        if not msg:
            return ""
        at_match = re.search(r'\[CQ:at,qq=(\d+)\]', msg)
        if at_match:
            return at_match.group(1)
        num_match = re.search(r'(\d{5,12})', msg)
        if num_match:
            return num_match.group(1)
        return ""

    def _parse_args(self, msg: str, target_id: str) -> str:
        """从消息中移除目标ID部分，返回剩余参数"""
        # 移除@格式
        msg = re.sub(r'\[CQ:at,qq=\d+\]', '', msg).strip()
        # 移除纯数字QQ号
        if target_id:
            msg = msg.replace(target_id, '', 1).strip()
        return msg

    async def _get_target(self, target_id: str) -> Tuple[bool, str, Player]:
        """获取目标玩家，返回 (success, error_msg, player)"""
        if not target_id:
            return False, "请指定目标玩家（@某人 或 QQ号）。", None
        player = await self.db.get_player_by_id(target_id)
        if not player:
            return False, f"玩家 {target_id} 不存在。", None
        return True, "", player

    async def handle_help(self) -> str:
        """GM指令帮助"""
        return (
            "🔧 GM管理员指令\n"
            "━━━━━━━━━━━━━━━\n"
            "GM加灵石 <目标> <数量> — 增加灵石\n"
            "GM扣灵石 <目标> <数量> — 扣除灵石\n"
            "GM加修为 <目标> <数量> — 增加修为\n"
            "GM设置境界 <目标> <等级> — 设置境界\n"
            "GM加物品 <目标> <物品名> [数量]\n"
            "GM扣物品 <目标> <物品名> [数量]\n"
            "GM加丹药 <目标> <丹药名> [数量]\n"
            "GM扣丹药 <目标> <丹药名> [数量]\n"
            "GM查看玩家 <目标> — 查看玩家信息\n"
            "GM刷新秘境 — 强制刷新秘境并重置所有玩家探索次数\n"
            "GM补偿 <物品 数量|物品 数量> — 创建全服补偿包\n"
            "━━━━━━━━━━━━━━━\n"
            "目标支持 @某人 或 QQ号\n"
            "补偿物品用 | 分隔，数量默认1，例：GM补偿 灵草 10|炼气丹 5"
        )

    async def handle_add_gold(self, target_id: str, args: str) -> str:
        """增加灵石"""
        ok, msg, player = await self._get_target(target_id)
        if not ok:
            return msg
        amount = self._parse_int(args)
        if amount is None or amount <= 0:
            return "用法：GM加灵石 <目标> <数量>"
        player.gold += amount
        await self.db.update_player(player)
        return f"✅ 已为【{player.user_name or player.user_id}】增加 {amount:,} 灵石，当前：{player.gold:,}"

    async def handle_sub_gold(self, target_id: str, args: str) -> str:
        """扣除灵石"""
        ok, msg, player = await self._get_target(target_id)
        if not ok:
            return msg
        amount = self._parse_int(args)
        if amount is None or amount <= 0:
            return "用法：GM扣灵石 <目标> <数量>"
        player.gold -= amount
        if player.gold < 0:
            player.gold = 0
        await self.db.update_player(player)
        return f"✅ 已为【{player.user_name or player.user_id}】扣除 {amount:,} 灵石，当前：{player.gold:,}"

    async def handle_add_exp(self, target_id: str, args: str) -> str:
        """增加修为"""
        ok, msg, player = await self._get_target(target_id)
        if not ok:
            return msg
        amount = self._parse_int(args)
        if amount is None or amount <= 0:
            return "用法：GM加修为 <目标> <数量>"
        player.experience += amount
        await self.db.update_player(player)
        return f"✅ 已为【{player.user_name or player.user_id}】增加 {amount:,} 修为，当前：{player.experience:,}"

    async def handle_set_level(self, target_id: str, args: str) -> str:
        """设置境界等级"""
        ok, msg, player = await self._get_target(target_id)
        if not ok:
            return msg
        level = self._parse_int(args)
        if level is None or level < 0:
            return "用法：GM设置境界 <目标> <等级数字>"
        player.level_index = level
        await self.db.update_player(player)
        return f"✅ 已将【{player.user_name or player.user_id}】境界设置为 {level}"

    async def handle_add_item(self, target_id: str, args: str) -> str:
        """添加物品到储物戒"""
        ok, msg, player = await self._get_target(target_id)
        if not ok:
            return msg
        item_name, count = self._parse_item_args(args)
        if not item_name:
            return "用法：GM加物品 <目标> <物品名> [数量]"
        items = player.get_storage_ring_items()
        items[item_name] = items.get(item_name, 0) + count
        player.set_storage_ring_items(items)
        await self.db.update_player(player)
        return f"✅ 已为【{player.user_name or player.user_id}】添加 {item_name} x{count}，当前：{items[item_name]}个"

    async def handle_sub_item(self, target_id: str, args: str) -> str:
        """从储物戒移除物品"""
        ok, msg, player = await self._get_target(target_id)
        if not ok:
            return msg
        item_name, count = self._parse_item_args(args)
        if not item_name:
            return "用法：GM扣物品 <目标> <物品名> [数量]"
        items = player.get_storage_ring_items()
        current = items.get(item_name, 0)
        if current < count:
            return f"❌ 该玩家只有 {item_name} x{current}，不足以扣除 {count}"
        if current == count:
            del items[item_name]
        else:
            items[item_name] = current - count
        player.set_storage_ring_items(items)
        await self.db.update_player(player)
        return f"✅ 已为【{player.user_name or player.user_id}】扣除 {item_name} x{count}，当前：{items.get(item_name, 0)}个"

    async def handle_add_pill(self, target_id: str, args: str) -> str:
        """添加丹药"""
        ok, msg, player = await self._get_target(target_id)
        if not ok:
            return msg
        pill_name, count = self._parse_item_args(args)
        if not pill_name:
            return "用法：GM加丹药 <目标> <丹药名> [数量]"
        inventory = player.get_pills_inventory()
        inventory[pill_name] = inventory.get(pill_name, 0) + count
        player.set_pills_inventory(inventory)
        await self.db.update_player(player)
        return f"✅ 已为【{player.user_name or player.user_id}】添加 {pill_name} x{count}，当前：{inventory[pill_name]}个"

    async def handle_sub_pill(self, target_id: str, args: str) -> str:
        """移除丹药"""
        ok, msg, player = await self._get_target(target_id)
        if not ok:
            return msg
        pill_name, count = self._parse_item_args(args)
        if not pill_name:
            return "用法：GM扣丹药 <目标> <丹药名> [数量]"
        inventory = player.get_pills_inventory()
        current = inventory.get(pill_name, 0)
        if current < count:
            return f"❌ 该玩家只有 {pill_name} x{current}，不足以扣除 {count}"
        if current == count:
            del inventory[pill_name]
        else:
            inventory[pill_name] = current - count
        player.set_pills_inventory(inventory)
        await self.db.update_player(player)
        return f"✅ 已为【{player.user_name or player.user_id}】扣除 {pill_name} x{count}，当前：{inventory.get(pill_name, 0)}个"

    async def handle_view_player(self, target_id: str) -> str:
        """查看玩家信息"""
        ok, msg, player = await self._get_target(target_id)
        if not ok:
            return msg
        items = player.get_storage_ring_items()
        pills = player.get_pills_inventory()
        item_count = sum(items.values())
        pill_count = sum(pills.values())

        return (
            f"👤 玩家信息\n"
            f"━━━━━━━━━━━━━━━\n"
            f"ID：{player.user_id}\n"
            f"昵称：{player.user_name or '无'}\n"
            f"境界等级：{player.level_index}\n"
            f"修为：{player.experience:,}\n"
            f"灵石：{player.gold:,}\n"
            f"寿命：{player.lifespan}\n"
            f"修炼路线：{player.cultivation_type}\n"
            f"储物戒：{player.storage_ring}（{item_count}件物品）\n"
            f"丹药：{pill_count}种\n"
            f"武器：{player.weapon or '无'}\n"
            f"防具：{player.armor or '无'}"
        )

    # ===== 补偿系统 =====

    def _parse_compensation_items(self, args: str) -> dict:
        """解析补偿物品参数，格式：'物品A 数量|物品B 数量|物品C'

        Returns:
            {"物品A": 数量, "物品B": 数量, "物品C": 1}
            解析失败返回空字典
        """
        args = args.strip()
        if not args:
            return {}
        items = {}
        for part in args.split("|"):
            part = part.strip()
            if not part:
                continue
            m = re.match(r'^(.+?)\s+(\d+)\s*$', part, re.DOTALL)
            if m:
                name = m.group(1).strip()
                count = int(m.group(2))
                if name and count > 0:
                    items[name] = items.get(name, 0) + count
            else:
                name = part.strip()
                if name:
                    items[name] = items.get(name, 0) + 1
        return items

    async def handle_create_compensation(self, args: str) -> str:
        """GM创建全服补偿包"""
        items = self._parse_compensation_items(args)
        if not items:
            return "用法：GM补偿 <物品名 数量|物品名 数量>\n示例：GM补偿 灵草 10|炼气丹 5|精铁"
        import json
        items_json = json.dumps(items, ensure_ascii=False)
        comp_id = await self.db.ext.create_compensation(items_json)
        # 清理旧补偿
        await self.db.ext.delete_old_compensations(comp_id)
        # 构建确认消息
        lines = [f"🎁 已创建全服补偿包（ID: {comp_id}）"]
        lines.append("━━━━━━━━━━━━━━━")
        for name, count in items.items():
            lines.append(f"  {name} ×{count}")
        lines.append("━━━━━━━━━━━━━━━")
        lines.append("玩家可使用【/补偿】领取")
        return "\n".join(lines)

    async def handle_claim_compensation(self, user_id: str) -> str:
        """玩家领取补偿"""
        # 查询活跃补偿
        comp = await self.db.ext.get_active_compensation()
        if not comp:
            return "📭 当前没有可领取的补偿。"
        # 检查是否已领取
        if await self.db.ext.has_claimed(user_id, comp["id"]):
            return "❌ 你已经领取过本次补偿了，请等待下一次补偿。"
        # 获取玩家
        player = await self.db.get_player_by_id(user_id)
        if not player:
            return "❌ 请先创建角色后再领取补偿。"
        # 记录领取（原子操作防并发）
        claimed = await self.db.ext.claim_compensation(user_id, comp["id"])
        if not claimed:
            return "❌ 你已经领取过本次补偿了，请等待下一次补偿。"
        # 发放物品
        import json
        items = json.loads(comp["items"])
        storage = player.get_storage_ring_items()
        pills_inv = player.get_pills_inventory()
        received = []
        for name, count in items.items():
            if self.config_manager and self.config_manager.is_pill(name):
                pills_inv[name] = pills_inv.get(name, 0) + count
            else:
                storage[name] = storage.get(name, 0) + count
            received.append(f"  {name} ×{count}")
        player.set_storage_ring_items(storage)
        player.set_pills_inventory(pills_inv)
        await self.db.update_player(player)
        # 返回结果
        lines = ["🎁 补偿领取成功！"]
        lines.append("━━━━━━━━━━━━━━━")
        lines.extend(received)
        lines.append("━━━━━━━━━━━━━━━")
        return "\n".join(lines)

    def _parse_int(self, text: str) -> int:
        """解析整数"""
        text = text.strip()
        m = re.search(r'(\d+)', text)
        return int(m.group(1)) if m else None

    def _parse_item_args(self, text: str) -> Tuple[str, int]:
        """解析物品名+数量参数，返回 (name, count)"""
        text = text.strip()
        if not text:
            return "", 1
        # 从末尾提取数量：匹配 "物品名 数量" 格式
        m = re.search(r'^(.+?)\s+(\d+)\s*$', text, re.DOTALL)
        if m:
            return m.group(1).strip(), int(m.group(2))
        # 只有物品名，默认数量1
        return text, 1
