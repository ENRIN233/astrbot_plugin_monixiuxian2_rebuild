# handlers/forging_handler.py
"""锻造系统处理器 — 锻造、配方信息、锻造信息、分解等命令"""
from ..data.data_manager import DataBase
from ..core.forging_manager import ForgingManager
from ..config_manager import ConfigManager
from ..models import Player
from .utils import player_required

__all__ = ["ForgingHandler"]


class ForgingHandler:
    """锻造系统处理器"""

    def __init__(self, db: DataBase, forging_mgr: ForgingManager, config_manager: ConfigManager):
        self.db = db
        self.forging_mgr = forging_mgr
        self.config_manager = config_manager
        self.db_extended = getattr(forging_mgr, "db_extended", None)

    @player_required
    async def handle_forge(self, player: Player, event, recipe_name: str = "", quantity: int = 1):
        """执行锻造

        格式：/锻造 <配方名> [数量]
        """
        if not recipe_name:
            yield event.plain_result(
                "❌ 请指定配方名称！\n"
                "格式：/锻造 <配方名> [数量]\n"
                "使用 /锻造配方 查看可用配方"
            )
            return

        if quantity < 1:
            quantity = 1
        if quantity > 10:
            quantity = 10

        # 查找配方（支持按名称或ID匹配）
        recipe_id = None
        for rid, recipe in self.forging_mgr._get_recipes().items():
            if recipe.get("name") == recipe_name or rid == recipe_name:
                recipe_id = rid
                break

        if not recipe_id:
            yield event.plain_result(
                f"❌ 未知配方：{recipe_name}\n"
                "使用 /锻造配方 查看可用配方"
            )
            return

        success, msg = await self.forging_mgr.forge(player, recipe_id, quantity)
        yield event.plain_result(msg)

    @player_required
    async def handle_forge_list(self, player: Player, event):
        """查看可锻造的配方列表"""
        recipes = await self.forging_mgr.get_forgeable_recipes(player)
        if not recipes:
            yield event.plain_result("暂无锻造配方数据")
            return

        lines = ["🔨 锻造配方一览", "━━━━━━━━━━━━━━━"]
        for r in recipes:
            status = "✅" if r["unlocked"] else "🔒"
            ings = " + ".join(f"{n}×{c}" for n, c in r["ingredients"].items())
            lines.append(
                f"{status} {r['name']}（{r['output_template']}）\n"
                f"   材料：{ings}\n"
                f"   需求锻造等级：Lv.{r['rank_required']}"
            )
        lines.append("━━━━━━━━━━━━━━━")
        lines.append("💡 使用 /锻造 <配方名> [数量] 进行锻造")

        yield event.plain_result("\n".join(lines))

    @player_required
    async def handle_forge_info(self, player: Player, event):
        """查看锻造等级和信息"""
        next_level_exp = player.forging_level * 30
        lines = [
            "🔨 锻造信息",
            "━━━━━━━━━━━━━━━",
            f"锻造等级：Lv.{player.forging_level}",
            f"锻造经验：{player.forging_exp} / {next_level_exp}",
            "━━━━━━━━━━━━━━━",
            "品质概率（当前）：",
        ]
        # 显示当前等级的品质概率
        qrates = self.forging_mgr._get_quality_rates_for_level(player.forging_level)
        for q, r in qrates.items():
            lines.append(f"  {q}：{r*100:.0f}%")
        lines.append("━━━━━━━━━━━━━━━")
        lines.append("💡 使用 /锻造配方 查看可锻造的配方")

        yield event.plain_result("\n".join(lines))

    @player_required
    async def handle_decompose(self, player: Player, event, instance_id: str = ""):
        """分解武器/防具实例回收材料

        格式：/分解 <序号/ID>
        """
        if not instance_id:
            yield event.plain_result(
                "❌ 请指定要分解的武器序号或ID\n"
                "格式：/分解 <序号/ID>\n"
                "使用 /武器列表 查看拥有的武器实例"
            )
            return

        # 序号匹配
        resolved = await self._resolve_index(player, instance_id)
        if resolved is None and instance_id.isdigit():
            yield event.plain_result(
                f"❌ 序号超出范围，使用 /武器列表 查看可用序号"
            )
            return

        success, msg = await self.forging_mgr.decompose(player, resolved or instance_id)
        yield event.plain_result(msg)

    @player_required
    async def handle_fuse(self, player: Player, event, arg1: str = "", arg2: str = ""):
        """融合原罪+无罪→天罪

        格式：/融合 <序号1/ID1> <序号2/ID2>
        """
        if not arg1 or not arg2:
            yield event.plain_result(
                "❌ 请指定两把武器的序号或ID\n"
                "格式：/融合 <序号1/ID1> <序号2/ID2>\n"
                "需要一把「原罪（残缺）」和一把「无罪（残缺）」"
            )
            return

        id1 = await self._resolve_index(player, arg1) or arg1
        id2 = await self._resolve_index(player, arg2) or arg2

        success, msg = await self.forging_mgr.fuse(player, id1, id2)
        yield event.plain_result(msg)

    async def _resolve_index(self, player: Player, raw: str) -> str | None:
        """将数字序号解析为 instance_id"""
        if raw.isdigit() and self.db_extended:
            idx = int(raw) - 1
            instances = await self.db_extended.get_player_weapon_instances(player.user_id)
            if 0 <= idx < len(instances):
                return instances[idx]["instance_id"]
        return None
