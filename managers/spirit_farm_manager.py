# managers/spirit_farm_manager.py
"""灵田系统管理器 — nonebot 迁移版（收取模型）"""
import json
import random
from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict, List, TYPE_CHECKING
from ..data import DataBase
from ..models import Player

if TYPE_CHECKING:
    from ..core import StorageRingManager
    from ..config_manager import ConfigManager

__all__ = ["SpiritFarmManager"]

# 灵田开垦配置（每级+1块灵田，起始1块，最高6块）
FIELD_UPGRADE_COSTS = {
    1: 3_500_000,
    2: 5_000_000,
    3: 7_000_000,
    4: 10_000_000,
    5: 15_000_000,
}

# 收取等级升级配置（消耗炼丹经验）
HARVEST_LEVEL_COSTS = {
    1: 1500,
    2: 3000,
    3: 6000,
}

# 丹药控火等级升级配置（消耗炼丹经验）
FIRE_CONTROL_COSTS = {
    1: 1000,
    2: 4000,
}

# 收取冷却基础时间（秒）
BASE_HARVEST_COOLDOWN = 48 * 3600  # 48小时


class SpiritFarmManager:
    """灵田管理器（收取模型）"""

    def __init__(
        self,
        db: DataBase,
        config_manager: "ConfigManager" = None,
        storage_ring_manager: "StorageRingManager" = None,
        activity_tracker=None,
    ):
        self.db = db
        self.config_manager = config_manager
        self.storage_ring_manager = storage_ring_manager
        self.activity_tracker = activity_tracker

    # ── 数据库操作 ──

    async def _ensure_table(self):
        """确保 spirit_farms 表存在"""
        await self.db.conn.execute(
            """CREATE TABLE IF NOT EXISTS spirit_farms (
                user_id TEXT PRIMARY KEY,
                farm_level INTEGER DEFAULT 1,
                herb_fields INTEGER DEFAULT 1,
                harvest_level INTEGER DEFAULT 0,
                harvest_speed INTEGER DEFAULT 0,
                last_harvest_time TEXT DEFAULT '',
                alchemy_exp INTEGER DEFAULT 0,
                fire_control INTEGER DEFAULT 0
            )"""
        )
        await self.db.conn.commit()

    async def get_user_farm(self, user_id: str) -> Optional[Dict]:
        """获取用户灵田信息"""
        await self._ensure_table()
        async with self.db.conn.execute(
            "SELECT * FROM spirit_farms WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def _update_farm(self, user_id: str, **kwargs):
        """更新灵田字段"""
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        vals = list(kwargs.values()) + [user_id]
        await self.db.conn.execute(
            f"UPDATE spirit_farms SET {sets} WHERE user_id = ?", vals
        )
        await self.db.conn.commit()

    # ── 核心功能 ──

    async def create_farm(self, player: Player) -> Tuple[bool, str]:
        """开垦灵田"""
        existing = await self.get_user_farm(player.user_id)
        if existing:
            return False, "❌ 你已经拥有灵田了！发送 /灵田 查看"

        cost = 2_000_000
        if player.gold < cost:
            return False, f"❌ 开垦灵田需要 {cost:,} 灵石"

        player.gold -= cost
        await self.db.update_player(player)

        await self._ensure_table()
        await self.db.conn.execute(
            "INSERT INTO spirit_farms (user_id) VALUES (?)",
            (player.user_id,),
        )
        await self.db.conn.commit()

        return True, (
            "🌱 灵田开垦成功！\n"
            "━━━━━━━━━━━━━━━\n"
            "灵田数量：1 块\n"
            "收取等级：Lv.0\n"
            "━━━━━━━━━━━━━━━\n"
            "💡 发送 /灵田收取 获取药材\n"
            "💡 发送 /灵田开垦 扩展灵田"
        )

    async def upgrade_fields(self, player: Player) -> Tuple[bool, str]:
        """扩展灵田数量（每级+1块）"""
        farm = await self.get_user_farm(player.user_id)
        if not farm:
            return False, "❌ 你还没有灵田！发送 /开垦灵田"

        current_fields = farm["herb_fields"]
        if current_fields >= 6:
            return False, "❌ 灵田已达最大数量（6块）！"

        cost = FIELD_UPGRADE_COSTS.get(current_fields, 15_000_000)
        if player.gold < cost:
            return False, f"❌ 扩展灵田需要 {cost:,} 灵石"

        player.gold -= cost
        await self.db.update_player(player)
        await self._update_farm(player.user_id, herb_fields=current_fields + 1)

        return True, f"🎉 灵田扩展成功！当前 {current_fields + 1} 块灵田"

    async def upgrade_harvest_level(self, player: Player) -> Tuple[bool, str]:
        """升级收取等级（消耗炼丹经验）"""
        farm = await self.get_user_farm(player.user_id)
        if not farm:
            return False, "❌ 你还没有灵田！"

        current = farm["harvest_level"]
        if current >= 3:
            return False, "❌ 收取等级已达最高（Lv.3）！"

        cost = HARVEST_LEVEL_COSTS.get(current + 1, 6000)
        if farm["alchemy_exp"] < cost:
            return False, f"❌ 升级需要 {cost} 炼丹经验，当前仅有 {farm['alchemy_exp']}"

        await self._update_farm(
            player.user_id,
            harvest_level=current + 1,
            alchemy_exp=farm["alchemy_exp"] - cost,
        )
        return True, f"🎉 收取等级升级到 Lv.{current + 1}！每次收取 +1 药材"

    async def upgrade_fire_control(self, player: Player) -> Tuple[bool, str]:
        """升级丹药控火等级（消耗炼丹经验）"""
        farm = await self.get_user_farm(player.user_id)
        if not farm:
            return False, "❌ 你还没有灵田！"

        current = farm["fire_control"]
        if current >= 2:
            return False, "❌ 丹药控火已达最高（Lv.2）！"

        cost = FIRE_CONTROL_COSTS.get(current + 1, 4000)
        if farm["alchemy_exp"] < cost:
            return False, f"❌ 升级需要 {cost} 炼丹经验，当前仅有 {farm['alchemy_exp']}"

        await self._update_farm(
            player.user_id,
            fire_control=current + 1,
            alchemy_exp=farm["alchemy_exp"] - cost,
        )
        return True, f"🎉 丹药控火升级到 Lv.{current + 1}！每次炼丹 +1 出丹数"

    def get_harvest_cooldown_seconds(self, farm: Dict) -> int:
        """获取收取冷却时间（秒）"""
        speed = farm.get("harvest_speed", 0)
        return int(BASE_HARVEST_COOLDOWN * (1 - 0.05 * speed))

    def get_harvest_remaining(self, farm: Dict) -> int:
        """获取收取剩余冷却秒数，0=可收取"""
        last = farm.get("last_harvest_time", "")
        if not last:
            return 0
        try:
            last_time = datetime.strptime(last, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return 0
        elapsed = (datetime.now() - last_time).total_seconds()
        cooldown = self.get_harvest_cooldown_seconds(farm)
        return max(0, int(cooldown - elapsed))

    async def harvest(self, player: Player, config_manager: "ConfigManager" = None) -> Tuple[bool, str]:
        """收取药材"""
        farm = await self.get_user_farm(player.user_id)
        if not farm:
            return False, "❌ 你还没有灵田！发送 /开垦灵田"

        remaining = self.get_harvest_remaining(farm)
        if remaining > 0:
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            return False, f"⏳ 收取冷却中，还需 {hours}小时{minutes}分"

        # 计算收取数量
        herb_fields = farm["herb_fields"]
        harvest_level = farm["harvest_level"]

        # 读取功法采集加成
        technique_harvest_bonus = 0
        if player.main_technique and config_manager:
            tech_data = config_manager.items_data.get(player.main_technique)
            if tech_data:
                technique_harvest_bonus = int(tech_data.get("harvest_bonus", 0))

        num = herb_fields + harvest_level + technique_harvest_bonus
        num = max(1, num)

        # 获取可收取的药材池（根据玩家境界 rank 过滤）
        herbs_data = (config_manager or self.config_manager).herbs_data if (config_manager or self.config_manager) else {}
        player_rank = self._get_player_harvest_rank(player)

        eligible_herbs = []
        for herb_id, herb in herbs_data.items():
            if herb.get("rank", 0) >= player_rank:
                eligible_herbs.append(herb_id)

        if not eligible_herbs:
            # fallback：至少给恒心草
            eligible_herbs = [hid for hid, h in herbs_data.items() if h.get("name") == "恒心草"]
            if not eligible_herbs:
                eligible_herbs = list(herbs_data.keys())[:1]

        # 随机抽取药材
        herb_counts: Dict[str, int] = {}
        for _ in range(num):
            herb_id = random.choice(eligible_herbs)
            herb_name = herbs_data[herb_id]["name"]
            herb_counts[herb_name] = herb_counts.get(herb_name, 0) + 1

        # 存入储物戒
        stored_items = []
        if self.storage_ring_manager:
            for herb_name, count in herb_counts.items():
                success, _ = await self.storage_ring_manager.store_item(
                    player, herb_name, count, silent=True
                )
                if success:
                    stored_items.append(f"{herb_name}×{count}")
                else:
                    stored_items.append(f"{herb_name}×{count}（储物戒已满）")

        # 更新收取时间
        await self._update_farm(
            player.user_id,
            last_harvest_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        # 活跃度追踪
        if self.activity_tracker:
            try:
                await self.activity_tracker.track_harvest(player)
            except Exception:
                pass

        # 构建消息
        cooldown_hours = self.get_harvest_cooldown_seconds(farm) // 3600
        msg_lines = [
            "🌾 灵田收取结果",
            "━━━━━━━━━━━━━━━",
            f"收取数量：{num}（灵田{herb_fields} + 等级{harvest_level} + 功法{technique_harvest_bonus}）",
        ]
        if stored_items:
            msg_lines.append("📦 存入储物戒：")
            for item in stored_items:
                msg_lines.append(f"  {item}")
        msg_lines.append("━━━━━━━━━━━━━━━")
        msg_lines.append(f"⏰ 下次收取：{cooldown_hours}小时后")

        return True, "\n".join(msg_lines)

    def _get_player_harvest_rank(self, player: Player) -> int:
        """根据玩家境界返回药材 rank 阈值（越低越高级）"""
        # nonebot 的 rank 系统：rank 越小 = 境界越高 = 能收取越稀有的药材
        # 简单映射：level_index 越大 → rank 阈值越低
        level_index = player.level_index
        if level_index >= 35:
            return 20  # 混元先天 → 几乎所有药材
        elif level_index >= 32:
            return 24
        elif level_index >= 28:
            return 28
        elif level_index >= 22:
            return 32
        elif level_index >= 16:
            return 36
        elif level_index >= 13:
            return 40
        elif level_index >= 12:
            return 44
        elif level_index >= 10:
            return 48
        else:
            return 54  # 最低境界 → 只能收一品药材

    async def add_alchemy_exp(self, user_id: str, exp: int):
        """增加炼丹经验"""
        farm = await self.get_user_farm(user_id)
        if farm:
            await self._update_farm(
                user_id, alchemy_exp=farm["alchemy_exp"] + exp
            )

    async def get_farm_info(self, user_id: str, config_manager: "ConfigManager" = None) -> str:
        """获取灵田信息展示"""
        farm = await self.get_user_farm(user_id)
        if not farm:
            return (
                "🌾 灵田系统\n"
                "━━━━━━━━━━━━━━━\n"
                "你还没有灵田！\n"
                f"开垦费用：2,000,000 灵石\n\n"
                "💡 使用 /开垦灵田"
            )

        remaining = self.get_harvest_remaining(farm)
        cooldown_total = self.get_harvest_cooldown_seconds(farm)

        if remaining > 0:
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            status = f"⏳ 冷却中（{hours}小时{minutes}分）"
        else:
            status = "✅ 可收取"

        # 读取功法加成
        technique_harvest_bonus = 0
        cm = config_manager or self.config_manager
        # 需要从 player 查 main_technique，这里简化为 0
        # 实际在 harvest 中会读取

        next_field_cost = FIELD_UPGRADE_COSTS.get(farm["herb_fields"], "已满")

        lines = [
            f"🌾 我的灵田",
            "━━━━━━━━━━━━━━━",
            f"灵田数量：{farm['herb_fields']} 块",
            f"收取等级：Lv.{farm['harvest_level']}",
            f"丹药控火：Lv.{farm['fire_control']}",
            f"药材速度：{farm['harvest_speed']}",
            f"炼丹经验：{farm['alchemy_exp']}",
            f"收取状态：{status}",
            f"冷却时间：{cooldown_total // 3600}小时",
            "━━━━━━━━━━━━━━━",
            f"下次扩展费用：{next_field_cost:,} 灵石" if isinstance(next_field_cost, int) else "灵田已满",
            "",
            "💡 /灵田收取 | /灵田开垦 | /升级收取 | /升级控火",
        ]

        return "\n".join(lines)
