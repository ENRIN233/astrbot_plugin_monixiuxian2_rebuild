# handlers/skill_handler.py
"""神通系统处理器"""

from astrbot.api.event import AstrMessageEvent
from ..data import DataBase
from ..config_manager import ConfigManager
from ..managers.skill_manager import SkillManager, SKILL_TYPE_NAMES
from ..models import Player
from .utils import player_required

__all__ = ["SkillHandler"]

SKILL_TYPE_DESC = {
    1: "攻击",
    2: "持续",
    3: "增益",
    4: "控制",
}


class SkillHandler:
    """神通系统处理器"""

    def __init__(self, db: DataBase, config_manager: ConfigManager,
                 skill_manager: SkillManager, equipment_manager, storage_ring_manager):
        self.db = db
        self.config_manager = config_manager
        self.skill_manager = skill_manager
        self.equipment_manager = equipment_manager
        self.storage_ring_manager = storage_ring_manager

    async def handle_skill_list(self, event: AstrMessageEvent):
        """显示所有神通列表"""
        skills_data = self.config_manager.skills_data
        if not skills_data:
            yield event.plain_result("暂无神通数据")
            return

        # 按类型分组
        by_type = {1: [], 2: [], 3: [], 4: []}
        for name, data in skills_data.items():
            stype = data.get("skill_type", 1)
            if stype in by_type:
                by_type[stype].append(data)

        lines = ["✦ 神通列表", "━━━━━━━━━━━━━━━"]

        for stype, label in SKILL_TYPE_DESC.items():
            skills = by_type.get(stype, [])
            if not skills:
                continue
            lines.append(f"\n【{label}神通】({len(skills)}个)")
            for s in sorted(skills, key=lambda x: x.get("required_level_index", 0)):
                rank = s.get("rank", "")
                level = s.get("required_level_index", 0)
                mp = s.get("mpcost", 0)
                cd = s.get("turncost", 0)
                rate = s.get("rate", 100)

                effect = ""
                if stype == 1:
                    av = s.get("atkvalue", [])
                    if isinstance(av, list) and len(av) > 1:
                        effect = f"{len(av)}连击，倍率{av}"
                    elif isinstance(av, list) and av:
                        effect = f"倍率{av[0]}"
                elif stype == 2:
                    effect = f"持续{s.get('turncost', 3)}回合"
                elif stype == 3:
                    bt = "攻击" if s.get("bufftype") == 1 else "防御"
                    bv = int(s.get("buffvalue", 0) * 100)
                    effect = f"{bt}+{bv}%({s.get('turncost', 3)}回合)"
                elif stype == 4:
                    effect = f"封禁{s.get('turncost', 2)}回合，成功率{s.get('success', 50)}%"

                hp_cost = s.get("hpcost", 0)
                cost_parts = []
                if mp > 0:
                    cost_parts.append(f"MP:{mp}")
                if hp_cost > 0:
                    cost_parts.append(f"HP:{int(hp_cost * 100)}%")
                cost_str = " ".join(cost_parts) if cost_parts else "无消耗"

                lines.append(
                    f"  {s['name']}（{rank}·Lv{level}）\n"
                    f"    {effect} | {cost_str} | CD:{cd}回合 | 触发:{rate}%"
                )

        lines.append("\n━━━━━━━━━━━━━━━")
        yield event.plain_result("\n".join(lines))

    @player_required
    async def handle_my_skill(self, player: Player, event: AstrMessageEvent):
        """查看已装备神通"""
        if not player.shentong:
            yield event.plain_result("你尚未装备神通\n使用 /装备神通 <名称> 装备神通")
            return

        skill_data = self.skill_manager.get_skill_data(player.shentong)
        if not skill_data:
            yield event.plain_result(f"神通数据异常：{player.shentong}")
            return

        stype = skill_data.get("skill_type", 1)
        label = SKILL_TYPE_DESC.get(stype, "未知")

        lines = [
            f"✦ 当前神通",
            f"━━━━━━━━━━━━━━━",
            f"【{player.shentong}】（{skill_data.get('rank', '')}·{label}神通）",
            f"  {skill_data.get('desc', '')}",
            "",
        ]

        if stype == 1:
            av = skill_data.get("atkvalue", [])
            if isinstance(av, list):
                lines.append(f"  攻击：{len(av)}段，倍率 {av}")
        elif stype == 2:
            av = skill_data.get("atkvalue", 0)
            lines.append(f"  持续伤害：倍率 {av}，持续 {skill_data.get('turncost', 3)} 回合")
        elif stype == 3:
            bt = "攻击力" if skill_data.get("bufftype") == 1 else "防御力"
            bv = int(skill_data.get("buffvalue", 0) * 100)
            lines.append(f"  效果：{bt} +{bv}%，持续 {skill_data.get('turncost', 3)} 回合")
        elif stype == 4:
            lines.append(f"  封禁 {skill_data.get('turncost', 2)} 回合，成功率 {skill_data.get('success', 50)}%")

        mp = skill_data.get("mpcost", 0)
        hp = skill_data.get("hpcost", 0)
        cost_parts = []
        if mp > 0:
            cost_parts.append(f"MP消耗: {mp}")
        if hp > 0:
            cost_parts.append(f"HP消耗: {int(hp * 100)}%")
        lines.append(f"  冷却: {skill_data.get('turncost', 0)} 回合")
        lines.append(f"  触发率: {skill_data.get('rate', 100)}%")
        if cost_parts:
            lines.append(f"  {'，'.join(cost_parts)}")

        lines.append("━━━━━━━━━━━━━━━")
        yield event.plain_result("\n".join(lines))

    @player_required
    async def handle_equip_skill(self, player: Player, event: AstrMessageEvent, skill_name: str):
        """装备神通"""
        if not skill_name or skill_name.strip() == "":
            yield event.plain_result("请指定神通名称\n用法：/装备神通 神通名称")
            return

        skill_name = skill_name.strip()

        # 检查神通是否存在
        skill_data = self.config_manager.skills_data.get(skill_name)
        if not skill_data:
            yield event.plain_result(f"未找到神通：{skill_name}")
            return

        # 检查境界要求
        required_level = skill_data.get("required_level_index", 0)
        if player.level_index < required_level:
            yield event.plain_result(f"境界不足！装备【{skill_name}】需要达到更高境界")
            return

        # 检查储物戒
        if not self.storage_ring_manager.has_item(player, skill_name, 1):
            yield event.plain_result(
                f"储物戒中没有【{skill_name}】\n"
                f"请先通过购买或获得该神通"
            )
            return

        # 从储物戒取出
        success, retrieve_msg = await self.storage_ring_manager.retrieve_item(player, skill_name, 1)
        if not success:
            yield event.plain_result(f"无法从储物戒取出：{retrieve_msg}")
            return

        # 创建Item对象
        from ..models import Item
        item = Item(
            item_id=skill_data.get("id", skill_name),
            name=skill_name,
            item_type="shentong",
            description=skill_data.get("desc", ""),
            rank=skill_data.get("rank", ""),
            required_level_index=skill_data.get("required_level_index", 0),
        )

        # 装备
        success, message = await self.equipment_manager.equip_item(player, item)

        if success:
            yield event.plain_result(f"✅ {message}")
        else:
            # 装备失败，放回储物戒
            await self.storage_ring_manager.store_item(player, skill_name, 1, silent=True)
            yield event.plain_result(f"❌ {message}")

    @player_required
    async def handle_unequip_skill(self, player: Player, event: AstrMessageEvent):
        """卸下神通"""
        if not player.shentong:
            yield event.plain_result("你尚未装备神通")
            return

        skill_name = player.shentong
        success, message = await self.equipment_manager.unequip_item(player, "神通")

        if success:
            storage_msg = ""
            store_success, store_msg = await self.storage_ring_manager.store_item(
                player, skill_name, 1, silent=True
            )
            if store_success:
                storage_msg = "\n已存入储物戒"
            else:
                storage_msg = f"\n存入储物戒失败：{store_msg}"
            yield event.plain_result(f"✅ {message}{storage_msg}")
        else:
            yield event.plain_result(f"❌ {message}")

    @player_required
    async def handle_skill_info(self, player: Player, event: AstrMessageEvent, skill_name: str):
        """查看神通详情"""
        if not skill_name or skill_name.strip() == "":
            yield event.plain_result("请指定神通名称\n用法：/神通信息 神通名称")
            return

        skill_name = skill_name.strip()
        skill_data = self.config_manager.skills_data.get(skill_name)
        if not skill_data:
            yield event.plain_result(f"未找到神通：{skill_name}")
            return

        stype = skill_data.get("skill_type", 1)
        label = SKILL_TYPE_DESC.get(stype, "未知")

        lines = [
            f"✦ 神通信息",
            f"━━━━━━━━━━━━━━━",
            f"【{skill_name}】",
            f"  品阶：{skill_data.get('rank', '')}",
            f"  类型：{label}神通",
            f"  境界要求：Lv{skill_data.get('required_level_index', 0)}",
            f"  触发率：{skill_data.get('rate', 100)}%",
            f"  冷却：{skill_data.get('turncost', 0)} 回合",
        ]

        mp = skill_data.get("mpcost", 0)
        hp = skill_data.get("hpcost", 0)
        if mp > 0:
            lines.append(f"  MP消耗：{mp}")
        if hp > 0:
            lines.append(f"  HP消耗：{int(hp * 100)}%")

        if stype == 1:
            av = skill_data.get("atkvalue", [])
            if isinstance(av, list):
                lines.append(f"  段数：{len(av)}")
                lines.append(f"  伤害倍率：{av}")
                lines.append(f"  总倍率：{sum(av):.1f}")
        elif stype == 2:
            av = skill_data.get("atkvalue", 0)
            lines.append(f"  即时伤害倍率：{av}")
            lines.append(f"  持续伤害：{skill_data.get('turncost', 3)} 回合")
        elif stype == 3:
            bt = "攻击力" if skill_data.get("bufftype") == 1 else "防御力"
            bv = skill_data.get("buffvalue", 0)
            lines.append(f"  增益类型：{bt}")
            lines.append(f"  增益幅度：+{int(bv * 100)}%")
            lines.append(f"  持续时间：{skill_data.get('turncost', 3)} 回合")
        elif stype == 4:
            lines.append(f"  封禁回合：{skill_data.get('turncost', 2)}")
            lines.append(f"  成功率：{skill_data.get('success', 50)}%")

        lines.append(f"\n  {skill_data.get('desc', '')}")
        lines.append("━━━━━━━━━━━━━━━")
        yield event.plain_result("\n".join(lines))
