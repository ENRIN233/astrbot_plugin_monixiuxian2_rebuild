# models.py - 新增模型定义

from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING, List, Optional
import json

if TYPE_CHECKING:
    from .config_manager import ConfigManager


class UserStatus(IntEnum):
    """用户状态枚举"""
    IDLE = 0           # 空闲
    CULTIVATING = 1    # 闭关中
    ADVENTURING = 2    # 已废弃（历练系统已删除），保留值兼容数据库
    EXPLORING = 3      # 探索秘境中
    SECT_TASK = 4      # 宗门任务中
    TRADING = 5        # 交易中

    @classmethod
    def get_name(cls, status: int) -> str:
        """获取状态名称"""
        names = {
            cls.IDLE: "空闲",
            cls.CULTIVATING: "闭关中",
            cls.ADVENTURING: "历练中",
            cls.EXPLORING: "探索秘境中",
            cls.SECT_TASK: "宗门任务中",
            cls.TRADING: "交易中",
        }
        return names.get(status, "忙碌中")

@dataclass
class Sect:
    """宗门数据模型"""
    
    sect_id: int  # 宗门ID（主键）
    sect_name: str  # 宗门名称
    sect_owner: str  # 宗主用户ID
    sect_scale: int = 0  # 建设度
    sect_used_stone: int = 0  # 可用灵石
    sect_fairyland: int = 0  # 洞天福地等级
    sect_materials: int = 0  # 资材
    mainbuff: str = "0"  # 主修功法buff ID列表（JSON字符串）
    secbuff: str = "0"  # 辅修功法buff ID列表（JSON字符串）
    elixir_room_level: int = 0  # 丹房等级
    
    def get_mainbuff_list(self) -> List[int]:
        """获取主修功法ID列表"""
        try:
            if self.mainbuff == "0" or not self.mainbuff:
                return []
            return json.loads(self.mainbuff) if isinstance(self.mainbuff, str) else [self.mainbuff]
        except:
            return []
    
    def set_mainbuff_list(self, buff_list: List[int]):
        """设置主修功法ID列表"""
        self.mainbuff = json.dumps(buff_list, ensure_ascii=False) if buff_list else "0"
    
    def get_secbuff_list(self) -> List[int]:
        """获取辅修功法ID列表"""
        try:
            if self.secbuff == "0" or not self.secbuff:
                return []
            return json.loads(self.secbuff) if isinstance(self.secbuff, str) else [self.secbuff]
        except:
            return []
    
    def set_secbuff_list(self, buff_list: List[int]):
        """设置辅修功法ID列表"""
        self.secbuff = json.dumps(buff_list, ensure_ascii=False) if buff_list else "0"


@dataclass
class BuffInfo:
    """Buff信息数据模型（用户装备的功法、法器等）"""
    
    id: int  # 主键
    user_id: str  # 用户ID
    main_buff: int = 0  # 主修功法ID
    sec_buff: int = 0  # 辅修功法ID
    faqi_buff: int = 0  # 已废弃（旧法器系统），保留字段兼容数据库
    fabao_weapon: int = 0  # 法宝武器ID
    armor_buff: int = 0  # 防具buff ID
    atk_buff: int = 0  # 永久攻击buff
    sub_buff: int = 0  # 副buff


@dataclass
class Boss:
    """Boss数据模型"""
    
    boss_id: int  # Boss ID（主键）
    boss_name: str  # Boss名称
    boss_level: str  # Boss境界
    hp: int  # 血量
    max_hp: int  # 最大血量
    atk: int  # 攻击力
    defense: int = 0  # 防御力
    stone_reward: int = 0  # 灵石奖励
    create_time: int = 0  # 生成时间
    status: int = 1  # 状态（0已击败，1存活）
    

@dataclass
class Rift:
    """秘境数据模型"""
    
    rift_id: int  # 秘境ID（主键）
    rift_name: str  # 秘境名称
    rift_level: int  # 秘境等级
    required_level: int # 需求境界
    rewards: str = "{}"  # 奖励配置（JSON字符串）
    
    def get_rewards(self) -> dict:
        """获取奖励字典"""
        try:
            return json.loads(self.rewards)
        except:
            return {}
    
    def set_rewards(self, rewards_dict: dict):
        """设置奖励字典"""
        self.rewards = json.dumps(rewards_dict, ensure_ascii=False)


@dataclass
class ImpartInfo:
    """传承信息数据模型"""
    
    id: int  # 主键
    user_id: str  # 用户ID
    impart_hp_per: float = 0.0  # HP加成百分比
    impart_mp_per: float = 0.0  # MP加成百分比
    impart_atk_per: float = 0.0  # ATK加成百分比
    impart_know_per: float = 0.0  # 会心率加成百分比
    impart_burst_per: float = 0.0  # 爆伤加成百分比


@dataclass
class UserCd:
    """用户CD信息数据模型"""
    
    user_id: str  # 用户ID（主键）
    type: int = UserStatus.IDLE  # CD类型，参见 UserStatus 枚举
    create_time: int = 0  # 创建时间
    scheduled_time: int = 0  # 计划完成时间
    extra_data: str = "{}"  # 额外数据（JSON字符串，如秘境ID等）
    
    def get_extra_data(self) -> dict:
        """获取额外数据字典"""
        try:
            return json.loads(self.extra_data)
        except:
            return {}
    
    def set_extra_data(self, data: dict):
        """设置额外数据"""
        self.extra_data = json.dumps(data, ensure_ascii=False)


@dataclass
class DungeonNode:
    """秘境地图节点"""
    step: int                    # 周期内序号 (1/2/3)
    node_type: str               # monster/elite/treasure/spring/campfire/theme_mine/nothing/merchant
    label: str                   # 展示文字 "灵蝠巢穴"
    detail: int = 0              # 预览详细度 0=完整 1=模糊
    generated: bool = False      # 是否已生成具体效果
    result: str = "{}"           # 走过后记录结果 (JSON)

    def get_result(self) -> dict:
        try:
            return json.loads(self.result)
        except:
            return {}

    def set_result(self, data: dict):
        self.result = json.dumps(data, ensure_ascii=False)

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "node_type": self.node_type,
            "label": self.label,
            "detail": self.detail,
            "generated": self.generated,
            "result": self.result,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DungeonNode":
        return cls(
            step=d.get("step", 1),
            node_type=d.get("node_type", "nothing"),
            label=d.get("label", ""),
            detail=d.get("detail", 0),
            generated=d.get("generated", False),
            result=d.get("result", "{}"),
        )


@dataclass
class DungeonCycle:
    """秘境一个 1-2-2 周期（从合并点到下一个合并点）"""
    cycle_index: int             # 第几个周期 (0-based)
    depth_start: int             # 起始深度
    path_a: str = "[]"           # JSON: 3个 DungeonNode
    path_b: str = "[]"           # JSON: 3个 DungeonNode

    def get_path_a(self) -> list:
        try:
            return [DungeonNode.from_dict(n) for n in json.loads(self.path_a)]
        except:
            return []

    def set_path_a(self, nodes: list):
        self.path_a = json.dumps([n.to_dict() for n in nodes], ensure_ascii=False)

    def get_path_b(self) -> list:
        try:
            return [DungeonNode.from_dict(n) for n in json.loads(self.path_b)]
        except:
            return []

    def set_path_b(self, nodes: list):
        self.path_b = json.dumps([n.to_dict() for n in nodes], ensure_ascii=False)

    def to_dict(self) -> dict:
        return {
            "cycle_index": self.cycle_index,
            "depth_start": self.depth_start,
            "path_a": self.path_a,
            "path_b": self.path_b,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DungeonCycle":
        return cls(
            cycle_index=d.get("cycle_index", 0),
            depth_start=d.get("depth_start", 0),
            path_a=d.get("path_a", "[]"),
            path_b=d.get("path_b", "[]"),
        )


@dataclass
class DungeonRun:
    """一次秘境副本的完整状态"""
    user_id: str = ""
    dungeon_key: str = ""
    depth: int = 0               # 当前深度（已走过的步数）
    stamina: int = 0             # 当前秘境灵力
    max_stamina: int = 0         # 初始总灵力
    hp: int = 0                  # 副本内当前血量
    max_hp: int = 0              # 副本内最大血量
    overdraft_count: int = 0     # 透支次数
    inventory: str = "{}"        # JSON: 副本内临时背包 {item_name: count, ...lingshi: N, exp: N}
    log: str = "[]"              # JSON: 已完成节点记录
    current_cycle: str = "{}"    # JSON: 当前周期 DungeonCycle（旧版兼容）
    chosen_path: str = ""        # "A" or "B"（旧版兼容）
    step_in_cycle: int = 0       # 旧版兼容
    state: str = "choosing"      # choosing/walking/boss/done
    map_graph: str = "{}"        # JSON: 树形地图 {"nodes": [...], "edges": [...]}
    current_node_id: str = ""    # 当前所在节点ID
    daily_reward_earned: int = 0 # 本次副本已获得的灵石奖励（用于每日上限计算）
    daily_exp_earned: int = 0    # 本次副本已获得的修为奖励
    create_time: int = 0
    expire_time: int = 0

    def get_inventory(self) -> dict:
        try:
            return json.loads(self.inventory)
        except:
            return {}

    def set_inventory(self, data: dict):
        self.inventory = json.dumps(data, ensure_ascii=False)

    def get_log(self) -> list:
        try:
            return json.loads(self.log)
        except:
            return []

    def add_log(self, entry: dict):
        log_list = self.get_log()
        log_list.append(entry)
        self.log = json.dumps(log_list, ensure_ascii=False)

    def get_current_cycle(self) -> "DungeonCycle":
        try:
            return DungeonCycle.from_dict(json.loads(self.current_cycle))
        except:
            return DungeonCycle(cycle_index=0, depth_start=0)

    def set_current_cycle(self, cycle: "DungeonCycle"):
        self.current_cycle = json.dumps(cycle.to_dict(), ensure_ascii=False)

    def get_map_graph(self) -> dict:
        try:
            return json.loads(self.map_graph)
        except:
            return {}

    def set_map_graph(self, data: dict):
        self.map_graph = json.dumps(data, ensure_ascii=False)

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "dungeon_key": self.dungeon_key,
            "depth": self.depth,
            "stamina": self.stamina,
            "max_stamina": self.max_stamina,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "overdraft_count": self.overdraft_count,
            "inventory": self.inventory,
            "log": self.log,
            "current_cycle": self.current_cycle,
            "chosen_path": self.chosen_path,
            "step_in_cycle": self.step_in_cycle,
            "state": self.state,
            "map_graph": self.map_graph,
            "current_node_id": self.current_node_id,
            "daily_reward_earned": self.daily_reward_earned,
            "daily_exp_earned": self.daily_exp_earned,
            "create_time": self.create_time,
            "expire_time": self.expire_time,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DungeonRun":
        return cls(
            user_id=d.get("user_id", ""),
            dungeon_key=d.get("dungeon_key", ""),
            depth=d.get("depth", 0),
            stamina=d.get("stamina", 0),
            max_stamina=d.get("max_stamina", 0),
            hp=d.get("hp", 0),
            max_hp=d.get("max_hp", 0),
            overdraft_count=d.get("overdraft_count", 0),
            inventory=d.get("inventory", "{}"),
            log=d.get("log", "[]"),
            current_cycle=d.get("current_cycle", "{}"),
            chosen_path=d.get("chosen_path", ""),
            step_in_cycle=d.get("step_in_cycle", 0),
            state=d.get("state", "choosing"),
            map_graph=d.get("map_graph", "{}"),
            current_node_id=d.get("current_node_id", ""),
            daily_reward_earned=d.get("daily_reward_earned", 0),
            daily_exp_earned=d.get("daily_exp_earned", 0),
            create_time=d.get("create_time", 0),
            expire_time=d.get("expire_time", 0),
        )
