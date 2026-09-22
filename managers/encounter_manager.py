# managers/encounter_manager.py
"""奇遇机缘系统管理器 — 事件池抽取 / 因果结算 / 修为占比锁定

设计文档:
- docs/superpowers/specs/2026-06-19-encounter-system-design.md (v2 机制框架)
- docs/superpowers/specs/2026-09-21-encounter-system-v3-design.md (因果失败减半等修订)
- docs/superpowers/specs/2026-09-22-encounter-events-pool-design.md (数值矩阵 v2)

核心数值规则:
- 灵石: 实发 = gold_center × uniform(0.6, 1.5) × level_bonus × gold_scale（center 已烘焙 rarity×risk）
- 修为: 实发 = D_daily × exp_pct/100 × uniform(0.6, 1.5)，clamp ≤ 0.5×D_daily
  D_daily = BASE_EXP_PER_MINUTE × 1440 × 灵根速度 × 境界因子 × (1+永久丹加成)
  期望占比 = exp_ratio（默认 0.15，即可调 10%~20% 带的锚点）
- 因果: 成功全额；失败同向减半 sign(delta)×ceil(|delta|/2)；钳制 [-1000, +1000]
"""
import json
import random
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from ..models import Player

try:
    from astrbot.api import logger
except ImportError:  # 测试环境
    import logging
    logger = logging.getLogger(__name__)

__all__ = ["EncounterManager"]

# ── 段位物品池（config 中以 "@herbs"/"@mats"/"@pills" 记号引用，按玩家境界段解析）──
TIER_HERBS: Dict[Tuple[int, int], List[str]] = {
    (0, 9): ["恒心草", "红绫草", "罗犀草", "天青花", "宁心草", "凝血草"],
    (10, 18): ["紫猴花", "九叶芝", "幻心草", "鬼臼草", "菩提花", "乌稠木",
               "五柳根", "天元果", "何首乌", "夜交藤", "轻灵草", "龙葵"],
    (19, 27): ["三叶青芝", "七彩月兰", "三尾风叶", "冰灵焰草", "天问花", "渊血冥花",
               "血莲精", "鸡冠草", "银精芝", "玉髓芝", "地心火芝", "天蝉灵叶"],
    (28, 36): ["地心淬灵乳", "天麻翡石精", "八角玄冰草", "奇茸通天菊", "阴阳黄泉花", "厉魂血珀",
               "浩淼水藤", "道蕴花", "狼桃", "霸王花", "太清玄灵草", "冥胎骨"],
    (37, 45): ["木灵三针花", "鎏鑫天晶草", "檀芒九叶花", "坎水玄冰果", "太乙碧莹花", "森檀木",
               "炼心芝", "重元换血草", "地龙干", "龙须藤", "鬼面花", "梧桐木",
               "离火梧桐芝", "尘磊岩麟果", "剑魄竹笋", "明心问道果"],
    (46, 57): ["离火梧桐芝", "尘磊岩麟果", "剑魄竹笋", "明心问道果"],
}
TIER_MATS: Dict[Tuple[int, int], List[str]] = {
    (0, 9): ["精铁", "百年灵草"],
    (10, 18): ["紫金沙", "千年人参"],
    (19, 27): ["魔核碎片", "幽魂草", "赤炎石"],
    (28, 36): ["玄冰之核", "月光粉尘", "灵兽骨", "妖丹", "精密齿轮"],
    (37, 45): ["龙骨髓", "星辉晶砂", "忘川花", "天火熔晶"],
    (46, 57): ["九幽寒铁", "混沌源石", "亡者之息"],
}
TIER_PILLS: Dict[Tuple[int, int], List[str]] = {
    (0, 9): [],
    (10, 18): ["筑基丹", "聚顶丹", "朝元丹"],
    (19, 27): ["锻脉丹", "护脉丹", "一纹清灵丹", "天命淬体丹"],
    (28, 36): ["澄心塑魂丹", "黑炎丹", "金血丸", "虚灵丹", "净明丹", "安神灵液"],
    (37, 45): ["魇龙之血", "化劫丹", "太上玄门丹", "九天蕴仙丹", "金仙造化丹"],
    (46, 57): ["太乙炼髓丹", "混沌丹", "创世丹", "极品混沌丹", "极品创世丹",
               "太清玉液丹", "一气鸿蒙丹", "大道归一丹", "菩提证道丹"],
}

RARITY_MULT = {"common": 1.0, "rare": 2.5, "epic": 6.0, "legendary": 15.0}
RARITY_LABEL = {"common": "普通", "rare": "稀有", "epic": "史诗", "legendary": "传说"}
RARITY_ICON = {"common": "🌀", "rare": "💠", "epic": "🌠", "legendary": "🌟"}


def _level_bonus(level_index: int) -> float:
    """境界缩放系数（与悬赏/秘境同源：1 + max(0, idx-3) × 0.045）"""
    return 1.0 + max(0, level_index - 3) * 0.045


def _tier_key(level_index: int) -> Tuple[int, int]:
    if level_index <= 9:
        return (0, 9)
    if level_index <= 18:
        return (10, 18)
    if level_index <= 27:
        return (19, 27)
    if level_index <= 36:
        return (28, 36)
    if level_index <= 45:
        return (37, 45)
    return (46, 57)


class EncounterManager:
    """奇遇机缘系统核心管理器"""

    def __init__(self, db, config_manager, storage_ring_mgr=None,
                 activity_tracker=None, cultivation_manager=None,
                 broadcast_fn=None, astrbot_config=None):
        self.db = db
        self.config_manager = config_manager
        self.storage_ring_mgr = storage_ring_mgr
        self.activity_tracker = activity_tracker
        self.cultivation_manager = cultivation_manager
        self.broadcast_fn = broadcast_fn  # 传说级全服广播回调 async (message) -> None
        self._pending: Dict[str, dict] = {}  # user_id -> pending

        cfg = config_manager.encounter_config if config_manager else {}
        self.encounters: List[dict] = cfg.get("encounters", [])
        self.trigger_chances: Dict[str, float] = cfg.get("trigger_chances", {})
        self.settings: Dict[str, dict] = cfg.get("settings", {})
        self.karma_settings: Dict[str, dict] = cfg.get("karma_settings", {})
        self.enabled: bool = True

        # WebUI 配置覆盖（_conf_schema.json 的 ENCOUNTER 节，运营常调项）
        self._apply_webui_overrides(astrbot_config)

    def _apply_webui_overrides(self, astrbot_config=None):
        """用 AstrBot WebUI 插件配置覆盖 encounter_config.json 中的同名运行参数"""
        if not astrbot_config:
            return
        section = astrbot_config.get("ENCOUNTER")
        if not isinstance(section, dict):
            return
        if "ENABLED" in section:
            self.enabled = bool(section["ENABLED"])
        mapping = {
            "DAILY_LIMIT": "daily_limit",
            "CHOICE_TIMEOUT_SECONDS": "choice_timeout_seconds",
            "EXP_RATIO": "exp_ratio",
            "GOLD_SCALE": "gold_scale",
            "LEGENDARY_BROADCAST": "legendary_broadcast",
        }
        for schema_key, setting_key in mapping.items():
            if schema_key in section:
                self.settings[setting_key] = section[schema_key]
        if "KARMA_DAILY_DECAY" in section:
            self.karma_settings["daily_decay"] = section["KARMA_DAILY_DECAY"]
        webui_chances = section.get("TRIGGER_CHANCES")
        if isinstance(webui_chances, dict):
            for action, pct in webui_chances.items():
                if action in self.trigger_chances or action in (
                    "check_in", "end_cultivation", "rift_complete", "bounty_complete",
                    "boss_fight", "dungeon_advance", "farm_harvest", "farm_sow",
                ):
                    self.trigger_chances[action] = float(pct)

    # ── 修为占比锁定（events pool v2 §1.3）──

    def get_daily_exp_base(self, player: Player) -> float:
        """玩家当前每日修为基数 D_daily（裸闭关 24h 口径）

        含: 基础每分钟修为 × 灵根速度 × 闭关境界因子 × (1+永久丹药修炼加成)
        不含: 心法/洞天/临时丹药等出关瞬态上下文（占比按基础面锚定）
        """
        base_per_minute = 60
        if self.cultivation_manager is not None:
            try:
                base_per_minute = int(
                    self.cultivation_manager.config["VALUES"].get("BASE_EXP_PER_MINUTE", 60)
                )
            except Exception:
                pass
        total = float(base_per_minute) * 1440.0

        mult = 1.0
        if self.cultivation_manager is not None:
            try:
                mult *= float(self.cultivation_manager.get_spiritual_root_speed(player))
            except Exception:
                pass
        try:
            mult *= float(self.config_manager.get_closing_realm_mult(player.level_index))
        except Exception:
            pass
        try:
            perm = player.get_permanent_pill_gains().get("_global", {}).get("cultivation_multiplier", 0)
            mult *= (1.0 + float(perm))
        except Exception:
            pass
        return total * mult

    # ── 触发 ──

    async def try_trigger(self, player: Player, action_type: str) -> Optional[str]:
        """尝试触发奇遇，成功返回奇遇描述文本（传说级同时全服广播），否则 None"""
        if not self.enabled:
            return None
        today = datetime.now().strftime("%Y-%m-%d")
        self._reset_daily_if_new_day(player, today)
        if player.daily_encounter_count >= int(self.settings.get("daily_limit", 3)):
            return None

        pending = self._pending.get(player.user_id)
        if pending is not None:
            if time.time() - pending["timestamp"] <= int(self.settings.get("choice_timeout_seconds", 180)):
                return None  # 已有待回复的奇遇
            del self._pending[player.user_id]

        trigger_pct = float(self.trigger_chances.get(action_type, 0.0))
        if trigger_pct <= 0 or random.random() >= trigger_pct:
            return None

        encounter = self._select_encounter(player)
        if not encounter:
            return None

        player.daily_encounter_count += 1
        player.last_encounter_date = today
        try:
            await self.db.update_player(player)
        except Exception:
            pass

        self._pending[player.user_id] = {
            "encounter": encounter,
            "timestamp": time.time(),
        }

        if self.activity_tracker:
            try:
                await self.activity_tracker.track_encounter(player)
            except Exception:
                pass

        if encounter.get("rarity") == "legendary" and self.broadcast_fn and self.settings.get("legendary_broadcast", True):
            try:
                broadcast_msg = (
                    "🌟 天降机缘！🌟\n"
                    "━━━━━━━━━━━━━━━\n"
                    f"某位修士触发了【{encounter['name']}】！\n"
                    "天地灵气波动，所有人都感受到了一丝异象...\n"
                    "━━━━━━━━━━━━━━━"
                )
                await self.broadcast_fn(broadcast_msg)
            except Exception:
                pass

        return self._build_encounter_message(encounter)

    def _select_encounter(self, player: Player) -> Optional[dict]:
        """按境界过滤 + 稀有度分层 + 因果偏移加权选择事件"""
        # 轮回门槛过滤（轮回系统未实装时 reincarnation_count 视为 0）
        reincarnation_count = 0
        try:
            reincarnation_count = int(getattr(player, "reincarnation_count", 0) or 0)
        except Exception:
            pass
        candidates = [
            e for e in self.encounters
            if e.get("min_level", 0) <= player.level_index <= e.get("max_level", 999)
            and reincarnation_count >= int(e.get("reincarnation_required", 0) or 0)
        ]
        if not candidates:
            return None

        roll = random.random()
        selected_rarity = "common"
        cumulative = 0.0
        for rarity, prob in (("legendary", 0.04), ("epic", 0.14), ("rare", 0.27), ("common", 0.55)):
            cumulative += prob
            if roll < cumulative:
                selected_rarity = rarity
                break

        pool = [e for e in candidates if e.get("rarity", "common") == selected_rarity]
        if not pool:
            pool = candidates

        karma = int(getattr(player, "karma", 0) or 0)
        bias_threshold = int(self.settings.get("karma_event_bias_threshold", 500))
        bias_pct = float(self.settings.get("karma_event_bias_pct", 25)) / 100.0

        weights = []
        for e in pool:
            w = float(e.get("weight", 100))
            if karma >= bias_threshold and self._is_positive_encounter(e):
                w *= (1.0 + bias_pct)
            elif karma <= -bias_threshold and any(
                c.get("karma_delta", 0) <= -5 for c in e.get("choices", [])
            ):
                w *= (1.0 + bias_pct)
            weights.append(w)

        return random.choices(pool, weights=weights, k=1)[0]

    @staticmethod
    def _is_positive_encounter(encounter: dict) -> bool:
        deltas = [c.get("karma_delta", 0) for c in encounter.get("choices", [])]
        return all(d >= 0 for d in deltas) and any(d > 0 for d in deltas)

    # ── 结算 ──

    async def resolve(self, player: Player, user_id: str, choice_id: str) -> str:
        """处理玩家选择，返回结果消息"""
        pending = self._pending.pop(user_id, None)
        if not pending:
            return "⏰ 你当前没有待回复的奇遇。"

        encounter = pending["encounter"]
        elapsed = time.time() - pending["timestamp"]
        timeout = int(self.settings.get("choice_timeout_seconds", 180))
        if elapsed > timeout:
            # 超时不消耗今日次数（回退）
            player.daily_encounter_count = max(0, player.daily_encounter_count - 1)
            await self.db.update_player(player)
            return (
                "⏰ 奇遇超时\n━━━━━━━━━━━━━━━\n"
                "你犹豫不决，机会已逝。\n（无惩罚，不消耗今日次数）"
            )

        choice = None
        for c in encounter.get("choices", []):
            if c.get("id") == choice_id.lower():
                choice = c
                break
        if not choice:
            self._pending[user_id] = pending  # 放回
            return f"无效的选择「{choice_id}」。请使用 /奇遇 {'/'.join(c['id'].upper() for c in encounter.get('choices', []))} 回复。"

        # 消耗
        cost = choice.get("cost", {}) or {}
        cost_gold = int(cost.get("gold", 0))
        if cost_gold > 0:
            if player.gold < cost_gold:
                self._pending[user_id] = pending  # 放回，玩家可改选
                return f"灵石不足！需要 {cost_gold:,} 灵石，你只有 {player.gold:,} 灵石。请重新 /奇遇 A/B/C。"
            player.gold -= cost_gold

        # 成败判定
        risk = float(choice.get("risk", 0))
        is_success = random.random() >= risk

        # ── 因果结算（v3 规则：成败同向，失败减半）──
        delta = int(choice.get("karma_delta", 0))
        if is_success or delta == 0:
            applied = delta
        else:
            applied = (1 if delta > 0 else -1) * ((abs(delta) + 1) // 2)
        kmin = int(self.karma_settings.get("min", -1000))
        kmax = int(self.karma_settings.get("max", 1000))
        player.karma = max(kmin, min(kmax, int(getattr(player, "karma", 0) or 0) + applied))

        gold_gain = 0
        exp_gain = 0
        item_lines: List[str] = []
        if is_success:
            rewards = choice.get("success_rewards", {}) or {}
            gold_gain, exp_gain, item_lines = await self._apply_rewards(player, rewards, encounter)
        else:
            penalty = choice.get("fail_penalty", {}) or {}
            item_lines = await self._apply_penalty(player, penalty)

        # 历史
        self._update_history(player, encounter, choice, is_success, applied)

        await self.db.update_player(player)

        karma_title = self.get_karma_title(player.karma)
        header = "✨" if is_success else "💀"
        lines = [
            f"{header} 你选择了【{choice.get('text', '')}】",
            "━━━━━━━━━━━━━━━",
        ]
        if is_success:
            lines.append(choice.get("success_text", "机缘已入你手。"))
            reward_parts = []
            if gold_gain > 0:
                reward_parts.append(f"灵石 ×{gold_gain:,}")
            if exp_gain > 0:
                reward_parts.append(f"修为 +{exp_gain:,}")
            if reward_parts:
                lines.append("📦 获得：" + " ｜ ".join(reward_parts))
            lines.extend(item_lines)
        else:
            lines.append(choice.get("fail_text", "事情并没有如你预期的发展。"))
            lines.extend(item_lines)
        lines.append(f"☯️ 因果：{applied:+d}（当前：{player.karma} | {karma_title}）")
        return "\n".join(lines)

    async def _apply_rewards(self, player: Player, rewards: dict, encounter: dict) -> Tuple[int, int, List[str]]:
        """发放奖励，返回 (灵石, 修为, 附加行)"""
        lines: List[str] = []

        # 灵石：center × uniform(0.6,1.5) × level_bonus × gold_scale
        gold_center = int(rewards.get("gold_center", 0))
        gold_gain = 0
        if gold_center > 0:
            gold_scale = float(self.settings.get("gold_scale", 1.0))
            gold_gain = int(gold_center * random.uniform(0.6, 1.5) * _level_bonus(player.level_index) * gold_scale)
            gold_gain = max(0, gold_gain)
            player.gold += gold_gain

        # 修为：D_daily × exp_pct/100 × uniform(0.6,1.5)，clamp ≤ 0.5×D_daily
        exp_pct = float(rewards.get("exp_pct", 0))
        exp_gain = 0
        if exp_pct > 0:
            d_daily = self.get_daily_exp_base(player)
            exp_gain = int(d_daily * (exp_pct / 100.0) * random.uniform(0.6, 1.5))
            exp_gain = max(0, min(exp_gain, int(d_daily * 0.5)))
            player.experience += exp_gain

        # 物品
        item_chance = float(rewards.get("item_chance", 0))
        item_pool = list(rewards.get("item_pool", []))
        if item_pool and random.random() < item_chance:
            pool_name = random.choice(item_pool)
            item_name = self._resolve_pool_item(pool_name, player.level_index)
            if item_name:
                if self.storage_ring_mgr is not None:
                    try:
                        ok, _ = await self.storage_ring_mgr.store_item(player, item_name, 1, silent=True)
                        if ok:
                            lines.append(f"🎁 物品：{item_name}（已存入储物戒）")
                        else:
                            lines.append(f"🎁 物品：{item_name}（储物戒已满，散落于地）")
                    except Exception:
                        lines.append(f"🎁 物品：{item_name}")
                else:
                    lines.append(f"🎁 物品：{item_name}")

        # 丹药 → 丹药背包
        pill_chance = float(rewards.get("pill_chance", 0))
        pill_pool = list(rewards.get("pill_pool", []))
        if pill_pool and random.random() < pill_chance:
            pool_name = random.choice(pill_pool)
            pill_name = self._resolve_pool_item(pool_name, player.level_index)
            if pill_name:
                try:
                    inv = json.loads(player.pills_inventory or "{}")
                except json.JSONDecodeError:
                    inv = {}
                inv[pill_name] = int(inv.get(pill_name, 0)) + 1
                player.pills_inventory = json.dumps(inv, ensure_ascii=False)
                lines.append(f"💊 丹药：{pill_name} ×1（已入丹药背包）")

        # HP 恢复（如灵泉）
        hp_restore = float(rewards.get("hp_restore_pct", 0))
        if hp_restore > 0:
            heal = int(player.hp * hp_restore)
            player.hp += heal
            if heal > 0:
                lines.append(f"💗 气血恢复 {heal:,}")

        return gold_gain, exp_gain, lines

    async def _apply_penalty(self, player: Player, penalty: dict) -> List[str]:
        """应用惩罚，返回附加行"""
        lines: List[str] = []
        hp_pct = float(penalty.get("hp_pct", 0))
        if hp_pct > 0:
            loss = int(player.hp * hp_pct)
            player.hp = max(0, player.hp - loss)
            if loss > 0:
                lines.append(f"💔 损失：{loss:,} 点生命值")
        gold_loss = int(penalty.get("gold_loss", 0))
        if gold_loss > 0:
            loss = min(player.gold, gold_loss)
            player.gold -= loss
            if loss > 0:
                lines.append(f"💸 灵石损失：{loss:,}")
        return lines

    def _resolve_pool_item(self, pool_token: str, level_index: int) -> Optional[str]:
        """解析物品池记号（@herbs/@mats/@pills → 按玩家境界段随机取一）"""
        if not pool_token:
            return None
        if not pool_token.startswith("@"):
            return pool_token  # 直接写了具体物品名
        tier = _tier_key(level_index)
        if pool_token == "@herbs":
            pool = TIER_HERBS.get(tier, [])
        elif pool_token == "@mats":
            pool = TIER_MATS.get(tier, [])
        elif pool_token == "@pills":
            pool = TIER_PILLS.get(tier, [])
        else:
            return None
        return random.choice(pool) if pool else None

    # ── 历史与因果 ──

    def _update_history(self, player: Player, encounter: dict, choice: dict, is_success: bool, applied_karma: int):
        try:
            history = json.loads(player.encounter_history or "[]")
        except json.JSONDecodeError:
            history = []
        history.append({
            "id": encounter.get("id", ""),
            "name": encounter.get("name", ""),
            "choice": choice.get("text", ""),
            "roll": "success" if is_success else "fail",
            "karma_delta": applied_karma,
            "rarity": encounter.get("rarity", "common"),
            "timestamp": int(time.time()),
        })
        player.encounter_history = json.dumps(history[-20:], ensure_ascii=False)

    def get_history(self, player: Player) -> List[dict]:
        try:
            return json.loads(player.encounter_history or "[]")
        except json.JSONDecodeError:
            return []

    def get_karma_title(self, karma: int) -> str:
        bonuses = self.karma_settings.get("bonuses", {})
        for key in ("demon", "evil", "neutral", "good", "saint"):
            b = bonuses.get(key, {})
            if b.get("min", 0) <= karma <= b.get("max", 0):
                return b.get("title", "中立")
        return "中立"

    async def apply_karma_decay(self, player: Player):
        """每日因果衰减（向 0 靠拢），在签到时调用"""
        decay = int(self.karma_settings.get("daily_decay", 2))
        karma = int(getattr(player, "karma", 0) or 0)
        if karma == 0 or decay <= 0:
            return
        if karma > 0:
            player.karma = max(0, karma - decay)
        else:
            player.karma = min(0, karma + decay)

    def _reset_daily_if_new_day(self, player: Player, today: str):
        if player.last_encounter_date != today:
            player.last_encounter_date = today
            player.daily_encounter_count = 0

    # ── 消息构建 ──

    def _build_encounter_message(self, encounter: dict) -> str:
        rarity = encounter.get("rarity", "common")
        icon = RARITY_ICON.get(rarity, "🌀")
        label = RARITY_LABEL.get(rarity, "普通")
        lines = [
            f"{icon} 【奇遇·{encounter.get('name', '')}】({label})",
            "━━━━━━━━━━━━━━━━━━━━",
            encounter.get("description", ""),
            "━━━━━━━━━━━━━━━━━━━━",
            "请选择（输入 /奇遇 A/B/C）：",
        ]
        for choice in encounter.get("choices", []):
            risk = float(choice.get("risk", 0))
            risk_text = "无" if risk <= 0 else f"{risk:.0%}"
            karma_delta = int(choice.get("karma_delta", 0))
            karma_text = f"因果：{karma_delta:+d}"
            cost = (choice.get("cost", {}) or {}).get("gold", 0)
            cost_text = f"，消耗：{int(cost):,}灵石" if cost else ""
            lines.append(
                f"{choice['id'].upper()}. {choice.get('text', '')}（风险：{risk_text}，{karma_text}{cost_text}）"
            )
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"⏰ {self.settings.get('choice_timeout_seconds', 180)}秒内选择，超时视为放弃。")
        lines.append("💡 使用 /奇遇 A 回复")
        return "\n".join(lines)
