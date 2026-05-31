import json
from pathlib import Path
from typing import List, Dict, Any

from astrbot.api import logger
from .data.default_configs import SECT_CONFIG, BOSS_CONFIG, RIFT_CONFIG, ALCHEMY_CONFIG

class ConfigManager:
    """配置管理器，加载境界、物品、武器和丹药配置"""

    def __init__(self, base_dir: Path):
        self._base_dir = base_dir
        self.level_data: List[dict] = []  # 灵修境界数据
        self.body_level_data: List[dict] = []  # 体修境界数据
        self.items_data: Dict[str, dict] = {}  # 物品数据，key为物品名称
        self.weapons_data: Dict[str, dict] = {}  # 武器数据，key为武器名称
        self.pills_data: Dict[str, dict] = {}  # 破境丹数据，key为丹药名称
        self.exp_pills_data: Dict[str, dict] = {}  # 修为丹数据，key为丹药名称
        self.utility_pills_data: Dict[str, dict] = {}  # 功能丹数据，key为丹药名称
        self.storage_rings_data: Dict[str, dict] = {}  # 储物戒数据，key为储物戒名称
        self.skills_data: Dict[str, dict] = {}  # 神通数据，key为神通名称
        
        # 新增系统配置
        self.sect_config: Dict[str, Any] = {}
        self.boss_config: Dict[str, Any] = {}
        self.rift_config: Dict[str, Any] = {}
        self.alchemy_config: Dict[str, Any] = {}
        
        self._load_all()

    def get_level_data(self, cultivation_type: str = "灵修") -> List[dict]:
        """根据修炼类型获取对应的境界数据"""
        if cultivation_type == "体修":
            return self.body_level_data
        return self.level_data

    def _load_json_data(self, file_path: Path) -> List[dict]:
        """加载JSON配置文件（列表格式）"""
        if not file_path.exists():
            logger.warning(f"数据文件 {file_path} 不存在，将使用空数据。")
            return []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"成功加载 {file_path.name} (共 {len(data)} 条数据)。")
                return data
        except Exception as e:
            logger.error(f"加载数据文件 {file_path} 失败: {e}")
            return []
            
    def _load_config_with_default(self, file_path: Path, default_config: Dict) -> Dict:
        """加载配置，如果不存在则创建默认配置"""
        if not file_path.exists():
            try:
                # 确保目录存在
                file_path.parent.mkdir(parents=True, exist_ok=True)
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, ensure_ascii=False, indent=2)
                logger.info(f"创建默认配置文件: {file_path.name}")
                return default_config
            except Exception as e:
                logger.error(f"创建配置文件 {file_path} 失败: {e}")
                return default_config
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"成功加载配置文件: {file_path.name}")
                return data
        except Exception as e:
            logger.error(f"加载配置文件 {file_path} 失败: {e}")
            return default_config

    def _load_items_data(self, file_path: Path) -> Dict[str, dict]:
        """加载物品配置文件并转换为字典（key为物品名称）"""
        if not file_path.exists():
            logger.warning(f"物品数据文件 {file_path} 不存在，将使用空数据。")
            return {}
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

                if isinstance(data, list):
                    items_dict = {item.get("name", ""): item for item in data if isinstance(item, dict) and item.get("name")}
                elif isinstance(data, dict):
                    items_dict = {}
                    for item_id, item_data in data.items():
                        if isinstance(item_data, dict) and item_data.get("name"):
                            if "id" not in item_data:
                                item_data["id"] = item_id
                            items_dict[item_data["name"]] = item_data
                else:
                    logger.error(f"物品数据文件 {file_path} 格式不正确，应该是数组或字典。")
                    return {}

                logger.info(f"成功加载 {file_path.name} (共 {len(items_dict)} 个物品)。")
                return items_dict
        except Exception as e:
            logger.error(f"加载物品数据文件 {file_path} 失败: {e}")
            return {}

    def _load_all(self):
        """加载所有配置文件"""
        config_dir = self._base_dir / "config"
        
        # 加载基础配置
        self.level_data = self._load_json_data(config_dir / "level_config.json")
        self.body_level_data = self._load_json_data(config_dir / "body_level_config.json")
        self.items_data = self._load_items_data(config_dir / "items.json")
        self.weapons_data = self._load_items_data(config_dir / "weapons.json")
        self.pills_data = self._load_items_data(config_dir / "pills.json")
        self.exp_pills_data = self._load_items_data(config_dir / "exp_pills.json")
        self.utility_pills_data = self._load_items_data(config_dir / "utility_pills.json")
        self.storage_rings_data = self._load_items_data(config_dir / "storage_rings.json")
        self.skills_data = self._load_items_data(config_dir / "skills.json")
        
        # 加载新系统配置
        self.sect_config = self._load_config_with_default(config_dir / "sect_config.json", SECT_CONFIG)
        self.boss_config = self._load_config_with_default(config_dir / "boss_config.json", BOSS_CONFIG)
        self.rift_config = self._load_config_with_default(config_dir / "rift_config.json", RIFT_CONFIG)
        self.alchemy_config = self._load_config_with_default(config_dir / "alchemy_config.json", ALCHEMY_CONFIG)
        self.alchemy_recipes = self._load_items_data(config_dir / "alchemy_recipes.json")
        
        # 加载游戏配置（包含各系统的硬编码参数）
        self.game_config = self._load_config_with_default(config_dir / "game_config.json", {})
        
        self._pill_names_cache = None

        logger.info(
            f"配置管理器初始化完成，"
            f"加载了 {len(self.level_data)} 个灵修境界配置，"
            f"{len(self.body_level_data)} 个体修境界配置，"
            f"以及新系统配置 (宗门/Boss/秘境/炼丹)，"
            f"{len(self.skills_data)} 个神通配置"
        )

    def save_game_config(self) -> None:
        """将 game_config 写回磁盘"""
        path = self._base_dir / "config" / "game_config.json"
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.game_config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存 game_config.json 失败: {e}")
    
    def is_pill(self, item_name: str) -> bool:
        """检查物品是否为丹药类型（统一的丹药判断方法）"""
        if item_name in self.pills_data:
            return True
        if item_name in self.exp_pills_data:
            return True
        if item_name in self.utility_pills_data:
            return True
        
        item_config = self.items_data.get(item_name)
        if item_config and item_config.get("type") == "丹药":
            return True
        
        return False
    
    def get_all_pill_names(self) -> set:
        """获取所有注册的丹药名称"""
        if self._pill_names_cache is not None:
            return self._pill_names_cache
        
        pill_names = set()
        pill_names.update(self.pills_data.keys())
        pill_names.update(self.exp_pills_data.keys())
        pill_names.update(self.utility_pills_data.keys())
        
        for name, item in self.items_data.items():
            if isinstance(item, dict) and item.get("type") == "丹药":
                pill_names.add(name)
        
        self._pill_names_cache = pill_names
        return pill_names
    
    def invalidate_cache(self):
        """清除缓存，在配置重载时调用"""
        self._pill_names_cache = None
