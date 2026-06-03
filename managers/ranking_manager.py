# managers/ranking_manager.py
"""
排行榜系统管理器 - 处理各种排行榜逻辑
"""

from typing import Tuple, List, TYPE_CHECKING, Optional
from ..data.data_manager import DataBase
from ..managers.combat_manager import CombatManager

if TYPE_CHECKING:
    from ..config_manager import ConfigManager
    from ..models import Player

# 宗门职位映射（安全映射，防止索引越界）
POSITION_MAP = {
    0: "宗主",
    1: "长老",
    2: "亲传",
    3: "内门",
    4: "外门",
}

# 名称最大显示长度
MAX_NAME_LENGTH = 12


def _short_id(user_id) -> str:
    """安全获取短ID，防止非字符串类型报错"""
    if user_id is None:
        return "未知"
    return str(user_id)[:6]


def _safe_name(player: Optional["Player"], fallback_id) -> str:
    """安全获取玩家名称，带长度截断和特殊字符过滤"""
    if player and player.user_name:
        name = player.user_name
    else:
        name = f"道友{_short_id(fallback_id)}"
    
    # 过滤危险字符（@可能触发群通知）
    name = name.replace("@", "＠")
    # 截断过长名称
    if len(name) > MAX_NAME_LENGTH:
        name = name[:MAX_NAME_LENGTH] + "…"
    return name


class RankingManager:
    """排行榜系统管理器"""
    
    def __init__(self, db: DataBase, combat_mgr: CombatManager, config_manager: "ConfigManager"):
        self.db = db
        self.combat_mgr = combat_mgr
        self.config_manager = config_manager
        
        # 延迟导入，避免循环依赖，只初始化一次
        from ..core import EquipmentManager
        self.equipment_manager = EquipmentManager(self.db, self.config_manager)
    
    async def get_level_ranking(self, limit: int = 10) -> Tuple[bool, str]:
        """
        境界排行榜
        
        Args:
            limit: 显示数量
            
        Returns:
            (成功标志, 消息)
        """
        all_players = await self.db.get_all_players()
        
        if not all_players:
            return False, "❌ 暂无数据！"
        
        # 按修为排序
        sorted_players = sorted(all_players, key=lambda p: p.experience, reverse=True)[:limit]
        
        msg = "📊 境界排行榜\n"
        msg += "━━━━━━━━━━━━━━━\n"
        
        for idx, player in enumerate(sorted_players, 1):
            name = _safe_name(player, player.user_id)
            level_name = player.get_level(self.config_manager)
            msg += f"{idx}. {name}\n"
            msg += f"   境界：{level_name} | 修为：{player.experience:,}\n\n"
        
        return True, msg
    
    async def get_power_ranking(self, limit: int = 10) -> Tuple[bool, str]:
        """
        战力排行榜（基于综合属性）
        
        战力计算公式：物伤 + 法伤 + 物防 + 法防 + 精神力/10
        与玩家信息显示的战力保持一致
        
        Args:
            limit: 显示数量
            
        Returns:
            (成功标志, 消息)
        """
        all_players = await self.db.get_all_players()
        
        if not all_players:
            return False, "❌ 暂无数据！"
        
        # 计算战力（复用战斗系统）
        from .combat_manager import CombatManager
        player_power = []
        for player in all_players:
            # 获取装备加成（用于主攻击属性显示）
            equipped_items = self.equipment_manager.get_equipped_items(
                player,
                self.config_manager.items_data,
                self.config_manager.weapons_data
            )
            total_attrs = player.get_total_attributes(equipped_items, None)

            # 构建 CombatStats 并计算战力（不含丹药临时效果，更公平）
            impart_info = await self.db.ext.get_impart_info(player.user_id)
            combat_stats = CombatManager.build_player_combat_stats(player, impart_info, self.config_manager)
            combat_power = CombatManager.calc_combat_power(combat_stats, combat_stats.max_hp, combat_stats.max_mp)
            player_power.append((player, combat_power, total_attrs))
        
        # 按战力排序
        sorted_players = sorted(player_power, key=lambda x: x[1], reverse=True)[:limit]
        
        msg = "📊 战力排行榜\n"
        msg += "━━━━━━━━━━━━━━━\n"
        
        for idx, (player, power, attrs) in enumerate(sorted_players, 1):
            name = _safe_name(player, player.user_id)
            # 显示主要攻击属性（根据修炼类型）
            if player.cultivation_type == "体修":
                main_atk = int(attrs['physical_damage'])
                atk_label = "物伤"
            else:
                main_atk = int(attrs['magic_damage'])
                atk_label = "法伤"
            msg += f"{idx}. {name}\n"
            msg += f"   战力：{power:,} | {atk_label}：{main_atk:,}\n\n"
        
        return True, msg
    
    async def get_wealth_ranking(self, limit: int = 10) -> Tuple[bool, str]:
        """
        财富排行榜（灵石）
        
        Args:
            limit: 显示数量
            
        Returns:
            (成功标志, 消息)
        """
        all_players = await self.db.get_all_players()
        
        if not all_players:
            return False, "❌ 暂无数据！"
        
        # 按灵石排序
        sorted_players = sorted(all_players, key=lambda p: p.gold, reverse=True)[:limit]
        
        msg = "📊 财富排行榜\n"
        msg += "━━━━━━━━━━━━━━━\n"
        
        for idx, player in enumerate(sorted_players, 1):
            name = _safe_name(player, player.user_id)
            msg += f"{idx}. {name}\n"
            msg += f"   灵石：{player.gold:,}\n\n"
        
        return True, msg
    
    async def get_sect_ranking(self, limit: int = 10) -> Tuple[bool, str]:
        """
        宗门排行榜（建设度）
        
        Args:
            limit: 显示数量
            
        Returns:
            (成功标志, 消息)
        """
        all_sects = await self.db.ext.get_all_sects()
        
        if not all_sects:
            return False, "❌ 暂无宗门数据！"
        
        # 显式按建设度排序，不依赖DB层的排序行为
        top_sects = sorted(all_sects, key=lambda s: s.sect_scale, reverse=True)[:limit]
        
        msg = "📊 宗门排行榜\n"
        msg += "━━━━━━━━━━━━━━━\n"
        
        for idx, sect in enumerate(top_sects, 1):
            owner = await self.db.get_player_by_id(sect.sect_owner)
            owner_name = _safe_name(owner, sect.sect_owner)
            members = await self.db.ext.get_sect_members(sect.sect_id)
            
            # 宗门名称也需要安全处理
            sect_name = sect.sect_name.replace("@", "＠")
            if len(sect_name) > MAX_NAME_LENGTH:
                sect_name = sect_name[:MAX_NAME_LENGTH] + "…"
            
            msg += f"{idx}. 【{sect_name}】\n"
            msg += f"   宗主：{owner_name}\n"
            msg += f"   建设度：{sect.sect_scale:,} | 成员：{len(members)}人\n\n"
        
        return True, msg
    
    async def get_deposit_ranking(self, limit: int = 10) -> Tuple[bool, str]:
        """
        存款排行榜（银行存款）
        
        Args:
            limit: 显示数量
            
        Returns:
            (成功标志, 消息)
        """
        rankings = await self.db.ext.get_deposit_ranking(limit)
        
        if not rankings:
            return False, "❌ 暂无存款数据！"
        
        msg = "📊 存款排行榜\n"
        msg += "━━━━━━━━━━━━━━━\n"
        
        for idx, item in enumerate(rankings, 1):
            uid = item["user_id"]
            player = await self.db.get_player_by_id(uid)
            name = _safe_name(player, uid)
            msg += f"{idx}. {name}\n"
            msg += f"   存款：{item['balance']:,} 灵石\n\n"
        
        return True, msg
    
    async def get_contribution_ranking(self, sect_id: int, limit: int = 10) -> Tuple[bool, str]:
        """
        宗门贡献度排行榜
        
        Args:
            sect_id: 宗门ID
            limit: 显示数量
            
        Returns:
            (成功标志, 消息)
        """
        sect = await self.db.ext.get_sect_by_id(sect_id)
        if not sect:
            return False, "❌ 宗门不存在！"
        
        members = await self.db.ext.get_sect_members(sect_id)
        
        if not members:
            return False, "❌ 宗门暂无成员！"
        
        # 按贡献度排序
        sorted_members = sorted(members, key=lambda p: p.sect_contribution, reverse=True)[:limit]
        
        # 宗门名称安全处理
        sect_name = sect.sect_name.replace("@", "＠")
        if len(sect_name) > MAX_NAME_LENGTH:
            sect_name = sect_name[:MAX_NAME_LENGTH] + "…"
        
        msg = f"📊 {sect_name} 贡献排行\n"
        msg += f"━━━━━━━━━━━━━━━\n"
        
        for idx, member in enumerate(sorted_members, 1):
            name = _safe_name(member, member.user_id)
            # 使用安全映射获取职位名称，防止索引越界
            position_name = POSITION_MAP.get(member.sect_position, "成员")
            msg += f"{idx}. {name} ({position_name})\n"
            msg += f"   贡献度：{member.sect_contribution:,}\n\n"
        
        return True, msg
