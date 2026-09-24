#!/usr/bin/env python3
"""云游商人经济 Monte Carlo 模拟 — sink 占比 / 修炼位成交分布 / 捡漏套利规模

设计文档: docs/superpowers/specs/2026-09-24-wandering-merchant-design.md (v1.1)
失败信号对照: §10.3（A-F）

用法（项目 venv 解释器）:
    python scripts/merchant_economy_sim.py [--days 30] [--players 20] [--runs 10]

模型假设（全部可调，标注 [PLACEHOLDER] 的与设计文档一致）:
- 玩家日灵石收入: 按境界分段（签到 50万 + 悬赏/秘境/Boss/寄售），简单三档
- 购买意愿: 常规品按价格/收入比弹性购买；修炼位按"攒钱进度"模型（灵石水位达到定价即有概率购入）
- 窗口: 每日 2-3 次随机，30-60 分钟
输出: sink 占比 / 修炼位售罄率 / 品阶成交分布 / 每日 sink 均值
"""
import argparse
import json
import random
import sys
import types
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "astrbot_plugin_monixiuxian2"


def _register_namespace(name: str, path: Path, **attrs):
    module = types.ModuleType(name)
    module.__path__ = [str(path)]
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module


if PACKAGE_NAME not in sys.modules:
    _register_namespace(PACKAGE_NAME, ROOT)
# 独立分析脚本不启动 AstrBot；绕开会导入 astrbot.api 的包初始化模块。
_register_namespace(f"{PACKAGE_NAME}.managers", ROOT / "managers")
_register_namespace(f"{PACKAGE_NAME}.data", ROOT / "data", DataBase=object)
_register_namespace(f"{PACKAGE_NAME}.core", ROOT / "core", StorageRingManager=object)
sys.path.insert(0, str(ROOT))

from astrbot_plugin_monixiuxian2.managers.merchant_manager import MerchantManager  # noqa: E402


class SimulationConfig:
    """只读配置替身，复刻生产 ConfigManager 的数据形态。"""

    def __init__(self, root: Path):
        config_dir = root / "config"
        self.items_data = self._named_dict(config_dir / "items.json")
        self.skills_data = self._named_dict(config_dir / "skills.json")
        self.sub_techniques_data = self._named_dict(config_dir / "sub_techniques.json")
        self.utility_pills_data = self._named_dict(config_dir / "utility_pills.json")
        # 生产加载器保留 herbs.json 的 list 形态，商人管理器需兼容该形态。
        self.herbs_data = self._json(config_dir / "herbs.json")
        self.garden_crops = self._json(config_dir / "garden_crops.json")

    @staticmethod
    def _json(path: Path):
        return json.loads(path.read_text(encoding="utf-8"))

    @classmethod
    def _named_dict(cls, path: Path):
        data = cls._json(path)
        if isinstance(data, list):
            return {
                str(entry.get("id", index)): entry
                for index, entry in enumerate(data)
                if isinstance(entry, dict)
            }
        return data if isinstance(data, dict) else {}

# [PLACEHOLDER] 玩家日收入三档（灵石/日）——playtest 后以真实数据替换
INCOME_TIERS = {
    "早期(练气-金丹)": 800_000,
    "中期(紫府-合体)": 3_000_000,
    "后期(大乘-合道)": 10_000_000,
}

REALM_TOP_INDEX = 50  # [PLACEHOLDER] 服务器最高境界


def sim_window(mgr: MerchantManager, rng, players, stats):
    """模拟一个窗口：生成货架 → 每个在线玩家按意愿尝试购买"""
    merchant, goods = mgr.generate_goods(top_idx=REALM_TOP_INDEX, rng=rng)
    for g in goods:
        g["stock_left"] = g["stock_total"]
    window_spend = 0

    for p in players:
        income = INCOME_TIERS[p["tier"]]
        if rng.random() > 0.55:  # 窗口在线率
            continue
        bought = 0
        tech_bought = 0
        for g in goods:
            if g["stock_left"] <= 0 or bought >= mgr.settings["window_buy_limit"]:
                continue
            if p["bought_today"] >= mgr.settings["daily_buy_limit"]:
                continue
            price = g["price"]
            if g["slot_type"] == "tech":
                if tech_bought >= mgr.settings["tech_window_buy_limit"]:
                    continue
                # 修炼位：价格 ≤ 灵石水位 × 意愿系数 才买（攒钱模型）
                willingness = 0.9 if g["rank_idx"] <= 9 else 0.5
                if p["gold"] >= price and rng.random() < willingness * 0.15:
                    p["gold"] -= price
                    p["gold"] += income * 0.2  # 窗口期收入
                    g["stock_left"] -= 1
                    bought += 1
                    tech_bought += 1
                    p["bought_today"] += 1
                    window_spend += price
                    stats["tech_sold"][g["rank_idx"]] = stats["tech_sold"].get(g["rank_idx"], 0) + 1
            else:
                # 常规品：日常消耗，价格/日收入比 <0.8 时高概率购买
                if p["gold"] >= price and price / income < 0.8 and rng.random() < 0.6:
                    p["gold"] -= price
                    g["stock_left"] -= 1
                    bought += 1
                    p["bought_today"] += 1
                    window_spend += price
                    stats["regular_sold"] += 1
    # 窗口间隙全服玩家继续攒钱
    for p in players:
        p["gold"] += INCOME_TIERS[p["tier"]]
    return window_spend, goods


def main():
    parser = argparse.ArgumentParser(description="云游商人经济 Monte Carlo")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--players", type=int, default=20)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--price-scale", type=float, default=1.0)
    args = parser.parse_args()
    if args.days < 1 or args.players < 1 or args.runs < 1 or args.price_scale <= 0:
        parser.error("days、players、runs 必须为正数，price-scale 必须大于 0")

    tiers = list(INCOME_TIERS.keys())
    config = SimulationConfig(ROOT)
    agg = {"sinks": [], "tech_sold_by_run": [], "sellout_rate": []}
    dist = Counter()

    for run in range(args.runs):
        rng = random.Random(20260924 + run)
        mgr = MerchantManager(db=None, config_manager=config)
        mgr.settings["price_scale"] = args.price_scale
        players = [
            {"tier": tiers[i % len(tiers)], "gold": 5_000_000, "bought_today": 0}
            for i in range(args.players)
        ]
        stats = {"tech_sold": {}, "regular_sold": 0}
        total_sink = 0
        tech_windows = 0
        tech_soldout = 0
        for _day in range(args.days):
            for player in players:
                player["bought_today"] = 0
            n_windows = rng.randint(
                mgr.settings["windows_per_day_min"], mgr.settings["windows_per_day_max"])
            for _window in range(n_windows):
                spend, goods = sim_window(mgr, rng, players, stats)
                total_sink += spend
                techs = [g for g in goods if g["slot_type"] == "tech"]
                if techs:
                    tech_windows += 1
                    if all(g["stock_left"] == 0 for g in techs):
                        tech_soldout += 1
        agg["sinks"].append(total_sink)
        agg["tech_sold_by_run"].append(sum(stats["tech_sold"].values()))
        agg["sellout_rate"].append(tech_soldout / tech_windows if tech_windows else 0)
        dist.update(stats["tech_sold"])

    avg_sink = sum(agg["sinks"]) / (args.runs * args.days)
    avg_income_daily = sum(INCOME_TIERS.values()) / len(INCOME_TIERS) * args.players
    print("=" * 56)
    print(f"云游商人经济模拟  {args.runs} runs × {args.days} 天 × {args.players} 人  price_scale={args.price_scale}")
    print("=" * 56)
    print(f"日均 sink            : {avg_sink:,.0f} 灵石")
    print(f"玩家日均总收入(估)   : {avg_income_daily:,.0f} 灵石")
    print(f"sink 占比            : {avg_sink / avg_income_daily * 100:.1f}%   "
          f"（目标 5%-15%，>15% 触发信号 D，<5% 触发信号 E）")
    print(f"修炼位日均成交       : {sum(agg['tech_sold_by_run']) / (args.runs * args.days):.1f} 件")
    print(f"修炼位售罄率         : {sum(agg['sellout_rate']) / args.runs * 100:.0f}%   "
          f"（连续 100% 且秒空 → 信号 A 定价过低）")
    tier_names = ["人下", "人上", "黄下", "黄上", "玄下", "玄上", "地下", "地上",
                  "天下", "天上", "仙下", "仙上", "仙极", "无上"]
    print("品阶成交分布         : " + (", ".join(
        f"{tier_names[rank]}×{count}" for rank, count in sorted(dist.items())) or "无"))
    print("=" * 56)
    print("处方对照 §10.3：A 定价过低 / B 零成交 / D-E sink 越界 → 调 PRICE_SCALE")


if __name__ == "__main__":
    main()
