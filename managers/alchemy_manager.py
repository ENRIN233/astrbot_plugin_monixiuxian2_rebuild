# managers/alchemy_manager.py
"""
炼丹系统管理器 — nonebot 迁移版（寒热调和 + 主药/药引/辅药匹配）
"""
import random
from typing import Tuple, List, Dict, Optional, TYPE_CHECKING
from ..data.data_manager import DataBase
from ..models import Player

if TYPE_CHECKING:
    from ..config_manager import ConfigManager
    from ..core import StorageRingManager
    from .spirit_farm_manager import SpiritFarmManager


class AlchemyManager:
    """炼丹系统管理器（nonebot 寒热调和版）"""

    def __init__(
        self,
        db: DataBase,
        config_manager: "ConfigManager" = None,
        storage_ring_manager: "StorageRingManager" = None,
        spirit_farm_manager: "SpiritFarmManager" = None,
        activity_tracker=None,
    ):
        self.db = db
        self.config_manager = config_manager
        self.storage_ring_manager = storage_ring_manager
        self.spirit_farm_manager = spirit_farm_manager
        self.activity_tracker = activity_tracker

    # ── 药材/配方数据 ──

    def _get_herbs_data(self) -> Dict[str, dict]:
        """获取药材数据（key=药材ID）"""
        if self.config_manager:
            return self.config_manager.herbs_data
        return {}

    def _get_recipes_data(self) -> Dict[str, dict]:
        """获取炼丹配方数据（key=配方ID）"""
        if self.config_manager and hasattr(self.config_manager, "alchemy_recipes"):
            return self.config_manager.alchemy_recipes
        return {}

    def _get_herb_by_name(self, name: str) -> Optional[Tuple[str, dict]]:
        """根据药材名查找药材ID和数据"""
        for hid, h in self._get_herbs_data().items():
            if h.get("name") == name:
                return hid, h
        return None

    # ── 寒热调和检查 ──

    @staticmethod
    def check_harmony(main_herb: dict, catalyst_herb: dict, main_count: int, catalyst_count: int) -> bool:
        """寒热调和检查（nonebot tiaohe 函数）

        主药.h_a_c.type × 主药.h_a_c.power × count +
        药引.h_a_c.type × 药引.h_a_c.power × count
        的绝对值必须 == 0
        """
        main_hac = main_herb.get("主药", {}).get("h_a_c", {})
        cat_hac = catalyst_herb.get("药引", {}).get("h_a_c", {})

        main_val = main_hac.get("type", 0) * main_hac.get("power", 0) * main_count
        cat_val = cat_hac.get("type", 0) * cat_hac.get("power", 0) * catalyst_count

        return abs(main_val + cat_val) == 0

    # ── 配方匹配 ──

    @staticmethod
    def match_recipe(main_herb: dict, aux_herb: dict, main_count: int, aux_count: int, recipes: Dict[str, dict]) -> Optional[dict]:
        """匹配最佳配方

        构建 elixir_config dict，与所有配方比较，返回最高等级匹配。
        """
        main_type = str(main_herb.get("主药", {}).get("type", 0))
        main_power = main_herb.get("主药", {}).get("power", 0) * main_count
        aux_type = str(aux_herb.get("辅药", {}).get("type", 0))
        aux_power = aux_herb.get("辅药", {}).get("power", 0) * aux_count

        player_config = {main_type: main_power, aux_type: aux_power}

        best_recipe = None
        best_total = 0

        for rid, recipe in recipes.items():
            req = recipe.get("elixir_config", {})
            if not req:
                continue

            # key 必须完全匹配
            if set(req.keys()) != set(player_config.keys()):
                continue

            # 每个 key 的 power 必须 >= 要求
            match = True
            for k, v in req.items():
                if player_config.get(k, 0) < v:
                    match = False
                    break

            if match:
                total = sum(req.values())
                if total > best_total:
                    best_total = total
                    best_recipe = recipe

        return best_recipe

    # ── 核心功能 ──

    async def find_recipes(self, player: Player) -> Tuple[bool, str]:
        """扫描储物戒中的药材，显示可用配方"""
        if not self.storage_ring_manager:
            return False, "❌ 储物戒系统未初始化"

        herbs_data = self._get_herbs_data()
        recipes_data = self._get_recipes_data()

        if not herbs_data:
            return False, "❌ 药材数据未加载"
        if not recipes_data:
            return False, "❌ 炼丹配方数据未加载"

        # 获取储物戒中的药材
        ring_items = player.get_storage_ring_items()
        herb_inventory = {}  # herb_name -> count
        for item_name, count in ring_items.items():
            result = self._get_herb_by_name(item_name)
            if result:
                herb_inventory[item_name] = count

        if not herb_inventory:
            return False, "❌ 储物戒中没有药材！请先 /灵田收取"

        # 转为列表用于组合
        herb_list = list(herb_inventory.items())
        if len(herb_list) > 25:
            random.shuffle(herb_list)
            herb_list = herb_list[:25]

        found_recipes = []
        seen = set()

        # 尝试所有 主药+药引+辅药 组合
        for i_name, i_count in herb_list:
            i_data = self._get_herb_by_name(i_name)
            if not i_data:
                continue
            _, i_herb = i_data

            for o_name, o_count in herb_list:
                if o_name == i_name:
                    continue
                o_data = self._get_herb_by_name(o_name)
                if not o_data:
                    continue
                _, o_herb = o_data

                for p_name, p_count in herb_list:
                    p_data = self._get_herb_by_name(p_name)
                    if not p_data:
                        continue
                    _, p_herb = p_data

                    # 尝试不同用量 (1-11)
                    for i_num in range(1, min(12, i_count + 1)):
                        for o_num in range(1, min(12, o_count + 1)):
                            for p_num in range(1, min(12, p_count + 1)):
                                if i_num + o_num + p_num > 23:
                                    continue

                                # 寒热调和
                                if not self.check_harmony(i_herb, o_herb, i_num, o_num):
                                    continue

                                # 配方匹配
                                recipe = self.match_recipe(i_herb, p_herb, i_num, p_num, recipes_data)
                                if recipe:
                                    key = (recipe.get("name"), i_name, o_name, p_name, i_num, o_num, p_num)
                                    if key not in seen:
                                        seen.add(key)
                                        found_recipes.append({
                                            "recipe": recipe,
                                            "main": (i_name, i_num),
                                            "catalyst": (o_name, o_num),
                                            "auxiliary": (p_name, p_num),
                                        })

        if not found_recipes:
            return False, "❌ 当前药材无法匹配任何配方\n💡 提示：寒热属性需要调和（寒+热或全平性）"

        # 按配方等级排序，取前 10 个
        found_recipes.sort(key=lambda r: sum(r["recipe"].get("elixir_config", {}).values()), reverse=True)
        found_recipes = found_recipes[:10]

        lines = ["⚗️ 可用炼丹配方", "━━━━━━━━━━━━━━━"]
        for idx, r in enumerate(found_recipes, 1):
            recipe = r["recipe"]
            m_name, m_num = r["main"]
            c_name, c_num = r["catalyst"]
            a_name, a_num = r["auxiliary"]
            lines.append(
                f"{idx}. {recipe['name']} — "
                f"主药{m_name}×{m_num} + 药引{c_name}×{c_num} + 辅药{a_name}×{a_num}"
            )
        lines.append("━━━━━━━━━━━━━━━")
        lines.append("💡 使用 /配方 主药XX N 药引YY N 辅药ZZ N")

        return True, "\n".join(lines)

    async def craft(
        self,
        player: Player,
        main_name: str, main_count: int,
        catalyst_name: str, catalyst_count: int,
        aux_name: str, aux_count: int,
    ) -> Tuple[bool, str]:
        """执行炼丹"""
        if not self.storage_ring_manager:
            return False, "❌ 储物戒系统未初始化"

        # 查找药材
        main_data = self._get_herb_by_name(main_name)
        cat_data = self._get_herb_by_name(catalyst_name)
        aux_data = self._get_herb_by_name(aux_name)

        if not main_data:
            return False, f"❌ 未知药材：{main_name}"
        if not cat_data:
            return False, f"❌ 未知药材：{catalyst_name}"
        if not aux_data:
            return False, f"❌ 未知药材：{aux_name}"

        _, main_herb = main_data
        _, cat_herb = cat_data
        _, aux_herb = aux_data

        # 检查数量（先累计同名药材的总需求，防止主药和辅药用同种药材时重复计算）
        ring_items = player.get_storage_ring_items()
        herb_needs = {}
        for name, need in [(main_name, main_count), (catalyst_name, catalyst_count), (aux_name, aux_count)]:
            herb_needs[name] = herb_needs.get(name, 0) + need
        for name, total_need in herb_needs.items():
            if ring_items.get(name, 0) < total_need:
                return False, f"❌ {name} 数量不足（需要 {total_need}，拥有 {ring_items.get(name, 0)}）"

        # 总用量限制
        if main_count + catalyst_count + aux_count > 23:
            return False, "❌ 总用量不能超过 23（单种药材最多 11 个）"

        # 寒热调和
        if not self.check_harmony(main_herb, cat_herb, main_count, catalyst_count):
            return False, "❌ 寒热不调和！主药与药引的寒热属性不平衡"

        # 配方匹配
        recipes_data = self._get_recipes_data()
        recipe = self.match_recipe(main_herb, aux_herb, main_count, aux_count, recipes_data)
        if not recipe:
            return False, "❌ 无法匹配任何已知配方"

        # 读取功法炼丹加成
        alchemy_count_bonus = 0
        alchemy_exp_bonus = 0
        if player.main_technique and self.config_manager:
            tech_data = self.config_manager.items_data.get(player.main_technique)
            if tech_data:
                alchemy_count_bonus = int(tech_data.get("alchemy_count_bonus", 0))
                alchemy_exp_bonus = int(tech_data.get("alchemy_exp_bonus", 0))

        # 读取灵田控火等级
        fire_control = 0
        if self.spirit_farm_manager:
            farm = await self.spirit_farm_manager.get_user_farm(player.user_id)
            if farm:
                fire_control = farm.get("fire_control", 0)

        # 读取炼丹炉加成
        furnace_buff = 0
        if player.furnace and self.config_manager:
            for fid, fdata in self.config_manager.furnaces_data.items():
                if fdata.get("name") == player.furnace:
                    furnace_buff = int(fdata.get("buff", 0))
                    break

        # 计算出丹数：基础1 + 控火 + 功法加成 + 炉子加成
        pill_count = 1 + fire_control + alchemy_count_bonus + furnace_buff
        pill_count = max(1, pill_count)

        # 消耗药材（检查返回值，防止同种药材重复消耗时数据不一致）
        for name, need in [(main_name, main_count), (catalyst_name, catalyst_count), (aux_name, aux_count)]:
            if need > 0:
                success, msg = await self.storage_ring_manager.remove_item(player, name, need, silent=True)
                if not success:
                    return False, f"❌ {name} 消耗失败：{msg}"

        # 产出丹药 → 存入丹药背包（pills_inventory）
        pill_name = recipe["name"]
        inv = player.get_pills_inventory()
        inv[pill_name] = inv.get(pill_name, 0) + pill_count
        player.set_pills_inventory(inv)
        await self.db.update_player(player)

        # 增加炼丹经验
        mix_exp = recipe.get("mix_exp", 10) + alchemy_exp_bonus
        if self.spirit_farm_manager:
            await self.spirit_farm_manager.add_alchemy_exp(player.user_id, mix_exp * pill_count)

        # 活跃度追踪
        if self.activity_tracker:
            try:
                await self.activity_tracker.track_alchemy(player)
            except Exception:
                pass

        lines = [
            f"⚗️ 炼丹成功！",
            "━━━━━━━━━━━━━━━",
            f"配方：{pill_name}",
            f"材料：{main_name}×{main_count} + {catalyst_name}×{catalyst_count} + {aux_name}×{aux_count}",
            f"产出：{pill_name} ×{pill_count}",
            f"获得炼丹经验：+{mix_exp * pill_count}",
        ]
        if furnace_buff > 0:
            lines.append(f"（炼丹炉加成 +{furnace_buff}）")
        if alchemy_count_bonus > 0:
            lines.append(f"（功法出丹加成 +{alchemy_count_bonus}）")
        if fire_control > 0:
            lines.append(f"（控火加成 +{fire_control}）")
        lines.append("━━━━━━━━━━━━━━━")

        return True, "\n".join(lines)
