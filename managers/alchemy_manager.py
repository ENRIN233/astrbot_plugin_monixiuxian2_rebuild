# managers/alchemy_manager.py
"""
炼丹系统管理器 - 处理炼丹、配方等逻辑（简化版）
"""

import random
from typing import Tuple, List, Dict, Optional, TYPE_CHECKING
from ..data.data_manager import DataBase
from ..models import Player
from ..models_extended import UserStatus

if TYPE_CHECKING:
    from ..config_manager import ConfigManager
    from ..core import StorageRingManager


class AlchemyManager:
    """炼丹系统管理器（简化版）"""
    
    def __init__(self, db: DataBase, config_manager: "ConfigManager" = None, storage_ring_manager: "StorageRingManager" = None, activity_tracker=None):
        self.db = db
        self.config_manager = config_manager
        self.storage_ring_manager = storage_ring_manager
        self.activity_tracker = activity_tracker
        self.config = config_manager.alchemy_config if config_manager else {}
        
        raw_recipes = {}
        if config_manager and hasattr(config_manager, 'alchemy_recipes') and config_manager.alchemy_recipes:
            raw_recipes = config_manager.alchemy_recipes
        
        self.recipes = {}
        for recipe in raw_recipes.values():
            if isinstance(recipe, dict) and recipe.get("id"):
                recipe_id = int(recipe["id"])
                self.recipes[recipe_id] = self._normalize_recipe(recipe_id, recipe)
    
    def _normalize_recipe(self, recipe_id: int, recipe: Dict) -> Dict:
        """标准化配方字段，兼容不同格式的配置"""
        name = recipe.get("name", f"丹药{recipe_id}")
        
        desc = recipe.get("desc", None)
        if not desc and self.config_manager:
            pill_config = self._get_pill_config_by_name(name)
            if pill_config:
                desc = self._generate_pill_desc(pill_config)
        if not desc:
            desc = "丹药效果"
        
        return {
            "id": recipe.get("id", recipe_id),
            "name": name,
            "level_required": recipe.get("level_required", recipe.get("level", 0)),
            "materials": recipe.get("materials", recipe.get("cost", {})),
            "success_rate": recipe.get("success_rate", recipe.get("success", 50)),
            "desc": desc
        }
    
    def _generate_pill_desc(self, pill_config: Dict) -> str:
        """根据丹药配置生成描述"""
        rank = pill_config.get("rank", "")
        
        if pill_config.get("exp_gain"):
            return f"增加{pill_config['exp_gain']}修为（{rank}修为丹）"
        
        if pill_config.get("breakthrough_bonus"):
            bonus = int(pill_config["breakthrough_bonus"] * 100)
            return f"提升{bonus}%突破成功率（{rank}破境丹）"
        
        if pill_config.get("description"):
            return pill_config["description"]
        
        effect = pill_config.get("effect", {})
        if effect:
            effects = []
            if effect.get("add_hp"):
                effects.append(f"恢复{effect['add_hp']}气血")
            if effect.get("add_experience"):
                effects.append(f"增加{effect['add_experience']}修为")
            if effect.get("add_breakthrough_bonus"):
                bonus = int(effect["add_breakthrough_bonus"] * 100)
                effects.append(f"提升{bonus}%突破率")
            if effects:
                return f"{'，'.join(effects)}（{rank}）"
        
        return f"{rank}丹药"
    
    def _get_pill_config_by_name(self, name: str) -> Optional[Dict]:
        """根据丹药名称从配置中获取丹药信息"""
        if not self.config_manager:
            return None
        
        if hasattr(self.config_manager, 'exp_pills_data'):
            pill = self.config_manager.exp_pills_data.get(name)
            if pill:
                return pill
        
        if hasattr(self.config_manager, 'utility_pills_data'):
            pill = self.config_manager.utility_pills_data.get(name)
            if pill:
                return pill
        
        if hasattr(self.config_manager, 'pills_data'):
            pill = self.config_manager.pills_data.get(name)
            if pill:
                return pill
        
        if hasattr(self.config_manager, 'items_data'):
            item = self.config_manager.items_data.get(name)
            if item and item.get("type") == "丹药":
                return item
        
        return None
    
    async def get_available_recipes(self, user_id: str) -> Tuple[bool, str]:
        """
        获取可用的丹药配方
        
        Args:
            user_id: 用户ID
            
        Returns:
            (成功标志, 消息)
        """
        player = await self.db.get_player_by_id(user_id)
        if not player:
            return False, "❌ 你还未踏入修仙之路！"
        
        available_recipes = []
        for recipe_id, recipe in self.recipes.items():
            if player.level_index >= recipe.get("level_required", 0):
                available_recipes.append(recipe)
        
        if not available_recipes:
            return False, "❌ 你当前境界无法炼制任何丹药！"
        
        msg = "🔥 丹药配方\n"
        msg += "━━━━━━━━━━━━━━━\n\n"
        
        for recipe in available_recipes:
            materials_str = ", ".join([f"{k}×{v}" for k, v in recipe["materials"].items()])
            msg += f"【{recipe['name']}】(ID:{recipe['id']})\n"
            msg += f"  需求境界：Lv.{recipe['level_required']}\n"
            msg += f"  材料：{materials_str}\n"
            msg += f"  成功率：{recipe['success_rate']}%\n"
            msg += f"  效果：{recipe['desc']}\n\n"
        
        msg += "使用 /炼丹 <丹药ID> 开始炼制"
        
        return True, msg
    
    async def craft_pill(
        self,
        user_id: str,
        pill_id: int
    ) -> Tuple[bool, str, Optional[Dict]]:
        """
        炼制丹药
        
        Args:
            user_id: 用户ID
            pill_id: 丹药ID
            
        Returns:
            (成功标志, 消息, 结果数据)
        """
        # 1. 检查用户
        player = await self.db.get_player_by_id(user_id)
        if not player:
            return False, "❌ 你还未踏入修仙之路！", None
        
        # 2. 检查用户状态（状态互斥）
        user_cd = await self.db.ext.get_user_cd(user_id)
        if user_cd and user_cd.type != UserStatus.IDLE:
            current_status = UserStatus.get_name(user_cd.type)
            return False, f"❌ 你当前正{current_status}，无法炼丹！", None
        
        # 3. 检查配方
        if pill_id not in self.recipes:
            return False, "❌ 无效的丹药ID！", None
        
        recipe = self.recipes[pill_id]
        
        # 3. 检查境界要求
        if player.level_index < recipe["level_required"]:
            return False, f"❌ 炼制{recipe['name']}需要达到境界等级 {recipe['level_required']}！", None
        
        # 4. 检查所有材料
        materials = recipe["materials"]
        missing_materials = []
        
        # 检查灵石
        required_gold = materials.get("灵石", 0)
        if player.gold < required_gold:
            missing_materials.append(f"灵石（需要{required_gold}，拥有{player.gold}）")
        
        # 检查储物戒中的材料
        if self.storage_ring_manager:
            for material_name, required_count in materials.items():
                if material_name == "灵石":
                    continue
                current_count = self.storage_ring_manager.get_item_count(player, material_name)
                if current_count < required_count:
                    missing_materials.append(f"{material_name}（需要{required_count}，拥有{current_count}）")
        else:
            # 没有储物戒管理器时，跳过其他材料检查（兼容旧逻辑）
            pass
        
        if missing_materials:
            return False, f"❌ 材料不足！\n" + "\n".join(f"  · {m}" for m in missing_materials), None
        
        # 5. 扣除所有材料
        player.gold -= required_gold
        
        # 扣除储物戒中的材料
        consumed_materials = []
        if self.storage_ring_manager:
            for material_name, required_count in materials.items():
                if material_name == "灵石":
                    continue
                success, _ = await self.storage_ring_manager.retrieve_item(player, material_name, required_count)
                if success:
                    consumed_materials.append(f"{material_name}×{required_count}")
        
        # 6. 判断成功率
        success_rate = recipe["success_rate"]
        # 境界加成：每高一级境界，成功率+2%
        level_bonus = (player.level_index - recipe["level_required"]) * 2
        final_success_rate = min(95, success_rate + level_bonus)
        
        roll = random.randint(1, 100)
        is_success = roll <= final_success_rate
        
        if is_success:
            # 炼制成功 - 丹药存入丹药背包
            pill_name = recipe["name"]
            
            # 将丹药存入丹药背包
            inventory = player.get_pills_inventory()
            inventory[pill_name] = inventory.get(pill_name, 0) + 1
            player.set_pills_inventory(inventory)

            await self.db.update_player(player)

            # 活跃度追踪
            if self.activity_tracker:
                try:
                    await self.activity_tracker.track_alchemy(player)
                except Exception:
                    pass

            # 构建消耗材料显示
            cost_lines = []
            if required_gold > 0:
                cost_lines.append(f"灵石 -{required_gold}")
            cost_lines.extend(consumed_materials)
            cost_str = "、".join(cost_lines) if cost_lines else "无"
            
            msg = f"""
🎉 炼丹成功！
━━━━━━━━━━━━━━━

你成功炼制了【{pill_name}】！
丹药已存入丹药背包

消耗：{cost_str}
成功率：{final_success_rate}%

💡 使用 /服用丹药 {pill_name} 可服用此丹药
💡 使用 /丹药背包 查看所有丹药
            """.strip()
            
            result_data = {
                "success": True,
                "pill_name": pill_name,
                "cost": required_gold,
                "materials_consumed": consumed_materials
            }
        else:
            # 炼制失败
            await self.db.update_player(player)
            
            # 构建消耗材料显示
            cost_lines = []
            if required_gold > 0:
                cost_lines.append(f"灵石 -{required_gold}")
            cost_lines.extend(consumed_materials)
            cost_str = "、".join(cost_lines) if cost_lines else "无"
            
            msg = f"""
💔 炼丹失败
━━━━━━━━━━━━━━━

炼制【{recipe['name']}】失败了...

材料已消耗
消耗：{cost_str}
成功率：{final_success_rate}%

再接再厉！
            """.strip()
            
            result_data = {
                "success": False,
                "pill_name": recipe["name"],
                "cost": required_gold,
                "materials_consumed": consumed_materials
            }
        
        return True, msg, result_data
