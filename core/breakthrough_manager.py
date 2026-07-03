# core/breakthrough_manager.py

import random
from typing import Optional, Tuple
from astrbot.api import logger

from ..models import Player
from ..data import DataBase
from ..config_manager import ConfigManager


def is_major_realm_transition(current_level_index: int, target_level_index: int) -> bool:
    """判断是否为主要境界突破（圆满 -> 下一境界初期）

    主要境界突破 = 目标境界是新境界的初期阶段，
    即 current_level_index 的下一境界是新境界的开始。

    58级体系中，每3级为一个大境界（初期/中期/圆满），
    所以 level_index % 3 == 2 表示圆满阶段。
    从圆满突破到下一个大境界的初期就是主要境界突破。
    """
    next_index = current_level_index + 1
    # 当前境界是圆满（index % 3 == 2）且目标就是下一境界（初期）
    return current_level_index % 3 == 2 and target_level_index == next_index


class BreakthroughManager:
    """突破管理器 - 处理境界突破相关逻辑"""

    def __init__(self, db: DataBase, config_manager: ConfigManager, config: dict):
        self.db = db
        self.config_manager = config_manager
        self.config = config

    def check_breakthrough_requirements(self, player: Player, level_data: list = None) -> Tuple[bool, str]:
        """检查玩家是否满足突破条件

        Args:
            player: 玩家对象
            level_data: 境界数据列表（可选，避免重复查询）

        Returns:
            (是否满足, 错误消息)
        """
        if level_data is None:
            level_data = self.config_manager.get_level_data()

        # 检查是否已经是最高境界
        if player.level_index >= len(level_data) - 1:
            return False, "你已经达到了最高境界，无法继续突破！"

        # 获取下一境界所需修为
        next_level_index = player.level_index + 1
        next_level_data = level_data[next_level_index]
        required_exp = next_level_data.get("exp_needed", 0)

        # 检查修为是否满足
        if player.experience < required_exp:
            current_level = level_data[player.level_index].get("name", "")
            next_level = next_level_data.get("name", "")
            return False, (
                f"修为不足！\n"
                f"当前境界：{current_level}\n"
                f"当前修为：{player.experience}\n"
                f"突破至【{next_level}】需要修为：{required_exp}"
            )

        return True, ""

    def calculate_breakthrough_success_rate(
        self,
        player: Player,
        pill_name: Optional[str] = None,
        temp_bonus: float = 0.0,
        level_data: list = None
    ) -> Tuple[float, str]:
        """计算突破成功率

        Args:
            player: 玩家对象
            pill_name: 使用的破境丹名称（可选）
            level_data: 境界数据列表（可选，避免重复查询）

        Returns:
            (成功率, 说明信息)
        """
        if level_data is None:
            level_data = self.config_manager.get_level_data()

        # 获取基础成功率
        next_level_index = player.level_index + 1
        next_level_data = level_data[next_level_index]
        base_success_rate = next_level_data.get("success_rate", 0.5)

        info_lines = [
            f"基础成功率：{base_success_rate:.1%}"
        ]

        final_rate = base_success_rate + temp_bonus
        max_rate = 1.0  # 默认最大100%

        if temp_bonus:
            info_lines.append(f"临时丹药加成：{temp_bonus:+.1%}")

        # 失败累积加成：每次失败+1%，无上限
        failure_bonus = 0.0
        if player.level_up_rate > 0:
            failure_bonus = player.level_up_rate / 100.0
            info_lines.append(f"失败累积加成：+{failure_bonus:.1%}（{player.level_up_rate}次）")
            final_rate += failure_bonus

        # 新增：主修心法加成
        technique_bonus = 0.0
        technique_number = 0.0
        if player.main_technique:
            items_data = self.config_manager.items_data
            technique_data = items_data.get(player.main_technique)
            if technique_data:
                technique_bonus = technique_data.get("breakthrough_bonus", 0.0)
                if technique_bonus > 0:
                    info_lines.append(f"主修心法加成：+{technique_bonus:.1%}")
                    final_rate += technique_bonus
                # 心法突破数值加成（nonebot number 字段）
                technique_number = technique_data.get("breakthrough_number", 0.0)
                if technique_number > 0:
                    info_lines.append(f"心法突破数值加成：+{technique_number:.0f}%")
                    final_rate += technique_number / 100.0

        # 如果使用了破境丹，记录日志（加成已通过 temp_bonus 从 active_pill_effects 计入，不重复添加）
        if pill_name:
            pill_data = self.config_manager.utility_pills_data.get(pill_name)
            if pill_data and pill_data.get("subtype") == "breakthrough_boost":
                effect = pill_data.get("effect", {})
                breakthrough_bonus = effect.get("breakthrough_bonus", 0)
                if breakthrough_bonus > 0:
                    info_lines.append(f"破境丹加成：+{breakthrough_bonus:.1%}（已含在临时丹药加成中）")
            else:
                logger.warning(f"无效的破境丹：{pill_name}")

        final_rate = max(0.0, min(final_rate, max_rate))
        info_lines.append(f"最终成功率：{final_rate:.1%}")
        info = "\n".join(info_lines)

        return final_rate, info

    async def execute_breakthrough(
        self,
        player: Player,
        pill_name: Optional[str] = None,
        temp_bonus: float = 0.0,
        death_rate_multiplier: float = 1.0
    ) -> Tuple[bool, str, bool]:
        """执行突破

        Args:
            player: 玩家对象
            pill_name: 使用的破境丹名称（可选）

        Returns:
            (是否成功, 消息, 是否死亡)
        """
        # 获取境界数据（单次查询，传递给子方法避免重复查询）
        level_data = self.config_manager.get_level_data()

        # 检查突破条件
        can_breakthrough, error_msg = self.check_breakthrough_requirements(player, level_data)
        if not can_breakthrough:
            return False, error_msg, False

        # 计算成功率
        success_rate, rate_info = self.calculate_breakthrough_success_rate(player, pill_name, temp_bonus, level_data)

        # 判定突破结果
        random_value = random.random()
        breakthrough_success = random_value < success_rate

        current_level_name = level_data[player.level_index].get("name", "未知境界")
        next_level_index = player.level_index + 1
        next_level_data = level_data[next_level_index]
        next_level_name = next_level_data.get("name", "未知境界")

        if breakthrough_success:
            # 突破成功 - nonebot 体系：仅提升境界，属性由 exp 推导
            player.level_index = next_level_index

            # 突破成功，重置失败累积加成
            old_failure_count = player.level_up_rate
            player.level_up_rate = 0

            # 保存到数据库
            await self.db.update_player(player)

            # 检查并处理突破贷款自动还款
            loan_msg = await self._handle_breakthrough_loan_repay(player)

            success_msg = (
                f"✨ 突破成功！✨\n"
                f"━━━━━━━━━━━━━━━\n"
                f"{rate_info}\n"
                f"━━━━━━━━━━━━━━━\n"
                f"恭喜你从【{current_level_name}】突破至【{next_level_name}】！\n"
                f"境界提升，实力大增！\n"
                f"\n当前境界：{next_level_name}"
            )

            # 如果有失败累积加成，追加重置提示
            if old_failure_count > 0:
                old_bonus = old_failure_count / 100.0
                filled = min(10, old_failure_count // 10)
                bar_before = "█" * filled + "░" * (10 - filled)
                bar_after = "░" * 10
                success_msg += (
                    f"\n\n🔄 失败累积加成已重置（原 +{old_bonus:.1%}）\n"
                    f"   [{bar_before}] → [{bar_after}]"
                )

            logger.info(
                f"玩家 {player.user_id} 突破成功：{current_level_name} -> {next_level_name}"
            )
            
            # 如果有贷款相关消息，追加到成功消息后
            if loan_msg:
                success_msg += f"\n\n{loan_msg}"

            return True, success_msg, False

        else:
            # 突破失败 - 判断是否死亡
            import json as _json
            death_probability_range = self.config.get("VALUES", {}).get(
                "BREAKTHROUGH_DEATH_PROBABILITY",
                [0.01, 0.1]  # 默认1%-10%死亡概率
            )
            # AstrBot可能将list存储为JSON字符串
            if isinstance(death_probability_range, str):
                try:
                    death_probability_range = _json.loads(death_probability_range)
                except (ValueError, TypeError):
                    death_probability_range = [0.01, 0.1]

            # 随机一个死亡概率
            death_rate = random.uniform(float(death_probability_range[0]), float(death_probability_range[1]))
            death_rate = max(0.0, min(1.0, death_rate * death_rate_multiplier))
            died = random.random() < death_rate

            if died:
                # 检查是否有回生丹效果
                from .pill_manager import PillManager
                pill_manager = PillManager(self.db, self.config_manager)
                resurrected, res_pill_name = await pill_manager.handle_resurrection(player)

                if resurrected:
                    # 回生丹触发，玩家复活
                    if res_pill_name == "涅槃重生丹":
                        penalty_line = "✨ 涅槃重生丹效果触发，属性完好无损！"
                    else:
                        penalty_line = "⚠️ 但所有属性降低了15%"
                    resurrection_msg = (
                        f"💀 突破失败，走火入魔！💀\n"
                        f"━━━━━━━━━━━━━━━\n"
                        f"{rate_info}\n"
                        f"━━━━━━━━━━━━━━━\n"
                        f"你在突破【{next_level_name}】时走火入魔...\n"
                        f"\n"
                        f"⚡ {res_pill_name}效果触发！⚡\n"
                        f"━━━━━━━━━━━━━━━\n"
                        f"🌟 你涅槃重生了！\n"
                        f"{penalty_line}\n"
                        f"💊 {res_pill_name}效果已消耗\n"
                        f"━━━━━━━━━━━━━━━\n"
                        f"请继续修炼，重回巅峰！"
                    )

                    logger.info(
                        f"玩家 {player.user_id} 突破失败触发回生丹，成功复活"
                    )

                    # 返回False（突破失败），消息，False（未真正死亡）
                    return False, resurrection_msg, False

                # 玩家死亡 - 级联删除所有关联数据
                await self.db.delete_player_cascade(player.user_id)

                death_msg = (
                    f"💀 突破失败，走火入魔！💀\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"{rate_info}\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"你在突破【{next_level_name}】时走火入魔，身死道消...\n"
                    f"所有修为和装备化为虚无\n"
                    f"若想重新修仙，请使用'我要修仙'命令重新开始"
                )

                logger.info(
                    f"玩家 {player.user_id} 突破失败并死亡：{current_level_name} -> {next_level_name}，死亡概率 {death_rate:.2%}"
                )

                return False, death_msg, True

            else:
                # 突破失败但未死亡 - 检查是否有死亡保护效果（渡厄金丹）
                has_death_protection = False
                active_effects = player.get_active_pill_effects()
                for eff in active_effects:
                    if eff.get("subtype") == "death_protection":
                        has_death_protection = True
                        break

                if has_death_protection:
                    # 渡厄金丹效果：不损失修为，然后消耗该效果（仅保护一次）
                    exp_penalty = 0
                    remaining_effects = [
                        e for e in active_effects
                        if e.get("subtype") != "death_protection"
                    ]
                    player.set_active_pill_effects(remaining_effects)
                else:
                    # 合体境(25)及以上：1%~5%；以下：0.1%~1%
                    if next_level_index >= 25:
                        penalty_rate = random.uniform(0.01, 0.05)
                    else:
                        penalty_rate = random.uniform(0.001, 0.01)
                    exp_penalty = max(1, int(player.experience * penalty_rate))
                    player.experience = max(0, int(player.experience) - exp_penalty)

                # 失败累积加成 +1%（无上限）
                player.level_up_rate += 1
                current_failure_bonus = player.level_up_rate / 100.0

                await self.db.update_player(player)

                # 随机失败描述
                fail_scenes = [
                    f"你感受到天地间一股无形的阻力，境界壁垒纹丝不动。",
                    f"体内灵气在经脉中逆行，你急忙收功，吐出一口浊气。",
                    f"差一步便能触及更高境界，却在最后一刻功亏一篑。",
                    f"天地法则如同铜墙铁壁，你的领悟还差了一丝火候。",
                    f"突破之际心魔侵扰，你不得不强行中断，气息紊乱。",
                    f"灵力汇聚于丹田即将突破，却被一股莫名的力量冲散。",
                ]
                scene = random.choice(fail_scenes)

                # 失败累积提示（每10次为一格，最多10格）
                filled = min(10, player.level_up_rate // 10)
                bar = "█" * filled + "░" * (10 - filled)
                bonus_line = f"🔥 失败累积：+{current_failure_bonus:.1%} [{bar}]（已失败{player.level_up_rate}次）"

                if has_death_protection:
                    exp_line = "⚡ 渡厄金丹效果触发，修为完好无损！"
                else:
                    exp_line = f"修为受损：-{exp_penalty}（{penalty_rate:.2%}）\n当前修为：{player.experience:,}"

                fail_msg = (
                    f"❌ 突破失败 ❌\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"{rate_info}\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"突破【{next_level_name}】失败\n"
                    f"\n"
                    f"{scene}\n"
                    f"\n"
                    f"{exp_line}\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"{bonus_line}\n"
                    f"下次突破成功率将提升！\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"道途坎坷，百折不挠方能证道。\n"
                    f"请继续修炼，来日再战！"
                )

                logger.info(
                    f"玩家 {player.user_id} 突破失败：{current_level_name} -> {next_level_name}，"
                    f"损失修为 {exp_penalty}，失败累积加成 +{player.level_up_rate}%"
                )

                return False, fail_msg, False
    
    async def _handle_breakthrough_loan_repay(self, player: Player) -> str:
        """处理突破贷款自动还款
        
        Args:
            player: 玩家对象
            
        Returns:
            还款消息（如果有贷款的话）
        """
        try:
            # 检查是否有突破贷款
            loan = await self.db.ext.get_active_loan(player.user_id)
            if not loan or loan["loan_type"] != "breakthrough":
                return ""
            
            # 计算应还金额
            import time
            now = int(time.time())
            days_borrowed = max(1, (now - loan["borrowed_at"]) // 86400)
            interest = int(loan["principal"] * loan["interest_rate"] * days_borrowed)
            total_due = loan["principal"] + interest
            
            # 检查玩家是否有足够灵石
            if player.gold >= total_due:
                # 自动扣款（事务保护）
                await self.db.conn.execute("BEGIN IMMEDIATE")
                try:
                    player.gold -= total_due
                    await self.db.update_player(player, auto_commit=False)

                    # 关闭贷款
                    await self.db.ext.close_loan(loan["id"], auto_commit=False)

                    # 记录流水
                    bank_data = await self.db.ext.get_bank_account(player.user_id)
                    balance = bank_data["balance"] if bank_data else 0
                    await self.db.ext.add_bank_transaction(
                        player.user_id, "auto_repay", -total_due, balance,
                        f"突破成功自动还款：本金{loan['principal']:,}+利息{interest:,}", now,
                        auto_commit=False
                    )

                    await self.db.conn.commit()
                except Exception:
                    await self.db.conn.rollback()
                    raise
                
                return (
                    f"💰 突破贷款自动还款成功！\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"已还本金：{loan['principal']:,} 灵石\n"
                    f"已还利息：{interest:,} 灵石\n"
                    f"当前持有：{player.gold:,} 灵石"
                )
            else:
                # 灵石不足，提醒玩家
                return (
                    f"⚠️ 你有未还清的突破贷款！\n"
                    f"应还金额：{total_due:,} 灵石\n"
                    f"当前持有：{player.gold:,} 灵石\n"
                    f"请尽快使用 /还款 命令还款"
                )
        except Exception as e:
            logger.warning(f"处理突破贷款自动还款异常: {e}")
            return ""
