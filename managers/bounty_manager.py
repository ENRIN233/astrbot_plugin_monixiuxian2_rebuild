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

    # 功法掉落品阶配置
    TECHNIQUE_RANK_ORDER = ["凡品", "灵品", "地品", "天品", "皇品", "帝品", "道品", "仙品", "混元先天"]
    TECHNIQUE_RANK_LEVEL = {
        "凡品": 0, "灵品": 10, "地品": 12, "天品": 13,
        "皇品": 16, "帝品": 22, "道品": 28, "仙品": 32, "混元先天": 35,
    }
    TECHNIQUE_BASE_WEIGHT = {
        "凡品": 1000, "灵品": 400, "地品": 150, "天品": 60,
        "皇品": 20, "帝品": 8, "道品": 3, "仙品": 1, "混元先天": 0.3,
    }
    TECHNIQUE_DROP_CHANCE = {"easy": 10, "normal": 20, "hard": 35, "elite": 50}
    TECHNIQUE_HALF_LIFE = 5.0
    DAILY_BOUNTY_LIMIT = 2

    def __init__(self, db: DataBase, storage_ring_manager: Optional["StorageRingManager"] = None,
                 items_data: Optional[Dict[str, dict]] = None):
        self.db = db
        self.storage_ring_manager = storage_ring_manager
        self._bounty_cache: Dict[str, Dict] = {}
        self.difficulties: Dict[str, dict] = {}
        self.templates_by_id: Dict[int, dict] = {}
        self.templates_by_diff: Dict[str, List[dict]] = {}
        self.item_tables: Dict[str, List[dict]] = {}
        self._technique_pool: Dict[str, List[tuple]] = {}  # rank -> [(name, item_cfg), ...]
        self.items_data = items_data or {}
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
        self._build_technique_pool()

    def _build_technique_pool(self):
        """从 items_data 构建功法池，按品阶分桶"""
        self._technique_pool = {}
        for name, item_cfg in self.items_data.items():
            if item_cfg.get("type") != "main_technique":
                continue
            rank = item_cfg.get("rank", "凡品")
            self._technique_pool.setdefault(rank, []).append((name, item_cfg))
        total = sum(len(v) for v in self._technique_pool.values())
        logger.info(f"功法池构建完成：{total} 个功法，覆盖 {len(self._technique_pool)} 个品阶")

    def _roll_bounty_technique(self, player: Player, difficulty: str) -> Optional[dict]:
        """预判功法掉落：概率检定 + 动态加权选一个"""
        drop_chance = self.TECHNIQUE_DROP_CHANCE.get(difficulty, 10)
        if random.randint(1, 100) > drop_chance:
            return None

        player_rank = self._get_player_rank(player.level_index)
        player_rank_idx = self.TECHNIQUE_RANK_ORDER.index(player_rank) if player_rank in self.TECHNIQUE_RANK_ORDER else 0

        candidates = []
        for rank, pool in self._technique_pool.items():
            if not pool:
                continue
            rank_weight = self.TECHNIQUE_BASE_WEIGHT.get(rank, 1.0)
            if rank_weight <= 0:
                continue
            rank_level = self.TECHNIQUE_RANK_LEVEL.get(rank, 0)
            rank_idx = self.TECHNIQUE_RANK_ORDER.index(rank) if rank in self.TECHNIQUE_RANK_ORDER else 0
            gap = rank_idx - player_rank_idx

            if gap <= 0:
                level_diff = player.level_index - rank_level
                factor = 0.5 ** (level_diff / self.TECHNIQUE_HALF_LIFE)
            elif gap == 1:
                factor = 0.1
            else:
                factor = 0.01

            adjusted = rank_weight * factor
            if adjusted > 0.001:
                candidates.append((rank, pool, adjusted))

        if not candidates:
            return None

        total_weight = sum(w for _, _, w in candidates)
        roll = random.uniform(0, total_weight)
        cumulative = 0.0
        chosen_rank, chosen_pool, _ = candidates[0]
        for rank, pool, weight in candidates:
            cumulative += weight
            if roll <= cumulative:
                chosen_rank, chosen_pool = rank, pool
                break

        name, cfg = random.choice(chosen_pool)
        return {
            "name": name, "rank": chosen_rank,
            "exp_multiplier": cfg.get("exp_multiplier", 1.0),
            "breakthrough_bonus": cfg.get("breakthrough_bonus", 0.0),
            "atk_bonus": cfg.get("atk_bonus", 0),
            "hp_bonus": cfg.get("hp_bonus", 0.0)
        }

    @staticmethod
    def _get_player_rank(level_index: int) -> str:
        sorted_ranks = sorted(
            BountyManager.TECHNIQUE_RANK_LEVEL.items(), key=lambda x: x[1], reverse=True
        )
        for rank, level in sorted_ranks:
            if level_index >= level:
                return rank
        return "凡品"

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
        technique_reward = self._roll_bounty_technique(player, difficulty)
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
            "technique_reward": technique_reward
        }

    def _calculate_reward(self, template: dict, diff_cfg: dict, player: Player, target: int) -> Dict[str, int]:
        base_reward = template.get("reward", {"stone": 200, "exp": 2000})
        stone = base_reward.get("stone", 0)
        exp = base_reward.get("exp", 0)
        level_bonus = 1 + max(0, player.level_index - 3) * 0.06
        progress_factor = max(1, target) / max(1, template.get("min_target", 1))
        stone_scale = diff_cfg.get("stone_scale", 1.0)
        exp_scale = diff_cfg.get("exp_scale", 1.0)
        final_stone = int(stone * stone_scale * progress_factor * level_bonus)
        final_exp = int(exp * exp_scale * progress_factor * level_bonus)
        return {"stone": final_stone, "exp": final_exp}

    def _calculate_time_limit(self, template: dict, target: int) -> int:
        return template.get("time_limit", 3600)

    # -------- 接取与状态 --------

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
                "technique_reward": cached.get("technique_reward")
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

        # 功法掉落
        tech_msg = ""
        rewards = json.loads(active["rewards"])
        tech_reward = rewards.get("technique_reward")
        if tech_reward and self.storage_ring_manager:
            tech_name = tech_reward["name"]
            tech_rank = tech_reward.get("rank", "")
            success, _ = await self.storage_ring_manager.store_item(player, tech_name, 1, silent=True)
            if success:
                tech_msg = f"\n\n📖 获得功法：【{tech_rank}】{tech_name}"
            else:
                tech_msg = f"\n\n📖 功法【{tech_rank}】{tech_name}（储物戒已满，丢失）"

        diff_name = rewards.get("difficulty_name", rewards.get("difficulty", "未知"))
        return True, (
            f"✅ 悬赏完成（{diff_name}）！\n"
            f"任务：{active['bounty_name']}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"获得灵石：+{rewards.get('stone', 0):,}\n"
            f"获得修为：+{rewards.get('exp', 0):,}{item_msg}{tech_msg}"
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
