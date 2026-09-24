"""云游商人系统管理器 — 随机窗口 + 限量货架 + 全服唯一修炼位

设计文档: docs/superpowers/specs/2026-09-24-wandering-merchant-design.md (v1.1)

核心规则 (v1.1 定案):
- 窗口: 每日 2-3 次随机开窗，每次 30-60 分钟；由后台任务每分钟 tick 驱动（惰性，无独立线程）
- 货架: 每窗口 5-6 格 = 常规位×3（材料/药材/功能丹，库存3-5）+ 修炼位×1-2（功法/神通/辅修，
        全服库存 1 件先到先得）+ 捡漏位 15% 概率（仅常规品 ×0.5-0.7）
- 定价: 修炼位独立定价表（人下 60万 → 无上 5亿，v1.1 后段加速），PRICE_SCALE 全局旋钮；
        常规位 = config 参考价 × U(1.1, 1.5)；药材按灵植园档位种子价 ×2 参照
- 品阶带锚定: 修炼位 rank 按"服务器最高境界"锚定主带 [top-12, top-4]，10% 长尾越级好货
- 购买: 每人每窗口 2 件/每日 4 件，修炼位每窗口 1 件；已拥有仅标注不拦截（v1.1，
        可转卖寄售行，商人价即市场锚价）；库存 CAS 扣减（条件 UPDATE）
- 入库: 丹药 → 丹药背包；其余 → 储物戒（白名单校验）
"""
import json
import random
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

try:
    from astrbot.api import logger
except ImportError:  # 测试环境
    import logging
    logger = logging.getLogger(__name__)

from ..data import DataBase
from ..models import Player

try:
    from ..core import StorageRingManager
except ImportError:  # pragma: no cover - 测试环境相对导入兜底
    StorageRingManager = None

__all__ = ["MerchantManager"]

# ── 品阶体系（rank idx 0-13，与心法/神通/辅修 14 档对齐）──
RANK_NAMES = [
    "人阶下品", "人阶上品", "黄阶下品", "黄阶上品",
    "玄阶下品", "玄阶上品", "地阶下品", "地阶上品",
    "天阶下品", "天阶上品", "仙阶下品", "仙阶上品",
    "仙阶极品", "无上",
]
# 神通的顶级档位名与功法不同（无上神通），rank 名 → idx 的别名表
RANK_ALIASES = {
    "无上仙法": 13,
    "无上神通": 13,
}

# 修炼位定价表（灵石，v1.1 设计值；MERCHANT.PRICE_SCALE 全局缩放）
TECH_BASE_PRICES = {
    0: 600_000,      # 人下
    1: 1_000_000,    # 人上
    2: 1_800_000,    # 黄下
    3: 3_000_000,    # 黄上
    4: 5_000_000,    # 玄下
    5: 8_000_000,    # 玄上
    6: 13_000_000,   # 地下
    7: 20_000_000,   # 地上
    8: 35_000_000,   # 天下
    9: 55_000_000,   # 天上
    10: 90_000_000,  # 仙下
    11: 140_000_000, # 仙上
    12: 250_000_000, # 仙极
    13: 500_000_000, # 无上
}

# 修炼位类别权重（功法/神通/辅修）
TECH_KIND_WEIGHTS = {"tech": 35, "skill": 35, "subtech": 30}

# 常规位类别权重（材料/药材/功能丹）
REGULAR_KIND_WEIGHTS = {"material": 50, "herb": 35, "pill": 15}

# 商人名号 flavor（纯装饰）
MERCHANT_NAMES = [
    "青衫客", "白发贾", "乾坤袋老人", "葫芦仙", "踏风商",
    "袖里乾坤", "半仙商", "云履客", "锦囊叟", "醉货郎",
]

# 药材无 config 定价，按灵植园档位种子价 ×2 参照（与种田成本自洽）
HERB_TIER_FALLBACK_PRICE = 300_000

TOTAL_REALM_LEVELS = 58  # 境界索引 0-57
DEFAULT_SETTINGS = {
    "enabled": True,
    "broadcast_enabled": True,
    "windows_per_day_min": 2,
    "windows_per_day_max": 3,
    "window_duration_min": 30,   # 分钟
    "window_duration_max": 60,
    "regular_slots": 3,
    "tech_slots_min": 1,
    "tech_slots_max": 2,
    "bargain_chance": 0.15,
    "bargain_discount_min": 0.5,
    "bargain_discount_max": 0.7,
    "price_scale": 1.0,
    "premium_min": 1.1,          # 常规位便利税下限
    "premium_max": 1.5,          # 常规位便利税上限
    "regular_stock_min": 3,
    "regular_stock_max": 5,
    "daily_buy_limit": 4,
    "window_buy_limit": 2,
    "tech_window_buy_limit": 1,
    "tick_interval_seconds": 60,
}


def rank_index_of(rank_name: str) -> int:
    """品阶名 → rank idx（0-13），未知返回 -1"""
    if not rank_name:
        return -1
    if rank_name in RANK_ALIASES:
        return RANK_ALIASES[rank_name]
    try:
        return RANK_NAMES.index(rank_name)
    except ValueError:
        return -1


def rank_for_realm(level_index: int) -> int:
    """境界索引（0-57）→ 适配品阶 idx（0-13），线性映射 clamp"""
    if level_index < 0:
        return 0
    return min(13, int(level_index * 14 / TOTAL_REALM_LEVELS))


def gen_daily_schedule(date_str: str, count: int,
                       dur_min_min: int, dur_max_min: int,
                       rng: random.Random) -> List[dict]:
    """生成某日窗口计划（纯函数，确定性：同 date+seed 结果一致）

    返回 [{"start_ts": float, "duration_sec": int}, ...] 按时间升序
    """
    base = datetime.strptime(date_str, "%Y-%m-%d")
    day_start = base.timestamp()
    slots = []
    # 候选开窗点：06:00 - 23:30 内随机，间隔下限 2h（贪心放置，重试足够次）
    min_gap = 2 * 3600
    for _ in range(count * 40):
        start = day_start + rng.randint(6 * 3600, 23 * 3600 + 1800)
        duration = rng.randint(dur_min_min, dur_max_min) * 60
        if all(abs(start - s["start_ts"]) >= min_gap for s in slots):
            slots.append({"start_ts": float(start), "duration_sec": duration})
        if len(slots) >= count:
            break
    slots.sort(key=lambda s: s["start_ts"])
    return slots


class MerchantManager:
    """云游商人管理器：窗口调度（tick 驱动）/ 选品 / 定价 / 购买"""

    def __init__(self, db: DataBase, config_manager, storage_ring_mgr=None,
                 broadcast_fn=None, astrbot_config=None):
        self.db = db
        self.config_manager = config_manager
        self.storage_ring_mgr = storage_ring_mgr
        self.broadcast_fn = broadcast_fn  # 全服广播回调 async (message) -> None
        self.settings: Dict = dict(DEFAULT_SETTINGS)
        self._apply_webui_overrides(astrbot_config)

    # ── 配置 ──

    def _apply_webui_overrides(self, astrbot_config=None):
        """_conf_schema.json MERCHANT 节覆盖运行参数"""
        if not astrbot_config:
            return
        section = astrbot_config.get("MERCHANT")
        if not isinstance(section, dict):
            return
        key_map = {
            "MERCHANT_ENABLED": "enabled",
            "BROADCAST_ENABLED": "broadcast_enabled",
            "WINDOWS_PER_DAY_MIN": "windows_per_day_min",
            "WINDOWS_PER_DAY_MAX": "windows_per_day_max",
            "WINDOW_DURATION_MIN": "window_duration_min",
            "WINDOW_DURATION_MAX": "window_duration_max",
            "REGULAR_SLOTS": "regular_slots",
            "TECH_SLOTS_MIN": "tech_slots_min",
            "TECH_SLOTS_MAX": "tech_slots_max",
            "BARGAIN_CHANCE": "bargain_chance",
            "BARGAIN_DISCOUNT_MIN": "bargain_discount_min",
            "BARGAIN_DISCOUNT_MAX": "bargain_discount_max",
            "PRICE_SCALE": "price_scale",
            "PREMIUM_MIN": "premium_min",
            "PREMIUM_MAX": "premium_max",
            "REGULAR_STOCK_MIN": "regular_stock_min",
            "REGULAR_STOCK_MAX": "regular_stock_max",
            "DAILY_BUY_LIMIT": "daily_buy_limit",
            "WINDOW_BUY_LIMIT": "window_buy_limit",
            "TECH_WINDOW_BUY_LIMIT": "tech_window_buy_limit",
            "TICK_INTERVAL_SECONDS": "tick_interval_seconds",
        }
        for schema_key, setting_key in key_map.items():
            if schema_key in section:
                self.settings[setting_key] = section[schema_key]

    @property
    def enabled(self) -> bool:
        return bool(self.settings.get("enabled", True))

    # ── 物品池 ──

    @staticmethod
    def _iter_config_entries(raw) -> List[Tuple[object, dict]]:
        """统一遍历配置条目，兼容 ConfigManager 的 list 与测试替身的 dict。"""
        if isinstance(raw, dict):
            return [(key, value) for key, value in raw.items() if isinstance(value, dict)]
        if isinstance(raw, list):
            return [(index, value) for index, value in enumerate(raw) if isinstance(value, dict)]
        return []

    def _pool_regular(self) -> Tuple[Dict[str, List[dict]], Dict[str, int]]:
        """常规池: (kind -> [{"name", "price"}], 有效权重副本)"""
        pools: Dict[str, List[dict]] = {"material": [], "herb": [], "pill": []}
        cm = self.config_manager
        if not cm:
            return pools, dict(REGULAR_KIND_WEIGHTS)
        items = getattr(cm, "items_data", {}) or {}
        for _key, entry in self._iter_config_entries(items):
            if entry.get("type") == "材料":
                price = int(entry.get("price", 0) or 0)
                if price > 0:
                    pools["material"].append({"name": entry["name"], "price": price})
        herbs = getattr(cm, "herbs_data", {}) or {}
        tiers = self._herb_tier_prices()
        for key, entry in self._iter_config_entries(herbs):
            tier_price = self._herb_price_by_rank(entry.get("rank"), tiers)
            pools["herb"].append({"name": entry.get("name") or key, "price": tier_price})
        pills = getattr(cm, "utility_pills_data", {}) or {}
        for _key, entry in self._iter_config_entries(pills):
            price = int(entry.get("price", 0) or 0)
            if price > 0:
                pools["pill"].append({"name": entry["name"], "price": price})
        weights = dict(REGULAR_KIND_WEIGHTS)
        for kind in list(pools.keys()):
            if not pools[kind]:  # 类别池全空时从权重中剔除（用局部副本，不改模块常量）
                weights.pop(kind, None)
        return pools, weights

    def _herb_tier_prices(self) -> List[Tuple[int, int, int]]:
        """[(rank_min, rank_max, 参照价)]，来自 garden_crops 档位种子价 ×2"""
        tiers = []
        try:
            cfg = getattr(self.config_manager, "garden_crops", None) or {}
            for t in cfg.get("tiers", []):
                tiers.append((int(t.get("rank_min", 0)), int(t.get("rank_max", 0)),
                              int(t.get("seed_cost", HERB_TIER_FALLBACK_PRICE)) * 2))
        except Exception:
            pass
        return tiers

    @staticmethod
    def _herb_price_by_rank(rank, tiers) -> int:
        try:
            r = int(rank)
        except (TypeError, ValueError):
            r = -1
        for lo, hi, price in tiers:
            if lo <= r <= hi:
                return price
        return HERB_TIER_FALLBACK_PRICE

    def _tech_pool(self, kind: str) -> Dict[int, List[str]]:
        """修炼池: rank_idx -> [名称]"""
        cm = self.config_manager
        if not cm:
            return {}
        if kind == "tech":
            src = (getattr(cm, "items_data", {}) or {}).values()
        elif kind == "skill":
            src = (getattr(cm, "skills_data", {}) or {}).values()
        else:
            src = (getattr(cm, "sub_techniques_data", {}) or {}).values()
        pool: Dict[int, List[str]] = {}
        for entry in src:
            idx = rank_index_of(entry.get("rank"))
            if idx >= 0:
                pool.setdefault(idx, []).append(entry["name"])
        return pool

    # ── 选品（纯逻辑，可测）──

    def _pick_kind(self, weights: Dict[str, int], rng: random.Random) -> str:
        kinds = list(weights.keys())
        w = [weights[k] for k in kinds]
        return rng.choices(kinds, weights=w, k=1)[0]

    def _pick_rank_in_band(self, top_idx: int, rng: random.Random) -> int:
        """品阶带锚定: 主带 [rank(top-12), rank(top-4)]，10% 长尾 +1~2 档"""
        lo = rank_for_realm(max(0, top_idx - 12))
        hi = rank_for_realm(max(0, top_idx - 4))
        if rng.random() < 0.10:
            hi = min(13, hi + rng.randint(1, 2))
        hi = max(hi, lo)
        return rng.randint(lo, hi)

    def generate_goods(self, top_idx: int, rng: Optional[random.Random] = None,
                       now: Optional[float] = None) -> Tuple[str, List[dict]]:
        """生成一个窗口的货架（纯逻辑）。

        返回 (merchant_name, goods) ，goods 每项:
        {slot_type, item_kind, item_name, rank_idx, price, stock_total, stock_left}
        """
        rng = rng or random.Random()
        s = self.settings
        price_scale = float(s.get("price_scale", 1.0))
        premium_lo = float(s.get("premium_min", 1.1))
        premium_hi = float(s.get("premium_max", 1.5))
        goods: List[dict] = []

        def _mk(kind, name, ref_price, slot_type, rank_idx=-1, stock=1, mult_lo=premium_lo, mult_hi=premium_hi):
            price = max(1, int(ref_price * rng.uniform(mult_lo, mult_hi) * price_scale))
            return {"slot_type": slot_type, "item_kind": kind, "item_name": name,
                    "rank_idx": rank_idx, "price": price,
                    "stock_total": stock, "stock_left": stock}

        # 1) 常规位
        reg_pools, reg_weights = self._pool_regular()
        reg_count = int(s.get("regular_slots", 3))
        reg_stock_lo = int(s.get("regular_stock_min", 3))
        reg_stock_hi = int(s.get("regular_stock_max", 5))
        regular_picked: List[dict] = []
        for _ in range(reg_count):
            if not reg_weights:
                break
            kind = self._pick_kind(reg_weights, rng)
            pool = reg_pools.get(kind) or []
            if not pool:
                continue
            src = rng.choice(pool)
            stock = rng.randint(reg_stock_lo, reg_stock_hi)
            item = _mk(kind, src["name"], src["price"], "regular", stock=stock)
            goods.append(item)
            regular_picked.append(item)

        # 2) 修炼位
        tech_count = rng.randint(int(s.get("tech_slots_min", 1)), int(s.get("tech_slots_max", 2)))
        for _ in range(tech_count):
            kind = self._pick_kind(TECH_KIND_WEIGHTS, rng)
            pool = self._tech_pool(kind)
            rank_idx = self._pick_rank_in_band(top_idx, rng)
            # 空档就近降档，再升档兜底
            for probe in list(range(rank_idx, -1, -1)) + list(range(rank_idx + 1, 14)):
                if pool.get(probe):
                    rank_idx = probe
                    break
            names = pool.get(rank_idx)
            if not names:
                continue
            name = rng.choice(names)
            goods.append(_mk(kind, name, TECH_BASE_PRICES[rank_idx], "tech",
                             rank_idx=rank_idx, stock=1))

        # 3) 捡漏位（仅常规品，不与修炼位竞争）
        if rng.random() < float(s.get("bargain_chance", 0.15)) and regular_picked:
            src = rng.choice(regular_picked)
            d_lo = float(s.get("bargain_discount_min", 0.5))
            d_hi = float(s.get("bargain_discount_max", 0.7))
            base_ref = self._regular_ref_price(src["item_kind"], src["item_name"])
            goods.append(_mk(src["item_kind"], src["item_name"], base_ref, "bargain",
                             stock=1, mult_lo=d_lo, mult_hi=d_hi))

        name = rng.choice(MERCHANT_NAMES)
        return name, goods

    def _regular_ref_price(self, kind: str, name: str) -> int:
        """捡漏位重取参考价（常规品在 config 中均有据可查）"""
        cm = self.config_manager
        if not cm:
            return HERB_TIER_FALLBACK_PRICE
        if kind == "material":
            items = getattr(cm, "items_data", {}) or {}
            for _key, e in self._iter_config_entries(items):
                if e.get("name") == name and e.get("type") == "材料":
                    return int(e.get("price", 0) or HERB_TIER_FALLBACK_PRICE)
        elif kind == "herb":
            herbs = getattr(cm, "herbs_data", {}) or {}
            for key, e in self._iter_config_entries(herbs):
                if (e.get("name") or key) == name:
                    return self._herb_price_by_rank(e.get("rank"), self._herb_tier_prices())
        elif kind == "pill":
            pills = getattr(cm, "utility_pills_data", {}) or {}
            for _key, e in self._iter_config_entries(pills):
                if e.get("name") == name:
                    return int(e.get("price", 0) or HERB_TIER_FALLBACK_PRICE)
        return HERB_TIER_FALLBACK_PRICE

    # ── 窗口生命周期 ──

    async def get_current_window(self) -> Optional[dict]:
        async with self.db.conn.execute(
            "SELECT id, merchant_name, opened_at, closed_at, status "
            "FROM merchant_windows WHERE status = 0 ORDER BY id DESC LIMIT 1"
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return None
        return {"id": row[0], "merchant_name": row[1], "opened_at": row[2],
                "closed_at": row[3], "status": row[4]}

    async def _close_window(self, window: dict) -> Optional[str]:
        """关闭过期窗口，返回关窗广播摘要（无货可播返回 None）"""
        async with self.db.conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(stock_total - stock_left), 0) "
            "FROM merchant_goods WHERE window_id = ?",
            (window["id"],),
        ) as cursor:
            total, sold = await cursor.fetchone()
        await self.db.conn.execute(
            "UPDATE merchant_windows SET status = 1 WHERE id = ? AND status = 0",
            (window["id"],),
        )
        await self.db.conn.execute(
            "UPDATE merchant_goods SET stock_left = 0 "
            "WHERE window_id = ? AND slot_type = 'tech'",
            (window["id"],),
        )
        await self.db.conn.commit()
        if not self.settings.get("broadcast_enabled", True):
            return None
        merchant = window.get("merchant_name") or "云游商人"
        return (
            f"🧳 云游商人·{merchant} 收起货摊，化作青烟离去。\n"
            f"本期共售出 {sold}/{total} 件货物，剩余的随他云游去了。"
        )

    async def _open_window(self, now: float) -> Optional[str]:
        """开窗并写入货架，返回开窗广播"""
        top_idx = await self._get_server_top_realm()
        merchant, goods = self.generate_goods(top_idx, now=now)
        duration_min = random.randint(
            int(self.settings.get("window_duration_min", 30)),
            int(self.settings.get("window_duration_max", 60)),
        )
        cursor = await self.db.conn.execute(
            "INSERT INTO merchant_windows (merchant_name, opened_at, closed_at, status, goods_count) "
            "VALUES (?, ?, ?, 0, ?)",
            (merchant, now, now + duration_min * 60, len(goods)),
        )
        window_id = cursor.lastrowid
        for g in goods:
            await self.db.conn.execute(
                "INSERT INTO merchant_goods (window_id, slot_type, item_kind, item_name, "
                "rank_idx, price, stock_total, stock_left) VALUES (?,?,?,?,?,?,?,?)",
                (window_id, g["slot_type"], g["item_kind"], g["item_name"],
                 g["rank_idx"], g["price"], g["stock_total"], g["stock_left"]),
            )
        await self.db.conn.commit()
        if not self.settings.get("broadcast_enabled", True) or not goods:
            return None
        techs = [g for g in goods if g["slot_type"] == "tech"]
        lines = [
            f"🧳 云游商人·{merchant} 降临！携 {len(goods)} 件奇货而来（{duration_min} 分钟后离开）",
            "━━━━━━━━━━━━━━━",
        ]
        if techs:
            for t in techs:
                kind_label = {"tech": "功法", "skill": "神通", "subtech": "辅修"}.get(t["item_kind"], "秘宝")
                rank_label = RANK_NAMES[t["rank_idx"]] if 0 <= t["rank_idx"] < len(RANK_NAMES) else "未知"
                lines.append(f"⭐ {rank_label}{kind_label}《{t['item_name']}》 — {t['price']:,} 灵石（全服仅 1 件！）")
        lines.append("💡 /云游商人 查看完整货架，/购买商品 <编号> 购买")
        return "\n".join(lines)

    async def _get_server_top_realm(self) -> int:
        """服务器最高境界索引（品阶带锚定用），异常回退 0"""
        try:
            async with self.db.conn.execute(
                "SELECT COALESCE(MAX(level_index), 0) FROM players"
            ) as cursor:
                row = await cursor.fetchone()
            return int(row[0] or 0)
        except Exception:
            return 0

    async def tick(self, now: Optional[float] = None) -> List[str]:
        """调度 tick（后台任务每分钟调用一次），返回待广播消息列表

        1. 关闭所有过期窗口（广播关窗摘要）
        2. 无开启窗口时按当日计划决定是否开窗（广播开窗货架）
        """
        now = now if now is not None else time.time()
        messages: List[str] = []
        if not self.enabled:
            return messages

        # 1) 关闭过期窗口
        async with self.db.conn.execute(
            "SELECT id, merchant_name, opened_at, closed_at, status "
            "FROM merchant_windows WHERE status = 0 AND closed_at <= ?",
            (now,),
        ) as cursor:
            expired = await cursor.fetchall()
        for row in expired:
            window = {"id": row[0], "merchant_name": row[1], "opened_at": row[2],
                      "closed_at": row[3], "status": row[4]}
            summary = await self._close_window(window)
            if summary:
                messages.append(summary)

        # 2) 按当日计划开窗
        current = await self.get_current_window()
        if current is None:
            plan = self._today_schedule(now)
            for slot in plan:
                if slot["start_ts"] <= now < slot["start_ts"] + slot["duration_sec"]:
                    opened = await self._open_window(now)
                    if opened:
                        messages.append(opened)
                    break
        return messages

    def _today_schedule(self, now: float) -> List[dict]:
        """当日窗口计划（当日确定性：日期作随机种子）"""
        date_str = datetime.fromtimestamp(now).strftime("%Y-%m-%d")
        count = random.randint(
            int(self.settings.get("windows_per_day_min", 2)),
            int(self.settings.get("windows_per_day_max", 3)),
        )
        rng = random.Random(f"merchant-{date_str}")
        return gen_daily_schedule(
            date_str, count,
            int(self.settings.get("window_duration_min", 30)),
            int(self.settings.get("window_duration_max", 60)),
            rng,
        )

    # ── 购买 ──

    async def buy(self, player: Player, goods_id: int,
                  quantity: int = 1, now: Optional[float] = None) -> Tuple[bool, str]:
        """购买商品：限购校验 → 扣灵石 → CAS 扣库存 → 入库 → 记流水 → 播报

        返回 (ok, message)。修炼位售出时触发全服广播。
        """
        now = now if now is not None else time.time()
        window = await self.get_current_window()
        if not window or window["closed_at"] <= now:
            return False, "🧳 云游商人不在。他行踪不定，来时全服自有公告。"

        async with self.db.conn.execute(
            "SELECT id, slot_type, item_kind, item_name, rank_idx, price, stock_left "
            "FROM merchant_goods WHERE id = ? AND window_id = ?",
            (goods_id, window["id"]),
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return False, "❌ 没有这件商品（编号无效或已被清退）。"
        gid, slot_type, kind, name, rank_idx, price, stock_left = row
        is_tech = slot_type == "tech"
        quantity = 1 if is_tech else max(1, min(99, int(quantity)))
        total = price * quantity

        # 库存前置提示（CAS 仍是最终裁决）
        if stock_left <= 0:
            return False, "❌ 手慢了，这件已被别人购入。"

        # 限购校验
        ok, msg = await self._check_purchase_limits(player.user_id, window["id"], is_tech, now, quantity)
        if not ok:
            return False, msg

        # 灵石校验 + 扣款（先扣款后扣库存，失败回滚，对齐 Boss 顺序经验）
        if player.gold < total:
            return False, f"❌ 灵石不足！需要 {total:,} 灵石，你只有 {player.gold:,} 灵石。"
        player.gold -= total
        await self.db.update_player(player)

        # CAS 扣库存
        cursor = await self.db.conn.execute(
            "UPDATE merchant_goods SET stock_left = stock_left - ? "
            "WHERE id = ? AND stock_left >= ?",
            (quantity, gid, quantity),
        )
        if cursor.rowcount <= 0:
            await self.db.conn.rollback()
            player.gold += total
            await self.db.update_player(player)
            return False, "❌ 手慢了，这件刚被别人购入。"
        await self.db.conn.commit()

        # 入库
        owned_mark = await self._owned_mark(player, kind, name)
        deliver_msg = await self._deliver(player, kind, name, quantity)
        if not deliver_msg[0]:
            # 库存已扣但入库失败（不应发生：商人商品全部来自白名单池）——退款兜底
            player.gold += total
            await self.db.update_player(player)
            await self.db.conn.execute(
                "UPDATE merchant_goods SET stock_left = stock_left + ? WHERE id = ?",
                (quantity, gid),
            )
            await self.db.conn.commit()
            return False, f"❌ 入库失败：{deliver_msg[1]}（灵石已退还）"

        # 流水
        await self.db.conn.execute(
            "INSERT INTO merchant_purchases (window_id, user_id, item_kind, item_name, "
            "quantity, price, total_price, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (window["id"], player.user_id, kind, name, quantity, price, total, now),
        )
        await self.db.conn.commit()

        merchant = window.get("merchant_name") or "云游商人"
        lines = [f"✅ 购入 {name} ×{quantity} — {total:,} 灵石"]
        if owned_mark:
            lines.append("📖 此物你已身怀——商人管不了你买去转赠有缘人。")
        lines.append(deliver_msg[1])

        # 修炼位售出 → 全服即时播报（社交钩子）
        if is_tech and self.settings.get("broadcast_enabled", True):
            kind_label = {"tech": "功法", "skill": "神通", "subtech": "辅修"}.get(kind, "秘宝")
            rank_label = RANK_NAMES[rank_idx] if 0 <= rank_idx < len(RANK_NAMES) else ""
            await self._broadcast(
                f"💥 云游商人·{merchant} 的 {rank_label}{kind_label}《{name}》"
                f"被 {player.user_name or player.user_id} 购入！"
            )
        return True, "\n".join(lines)

    async def _broadcast(self, message: str):
        if self.broadcast_fn:
            try:
                await self.broadcast_fn(message)
            except Exception as e:  # 广播失败不影响成交
                logger.warning(f"【云游商人】播报失败: {e}")

    async def _check_purchase_limits(self, user_id: str, window_id: int,
                                     is_tech: bool, now: float, quantity: int) -> Tuple[bool, str]:
        s = self.settings
        async with self.db.conn.execute(
            "SELECT COALESCE(SUM(quantity), 0) FROM merchant_purchases "
            "WHERE user_id = ? AND window_id = ?",
            (user_id, window_id),
        ) as cursor:
            window_bought = int((await cursor.fetchone())[0] or 0)
        day_start = datetime.fromtimestamp(now).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        async with self.db.conn.execute(
            "SELECT COALESCE(SUM(quantity), 0) FROM merchant_purchases "
            "WHERE user_id = ? AND created_at >= ?",
            (user_id, day_start),
        ) as cursor:
            day_bought = int((await cursor.fetchone())[0] or 0)
        window_limit = int(s.get("window_buy_limit", 2))
        daily_limit = int(s.get("daily_buy_limit", 4))
        if window_bought + quantity > window_limit:
            return False, f"❌ 本期你已购 {window_bought} 件（每期上限 {window_limit} 件）。等商人下次到来吧。"
        if day_bought + quantity > daily_limit:
            return False, f"❌ 今日你已购 {day_bought} 件（每日上限 {daily_limit} 件）。"
        if is_tech:
            async with self.db.conn.execute(
                "SELECT COALESCE(SUM(p.quantity), 0) FROM merchant_purchases p "
                "JOIN merchant_goods g ON p.window_id = g.window_id "
                "AND p.item_name = g.item_name "
                "WHERE p.user_id = ? AND p.window_id = ? AND g.slot_type = 'tech'",
                (user_id, window_id),
            ) as cursor:
                tech_bought = int((await cursor.fetchone())[0] or 0)
            if tech_bought + quantity > int(s.get("tech_window_buy_limit", 1)):
                return False, "❌ 修炼秘宝每人每期限购 1 件。"
        return True, ""

    async def _owned_mark(self, player: Player, kind: str, name: str) -> bool:
        """已拥有判定（仅标注）：储物戒持有 或 已装备/已学（悬赏掉落与商人购买同走储物戒）"""
        try:
            ring = json.loads(player.storage_ring_items or "{}")
            equipped = getattr(player, "shentong", "") or ""
            sub = getattr(player, "sub_technique", "") or ""
            if kind == "tech":
                techniques = json.loads(player.techniques or "[]")
                if isinstance(techniques, dict):
                    techniques = list(techniques.keys())
                return name in ring or name in techniques
            if kind == "skill":
                return name in ring or name == equipped
            if kind == "subtech":
                return name in ring or name == sub
        except Exception:
            return False
        return False

    async def _deliver(self, player: Player, kind: str, name: str,
                       quantity: int) -> Tuple[bool, str]:
        """入库路由：丹药 → 丹药背包；其余 → 储物戒白名单"""
        if kind == "pill":
            inv = json.loads(player.pills_inventory or "{}")
            inv[name] = int(inv.get(name, 0)) + quantity
            player.pills_inventory = json.dumps(inv, ensure_ascii=False)
            await self.db.update_player(player)
            return True, f"💊 已放入丹药背包（{inv[name]} 颗）。"
        if self.storage_ring_mgr is None:
            return False, "储物戒系统不可用"
        ok, msg = await self.storage_ring_mgr.store_item(player, name, quantity)
        if ok:
            return True, "🎒 已存入储物戒。"
        return False, msg

    # ── 查询 ──

    async def list_goods(self, now: Optional[float] = None) -> Tuple[Optional[dict], List[dict]]:
        """当前窗口货架（含每件商品我的库存编号），供 /云游商人 渲染"""
        now = now if now is not None else time.time()
        window = await self.get_current_window()
        if not window or window["closed_at"] <= now:
            return None, []
        async with self.db.conn.execute(
            "SELECT id, slot_type, item_kind, item_name, rank_idx, price, stock_left "
            "FROM merchant_goods WHERE window_id = ? AND stock_left > 0 ORDER BY id",
            (window["id"],),
        ) as cursor:
            rows = await cursor.fetchall()
        goods = [
            {"id": r[0], "slot_type": r[1], "item_kind": r[2], "item_name": r[3],
             "rank_idx": r[4], "price": r[5], "stock_left": r[6]}
            for r in rows
        ]
        return window, goods
