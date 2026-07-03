import json
import random
import time
from typing import Tuple, List, Optional, Dict
from ..data.data_manager import DataBase
from ..models_extended import Sect, UserStatus
from ..models import Player

SECT_NAME_MIN_LENGTH = 2
SECT_NAME_MAX_LENGTH = 12
SECT_NAME_FORBIDDEN = ["管理员", "系统", "官方", "GM", "admin"]


class SectManager:
    """宗门系统管理器"""

    # 宗门职位定义
    POSITIONS = {
        0: "宗主",
        1: "长老",
        2: "亲传弟子",
        3: "内门弟子",
        4: "外门弟子"
    }

    # 宗门职位权限
    POSITION_PERMISSIONS = {
        0: ["manage_all", "kick", "position_change", "build", "search_skill"],
        1: ["kick_outer", "build"],
        2: ["learn_skill"],
        3: ["learn_skill"],
        4: []  # 外门弟子无特殊权限
    }

    def __init__(self, db: DataBase, config_manager=None, activity_tracker=None):
        self.db = db
        self.config_manager = config_manager
        self.config = config_manager.sect_config if config_manager else {}
        self.activity_tracker = activity_tracker

    def _validate_sect_name(self, name: str) -> Tuple[bool, str]:
        """验证宗门名称"""
        if len(name) < SECT_NAME_MIN_LENGTH or len(name) > SECT_NAME_MAX_LENGTH:
            return False, f"❌ 宗门名称长度需在{SECT_NAME_MIN_LENGTH}-{SECT_NAME_MAX_LENGTH}字之间！"
        for forbidden in SECT_NAME_FORBIDDEN:
            if forbidden.lower() in name.lower():
                return False, f"❌ 宗门名称包含禁用词汇！"
        return True, ""

    def _get_member_limits(self, elixir_room_level: int) -> dict:
        """获取指定丹房等级下的成员上限配置

        Args:
            elixir_room_level: 丹房等级（0 = 未建设）

        Returns:
            {"total": ..., "elder": ..., "direct": ..., "inner": ...}
        """
        limits = self.config.get("member_limits", {})
        return limits.get(str(elixir_room_level), limits.get("0", {
            "total": 16, "elder": 3, "direct": 3, "inner": 11
        }))

    async def create_sect(
        self,
        user_id: str,
        sect_name: str,
        required_stone: int = None,
        required_level: int = None
    ) -> Tuple[bool, str]:
        """
        创建宗门

        Args:
            user_id: 用户ID
            sect_name: 宗门名称
            required_stone: 需求灵石（默认为配置值或10000）
            required_level: 需求境界等级（默认为配置值或3）

        Returns:
            (成功标志, 消息)
        """
        # 加载配置
        if required_stone is None:
            required_stone = self.config.get("create_cost", 10000)
        if required_level is None:
            required_level = self.config.get("create_level_required", 3)
        # 1. 检查用户是否存在
        player = await self.db.get_player_by_id(user_id)
        if not player:
            return False, "❌ 你还未踏入修仙之路！"

        # 2. 检查是否已有宗门
        if player.sect_id != 0:
            return False, "❌ 你已经加入了宗门，无法创建新宗门！"

        # 3. 检查境界
        if player.level_index < required_level:
            return False, f"❌ 创建宗门需要达到境界等级 {required_level}！"

        # 4. 检查灵石
        if player.gold < required_stone:
            return False, f"❌ 创建宗门需要 {required_stone} 灵石！"

        # 验证宗门名称
        valid, error = self._validate_sect_name(sect_name)
        if not valid:
            return False, error

        # 5. 检查宗门名称是否重复
        existing_sect = await self.db.ext.get_sect_by_name(sect_name)
        if existing_sect:
            return False, f"❌ 宗门名称『{sect_name}』已被使用！"

        # 6. 扣除灵石
        player.gold -= required_stone
        await self.db.update_player(player)

        # 7. 创建宗门
        new_sect = Sect(
            sect_id=0,  # 自动生成
            sect_name=sect_name,
            sect_owner=user_id,
            sect_scale=100,  # 初始建设度
            sect_used_stone=0,
            sect_fairyland=0,
            sect_materials=100,  # 初始资材
            mainbuff="0",
            secbuff="0",
            elixir_room_level=0
        )

        sect_id = await self.db.ext.create_sect(new_sect)

        # 8. 更新玩家宗门信息（设为宗主）
        await self.db.ext.update_player_sect_info(user_id, sect_id, 0)

        # 9. 初始化用户buff信息（如果没有）
        buff_info = await self.db.ext.get_buff_info(user_id)
        if not buff_info:
            await self.db.ext.create_buff_info(user_id)

        return True, f"✨ 恭喜！你成功创建了宗门『{sect_name}』，成为一代宗主！"

    async def join_sect(self, user_id: str, sect_name: str) -> Tuple[bool, str]:
        """
        加入宗门

        Args:
            user_id: 用户ID
            sect_name: 宗门名称

        Returns:
            (成功标志, 消息)
        """
        # 1. 检查用户
        player = await self.db.get_player_by_id(user_id)
        if not player:
            return False, "❌ 你还未踏入修仙之路！"

        if player.sect_id != 0:
            return False, "❌ 你已经加入了宗门！请先退出当前宗门。"

        # 2. 查找宗门
        sect = await self.db.ext.get_sect_by_name(sect_name)
        if not sect:
            return False, f"❌ 未找到宗门『{sect_name}』！"

        # 3. 检查成员上限
        limits = self._get_member_limits(sect.elixir_room_level)
        members = await self.db.ext.get_sect_members(sect.sect_id)
        member_count = len(members)
        total_limit = limits.get("total", 16)
        if member_count >= total_limit:
            return False, f"❌ 宗门『{sect_name}』成员已满（{member_count}/{total_limit}），无法加入！"

        # 4. 加入宗门（默认为外门弟子）
        await self.db.ext.update_player_sect_info(user_id, sect.sect_id, 4)

        # 5. 初始化buff信息
        buff_info = await self.db.ext.get_buff_info(user_id)
        if not buff_info:
            await self.db.ext.create_buff_info(user_id)

        return True, f"✨ 你成功加入了宗门『{sect_name}』，成为外门弟子！"

    async def leave_sect(self, user_id: str) -> Tuple[bool, str]:
        """
        退出宗门

        Args:
            user_id: 用户ID

        Returns:
            (成功标志, 消息)
        """
        player = await self.db.get_player_by_id(user_id)
        if not player:
            return False, "❌ 你还未踏入修仙之路！"

        if player.sect_id == 0:
            return False, "❌ 你还未加入任何宗门！"

        # 检查是否为宗主
        sect = await self.db.ext.get_sect_by_id(player.sect_id)
        if sect and sect.sect_owner == user_id:
            return False, "❌ 宗主无法直接退出宗门！请先传位或解散宗门。"

        sect_name = sect.sect_name if sect else "未知宗门"

        # 清除宗门信息
        await self.db.ext.update_player_sect_info(user_id, 0, 4)
        player.sect_contribution = 0
        await self.db.update_player(player)

        return True, f"✨ 你已退出宗门『{sect_name}』！"

    async def donate_to_sect(
        self,
        user_id: str,
        stone_amount: int
    ) -> Tuple[bool, str]:
        """
        宗门捐献（1灵石 = 10建设度）

        Args:
            user_id: 用户ID
            stone_amount: 捐献灵石数量

        Returns:
            (成功标志, 消息)
        """
        player = await self.db.get_player_by_id(user_id)
        if not player:
            return False, "❌ 你还未踏入修仙之路！"

        if player.sect_id == 0:
            return False, "❌ 你还未加入宗门！"

        if stone_amount <= 0:
            return False, "❌ 捐献数量必须大于0！"

        if player.gold < stone_amount:
            return False, f"❌ 你的灵石不足！当前拥有 {player.gold} 灵石。"

        # 扣除灵石
        player.gold -= stone_amount

        # 增加宗门贡献度（1灵石 = 1贡献）
        player.sect_contribution += stone_amount
        await self.db.update_player(player)

        # 增加宗门建设度和灵石（1灵石 = 10建设度）
        await self.db.ext.donate_to_sect(player.sect_id, stone_amount)

        scale_gained = stone_amount * self.config.get("scale_ratio", 10)

        return True, f"✨ 捐献成功！消耗 {stone_amount} 灵石，宗门获得 {scale_gained} 建设度！\n你的宗门贡献度：{player.sect_contribution}"

    async def get_sect_info(self, user_id: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        获取宗门信息

        Args:
            user_id: 用户ID

        Returns:
            (成功标志, 消息, 宗门数据)
        """
        player = await self.db.get_player_by_id(user_id)
        if not player:
            return False, "❌ 你还未踏入修仙之路！", None

        if player.sect_id == 0:
            return False, "❌ 你还未加入宗门！", None

        sect = await self.db.ext.get_sect_by_id(player.sect_id)
        if not sect:
            return False, "❌ 宗门信息异常！", None

        # 获取宗主信息
        owner = await self.db.get_player_by_id(sect.sect_owner)
        owner_name = owner.user_name if owner and owner.user_name else sect.sect_owner

        # 获取成员数量
        members = await self.db.ext.get_sect_members(sect.sect_id)
        member_count = len(members)

        # 构建信息
        position_name = self.POSITIONS.get(player.sect_position, "未知")

        # 丹房名称
        elixir_config = self.config.get("elixir_room", {})
        elixir_levels = elixir_config.get("levels", {})
        elixir_name = elixir_levels.get(str(sect.elixir_room_level), {}).get("name", "暂无") if sect.elixir_room_level > 0 else "暂无"

        # 修炼上限
        practice_config = self.config.get("practice", {})
        construction_per_level = practice_config.get("construction_per_level", 5000)
        max_level = practice_config.get("max_level", 50)
        practice_cap = min(sect.sect_scale // construction_per_level, max_level)

        # 成员上限
        limits = self._get_member_limits(sect.elixir_room_level)
        total_limit = limits.get("total", 16)

        info_msg = f"""
🏛️ 宗门信息
━━━━━━━━━━━━━━━

宗门名称：{sect.sect_name}
宗主：{owner_name}
建设度：{sect.sect_scale}
宗门灵石：{sect.sect_used_stone}
宗门资材：{sect.sect_materials}
丹房：{elixir_name}
成员数量：{member_count}/{total_limit}人

你的职位：{position_name}
你的贡献：{player.sect_contribution}
修炼上限：{practice_cap}级
        """.strip()

        sect_data = {
            "sect": sect,
            "player_position": player.sect_position,
            "player_contribution": player.sect_contribution,
            "member_count": member_count
        }

        return True, info_msg, sect_data

    async def list_all_sects(self) -> Tuple[bool, str]:
        """
        获取所有宗门列表

        Returns:
            (成功标志, 消息)
        """
        sects = await self.db.ext.get_all_sects()

        if not sects:
            return False, "❌ 当前还没有任何宗门！"

        msg = "🏛️ 宗门列表\n"
        msg += "━━━━━━━━━━━━━━━\n"

        for idx, sect in enumerate(sects[:10], 1):  # 只显示前10个
            owner = await self.db.get_player_by_id(sect.sect_owner)
            owner_name = owner.user_name if owner and owner.user_name else "未知"
            members = await self.db.ext.get_sect_members(sect.sect_id)

            # 成员上限
            limits = self._get_member_limits(sect.elixir_room_level)
            total_limit = limits.get("total", 16)

            msg += f"{idx}. 【{sect.sect_name}】\n"
            msg += f"   宗主：{owner_name}\n"
            msg += f"   建设度：{sect.sect_scale} | 成员：{len(members)}/{total_limit}人\n\n"

        return True, msg

    async def change_position(
        self,
        operator_id: str,
        target_id: str,
        new_position: int
    ) -> Tuple[bool, str]:
        """
        变更宗门职位

        Args:
            operator_id: 操作者ID（必须是宗主）
            target_id: 目标用户ID
            new_position: 新职位（0-4）

        Returns:
            (成功标志, 消息)
        """
        # 检查操作者
        operator = await self.db.get_player_by_id(operator_id)
        if not operator or operator.sect_id == 0:
            return False, "❌ 你还未加入宗门！"

        if operator.sect_position != 0:
            return False, "❌ 只有宗主才能变更职位！"

        # 检查目标用户
        target = await self.db.get_player_by_id(target_id)
        if not target:
            return False, "❌ 目标用户不存在！"

        if target.sect_id != operator.sect_id:
            return False, "❌ 目标用户不在你的宗门！"

        if target_id == operator_id:
            return False, "❌ 无法变更自己的职位！"

        if new_position not in self.POSITIONS:
            return False, "❌ 无效的职位！职位范围：0（宗主）- 4（外门弟子）"

        if new_position == 0:
            return False, "❌ 无法直接任命宗主！请使用传位功能。"

        # 检查目标职位的成员上限
        sect = await self.db.ext.get_sect_by_id(operator.sect_id)
        if not sect:
            return False, "❌ 宗门信息异常！"

        limits = self._get_member_limits(sect.elixir_room_level)
        members = await self.db.ext.get_sect_members(sect.sect_id)

        # 职位映射：1=长老 elder, 2=亲传弟子 direct, 3=内门弟子 inner, 4=外门弟子（无上限）
        position_limit_map = {
            1: "elder",
            2: "direct",
            3: "inner"
        }

        if new_position in position_limit_map:
            limit_key = position_limit_map[new_position]
            position_cap = limits.get(limit_key, 999)
            # 统计当前该职位的成员数量（排除正在被变更的目标用户，因为目标可能已在该职位）
            current_count = sum(1 for m in members if m.sect_position == new_position and m.user_id != target_id)
            if current_count >= position_cap:
                position_name = self.POSITIONS[new_position]
                return False, f"❌ {position_name}已达上限（{current_count}/{position_cap}），无法继续任命！"

        # 变更职位
        await self.db.ext.update_player_sect_info(target_id, target.sect_id, new_position)

        target_name = target.user_name if target.user_name else target_id
        position_name = self.POSITIONS[new_position]

        return True, f"✨ 已将 {target_name} 的职位变更为：{position_name}"

    async def transfer_ownership(
        self,
        current_owner_id: str,
        new_owner_id: str
    ) -> Tuple[bool, str]:
        """
        宗主传位

        Args:
            current_owner_id: 当前宗主ID
            new_owner_id: 新宗主ID

        Returns:
            (成功标志, 消息)
        """
        # 检查当前宗主
        current_owner = await self.db.get_player_by_id(current_owner_id)
        if not current_owner or current_owner.sect_id == 0:
            return False, "❌ 你还未加入宗门！"

        sect = await self.db.ext.get_sect_by_id(current_owner.sect_id)
        if not sect or sect.sect_owner != current_owner_id:
            return False, "❌ 你不是宗主！"

        # 检查新宗主
        new_owner = await self.db.get_player_by_id(new_owner_id)
        if not new_owner:
            return False, "❌ 目标用户不存在！"

        if new_owner.sect_id != current_owner.sect_id:
            return False, "❌ 目标用户不在你的宗门！"

        if new_owner_id == current_owner_id:
            return False, "❌ 无法传位给自己！"

        # 执行传位
        sect.sect_owner = new_owner_id
        await self.db.ext.update_sect(sect)

        # 更新职位：新宗主->宗主，旧宗主->长老
        await self.db.ext.update_player_sect_info(new_owner_id, sect.sect_id, 0)
        await self.db.ext.update_player_sect_info(current_owner_id, sect.sect_id, 1)

        new_owner_name = new_owner.user_name if new_owner.user_name else new_owner_id

        return True, f"✨ 宗主之位已传给 {new_owner_name}！你现在是长老。"

    async def kick_member(
        self,
        operator_id: str,
        target_id: str
    ) -> Tuple[bool, str]:
        """
        踢出宗门成员

        Args:
            operator_id: 操作者ID
            target_id: 目标用户ID

        Returns:
            (成功标志, 消息)
        """
        # 检查操作者权限
        operator = await self.db.get_player_by_id(operator_id)
        if not operator or operator.sect_id == 0:
            return False, "❌ 你还未加入宗门！"

        # 宗主和长老可以踢人
        if operator.sect_position not in [0, 1]:
            return False, "❌ 只有宗主和长老才能踢出成员！"

        # 检查目标
        target = await self.db.get_player_by_id(target_id)
        if not target:
            return False, "❌ 目标用户不存在！"

        if target.sect_id != operator.sect_id:
            return False, "❌ 目标用户不在你的宗门！"

        if target_id == operator_id:
            return False, "❌ 无法踢出自己！"

        # 长老只能踢外门弟子
        if operator.sect_position == 1 and target.sect_position <= 3:
            return False, "❌ 长老只能踢出外门弟子！"

        # 无法踢出宗主
        if target.sect_position == 0:
            return False, "❌ 无法踢出宗主！"

        # 踢出
        target_name = target.user_name if target.user_name else target_id
        await self.db.ext.update_player_sect_info(target_id, 0, 4)
        target.sect_contribution = 0
        await self.db.update_player(target)

        return True, f"✨ 已将 {target_name} 踢出宗门！"

    def _get_random_task(self) -> dict:
        """从配置中随机选取一个宗门任务（等概率20%）"""
        tasks = self.config.get("tasks", [])
        if not tasks:
            return None
        return random.choice(tasks)

    async def get_current_task(self, user_id: str) -> Optional[dict]:
        """获取玩家当前的宗门任务（从 extra_data 读取）"""
        user_cd = await self.db.ext.get_user_cd(user_id)
        if not user_cd:
            return None
        extra = user_cd.get_extra_data()
        task_data = extra.get("current_sect_task")
        if task_data:
            return task_data
        return None

    async def _assign_task(self, user_id: str) -> dict:
        """随机分配任务并持久化到 extra_data"""
        task = self._get_random_task()
        if not task:
            return None
        user_cd = await self.db.ext.get_user_cd(user_id)
        if not user_cd:
            await self.db.ext.create_user_cd(user_id)
            user_cd = await self.db.ext.get_user_cd(user_id)
        extra = user_cd.get_extra_data()
        extra["current_sect_task"] = task
        extra["sect_task_name"] = task["name"]
        await self.db.conn.execute(
            "UPDATE user_cd SET extra_data = ? WHERE user_id = ?",
            (json.dumps(extra, ensure_ascii=False), user_id)
        )
        await self.db.conn.commit()
        return task

    async def perform_sect_task(self, user_id: str) -> Tuple[bool, str]:
        """
        执行宗门任务（5种任务类型）
        每日限3次，冷却10分钟

        Args:
            user_id: 用户ID

        Returns:
            (成功标志, 消息)
        """
        player = await self.db.get_player_by_id(user_id)
        if not player or player.sect_id == 0:
            return False, "❌ 你还未加入宗门！"

        user_cd = await self.db.ext.get_user_cd(user_id)
        if not user_cd:
            await self.db.ext.create_user_cd(user_id)
            user_cd = await self.db.ext.get_user_cd(user_id)

        current_time = int(time.time())
        today_str = time.strftime("%Y-%m-%d", time.localtime(current_time))

        # 检查用户是否处于其他忙碌状态（闭关/历练/探索等）
        if user_cd.type != UserStatus.IDLE and user_cd.type != UserStatus.SECT_TASK:
            status_name = UserStatus.get_name(user_cd.type)
            return False, f"❌ 你当前正{status_name}，无法执行宗门任务！"

        extra = user_cd.get_extra_data()

        # 通过 extra_data 中的 sect_task_cd 检查冷却（不占用用户忙碌状态）
        sect_cd = extra.get("sect_task_cd", 0)
        if sect_cd > 0 and current_time < sect_cd:
            remaining = sect_cd - current_time
            return False, f"❌ 宗门任务冷却中！还需 {remaining//60} 分钟{remaining % 60} 秒。"

        # 每日次数限制（跨日自动重置当前玩家，全服重置由后台定时任务处理）
        task_config = self.config
        daily_limit = task_config.get("daily_task_limit", 3)
        task_cooldown = task_config.get("task_cooldown", 600)

        last_date = extra.get("sect_task_date", "")
        if last_date != today_str:
            player.sect_task = 0
            extra["sect_task_date"] = today_str

        if player.sect_task >= daily_limit:
            return False, f"❌ 今日宗门任务次数已用完（每日{daily_limit}次），明天再来吧！"

        # 获取或分配当前任务
        task = extra.get("current_sect_task")
        if not task:
            task = await self._assign_task(user_id)
            if not task:
                return False, "❌ 宗门任务配置异常，请联系管理员！"
            # 重新获取 extra（_assign_task 已更新数据库）
            user_cd = await self.db.ext.get_user_cd(user_id)
            extra = user_cd.get_extra_data()

        task_name = task.get("name", "未知任务")
        task_type = task.get("type", "hp")

        # 检查代价
        cost_msg = ""
        if task_type == "hp":
            cost_ratio = task.get("cost_ratio", 0.4)
            cost_hp = int(player.experience / 2 * cost_ratio)
            # 检查血量是否足够
            if player.hp < player.experience / 10:
                return False, f"❌ 你的血量不足，无法执行『{task_name}』！请先恢复血量。"
            if cost_hp >= player.hp:
                return False, f"❌ 执行『{task_name}』需要消耗 {cost_hp} 血量，但你当前只有 {player.hp} 血量！"
            player.hp -= cost_hp
            cost_msg = f"消耗血量：{cost_hp}"
        elif task_type == "stone":
            cost = task.get("cost", 0)
            if player.gold < cost:
                return False, f"❌ 执行『{task_name}』需要 {cost} 灵石，但你只有 {player.gold} 灵石！"
            player.gold -= cost
            cost_msg = f"消耗灵石：{cost}"

        # 计算经验奖励
        exp_ratio = task.get("exp_ratio", 0.01)
        exp_gain = int(player.experience * exp_ratio)

        # 按职位限制经验上限
        task_exp_caps = task_config.get("task_exp_caps", {})
        position_key = str(player.sect_position)
        exp_cap = task_exp_caps.get(position_key, task_exp_caps.get("4", 10000))
        if exp_gain > exp_cap:
            exp_gain = exp_cap

        # 发放奖励
        player.experience += exp_gain
        player.sect_contribution += task.get("sect_stone", 0)
        player.sect_task += 1  # 先在内存中递增，防止后续 update_player 覆盖 DB 中的 increment
        await self.db.update_player(player)

        # 宗门增加资材和建设度（使用任务配置的倍率）
        sect_stone = task.get("sect_stone", 0)
        material_mult = task.get("material_mult", 10)
        scale_mult = task.get("scale_mult", 1)
        materials_gain = sect_stone * material_mult
        scale_gain = sect_stone * scale_mult

        sect = await self.db.ext.get_sect_by_id(player.sect_id)
        if sect:
            sect.sect_materials += materials_gain
            sect.sect_scale += scale_gain
            await self.db.ext.update_sect(sect)

        # 设置冷却 + 清除当前任务 + 更新日期，通过 extra_data 存储
        extra["sect_task_cd"] = current_time + task_cooldown
        extra["sect_task_date"] = today_str
        extra.pop("current_sect_task", None)
        extra.pop("sect_task_name", None)
        await self.db.conn.execute(
            "UPDATE user_cd SET type = 0, extra_data = ? WHERE user_id = ?",
            (json.dumps(extra, ensure_ascii=False), user_id)
        )
        await self.db.conn.commit()

        # 活跃度追踪
        if self.activity_tracker:
            try:
                await self.activity_tracker.track_sect(player)
            except Exception:
                pass

        remaining_count = daily_limit - player.sect_task
        return True, (
            f"✨ 完成宗门任务『{task_name}』！\n"
            f"📜 {task.get('desc', '')}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"{cost_msg}\n"
            f"获得修为：+{exp_gain}\n"
            f"获得贡献：+{sect_stone}\n"
            f"宗门资材：+{materials_gain}\n"
            f"宗门建设：+{scale_gain}\n"
            f"📋 今日剩余次数：{remaining_count}/{daily_limit}"
        )

    async def refresh_sect_task(self, user_id: str) -> Tuple[bool, str]:
        """
        刷新宗门任务（5分钟冷却，不消耗每日次数）

        Args:
            user_id: 用户ID

        Returns:
            (成功标志, 消息)
        """
        player = await self.db.get_player_by_id(user_id)
        if not player or player.sect_id == 0:
            return False, "❌ 你还未加入宗门！"

        user_cd = await self.db.ext.get_user_cd(user_id)
        if not user_cd:
            await self.db.ext.create_user_cd(user_id)
            user_cd = await self.db.ext.get_user_cd(user_id)

        current_time = int(time.time())
        extra = user_cd.get_extra_data()

        # 检查刷新冷却
        refresh_cd = self.config.get("task_refresh_cd", 300)
        last_refresh = extra.get("sect_task_refresh_cd", 0)
        if last_refresh > 0 and current_time < last_refresh:
            remaining = last_refresh - current_time
            return False, f"❌ 刷新冷却中！还需 {remaining//60} 分{remaining % 60} 秒。"

        # 分配新任务
        task = await self._assign_task(user_id)
        if not task:
            return False, "❌ 宗门任务配置异常，请联系管理员！"

        # 设置刷新冷却
        extra = (await self.db.ext.get_user_cd(user_id)).get_extra_data()
        extra["sect_task_refresh_cd"] = current_time + refresh_cd
        await self.db.conn.execute(
            "UPDATE user_cd SET extra_data = ? WHERE user_id = ?",
            (json.dumps(extra, ensure_ascii=False), user_id)
        )
        await self.db.conn.commit()

        return True, (
            f"✨ 任务刷新成功！\n"
            f"新任务：『{task['name']}』\n"
            f"📜 {task.get('desc', '')}"
        )

    # ===== 攻击修炼系统 =====

    def _get_attack_practice_cost(self, level: int) -> Tuple[int, int]:
        """获取攻击修炼指定等级的消耗

        Args:
            level: 要升级到的等级

        Returns:
            (materials_cost, stone_cost)
        """
        cost_table = self.config.get("attack_practice_costs", [])
        if not cost_table:
            # 降级：如果没有成本表，使用默认值
            return (8000000, 800000)

        # 查找对应等级的消耗（level 从 1 开始，索引从 0 开始）
        if level <= 0:
            return (cost_table[0]["materials"], cost_table[0]["stone"])

        # 如果等级超出表范围，使用最后一个条目的消耗
        if level > len(cost_table):
            last_entry = cost_table[-1]
            return (last_entry["materials"], last_entry["stone"])

        entry = cost_table[level - 1]
        return (entry["materials"], entry["stone"])

    async def upgrade_practice(self, user_id: str, count: int = 1) -> Tuple[bool, str]:
        """升级攻击修炼等级

        Args:
            user_id: 用户ID
            count: 升级次数

        Returns:
            (成功标志, 消息)
        """
        player = await self.db.get_player_by_id(user_id)
        if not player:
            return False, "❌ 你还未踏入修仙之路！"

        if player.sect_id == 0:
            return False, "❌ 你尚未加入宗门，请加入宗门后再修炼！"

        if player.sect_position == 4:
            return False, "❌ 外门弟子无法使用宗门修炼资源，请先提升职位！"

        sect = await self.db.ext.get_sect_by_id(player.sect_id)
        if not sect:
            return False, "❌ 宗门信息异常！"

        practice_config = self.config.get("practice", {})
        atk_per_level = practice_config.get("atk_per_level", 0.04)
        max_level = practice_config.get("max_level", 50)
        construction_per_level = practice_config.get("construction_per_level", 5000)

        # 宗门修炼等级上限 = 建设度 / construction_per_level，封顶 max_level
        sect_level_cap = min(sect.sect_scale // construction_per_level, max_level)

        if player.atkpractice >= sect_level_cap:
            return False, (
                f"❌ 修炼等级已达当前宗门上限：{sect_level_cap}级！\n"
                f"请捐献灵石提升宗门建设度来解锁更高等级。"
            )

        # 限制升级次数不超过上限
        count = min(count, sect_level_cap - player.atkpractice)
        if count <= 0:
            return False, "❌ 无法继续升级！"

        # 计算总成本（逐级累加，使用成本表）
        total_stone = 0
        total_materials = 0
        for i in range(count):
            next_level = player.atkpractice + i + 1  # 要升级到的等级
            materials_cost, stone_cost = self._get_attack_practice_cost(next_level)
            total_stone += stone_cost
            total_materials += materials_cost

        if player.gold < total_stone:
            return False, f"❌ 灵石不足！升级到 {player.atkpractice + count} 级需要 {total_stone} 灵石，你只有 {player.gold}。"

        if sect.sect_materials < total_materials:
            return False, f"❌ 宗门资材不足！需要 {total_materials} 资材，当前只有 {sect.sect_materials}。"

        # 扣除资源
        player.gold -= total_stone
        player.atkpractice += count
        await self.db.update_player(player)

        sect.sect_materials -= total_materials
        await self.db.ext.update_sect(sect)

        atk_bonus_pct = player.atkpractice * atk_per_level * 100
        return True, (
            f"✨ 修炼成功！当前攻击修炼等级：{player.atkpractice}\n"
            f"攻击力加成：+{atk_bonus_pct:.0f}%\n"
            f"消耗灵石：{total_stone}，宗门资材：{total_materials}"
        )

    async def get_practice_info(self, user_id: str) -> Tuple[bool, str]:
        """查看修炼信息"""
        player = await self.db.get_player_by_id(user_id)
        if not player:
            return False, "❌ 你还未踏入修仙之路！"

        if player.sect_id == 0:
            return False, "❌ 你尚未加入宗门！"

        sect = await self.db.ext.get_sect_by_id(player.sect_id)
        if not sect:
            return False, "❌ 宗门信息异常！"

        practice_config = self.config.get("practice", {})
        atk_per_level = practice_config.get("atk_per_level", 0.04)
        max_level = practice_config.get("max_level", 50)
        construction_per_level = practice_config.get("construction_per_level", 5000)

        sect_level_cap = min(sect.sect_scale // construction_per_level, max_level)
        current_bonus = player.atkpractice * atk_per_level * 100

        position_name = self.POSITIONS.get(player.sect_position, "未知")

        msg = (
            f"⚔️ 攻击修炼信息\n"
            f"━━━━━━━━━━━━━━━\n"
            f"当前等级：{player.atkpractice}\n"
            f"宗门上限：{sect_level_cap}级\n"
            f"攻击力加成：+{current_bonus:.0f}%\n"
            f"你的职位：{position_name}"
        )

        if player.atkpractice < sect_level_cap:
            next_level = player.atkpractice + 1
            next_mats, next_stone = self._get_attack_practice_cost(next_level)
            msg += f"\n\n下次升级消耗：\n灵石：{next_stone}，资材：{next_mats}"

        return True, msg

    # ===== 丹房系统 =====

    async def upgrade_elixir_room(self, user_id: str) -> Tuple[bool, str]:
        """建设/升级宗门丹房（宗主专属）

        升级消耗建设度（sect_scale），不消耗宗门灵石。
        """
        player = await self.db.get_player_by_id(user_id)
        if not player:
            return False, "❌ 你还未踏入修仙之路！"

        if player.sect_id == 0:
            return False, "❌ 你尚未加入宗门！"

        if player.sect_position != 0:
            return False, "❌ 只有宗主才能建设丹房！"

        sect = await self.db.ext.get_sect_by_id(player.sect_id)
        if not sect:
            return False, "❌ 宗门信息异常！"

        elixir_config = self.config.get("elixir_room", {})
        levels = elixir_config.get("levels", {})
        current_level = str(sect.elixir_room_level)

        if current_level == str(len(levels)):
            return False, "❌ 丹房已达到最高等级！"

        next_level = str(sect.elixir_room_level + 1)
        if next_level not in levels:
            return False, "❌ 丹房配置异常！"

        level_config = levels[next_level]
        cost_scale = level_config["upgrade_cost_scale"]

        if sect.sect_scale < cost_scale:
            return False, f"❌ 建设度不足！需要 {cost_scale}，当前 {sect.sect_scale}。"

        # 仅扣除建设度，不消耗宗门灵石
        sect.sect_scale -= cost_scale
        sect.elixir_room_level = int(next_level)
        await self.db.ext.update_sect(sect)

        room_name = level_config["name"]
        return True, (
            f"✨ 丹房建设成功！\n"
            f"当前丹房：{room_name}\n"
            f"消耗建设度：{cost_scale}"
        )

    async def claim_sect_pill(self, user_id: str) -> Tuple[bool, str]:
        """领取宗门丹药（每日一次）

        第一颗丹药必定为渡厄丹（guaranteed_pill），其余为随机丹药。
        """
        player = await self.db.get_player_by_id(user_id)
        if not player:
            return False, "❌ 你还未踏入修仙之路！"

        if player.sect_id == 0:
            return False, "❌ 你还未加入宗门！"

        if player.sect_position == 4:
            return False, "❌ 外门弟子无法领取丹药，请先提升职位！"

        sect = await self.db.ext.get_sect_by_id(player.sect_id)
        if not sect:
            return False, "❌ 宗门信息异常！"

        if sect.elixir_room_level == 0:
            return False, "❌ 宗门尚未建设丹房！请宗主使用 /丹房建设。"

        elixir_config = self.config.get("elixir_room", {})
        claim_required = elixir_config.get("claim_contribution_required", 100)
        if player.sect_contribution < claim_required:
            return False, f"❌ 贡献不足！需要 {claim_required} 贡献，当前 {player.sect_contribution}。"

        # 跨日自愈重置（与 sect_task 同模式）
        user_cd = await self.db.ext.get_user_cd(player.user_id)
        if not user_cd:
            await self.db.ext.create_user_cd(player.user_id)
            user_cd = await self.db.ext.get_user_cd(player.user_id)
        if user_cd:
            extra = user_cd.get_extra_data()
            today_str = time.strftime("%Y-%m-%d")
            if extra.get("elixir_claim_date", "") != today_str:
                player.sect_elixir_get = 0
                extra["elixir_claim_date"] = today_str
                await self.db.conn.execute(
                    "UPDATE user_cd SET extra_data = ? WHERE user_id = ?",
                    (json.dumps(extra, ensure_ascii=False), player.user_id)
                )
                await self.db.conn.commit()

        if player.sect_elixir_get == 1:
            return False, "❌ 今日已领取过丹药，不要贪心哦~"

        # 从等级配置中读取维护费
        levels = elixir_config.get("levels", {})
        level_config = levels.get(str(sect.elixir_room_level), {})
        maintenance_cost = level_config.get("maintenance_cost", 0)
        if maintenance_cost == 0:
            # 降级兼容：旧配置用 maintenance_cost_per_level
            maintenance_per_level = elixir_config.get("maintenance_cost_per_level", 5000)
            maintenance_cost = sect.elixir_room_level * maintenance_per_level
        if sect.sect_materials < maintenance_cost:
            return False, f"❌ 宗门资材不足以维护丹房（需要 {maintenance_cost}），请等待资材发放后再领取！"

        daily_pills = level_config.get("daily_pills", 1)
        pill_rank_max = level_config.get("pill_rank_max", 5)
        guaranteed_pill = level_config.get("guaranteed_pill", "渡厄丹")

        # 第一颗必定为渡厄丹，其余随机
        pill_names = [guaranteed_pill]
        random_count = daily_pills - 1
        if random_count > 0:
            random_pills = self._select_random_pills(player.level_index, random_count, pill_rank_max)
            pill_names.extend(random_pills)

        # 扣除维护费
        sect.sect_materials -= maintenance_cost
        await self.db.ext.update_sect(sect)

        # 发放丹药
        inventory = player.get_pills_inventory()
        for pill_name in pill_names:
            inventory[pill_name] = inventory.get(pill_name, 0) + 1
        player.set_pills_inventory(inventory)

        # 标记已领取
        player.sect_elixir_get = 1
        await self.db.update_player(player)

        pill_list = "、".join(f"{name} x1" for name in pill_names)
        return True, (
            f"✨ 成功领取宗门丹药！\n"
            f"获得：{pill_list}\n"
            f"（丹房维护消耗资材：{maintenance_cost}）"
        )

    def _select_random_pills(self, player_level: int, count: int, pill_rank_max: int = 5) -> list:
        """为丹房领取随机选择丹药（高品阶丹药权重更高）

        Args:
            player_level: 玩家 level_index
            count: 发放数量
            pill_rank_max: 最高品阶（1=凡品, 2=灵品, 3=地品, 4=天品, 5=皇品, 6=帝品, 7=道品, 8=仙品, 9=混元先天）
        """
        RANK_MAP = {
            "凡品": 1, "灵品": 2, "地品": 3, "天品": 4,
            "皇品": 5, "帝品": 6, "道品": 7, "仙品": 8, "混元先天": 9
        }
        # 每个品阶的权重：品阶越高权重越大
        RANK_WEIGHT = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8, 9: 9}

        pill_pool = []  # (name, weight)

        # 仅从经验丹中筛选（exp_pills_data 有 required_level_index 字段）
        if self.config_manager and hasattr(self.config_manager, 'exp_pills_data'):
            for name, data in self.config_manager.exp_pills_data.items():
                if not isinstance(data, dict):
                    continue
                req_level = data.get("required_level_index", 99)
                rank = data.get("rank", "")
                rank_value = RANK_MAP.get(rank, 99)
                if req_level <= player_level and rank_value <= pill_rank_max:
                    weight = RANK_WEIGHT.get(rank_value, 1)
                    pill_pool.append((name, weight))

        if not pill_pool:
            # 降级：无合适丹药，返回渡厄丹
            return ["渡厄丹"] * count

        # 按品阶加权随机选择
        names, weights = zip(*pill_pool)
        return [random.choices(names, weights=weights, k=1)[0] for _ in range(count)]

    # ===== 宗门改名 =====

    async def rename_sect(self, user_id: str, new_name: str) -> Tuple[bool, str]:
        """宗门改名（宗主专属）"""
        player = await self.db.get_player_by_id(user_id)
        if not player:
            return False, "❌ 你还未踏入修仙之路！"

        if player.sect_id == 0:
            return False, "❌ 你尚未加入宗门！"

        if player.sect_position != 0:
            return False, "❌ 只有宗主才能改名！"

        # 验证名称
        valid, error = self._validate_sect_name(new_name)
        if not valid:
            return False, error

        rename_config = self.config.get("rename", {})
        cost_contribution = rename_config.get("cost_contribution", 500)

        if player.sect_contribution < cost_contribution:
            return False, f"❌ 贡献不足！改名需要 {cost_contribution} 贡献，当前 {player.sect_contribution}。"

        # 检查重名
        existing = await self.db.ext.get_sect_by_name(new_name)
        if existing:
            return False, f"❌ 宗门名称『{new_name}』已被使用！"

        # 执行改名
        sect = await self.db.ext.get_sect_by_id(player.sect_id)
        old_name = sect.sect_name if sect else "未知"
        success = await self.db.ext.update_sect_name(player.sect_id, new_name)
        if not success:
            return False, "❌ 改名失败，可能名称重复！"

        # 扣除贡献
        player.sect_contribution -= cost_contribution
        await self.db.update_player(player)

        return True, (
            f"✨ 宗门改名成功！\n"
            f"『{old_name}』 → 『{new_name}』\n"
            f"消耗贡献：{cost_contribution}"
        )

    async def handle_owner_death(self, sect_id: int, dead_owner_id: str) -> Tuple[bool, str]:
        """处理宗主离线/退游，自动传位或解散宗门。

        注意：此方法为 GM 管理工具，当玩家账号被删除或长期离线时调用。
        战斗中的"死亡"（HP ≤ 0）不触发此逻辑。
        """
        members = await self.db.ext.get_sect_members(sect_id)
        # 过滤掉死亡的宗主
        remaining = [m for m in members if m.user_id != dead_owner_id]

        if not remaining:
            # 无其他成员，解散宗门
            await self.db.ext.delete_sect(sect_id)
            return True, "宗门已解散"

        # 按职位和贡献排序，选择新宗主
        remaining.sort(key=lambda m: (m.sect_position, -m.sect_contribution))
        new_owner = remaining[0]

        # 更新宗门宗主
        sect = await self.db.ext.get_sect_by_id(sect_id)
        if sect:
            sect.sect_owner = new_owner.user_id
            await self.db.ext.update_sect(sect)
            await self.db.ext.update_player_sect_info(new_owner.user_id, sect_id, 0)

        return True, f"宗主之位已传给{new_owner.user_name or new_owner.user_id}"
