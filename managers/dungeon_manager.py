# managers/dungeon_manager.py
"""
探险副本管理器 - 肉鸽玩法核心逻辑
1-2-2 分支地图，选一次走两步，每日奖励上限
"""

import random
import time
import math
import json
from typing import Tuple, Dict, Optional, List
from astrbot.api import logger
from ..models_extended import DungeonNode, DungeonCycle, DungeonRun, UserStatus
from ..models import Player
from ..data.data_manager import DataBase


class DungeonManager:
    """探险副本管理器"""

    def __init__(self, db: DataBase, config_manager):
        self.db = db
        self.config_manager = config_manager

    def _get_dungeon_config(self, key: str) -> Optional[dict]:
        """从配置中获取指定探险"""
        dungeons = self.config_manager.dungeon_config.get("dungeons", [])
        for d in dungeons:
            if d.get("key") == key:
                return d
        return None

    def _get_global_config(self) -> dict:
        return self.config_manager.dungeon_config.get("global", {})

    # ==================== 公开接口 ====================

    async def get_available_dungeons(self, player: Player) -> Tuple[bool, str]:
        """列出玩家可进入的探险"""
        dungeons = self.config_manager.dungeon_config.get("dungeons", [])
        if not dungeons:
            return False, "暂无可用探险。"

        lines = ["🌀 探险列表", "━━━━━━━━━━━━━━━"]
        for d in dungeons:
            lvl = d.get("min_level", 0)
            cap_gold = d.get("daily_reward_cap", 0)
            cap_exp = d.get("daily_reward_cap_exp", 0)
            lines.append(
                f"· 【{d['name']}】\n"
                f"  推荐境界等级 ≥ {lvl} | 深度 {d.get('max_depth', 30)}\n"
                f"  每日奖励上限: 灵石{cap_gold:,} 修为{cap_exp:,}\n"
                f"  {d.get('description', '')}"
            )
        lines.append("━━━━━━━━━━━━━━━")
        lines.append(
            "💡 指令用法:\n"
            "  /进入探险 <名称> — 进入探险\n"
            "  /探险前进 [序号] — 前进并选择路径\n"
            "  /探险状态 — 查看当前副本状态\n"
            "  /探险撤离 — 主动撤离，结算已有奖励"
        )
        return True, "\n".join(lines)

    async def enter_dungeon(
        self, user_id: str, dungeon_key: str, player: Player
    ) -> Tuple[bool, str]:
        """进入探险副本"""
        # 检查是否已在副本中
        existing = await self.db.ext.get_dungeon_run(user_id)
        if existing:
            return False, "你已在探险中，请先完成或撤离当前副本。\n💡 /探险状态 | /探险撤离"

        dungeon = self._get_dungeon_config(dungeon_key)
        if not dungeon:
            return False, f"未找到探险「{dungeon_key}」。"

        # 境界检查
        if player.level_index < dungeon.get("min_level", 0):
            return False, f"境界不足，进入【{dungeon['name']}】需要等级 ≥ {dungeon.get('min_level', 0)}。"

        # 构建玩家战斗属性来计算血量
        from .combat_manager import CombatManager
        impart_info = await self.db.ext.get_impart_info(user_id)
        stats = CombatManager.build_player_combat_stats(player, impart_info, self.config_manager)

        # 灵力计算（基础 + 境界缩放）
        base_stamina = dungeon.get("base_stamina", 20)
        scaling = dungeon.get("stamina_scaling", {})
        extra = int(player.level_index * scaling.get("per_level", 0.5))
        max_stamina = base_stamina + extra

        now = int(time.time())
        expire_hours = self._get_global_config().get("run_expire_hours", 24)

        run = DungeonRun(
            user_id=user_id,
            dungeon_key=dungeon_key,
            depth=0,
            stamina=max_stamina,
            max_stamina=max_stamina,
            hp=stats.max_hp,
            max_hp=stats.max_hp,
            overdraft_count=0,
            inventory="{}",
            log="[]",
            current_cycle="{}",
            chosen_path="",
            step_in_cycle=0,
            state="choosing",
            daily_reward_earned=0,
            daily_exp_earned=0,
            create_time=now,
            expire_time=now + expire_hours * 3600,
        )

        # 生成树形地图
        map_graph = self._generate_map_layer(run, dungeon)
        run.set_map_graph(map_graph)
        run.current_node_id = "n0"

        await self.db.ext.save_dungeon_run(run)
        await self.db.ext.set_user_busy(
            user_id, UserStatus.EXPLORING, run.expire_time,
            extra_data={"type": "dungeon", "dungeon_key": dungeon_key}
        )

        # 渲染初始地图
        map_text = self._render_map(run, dungeon)
        return True, (
            f"═══ 进入【{dungeon['name']}】═══\n"
            f"灵力: {max_stamina}/{max_stamina} | 血量: {stats.max_hp:,}/{stats.max_hp:,}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"{map_text}"
        )

    async def choose_and_advance(
        self, user_id: str, choice: str, player: Player
    ) -> Tuple[bool, str]:
        """选择路径并前进（核心循环）"""
        run = await self.db.ext.get_dungeon_run(user_id)
        if not run:
            return False, "你当前没有进行中的探险。"

        if run.state == "done":
            return False, "副本已结束，请使用 /探险撤离 结算奖励。"

        dungeon = self._get_dungeon_config(run.dungeon_key)
        if not dungeon:
            return False, "探险配置异常，请联系管理员。"

        # 过期检查
        if int(time.time()) > run.expire_time:
            return await self._force_settle(run, player, "探险已过期，强制结算。")

        graph = run.get_map_graph()
        if graph and graph.get("nodes"):
            # 新版树形地图
            return await self._advance_tree(run, graph, choice, dungeon, player)
        else:
            # 旧版兼容：周期地图
            cycle = run.get_current_cycle()
            path_a = cycle.get_path_a()
            path_b = cycle.get_path_b()
            if not path_a or not path_b:
                return False, "地图数据异常，请联系管理员。"

            if run.state == "choosing":
                return await self._handle_choice(run, cycle, path_a, path_b, choice, dungeon, player)
            elif run.state == "walking":
                return await self._handle_walking(run, dungeon, player)
            elif run.state == "boss":
                return await self._handle_boss(run, dungeon, player)
            else:
                return False, "未知副本状态。"

    async def _advance_tree(
        self, run: DungeonRun, graph: dict,
        choice: str, dungeon: dict, player: Player
    ) -> Tuple[bool, str]:
        """新版树形地图的状态机"""
        if run.state == "boss":
            return await self._handle_boss(run, dungeon, player)

        if run.state != "choosing":
            return False, "未知副本状态。"

        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        node_map = {n["id"]: n for n in nodes}

        # 构建 children 映射
        children_of = {}
        for e in edges:
            children_of.setdefault(e["from"], []).append(e["to"])

        current_id = run.current_node_id or "n0"
        current_node = node_map.get(current_id)
        if not current_node:
            return False, "地图数据异常，请联系管理员。"

        # 获取子节点
        child_ids = children_of.get(current_id, [])
        child_nodes = [node_map[cid] for cid in child_ids if cid in node_map]

        if not child_nodes:
            # 无子节点，不应该发生
            return False, "无路可走，请联系管理员。"

        # 确定要前进的目标节点
        target_node = None

        if len(child_nodes) == 1:
            # 只有一个子节点 → 自动前进
            target_node = child_nodes[0]
        else:
            # 两个子节点 → 等待玩家选择
            choice_stripped = choice.strip().lower()

            # 尝试匹配节点ID（如 n2/n3）
            for cn in child_nodes:
                if choice_stripped == cn["id"].lower():
                    target_node = cn
                    break

            # 尝试匹配序号（1/2）
            if not target_node:
                try:
                    idx = int(choice_stripped) - 1
                    if 0 <= idx < len(child_nodes):
                        target_node = child_nodes[idx]
                except ValueError:
                    pass

            if not target_node:
                # 无效选择，展示地图
                map_text = self._render_tree_map(run, dungeon, graph)
                opts = " / ".join(
                    f"{i+1}.{cn['label']}" for i, cn in enumerate(child_nodes)
                )
                return False, f"请选择路径: {opts}\n{map_text}"

        # 消耗灵力
        stamina_msg = ""
        if run.stamina > 0:
            run.stamina -= 1
        else:
            overdraft_result = self._apply_overdraft(run, dungeon)
            stamina_msg = f"\n{overdraft_result}"
            if run.hp <= 0:
                run.state = "done"
                await self.db.ext.save_dungeon_run(run)
                settle_msg = await self._settle_and_finish(run, player, victory=False)
                return True, (
                    f"💀 灵力枯竭，你倒在了探险中...\n\n{settle_msg[1]}"
                )

        # 构建战斗属性（用于战斗节点）
        from .combat_manager import CombatManager
        impart_info = await self.db.ext.get_impart_info(run.user_id)
        player_stats = CombatManager.build_player_combat_stats(
            player, impart_info, self.config_manager
        )
        player_stats.hp = run.hp
        player_stats.max_hp = run.max_hp

        # 处理节点效果
        step_icons = {
            "entry": "🔵", "monster": "⚔️", "elite": "💀", "treasure": "📦",
            "spring": "💧", "campfire": "🔥", "theme_mine": "⛏️",
            "nothing": "🍃", "merchant": "🏪", "boss": "🔴",
        }

        node_result_text = ""
        if target_node["type"] == "boss":
            # 到达Boss，不处理效果，直接标记
            pass
        else:
            # 将 dict 节点转为 DungeonNode 以复用 _process_node
            fake_node = DungeonNode(
                step=0,
                node_type=target_node["type"],
                label=target_node["label"],
                detail=0,
            )
            result = await self._process_node(
                run, fake_node, player_stats, dungeon, player
            )
            node_result_text = result.get("text", "")

        # 同步血量
        run.hp = max(0, player_stats.hp) if target_node["type"] not in ("boss",) else run.hp

        # 检查死亡
        if run.hp <= 0:
            run.state = "done"
            await self.db.ext.save_dungeon_run(run)
            settle_msg = await self._settle_and_finish(run, player, victory=False)
            icon = step_icons.get(target_node["type"], "❓")
            return True, (
                f"{icon} {node_result_text}\n"
                f"💀 血量耗尽，探险崩塌！\n\n{settle_msg[1]}"
            )

        # 标记节点已访问，记录父节点（用于路径回溯渲染）
        target_node["visited"] = True
        target_node["parent_id"] = current_id
        run.current_node_id = target_node["id"]
        run.depth += 1
        run.set_map_graph(graph)

        # 判断下一状态
        if target_node["type"] == "boss":
            run.state = "boss"
            await self.db.ext.save_dungeon_run(run)
            boss_name = target_node["label"]
            return True, (
                f"═══ 到达核心区域 ═══\n"
                f"【{boss_name}】出现了！\n"
                f"血量: {run.hp:,}/{run.max_hp:,}\n"
                f"输入 /探险前进 应战！"
            )

        # 仍在探索中
        run.state = "choosing"
        await self.db.ext.save_dungeon_run(run)

        # 渲染结果
        icon = step_icons.get(target_node["type"], "❓")
        max_d = dungeon.get("max_depth", 30)
        map_text = self._render_tree_map(run, dungeon, graph)
        stamina_bar = self._progress_bar(run.stamina, run.max_stamina, 8)
        hp_bar = self._progress_bar(run.hp, run.max_hp, 8)

        result_lines = [
            f"{icon} {node_result_text}" if node_result_text else f"{icon} {target_node['label']}",
            stamina_msg,
            "",
            f"═══ 深度 {run.depth}/{max_d} ═══",
            f"灵力: {stamina_bar} {run.stamina}/{run.max_stamina} | "
            f"血量: {hp_bar} {run.hp:,}/{run.max_hp:,}",
            "",
            map_text,
        ]
        return True, "\n".join(filter(None, result_lines))

    async def get_status(self, user_id: str) -> Tuple[bool, str]:
        """查看副本状态"""
        run = await self.db.ext.get_dungeon_run(user_id)
        if not run:
            return False, "你当前没有进行中的探险。"

        dungeon = self._get_dungeon_config(run.dungeon_key)
        d_name = dungeon["name"] if dungeon else "未知"

        inv = run.get_inventory()
        lingshi = inv.get("lingshi", 0)
        exp_earned = inv.get("exp", 0)
        items = {k: v for k, v in inv.items() if k not in ("lingshi", "exp")}
        item_lines = []
        for name, cnt in items.items():
            item_lines.append(f"  · {name} x{cnt}" if cnt > 1 else f"  · {name}")

        stamina_bar = self._progress_bar(run.stamina, run.max_stamina, 10)
        hp_bar = self._progress_bar(run.hp, run.max_hp, 10)
        tier_label = self._get_tier_label(run.depth, dungeon)

        lines = [
            f"═══ {d_name} ═══",
            f"深度: {run.depth}/{dungeon.get('max_depth', 30) if dungeon else '?'} [{tier_label}]",
            f"灵力: {stamina_bar} {run.stamina}/{run.max_stamina}",
            f"血量: {hp_bar} {run.hp:,}/{run.max_hp:,}",
            f"透支次数: {run.overdraft_count}",
            "",
            f"🎒 临时背包:",
            f"  · 灵石 x{lingshi:,}" if lingshi else "  (空)",
            f"  · 修为 x{exp_earned:,}" if exp_earned else "",
        ]
        lines.extend(item_lines)
        lines.append("")
        daily = await self.db.ext.get_dungeon_daily_reward(user_id)
        cap_gold = dungeon.get("daily_reward_cap", 0) if dungeon else 0
        cap_exp = dungeon.get("daily_reward_cap_exp", 0) if dungeon else 0
        lines.append(f"📊 今日已获取: 灵石 {daily['gold']:,}/{cap_gold:,} | 修为 {daily['exp']:,}/{cap_exp:,}")

        state_desc = {
            "choosing": "等待选择路径",
            "walking": "正在前进中...",
            "boss": "BOSS战中！",
        }
        lines.append(f"\n当前状态: {state_desc.get(run.state, run.state)}")

        # 如果在选择状态，显示地图
        if run.state == "choosing" and dungeon:
            lines.append("")
            lines.append(self._render_map(run, dungeon))

        return True, "\n".join(lines)

    async def retreat(self, user_id: str, player: Player) -> Tuple[bool, str]:
        """主动撤离，结算已有奖励"""
        run = await self.db.ext.get_dungeon_run(user_id)
        if not run:
            return False, "你当前没有进行中的探险。"

        return await self._settle_and_finish(run, player, victory=False, is_retreat=True)

    async def show_current_map(self, user_id: str) -> Tuple[bool, str]:
        """重新展示当前地图（用于 /探险前进 无参数时）"""
        run = await self.db.ext.get_dungeon_run(user_id)
        if not run:
            return False, "你当前没有进行中的探险。"

        dungeon = self._get_dungeon_config(run.dungeon_key)
        if not dungeon:
            return False, "探险配置异常。"

        if run.state == "choosing":
            map_text = self._render_map(run, dungeon)
            graph = run.get_map_graph()
            if graph and graph.get("nodes"):
                # 新版树形地图
                return True, f"请选路:\n{map_text}"
            else:
                # 旧版兼容
                return True, f"请选路:\n{map_text}\n输入 A 或 B"
        elif run.state == "boss":
            return True, "BOSS战即将开始！输入 /探险前进 应战。"
        else:
            return True, "正在前进中，请稍候..."

    # ==================== 内部逻辑 ====================

    async def _handle_choice(
        self, run: DungeonRun, cycle: DungeonCycle,
        path_a: list, path_b: list,
        choice: str, dungeon: dict, player: Player
    ) -> Tuple[bool, str]:
        """处理玩家的路径选择，然后自动走3步"""
        choice = choice.strip().upper()
        if choice not in ("A", "B"):
            map_text = self._render_map(run, dungeon)
            return False, f"请输入 A 或 B 选择路径:\n{map_text}"

        run.chosen_path = choice
        run.step_in_cycle = 0
        run.state = "walking"
        await self.db.ext.save_dungeon_run(run)

        # 自动走3步
        return await self._walk_three_steps(run, cycle, dungeon, player)

    async def _handle_walking(
        self, run: DungeonRun, dungeon: dict, player: Player
    ) -> Tuple[bool, str]:
        """walking 状态 - 理论上不会触发（选择后自动走完）"""
        return True, "正在前进中，请稍候..."

    async def _handle_boss(
        self, run: DungeonRun, dungeon: dict, player: Player
    ) -> Tuple[bool, str]:
        """处理BOSS战"""
        boss_config = dungeon.get("boss", {})
        from .combat_manager import CombatManager
        impart_info = await self.db.ext.get_impart_info(run.user_id)
        player_stats = CombatManager.build_player_combat_stats(player, impart_info, self.config_manager)
        # 使用副本内血量
        player_stats.hp = run.hp
        player_stats.max_hp = run.max_hp

        # 构建BOSS属性
        boss_hp = int(run.max_hp * boss_config.get("hp_mult", 5.0))
        boss_atk = int(player_stats.atk * boss_config.get("atk_mult", 2.0))
        boss_stats = CombatManager(
        ) if False else None  # placeholder - 直接用 CombatStats
        from .combat_manager import CombatStats
        boss_stats = CombatStats(
            user_id="boss",
            name=boss_config.get("name", "探险守护兽"),
            hp=boss_hp,
            max_hp=boss_hp,
            mp=0,
            max_mp=0,
            atk=boss_atk,
            base_def=player_stats.base_def * 0.8,
            equip_def=int(player_stats.equip_def * 0.5),
            crit_rate=5,
            crit_damage=1.5,
        )

        # 战斗（使用副本简化战斗）
        result = self._dungeon_combat(player_stats, boss_stats)

        # 更新副本血量
        run.hp = max(0, player_stats.hp)

        if result["victory"]:
            run.state = "done"
            # BOSS奖励: 二选一
            reward_pool = boss_config.get("reward_pool", [])
            choices = self._roll_boss_rewards(reward_pool, boss_config.get("reward_choices", 2))
            inv = run.get_inventory()
            reward_lines = ["🏆 击败探险守护兽！\n请选择一项奖励:"]

            for i, r in enumerate(choices):
                reward_lines.append(f"  {chr(65+i)}. {r['name']} x{r.get('count', 1)}")

            # 暂存选择，先不给奖励（等玩家选）
            run.add_log({"type": "boss_victory", "choices": choices})
            await self.db.ext.save_dungeon_run(run)

            # TODO: 此处简化为随机给第一个奖励
            chosen = choices[0]
            name = chosen["name"]
            cnt = chosen.get("count", 1)
            inv[name] = inv.get(name, 0) + cnt
            run.set_inventory(inv)

            settle_msg = await self._settle_and_finish(run, player, victory=True, boss_reward=chosen)
            return True, (
                f"{result['summary']}\n\n"
                f"🎁 BOSS奖励: {name} x{cnt}\n\n"
                f"{settle_msg[1]}"
            )
        else:
            # BOSS战败 - 探险崩塌
            settle_msg = await self._settle_and_finish(run, player, victory=False)
            return True, (
                f"{result['summary']}\n\n"
                f"💀 你被守护兽击败，探险崩塌！\n\n"
                f"{settle_msg[1]}"
            )

    async def _walk_three_steps(
        self, run: DungeonRun, cycle: DungeonCycle,
        dungeon: dict, player: Player
    ) -> Tuple[bool, str]:
        """自动走3步，每步处理节点事件"""
        path_a = cycle.get_path_a()
        path_b = cycle.get_path_b()
        chosen_path = path_a if run.chosen_path == "A" else path_b

        output_lines = []
        step_icons = {
            "monster": "⚔️", "elite": "💀", "treasure": "📦",
            "spring": "💧", "campfire": "🔥", "theme_mine": "⛏️",
            "nothing": "🍃", "merchant": "🏪",
        }

        from .combat_manager import CombatManager
        impart_info = await self.db.ext.get_impart_info(run.user_id)
        player_stats = CombatManager.build_player_combat_stats(player, impart_info, self.config_manager)
        player_stats.hp = run.hp
        player_stats.max_hp = run.max_hp

        for i, node in enumerate(chosen_path):
            # 消耗灵力
            if run.stamina > 0:
                run.stamina -= 1
            else:
                # 透支
                overdraft_result = self._apply_overdraft(run, dungeon)
                output_lines.append(overdraft_result)
                if run.hp <= 0:
                    run.state = "done"
                    settle_msg = await self._settle_and_finish(run, player, victory=False)
                    return True, (
                        "\n".join(output_lines) +
                        "\n\n💀 灵力枯竭，你倒在了探险中...\n\n" +
                        settle_msg[1]
                    )

            # 处理节点
            icon = step_icons.get(node.node_type, "❓")
            node_result = await self._process_node(
                run, node, player_stats, dungeon, player
            )
            output_lines.append(f"  {icon} {node_result['text']}")

            # 检查死亡
            if run.hp <= 0:
                run.state = "done"
                settle_msg = await self._settle_and_finish(run, player, victory=False)
                return True, (
                    "\n".join(output_lines) +
                    "\n\n💀 血量耗尽，探险崩塌！\n\n" +
                    settle_msg[1]
                )

            run.depth += 1

        # 3步走完，检查是否到达BOSS深度
        max_depth = dungeon.get("max_depth", 30)
        if run.depth >= max_depth:
            run.state = "boss"
            run.hp = player_stats.hp  # 同步血量
            await self.db.ext.save_dungeon_run(run)
            boss_name = dungeon.get("boss", {}).get("name", "探险守护兽")
            return True, (
                "\n".join(output_lines) +
                f"\n\n═══ 到达核心区域 ═══\n"
                f"【{boss_name}】出现了！\n"
                f"血量: {run.hp:,}/{run.max_hp:,}\n"
                f"输入 /探险前进 应战！"
            )

        # 生成下一个周期
        new_cycle = self._generate_cycle(run, dungeon)
        run.set_current_cycle(new_cycle)
        run.chosen_path = ""
        run.step_in_cycle = 0
        run.state = "choosing"
        run.hp = player_stats.hp  # 同步血量
        await self.db.ext.save_dungeon_run(run)

        # 展示结果 + 新地图
        map_text = self._render_map(run, dungeon)
        stamina_bar = self._progress_bar(run.stamina, run.max_stamina, 8)
        hp_bar = self._progress_bar(run.hp, run.max_hp, 8)

        result_text = "\n".join(output_lines)
        return True, (
            f"{result_text}\n\n"
            f"═══ 深度 {run.depth}/{max_depth} ═══\n"
            f"灵力: {stamina_bar} {run.stamina}/{run.max_stamina} | "
            f"血量: {hp_bar} {run.hp:,}/{run.max_hp:,}\n\n"
            f"{map_text}"
        )

    async def _process_node(
        self, run: DungeonRun, node: DungeonNode,
        player_stats, dungeon: dict, player: Player
    ) -> dict:
        """处理单个节点事件，返回 {text, ...}"""
        tier_mult = self._get_tier_mult(run.depth, dungeon)
        pool_cfg = dungeon.get("node_pool", {}).get(node.node_type, {})

        if node.node_type == "monster":
            return await self._process_monster_node(run, node, player_stats, pool_cfg, tier_mult, False)
        elif node.node_type == "elite":
            return await self._process_monster_node(run, node, player_stats, pool_cfg, tier_mult, True)
        elif node.node_type == "treasure":
            return self._process_treasure_node(run, node, pool_cfg, tier_mult)
        elif node.node_type == "spring":
            return self._process_spring_node(run, node, pool_cfg)
        elif node.node_type == "campfire":
            return self._process_campfire_node(run, node, player)
        elif node.node_type == "theme_mine":
            return self._process_theme_mine_node(run, node, pool_cfg, tier_mult)
        elif node.node_type == "merchant":
            return self._process_merchant_node(run, node, pool_cfg)
        else:
            return {"text": f"{node.label} — 安全通过"}

    async def _process_monster_node(
        self, run: DungeonRun, node: DungeonNode,
        player_stats, pool_cfg: dict, tier_mult: float, is_elite: bool
    ) -> dict:
        """处理战斗节点"""
        from .combat_manager import CombatManager, CombatStats

        hp_mult = pool_cfg.get("hp_mult", 0.6 if not is_elite else 2.0)
        atk_mult = pool_cfg.get("atk_mult", 0.5 if not is_elite else 1.5)
        drop_bonus = pool_cfg.get("drop_bonus", 1.0 if not is_elite else 2.0)

        monster_hp = int(player_stats.max_hp * hp_mult * tier_mult)
        monster_atk = int(player_stats.atk * atk_mult * tier_mult)

        monster = CombatStats(
            user_id="monster",
            name=node.label,
            hp=monster_hp,
            max_hp=monster_hp,
            mp=0,
            max_mp=0,
            atk=monster_atk,
            base_def=player_stats.base_def * 0.6,
            equip_def=max(1, int(player_stats.equip_def * 0.3)),
            crit_rate=3,
            crit_damage=1.3,
        )

        result = self._dungeon_combat(player_stats, monster)
        run.hp = max(0, player_stats.hp)

        if result["victory"]:
            # 掉落
            base_gold = int((50 + run.depth * 20) * drop_bonus * tier_mult)
            base_exp = int((30 + run.depth * 15) * drop_bonus * tier_mult)
            inv = run.get_inventory()
            inv["lingshi"] = inv.get("lingshi", 0) + base_gold
            inv["exp"] = inv.get("exp", 0) + base_exp
            run.set_inventory(inv)
            run.daily_reward_earned += base_gold
            run.daily_exp_earned += base_exp

            return {
                "text": f"击败{node.label}！(灵石+{base_gold} 修为+{base_exp}) "
                        f"[HP: {run.hp:,}/{run.max_hp:,}]"
            }
        else:
            return {
                "text": f"不敌{node.label}... [HP: {run.hp:,}/{run.max_hp:,}]"
            }

    def _process_treasure_node(
        self, run: DungeonRun, node: DungeonNode,
        pool_cfg: dict, tier_mult: float
    ) -> dict:
        """宝箱节点"""
        base = pool_cfg.get("base_gold", 100)
        per_depth = pool_cfg.get("gold_per_depth", 30)
        gold = int((base + run.depth * per_depth) * tier_mult)

        # 随机掉落物品
        dungeon_cfg = self._get_dungeon_config(run.dungeon_key)
        drop_items = []
        if dungeon_cfg:
            boss_pool = dungeon_cfg.get("boss", {}).get("reward_pool", [])
            if boss_pool and random.random() < 0.3:
                item = random.choice(boss_pool)
                drop_items.append(item)

        inv = run.get_inventory()
        inv["lingshi"] = inv.get("lingshi", 0) + gold
        reward_text = f"灵石+{gold}"
        for item in drop_items:
            name = item["name"]
            cnt = item.get("count", 1)
            inv[name] = inv.get(name, 0) + cnt
            reward_text += f" {name}x{cnt}"
        run.set_inventory(inv)
        run.daily_reward_earned += gold

        return {"text": f"{node.label} — 获得 {reward_text}"}

    def _process_spring_node(
        self, run: DungeonRun, node: DungeonNode, pool_cfg: dict
    ) -> dict:
        """灵泉节点"""
        heal_pct = pool_cfg.get("heal_pct", 0.3)
        stamina_restore = pool_cfg.get("stamina_restore", 2)
        heal = int(run.max_hp * heal_pct)
        run.hp = min(run.max_hp, run.hp + heal)
        run.stamina = min(run.max_stamina, run.stamina + stamina_restore)
        return {
            "text": f"{node.label} — 回复{heal}HP +{stamina_restore}灵力 "
                    f"[HP: {run.hp:,} 灵力: {run.stamina}]"
        }

    def _process_campfire_node(
        self, run: DungeonRun, node: DungeonNode, player: Player
    ) -> dict:
        """篝火节点 - 回满血 + 按睡袋回灵力"""
        run.hp = run.max_hp
        bag_level = player.sleeping_bag_level
        dungeon = self._get_dungeon_config(run.dungeon_key)
        recovery_table = dungeon.get("sleeping_bag_recovery", [2, 4, 6, 8, 10, 13]) if dungeon else [2, 4, 6, 8, 10, 13]
        idx = min(bag_level, len(recovery_table) - 1)
        stam_restore = recovery_table[idx]
        old_stam = run.stamina
        run.stamina = min(run.max_stamina, run.stamina + stam_restore)
        actual = run.stamina - old_stam
        return {
            "text": f"{node.label} — 血量回满，灵力+{actual} "
                    f"(睡袋Lv.{bag_level}) [灵力: {run.stamina}/{run.max_stamina}]"
        }

    def _process_theme_mine_node(
        self, run: DungeonRun, node: DungeonNode,
        pool_cfg: dict, tier_mult: float
    ) -> dict:
        """主题挖矿节点 - 花灵力换灵石"""
        cost = pool_cfg.get("cost_stamina", 2)
        if run.stamina < cost:
            return {"text": f"{node.label} — 灵力不足(需{cost})，无法开采"}
        run.stamina -= cost
        base = pool_cfg.get("base_gold", 200)
        per_depth = pool_cfg.get("gold_per_depth", 50)
        gold = int((base + run.depth * per_depth) * tier_mult)
        inv = run.get_inventory()
        inv["lingshi"] = inv.get("lingshi", 0) + gold
        run.set_inventory(inv)
        run.daily_reward_earned += gold
        return {
            "text": f"{node.label} — 消耗{cost}灵力开采，获得灵石+{gold} "
                    f"[灵力: {run.stamina}/{run.max_stamina}]"
        }

    def _process_merchant_node(
        self, run: DungeonRun, node: DungeonNode, pool_cfg: dict
    ) -> dict:
        """商人节点 - 自动购买回血药"""
        items = pool_cfg.get("items", [])
        inv = run.get_inventory()
        lingshi = inv.get("lingshi", 0)

        bought = []
        for item in items:
            price = item.get("price", 0)
            if lingshi >= price:
                if item.get("heal_pct") and run.hp < run.max_hp:
                    lingshi -= price
                    heal = int(run.max_hp * item["heal_pct"])
                    run.hp = min(run.max_hp, run.hp + heal)
                    bought.append(f"{item['name']}(回血{heal})")
                elif item.get("stamina_restore") and run.stamina < run.max_stamina:
                    lingshi -= price
                    run.stamina = min(run.max_stamina, run.stamina + item["stamina_restore"])
                    bought.append(f"{item['name']}(灵力+{item['stamina_restore']})")
                # 跳过 escape 类型

        inv["lingshi"] = lingshi
        run.set_inventory(inv)

        if bought:
            return {"text": f"{node.label} — 购买了 {', '.join(bought)}"}
        else:
            return {"text": f"{node.label} — 灵石不足或无需补给，无事发生"}

    # ==================== 地图生成 ====================

    def _generate_cycle(self, run: DungeonRun, dungeon: dict) -> DungeonCycle:
        """生成一个 1-2-2 周期（6个节点）"""
        pool = dungeon.get("node_pool", {})
        rules = dungeon.get("branch_rules", {})
        weights = {k: v.get("weight", 0) for k, v in pool.items() if isinstance(v, dict) and "weight" in v}

        def pick_type(exclude=None, prefer_campfire=False):
            """按权重随机选节点类型"""
            w = dict(weights)
            if exclude:
                for e in (exclude if isinstance(exclude, list) else [exclude]):
                    w.pop(e, None)
            if prefer_campfire:
                w["campfire"] = w.get("campfire", 8) * 3
            if not w:
                return "nothing"
            types = list(w.keys())
            probs = list(w.values())
            return random.choices(types, weights=probs, k=1)[0]

        def make_node(step, node_type, detail=0):
            cfg = pool.get(node_type, {})
            labels = cfg.get("labels", [node_type])
            return DungeonNode(
                step=step,
                node_type=node_type,
                label=random.choice(labels),
                detail=detail,
            )

        # Step 1: 两个选项
        type_a = pick_type()
        type_b = pick_type(exclude=[type_a] if rules.get("no_duplicate_step1") else None)

        # Step 2: 每条路各一个
        step2_a = pick_type(exclude=["elite"] if rules.get("elite_on_step1_only") else None)
        step2_b = pick_type(exclude=["elite"] if rules.get("elite_on_step1_only") else None)
        step2_c = pick_type(exclude=["elite"] if rules.get("elite_on_step1_only") else None)
        step2_d = pick_type(exclude=["elite"] if rules.get("elite_on_step1_only") else None)

        # Step 3: 每条路各一个，倾向篝火
        prefer_cf = rules.get("campfire_on_step3_preferred", False)
        step3_a = pick_type(exclude=["elite"] if rules.get("elite_on_step1_only") else None, prefer_campfire=prefer_cf)
        step3_b = pick_type(exclude=["elite"] if rules.get("elite_on_step1_only") else None, prefer_campfire=prefer_cf)
        step3_c = pick_type(exclude=["elite"] if rules.get("elite_on_step1_only") else None, prefer_campfire=prefer_cf)
        step3_d = pick_type(exclude=["elite"] if rules.get("elite_on_step1_only") else None, prefer_campfire=prefer_cf)

        path_a = [make_node(1, type_a), make_node(2, step2_a), make_node(3, step3_a)]
        path_a_branch = [make_node(1, type_a), make_node(2, step2_b), make_node(3, step3_b)]
        path_b = [make_node(1, type_b), make_node(2, step2_c), make_node(3, step3_c)]
        path_b_branch = [make_node(1, type_b), make_node(2, step2_d), make_node(3, step3_d)]

        # 实际只需两条路（path_a 和 path_b 各3步）
        # 但每条路的 step2/step3 有变体，这里简化为各取一个
        cycle = DungeonCycle(
            cycle_index=run.depth // 3,
            depth_start=run.depth,
        )
        cycle.set_path_a(path_a)
        cycle.set_path_b(path_b)
        return cycle

    def _generate_map_layer(self, run: DungeonRun, dungeon: dict) -> dict:
        """生成一个7节点树形地图层：
        n0(入口) -> n1(分支) -> n2(分支) -> n4(合并) -> n5(分支) -> n6(Boss)
                                \           /             |
                                 n3(分支) --              (n5只有一个子节点n6)

        Returns: {"nodes": [...], "edges": [...]}
        """
        pool = dungeon.get("node_pool", {})
        rules = dungeon.get("branch_rules", {})
        weights = {
            k: v.get("weight", 0)
            for k, v in pool.items()
            if isinstance(v, dict) and "weight" in v
        }

        def pick_type(exclude=None, prefer_campfire=False):
            """按权重随机选节点类型"""
            w = dict(weights)
            if exclude:
                for e in (exclude if isinstance(exclude, list) else [exclude]):
                    w.pop(e, None)
            if prefer_campfire:
                w["campfire"] = w.get("campfire", 8) * 3
            if not w:
                return "nothing"
            types = list(w.keys())
            probs = list(w.values())
            return random.choices(types, weights=probs, k=1)[0]

        def make_node_info(node_id, node_type):
            """生成节点信息字典"""
            cfg = pool.get(node_type, {})
            labels = cfg.get("labels", [node_type])
            return {
                "id": node_id,
                "type": node_type,
                "label": random.choice(labels),
                "visited": False,
            }

        boss_name = dungeon.get("boss", {}).get("name", "探险守护兽")

        # n0: 入口
        n0 = {"id": "n0", "type": "entry", "label": "入口", "visited": True}

        # n1: 分支点（排除精英）
        n1_type = pick_type(exclude=["elite"] if rules.get("elite_on_step1_only") else None)
        n1 = make_node_info("n1", n1_type)

        # n2, n3: 两条分支
        n2_type = pick_type(exclude=["elite"] if rules.get("elite_on_step1_only") else None)
        n3_type = pick_type(exclude=["elite"] if rules.get("elite_on_step1_only") else None)
        n2 = make_node_info("n2", n2_type)
        n3 = make_node_info("n3", n3_type)

        # n4: 合并点（倾向篝火）
        prefer_cf = rules.get("campfire_on_step3_preferred", False)
        n4_type = pick_type(
            exclude=["elite"] if rules.get("elite_on_step1_only") else None,
            prefer_campfire=prefer_cf,
        )
        n4 = make_node_info("n4", n4_type)

        # n5: Boss前最后一个分支
        n5_type = pick_type(
            exclude=["elite"] if rules.get("elite_on_step1_only") else None,
            prefer_campfire=prefer_cf,
        )
        n5 = make_node_info("n5", n5_type)

        # n6: Boss
        n6 = {"id": "n6", "type": "boss", "label": boss_name, "visited": False}

        nodes = [n0, n1, n2, n3, n4, n5, n6]
        edges = [
            {"from": "n0", "to": "n1"},
            {"from": "n1", "to": "n2"},
            {"from": "n1", "to": "n3"},
            {"from": "n2", "to": "n4"},
            {"from": "n3", "to": "n4"},
            {"from": "n4", "to": "n5"},
            {"from": "n5", "to": "n6"},
        ]

        return {"nodes": nodes, "edges": edges}

    # ==================== 地图渲染 ====================

    def _render_map(self, run: DungeonRun, dungeon: dict) -> str:
        """渲染文字地图预览（新版树形地图 / 旧版周期地图兼容）"""
        graph = run.get_map_graph()
        if graph and graph.get("nodes"):
            return self._render_tree_map(run, dungeon, graph)

        # 旧版兼容：周期地图
        cycle = run.get_current_cycle()
        path_a = cycle.get_path_a()
        path_b = cycle.get_path_b()
        if not path_a or not path_b:
            return "(地图数据加载中...)"

        icons = {
            "monster": "⚔️", "elite": "💀", "treasure": "📦",
            "spring": "💧", "campfire": "🔥", "theme_mine": "⛏️",
            "nothing": "🍃", "merchant": "🏪",
        }

        def fmt_node(n: DungeonNode, detail_level: int = 0) -> str:
            icon = icons.get(n.node_type, "❓")
            if detail_level >= 2 and n.node_type in ("monster", "elite"):
                return f"{icon} ???"
            return f"{icon} {n.label}"

        a1 = fmt_node(path_a[0])
        a2 = fmt_node(path_a[1], 1)
        a3 = fmt_node(path_a[2], 2)
        b1 = fmt_node(path_b[0])
        b2 = fmt_node(path_b[1], 1)
        b3 = fmt_node(path_b[2], 2)

        max_d = dungeon.get("max_depth", 30)
        tier_label = self._get_tier_label(run.depth, dungeon)

        lines = [
            f"📍 [{tier_label}] 深度 {run.depth}/{max_d}",
            "",
            f"  ┌─ A {a1} ── {a2} ── {a3} ─┐",
            f"  │                         ├── 下一合并点",
            f"  └─ B {b1} ── {b2} ── {b3} ─┘",
            "",
            "  → 输入 A 或 B 选择路径",
        ]
        return "\n".join(lines)

    def _render_tree_map(self, run: DungeonRun, dungeon: dict, graph: dict) -> str:
        """渲染树形地图：只显示当前节点及其直接子节点，Boss始终在底部"""
        ICON_MAP = {
            "entry": "🔵", "monster": "⚔️", "elite": "💀", "treasure": "📦",
            "spring": "💧", "campfire": "🔥", "theme_mine": "⛏️",
            "nothing": "🍃", "merchant": "🏪", "boss": "🔴",
        }

        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        node_map = {n["id"]: n for n in nodes}
        boss_node = next((n for n in nodes if n["type"] == "boss"), None)

        # 构建 children 映射
        children_of = {}
        for e in edges:
            children_of.setdefault(e["from"], []).append(e["to"])

        current_id = run.current_node_id or "n0"
        current_node = node_map.get(current_id)
        if not current_node:
            return "(地图数据异常)"

        # 辅助：格式化单个节点
        def fmt_node(nd, is_current=False, force_unknown=False):
            icon = ICON_MAP.get(nd["type"], "❓")
            if is_current:
                return f"◀▶ {icon} {nd['label']}"
            if nd["visited"]:
                return f"✅ {icon} {nd['label']}"
            if force_unknown:
                return f"⚪ {icon} ???"
            return f"⚪ {icon} {nd['label']}"

        # 收集需要显示的节点（从当前节点开始的可见路径）
        # 规则：显示已访问的祖先路径 + 当前节点 + 直接子节点 + ... + Boss
        max_d = dungeon.get("max_depth", 30)
        tier_label = self._get_tier_label(run.depth, dungeon)
        stamina_bar = self._progress_bar(run.stamina, run.max_stamina, 10)

        lines = [
            f"📍 {tier_label} | 深度 {run.depth}/{max_d} | 灵力 {run.stamina}/{run.max_stamina}",
            "━━━━━━━━━━━━━━━",
        ]

        # 从入口到当前节点的路径（通过 parent_id 回溯）
        def find_path_to(target_id):
            """从 target_id 沿 parent_id 回溯到 n0，返回正序路径"""
            path = [target_id]
            nid = target_id
            while nid != "n0":
                nd = node_map.get(nid)
                parent = nd.get("parent_id") if nd else None
                if not parent:
                    break
                path.append(parent)
                nid = parent
            path.reverse()
            return path

        path_to_current = find_path_to(current_id)

        # 渲染路径上的已访问节点（不含当前节点）
        for nid in path_to_current[:-1]:
            nd = node_map.get(nid)
            if nd:
                lines.append(f"  {fmt_node(nd)}")
                lines.append("    │")

        # 渲染当前节点
        children = children_of.get(current_id, [])
        child_nodes = [node_map[cid] for cid in children if cid in node_map]

        if len(child_nodes) >= 2:
            # 有两个子节点：分支显示
            lines.append(f"  {fmt_node(current_node, is_current=True)}")
            lines.append("    ╱ ╲")
            for i, child in enumerate(child_nodes):
                # 计算该子节点到Boss的距离来决定是否显示 ???
                # 当前节点深度为 step，子节点深度为 step+1
                # 如果子节点不是直接相连的下一层（距离>1），显示 ???
                force_unk = False
                if not child["visited"] and child["type"] != "boss":
                    # 如果子节点还有子节点（非叶子），显示 ???
                    grandchildren = children_of.get(child["id"], [])
                    if grandchildren:
                        force_unk = True

                child_line = fmt_node(child, force_unknown=force_unk)
                lines.append(f"  {child_line}")

        elif len(child_nodes) == 1:
            # 只有一个子节点：直线连接
            child = child_nodes[0]
            lines.append(f"  {fmt_node(current_node, is_current=True)}")
            lines.append("    │")
            force_unk = False
            if not child["visited"] and child["type"] != "boss":
                grandchildren = children_of.get(child["id"], [])
                if grandchildren:
                    force_unk = True
            lines.append(f"  {fmt_node(child, force_unknown=force_unk)}")

        else:
            # 无子节点（理论上只在Boss节点）
            lines.append(f"  {fmt_node(current_node, is_current=True)}")

        # Boss 始终显示在底部（如果当前节点不是Boss）
        if boss_node and current_id != boss_node["id"]:
            # 检查Boss是否已经在子节点中显示过了
            boss_already_shown = any(c["id"] == boss_node["id"] for c in child_nodes)
            if not boss_already_shown:
                lines.append("    │")
                lines.append("    ⚪ ...")
                lines.append("    │")
                lines.append(f"  {fmt_node(boss_node)}")

        # 选择提示
        if len(child_nodes) >= 2:
            lines.append("")
            lines.append("  → 输入节点编号选择路径 (如 n1 或 1/2)")
        elif len(child_nodes) == 1:
            lines.append("")
            lines.append("  → 自动前进中...")

        return "\n".join(lines)

    # ==================== 战斗 ====================

    def _dungeon_combat(self, player_stats, monster_stats) -> dict:
        """副本内简化战斗 - 复用 execute_attack，摘要输出"""
        from .combat_manager import CombatManager

        total_damage_dealt = 0
        total_damage_taken = 0
        rounds = 0
        key_events = []

        for rnd in range(1, 101):
            rounds = rnd

            # 玩家回合
            result = CombatManager.execute_attack(player_stats, monster_stats)
            if result["dodged"]:
                key_events.append(f"第{rnd}回合: 你攻击被闪避")
            else:
                total_damage_dealt += result["damage"]
                if result["is_crit"]:
                    key_events.append(f"第{rnd}回合: 会心一击！伤害{result['damage']}")
                if result["lifesteal_heal"] > 0:
                    key_events.append(f"第{rnd}回合: 吸血回复{result['lifesteal_heal']}")
                if result["triggered_double"]:
                    key_events.append(f"第{rnd}回合: 触发连击")

            if monster_stats.hp <= 0:
                break

            # 怪物回合
            result2 = CombatManager.execute_attack(monster_stats, player_stats)
            if result2["dodged"]:
                key_events.append(f"第{rnd}回合: 你闪避了攻击")
            else:
                total_damage_taken += result2["damage"]
                if result2["is_crit"]:
                    key_events.append(f"第{rnd}回合: 被暴击！受伤{result2['damage']}")
                if result2["reflect_dmg"] > 0:
                    key_events.append(f"第{rnd}回合: 反伤{result2['reflect_dmg']}")

            if player_stats.hp <= 0:
                break

        victory = monster_stats.hp <= 0
        events_str = " | ".join(key_events[:4]) if key_events else "无特殊事件"

        summary = (
            f"{'🏆 胜利' if victory else '💀 败北'}！({rounds}回合)\n"
            f"  造成伤害: {total_damage_dealt:,} | 受到伤害: {total_damage_taken:,}\n"
            f"  关键事件: {events_str}"
        )

        return {
            "victory": victory,
            "rounds": rounds,
            "total_damage_dealt": total_damage_dealt,
            "total_damage_taken": total_damage_taken,
            "summary": summary,
        }

    # ==================== 透支机制 ====================

    def _apply_overdraft(self, run: DungeonRun, dungeon: dict) -> str:
        """透支扣血，返回提示文字"""
        od = dungeon.get("overdraft", {})
        base_pct = od.get("base_pct", 0.10)
        inc_pct = od.get("increment_pct", 0.05)
        max_pct = od.get("max_pct", 0.40)

        pct = min(base_pct + run.overdraft_count * inc_pct, max_pct)
        dmg = max(1, int(run.max_hp * pct))
        run.hp = max(0, run.hp - dmg)
        run.overdraft_count += 1

        warn_pct = self._get_global_config().get("overdraft_warning_pct", 0.5)
        warning = ""
        if run.hp <= run.max_hp * warn_pct and run.hp > 0:
            warning = " ⚠️ 血量危险！"

        return f"  ⚡ 灵力枯竭！透支扣血 {dmg} ({int(pct*100)}%){warning} [HP: {run.hp:,}/{run.max_hp:,}]"

    # ==================== 结算 ====================

    async def _settle_and_finish(
        self, run: DungeonRun, player: Player,
        victory: bool = False, is_retreat: bool = False,
        boss_reward: dict = None
    ) -> Tuple[bool, str]:
        """结算副本奖励并清理"""
        inv = run.get_inventory()
        lingshi = inv.get("lingshi", 0)
        exp_earned = inv.get("exp", 0)
        items = {k: v for k, v in inv.items() if k not in ("lingshi", "exp")}

        # 每日上限裁剪
        daily = await self.db.ext.get_dungeon_daily_reward(run.user_id)
        dungeon = self._get_dungeon_config(run.dungeon_key)
        cap_gold = dungeon.get("daily_reward_cap", 999999) if dungeon else 999999
        cap_exp = dungeon.get("daily_reward_cap_exp", 999999) if dungeon else 999999

        actual_gold = max(0, min(lingshi, cap_gold - daily["gold"]))
        actual_exp = max(0, min(exp_earned, cap_exp - daily["exp"]))

        # 战败丢失部分物品
        lost_items = {}
        if not victory and not is_retreat and items:
            lose_ratio = random.uniform(0.3, 0.6)
            for name, cnt in list(items.items()):
                lose_count = max(0, int(cnt * lose_ratio))
                if lose_count > 0:
                    lost_items[name] = lose_count
                    items[name] = cnt - lose_count
                    if items[name] <= 0:
                        del items[name]

        # 写入数据库
        try:
            await self.db.conn.execute("BEGIN IMMEDIATE")
            # 灵石 + 修为
            player.gold += actual_gold
            player.experience += actual_exp
            # 物品存入储物戒
            if items:
                storage_items = player.get_storage_ring_items()
                for name, cnt in items.items():
                    storage_items[name] = storage_items.get(name, 0) + cnt
                player.set_storage_ring_items(storage_items)
            await self.db.update_player(player, auto_commit=False)
            await self.db.ext.add_dungeon_daily_reward(run.user_id, actual_gold, actual_exp)
            await self.db.ext.delete_dungeon_run(run.user_id, auto_commit=False)
            await self.db.conn.commit()
        except Exception as e:
            await self.db.conn.rollback()
            logger.error(f"探险结算异常: {e}")
            return False, "结算异常，请稍后重试。"

        # 释放busy
        await self.db.ext.set_user_free(run.user_id)

        # 构建结算文本
        lines = ["═══ 探险结算 ═══"]
        if is_retreat:
            lines.append("📢 主动撤离，获得已有奖励:")
        elif victory:
            lines.append("🏆 探险通关！奖励:")
        else:
            lines.append("💀 探险失败，部分奖励:")

        if actual_gold > 0:
            cap_note = f" (已达上限，原{lingshi:,})" if actual_gold < lingshi else ""
            lines.append(f"  · 灵石 +{actual_gold:,}{cap_note}")
        if actual_exp > 0:
            cap_note = f" (已达上限，原{exp_earned:,})" if actual_exp < exp_earned else ""
            lines.append(f"  · 修为 +{actual_exp:,}{cap_note}")
        for name, cnt in items.items():
            lines.append(f"  · {name} x{cnt}")
        if boss_reward:
            lines.append(f"  · [BOSS] {boss_reward['name']} x{boss_reward.get('count', 1)}")
        if lost_items:
            lines.append("\n  💔 战败丢失:")
            for name, cnt in lost_items.items():
                lines.append(f"    · {name} x{cnt}")

        lines.append(f"\n总深度: {run.depth}")
        return True, "\n".join(lines)

    async def _force_settle(self, run: DungeonRun, player: Player, reason: str) -> Tuple[bool, str]:
        """强制结算（过期等）"""
        settle = await self._settle_and_finish(run, player, victory=False)
        return True, f"{reason}\n\n{settle[1]}"

    # ==================== 工具方法 ====================

    def _get_tier_mult(self, depth: int, dungeon: dict) -> float:
        """根据深度获取难度倍率"""
        tiers = dungeon.get("depth_tiers", [])
        max_d = dungeon.get("max_depth", 30)
        pct = depth / max_d if max_d > 0 else 0
        for tier in tiers:
            if pct <= tier.get("max_depth_pct", 1.0):
                return tier.get("mult", 1.0)
        return 1.0

    def _get_tier_label(self, depth: int, dungeon: dict) -> str:
        """获取当前深度的难度标签"""
        tiers = dungeon.get("depth_tiers", [])
        max_d = dungeon.get("max_depth", 30)
        pct = depth / max_d if max_d > 0 else 0
        for tier in tiers:
            if pct <= tier.get("max_depth_pct", 1.0):
                return tier.get("label", "")
        return ""

    def _roll_boss_rewards(self, pool: list, count: int) -> list:
        """从奖励池中按权重抽取N个"""
        if not pool:
            return [{"name": "灵石", "count": 1000}]
        weights = [r.get("weight", 1) for r in pool]
        selected = []
        available = list(range(len(pool)))
        for _ in range(min(count, len(pool))):
            if not available:
                break
            w = [weights[i] for i in available]
            idx = random.choices(available, weights=w, k=1)[0]
            selected.append(pool[idx])
            available.remove(idx)
        return selected if selected else [pool[0]]

    @staticmethod
    def _progress_bar(current: int, maximum: int, length: int = 10) -> str:
        """生成进度条"""
        if maximum <= 0:
            return "░" * length
        filled = min(round(current / maximum * length), length)
        empty = length - filled
        return "█" * filled + "░" * empty
