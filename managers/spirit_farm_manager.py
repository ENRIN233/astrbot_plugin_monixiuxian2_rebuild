# managers/spirit_farm_manager.py
"""灵植园系统管理器 v2 — 逐块地块（播种/生长/枯萎）+ 偷菜 + 护园灵兽 + 园圃等级

设计文档: docs/superpowers/specs/2026-09-21-spirit-garden-v2-design.md (v1.2)

v2 核心规则:
- 地块模型: 每块田独立 plots JSON，状态惰性推导（空地→24h 自动野生→48h 成熟→过熟枯萎→枯死）
- 播种: /灵田播种 <药名> [数量]，数量可省略(=1)/数字/全部；种子钱=灵石 sink
- 收取: 收全部成熟地块；产量 = 地块基础产量 × 枯萎系数 − 被偷数（保底 1）+ 收取等级/功法加成
- 催熟: 全部生长中种植地块推至成熟，费用 = 剩余时长 × 10万/h，最低 15 万
- 偷菜: 纯娱乐玩法（v1.2 定案），不接入因果；每日偷 3 次/被偷 5 次；护园灵兽拦截罚款 5:5 分账
- 园圃等级: 播种 +5/块、收取 +10/次；Lv2 完美窗口+6h / Lv3 野生免疫枯萎 / Lv4 产量+10% / Lv5 10% 双倍
"""
import json
import math
import random
from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict, List, TYPE_CHECKING
from ..data import DataBase
from ..models import Player

try:
    from astrbot.api import logger
except ImportError:  # 测试环境
    import logging
    logger = logging.getLogger(__name__)

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

# 旧收取冷却基础时间（秒）——v2 已由地块驱动，仅迁移折算语义保留
BASE_HARVEST_COOLDOWN = 48 * 3600  # 48小时

_GARDEN_CROPS_FALLBACK = {
    "tiers": [
        {"tier": 1, "label": "凡品", "rank_min": 48, "rank_max": 999, "growth_hours": 12, "seed_cost": 50000, "yield_min": 1, "yield_max": 2, "perfect_window_hours": 24, "wither_step_pct": 25},
        {"tier": 2, "label": "良品", "rank_min": 40, "rank_max": 47, "growth_hours": 24, "seed_cost": 250000, "yield_min": 2, "yield_max": 2, "perfect_window_hours": 24, "wither_step_pct": 25},
        {"tier": 3, "label": "珍品", "rank_min": 32, "rank_max": 39, "growth_hours": 24, "seed_cost": 800000, "yield_min": 2, "yield_max": 3, "perfect_window_hours": 18, "wither_step_pct": 25},
        {"tier": 4, "label": "灵品", "rank_min": 24, "rank_max": 31, "growth_hours": 36, "seed_cost": 2000000, "yield_min": 3, "yield_max": 3, "perfect_window_hours": 18, "wither_step_pct": 30},
        {"tier": 5, "label": "仙品", "rank_min": 0, "rank_max": 23, "growth_hours": 48, "seed_cost": 5000000, "yield_min": 3, "yield_max": 4, "perfect_window_hours": 12, "wither_step_pct": 30},
    ],
    "wild_growth_hours": 48,
    "wild_perfect_window_hours": 24,
    "wild_yield_min": 1,
    "wild_yield_max": 1,
    "empty_to_wild_hours": 24,
    "ripen_cost_per_hour": 100000,
    "ripen_cost_min": 150000,
    "dead_after_overripe_hours": 48,
    "wither_floor_pct": 40,
    "steal_limit_thief": 3,
    "steal_limit_victim": 5,
    "steal_fine": 500000,
    "beast_costs": [0, 3000000, 2000000, 5000000],
    "beast_rates": [0.0, 0.15, 0.25, 0.35],
    "garden_exp_sow_per_plot": 5,
    "garden_exp_harvest": 10,
    "garden_levels": [
        {"level": 1, "exp": 0, "max_tier": 1, "perks": []},
        {"level": 2, "exp": 200, "max_tier": 2, "perks": ["perfect_plus6"]},
        {"level": 3, "exp": 600, "max_tier": 3, "perks": ["wild_no_wither"]},
        {"level": 4, "exp": 1500, "max_tier": 4, "perks": ["yield_plus10"]},
        {"level": 5, "exp": 3000, "max_tier": 5, "perks": ["double_chance"]},
    ],
}


def _parse_dt(s: str) -> Optional[datetime]:
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


class SpiritFarmManager:
    """灵植园管理器 v2（逐块地块模型）"""

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
        self.crops_cfg = dict(_GARDEN_CROPS_FALLBACK)
        if config_manager is not None and getattr(config_manager, "garden_crops", None):
            self.crops_cfg.update(config_manager.garden_crops)

    # ── 数据库 ──

    async def _ensure_table(self):
        """确保 spirit_farms 表存在（含 v43 灵植园列）"""
        await self.db.conn.execute(
            """CREATE TABLE IF NOT EXISTS spirit_farms (
                user_id TEXT PRIMARY KEY,
                farm_level INTEGER DEFAULT 1,
                herb_fields INTEGER DEFAULT 1,
                harvest_level INTEGER DEFAULT 0,
                harvest_speed INTEGER DEFAULT 0,
                last_harvest_time TEXT DEFAULT '',
                alchemy_exp INTEGER DEFAULT 0,
                fire_control INTEGER DEFAULT 0,
                plots TEXT DEFAULT '[]',
                garden_exp INTEGER DEFAULT 0,
                garden_level INTEGER DEFAULT 1,
                beast_level INTEGER DEFAULT 0,
                steal_out_date TEXT DEFAULT '',
                steal_out_count INTEGER DEFAULT 0,
                steal_in_date TEXT DEFAULT '',
                steal_in_count INTEGER DEFAULT 0,
                grudge_log TEXT DEFAULT '[]'
            )"""
        )
        # 旧库补列（v43 前创建的表）
        async with self.db.conn.execute("PRAGMA table_info(spirit_farms)") as cursor:
            cols = {row[1] for row in await cursor.fetchall()}
        for col, typedef, default in [
            ("plots", "TEXT", "'[]'"),
            ("garden_exp", "INTEGER", "0"),
            ("garden_level", "INTEGER", "1"),
            ("beast_level", "INTEGER", "0"),
            ("steal_out_date", "TEXT", "''"),
            ("steal_out_count", "INTEGER", "0"),
            ("steal_in_date", "TEXT", "''"),
            ("steal_in_count", "INTEGER", "0"),
            ("grudge_log", "TEXT", "'[]'"),
        ]:
            if col not in cols:
                try:
                    await self.db.conn.execute(
                        f"ALTER TABLE spirit_farms ADD COLUMN {col} {typedef} DEFAULT {default}"
                    )
                except Exception:
                    pass
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

    # ── 作物/园圃配置读取 ──

    def _tiers(self) -> List[dict]:
        return self.crops_cfg.get("tiers", [])

    def _tier_of_herb(self, rank: int) -> Optional[dict]:
        for t in self._tiers():
            if t["rank_min"] <= rank <= t["rank_max"]:
                return t
        return None

    def _garden_level_def(self, level: int) -> dict:
        for g in self.crops_cfg.get("garden_levels", []):
            if g["level"] == level:
                return g
        return self.crops_cfg["garden_levels"][0]

    def get_garden_level(self, farm: Dict) -> int:
        return int(farm.get("garden_level", 1) or 1)

    def _has_perk(self, farm: Dict, perk: str) -> bool:
        gdef = self._garden_level_def(self.get_garden_level(farm))
        return perk in gdef.get("perks", [])

    # ── 地块状态推导（惰性，无后台任务）──

    def _derive_plot_state(self, plot: Dict, garden_level: int, now: Optional[datetime] = None) -> Dict:
        """按 planted_at + growth_hours 推导地块当前状态

        返回: {state, progress(0~1), hours_to_mature, wither_mult, dead}
        state: empty / growing / mature / overripe / dead
        """
        now = now or datetime.now()
        mode = plot.get("mode", "wild")
        if mode == "empty":
            return {"state": "empty", "progress": 0.0, "wither_mult": 1.0, "dead": False}

        planted = _parse_dt(plot.get("planted_at", ""))
        if not planted:
            return {"state": "empty", "progress": 0.0, "wither_mult": 1.0, "dead": False}

        growth_hours = float(plot.get("growth_hours", 48))
        perfect_hours = float(plot.get("perfect_window_hours", 24))
        # 园圃 Lv2 perk：完美窗口 +6h
        if self._has_perk({"garden_level": garden_level}, "perfect_plus6"):
            perfect_hours += 6.0

        elapsed_h = (now - planted).total_seconds() / 3600.0
        mature_at = growth_hours

        # 野生免疫枯萎（园圃 Lv3 perk）
        wild_immune = (mode == "wild" and self._has_perk({"garden_level": garden_level}, "wild_no_wither"))

        progress = min(1.0, elapsed_h / mature_at) if mature_at > 0 else 1.0

        if elapsed_h < mature_at:
            return {"state": "growing", "progress": progress,
                    "hours_to_mature": mature_at - elapsed_h, "wither_mult": 1.0, "dead": False}

        if wild_immune:
            return {"state": "mature", "progress": 1.0, "wither_mult": 1.0, "dead": False}

        overripe_h = elapsed_h - mature_at
        dead_after = perfect_hours + float(self.crops_cfg.get("dead_after_overripe_hours", 48))
        if overripe_h > dead_after:
            return {"state": "dead", "progress": 1.0, "wither_mult": 0.0, "dead": True}

        if overripe_h <= perfect_hours:
            # 仍在完美窗口内
            return {"state": "mature", "progress": 1.0, "wither_mult": 1.0, "dead": False}

        # 过熟：完美期结束后每 12h −wither_step%，下限 wither_floor%
        step = float(plot.get("wither_step_pct", 25)) / 100.0
        steps = int((overripe_h - perfect_hours) // 12.0)
        wither_mult = max(
            float(self.crops_cfg.get("wither_floor_pct", 40)) / 100.0,
            1.0 - steps * step,
        )
        return {"state": "mature" if wither_mult >= 1.0 else "overripe",
                "progress": 1.0, "wither_mult": wither_mult, "dead": False}

    def _refresh_plots(self, farm: Dict, player: Optional[Player] = None) -> List[Dict]:
        """惰性刷新地块列表：空地超时自动野生 / 野生定名 / 结果写入 farm["_plots"]"""
        now = datetime.now()
        try:
            plots = json.loads(farm.get("plots") or "[]")
        except json.JSONDecodeError:
            plots = []
        fields = int(farm.get("herb_fields", 1) or 1)

        by_slot = {p.get("slot"): p for p in plots if isinstance(p, dict)}
        changed = False
        result: List[Dict] = []

        for slot in range(1, fields + 1):
            plot = by_slot.get(slot)
            if plot is None:
                # 空地登记空置起点
                plot = {"slot": slot, "mode": "empty", "planted_at": now.strftime("%Y-%m-%d %H:%M:%S")}
                by_slot[slot] = plot
                result.append(plot)
                changed = True
                continue

            mode = plot.get("mode", "wild")
            planted = _parse_dt(plot.get("planted_at", "")) or now
            empty_hours = float(self.crops_cfg.get("empty_to_wild_hours", 24))

            if mode == "empty":
                if (now - planted).total_seconds() / 3600.0 >= empty_hours:
                    # 自动野生：从现在起生长
                    plot = {
                        "slot": slot, "mode": "wild", "herb_id": "auto", "herb_name": "",
                        "planted_at": now.strftime("%Y-%m-%d %H:%M:%S"),
                        "growth_hours": float(self.crops_cfg.get("wild_growth_hours", 48)),
                        "perfect_window_hours": float(self.crops_cfg.get("wild_perfect_window_hours", 24)),
                        "wither_step_pct": 25, "yield_min": int(self.crops_cfg.get("wild_yield_min", 1)),
                        "yield_max": int(self.crops_cfg.get("wild_yield_max", 1)), "yield_stolen": 0,
                    }
                    by_slot[slot] = plot
                    changed = True
                result.append(plot)
                continue

            # 野生地块定名（查看/被偷/收取前需要名字）：从玩家境界池随机
            if mode == "wild" and not plot.get("herb_name") and player is not None and self.config_manager:
                herbs_data = getattr(self.config_manager, "herbs_data", {}) or {}
                rank_threshold = self._get_player_harvest_rank(player)
                pool = [name for name, h in herbs_data.items() if int(h.get("rank", 99)) >= rank_threshold] or list(herbs_data.keys())
                if pool:
                    plot["herb_name"] = random.choice(pool)
                    changed = True

            result.append(plot)

        result.sort(key=lambda p: p.get("slot", 0))
        farm["_plots"] = result
        farm["_plots_changed"] = changed
        return result

    async def _save_plots(self, user_id: str, plots: List[Dict]):
        await self._update_farm(user_id, plots=json.dumps(plots, ensure_ascii=False))

    # ── 玩家境界 → rank 阈值 ──

    def _get_player_harvest_rank(self, player: Player) -> int:
        """根据玩家境界返回药材 rank 阈值（越低越高级）"""
        level_index = player.level_index
        if level_index >= 35:
            return 20
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
            return 54

    # ── 基础功能（v1 接口保留）──

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
            "园圃等级：Lv.1\n"
            "━━━━━━━━━━━━━━━\n"
            "💡 发送 /灵田 查看（空地 24h 后自动长出野生灵草）\n"
            "💡 /灵田播种 <药名> [数量] 可自选作物\n"
            "💡 /灵田开垦 扩展灵田"
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

    # ── v2 播种 ──

    async def sow(self, player: Player, herb_name: str, count_expr: str = "1") -> Tuple[bool, str]:
        """播种：/灵田播种 <药名> [数量]（数量=数字或 全部/all，默认1）"""
        farm = await self.get_user_farm(player.user_id)
        if not farm:
            return False, "❌ 你还没有灵田！发送 /开垦灵田"

        herb_name = (herb_name or "").strip()
        if not herb_name:
            return False, "💡 用法：/灵田播种 <药材名> [数量|全部]，如 /灵田播种 血琥珀 3"

        herbs_data = getattr(self.config_manager, "herbs_data", {}) or {}
        herb = herbs_data.get(herb_name)
        if not herb:
            return False, f"❌ 没有名为「{herb_name}」的药材，请检查名称（播种可用境界内药材名）"

        rank = int(herb.get("rank", 99))
        tier = self._tier_of_herb(rank)
        if not tier:
            return False, f"❌「{herb_name}」暂不支持播种。"

        garden_level = self.get_garden_level(farm)
        gdef = self._garden_level_def(garden_level)
        if tier["tier"] > int(gdef.get("max_tier", 1)):
            return False, f"❌「{herb_name}」为{tier['label']}灵植，需园圃 Lv.{tier['tier']}（当前 Lv.{garden_level}）"

        player_rank = self._get_player_harvest_rank(player)
        if rank < player_rank:
            return False, f"❌ 你的境界尚无法驾驭「{herb_name}」此等灵植。"

        plots = self._refresh_plots(farm, player)
        empty_slots = [p for p in plots if p.get("mode") == "empty"]
        if not empty_slots:
            return False, "❌ 没有空地。等待收获或 /灵田清理 枯死地块。"

        expr = (count_expr or "1").strip().lower()
        capped_note = ""
        if expr in ("全部", "all", "全"):
            count = len(empty_slots)
        else:
            try:
                count = max(1, int(expr))
            except ValueError:
                return False, f"❌ 数量参数无效：{count_expr}（请输入数字或 全部）"

        if count > len(empty_slots):
            count = len(empty_slots)
            capped_note = f"（空地不足，实际播种 {count} 块）"

        total_cost = int(tier["seed_cost"]) * count
        if player.gold < total_cost:
            return False, f"❌ 种子需要 {total_cost:,} 灵石（{tier['seed_cost']:,}/块 × {count}），你只有 {player.gold:,}"

        player.gold -= total_cost
        await self.db.update_player(player)

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for plot in empty_slots[:count]:
            plot.update({
                "mode": "planted", "herb_id": herb_name, "herb_name": herb_name,
                "planted_at": now_str,
                "growth_hours": float(tier["growth_hours"]),
                "perfect_window_hours": float(tier["perfect_window_hours"]),
                "wither_step_pct": int(tier["wither_step_pct"]),
                "yield_min": int(tier["yield_min"]), "yield_max": int(tier["yield_max"]),
                "yield_stolen": 0,
            })

        # 园圃经验：每块 +5
        gained_exp = int(self.crops_cfg.get("garden_exp_sow_per_plot", 5)) * count
        new_exp = int(farm.get("garden_exp", 0)) + gained_exp
        new_level = self._level_from_exp(new_exp)

        await self._save_plots(player.user_id, plots)
        await self._update_farm(player.user_id, garden_exp=new_exp, garden_level=new_level)

        level_note = f"\n🎉 园圃升级到 Lv.{new_level}！" if new_level > garden_level else ""
        return True, (
            f"🌱 播种成功！{capped_note}\n"
            "━━━━━━━━━━━━━━━\n"
            f"作物：{herb_name}（{tier['label']}）× {count} 块\n"
            f"种子花费：{total_cost:,} 灵石\n"
            f"生长时长：{tier['growth_hours']} 小时\n"
            f"灵植经验：+{gained_exp}（{new_exp}）{level_note}\n"
            "━━━━━━━━━━━━━━━\n"
            "💡 成熟后 /灵田收取；长时间不收会过熟减产"
        )

    def _level_from_exp(self, exp: int) -> int:
        level = 1
        for g in self.crops_cfg.get("garden_levels", []):
            if exp >= int(g.get("exp", 0)):
                level = int(g["level"])
        return level

    # ── v2 收取 ──

    async def harvest(self, player: Player, config_manager: "ConfigManager" = None) -> Tuple[bool, str]:
        """收取全部成熟地块（含野生），未成熟不动"""
        farm = await self.get_user_farm(player.user_id)
        if not farm:
            return False, "❌ 你还没有灵田！发送 /开垦灵田"

        cm = config_manager or self.config_manager
        plots = self._refresh_plots(farm, player)
        garden_level = self.get_garden_level(farm)

        mature_plots = []
        for p in plots:
            if p.get("mode") == "empty":
                continue
            st = self._derive_plot_state(p, garden_level)
            if st["state"] in ("mature", "overripe") and not st["dead"]:
                mature_plots.append((p, st))

        if not mature_plots:
            return False, "❌ 目前没有成熟的地块。/灵田 查看生长进度。"

        herb_counts: Dict[str, int] = {}
        for plot, st in mature_plots:
            base = random.randint(int(plot.get("yield_min", 1)), int(plot.get("yield_max", 1)))
            amount = base * st["wither_mult"]
            stolen = int(plot.get("yield_stolen", 0))
            amount = max(1, int(round(amount)) - stolen)
            # 园圃 Lv4：全田产量 +10%
            if self._has_perk(farm, "yield_plus10"):
                amount = max(1, int(round(amount * 1.1)))
            # 园圃 Lv5：10% 概率双倍
            if self._has_perk(farm, "double_chance") and random.random() < 0.10:
                amount *= 2
            herb_name = plot.get("herb_name") or "恒心草"
            herb_counts[herb_name] = herb_counts.get(herb_name, 0) + amount

        # 全田加成：收取等级 + 功法 harvest_bonus（加成株按境界池随机补入）
        technique_bonus = 0
        if player.main_technique and cm:
            tech_data = (getattr(cm, "herbs_data", {}) or {}).get(player.main_technique)
            if tech_data:
                technique_bonus = int(tech_data.get("harvest_bonus", 0))
        bonus_num = int(farm.get("harvest_level", 0)) + technique_bonus
        if bonus_num > 0:
            herbs_data = getattr(cm, "herbs_data", {}) or {}
            player_rank = self._get_player_harvest_rank(player)
            pool = [name for name, h in herbs_data.items() if int(h.get("rank", 99)) >= player_rank] or list(herbs_data.keys())[:1]
            for _ in range(bonus_num):
                bonus_name = random.choice(pool) if pool else "恒心草"
                herb_counts[bonus_name] = herb_counts.get(bonus_name, 0) + 1

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

        # 收取后地块回到空地（登记空置起点，24h 后自动野生）
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        old_level = garden_level
        for plot, _ in mature_plots:
            slot = plot.get("slot", 0)
            plot.clear()
            plot.update({"slot": slot, "mode": "empty", "planted_at": now_str})

        # 园圃经验 +10
        gained_exp = int(self.crops_cfg.get("garden_exp_harvest", 10))
        new_exp = int(farm.get("garden_exp", 0)) + gained_exp
        new_level = self._level_from_exp(new_exp)

        await self._save_plots(player.user_id, plots)
        await self._update_farm(player.user_id, garden_exp=new_exp, garden_level=new_level,
                                last_harvest_time=now_str)

        # 活跃度追踪
        if self.activity_tracker:
            try:
                await self.activity_tracker.track_harvest(player)
            except Exception:
                pass

        level_note = f"\n🎉 园圃升级到 Lv.{new_level}！" if new_level > old_level else ""
        total = sum(herb_counts.values())
        msg_lines = [
            "🌾 灵田收取结果",
            "━━━━━━━━━━━━━━━",
            f"收取地块：{len(mature_plots)} 块 ｜ 灵植经验：+{gained_exp}{level_note}",
        ]
        if stored_items:
            msg_lines.append("📦 存入储物戒：")
            for item in stored_items:
                msg_lines.append(f"  {item}")
        msg_lines.append(f"合计：{total} 株药材")
        msg_lines.append("━━━━━━━━━━━━━━━")
        return True, "\n".join(msg_lines)

    # ── v2 催熟 / 清理 ──

    async def force_ripen(self, player: Player) -> Tuple[bool, str]:
        """催熟：全部生长中的种植地块立即成熟（灵石 sink）"""
        farm = await self.get_user_farm(player.user_id)
        if not farm:
            return False, "❌ 你还没有灵田！"

        plots = self._refresh_plots(farm, player)
        now = datetime.now()
        garden_level = self.get_garden_level(farm)
        total_hours = 0.0
        ripened = 0
        for p in plots:
            if p.get("mode") != "planted":
                continue
            st = self._derive_plot_state(p, garden_level, now)
            if st["state"] == "growing":
                total_hours += float(st.get("hours_to_mature", 0))
                ripened += 1

        if ripened == 0:
            return False, "❌ 没有生长中的灵植需要催熟。"

        per_hour = int(self.crops_cfg.get("ripen_cost_per_hour", 100000))
        min_cost = int(self.crops_cfg.get("ripen_cost_min", 150000))
        cost = max(min_cost, math.ceil(total_hours) * per_hour)
        if player.gold < cost:
            return False, f"❌ 催熟 {ripened} 块需要 {cost:,} 灵石（{total_hours:.1f} 小时 × {per_hour:,}/h），你只有 {player.gold:,}"

        player.gold -= cost
        await self.db.update_player(player)

        for p in plots:
            if p.get("mode") != "planted":
                continue
            st = self._derive_plot_state(p, garden_level, now)
            if st["state"] == "growing":
                p["planted_at"] = (now - timedelta(hours=float(p.get("growth_hours", 12)))).strftime("%Y-%m-%d %H:%M:%S")
        await self._save_plots(player.user_id, plots)

        return True, (
            f"✨ 催熟成功！{ripened} 块灵植已全部成熟\n"
            "━━━━━━━━━━━━━━━\n"
            f"花费：{cost:,} 灵石\n"
            "💡 发送 /灵田收取 收获"
        )

    async def clear_dead_plots(self, player: Player) -> Tuple[bool, str]:
        """清理枯死地块（免费），回到空地"""
        farm = await self.get_user_farm(player.user_id)
        if not farm:
            return False, "❌ 你还没有灵田！"

        plots = self._refresh_plots(farm, player)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cleared = 0
        for p in plots:
            st = self._derive_plot_state(p, self.get_garden_level(farm))
            if st["dead"]:
                slot = p.get("slot", 0)
                p.clear()
                p.update({"slot": slot, "mode": "empty", "planted_at": now_str})
                cleared += 1

        if cleared == 0:
            return False, "❌ 没有枯死的灵植需要清理。"

        await self._save_plots(player.user_id, plots)
        return True, f"🧹 已清理 {cleared} 块枯死灵植，地块回到空地（24h 后自动野生）。"

    # ── v2 偷菜（纯娱乐，不接入因果）──

    def _reset_steal_counters_if_new_day(self, farm: Dict, today: str):
        if farm.get("steal_out_date") != today:
            farm["steal_out_date"] = today
            farm["steal_out_count"] = 0
        if farm.get("steal_in_date") != today:
            farm["steal_in_date"] = today
            farm["steal_in_count"] = 0

    async def steal(self, thief: Player, target: Player) -> Tuple[bool, str]:
        """偷菜：从目标园子偷 1 株成熟药材（纯娱乐，不扣因果）"""
        today = datetime.now().strftime("%Y-%m-%d")

        if thief.user_id == target.user_id:
            return False, "❌ 偷自己的园子？你的灵犬正在看你。"

        thief_farm = await self.get_user_farm(thief.user_id)
        if not thief_farm:
            return False, "❌ 你还没有灵田，无技可施。发送 /开垦灵田"

        target_farm = await self.get_user_farm(target.user_id)
        if not target_farm:
            return False, f"❌ {target.user_name or '对方'}还没有灵田。"

        # 频次重置与校验
        self._reset_steal_counters_if_new_day(thief_farm, today)
        self._reset_steal_counters_if_new_day(target_farm, today)
        if int(thief_farm.get("steal_out_count", 0)) >= int(self.crops_cfg.get("steal_limit_thief", 3)):
            return False, "❌ 今日偷菜次数已用完（3/3）。夜路走多了容易被逮。"
        if int(target_farm.get("steal_in_count", 0)) >= int(self.crops_cfg.get("steal_limit_victim", 5)):
            return False, "🛡️ 对方园子今日已被偷太多，灵气自行封闭，无人能再下手。"

        # 目标成熟地块
        target_plots = self._refresh_plots(target_farm, target)
        garden_level = self.get_garden_level(target_farm)
        mature = []
        for p in target_plots:
            if p.get("mode") == "empty":
                continue
            st = self._derive_plot_state(p, garden_level)
            if st["state"] in ("mature", "overripe") and not st["dead"]:
                mature.append(p)
        if not mature:
            return False, "❌ 对方园子里没有成熟灵植可偷。"

        # 护园灵兽拦截
        beast_level = int(target_farm.get("beast_level", 0) or 0)
        rates = self.crops_cfg.get("beast_rates", [0.0, 0.15, 0.25, 0.35])
        catch_rate = float(rates[beast_level]) if beast_level < len(rates) else 0.0
        if beast_level > 0 and random.random() < catch_rate:
            fine = int(self.crops_cfg.get("steal_fine", 500000))
            fined = min(thief.gold, fine)
            thief.gold -= fined
            owner_share = fined // 2
            target.gold += owner_share
            await self.db.update_player(thief)
            await self.db.update_player(target)
            # 小偷次数照扣（v1.2：无因果扣减）
            await self._update_farm(thief.user_id, steal_out_date=today,
                                    steal_out_count=int(thief_farm.get("steal_out_count", 0)) + 1)
            self._append_grudge(target_farm, thief, "（被灵兽拦截）")
            await self._update_farm(target.user_id, steal_in_date=today,
                                    steal_in_count=int(target_farm.get("steal_in_count", 0)) + 1,
                                    grudge_log=target_farm["grudge_log"])
            beast_names = {1: "灵犬", 2: "守园鹤", 3: "灵猿"}
            beast_name = beast_names.get(beast_level, "灵兽")
            return True, (
                f"🐕 {beast_name}一声长啸，你被当场逮住！\n"
                "━━━━━━━━━━━━━━━\n"
                f"罚款：{fined:,} 灵石（园主分得 {owner_share:,}）\n"
                "偷菜有风险，下夜班请先看看对方养了什么。"
            )

        # 偷取：随机选一块成熟地
        plot = random.choice(mature)
        herb_name = plot.get("herb_name")
        if not herb_name:
            # 野生未定名（罕见）：此时定名
            herbs_data = getattr(self.config_manager, "herbs_data", {}) or {}
            pool = [n for n, h in herbs_data.items()
                    if int(h.get("rank", 99)) >= self._get_player_harvest_rank(target)] or list(herbs_data.keys())[:1]
            herb_name = random.choice(pool)
            plot["herb_name"] = herb_name

        plot["yield_stolen"] = int(plot.get("yield_stolen", 0)) + 1

        # 药材给小偷
        got_msg = f"🌿 偷得：{herb_name} ×1"
        if self.storage_ring_manager:
            ok, _ = await self.storage_ring_manager.store_item(thief, herb_name, 1, silent=True)
            if not ok:
                got_msg = f"🌿 偷得：{herb_name} ×1（储物戒已满，只好含泪扔掉）"

        # 双方次数 + 恩怨簿
        await self._update_farm(thief.user_id, steal_out_date=today,
                                steal_out_count=int(thief_farm.get("steal_out_count", 0)) + 1)
        self._append_grudge(target_farm, thief, herb_name)
        await self._update_farm(target.user_id, steal_in_date=today,
                                steal_in_count=int(target_farm.get("steal_in_count", 0)) + 1,
                                grudge_log=target_farm["grudge_log"])
        await self._save_plots(target.user_id, target_plots)

        stolen_total = int(target_farm.get("steal_in_count", 0)) + 0
        return True, (
            "🌙 夜半摸金行动…\n"
            "━━━━━━━━━━━━━━━\n"
            f"目标：{target.user_name or '某位修士'} 的灵田\n"
            f"{got_msg}\n"
            f"今日偷菜：{int(thief_farm.get('steal_out_count', 0)) + 1}/{self.crops_cfg.get('steal_limit_thief', 3)} 次\n"
            "━━━━━━━━━━━━━━━\n"
            f"该园子今日已被偷 {stolen_total}/{self.crops_cfg.get('steal_limit_victim', 5)} 次"
        )

    def _append_grudge(self, target_farm: Dict, thief: Player, note: str):
        try:
            log = json.loads(target_farm.get("grudge_log") or "[]")
        except json.JSONDecodeError:
            log = []
        log.append({
            "time": datetime.now().strftime("%m-%d %H:%M"),
            "thief_id": thief.user_id,
            "thief_name": thief.user_name or str(thief.user_id)[-6:],
            "note": note,
        })
        target_farm["grudge_log"] = json.dumps(log[-10:], ensure_ascii=False)

    # ── v2 护园灵兽 ──

    async def buy_or_upgrade_beast(self, player: Player) -> Tuple[bool, str]:
        """购买/升级护园灵兽（灵犬 300万 → +200万 → +500万）"""
        farm = await self.get_user_farm(player.user_id)
        if not farm:
            return False, "❌ 你还没有灵田！"

        level = int(farm.get("beast_level", 0) or 0)
        if level >= 3:
            return False, "❌ 护园灵兽已达最高等级（Lv.3）！"

        costs = self.crops_cfg.get("beast_costs", [0, 3000000, 2000000, 5000000])
        cost = int(costs[level + 1]) if level + 1 < len(costs) else 5000000
        if player.gold < cost:
            return False, f"❌ 需要 {cost:,} 灵石，你只有 {player.gold:,}"

        player.gold -= cost
        await self.db.update_player(player)
        await self._update_farm(player.user_id, beast_level=level + 1)

        names = {1: "灵犬", 2: "守园鹤", 3: "灵猿"}
        rates = self.crops_cfg.get("beast_rates", [0.0, 0.15, 0.25, 0.35])
        action = "招募" if level == 0 else "升级"
        return True, (
            f"🐾 护园灵兽{action}成功！\n"
            "━━━━━━━━━━━━━━━\n"
            f"{names.get(level + 1, '灵兽')} Lv.{level + 1}（拦截率 {rates[level + 1]:.0%}）\n"
            f"花费：{cost:,} 灵石"
        )

    # ── v2 灵田视图 ──

    async def get_farm_info(self, user_id: str, config_manager: "ConfigManager" = None, player: Optional[Player] = None) -> str:
        """获取灵田信息展示（v2 地块矩阵 + 灵兽 + 恩怨簿）"""
        farm = await self.get_user_farm(user_id)
        if not farm:
            return (
                "🌾 灵田系统\n"
                "━━━━━━━━━━━━━━━\n"
                "你还没有灵田！\n"
                f"开垦费用：2,000,000 灵石\n\n"
                "💡 使用 /开垦灵田"
            )

        cm = config_manager or self.config_manager
        player_obj = player
        if player_obj is None and self.db is not None and hasattr(self.db, "get_player_by_id"):
            try:
                player_obj = await self.db.get_player_by_id(user_id)
            except Exception:
                player_obj = None

        plots = self._refresh_plots(farm, player_obj)
        garden_level = self.get_garden_level(farm)

        # 惰性转化/定名后若有变化则写回
        if farm.get("_plots_changed"):
            await self._save_plots(user_id, plots)

        icons = {"empty": "⬜", "growing": "🌱", "mature": "✨", "overripe": "🥀", "dead": "💀"}
        lines = [
            f"🌾 我的灵田（园圃 Lv.{garden_level}｜灵植经验 {farm.get('garden_exp', 0)}）",
            "━━━━━━━━━━━━━━━",
        ]
        for p in plots:
            slot = p.get("slot", "?")
            mode = p.get("mode", "empty")
            state = self._derive_plot_state(p, garden_level)
            st_name = state["state"]
            icon = icons.get(st_name, "⬜")
            if st_name == "empty":
                lines.append(f"{slot} {icon} 空地（{int(self.crops_cfg.get('empty_to_wild_hours', 24))}h 后自行野生）")
                continue
            name = p.get("herb_name") or "野生灵草"
            if st_name == "growing":
                hours = state.get("hours_to_mature", 0)
                filled = int(state.get("progress", 0) * 10)
                bar = "▓" * filled + "░" * (10 - filled)
                lines.append(f"{slot} {icon} {name}  🌱 生长  {bar} {hours:.0f}h 后成熟")
            elif st_name == "mature":
                lines.append(f"{slot} {icon} {name}  ✨ 成熟（/灵田收取）")
            elif st_name == "overripe":
                pct = int((1 - state["wither_mult"]) * 100)
                lines.append(f"{slot} {icon} {name}  🥀 过熟（产量 −{pct}%，速收！）")
            else:
                lines.append(f"{slot} {icon} {name}  💀 枯死（/灵田清理）")

        beast_level = int(farm.get("beast_level", 0) or 0)
        rates = self.crops_cfg.get("beast_rates", [0.0, 0.15, 0.25, 0.35])
        beast_names = {0: "无", 1: "灵犬", 2: "守园鹤", 3: "灵猿"}
        if beast_level > 0:
            lines.append(f"🐾 护园灵兽：{beast_names.get(beast_level, '灵兽')} Lv.{beast_level}（拦截率 {rates[beast_level]:.0%}）")
        else:
            lines.append("🐾 护园灵兽：无（/护园 招募灵犬）")

        # 恩怨簿
        try:
            grudge = json.loads(farm.get("grudge_log") or "[]")
        except json.JSONDecodeError:
            grudge = []
        today = datetime.now().strftime("%Y-%m-%d")
        self._reset_steal_counters_if_new_day(farm, today)
        if int(farm.get("steal_in_count", 0)) > 0:
            names_preview = "、".join(g.get("thief_name", "?") for g in grudge[-3:])
            lines.append(f"📔 恩怨簿：今日被偷 {farm.get('steal_in_count', 0)} 次（{names_preview}…）")

        lines.append("━━━━━━━━━━━━━━━")
        next_field_cost = FIELD_UPGRADE_COSTS.get(farm["herb_fields"])
        lines.append(f"下次扩展费用：{next_field_cost:,} 灵石" if next_field_cost else "灵田已满（6 块）")
        lines.append("")
        lines.append("💡 /灵田播种 <药名> [数量] ｜ /灵田收取 ｜ /灵田催熟 ｜ /灵田清理")
        lines.append("💡 /偷菜 @某人 ｜ /护园")
        return "\n".join(lines)

    # ── 兼容接口（旧冷却模型，v2 后恒返 0 避免外部报错）──

    def get_harvest_cooldown_seconds(self, farm: Dict) -> int:
        """旧冷却接口（v2 地块模型后不再有全田冷却，恒返 0）"""
        return 0

    def get_harvest_remaining(self, farm: Dict) -> int:
        """旧冷却接口（v2 后恒返 0 = 可收取，是否真有收取决于地块状态）"""
        return 0

    async def add_alchemy_exp(self, user_id: str, exp: int):
        """增加炼丹经验"""
        farm = await self.get_user_farm(user_id)
        if farm:
            await self._update_farm(
                user_id, alchemy_exp=farm["alchemy_exp"] + exp
            )
