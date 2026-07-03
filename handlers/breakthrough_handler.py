# handlers/breakthrough_handler.py

from astrbot.api.event import AstrMessageEvent
from ..data import DataBase
from ..core import BreakthroughManager, PillManager
from ..config_manager import ConfigManager
from ..models import Player
from .utils import player_required

CMD_BREAKTHROUGH = "突破"
CMD_BREAKTHROUGH_INFO = "突破信息"

__all__ = ["BreakthroughHandler"]


class BreakthroughHandler:
    """突破系统处理器"""

    def __init__(self, db: DataBase, config_manager: ConfigManager, config: dict):
        self.db = db
        self.config_manager = config_manager
        self.config = config
        self.breakthrough_manager = BreakthroughManager(db, config_manager, config)
        self.pill_manager = PillManager(db, config_manager)

    @player_required
    async def handle_breakthrough_info(self, player: Player, event: AstrMessageEvent):
        """查看突破信息"""
        display_name = event.get_sender_name()

        # 根据修炼类型获取对应的境界数据
        level_data = self.config_manager.get_level_data(player.cultivation_type)

        # 检查是否已经是最高境界
        if player.level_index >= len(level_data) - 1:
            yield event.plain_result("你已经达到了最高境界，无法继续突破！")
            return

        await self.pill_manager.update_temporary_effects(player)
        target_level_index = player.level_index + 1
        modifiers = self.pill_manager.get_breakthrough_modifiers(player, target_level_index)

        # 获取当前和下一境界信息
        current_level_data = level_data[player.level_index]
        next_level_data = level_data[player.level_index + 1]

        current_level_name = current_level_data.get("name", "未知境界")
        next_level_name = next_level_data.get("name", "未知境界")
        required_exp = next_level_data.get("exp_needed", 0)
        base_success_rate = next_level_data.get("success_rate", 0.5)
        temp_bonus = modifiers["temp_bonus"]

        # 检查修为是否满足
        exp_satisfied = player.experience >= required_exp
        exp_status = "✅ 满足" if exp_satisfied else "❌ 不足"

        # 查找适用的破境丹（utility_pills_data 中的 breakthrough_boost，含失败累积加成）
        failure_bonus = player.level_up_rate / 100.0 if player.level_up_rate > 0 else 0.0

        # 计算心法加成（与 manager 的 calculate_breakthrough_success_rate 保持一致）
        technique_bonus = 0.0
        technique_number = 0.0
        if player.main_technique:
            items_data = self.config_manager.items_data
            technique_data = items_data.get(player.main_technique)
            if technique_data:
                technique_bonus = technique_data.get("breakthrough_bonus", 0.0)
                technique_number = technique_data.get("breakthrough_number", 0.0)

        available_pills = []
        for pill_name, pill_data in self.config_manager.utility_pills_data.items():
            subtype = pill_data.get("subtype", "")
            if subtype != "breakthrough_boost":
                continue
            # 境界特定丹药需匹配 target_level_index；通用丹药无此字段，始终可用
            target_level = pill_data.get("target_level_index")
            if target_level is not None and target_level != player.level_index + 1:
                continue
            effect = pill_data.get("effect", {})
            breakthrough_bonus = effect.get("breakthrough_bonus", 0)
            final_rate = min(base_success_rate + temp_bonus + failure_bonus + technique_bonus + technique_number / 100.0 + breakthrough_bonus, 1.0)
            available_pills.append({
                "name": pill_name,
                "rank": pill_data.get("rank", ""),
                "final_rate": final_rate,
                "max_rate": 1.0,
            })

        # 构建信息显示
        info_lines = [
            f"=== {display_name} 的突破信息 ===\n",
            f"当前境界：{current_level_name}\n",
            f"下一境界：{next_level_name}\n",
            f"━━━━━━━━━━━━━━━\n",
            f"【突破条件】\n",
            f"所需修为：{required_exp}\n",
            f"当前修为：{player.experience}\n",
            f"修为状态：{exp_status}\n",
            f"━━━━━━━━━━━━━━━\n",
            f"【突破成功率】\n",
            f"基础成功率：{base_success_rate:.1%}\n",
        ]

        # 失败累积加成（每次+1%，无上限）
        if player.level_up_rate > 0:
            filled = min(10, player.level_up_rate // 10)
            bar = "█" * filled + "░" * (10 - filled)
            info_lines.append(f"失败累积加成：+{failure_bonus:.1%} [{bar}]（已失败{player.level_up_rate}次）\n")

        if technique_bonus > 0:
            info_lines.append(f"主修心法加成：+{technique_bonus:.1%}\n")
        if technique_number > 0:
            info_lines.append(f"心法突破数值加成：+{technique_number:.0f}%\n")

        if temp_bonus:
            info_lines.append(f"临时丹药加成：{temp_bonus:+.1%}\n")
        death_reduce = 1 - modifiers["permanent_death_multiplier"]
        if death_reduce > 0:
            info_lines.append(f"突破死亡概率降低：{death_reduce:.1%}\n")

        if available_pills:
            info_lines.append(f"\n【可用破境丹】\n")
            for pill in available_pills:
                info_lines.append(
                    f"• {pill['name']}（{pill['rank']}）\n"
                    f"  使用后成功率：{pill['final_rate']:.1%}（最高{pill['max_rate']:.1%}）\n"
                )
        else:
            info_lines.append(f"\n暂无适用的破境丹\n")

        # 突破说明
        success_flavor = "肉身更强" if player.cultivation_type == "体修" else "实力大增"
        info_lines.extend([
            f"━━━━━━━━━━━━━━━\n",
            f"【突破说明】\n",
            f"• 使用命令：{CMD_BREAKTHROUGH} 或 {CMD_BREAKTHROUGH} [破境丹名称]\n",
            f"• 突破成功：境界提升，{success_flavor}\n",
            f"• 突破失败：损失0.1%~1%修为，有概率死亡\n",
            f"• 失败累积：每次失败+1%成功率（无上限），突破成功后重置\n",
            f"• 破境丹：使用后持续生效，突破失败不消失，突破成功后才消耗\n",
            f"• 死亡后：所有数据清除，需重新入仙途\n",
            f"=" * 28
        ])

        yield event.plain_result("".join(info_lines))

    @player_required
    async def handle_breakthrough(self, player: Player, event: AstrMessageEvent, pill_name: str = None):
        """执行突破"""
        display_name = event.get_sender_name()

        await self.pill_manager.update_temporary_effects(player)
        target_level_index = player.level_index + 1
        modifiers = self.pill_manager.get_breakthrough_modifiers(player, target_level_index)

        # 根据修炼类型获取对应的境界数据
        level_data = self.config_manager.get_level_data(player.cultivation_type)

        # 如果指定了破境丹，验证其有效性
        if pill_name and pill_name.strip():
            pill_name = pill_name.strip()
            pill_data = self.config_manager.utility_pills_data.get(pill_name)

            if not pill_data:
                yield event.plain_result(f"未找到破境丹：{pill_name}")
                return

            if pill_data.get("subtype") != "breakthrough_boost":
                yield event.plain_result(f"{pill_name} 不是破境丹")
                return

            # 检查是否适用于当前突破
            target_level = pill_data.get("target_level_index")
            if target_level is not None and target_level != player.level_index + 1:
                current_level = level_data[player.level_index].get("name", "未知境界")
                # 获取丹药目标境界名称
                target_level_name = f"境界{target_level}"
                if 0 <= target_level < len(level_data):
                    target_level_name = level_data[target_level].get("name", "未知境界")
                yield event.plain_result(
                    f"{pill_name} 不适用于当前突破\n"
                    f"当前境界：{current_level}\n"
                    f"此丹药用于突破到：【{target_level_name}】"
                )
                return

            # 检查主要境界突破限制（境界特定丹药只在主要境界突破时可用）
            from ..core.breakthrough_manager import is_major_realm_transition
            target_level_val = pill_data.get("target_level_index")
            if target_level_val is not None and not is_major_realm_transition(player.level_index, target_level_val):
                yield event.plain_result(
                    f"{pill_name} 仅在主要境界突破时可用\n"
                    f"（圆满 -> 下一境界初期的突破）"
                )
                return

            yield event.plain_result(f"使用【{pill_name}】进行突破...")
        else:
            pill_name = None
            yield event.plain_result("开始尝试突破...")

        # 执行突破
        success, message, died = await self.breakthrough_manager.execute_breakthrough(
            player,
            pill_name,
            modifiers["temp_bonus"],
            modifiers["permanent_death_multiplier"]
        )

        # 仅在突破成功时消耗突破加成效果，保留死亡保护效果供后续突破使用
        if success and modifiers["has_temp_effects"]:
            await self.pill_manager.consume_breakthrough_boost_only(player)

        yield event.plain_result(message)
