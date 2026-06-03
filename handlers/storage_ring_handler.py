# handlers/storage_ring_handler.py

import time
from astrbot.api.event import AstrMessageEvent
from astrbot.api.all import At, Plain
from ..data import DataBase
from ..core import StorageRingManager
from ..config_manager import ConfigManager
from ..models import Player
from .utils import player_required

CMD_STORAGE_RING = "储物戒"
CMD_STORE_ITEM = "存入"
CMD_RETRIEVE_ITEM = "取出"
CMD_UPGRADE_RING = "更换储物戒"
CMD_DISCARD_ITEM = "丢弃"
CMD_GIFT_ITEM = "赠予"
CMD_ACCEPT_GIFT = "接收"
CMD_REJECT_GIFT = "拒绝"
CMD_STORE_ALL = "存入所有"
CMD_RETRIEVE_ALL = "取出所有"
CMD_SEARCH_ITEM = "搜索物品"
CMD_VIEW_CATEGORY = "查看分类"

# 物品分类定义
ITEM_CATEGORIES = {
    "材料": ["灵草", "精铁", "玄铁", "星辰石", "灵石碎片", "灵兽毛皮", "灵兽内丹", 
             "妖兽精血", "功法残页", "秘境精华", "天材地宝", "混沌精华", "神兽之骨", 
             "远古秘籍", "仙器碎片"],
    "装备": ["武器", "防具", "法器"],
    "功法": ["心法", "技能"],
    "其他": []
}

__all__ = ["StorageRingHandler"]


class StorageRingHandler:
    """储物戒系统处理器"""

    def __init__(self, db: DataBase, config_manager: ConfigManager, activity_tracker=None):
        self.db = db
        self.config_manager = config_manager
        self.storage_ring_manager = StorageRingManager(db, config_manager)
        self.activity_tracker = activity_tracker

    @player_required
    async def handle_storage_ring(self, player: Player, event: AstrMessageEvent):
        """显示储物戒信息（含丹药、临时效果、回生丹状态）"""
        display_name = event.get_sender_name()

        # 获取储物戒信息
        ring_info = self.storage_ring_manager.get_storage_ring_info(player)

        lines = [
            f"=== {display_name} 的储物戒 ===\n",
            f"【{ring_info['name']}】（{ring_info['rank']}）\n",
            f"{ring_info['description']}\n",
            f"\n容量：{ring_info['used']}/{ring_info['capacity']}格\n",
            f"━━━━━━━━━━━━━━━\n",
        ]

        # 按分类显示存储的物品
        items = ring_info['items']
        if items:
            categorized = self._categorize_items(items)
            for category, cat_items in categorized.items():
                if cat_items:
                    lines.append(f"【{category}】\n")
                    for item_name, count in cat_items:
                        if count > 1:
                            lines.append(f"  · {item_name}×{count}\n")
                        else:
                            lines.append(f"  · {item_name}\n")
        else:
            lines.append("【存储物品】空\n")

        # 丹药背包
        pills_inv = player.get_pills_inventory()
        if pills_inv:
            lines.append(f"━━━━━━━━━━━━━━━\n")
            lines.append("【丹药】\n")
            for pill_name, count in pills_inv.items():
                pill_data = self._get_pill_data(pill_name)
                rank = pill_data.get("rank", "") if pill_data else ""
                prefix = f"[{rank}] " if rank else ""
                extra = ""
                if pill_data and pill_data.get("effect_type") == "permanent":
                    usage = player.get_permanent_pill_usage()
                    used = usage.get(pill_name, 0)
                    extra = f" (已服用 {used}/2)"
                if count > 1:
                    lines.append(f"  · {prefix}{pill_name}×{count}{extra}\n")
                else:
                    lines.append(f"  · {prefix}{pill_name}{extra}\n")

            # 临时效果
            active_effects = player.get_active_pill_effects()
            now_ts = int(time.time())
            shown_effects = []
            for effect in active_effects:
                expiry_time = effect.get("expiry_time", 0)
                if expiry_time > 0 and now_ts >= expiry_time:
                    continue
                pill_name_eff = effect.get("pill_name", "未知丹药")
                remaining_seconds = expiry_time - now_ts if expiry_time > 0 else 0
                if remaining_seconds > 0:
                    remaining_minutes = remaining_seconds // 60
                    hours = remaining_minutes // 60
                    minutes = remaining_minutes % 60
                    time_str = f"{hours}小时{minutes}分钟" if hours > 0 else f"{minutes}分钟"
                    shown_effects.append(f"  🌟 {pill_name_eff} (剩余: {time_str})")
            if shown_effects:
                lines.append("\n【临时效果】\n")
                for e in shown_effects:
                    lines.append(e + "\n")

            # 回生丹
            if player.has_resurrection_pill:
                lines.append(f"\n🛡️ 当前拥有【{player.has_resurrection_pill}】效果（可抵消一次死亡）\n")

        # 空间警告
        warning = self.storage_ring_manager.get_space_warning(player)
        if warning:
            lines.append(f"\n{warning}\n")

        yield event.plain_result("".join(lines))

    def _get_pill_data(self, pill_name: str) -> dict:
        """从config_manager获取丹药配置"""
        pill = self.config_manager.pills_data.get(pill_name)
        if pill:
            return pill
        pill = self.config_manager.exp_pills_data.get(pill_name)
        if pill:
            return pill
        pill = self.config_manager.utility_pills_data.get(pill_name)
        if pill:
            return pill
        item = self.config_manager.items_data.get(pill_name)
        if item and item.get("type") == "丹药":
            return item
        return {}

    @player_required
    async def handle_store_item(self, player: Player, event: AstrMessageEvent, args: str):
        """存入物品到储物戒 - 已禁用手动存入"""
        yield event.plain_result(
            "📦 储物戒说明：\n"
            "物品会在以下情况自动存入储物戒：\n"
            "  · 商店购买物品\n"
            "  · 历练/秘境获得物品\n"
            "  · Boss击杀掉落\n"
            "  · 悬赏任务奖励\n"
            "  · 卸下装备\n"
            "\n⚠️ 不支持手动存入物品"
        )

    @player_required
    async def handle_retrieve_item(self, player: Player, event: AstrMessageEvent, args: str):
        """从储物戒取出物品"""
        if not args or args.strip() == "":
            yield event.plain_result(
                f"请指定要取出的物品\n"
                f"用法：{CMD_RETRIEVE_ITEM} 物品名 [数量]\n"
                f"示例：{CMD_RETRIEVE_ITEM} 精铁 5"
            )
            return

        args = args.strip()
        parts = args.rsplit(" ", 1)

        # 解析物品名和数量
        if len(parts) == 2 and parts[1].isdigit():
            item_name = parts[0]
            count = int(parts[1])
        else:
            item_name = args
            count = 1

        if count <= 0:
            yield event.plain_result("数量必须大于0")
            return

        # 取出物品
        success, message = await self.storage_ring_manager.retrieve_item(player, item_name, count)

        if success:
            yield event.plain_result(f"✅ {message}")
        else:
            yield event.plain_result(f"❌ {message}")

    @player_required
    async def handle_discard_item(self, player: Player, event: AstrMessageEvent, args: str):
        """丢弃储物戒中的物品"""
        if not args or args.strip() == "":
            yield event.plain_result(
                f"请指定要丢弃的物品\n"
                f"用法：{CMD_DISCARD_ITEM} 物品名 [数量]\n"
                f"示例：{CMD_DISCARD_ITEM} 精铁 5\n"
                f"⚠️ 丢弃的物品将永久销毁！"
            )
            return

        args = args.strip()
        parts = args.rsplit(" ", 1)

        # 解析物品名和数量
        if len(parts) == 2 and parts[1].isdigit():
            item_name = parts[0]
            count = int(parts[1])
        else:
            item_name = args
            count = 1

        if count <= 0:
            yield event.plain_result("数量必须大于0")
            return

        # 丢弃物品
        success, message = await self.storage_ring_manager.discard_item(player, item_name, count)

        if success:
            yield event.plain_result(f"🗑️ {message}")
        else:
            yield event.plain_result(f"❌ {message}")

    @player_required
    async def handle_gift_item(self, player: Player, event: AstrMessageEvent, args: str):
        """赠予物品给其他玩家"""
        target_id = None
        item_name = None
        count = 1

        # 从消息链中提取 At 组件和 Plain 文本
        text_parts = []
        message_chain = event.message_obj.message if hasattr(event, 'message_obj') and event.message_obj else []
        
        for comp in message_chain:
            if isinstance(comp, At):
                # 兼容多种At属性名
                if target_id is None:
                    if hasattr(comp, 'qq'):
                        target_id = str(comp.qq)
                    elif hasattr(comp, 'target'):
                        target_id = str(comp.target)
                    elif hasattr(comp, 'uin'):
                        target_id = str(comp.uin)
            elif isinstance(comp, Plain):
                text_parts.append(comp.text)

        # 合并文本内容并移除命令前缀
        text_content = "".join(text_parts).strip()
        for prefix in ["#赠予", "/赠予", "赠予"]:
            if text_content.startswith(prefix):
                text_content = text_content[len(prefix):].strip()
                break
        
        # 如果没有从At组件获取到target_id，尝试从文本解析纯数字QQ号
        if not target_id and text_content:
            parts = text_content.split(None, 1)
            if len(parts) >= 1:
                potential_id = parts[0].lstrip('@')
                if potential_id.isdigit() and len(potential_id) >= 5:
                    target_id = potential_id
                    text_content = parts[1].strip() if len(parts) > 1 else ""

        # 解析物品名和数量
        if text_content:
            parts = text_content.rsplit(" ", 1)
            if len(parts) == 2 and parts[1].isdigit():
                item_name = parts[0].strip()
                count = int(parts[1])
            else:
                item_name = text_content.strip()

        # 验证必要参数
        if not target_id:
            yield event.plain_result(
                f"请指定赠予对象\n"
                f"用法：{CMD_GIFT_ITEM} @某人 物品名 [数量]\n"
                f"或：{CMD_GIFT_ITEM} QQ号 物品名 [数量]\n"
                f"示例：{CMD_GIFT_ITEM} 123456789 精铁 5"
            )
            return

        if not item_name:
            yield event.plain_result("请指定要赠予的物品名称")
            return

        if count <= 0:
            yield event.plain_result("数量必须大于0")
            return

        # 检查物品是否在储物戒中
        if not self.storage_ring_manager.has_item(player, item_name, count):
            current = self.storage_ring_manager.get_item_count(player, item_name)
            if current == 0:
                yield event.plain_result(f"储物戒中没有【{item_name}】")
            else:
                yield event.plain_result(f"储物戒中【{item_name}】数量不足（当前：{current}个）")
            return

        target_player = await self.db.get_player_by_id(target_id)
        if not target_player:
            yield event.plain_result(f"目标玩家（QQ:{target_id}）尚未开始修仙")
            return

        if target_id == player.user_id:
            yield event.plain_result("不能赠予物品给自己")
            return

        # 先从储物戒中取出物品
        success, _ = await self.storage_ring_manager.retrieve_item(player, item_name, count)
        if not success:
            yield event.plain_result("赠予失败：无法取出物品")
            return

        # 存储待处理的赠予请求到数据库
        sender_name = event.get_sender_name()
        await self.db.ext.create_pending_gift(
            receiver_id=target_id,
            sender_id=player.user_id,
            sender_name=sender_name,
            item_name=item_name,
            count=count,
            expires_hours=24  # 24小时后过期
        )

        yield event.plain_result(
            f"📦 赠予请求已发送！\n"
            f"【{item_name}】x{count} → @{target_id}\n"
            f"等待对方确认...（24小时内有效）\n"
            f"对方可使用 {CMD_ACCEPT_GIFT} 接收或 {CMD_REJECT_GIFT} 拒绝"
        )

    @player_required
    async def handle_accept_gift(self, player: Player, event: AstrMessageEvent):
        """接收赠予的物品"""
        user_id = player.user_id

        # 从数据库获取待处理的赠予请求
        gift = await self.db.ext.get_pending_gift(user_id)
        if not gift:
            yield event.plain_result("你没有待接收的赠予物品")
            return

        item_name = gift["item_name"]
        count = gift["count"]
        sender_name = gift["sender_name"]
        gift_id = gift["id"]

        # 尝试存入接收者的储物戒
        success, message = await self.storage_ring_manager.store_item(player, item_name, count)

        if success:
            # 删除数据库中的赠予请求
            await self.db.ext.delete_pending_gift(gift_id)
            yield event.plain_result(
                f"✅ 已接收来自【{sender_name}】的赠予！\n"
                f"获得：【{item_name}】x{count}"
            )
        else:
            # 存入失败，物品返还给发送者
            sender_id = gift["sender_id"]
            sender_player = await self.db.get_player_by_id(sender_id)
            if sender_player:
                await self.storage_ring_manager.store_item(sender_player, item_name, count, silent=True)

            # 删除数据库中的赠予请求
            await self.db.ext.delete_pending_gift(gift_id)
            yield event.plain_result(
                f"❌ 接收失败：{message}\n"
                f"物品已返还给【{sender_name}】"
            )

    @player_required
    async def handle_reject_gift(self, player: Player, event: AstrMessageEvent):
        """拒绝赠予的物品"""
        user_id = player.user_id

        # 从数据库获取待处理的赠予请求
        gift = await self.db.ext.get_pending_gift(user_id)
        if not gift:
            yield event.plain_result("你没有待处理的赠予请求")
            return

        item_name = gift["item_name"]
        count = gift["count"]
        sender_id = gift["sender_id"]
        sender_name = gift["sender_name"]
        gift_id = gift["id"]

        # 物品返还给发送者
        sender_player = await self.db.get_player_by_id(sender_id)
        if sender_player:
            await self.storage_ring_manager.store_item(sender_player, item_name, count, silent=True)

        # 删除数据库中的赠予请求
        await self.db.ext.delete_pending_gift(gift_id)
        yield event.plain_result(
            f"已拒绝来自【{sender_name}】的赠予\n"
            f"【{item_name}】x{count} 已返还"
        )

    @player_required
    async def handle_upgrade_ring(self, player: Player, event: AstrMessageEvent, ring_name: str):
        """升级/更换储物戒"""
        if not ring_name or ring_name.strip() == "":
            # 显示可用的储物戒列表
            rings = self.storage_ring_manager.get_all_storage_rings()
            current_capacity = self.storage_ring_manager.get_ring_capacity(player.storage_ring)

            lines = [
                f"=== 储物戒列表 ===\n",
                f"当前：【{player.storage_ring}】({current_capacity}格)\n",
                f"━━━━━━━━━━━━━━━\n",
            ]

            for ring in rings:
                # 标记当前装备
                if ring["name"] == player.storage_ring:
                    marker = "✓ "
                elif ring["capacity"] <= current_capacity:
                    marker = "✗ "  # 容量不高于当前的
                else:
                    marker = "  "

                level_name = self.storage_ring_manager._format_required_level(ring["required_level_index"])
                lines.append(
                    f"{marker}【{ring['name']}】({ring['rank']})\n"
                    f"    容量：{ring['capacity']}格 | 需求：{level_name}\n"
                )

            lines.append(f"\n用法：{CMD_UPGRADE_RING} 储物戒名")
            lines.append("\n注：储物戒只能升级，不能卸下")

            yield event.plain_result("".join(lines))
            return

        ring_name = ring_name.strip()

        # 检查是否为储物戒类型
        ring_config = self.storage_ring_manager.get_storage_ring_config(ring_name)
        if not ring_config:
            yield event.plain_result(f"未找到储物戒：{ring_name}")
            return

        # 升级储物戒
        success, message = await self.storage_ring_manager.upgrade_ring(player, ring_name)

        if success:
            yield event.plain_result(f"✅ {message}")
        else:
            yield event.plain_result(f"❌ {message}")

    def _categorize_items(self, items: dict) -> dict:
        """将物品按分类整理"""
        result = {cat: [] for cat in ITEM_CATEGORIES.keys()}
        
        for item_name, count in items.items():
            categorized = False
            for category, keywords in ITEM_CATEGORIES.items():
                if category == "其他":
                    continue
                # 检查物品名是否包含分类关键词
                for keyword in keywords:
                    if keyword in item_name or item_name in keyword:
                        result[category].append((item_name, count))
                        categorized = True
                        break
                if categorized:
                    break
            
            # 根据配置判断物品类型
            if not categorized:
                item_config = self.config_manager.items_data.get(item_name, {})
                item_type = item_config.get("type", "")
                
                if item_type in ["weapon", "武器"]:
                    result["装备"].append((item_name, count))
                elif item_type in ["armor", "防具"]:
                    result["装备"].append((item_name, count))
                elif item_type in ["technique", "功法", "main_technique"]:
                    result["功法"].append((item_name, count))
                elif item_type in ["material", "材料"]:
                    result["材料"].append((item_name, count))
                else:
                    result["其他"].append((item_name, count))
        
        # 移除空分类
        return {k: v for k, v in result.items() if v}

    @player_required
    async def handle_search_item(self, player: Player, event: AstrMessageEvent, keyword: str):
        """搜索储物戒中的物品"""
        if not keyword or keyword.strip() == "":
            yield event.plain_result(
                f"请指定搜索关键词\n"
                f"用法：{CMD_SEARCH_ITEM} 关键词\n"
                f"示例：{CMD_SEARCH_ITEM} 灵草"
            )
            return

        keyword = keyword.strip().lower()
        items = player.get_storage_ring_items()
        
        # 模糊搜索
        matched = []
        for item_name, count in items.items():
            if keyword in item_name.lower():
                matched.append((item_name, count))
        
        if not matched:
            yield event.plain_result(f"未找到包含「{keyword}」的物品")
            return
        
        lines = [f"=== 搜索结果：{keyword} ===\n"]
        for item_name, count in matched:
            lines.append(f"  · {item_name}×{count}\n")
        lines.append(f"\n共找到 {len(matched)} 种物品")
        
        yield event.plain_result("".join(lines))

    @player_required
    async def handle_store_all(self, player: Player, event: AstrMessageEvent, category: str = None):
        """批量存入物品（预留接口，实际物品来源需要其他系统配合）"""
        yield event.plain_result(
            f"📦 批量存入功能说明：\n"
            f"当前物品会在以下情况自动存入储物戒：\n"
            f"  · 商店购买物品\n"
            f"  · 历练/秘境获得物品\n"
            f"  · Boss击杀掉落\n"
            f"  · 悬赏任务奖励\n"
            f"  · 卸下装备\n"
            f"\n所有物品获取后会自动存入储物戒"
        )

    @player_required
    async def handle_retrieve_all(self, player: Player, event: AstrMessageEvent, category: str = None):
        """批量取出指定分类的物品"""
        if not category or category.strip() == "":
            yield event.plain_result(
                f"请指定要取出的分类\n"
                f"用法：{CMD_RETRIEVE_ALL} 分类名\n"
                f"可用分类：材料、装备、功法、其他\n"
                f"示例：{CMD_RETRIEVE_ALL} 材料"
            )
            return
        
        category = category.strip()
        if category not in ITEM_CATEGORIES:
            yield event.plain_result(f"未知分类：{category}\n可用分类：材料、装备、功法、其他")
            return
        
        items = player.get_storage_ring_items()
        categorized = self._categorize_items(items)
        cat_items = categorized.get(category, [])
        
        if not cat_items:
            yield event.plain_result(f"储物戒中没有【{category}】类物品")
            return
        
        # 取出所有该分类的物品
        retrieved = []
        failed = []
        for item_name, count in cat_items:
            success, msg = await self.storage_ring_manager.retrieve_item(player, item_name, count)
            if success:
                retrieved.append(f"{item_name}×{count}")
            else:
                failed.append(f"{item_name}：{msg}")
        
        lines = [f"=== 批量取出【{category}】 ===\n"]
        if retrieved:
            lines.append(f"✅ 已取出：\n")
            for item in retrieved:
                lines.append(f"  · {item}\n")
        if failed:
            lines.append(f"\n❌ 失败：\n")
            for item in failed:
                lines.append(f"  · {item}\n")

        yield event.plain_result("".join(lines))

    def _get_item_price(self, item_name: str) -> int:
        """查找物品的市场价格（遍历所有配置源）"""
        for src in [
            self.config_manager.items_data,
            self.config_manager.weapons_data,
            self.config_manager.skills_data,
            self.config_manager.exp_pills_data,
            self.config_manager.utility_pills_data,
            self.config_manager.pills_data,
        ]:
            if src and item_name in src:
                return src[item_name].get("price", 0)
            if src:
                for cfg in src.values():
                    if cfg.get("name") == item_name:
                        return cfg.get("price", 0)
        return 0

    @player_required
    async def handle_alchemy_transmute(self, player: Player, event: AstrMessageEvent,
                                       item_name: str = "", count: int = 1):
        """将储物戒物品按市场价20%转化为灵石"""
        if not item_name or item_name.strip() == "":
            yield event.plain_result(
                "请指定要炼金的物品\n"
                "用法：炼金 物品名 [数量]\n"
                "示例：炼金 灵草 5"
            )
            return

        item_name = item_name.strip()
        if count <= 0:
            count = 1

        # 检查库存
        current_count = self.storage_ring_manager.get_item_count(player, item_name)
        if current_count <= 0:
            yield event.plain_result(f"❌ 储物戒中没有【{item_name}】")
            return
        if count > current_count:
            yield event.plain_result(f"❌ 【{item_name}】库存不足，当前拥有 {current_count} 个")
            return

        # 查找市场价格
        price = self._get_item_price(item_name)
        unit_gold = int(price * 0.2)
        total_gold = unit_gold * count

        # 执行炼金（事务保护）
        await self.db.conn.execute("BEGIN IMMEDIATE")
        try:
            # 重新获取最新玩家数据
            player = await self.db.get_player_by_id(player.user_id)
            current_count = self.storage_ring_manager.get_item_count(player, item_name)
            if count > current_count:
                await self.db.conn.rollback()
                yield event.plain_result(f"❌ 【{item_name}】库存不足")
                return

            # 移除物品
            items = player.get_storage_ring_items()
            remaining = items.get(item_name, 0) - count
            if remaining <= 0:
                del items[item_name]
            else:
                items[item_name] = remaining
            player.set_storage_ring_items(items)

            # 增加灵石
            MAX_VALUE = 2**63 - 1
            player.gold = min(player.gold + total_gold, MAX_VALUE)

            await self.db.update_player(player)
            await self.db.conn.commit()
        except Exception:
            await self.db.conn.rollback()
            raise

        # 活跃度追踪
        if self.activity_tracker:
            try:
                await self.activity_tracker.track_smelt(player)
            except Exception:
                pass

        if total_gold > 0:
            yield event.plain_result(
                f"✅ 炼金成功！\n"
                f"物品：【{item_name}】×{count}\n"
                f"获得灵石：+{total_gold:,}"
            )
        else:
            yield event.plain_result(
                f"✅ 炼金完成\n"
                f"物品：【{item_name}】×{count}\n"
                f"⚠️ 该物品无市场价值，已销毁"
            )
