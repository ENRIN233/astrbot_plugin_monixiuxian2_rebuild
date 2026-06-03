# core/shop_manager.py

import random
import time
import json
from typing import List, Dict, Optional, Tuple

from astrbot.api import AstrBotConfig, logger
from ..config_manager import ConfigManager
from ..models import Item

class ShopManager:
    """商店管理器，负责商店物品生成、刷新和购买"""

    def __init__(self, config: AstrBotConfig, config_manager: ConfigManager):
        self.config = config
        self.config_manager = config_manager

    def _format_required_level(self, level_index: int) -> str:
        """同时展示灵修/体修的需求境界名称"""
        names = []
        if 0 <= level_index < len(self.config_manager.level_data):
            name = self.config_manager.level_data[level_index].get("level_name", "")
            if name:
                names.append(name)
        if 0 <= level_index < len(self.config_manager.body_level_data):
            name = self.config_manager.body_level_data[level_index].get("level_name", "")
            if name and name not in names:
                names.append(name)
        if not names:
            return "未知境界"
        return " / ".join(names)

    def _get_all_shop_items(self) -> List[Dict]:
        """获取所有可以在商店出售的物品（排除禁用物品）"""
        all_items = []
        disabled = set(self.config_manager.game_config.get('disabled_items', []))

        # 添加武器
        for weapon in self.config_manager.weapons_data.values():
            if weapon.get('shop_weight', 0) > 0 and weapon.get('price', 0) > 0 and weapon['name'] not in disabled:
                all_items.append({
                    'id': weapon['id'],
                    'name': weapon['name'],
                    'type': weapon.get('type', 'weapon'),
                    'price': weapon['price'],
                    'weight': weapon['shop_weight'],
                    'rank': weapon.get('rank', '凡品'),
                    'data': weapon
                })

        # 添加物品（防具、心法、功法）
        for item in self.config_manager.items_data.values():
            if item.get('shop_weight', 0) > 0 and item.get('price', 0) > 0 and item['name'] not in disabled:
                all_items.append({
                    'id': item.get('id', item['name']),
                    'name': item['name'],
                    'type': item['type'],
                    'price': item['price'],
                    'weight': item['shop_weight'],
                    'rank': item.get('rank', '凡品'),
                    'data': item
                })

        # 添加破境丹
        for pill in self.config_manager.pills_data.values():
            if pill.get('shop_weight', 0) > 0 and pill.get('price', 0) > 0 and pill['name'] not in disabled:
                all_items.append({
                    'id': pill['id'],
                    'name': pill['name'],
                    'type': 'pill',
                    'price': pill['price'],
                    'weight': pill['shop_weight'],
                    'rank': pill.get('rank', '凡品'),
                    'data': pill
                })

        # 添加修为丹
        for pill in self.config_manager.exp_pills_data.values():
            if pill.get('shop_weight', 0) > 0 and pill.get('price', 0) > 0 and pill['name'] not in disabled:
                all_items.append({
                    'id': pill['id'],
                    'name': pill['name'],
                    'type': 'exp_pill',
                    'price': pill['price'],
                    'weight': pill['shop_weight'],
                    'rank': pill.get('rank', '凡品'),
                    'data': pill
                })

        # 添加功能丹
        for pill in self.config_manager.utility_pills_data.values():
            if pill.get('shop_weight', 0) > 0 and pill.get('price', 0) > 0 and pill['name'] not in disabled:
                all_items.append({
                    'id': pill['id'],
                    'name': pill['name'],
                    'type': 'utility_pill',
                    'price': pill['price'],
                    'weight': pill['shop_weight'],
                    'rank': pill.get('rank', '凡品'),
                    'data': pill
                })

        # 添加神通
        for skill in self.config_manager.skills_data.values():
            if skill.get('shop_weight', 0) > 0 and skill.get('price', 0) > 0 and skill['name'] not in disabled:
                all_items.append({
                    'id': skill.get('name', ''),
                    'name': skill['name'],
                    'type': 'shentong',
                    'price': skill['price'],
                    'weight': skill['shop_weight'],
                    'rank': skill.get('rank', '凡品'),
                    'data': skill
                })

        return all_items

    def _weighted_random_choice(self, items: List[Dict], count: int) -> List[Dict]:
        """基于权重的随机选择（不重复）"""
        if len(items) <= count:
            return items.copy()

        selected = []
        available_items = items.copy()

        for _ in range(count):
            if not available_items:
                break

            # 计算总权重
            total_weight = sum(item['weight'] for item in available_items)
            if total_weight == 0:
                # 如果所有权重都是0，则随机选择
                choice = random.choice(available_items)
            else:
                # 基于权重选择
                rand = random.uniform(0, total_weight)
                cumulative = 0
                choice = available_items[0]
                for item in available_items:
                    cumulative += item['weight']
                    if rand <= cumulative:
                        choice = item
                        break

            selected.append(choice)
            available_items.remove(choice)

        return selected

    def _calculate_stock(self, weight: int) -> int:
        """根据权重计算库存数量

        权重越高，物品越常见，库存越多
        权重越低，物品越稀有，库存越少（最少为1）

        Args:
            weight: 物品的商店权重

        Returns:
            库存数量（最小为1）
        """
        # 获取库存计算基数，默认100
        stock_divisor = self.config.get("SHOP_STOCK_DIVISOR", 100)

        # 库存 = 权重 / 基数，向上取整，最小为1
        stock = max(1, (weight + stock_divisor - 1) // stock_divisor)

        return stock

    def ensure_items_have_stock(self, shop_items: List[Dict]) -> bool:
        """确保已有商店物品列表包含库存字段（用于兼容旧数据）

        Args:
            shop_items: 商店物品列表

        Returns:
            是否发生了修改
        """
        updated = False
        for item in shop_items:
            stock = item.get('stock')
            if stock is None:
                data = item.get('data', {})
                weight = 0
                if isinstance(data, dict):
                    weight = data.get('shop_weight') or data.get('weight') or 0
                item['stock'] = self._calculate_stock(weight)
                updated = True
            elif stock < 0:
                item['stock'] = 0
                updated = True
        return updated

    def generate_shop_items(self, count: int) -> List[Dict]:
        """生成商店物品列表

        Args:
            count: 要生成的物品数量

        Returns:
            商店物品列表，每个物品包含 id, name, type, price, discount, final_price, stock
        """
        all_items = self._get_all_shop_items()
        if not all_items:
            logger.warning("没有可用的商店物品")
            return []

        # 随机选择物品
        selected_items = self._weighted_random_choice(all_items, count)

        # 获取折扣配置
        discount_min = self.config.get("SHOP_DISCOUNT_MIN", 0.8)
        discount_max = self.config.get("SHOP_DISCOUNT_MAX", 1.2)

        # 生成商店物品
        shop_items = []
        for item in selected_items:
            # 随机折扣
            discount = random.uniform(discount_min, discount_max)
            final_price = int(item['price'] * discount)

            # 计算库存（基于权重）
            stock = self._calculate_stock(item['weight'])

            shop_items.append({
                'id': item['id'],
                'name': item['name'],
                'type': item['type'],
                'rank': item['rank'],
                'original_price': item['price'],
                'discount': discount,
                'price': final_price,
                'stock': stock,
                'data': item['data']
            })

        return shop_items

    def should_refresh_shop(self, last_refresh_time: int, refresh_hours: int = None) -> bool:
        """检查是否需要刷新"""
        if refresh_hours is None:
            refresh_hours = self.config.get("SHOP_REFRESH_HOURS", 6)
        if refresh_hours <= 0:
            return False
        return (int(time.time()) - last_refresh_time) >= (refresh_hours * 3600)

    def generate_pavilion_items(self, item_getter, count: int) -> List[Dict]:
        """生成阁楼物品列表（带库存和折扣）"""
        base_items = item_getter(count * 2)  # 获取更多以便随机选择
        selected = self._weighted_random_choice(
            [{'weight': i.get('data', {}).get('shop_weight', 100), **i} for i in base_items], count
        )
        discount_min = self.config.get("SHOP_DISCOUNT_MIN", 0.8)
        discount_max = self.config.get("SHOP_DISCOUNT_MAX", 1.2)
        result = []
        for item in selected:
            discount = random.uniform(discount_min, discount_max)
            stock = self._calculate_stock(item.get('weight', 100))
            result.append({
                'name': item['name'], 'type': item['type'], 'rank': item['rank'],
                'original_price': item['price'], 'discount': discount,
                'price': int(item['price'] * discount), 'stock': stock, 'data': item.get('data', {})
            })
        return result

    def mark_limited_offers(self, items: List[Dict], offer_count: int = 2, extra_discount: float = 0.7) -> List[Dict]:
        """从商品列表中随机标记限时特价商品

        Args:
            items: 商品列表（会被原地修改）
            offer_count: 限时特价商品数量（默认2）
            extra_discount: 额外折扣倍率（0.7 = 在现价基础上再打7折）

        Returns:
            被标记为限时特价的商品列表
        """
        if not items or offer_count <= 0:
            return []

        # 优先选择非限时商品中价格较高的（更有吸引力）
        candidates = [i for i, item in enumerate(items) if not item.get('limited_offer')]
        if not candidates:
            candidates = list(range(len(items)))

        count = min(offer_count, len(candidates))
        chosen_indices = random.sample(candidates, count)

        offers = []
        for idx in chosen_indices:
            item = items[idx]
            item['limited_offer'] = True
            item['original_discount'] = item.get('discount', 1.0)
            item['discount'] = item.get('discount', 1.0) * extra_discount
            item['price'] = int(item['original_price'] * item['discount'])
            offers.append(item)

        return offers

    def get_pills_for_display(self, count: int) -> List[Dict]:
        """获取丹药列表用于丹阁展示"""
        all_pills = []
        for pill in self.config_manager.pills_data.values():
            if pill.get('price', 0) > 0:
                all_pills.append({'name': pill['name'], 'type': 'pill', 'price': pill['price'], 'rank': pill.get('rank', '凡品'), 'data': pill})
        for pill in self.config_manager.exp_pills_data.values():
            if pill.get('price', 0) > 0:
                all_pills.append({'name': pill['name'], 'type': 'exp_pill', 'price': pill['price'], 'rank': pill.get('rank', '凡品'), 'data': pill})
        for pill in self.config_manager.utility_pills_data.values():
            if pill.get('price', 0) > 0:
                all_pills.append({'name': pill['name'], 'type': 'utility_pill', 'price': pill['price'], 'rank': pill.get('rank', '凡品'), 'data': pill})
        return all_pills

    def get_weapons_for_display(self, count: int) -> List[Dict]:
        """获取武器列表用于器阁展示"""
        all_weapons = []
        for weapon in self.config_manager.weapons_data.values():
            if weapon.get('price', 0) > 0:
                all_weapons.append({'name': weapon['name'], 'type': weapon.get('type', 'weapon'), 'price': weapon['price'], 'rank': weapon.get('rank', '凡品'), 'data': weapon})
        return all_weapons

    def get_all_items_for_display(self, count: int) -> List[Dict]:
        """获取所有物品用于百宝阁展示"""
        all_items = []
        for weapon in self.config_manager.weapons_data.values():
            if weapon.get('price', 0) > 0:
                all_items.append({'name': weapon['name'], 'type': weapon.get('type', 'weapon'), 'price': weapon['price'], 'rank': weapon.get('rank', '凡品'), 'data': weapon})
        for item in self.config_manager.items_data.values():
            if item.get('price', 0) > 0:
                item_type = self._map_legacy_item_type(item)
                all_items.append({'name': item['name'], 'type': item_type, 'price': item['price'], 'rank': item.get('rank', '凡品'), 'data': item})
        for pill in self.config_manager.pills_data.values():
            if pill.get('price', 0) > 0:
                all_items.append({'name': pill['name'], 'type': 'pill', 'price': pill['price'], 'rank': pill.get('rank', '凡品'), 'data': pill})
        for pill in self.config_manager.exp_pills_data.values():
            if pill.get('price', 0) > 0:
                all_items.append({'name': pill['name'], 'type': 'exp_pill', 'price': pill['price'], 'rank': pill.get('rank', '凡品'), 'data': pill})
        for pill in self.config_manager.utility_pills_data.values():
            if pill.get('price', 0) > 0:
                all_items.append({'name': pill['name'], 'type': 'utility_pill', 'price': pill['price'], 'rank': pill.get('rank', '凡品'), 'data': pill})
        for skill in self.config_manager.skills_data.values():
            if skill.get('price', 0) > 0:
                all_items.append({'name': skill['name'], 'type': 'shentong', 'price': skill['price'], 'rank': skill.get('rank', '凡品'), 'data': skill})
        return all_items

    def _map_legacy_item_type(self, item: dict) -> str:
        """将旧格式物品类型映射到新格式

        Args:
            item: 物品配置字典

        Returns:
            映射后的类型字符串
        """
        original_type = item.get('type', '')
        subtype = item.get('subtype', '')

        # 法器类型映射
        if original_type == '法器':
            if subtype == '武器':
                return 'weapon'
            elif subtype == '防具':
                return 'armor'
            elif subtype == '饰品':
                return 'accessory'
            else:
                return 'weapon'  # 默认为武器

        # 功法类型映射
        if original_type == '功法':
            return 'main_technique'

        # 丹药类型映射（旧系统丹药）
        if original_type == '丹药':
            return 'legacy_pill'

        # 材料类型映射
        if original_type == '材料':
            return 'material'

        # 其他类型保持不变
        return original_type

    def find_item_by_name(self, name: str) -> Optional[Dict]:
        """根据名称查找物品"""
        for weapon in self.config_manager.weapons_data.values():
            if weapon['name'] == name and weapon.get('price', 0) > 0:
                return {'name': weapon['name'], 'type': weapon.get('type', 'weapon'), 'price': weapon['price'], 'rank': weapon.get('rank', '凡品'), 'data': weapon}
        for item in self.config_manager.items_data.values():
            if item['name'] == name and item.get('price', 0) > 0:
                item_type = self._map_legacy_item_type(item)
                return {'name': item['name'], 'type': item_type, 'price': item['price'], 'rank': item.get('rank', '凡品'), 'data': item}
        for pill in self.config_manager.pills_data.values():
            if pill['name'] == name and pill.get('price', 0) > 0:
                return {'name': pill['name'], 'type': 'pill', 'price': pill['price'], 'rank': pill.get('rank', '凡品'), 'data': pill}
        for pill in self.config_manager.exp_pills_data.values():
            if pill['name'] == name and pill.get('price', 0) > 0:
                return {'name': pill['name'], 'type': 'exp_pill', 'price': pill['price'], 'rank': pill.get('rank', '凡品'), 'data': pill}
        for pill in self.config_manager.utility_pills_data.values():
            if pill['name'] == name and pill.get('price', 0) > 0:
                return {'name': pill['name'], 'type': 'utility_pill', 'price': pill['price'], 'rank': pill.get('rank', '凡品'), 'data': pill}
        for skill in self.config_manager.skills_data.values():
            if skill['name'] == name and skill.get('price', 0) > 0:
                return {'name': skill['name'], 'type': 'shentong', 'price': skill['price'], 'rank': skill.get('rank', '凡品'), 'data': skill}
        return None

    def find_item_by_name_any(self, name: str) -> Optional[Dict]:
        """根据名称查找物品（不限价格，覆盖所有数据源）"""
        for weapon in self.config_manager.weapons_data.values():
            if weapon['name'] == name:
                return {'name': weapon['name'], 'type': weapon.get('type', 'weapon'), 'price': weapon.get('price', 0), 'rank': weapon.get('rank', '凡品'), 'data': weapon}
        for item in self.config_manager.items_data.values():
            if item['name'] == name:
                item_type = self._map_legacy_item_type(item)
                return {'name': item['name'], 'type': item_type, 'price': item.get('price', 0), 'rank': item.get('rank', '凡品'), 'data': item}
        for pill in self.config_manager.pills_data.values():
            if pill['name'] == name:
                return {'name': pill['name'], 'type': 'pill', 'price': pill.get('price', 0), 'rank': pill.get('rank', '凡品'), 'data': pill}
        for pill in self.config_manager.exp_pills_data.values():
            if pill['name'] == name:
                return {'name': pill['name'], 'type': 'exp_pill', 'price': pill.get('price', 0), 'rank': pill.get('rank', '凡品'), 'data': pill}
        for pill in self.config_manager.utility_pills_data.values():
            if pill['name'] == name:
                return {'name': pill['name'], 'type': 'utility_pill', 'price': pill.get('price', 0), 'rank': pill.get('rank', '凡品'), 'data': pill}
        for ring in self.config_manager.storage_rings_data.values():
            if ring['name'] == name:
                return {'name': ring['name'], 'type': 'storage_ring', 'price': ring.get('price', 0), 'rank': ring.get('rank', '凡品'), 'data': ring}
        for skill in self.config_manager.skills_data.values():
            if skill['name'] == name:
                return {'name': skill['name'], 'type': 'shentong', 'price': skill.get('price', 0), 'rank': skill.get('rank', '凡品'), 'data': skill}
        return None

    def format_pavilion_display(self, pavilion_name: str, items: List[Dict], refresh_hours: int = 6, last_refresh: int = 0) -> str:
        """格式化阁楼展示信息"""
        if not items:
            return f"{pavilion_name}暂无物品出售"

        type_label_map = {
            'weapon': '武器', 'armor': '防具', 'main_technique': '心法',
            'pill': '破境丹', 'exp_pill': '修为丹', 'utility_pill': '功能丹',
            'legacy_pill': '丹药', 'material': '材料', 'accessory': '饰品', 'shentong': '神通'
        }

        lines = [f"=== {pavilion_name} ===\n"]
        for i, item in enumerate(items, 1):
            stock = item.get('stock', 0)
            if stock <= 0:
                continue
            type_label = type_label_map.get(item['type'], '物品')
            discount_text = ""
            if item.get('limited_offer'):
                # 限时特价：显示原折扣和特价折扣
                original_disc = item.get('original_discount', item.get('discount', 1.0))
                if original_disc < 1.0:
                    discount_text = f" 🔥限时特价 [{int((1.0 - original_disc) * 100)}%→{int((1.0 - item['discount']) * 100)}%折]"
                else:
                    discount_text = f" 🔥限时特价 [{int((1.0 - item['discount']) * 100)}%折]"
            elif item.get('discount', 1.0) < 1.0:
                discount_text = f" [{int((1.0 - item['discount']) * 100)}%折]"
            elif item.get('discount', 1.0) > 1.0:
                discount_text = f" [+{int((item['discount'] - 1.0) * 100)}%]"
            stock_text = f"库存紧张:{stock}" if stock <= 3 else f"库存:{stock}"
            
            # 获取物品效果描述
            effect_desc = self._get_item_effect_short(item)
            effect_line = f"\n   效果: {effect_desc}" if effect_desc else ""

            # 境界需求
            data = item.get('data', {})
            req_level = data.get('required_level_index', 0) if isinstance(data, dict) else 0
            level_line = ""
            if req_level > 0:
                level_name = self._format_required_level(req_level)
                level_line = f"\n   需求境界: {level_name}"

            lines.append(f"{i}. [{item['rank']}] {item['name']} ({type_label}){discount_text}\n   价格: {item['price']} 灵石 {stock_text}{effect_line}{level_line}\n")

        if refresh_hours > 0 and last_refresh:
            remaining = (last_refresh + refresh_hours * 3600) - int(time.time())
            if remaining > 0:
                lines.append(f"\n下次刷新: {remaining // 3600}小时{(remaining % 3600) // 60}分钟后")
        lines.append(f"\n提示: 使用 '购买 [物品名]' 购买物品")
        return "".join(lines)

    def _get_item_effect_short(self, item: Dict) -> str:
        """获取物品效果的简短描述"""
        data = item.get('data', {})
        item_type = item.get('type', '')
        effects = []
        
        # 武器/装备属性
        if item_type in ['weapon', 'armor', 'accessory']:
            if data.get('physical_damage', 0) > 0:
                effects.append(f"物伤+{data['physical_damage']}")
            if data.get('magic_damage', 0) > 0:
                effects.append(f"法伤+{data['magic_damage']}")
            if data.get('physical_defense', 0) > 0:
                effects.append(f"物防+{data['physical_defense']}")
            if data.get('magic_defense', 0) > 0:
                effects.append(f"法防+{data['magic_defense']}")
            if data.get('mental_power', 0) > 0:
                effects.append(f"精神力+{data['mental_power']}")
        
        # 功法属性
        elif item_type in ['main_technique', '功法']:
            if data.get('exp_multiplier', 0) > 0:
                effects.append(f"修炼效率+{int(data['exp_multiplier']*100)}%")
            if data.get('breakthrough_bonus', 0) > 0:
                effects.append(f"突破+{int(data['breakthrough_bonus']*100)}%")
            if data.get('atk_bonus', 0) > 0:
                effects.append(f"攻击+{data['atk_bonus']:.0%}")
            if data.get('hp_bonus', 0) > 0:
                effects.append(f"生命+{int(data['hp_bonus']*100)}%")
            if data.get('mp_bonus', 0) > 0:
                effects.append(f"真元+{int(data['mp_bonus']*100)}%")
            if data.get('physical_damage', 0) > 0:
                effects.append(f"物伤+{data['physical_damage']}")
            if data.get('magic_damage', 0) > 0:
                effects.append(f"法伤+{data['magic_damage']}")
        
        # 丹药效果
        elif item_type in ['pill', 'exp_pill', 'utility_pill', 'legacy_pill']:
            # 尝试从 effect 字段获取
            effect_data = data.get('effect', {})
            if isinstance(effect_data, dict):
                if effect_data.get('add_experience', 0) > 0:
                    effects.append(f"修为+{effect_data['add_experience']}")
                if effect_data.get('add_hp', 0) > 0:
                    effects.append(f"气血+{effect_data['add_hp']}")
                if effect_data.get('add_max_hp', 0) > 0:
                    effects.append(f"气血上限+{effect_data['add_max_hp']}")
                if effect_data.get('add_attack', 0) > 0:
                    effects.append(f"攻击+{effect_data['add_attack']}")
                if effect_data.get('add_defense', 0) > 0:
                    effects.append(f"防御+{effect_data['add_defense']}")
            
            # 破境丹特殊处理
            if data.get('subtype') == 'breakthrough':
                bonus = data.get('breakthrough_bonus', 0)
                if bonus > 0:
                    effects.append(f"突破成功率+{int(bonus*100)}%")
            
            # 修为丹
            if data.get('exp_boost', 0) > 0:
                effects.append(f"修为+{data['exp_boost']}")
        
        # 材料
        elif item_type == 'material':
            if data.get('description'):
                return data['description'][:20]

        # 神通
        elif item_type == 'shentong':
            type_names = {1: '攻击', 2: '持续', 3: '增益', 4: '控制'}
            stype = type_names.get(data.get('skill_type', 1), '攻击')
            effects.append(f"类型:{stype}")
            if data.get('mpcost', 0) > 0:
                effects.append(f"MP消耗:{int(data['mpcost']*100)}%")
        
        # 如果有描述字段，优先使用
        if not effects and data.get('description'):
            desc = data['description']
            return desc[:25] + "..." if len(desc) > 25 else desc
        
        return ", ".join(effects[:3]) if effects else ""

    def get_item_details(self, item_data: Dict) -> str:
        """获取物品详细信息

        Args:
            item_data: 物品数据字典

        Returns:
            物品详细描述
        """
        item_type = item_data.get('type', '')
        data = item_data.get('data', {})

        details = [f"名称: {item_data['name']}"]
        details.append(f"品级: {item_data['rank']}")
        details.append(f"价格: {item_data['price']} 灵石")

        description = data.get('description')
        if description:
            details.append(f"描述: {description}")

        # 武器/防具/饰品属性
        if item_type in ['weapon', 'armor', 'accessory']:
            attrs = []
            if data.get('magic_damage', 0) > 0:
                attrs.append(f"法伤+{data['magic_damage']}")
            if data.get('physical_damage', 0) > 0:
                attrs.append(f"物伤+{data['physical_damage']}")
            if data.get('magic_defense', 0) > 0:
                attrs.append(f"法防+{data['magic_defense']}")
            if data.get('physical_defense', 0) > 0:
                attrs.append(f"物防+{data['physical_defense']}")
            if data.get('mental_power', 0) > 0:
                attrs.append(f"精神力+{data['mental_power']}")
            if attrs:
                details.append(f"属性: {', '.join(attrs)}")
            if 'required_level_index' in data:
                level_name = self._format_required_level(data['required_level_index'])
                details.append(f"需求境界: {level_name}")

        # 心法/功法
        elif item_type in ['main_technique']:
            attrs = []
            if data.get('exp_multiplier', 0) > 0:
                attrs.append(f"修炼效率+{data['exp_multiplier']:.1%}")
            if data.get('breakthrough_bonus', 0) > 0:
                attrs.append(f"突破成功率+{data['breakthrough_bonus']:.1%}")
            if data.get('atk_bonus', 0) > 0:
                attrs.append(f"攻击力+{data['atk_bonus']:.0%}")
            if data.get('hp_bonus', 0) > 0:
                attrs.append(f"生命值+{data['hp_bonus']:.1%}")
            if data.get('mp_bonus', 0) > 0:
                attrs.append(f"真元+{data['mp_bonus']:.1%}")
            if data.get('magic_damage', 0) > 0:
                attrs.append(f"法伤+{data['magic_damage']}")
            if data.get('physical_damage', 0) > 0:
                attrs.append(f"物伤+{data['physical_damage']}")
            if data.get('magic_defense', 0) > 0:
                attrs.append(f"法防+{data['magic_defense']}")
            if data.get('physical_defense', 0) > 0:
                attrs.append(f"物防+{data['physical_defense']}")
            if data.get('mental_power', 0) > 0:
                attrs.append(f"精神力+{data['mental_power']}")
            if attrs:
                details.append(f"效果: {', '.join(attrs)}")
            if 'required_level_index' in data:
                level_name = self._format_required_level(data['required_level_index'])
                details.append(f"需求境界: {level_name}")

        # 丹药类
        elif item_type in ['pill', 'exp_pill', 'utility_pill', 'legacy_pill']:
            if 'required_level_index' in data and data['required_level_index'] > 0:
                level_name = self._format_required_level(data['required_level_index'])
                details.append(f"需求境界: {level_name}")

            subtype = data.get('subtype', '')
            effect_desc = []

            if item_type == 'pill' and subtype == 'breakthrough':
                bonus = data.get('breakthrough_bonus', 0)
                max_rate = data.get('max_success_rate', 1.0)
                target = data.get('target_level_index')
                if target is not None:
                    level_name = self._format_required_level(target)
                    effect_desc.append(f"目标境界: {level_name}")
                effect_desc.append(f"突破成功率+{int(bonus * 100)}%，最高可达 {int(max_rate * 100)}%")

            elif item_type == 'exp_pill':
                exp_gain = data.get('exp_gain', 0)
                effect_desc.append(f"立即获得修为：+{exp_gain}")

            elif item_type == 'utility_pill':
                effect_type = data.get('effect_type', '')
                if subtype == 'resurrection':
                    pill_id = data.get('id', '')
                    if pill_id == 'util_002':
                        effect_desc.append("死亡时自动复活（不损失属性）")
                    else:
                        effect_desc.append("死亡时自动复活（损失15%属性）")
                elif effect_type == 'temporary':
                    duration = data.get('duration_minutes', 0)
                    mult = data.get('cultivation_multiplier', 0)
                    if mult > 0:
                        effect_desc.append(f"修炼速度+{int(mult * 100)}% 持续 {duration} 分钟")
                    if data.get('physical_damage_multiplier'):
                        effect_desc.append(f"物伤倍率+{data['physical_damage_multiplier']:.0%}")
                elif effect_type == 'permanent':
                    gains = []
                    for attr_key, label in [
                        ('physical_damage_gain', '物伤'),
                        ('magic_damage_gain', '法伤'),
                        ('physical_defense_gain', '物防'),
                        ('magic_defense_gain', '法防'),
                        ('mental_power_gain', '精神力')
                    ]:
                        value = data.get(attr_key)
                        if value:
                            sign = "+" if value > 0 else ""
                            gains.append(f"{label}{sign}{value}")
                    if gains:
                        effect_desc.append("永久增益：" + "，".join(gains))
                if data.get('resets_permanent_pills'):
                    refund_ratio = data.get('reset_refund_ratio', 0)
                    hint = "重置所有永久丹药增益"
                    if refund_ratio:
                        hint += f"，返还售价的{int(refund_ratio*100)}%"
                    effect_desc.append(hint)
                if data.get('blocks_next_debuff'):
                    effect_desc.append("获得定魂护盾，抵消下一次负面状态")

            elif item_type == 'legacy_pill':
                effect_data = data.get('effect', {})
                for key, label in [
                    ('add_hp', '恢复气血'),
                    ('add_experience', '增加修为'),
                    ('add_max_hp', '提升上限'),
                    ('add_attack', '物伤变化'),
                    ('add_defense', '物防变化'),
                    ('add_spiritual_power', '法伤变化'),
                    ('add_mental_power', '精神力变化'),
                    ('add_gold', '灵石变化'),
                ]:
                    value = effect_data.get(key)
                    if value:
                        sign = "+" if value > 0 else ""
                        effect_desc.append(f"{label}{sign}{value}")
                if effect_data.get('add_breakthrough_bonus'):
                    effect_desc.append(f"突破成功率+{int(effect_data['add_breakthrough_bonus']*100)}%（1小时）")

            if effect_desc:
                details.append("效果: " + "；".join(effect_desc))

        return "\n".join(details)

    TYPE_LABEL_MAP = {
        'weapon': '武器', 'armor': '防具', 'main_technique': '心法',
        'pill': '破境丹', 'exp_pill': '修为丹',
        'utility_pill': '功能丹', 'legacy_pill': '丹药', 'material': '材料',
        'accessory': '饰品', 'storage_ring': '储物戒', 'shentong': '神通',
    }

    def get_item_details_full(self, item_data: Dict) -> str:
        """获取物品完整详细信息（用于 /查看 指令，覆盖所有类型）"""
        item_type = item_data.get('type', '')
        data = item_data.get('data', {})
        type_label = self.TYPE_LABEL_MAP.get(item_type, '物品')

        details = [
            f"=== {item_data['name']} ===",
            f"类型: {type_label}",
            f"品级: {item_data.get('rank', '凡品')}",
        ]

        price = item_data.get('price', 0)
        if price and price > 0:
            details.append(f"价格: {price:,} 灵石")

        description = data.get('description')
        if description:
            details.append(f"描述: {description}")

        if item_type in ['weapon', 'armor', 'accessory']:
            if data.get('weapon_category'):
                details.append(f"类别: {data['weapon_category']}")
            attrs = []
            for key, label in [
                ('physical_damage', '物伤'), ('magic_damage', '法伤'),
                ('physical_defense', '物防'), ('magic_defense', '法防'),
                ('mental_power', '精神力'),
            ]:
                val = data.get(key, 0)
                if val:
                    attrs.append(f"{label}+{val}")
            if attrs:
                details.append(f"属性: {', '.join(attrs)}")
            if 'required_level_index' in data:
                details.append(f"需求境界: {self._format_required_level(data['required_level_index'])}")

        elif item_type in ['main_technique']:
            attrs = []
            if data.get('exp_multiplier', 0) > 0:
                attrs.append(f"修炼效率+{data['exp_multiplier']:.1%}")
            if data.get('breakthrough_bonus', 0) > 0:
                attrs.append(f"突破成功率+{data['breakthrough_bonus']:.1%}")
            if data.get('atk_bonus', 0) > 0:
                attrs.append(f"攻击力+{data['atk_bonus']:.0%}")
            if data.get('hp_bonus', 0) > 0:
                attrs.append(f"生命值+{data['hp_bonus']:.1%}")
            if data.get('mp_bonus', 0) > 0:
                attrs.append(f"真元+{data['mp_bonus']:.1%}")
            for key, label in [
                ('physical_damage', '物伤'), ('magic_damage', '法伤'),
                ('physical_defense', '物防'), ('magic_defense', '法防'),
                ('mental_power', '精神力'),
            ]:
                val = data.get(key, 0)
                if val:
                    attrs.append(f"{label}+{val}")
            if attrs:
                details.append(f"效果: {', '.join(attrs)}")
            if 'required_level_index' in data:
                details.append(f"需求境界: {self._format_required_level(data['required_level_index'])}")

        elif item_type in ['pill', 'exp_pill', 'utility_pill', 'legacy_pill']:
            if 'required_level_index' in data and data['required_level_index'] > 0:
                details.append(f"需求境界: {self._format_required_level(data['required_level_index'])}")
            subtype = data.get('subtype', '')
            effect_desc = []
            if item_type == 'pill' and subtype == 'breakthrough':
                bonus = data.get('breakthrough_bonus', 0)
                max_rate = data.get('max_success_rate', 1.0)
                target = data.get('target_level_index')
                if target is not None:
                    effect_desc.append(f"目标境界: {self._format_required_level(target)}")
                effect_desc.append(f"突破成功率+{int(bonus * 100)}%，最高可达 {int(max_rate * 100)}%")
            elif item_type == 'exp_pill':
                exp_gain = data.get('exp_gain', 0)
                if exp_gain:
                    effect_desc.append(f"立即获得修为：+{exp_gain}")
            elif item_type == 'utility_pill':
                effect_type = data.get('effect_type', '')
                if subtype == 'resurrection':
                    pill_id = data.get('id', '')
                    if pill_id == 'util_002':
                        effect_desc.append("死亡时自动复活（不损失属性）")
                    else:
                        effect_desc.append("死亡时自动复活（损失15%属性）")
                elif effect_type == 'temporary':
                    duration = data.get('duration_minutes', 0)
                    mult = data.get('cultivation_multiplier', 0)
                    if mult > 0:
                        effect_desc.append(f"修炼速度+{int(mult * 100)}% 持续 {duration} 分钟")
                    if data.get('physical_damage_multiplier'):
                        effect_desc.append(f"物伤倍率+{data['physical_damage_multiplier']:.0%}")
                elif effect_type == 'permanent':
                    gains = []
                    for attr_key, label in [
                        ('physical_damage_gain', '物伤'), ('magic_damage_gain', '法伤'),
                        ('physical_defense_gain', '物防'), ('magic_defense_gain', '法防'),
                        ('mental_power_gain', '精神力'),
                    ]:
                        value = data.get(attr_key)
                        if value:
                            sign = "+" if value > 0 else ""
                            gains.append(f"{label}{sign}{value}")
                    if gains:
                        effect_desc.append("永久增益：" + "，".join(gains))
                if data.get('resets_permanent_pills'):
                    refund_ratio = data.get('reset_refund_ratio', 0)
                    hint = "重置所有永久丹药增益"
                    if refund_ratio:
                        hint += f"，返还售价的{int(refund_ratio*100)}%"
                    effect_desc.append(hint)
                if data.get('blocks_next_debuff'):
                    effect_desc.append("获得定魂护盾，抵消下一次负面状态")
            elif item_type == 'legacy_pill':
                effect_data = data.get('effect', {})
                for key, label in [
                    ('add_hp', '恢复气血'), ('add_experience', '增加修为'),
                    ('add_max_hp', '提升上限'), ('add_attack', '物伤变化'),
                    ('add_defense', '物防变化'), ('add_spiritual_power', '法伤变化'),
                    ('add_mental_power', '精神力变化'), ('add_gold', '灵石变化'),
                ]:
                    value = effect_data.get(key)
                    if value:
                        sign = "+" if value > 0 else ""
                        effect_desc.append(f"{label}{sign}{value}")
                if effect_data.get('add_breakthrough_bonus'):
                    effect_desc.append(f"突破成功率+{int(effect_data['add_breakthrough_bonus']*100)}%（1小时）")
            if effect_desc:
                details.append("效果: " + "；".join(effect_desc))

        elif item_type == 'storage_ring':
            capacity = data.get('capacity', 0)
            if capacity:
                details.append(f"容量: {capacity} 格")
            if 'required_level_index' in data:
                details.append(f"需求境界: {self._format_required_level(data['required_level_index'])}")

        elif item_type == 'material':
            pass

        elif item_type == 'shentong':
            type_names = {1: '攻击', 2: '持续', 3: '增益', 4: '控制'}
            stype = type_names.get(data.get('skill_type', 1), '攻击')
            details.append(f"神通类型: {stype}")
            atkvalue = data.get('atkvalue', [])
            if atkvalue:
                hits = len(atkvalue) if isinstance(atkvalue, list) else 1
                details.append(f"连击段数: {hits}")
                if isinstance(atkvalue, list):
                    details.append(f"伤害倍率: {' / '.join(f'{v}x' for v in atkvalue)}")
            mpcost = data.get('mpcost', 0)
            hpcost = data.get('hpcost', 0)
            if mpcost > 0:
                details.append(f"MP消耗: {int(mpcost*100)}%")
            if hpcost > 0:
                details.append(f"HP消耗: {int(hpcost*100)}%")
            details.append(f"冷却回合: {data.get('turncost', 0)}")
            details.append(f"触发概率: {data.get('rate', 100)}%")
            if data.get('bufftype') and data.get('buffvalue'):
                buff_name = "攻击力" if data['bufftype'] == 1 else "防御力"
                details.append(f"增益效果: {buff_name}+{int(data['buffvalue']*100)}%")
            if data.get('success'):
                details.append(f"封印成功率: {data['success']}%")
            if data.get('desc'):
                details.append(f"描述: {data['desc']}")
            if 'required_level_index' in data and data['required_level_index'] > 0:
                details.append(f"需求境界: {self._format_required_level(data['required_level_index'])}")

        return "\n".join(details)
