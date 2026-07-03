# handlers/player_handler.py
import math
import time
import random
from datetime import datetime
from astrbot.api.event import AstrMessageEvent
from astrbot.api import AstrBotConfig
from ..data import DataBase
from ..core import CultivationManager, PillManager
from ..managers.achievement_manager import AchievementManager
from ..models import Player
from ..models_extended import UserStatus
from ..config_manager import ConfigManager
from .utils import player_required

CMD_START_XIUXIAN = "我要修仙"
CMD_PLAYER_INFO = "我的信息"
CMD_START_CULTIVATION = "闭关"
CMD_END_CULTIVATION = "出关"
CMD_CHECK_IN = "签到"
CMD_REROLL_ROOT = "重铸灵根"
REBIRTH_COOLDOWN = 7 * 24 * 3600
REROLL_ROOT_COST = 250000

__all__ = ["PlayerHandler"]

class PlayerHandler:
    """玩家基础信息处理器"""

    def __init__(self, db: DataBase, config: AstrBotConfig, config_manager: ConfigManager, achievement_mgr: AchievementManager = None, activity_tracker=None):
        self.db = db
        self.config = config
        self.config_manager = config_manager
        self.cultivation_manager = CultivationManager(config, config_manager)
        self.pill_manager = PillManager(self.db, self.config_manager)
        self.achievement_mgr = achievement_mgr
        self.activity_tracker = activity_tracker

    async def handle_start_xiuxian(self, event: AstrMessageEvent, cultivation_type: str = ""):
        """处理创建角色

        Args:
            cultivation_type: 修炼类型，"灵修"或"体修"，为空则显示选择提示
        """
        user_id = event.get_sender_id()

        # 检查是否已创建角色
        if await self.db.get_player_by_id(user_id):
            yield event.plain_result("道友，你已踏入仙途，无需重复此举。")
            return

        # 如果没有提供职业选择，显示选择提示
        if not cultivation_type or cultivation_type.strip() == "":
            help_msg = (
                "🌟 欢迎踏入修仙之路！\n"
                "━━━━━━━━━━━━━━━\n"
                "初入江湖，你成为了【江湖好手】\n"
                "初始属性：气血500、真元1000、攻击100\n\n"
                "⚠️ 修仙风险警告 ⚠️\n"
                "• 突破失败有概率走火入魔身死道消\n"
                "• 生命值归零也会导致死亡\n"
                "• 死亡后所有数据清除，需重新入仙途\n"
                "━━━━━━━━━━━━━━━\n"
                f"💡 使用 /我要修仙 确认开始"
            )
            yield event.plain_result(help_msg)
            return

        # 验证修炼类型（保留参数兼容，v36已统一为单一体系）
        cultivation_type = cultivation_type.strip()
        if cultivation_type not in ["灵修", "体修"]:
            yield event.plain_result(f"修炼类型错误！请选择「灵修」或「体修」。")
            return

        # 生成新玩家
        new_player = self.cultivation_manager.generate_new_player_stats(user_id, cultivation_type)
        await self.db.create_player(new_player)

        # 获取灵根描述
        root_name = new_player.spiritual_root.replace("灵根", "")
        root_description = self.cultivation_manager._get_root_description(root_name)

        reply_msg = (
            f"🎉 恭喜道友 {event.get_sender_name()} 踏上仙途！\n"
            f"━━━━━━━━━━━━━━━\n"
            f"修炼方式：【{new_player.cultivation_type}】\n"
            f"灵根：【{new_player.spiritual_root}】\n"
            f"评价：{root_description}\n"
            f"启动资金：{new_player.gold} 灵石\n"
            f"━━━━━━━━━━━━━━━\n"
            f"⚠️ 修仙有风险，突破需谨慎！\n"
            f"突破失败或生命值归零会导致\n"
            f"身死道消，所有数据清除！\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💡 发送「{CMD_PLAYER_INFO}」查看状态"
        )
        yield event.plain_result(reply_msg)

    @player_required
    async def handle_player_info(self, player: Player, event: AstrMessageEvent):
        """处理查看玩家信息 - 展示新属性"""
        display_name = event.get_sender_name()
        required_exp = player.get_required_exp(self.config_manager)

        # 更新丹药效果并计算最终属性倍率
        await self.pill_manager.update_temporary_effects(player)
        pill_multipliers = self.pill_manager.calculate_pill_attribute_effects(player)

        # 获取装备加成后的属性
        from ..core import EquipmentManager
        equipment_manager = EquipmentManager(self.db, self.config_manager)
        equipped_items = equipment_manager.get_equipped_items(
            player,
            self.config_manager.items_data,
            self.config_manager.weapons_data
        )

        # 图片生成暂时禁用（缺少资源文件会导致效果很差）
        # 直接使用优化后的文本格式显示

        # 文本模式 (完整信息显示)
        
        # 获取战力（nonebot 公式：exp * root_speed * realm_spend）
        from ..managers.combat_manager import CombatManager
        impart_info = await self.db.ext.get_impart_info(player.user_id)
        combat_stats = CombatManager.build_player_combat_stats(player, impart_info, self.config_manager)

        # 读取灵根倍率
        root_speed = self.cultivation_manager.get_spiritual_root_speed(player) if hasattr(self, 'cultivation_manager') else 1.0
        # 读取境界 spend
        level_data = self.config_manager.get_level_data()
        realm_spend = level_data[player.level_index].get("spend", 1.0) if player.level_index < len(level_data) else 1.0

        combat_power = CombatManager.calc_combat_power(
            combat_stats, combat_stats.max_hp, combat_stats.max_mp,
            experience=player.experience, root_speed=root_speed, realm_spend=realm_spend
        )
        
        # 获取宗门信息
        sect_name = "无宗门"
        position_name = "散修"
        if player.sect_id and player.sect_id != 0:
            sect = await self.db.ext.get_sect_by_id(player.sect_id)
            if sect:
                sect_name = sect.sect_name
                if sect.sect_owner == player.user_id:
                    position_name = "宗主"
                elif player.sect_position == 1:
                    position_name = "长老"
                elif player.sect_position == 2:
                    position_name = "亲传弟子"
                elif player.sect_position == 3:
                    position_name = "内门弟子"
                else:
                    position_name = "外门弟子"
        
        # 获取装备信息
        weapon_name = player.weapon if player.weapon else "无"
        armor_name = player.armor if player.armor else "无"
        technique_name = player.main_technique if player.main_technique else "无"
        sub_technique_name = player.sub_technique if player.sub_technique else "无"
        
        # 获取突破状态
        breakthrough_rate = f"+{player.level_up_rate}%" if player.level_up_rate > 0 else "0%"
        
        # 构建信息显示
        dao_hao = player.user_name if player.user_name else display_name
        
        # 双层减伤率计算
        base_def_reduction = combat_stats.base_def / (combat_stats.base_def + 500) * 100 if combat_stats.base_def > 0 else 0
        equip_def_val = math.log(combat_stats.equip_def + 1) * 20 if combat_stats.equip_def > 0 else 0
        equip_def_reduction = equip_def_val / (equip_def_val + 200) * 100 if equip_def_val > 0 else 0
        total_reduction = (1 - (1 - base_def_reduction / 100) * (1 - equip_def_reduction / 100)) * 100
        mp_pct = f"{player.mp * 100 // combat_stats.max_mp}%" if combat_stats.max_mp > 0 else "0%"

        reply_msg = (
            f"📋 道友 {dao_hao} 的信息\n"
            f"━━━━━━━━━━━━━━━\n"
            f"\n"
            f"【基本信息】\n"
            f"  道号：{dao_hao}\n"
            f"  境界：{player.get_level(self.config_manager)}\n"
            f"  修为：{int(player.experience):,}/{int(required_exp):,}\n"
            f"  灵石：{player.gold:,}\n"
            f"  战力：{combat_power:,}\n"
            f"  灵根：{player.spiritual_root}\n"
            f"  突破加成：{breakthrough_rate}\n"
            f"\n"
            f"【战斗属性】\n"
            f"  ❤️ 生命：{combat_stats.max_hp:,}\n"
            f"  💧 真元：{combat_stats.max_mp:,}（{mp_pct}）\n"
            f"  ⚔️ 攻击力：{combat_stats.atk:,}\n"
            f"  🎯 会心率：{combat_stats.crit_rate}%\n"
            f"  💥 会心伤害：{combat_stats.crit_damage:.2f}x\n"
            f"  🗡️ 破甲：{combat_stats.armor_pen}%\n"
            f"  🩸 吸血：{combat_stats.lifesteal}%\n"
            f"  ⚡ 连击：{combat_stats.double_hit}%\n"
            f"  💨 闪避率：{combat_stats.dodge_rate}%\n"
            f"  🛡️ 减伤率：{total_reduction:.1f}%\n"
            f"  🔄 会心抵抗：{combat_stats.crit_resist}%\n"
            f"  🔁 反伤：{combat_stats.reflect_pct}%\n"
            f"  🧱 格挡：{combat_stats.block_value}\n"
            f"  💚 生命回复：{combat_stats.hp_regen_pct}%/回合\n"
        )

        # 计算修炼效率
        root_speed = self.cultivation_manager.get_spiritual_root_speed(player)
        technique_bonus = 0.0
        for item in equipped_items:
            if item.item_type == "main_technique":
                technique_bonus = item.exp_multiplier
                break
        cultivation_pill_bonus = pill_multipliers.get("cultivation_speed", 1.0)
        # 分离永久和临时丹药修炼加成
        permanent_gains = player.get_permanent_pill_gains()
        perm_cultivation_mult = permanent_gains.get("_global", {}).get("cultivation_multiplier", 0)
        temp_cultivation_mult = cultivation_pill_bonus - 1.0 - perm_cultivation_mult
        # 洞天加成
        land_bonus = 0.0
        async with self.db.conn.execute(
            "SELECT SUM(exp_bonus) FROM blessed_lands WHERE user_id = ?",
            (player.user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                land_bonus = row[0]
        total_efficiency = root_speed * (1.0 + technique_bonus) * cultivation_pill_bonus * (1.0 + land_bonus)

        reply_msg += (
            f"\n"
            f"【修炼效率】\n"
            f"  修炼方式：{player.cultivation_type}\n"
            f"  状态：{player.state}\n"
            f"  灵根倍率：x{root_speed:.1f}\n"
        )
        if technique_bonus > 0:
            reply_msg += f"  心法加成：+{technique_bonus:.0%}\n"
        if temp_cultivation_mult > 0:
            reply_msg += f"  临时丹药：+{temp_cultivation_mult:.0%}\n"
        if perm_cultivation_mult != 0:
            reply_msg += f"  永久丹药：{perm_cultivation_mult:+.0%}\n"
        if land_bonus > 0:
            reply_msg += f"  洞天加成：+{land_bonus:.0%}\n"
        reply_msg += f"  总效率：x{total_efficiency:.2f}\n"
        if player.atkpractice > 0:
            practice_bonus_pct = player.atkpractice * 4
            reply_msg += f"  攻击修炼：Lv.{player.atkpractice}（攻击力+{practice_bonus_pct}%）\n"

        reply_msg += (
            f"\n"
            f"【装备信息】\n"
            f"  主修功法：{technique_name}\n"
            f"  辅修功法：{sub_technique_name}\n"
            f"  武器：{weapon_name}\n"
            f"  防具：{armor_name}\n"
        )

        # 成就显示
        if self.achievement_mgr:
            ach_bonus = self.achievement_mgr.get_achievement_bonus(player)
            ach_data = player.get_achievement_data()
            equipped_ach = ach_data.get("equipped", "")
            if equipped_ach and ach_bonus:
                bonus_text = self.achievement_mgr._format_bonus_short(ach_bonus)
                reply_msg += f"  🏆 成就：{equipped_ach}（{bonus_text}）\n"

        reply_msg += (
            f"\n"
            f"【宗门信息】\n"
            f"  所在宗门：{sect_name}\n"
            f"  宗门职位：{position_name}\n"
        )
        
        # 获取贷款信息
        loan = await self.db.ext.get_active_loan(player.user_id)
        if loan:
            now = int(time.time())
            remaining_seconds = loan["due_at"] - now
            remaining_days = remaining_seconds // 86400
            remaining_hours = (remaining_seconds % 86400) // 3600
            
            days_borrowed = max(1, (now - loan["borrowed_at"]) // 86400)
            interest = int(loan["principal"] * loan["interest_rate"] * days_borrowed)
            total_due = loan["principal"] + interest
            
            loan_type_name = "突破贷款" if loan["loan_type"] == "breakthrough" else "普通贷款"
            
            if remaining_seconds <= 0:
                time_str = "⚠️ 已逾期！"
            elif remaining_days <= 0:
                time_str = f"🔴 {remaining_hours}小时"
            elif remaining_days <= 1:
                time_str = f"🟠 {remaining_days}天{remaining_hours}小时"
            else:
                time_str = f"🟡 {remaining_days}天"
            
            reply_msg += (
                f"\n"
                f"【贷款信息】💰\n"
                f"  类型：{loan_type_name}\n"
                f"  应还：{total_due:,} 灵石\n"
                f"  剩余：{time_str}\n"
                f"  💀 逾期将被追杀致死！\n"
            )
        
        reply_msg += "━━━━━━━━━━━━━━━"
        
        yield event.plain_result(reply_msg)

    @player_required
    async def handle_start_cultivation(self, player: Player, event: AstrMessageEvent):
        """处理闭关指令"""
        # 检查是否已经在闭关
        if player.state == "修炼中":
            yield event.plain_result("道友已在闭关中，请勿重复进入。")
            return
        
        # 检查是否在其他活动中（历练、秘境探索等）
        user_cd = await self.db.ext.get_user_cd(player.user_id)
        if user_cd and user_cd.type != UserStatus.IDLE:
            current_status = UserStatus.get_name(user_cd.type)
            yield event.plain_result(f"❌ 道友当前正{current_status}，无法闭关修炼！")
            return

        # 记录闭关开始时间
        player.state = "修炼中"
        player.cultivation_start_time = int(time.time())
        await self.db.update_player(player)
        await self.db.ext.set_user_busy(player.user_id, UserStatus.CULTIVATING, 0)

        yield event.plain_result(
            "🧘 道友已进入闭关状态\n"
            "━━━━━━━━━━━━━━━\n"
            "闭关期间，你将与世隔绝，潜心修炼。\n"
            f"💡 发送「{CMD_END_CULTIVATION}」结束闭关\n"
            "⏱️ 每分钟将获得修为，受灵根资质影响。"
        )

    @player_required
    async def handle_end_cultivation(self, player: Player, event: AstrMessageEvent):
        """处理出关指令"""
        # 检查是否在闭关中
        if player.state != "修炼中":
            yield event.plain_result("道友当前并未闭关，无需出关。")
            return

        # 检查是否有闭关开始时间
        if player.cultivation_start_time == 0:
            yield event.plain_result("数据异常：未记录闭关开始时间。")
            return

        # 计算闭关时长（分钟）
        end_time = int(time.time())
        duration_seconds = end_time - player.cultivation_start_time
        duration_minutes = duration_seconds // 60

        if duration_minutes < 1:
            yield event.plain_result("道友闭关时间不足1分钟，未获得修为。请继续闭关修炼。")
            return

        # 闭关时长上限：15天
        MAX_CULTIVATION_MINUTES = 21600  # 15天 = 360小时
        effective_minutes = min(duration_minutes, MAX_CULTIVATION_MINUTES)
        exceeded_time = duration_minutes > MAX_CULTIVATION_MINUTES

        # 读取所有丹药效果（含已过期的），用于分段计算
        raw_pill_effects = player.get_active_pill_effects()

        # 获取主修心法的修为加成
        technique_bonus = 0.0
        closing_exp_bonus = 0.0
        if player.main_technique:
            from ..core import EquipmentManager
            equipment_manager = EquipmentManager(self.db, self.config_manager)
            equipped_items = equipment_manager.get_equipped_items(
                player,
                self.config_manager.items_data,
                self.config_manager.weapons_data
            )
            # 找到主修心法
            for item in equipped_items:
                if item.item_type == "main_technique":
                    technique_bonus = item.exp_multiplier
                    closing_exp_bonus = item.closing_exp_bonus
                    break

        # 获取洞天福地修炼效率加成
        land_bonus = 0.0
        async with self.db.conn.execute(
            "SELECT SUM(exp_bonus) FROM blessed_lands WHERE user_id = ?",
            (player.user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                land_bonus = row[0]

        # 分段计算修为（丹药过期前后分别计算）
        gained_exp = self.cultivation_manager.calculate_cultivation_exp_with_segments(
            player,
            start_time=player.cultivation_start_time,
            end_time=end_time,
            technique_bonus=technique_bonus,
            raw_pill_effects=raw_pill_effects,
            land_bonus=land_bonus,
            closing_exp_bonus=closing_exp_bonus
        )

        # 更新玩家数据
        player.experience += gained_exp
        player.state = "空闲"
        player.cultivation_start_time = 0
        await self.db.update_player(player)
        await self.db.ext.set_user_free(player.user_id)

        # 清理过期丹药效果（修为计算完成后再清理）
        await self.pill_manager.update_temporary_effects(player)

        # 计算闭关时长显示
        hours = duration_minutes // 60
        minutes = duration_minutes % 60
        time_str = ""
        if hours > 0:
            time_str += f"{hours}小时"
        if minutes > 0:
            time_str += f"{minutes}分钟"

        # 超时提示
        exceed_msg = ""
        if exceeded_time:
            exceed_days = MAX_CULTIVATION_MINUTES // 1440
            exceed_msg = f"\n⚠️ 闭关超过{exceed_days}天，仅计算前{exceed_days}天修为"

        reply_msg = (
            "🌟 道友出关成功！\n"
            "━━━━━━━━━━━━━━━\n"
            f"⏱️ 闭关时长：{time_str}\n"
            f"📈 获得修为：{gained_exp:,}{exceed_msg}\n"
            f"💫 当前修为：{player.experience:,}\n"
            "━━━━━━━━━━━━━━━\n"
            "道友已回归红尘，可继续修行。"
        )
        yield event.plain_result(reply_msg)

    @player_required
    async def handle_check_in(self, player: Player, event: AstrMessageEvent):
        """处理签到指令"""
        today = datetime.now().strftime("%Y-%m-%d")
        current_month = datetime.now().strftime("%Y-%m")

        # 检查是否已经签到过
        if player.last_check_in_date == today:
            # 已签到，显示本月进度
            count = player.monthly_sign_count if player.monthly_sign_month == current_month else 0
            progress = self._build_sign_progress(count)
            yield event.plain_result(
                f"📅 道友今日已签到\n"
                f"请明日再来。\n"
                f"━━━━━━━━━━━━━━━\n"
                f"{progress}"
            )
            return

        # 获取签到奖励范围配置
        check_in_gold_min = self.config["VALUES"].get("CHECK_IN_GOLD_MIN", 50)
        check_in_gold_max = self.config["VALUES"].get("CHECK_IN_GOLD_MAX", 500)
        if check_in_gold_min > check_in_gold_max:
            check_in_gold_min, check_in_gold_max = check_in_gold_max, check_in_gold_min

        check_in_gold = random.randint(check_in_gold_min, check_in_gold_max)

        # 月累计签到：跨月重置
        if player.monthly_sign_month != current_month:
            player.monthly_sign_count = 0
            player.monthly_sign_month = current_month

        player.monthly_sign_count += 1
        count = player.monthly_sign_count

        # 更新玩家数据
        player.gold += check_in_gold
        player.last_check_in_date = today
        await self.db.update_player(player)

        # 活跃度追踪
        if self.activity_tracker:
            try:
                await self.activity_tracker.track_check_in(player)
            except Exception:
                pass

        # 构建进度
        progress = self._build_sign_progress(count)
        milestone_msg = await self._get_milestone_msg(player, count)

        reply_msg = (
            f"✅ 签到成功！（本月第{count}天）\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💰 获得灵石：{check_in_gold:,}\n"
            f"💎 当前灵石：{player.gold:,}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"{progress}"
        )
        if milestone_msg:
            reply_msg += f"\n━━━━━━━━━━━━━━━\n{milestone_msg}"
        yield event.plain_result(reply_msg)

    @staticmethod
    def _build_sign_progress(count: int) -> str:
        """构建月累计签到进度展示"""
        milestones = [7, 14, 21, 28]
        lines = [f"📅 本月签到：{count} 天"]
        for m in milestones:
            if count >= m:
                bar = "█" * 7 + " ✅"
            else:
                progress = count / m
                filled = round(progress * 7)
                bar = "█" * filled + "░" * (7 - filled) + " ⏳"
            lines.append(f" {m:>2}天 {bar}")
        return "\n".join(lines)

    async def _get_milestone_msg(self, player: Player, count: int) -> str:
        """检查是否达成里程碑，发放奖励并返回提示"""
        milestones = {
            7: ("第一周", "gold", 5000000),
            14: ("第二周", "pill", ("天道加速丹", 4)),
            21: ("第三周", "pill", ("混元加速丹", 2)),
            28: ("第四周", "pill", ("天命幸运丹", 1)),
        }
        if count not in milestones:
            return ""
        name, reward_type, reward_data = milestones[count]
        if reward_type == "gold":
            player.gold += reward_data
            await self.db.update_player(player)
            return (
                f"🎉 恭喜达成本月【{name}】签到里程碑！\n"
                f"💰 额外奖励：{reward_data:,} 灵石"
            )
        elif reward_type == "pill":
            pill_name, pill_count = reward_data
            inventory = player.get_pills_inventory()
            inventory[pill_name] = inventory.get(pill_name, 0) + pill_count
            player.set_pills_inventory(inventory)
            await self.db.update_player(player)
            return (
                f"🎉 恭喜达成本月【{name}】签到里程碑！\n"
                f"💊 额外奖励：{pill_name} ×{pill_count}"
            )
        return ""

    @player_required
    async def handle_rebirth(self, player: Player, event: AstrMessageEvent, confirm_text: str = ""):
        """弃道重修（7天冷却）"""
        user_cd = await self.db.ext.get_user_cd(player.user_id)
        if user_cd and user_cd.type != UserStatus.IDLE:
            status_name = UserStatus.get_name(user_cd.type)
            yield event.plain_result(f"❌ 你当前正在「{status_name}」，无法弃道重修。")
            return

        if player.state != "空闲":
            yield event.plain_result("❌ 只有处于空闲状态时才能弃道重修。请先结束闭关等活动。")
            return

        loan = await self.db.ext.get_active_loan(player.user_id)
        if loan:
            yield event.plain_result("❌ 你仍有未结清的灵石贷款，无法重修。请先还款。")
            return

        key = f"rebirth_last_{player.user_id}"
        last_ts = await self.db.ext.get_system_config(key)
        now = int(time.time())
        if last_ts:
            diff = now - int(last_ts)
            if diff < REBIRTH_COOLDOWN:
                remaining = REBIRTH_COOLDOWN - diff
                days = remaining // 86400
                hours = (remaining % 86400) // 3600
                minutes = (remaining % 3600) // 60
                yield event.plain_result(
                    "⌛ 弃道重修冷却中\n"
                    "━━━━━━━━━━━━━━━\n"
                    f"距离下次重修还需：{days}天{hours}小时{minutes}分钟"
                )
                return

        if confirm_text.strip() != "确认":
            yield event.plain_result(
                "⚠️ 弃道重修将删除当前角色的所有数据，并无法撤回！\n"
                "限制：每7天只能重修一次，且必须在空闲状态、无贷款时使用。\n"
                "━━━━━━━━━━━━━━━\n"
                "若你已做好准备，请发送：\n"
                "弃道重修 确认"
            )
            return

        await self.db.delete_player_cascade(player.user_id)
        await self.db.ext.set_system_config(key, str(now))

        yield event.plain_result(
            "💀 你选择了弃道重修，旧生一切化为尘埃。\n"
            "━━━━━━━━━━━━━━━\n"
            "可立即使用「我要修仙」重新踏上仙途。\n"
            "（7天内不可再次重修）"
        )

    @player_required
    async def handle_reroll_root(self, player: Player, event: AstrMessageEvent):
        """重铸灵根"""
        if player.gold < REROLL_ROOT_COST:
            yield event.plain_result(
                f"❌ 灵石不足！重铸灵根需要 {REROLL_ROOT_COST:,} 灵石。\n"
                f"当前灵石：{player.gold:,}"
            )
            return

        old_root = player.spiritual_root
        old_root_name = old_root.replace("灵根", "")
        old_desc = self.cultivation_manager._get_root_description(old_root_name)

        player.gold -= REROLL_ROOT_COST
        new_root = self.cultivation_manager._get_random_spiritual_root()
        player.spiritual_root = f"{new_root}灵根"
        await self.db.update_player(player)

        new_desc = self.cultivation_manager._get_root_description(new_root)

        yield event.plain_result(
            "✨ 重铸灵根成功！\n"
            "━━━━━━━━━━━━━━━\n"
            f"旧灵根：{old_root}（{old_desc}）\n"
            f"新灵根：{player.spiritual_root}（{new_desc}）\n"
            f"消耗灵石：{REROLL_ROOT_COST:,}\n"
            f"当前灵石：{player.gold:,}"
        )
