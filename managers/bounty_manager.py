# managers/bounty_manager.py
"""悬赏令系统管理器"""

import json
import random
import time
from pathlib import Path
from typing import Tuple, List, Optional, Dict, TYPE_CHECKING

from astrbot.api import logger

from ..data import DataBase
from ..models import Player

if TYPE_CHECKING:
    from ..core import StorageRingManager

__all__ = ["BountyManager"]


class BountyManager:
    """悬赏令管理器"""

    BOUNTY_CACHE_DURATION = 600  # 任务列表缓存10分钟
    CONFIG_FILE = Path(__file__).resolve().parents[1] / "config" / "bounty_templates.json"
    DROP_CONFIG_FILE = Path(__file__).resolve().parents[1] / "config" / "bounty_drop_config.json"
    DEFAULT_CONFIG = {
        "difficulties": {
            "easy": {"name": "F级", "stone_scale": 1.0, "exp_scale": 1.0, "min_level": 0}
        },
        "templates": [
            {
                "id": 1,
                "name": "击退妖兽",
                "difficulty": "easy",
                "category": "巡山",
                "min_target": 3,
                "max_target": 5,
                "time_limit": 3600,
                "reward": {"stone": 300, "exp": 2500},
                "item_table": "hunt",
                "description": "驱逐骚扰山门的妖兽。"
            }
        ],
        "item_tables": {
            "hunt": [
                {"name": "灵兽毛皮", "weight": 40, "min": 1, "max": 3},
                {"name": "妖兽精血", "weight": 30, "min": 1, "max": 2},
                {"name": "玄铁", "weight": 30, "min": 1, "max": 2}
            ]
        }
    }

    DAILY_BOUNTY_LIMIT = 3

    def __init__(self, db: DataBase, storage_ring_manager: Optional["StorageRingManager"] = None,
                 items_data: Optional[Dict[str, dict]] = None,
                 skills_data: Optional[Dict[str, dict]] = None,
                 activity_tracker=None, game_config=None):
        self.db = db
        self.storage_ring_manager = storage_ring_manager
        self.activity_tracker = activity_tracker
        self.game_config = game_config or {}
        self._bounty_cache: Dict[str, Dict] = {}
        self.difficulties: Dict[str, dict] = {}
        self.templates_by_id: Dict[int, dict] = {}
        self.templates_by_diff: Dict[str, List[dict]] = {}
        self.item_tables: Dict[str, List[dict]] = {}
        self.items_data = items_data or {}
        self.skills_data = skills_data or {}
        self.reload_config()

    # -------- 配置 --------

    def reload_config(self):
        config = self._load_config_file()
        self.difficulties = config.get("difficulties", self.DEFAULT_CONFIG["difficulties"])
        self.item_tables = config.get("item_tables", self.DEFAULT_CONFIG["item_tables"])
        self.templates_by_id = {}
        self.templates_by_diff = {}
        for tpl in config.get("templates", []):
            tpl_copy = dict(tpl)
            self.templates_by_id[tpl_copy["id"]] = tpl_copy
            self.templates_by_diff.setdefault(tpl_copy["difficulty"], []).append(tpl_copy)
        logger.info(f"悬赏配置加载完成：{len(self.templates_by_id)} 条模板")
        self._load_drop_config()

    def _load_drop_config(self):
        """加载功法概率设置配置"""
        self._drop_config = {}
        if self.DROP_CONFIG_FILE.exists():
            try:
                with open(self.DROP_CONFIG_FILE, "r", encoding="utf-8") as f:
                    self._drop_config = json.load(f)
                logger.info(f"功法掉落配置加载完成：{len(self._drop_config)} 个品阶")
            except Exception as exc:
                logger.error(f"加载 bounty_drop_config.json 失败: {exc}")
        else:
            logger.warning("bounty_drop_config.json 不存在，使用旧掉落机制")

    def _roll_bounty_drop(self, player: Player) -> Optional[dict]:
        """100%掉落功法或神通：按 type_rate 权重选品阶，再随机选功法或神通"""
        if not self._drop_config:
            return None

        # 按 type_rate 权重选择品阶
        ranks = list(self._drop_config.keys())
        weights = [self._drop_config[r]["type_rate"] for r in ranks]
        chosen_rank = random.choices(ranks, weights=weights, k=1)[0]
        rank_data = self._drop_config[chosen_rank]

        gf_list = rank_data.get("gf_list", [])
        st_list = rank_data.get("st_list", [])
        fx_list = rank_data.get("fx_list", [])

        # 构建有内容的类别池，各占 1/3 概率
        pools = []
        if gf_list:
            pools.append(("main_technique", gf_list))
        if st_list:
            pools.append(("skill", st_list))
        if fx_list:
            pools.append(("sub_technique", fx_list))

        if not pools:
            return None

        # 先等概率选类别，再从类别内随机选物品
        item_type, item_pool = random.choice(pools)
        item_name = random.choice(item_pool)

        return {
            "name": item_name,
            "rank": chosen_rank,
            "type": item_type,
        }

    def _load_config_file(self) -> dict:
        if self.CONFIG_FILE.exists():
            try:
                with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as exc:
                logger.error(f"加载 bounty_templates.json 失败，将使用默认配置: {exc}")
        return self.DEFAULT_CONFIG

    # -------- 列表 & 缓存 --------

    def _get_cached_bounties(self, user_id: str) -> Optional[List[dict]]:
        cache = self._bounty_cache.get(user_id)
        if cache and cache["expire_time"] > int(time.time()):
            return cache["bounties"]
        return None

    def _set_cached_bounties(self, user_id: str, bounties: List[dict]):
        self._bounty_cache[user_id] = {
            "bounties": bounties,
            "expire_time": int(time.time()) + self.BOUNTY_CACHE_DURATION
        }

    async def get_bounty_list(self, player: Player) -> List[dict]:
        """获取悬赏列表（固定3条，允许重复模板）"""
        cached = self._get_cached_bounties(player.user_id)
        if cached:
            return cached

        plan = self._get_difficulty_plan(player.level_index)
        bounties: List[dict] = []
        seen_ids: Dict[int, int] = {}  # template_id -> occurrence count
        for _ in range(3):
            diff = random.choice(plan)
            entry = self._build_bounty_entry(diff, player)
            if entry:
                tid = entry["id"]
                occ = seen_ids.get(tid, 0)
                seen_ids[tid] = occ + 1
                entry["slot"] = f"{tid}_{occ}"  # unique key for duplicate templates
                bounties.append(entry)

        self._set_cached_bounties(player.user_id, bounties)
        return bounties

    def _get_difficulty_plan(self, level_index: int) -> List[str]:
        plan = ["easy", "normal"]
        if level_index >= 7:
            plan.append("hard")
        if level_index >= 12:
            plan.append("elite")
        return [diff for diff in plan if diff in self.difficulties]

    def _pick_template(self, difficulty: str) -> Optional[dict]:
        templates = self.templates_by_diff.get(difficulty)
        if not templates:
            return None
        total = sum(max(1, tpl.get("weight", 1)) for tpl in templates)
        roll = random.randint(1, total)
        upto = 0
        for tpl in templates:
            upto += max(1, tpl.get("weight", 1))
            if roll <= upto:
                return tpl
        return templates[0]

    def _build_bounty_entry(self, difficulty: str, player: Player) -> Optional[dict]:
        template = self._pick_template(difficulty)
        if not template:
            return None
        diff_cfg = self.difficulties.get(difficulty, {})
        target = random.randint(template.get("min_target", 1), template.get("max_target", 1))
        reward = self._calculate_reward(template, diff_cfg, player, target)
        time_limit = self._calculate_time_limit(template, target)
        drop_reward = self._roll_bounty_drop(player)
        return {
            "id": template["id"],
            "name": template["name"],
            "category": template.get("category", "任务"),
            "difficulty": difficulty,
            "difficulty_name": diff_cfg.get("name", difficulty),
            "description": random.choice(template["descriptions"]) if template.get("descriptions") else template.get("description", ""),
            "count": target,
            "reward": reward,
            "time_limit": time_limit,
            "item_table": template.get("item_table", "gather"),
            "drop_reward": drop_reward
        }

    def _calculate_reward(self, template: dict, diff_cfg: dict, player: Player, target: int) -> Dict[str, int]:
        base_reward = template.get("reward", {"stone": 200, "exp": 2000})
        stone = base_reward.get("stone", 0)
        exp = base_reward.get("exp", 0)
        level_cfg = self.game_config.get("level_scaling", {})
        coeff = level_cfg.get("bounty_rift_coefficient", 0.045)
        base_level = level_cfg.get("bounty_rift_base_level", 3)
        level_bonus = 1 + max(0, player.level_index - base_level) * coeff
        progress_factor = max(1, target) / max(1, template.get("min_target", 1))
        stone_scale = diff_cfg.get("stone_scale", 1.0)
        exp_scale = diff_cfg.get("exp_scale", 1.0)
        final_stone = int(stone * stone_scale * progress_factor * level_bonus)
        final_exp = int(exp * exp_scale * progress_factor * level_bonus)
        return {"stone": final_stone, "exp": final_exp}

    def _calculate_time_limit(self, template: dict, target: int) -> int:
        return template.get("time_limit", 3600)

    # -------- 接取与状态 --------

    async def get_daily_bounty_count(self, user_id: str) -> int:
        """获取今日已完成悬赏次数"""
        daily_key = f"bounty_daily_{user_id}"
        daily_data = await self.db.ext.get_system_config(daily_key)
        today = time.strftime("%Y-%m-%d")
        if daily_data:
            parts = daily_data.split("|")
            if len(parts) == 2 and parts[0] == today:
                return int(parts[1])
        return 0

    async def accept_bounty(self, player: Player, bounty_id: int) -> Tuple[bool, str]:
        if bounty_id <= 0:
            return False, "无效的悬赏编号。"

        cached_bounties = self._get_cached_bounties(player.user_id)
        cached = None
        if cached_bounties:
            # 优先按位置匹配（1/2/3），再按模板ID匹配
            if 1 <= bounty_id <= len(cached_bounties):
                cached = cached_bounties[bounty_id - 1]
            else:
                cached = next((b for b in cached_bounties if b["id"] == bounty_id), None)
        if not cached:
            return False, "⚠️ 悬赏列表已刷新，请先发送 /悬赏令 重新查看后再接取。"

        now = int(time.time())
        time_limit = cached.get("time_limit", 3600)

        await self.db.conn.execute("BEGIN IMMEDIATE")
        try:
            active = await self.db.ext.get_active_bounty(player.user_id)
            if active:
                await self.db.conn.rollback()
                return False, f"你已有进行中的悬赏：{active['bounty_name']}，请先完成或放弃。"

            # 也检查已过期但未领取的悬赏
            expired = await self.db.ext.get_expired_bounty(player.user_id)
            if expired:
                await self.db.conn.rollback()
                return False, f"你有已过期未领取的悬赏：{expired['bounty_name']}，请先完成或放弃。"

            cd_key = f"bounty_abandon_cd_{player.user_id}"
            cd_value = await self.db.ext.get_system_config(cd_key)
            if cd_value:
                cd_time = int(cd_value)
                if now < cd_time:
                    await self.db.conn.rollback()
                    remaining = (cd_time - now) // 60 or 1
                    return False, f"你刚放弃过悬赏，还需等待 {remaining} 分钟才能再次接取。"

            # 每日接取次数限制
            daily_key = f"bounty_daily_{player.user_id}"
            daily_data = await self.db.ext.get_system_config(daily_key)
            today = time.strftime("%Y-%m-%d")
            daily_count = 0
            if daily_data:
                parts = daily_data.split("|")
                if len(parts) == 2 and parts[0] == today:
                    daily_count = int(parts[1])
            if daily_count >= self.DAILY_BOUNTY_LIMIT:
                await self.db.conn.rollback()
                return False, f"你今日已接取{self.DAILY_BOUNTY_LIMIT}次悬赏，明日再来。"

            expire_time = now + time_limit
            rewards_json = json.dumps({
                "stone": cached["reward"]["stone"],
                "exp": cached["reward"]["exp"],
                "difficulty": cached.get("difficulty", "easy"),
                "difficulty_name": cached.get("difficulty_name", ""),
                "item_table": cached.get("item_table"),
                "description": cached.get("description", ""),
                "drop_reward": cached.get("drop_reward")
            }, ensure_ascii=False)

            await self.db.conn.execute(
                """
                INSERT INTO bounty_tasks (
                    user_id, bounty_id, bounty_name, target_type,
                    target_count, current_progress, rewards,
                    start_time, expire_time, status
                ) VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, 1)
                """,
                (
                    player.user_id,
                    cached.get("id", bounty_id),
                    cached.get("name", "悬赏"),
                    cached.get("category", "任务"),
                    cached["count"],
                    rewards_json,
                    now,
                    expire_time
                )
            )
            await self.db.conn.commit()

            # 更新每日接取计数
            new_count = daily_count + 1
            await self.db.ext.set_system_config(daily_key, f"{today}|{new_count}")

        except Exception:
            await self.db.conn.rollback()
            raise

        remaining = self.DAILY_BOUNTY_LIMIT - new_count
        return True, (
            f"🎯 接取悬赏成功！\n"
            f"任务：{cached.get('name', '悬赏')}（{cached.get('difficulty_name', '')}）\n"
            f"奖励：{cached['reward']['stone']:,} 灵石 + {cached['reward']['exp']:,} 修为\n"
            f"时限：{time_limit // 60} 分钟（到时限后可领取奖励）\n"
            f"今日剩余接取次数：{remaining}"

        )

    async def check_bounty_status(self, player: Player) -> Tuple[bool, str]:
        active = await self.db.ext.get_active_bounty(player.user_id)
        is_expired_claim = False
        if not active:
            # 后台过期检查可能已将 status 改为 3，尝试查已过期的悬赏
            active = await self.db.ext.get_expired_bounty(player.user_id)
            if not active:
                return False, "你当前没有进行中的悬赏任务。\n使用 /悬赏令 查看可接取的任务。"
            is_expired_claim = True

        rewards = json.loads(active["rewards"])
        remaining = max(0, active["expire_time"] - int(time.time()))

        diff_name = rewards.get("difficulty_name", rewards.get("difficulty", "未知"))
        desc = rewards.get("description", "")

        if is_expired_claim:
            status_text = "⚠️ 时限已过，请尽快使用 /完成悬赏 领取奖励（即将失效）"
        elif remaining > 0:
            status_text = f"⏳ 剩余时间：{remaining // 60} 分钟（到时限后可领取奖励）"
        else:
            status_text = "✅ 时限已到，使用 /完成悬赏 领取奖励"

        return True, (
            f"📜 当前悬赏（{diff_name}）\n"
            f"━━━━━━━━━━━━━━━\n"
            f"任务：{active['bounty_name']}\n"
            f"说明：{desc}\n"
            f"{status_text}\n"
            f"奖励：{rewards.get('stone', 0):,} 灵石 + {rewards.get('exp', 0):,} 修为\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💡 使用 /完成悬赏 领取奖励"
        )

    async def complete_bounty(self, player: Player) -> Tuple[bool, str]:
        await self.db.conn.execute("BEGIN IMMEDIATE")
        try:
            active = await self.db.ext.get_active_bounty(player.user_id)
            is_expired_claim = False
            if not active:
                # 后台过期检查可能已将 status 改为 3，尝试查已过期的悬赏
                active = await self.db.ext.get_expired_bounty(player.user_id)
                if not active:
                    await self.db.conn.rollback()
                    return False, "你当前没有进行中的悬赏任务。"
                is_expired_claim = True

            now = int(time.time())
            # status=3 的悬赏已被后台标记为过期，跳过时限检查
            if not is_expired_claim and now < active["expire_time"]:
                remaining = (active["expire_time"] - now) // 60 or 1
                await self.db.conn.rollback()
                return False, (
                    f"⏳ 悬赏时限未到！\n"
                    f"任务：{active['bounty_name']}\n"
                    f"剩余时间：{remaining} 分钟\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"💡 到时限后使用 /完成悬赏 领取奖励"
                )

            rewards = json.loads(active["rewards"])
            stone_reward = rewards.get("stone", 0)
            exp_reward = rewards.get("exp", 0)

            await self.db.conn.execute(
                "UPDATE bounty_tasks SET status = 2 WHERE user_id = ? AND status IN (1, 3)",
                (player.user_id,)
            )

            MAX_VALUE = 2**63 - 1
            player.gold = min(player.gold + stone_reward, MAX_VALUE)
            player.experience = min(player.experience + exp_reward, MAX_VALUE)
            await self.db.conn.execute(
                "UPDATE players SET gold = ?, experience = ? WHERE user_id = ?",
                (player.gold, player.experience, player.user_id)
            )
            await self.db.conn.commit()
        except Exception:
            await self.db.conn.rollback()
            raise

        # 活跃度追踪
        if self.activity_tracker:
            try:
                await self.activity_tracker.track_bounty(player)
            except Exception:
                pass

        item_msg = ""
        if self.storage_ring_manager:
            try:
                rewards = json.loads(active["rewards"])
                item_table = rewards.get("item_table") or active.get("target_type", "gather")
                dropped_items = await self._roll_bounty_items(player, item_table)
                if dropped_items:
                    lines = []
                    for item_name, count in dropped_items:
                        success, _ = await self.storage_ring_manager.store_item(player, item_name, count, silent=True)
                        if success:
                            lines.append(f"  · {item_name} x{count}")
                        else:
                            lines.append(f"  · {item_name} x{count}（储物戒已满，丢失）")
                    if lines:
                        item_msg = "\n\n📦 获得物品：\n" + "\n".join(lines)
            except Exception:
                logger.warning("悬赏物品奖励发放异常", exc_info=True)

        # 功法/神通掉落（100%掉落）
        drop_msg = ""
        rewards = json.loads(active["rewards"])
        drop_reward = rewards.get("drop_reward")
        if drop_reward and self.storage_ring_manager:
            drop_name = drop_reward["name"]
            drop_rank = drop_reward.get("rank", "")
            drop_type = drop_reward.get("type", "main_technique")
            success, _ = await self.storage_ring_manager.store_item(player, drop_name, 1, silent=True)
            if drop_type == "skill":
                icon = "⚡"
                type_label = "神通"
            elif drop_type == "sub_technique":
                icon = "🔮"
                type_label = "辅修功法"
            else:
                icon = "📖"
                type_label = "功法"
            if success:
                drop_msg = f"\n\n{icon} 获得{type_label}：【{drop_rank}】{drop_name}"
            else:
                drop_msg = f"\n\n{icon} {type_label}【{drop_rank}】{drop_name}（储物戒已满，丢失）"

        diff_name = rewards.get("difficulty_name", rewards.get("difficulty", "未知"))
        return True, (
            f"✅ 悬赏完成（{diff_name}）！\n"
            f"任务：{active['bounty_name']}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"获得灵石：+{rewards.get('stone', 0):,}\n"
            f"获得修为：+{rewards.get('exp', 0):,}{item_msg}{drop_msg}"
        )

    async def abandon_bounty(self, player: Player) -> Tuple[bool, str]:
        active = await self.db.ext.get_active_bounty(player.user_id)
        if not active:
            # 也检查已过期的悬赏
            active = await self.db.ext.get_expired_bounty(player.user_id)
            if not active:
                return False, "你当前没有进行中的悬赏任务。"

        await self.db.ext.cancel_bounty(player.user_id)
        abandon_cooldown = int(time.time()) + 1800
        await self.db.ext.set_system_config(f"bounty_abandon_cd_{player.user_id}", str(abandon_cooldown))
        return True, f"已放弃悬赏：{active['bounty_name']}\n⚠️ 30分钟内无法接取新悬赏"

    # -------- 进度与奖励 --------

    async def _roll_bounty_items(self, player: Player, table_name: str) -> List[Tuple[str, int]]:
        dropped_items: List[Tuple[str, int]] = []
        drop_table = self.item_tables.get(table_name, self.item_tables.get("gather", []))
        if not drop_table or random.randint(1, 100) > 70:
            return dropped_items

        total_weight = sum(item["weight"] for item in drop_table)
        roll = random.randint(1, total_weight)
        upto = 0
        chosen = drop_table[0]
        for item in drop_table:
            upto += item["weight"]
            if roll <= upto:
                chosen = item
                break

        count = random.randint(chosen["min"], chosen["max"])
        dropped_items.append((chosen["name"], count))
        return dropped_items

    async def check_and_expire_bounties(self) -> int:
        now = int(time.time())
        cursor = await self.db.conn.execute(
            "UPDATE bounty_tasks SET status = 3 WHERE status = 1 AND expire_time < ?",
            (now,)
        )
        await self.db.conn.commit()
        return cursor.rowcount
