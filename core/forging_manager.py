# core/forging_manager.py
"""
锻造系统管理器 — 配方匹配、品质roll、属性计算、实例创建、分解回收
"""
import random
import uuid
from typing import Tuple, List, Dict, Optional, TYPE_CHECKING

from ..models import Player

if TYPE_CHECKING:
    from ..data.data_manager import DataBase
    from ..data.database_extended import DatabaseExtended
    from ..config_manager import ConfigManager
    from .storage_ring_manager import StorageRingManager

# ── 品质倍率 ──

QUALITY_MULT: Dict[str, float] = {
    "下品": 0.85,
    "中品": 1.0,
    "上品": 1.2,
    "极品": 1.5,
}

# ── 品质对应词条数范围 (min, max) ──

QUALITY_AFFIX_COUNT: Dict[str, Tuple[int, int]] = {
    "下品": (0, 0),
    "中品": (1, 1),
    "上品": (2, 3),
    "极品": (3, 4),
}

# ── 随机词条池（v3 区间模板：每条词条按品质带权在 [min, max] 内 roll） ──
# 设计文档：词条随机化设计方案 v3（实战校准版）
# 锚点为战斗影响：极品套装 ≈ +35% 伤害增幅、毕业 ≈ +50%、天成全套 ≈ +65~77%

FORGE_AFFIXES: List[dict] = [
    {"name": "嗜血", "attr": "lifesteal", "min": 1.0, "max": 12.0},
    {"name": "破甲", "attr": "armor_pen", "min": 2.0, "max": 12.0},
    {"name": "连击", "attr": "double_hit", "min": 1.0, "max": 18.0},
    {"name": "精准", "attr": "crit_rate", "min": 1.0, "max": 12.0},
    {"name": "铁壁", "attr": "def_buff", "min": 0.01, "max": 0.10},
    {"name": "闪避", "attr": "dodge_rate", "min": 1.0, "max": 12.0},
    {"name": "暴伤", "attr": "crit_damage", "min": 0.02, "max": 0.40},
    # 回春：战斗端按百分比数值使用（每回合回复 max_hp × val/100），val=2 即每回合 2%
    {"name": "回春", "attr": "hp_regen_pct", "min": 0.5, "max": 6.0},
]

# ── 词条 roll 机制（v3） ──

# 品质带权：品质决定 roll 落在区间标尺的哪一段（0~1），相邻带重叠防断崖
QUALITY_AFFIX_BANDS: Dict[str, Tuple[float, float]] = {
    "中品": (0.00, 0.45),
    "上品": (0.20, 0.75),
    "极品": (0.55, 1.00),
}
# 下品不出词条（QUALITY_AFFIX_COUNT 为 0），无对应带

# 天成概率：单条词条独立判定，直接突破数值表上限
PERFECT_CHANCE: float = 0.04
PERFECT_OVERCAP: float = 1.15  # 天成数值 = max × 1.15

# 三角分布众数位置（区间下段 40% 处）：中庸为主、高 roll 稀缺
BAND_MODE_FRAC: float = 0.4

# ── 武器评分（双分数架构：词条评分 + 威力倍率，配套词条随机化 v3） ──
# 设计文档：武器评分系统设计（评级阈值经 15 万场 roll 模拟锚定）

# 旧格式固定值词条表（v3 上线前的存量数据），按 LEGACY_AFFIX_T 计入评分
LEGACY_AFFIX_VALS: Dict[str, float] = {
    "lifesteal": 3,
    "armor_pen": 5,
    "double_hit": 4,
    "crit_rate": 3,
    "def_buff": 0.03,
    "dodge_rate": 3,
    "crit_damage": 0.1,
    "hp_regen_pct": 2,
}
# 旧固定值 = 随机化前的期望锚点，对应 v3 标尺的上品期望位置 0.45
LEGACY_AFFIX_T: float = 0.45

# 评级分档（锚点：中品 P50=32 → C/D 分界 30；极品 P50=71 → A 档 70；
# 毕业 90 → S 档 85；SS≥100 仅天成可达——单条满 roll 上限 100、天成 115）
SCORE_GRADES: List[Tuple[float, str]] = [
    (100.0, "SS"),
    (85.0, "S"),
    (70.0, "A"),
    (55.0, "B"),
    (30.0, "C"),
]

# 威力倍率折算系数（复用战斗公式既有常数，零新增 magic number）：
# 连击 0.5 = execute_attack 连击伤害减半；破甲 0.85 = 减伤公式中装备防御层占比折算
POWER_DBL_FRAC: float = 0.5
POWER_PEN_FRAC: float = 0.85

# 词条模板索引（attr → 区间模板），供评分标尺定位
AFFIX_TPL_BY_ATTR: Dict[str, dict] = {t["attr"]: t for t in FORGE_AFFIXES}

# ── 品质概率档位（按锻造等级分段） ──

QUALITY_RATES_TIERS: List[Tuple[int, Dict[str, float]]] = [
    (1,  {"下品": 0.40, "中品": 0.35, "上品": 0.20, "极品": 0.05}),
    (11, {"下品": 0.30, "中品": 0.35, "上品": 0.25, "极品": 0.10}),
    (21, {"下品": 0.25, "中品": 0.30, "上品": 0.30, "极品": 0.15}),
    (31, {"下品": 0.20, "中品": 0.30, "上品": 0.30, "极品": 0.20}),
    (41, {"下品": 0.15, "中品": 0.25, "上品": 0.30, "极品": 0.30}),
    (51, {"下品": 0.10, "中品": 0.20, "上品": 0.30, "极品": 0.40}),
]

# ── 分解回收率 ──

DECOMPOSE_RATES: Dict[str, float] = {
    "下品": 0.25,
    "中品": 0.30,
    "上品": 0.40,
    "极品": 0.50,
}


class ForgingManager:
    """锻造系统管理器"""

    def __init__(
        self,
        db: "DataBase",
        db_extended: "DatabaseExtended",
        config_manager: "ConfigManager",
        storage_ring_manager: "StorageRingManager",
    ):
        self.db = db
        self.db_extended = db_extended
        self.config_manager = config_manager
        self.storage_ring_manager = storage_ring_manager

    # ── Recipe access ──

    def _get_recipes(self) -> Dict[str, dict]:
        """获取全部锻造配方"""
        if self.config_manager:
            return self.config_manager.forging_recipes
        return {}

    # ── Instance ID ──

    def _generate_instance_id(self) -> str:
        """生成唯一武器/防具实例 ID"""
        return f"forge_{uuid.uuid4().hex[:16]}"

    # ── Quality system ──

    def _get_quality_rates_for_level(self, forging_level: int) -> Dict[str, float]:
        """根据锻造等级获取品级概率分布"""
        result = QUALITY_RATES_TIERS[-1][1]  # 默认最高档
        for threshold, rates in reversed(QUALITY_RATES_TIERS):
            if forging_level >= threshold:
                result = rates
                break
        return result

    def _roll_quality(self, forging_level: int) -> Tuple[str, float]:
        """基于锻造等级加权随机品质"""
        quality_rates = self._get_quality_rates_for_level(forging_level)
        qualities = list(quality_rates.keys())
        weights = list(quality_rates.values())
        quality = random.choices(qualities, weights=weights, k=1)[0]
        return quality, QUALITY_MULT.get(quality, 1.0)

    # ── Affix system ──

    def _roll_affixes(self, quality: str) -> List[dict]:
        """根据品级随机生成词条（不重复抽池 + 带权区间 roll + 天成判定）

        Returns:
            词条实例列表，落库格式：
            {"name": "精准", "attr": "crit_rate", "val": 13.8, "perfect": True}
            （val 为浮点；天成词条携带 perfect 标记且 val = max × PERFECT_OVERCAP；
            旧版固定值词条仅有 name/attr/val，读取端天然兼容）
        """
        min_count, max_count = QUALITY_AFFIX_COUNT.get(quality, (0, 0))
        count = random.randint(min_count, max_count)
        if count <= 0:
            return []
        band = QUALITY_AFFIX_BANDS.get(quality)
        pool = list(FORGE_AFFIXES)
        random.shuffle(pool)
        chosen = pool[:count]
        affixes: List[dict] = []
        for tpl in chosen:
            affixes.append(self._roll_affix_value(tpl, band))
        return affixes

    @staticmethod
    def _roll_affix_value(tpl: dict, band: Optional[Tuple[float, float]]) -> dict:
        """对单条词条模板 roll 数值（三角分布 + 品质带截断 + 天成）"""
        name = tpl["name"]
        attr = tpl["attr"]
        lo = float(tpl["min"])
        hi = float(tpl["max"])
        if band is not None:
            blo, bhi = band
        else:
            blo, bhi = 0.0, 1.0
        if random.random() < PERFECT_CHANCE:
            # 天成：突破数值表上限，携带 perfect 标记
            return {"name": name, "attr": attr, "val": round(hi * PERFECT_OVERCAP, 4), "perfect": True}
        mode = lo + BAND_MODE_FRAC * (hi - lo)
        val = None
        for _ in range(64):
            x = random.triangular(lo, hi, mode)
            if blo <= (x - lo) / (hi - lo) <= bhi:
                val = x
                break
        if val is None:
            # 极端兜底：取品质带内偏中位置
            val = lo + (blo + 0.3 * (bhi - blo)) * (hi - lo)
        # 保留 4 位小数，避免浮点长尾入库
        return {"name": name, "attr": attr, "val": round(val, 4)}

    @staticmethod
    def format_affix_val(attr: str, val: float) -> str:
        """单位感知的词条数值格式化（展示层统一入口）

        - def_buff：内部小数 → 百分比减伤（0.03 → "+3%减伤"）
        - crit_damage：会心伤害倍率增量（0.15 → "会伤+0.15"）
        - 其余：均为百分比数值（3 → "+3%"；2 → "+2%"）
        """
        if attr == "def_buff":
            return f"+{val * 100:g}%减伤"
        if attr == "crit_damage":
            return f"会伤+{val:g}"
        return f"+{val:g}%"

    # ── Weapon scoring（双分数：词条评分 + 威力倍率） ──

    @staticmethod
    def _parse_affixes_field(raw) -> List[dict]:
        """实例 affixes 字段解析（兼容 JSON 字符串 / 列表 / 脏数据）"""
        if isinstance(raw, str):
            try:
                import json as _j
                parsed = _j.loads(raw)
                return parsed if isinstance(parsed, list) else []
            except (ValueError, TypeError):
                return []
        return raw if isinstance(raw, list) else []

    @staticmethod
    def _affix_t(affix: dict) -> float:
        """单条词条在 v3 区间标尺上的位置（0~1，天成 1.15，旧格式 0.45）"""
        if affix.get("perfect"):
            return PERFECT_OVERCAP
        attr = affix.get("attr", "")
        tpl = AFFIX_TPL_BY_ATTR.get(attr)
        val = float(affix.get("val", 0) or 0)
        if tpl is None or val == LEGACY_AFFIX_VALS.get(attr):
            # 未知属性 / 旧格式固定值：按随机化前期望锚点 0.45 计入
            return LEGACY_AFFIX_T
        lo, hi = float(tpl["min"]), float(tpl["max"])
        t = (val - lo) / (hi - lo)
        # 脏数据 clamp：val 超出合理范围时不崩溃，异常高值最多视作天成位
        return max(0.0, min(PERFECT_OVERCAP, t))

    @staticmethod
    def grade_of(score: float) -> str:
        """词条评分 → 评级（阈值经 15 万场 roll 模拟锚定）"""
        for threshold, grade in SCORE_GRADES:
            if score >= threshold:
                return grade
        return "D"

    @staticmethod
    def score_instance(inst: dict) -> dict:
        """武器/防具实例双分数评分（设计文档：武器评分系统设计）

        - 词条评分 roll_score：100 × mean(t_i)，t_i 为词条在区间标尺上的
          位置（等权、只衡量 roll 质量）；无词条为 None
        - 威力倍率 power_mult：白板持有者（暴击 0 / 无其他加成）装备该件后
          的输出乘数 × 生存乘数，系数全部复用官方战斗公式
        - grade：D/C/B/A/S/SS 分档；无词条为 None

        Returns:
            {"roll_score", "grade", "power_mult", "breakdown"}
            breakdown.affixes: 每条词条的 t 值明细（/武器评分 详情用）
            breakdown.power:  atk/crit/dbl/pen + def/dodge/regen/steal 乘数及 A/D
        """
        inst = inst or {}
        affixes = ForgingManager._parse_affixes_field(inst.get("affixes", "[]"))

        # ── 词条评分：标尺位置等权均值 ──
        affix_bd: List[dict] = []
        if affixes:
            ts = []
            for a in affixes:
                t = ForgingManager._affix_t(a)
                ts.append(t)
                affix_bd.append({
                    "name": a.get("name", "?"),
                    "attr": a.get("attr", ""),
                    "val": float(a.get("val", 0) or 0),
                    "perfect": bool(a.get("perfect")),
                    "t": t,
                })
            roll_score = int(round(100 * sum(ts) / len(ts)))
            grade = ForgingManager.grade_of(roll_score)
        else:
            roll_score = None
            grade = None

        # ── 威力倍率：模板属性 + 词条代入官方乘数链 ──
        def _total(field: str, attr: str) -> float:
            base = float(inst.get(field, 0) or 0)
            extra = sum(
                float(a.get("val", 0) or 0)
                for a in affixes if a.get("attr") == attr
            )
            return base + extra

        atk = float(inst.get("atk_bonus", 0) or 0)
        crit_rate = _total("crit_rate", "crit_rate")
        crit_damage = _total("crit_damage", "crit_damage")
        double_hit = _total("double_hit", "double_hit")
        armor_pen = _total("armor_pen", "armor_pen")
        # 战斗端武器 damage_reduction 并入 def_buff（load_equipment_bonus 同口径）
        def_buff = _total("def_buff", "def_buff") + float(inst.get("damage_reduction", 0) or 0)
        dodge = _total("dodge_rate", "dodge_rate")
        hp_regen = _total("hp_regen_pct", "hp_regen_pct")
        lifesteal = _total("lifesteal", "lifesteal")

        atk_part = 1 + atk
        crit_part = 1 + min(crit_rate, 100.0) / 100.0 * max(0.0, crit_damage)
        dbl_part = 1 + min(double_hit, 100.0) / 100.0 * POWER_DBL_FRAC
        pen_part = 1 + armor_pen * POWER_PEN_FRAC / 100.0
        atk_mult = atk_part * crit_part * dbl_part * pen_part
        def_mult = (
            (1 + def_buff)
            * 100.0 / (100.0 - min(dodge, 95.0))
            * (1 + hp_regen / 100.0)
            * (1 + lifesteal / 100.0)
        )

        return {
            "roll_score": roll_score,
            "grade": grade,
            "power_mult": atk_mult * def_mult,
            "breakdown": {
                "affixes": affix_bd,
                "power": {
                    "atk": atk_part, "crit": crit_part,
                    "dbl": dbl_part, "pen": pen_part,
                    "def": 1 + def_buff,
                    "dodge": 100.0 / (100.0 - min(dodge, 95.0)),
                    "regen": 1 + hp_regen / 100.0,
                    "steal": 1 + lifesteal / 100.0,
                    "A": atk_mult, "D": def_mult,
                },
            },
        }

    # ── Stats calculation ──

    @staticmethod
    def _calc_instance_stats(template: dict, quality_mult: float) -> dict:
        """计算实例属性（模板属性 × 品级倍率）"""
        stats = {}
        fields = {
            "atk_bonus": float,
            "crit_rate": int,
            "crit_damage": float,
            "armor_pen": int,
            "lifesteal": int,
            "double_hit": int,
            "damage_reduction": float,
            "mp_bonus": float,
            "def_buff": float,
            "dodge_rate": int,
            "crit_resist": int,
            "reflect_pct": int,
            "block_value": int,
            "hp_regen_pct": float,
        }
        for field, field_type in fields.items():
            base = template.get(field, 0)
            if field_type == int:
                stats[field] = round(base * quality_mult)
            else:
                stats[field] = base * quality_mult
        return stats

    # ── Core forge logic ──

    async def forge(
        self, player: Player, recipe_id: str, quantity: int = 1
    ) -> Tuple[bool, str]:
        """执行锻造

        Args:
            player: 玩家对象
            recipe_id: 配方 ID (如 "forge_001")
            quantity: 锻造次数 (1~10)

        Returns:
            (success, message)
        """
        if quantity < 1 or quantity > 10:
            return False, "❌ 每次锻造数量范围为 1~10"

        recipes = self._get_recipes()
        if recipe_id not in recipes:
            return False, f"❌ 未知配方：{recipe_id}"

        recipe = recipes[recipe_id]

        # 检查锻造等级（使用 forging_level，非 level_index）
        rank_required = recipe.get("rank_required", 1)
        if player.forging_level < rank_required:
            return False, (
                f"❌ 锻造等级不足！需要 Lv.{rank_required}"
                f"（当前 Lv.{player.forging_level}）"
            )

        # 检查配方所需输出模板是否存在
        output_template = recipe["output_template"]
        output_type = recipe.get("output_type", "weapon")
        template = self.config_manager.weapons_data.get(output_template)
        if not template:
            return False, f"❌ 装备模板「{output_template}」不存在"

        # 计算材料总需求
        ingredients = recipe.get("ingredients", {})
        total_ingredients: Dict[str, int] = {}
        for mat_name, mat_count in ingredients.items():
            total_ingredients[mat_name] = mat_count * quantity

        # 检查材料数量
        ring_items = player.get_storage_ring_items()
        for mat_name, total_need in total_ingredients.items():
            if ring_items.get(mat_name, 0) < total_need:
                return False, (
                    f"❌ {mat_name} 数量不足"
                    f"（需要 {total_need}，拥有 {ring_items.get(mat_name, 0)}）"
                )

        # 消耗材料（通过 StorageRingManager.discard_item）
        # NOTE: discard_item 和 create_weapon_instance 各自有独立事务，
        # 目前无跨方法事务支持。材料检查在消耗前已通过，如果 create_weapon_instance 异常退出，
        # 已消耗的材料可能无法自动回滚（需要 GM 补偿）。
        for mat_name, total_need in total_ingredients.items():
            success, msg = await self.storage_ring_manager.discard_item(
                player, mat_name, total_need
            )
            if not success:
                return False, f"❌ {mat_name} 消耗失败：{msg}"

        # 获取等级对应的品质概率
        quality_rates = self._get_quality_rates_for_level(player.forging_level)

        # 批量锻造
        total_exp = 0
        result_lines = []

        for i in range(quantity):
            quality, quality_mult = self._roll_quality(player.forging_level)
            affixes = self._roll_affixes(quality)
            stats = self._calc_instance_stats(template, quality_mult)

            instance_id = self._generate_instance_id()
            forge_exp = recipe.get("forge_exp", 10)

            data = {
                "instance_id": instance_id,
                "template_name": output_template,
                "item_type": output_type,
                "quality": quality,
                "quality_mult": quality_mult,
                "enhance_level": 0,
                "affixes": affixes,
                "source_recipe": recipe_id,
                **stats,
            }
            await self.db_extended.create_weapon_instance(player.user_id, data)

            # 单次结果行（v3：词条名 + 数值 + 天成高光；双分数：评分 74（A））
            if affixes:
                affix_parts = []
                for a in affixes:
                    part = f"{a['name']}{self.format_affix_val(a['attr'], a['val'])}"
                    if a.get("perfect"):
                        part = f"✨{part}（天成）"
                    affix_parts.append(part)
                affix_str = f" 词条: {' '.join(affix_parts)}"
                score_info = self.score_instance(data)
                score_str = f" 评分 {score_info['roll_score']}（{score_info['grade']}）"
            else:
                affix_str = ""
                score_str = ""
            result_lines.append(f"  🔸 {output_template}·{quality}{score_str}{affix_str}")

            total_exp += forge_exp

        # 累计锻造经验并处理升级
        player.forging_exp += total_exp
        while player.forging_level > 0 and player.forging_exp >= player.forging_level * 30:
            player.forging_exp -= player.forging_level * 30
            player.forging_level += 1

        await self.db.update_player(player)

        # 构建消息
        lines = [
            "🔨 锻造成功！",
            "━━━━━━━━━━━━━━━",
            f"配方：{recipe.get('name', '?')}",
        ]
        lines.extend(result_lines)
        lines.append("━━━━━━━━━━━━━━━")
        lines.append(f"锻造经验：+{total_exp}")
        lines.append(
            f"锻造等级：Lv.{player.forging_level}"
            f"（{player.forging_exp}/{player.forging_level * 30}）"
        )
        lines.append("💡 使用 /武器列表 查看锻造品，/装备 <ID> 装备")

        return True, "\n".join(lines)

    # ── Forgeable recipe listing ──

    async def get_forgeable_recipes(self, player: Player) -> List[dict]:
        """获取玩家可锻造的配方列表（按等级排序）"""
        result = []
        for rid, recipe in self._get_recipes().items():
            rank_required = recipe.get("rank_required", 1)
            unlocked = player.forging_level >= rank_required
            result.append({
                "id": rid,
                "name": recipe.get("name", "?"),
                "rank_required": rank_required,
                "unlocked": unlocked,
                "ingredients": recipe.get("ingredients", {}),
                "output_template": recipe.get("output_template", ""),
                "output_type": recipe.get("output_type", "weapon"),
                "forge_exp": recipe.get("forge_exp", 10),
            })
        result.sort(key=lambda r: r["rank_required"])
        return result

    # ── Fusion ──

    async def fuse(self, player: Player, id1: str, id2: str) -> Tuple[bool, str]:
        """融合原罪+无罪→天罪

        消耗两把残缺神器，按最高品质产出天罪，继承双方词条（去重取高值）。
        """
        inst1 = await self.db_extended.get_weapon_instance(id1)
        inst2 = await self.db_extended.get_weapon_instance(id2)

        if not inst1 or not inst2:
            return False, "❌ 武器实例不存在"
        if inst1["user_id"] != player.user_id or inst2["user_id"] != player.user_id:
            return False, "❌ 这不是你的武器"
        if inst1.get("is_equipped") or inst2.get("is_equipped"):
            return False, "❌ 请先卸下装备再融合"

        # 验证配方来源：原罪（残缺）+ 无罪（残缺）
        # NOTE: 实例的 source_recipe 存的是配方 name（config_manager._load_items_data 会把
        # dict 型配方的 key 从 forge_053a/forge_053b 替换为 name），因此不能用 ID 常量校验；
        # 改用 template_name 判断，与实例落库值和展示名一致，对存量数据同样有效。
        if not ({inst1["template_name"], inst2["template_name"]}
                == {"原罪（残缺）", "无罪（残缺）"}):
            return False, "❌ 融合需要一把「原罪（残缺）」和一把「无罪（残缺）」"

        # 品质取最高
        QUAL_ORDER = ["下品", "中品", "上品", "极品"]
        q1 = inst1.get("quality", "下品")
        q2 = inst2.get("quality", "下品")
        best_quality = q1 if QUAL_ORDER.index(q1) >= QUAL_ORDER.index(q2) else q2
        best_qmult = QUALITY_MULT.get(best_quality, 1.5)

        # 词条继承：合并两把的词条，按 attr 去重取高值
        def _parse_affixes(inst):
            raw = inst.get("affixes", "[]")
            if isinstance(raw, str):
                try:
                    import json as _j
                    return _j.loads(raw)
                except Exception:
                    return []
            return raw if isinstance(raw, list) else []

        affix1 = _parse_affixes(inst1)
        affix2 = _parse_affixes(inst2)
        merged = {}
        for a in affix1 + affix2:
            attr = a.get("attr", "")
            if attr and (attr not in merged or a.get("val", 0) > merged[attr]["val"]):
                merged[attr] = a
        inherited = list(merged.values())

        # 从天罪模板读取属性
        template = self.config_manager.weapons_data.get("天罪")
        if not template:
            return False, "❌ 装备模板「天罪」不存在"

        instance_id = self._generate_instance_id()
        stats = self._calc_instance_stats(template, best_qmult)
        data = {
            "instance_id": instance_id,
            "template_name": "天罪",
            "item_type": "weapon",
            "quality": best_quality,
            "quality_mult": best_qmult,
            "enhance_level": 0,
            "affixes": inherited,
            "source_recipe": "forge_053_fusion",
            **stats,
        }
        await self.db_extended.create_weapon_instance(player.user_id, data)

        # 删除两把来源武器
        await self.db_extended.delete_weapon_instance(player.user_id, id1)
        await self.db_extended.delete_weapon_instance(player.user_id, id2)

        # 继承词条播报（v3：带数值展示，天成词条保留高光标记）
        if inherited:
            inherit_parts = []
            for a in inherited:
                part = f"{a['name']}{self.format_affix_val(a['attr'], a['val'])}"
                if a.get("perfect"):
                    part = f"✨{part}（天成）"
                inherit_parts.append(part)
            affix_str = "词条: " + " ".join(inherit_parts)
        else:
            affix_str = "无词条"

        # 评分播报：继承后总分 + 融合前后对比（SS 低威力=融合神材料的引导信号）
        new_score = self.score_instance(data)
        before_scores = [
            s["roll_score"]
            for s in (self.score_instance(inst1), self.score_instance(inst2))
            if s["roll_score"] is not None
        ]
        if new_score["roll_score"] is not None:
            score_line = (
                f"评分：{new_score['roll_score']}（{new_score['grade']}）"
                f"　威力 ×{new_score['power_mult']:.2f}"
            )
            if before_scores:
                score_line += f"（融合前 {'/'.join(str(b) for b in before_scores)}）"
        else:
            score_line = f"评分：无词条　威力 ×{new_score['power_mult']:.2f}"

        lines = [
            "✨ 融合成功！",
            "━━━━━━━━━━━━━━━",
            f"原罪（{q1}）+ 无罪（{q2}）→ 天罪（{best_quality}）",
            f"属性：ATK+{stats.get('atk_bonus', 0)*100:.0f}% 暴击+{stats.get('crit_rate', 0)}%",
            f"继承：{affix_str}",
            score_line,
            "━━━━━━━━━━━━━━━",
            "💡 使用 /装备 <序号> 装备天罪",
        ]
        return True, "\n".join(lines)

    async def decompose(self, player: Player, instance_id: str) -> Tuple[bool, str]:
        """分解武器/防具实例，回收部分材料到储物戒"""
        inst = await self.db_extended.get_weapon_instance(instance_id)
        if not inst:
            return False, f"❌ 武器实例 {instance_id} 不存在"
        if inst["user_id"] != player.user_id:
            return False, "❌ 这不是你的武器"
        if inst.get("is_equipped"):
            return False, "❌ 请先卸下装备再分解"

        template_name = inst["template_name"]
        source_recipe = inst.get("source_recipe", "")

        # 查找配方（优先用 source_recipe，再按模板名匹配）
        recipe = None
        if source_recipe:
            recipe = self._get_recipes().get(source_recipe)
        if not recipe:
            for rcp in self._get_recipes().values():
                if rcp.get("output_template") == template_name:
                    recipe = rcp
                    break

        if not recipe:
            return False, f"❌ 无法确定 {template_name} 的配方，分解失败"

        quality = inst.get("quality", "下品")
        rate = DECOMPOSE_RATES.get(quality, 0.3)
        ingredients = recipe.get("ingredients", {})

        returns = []
        for mat_name, mat_count in ingredients.items():
            refund = max(1, int(mat_count * rate))
            if refund > 0:
                ok, store_msg = await self.storage_ring_manager.store_item(
                    player, mat_name, refund, silent=True
                )
                if ok:
                    returns.append(f"{mat_name}×{refund}")
                else:
                    # 储物戒满时跳过该材料但继续处理其他（实例已标记删除不可回滚）
                    returns.append(f"{mat_name}×{refund}⚠️")

        await self.db_extended.delete_weapon_instance(player.user_id, instance_id)

        lines = [
            "🔨 分解成功！",
            "━━━━━━━━━━━━━━━",
            f"分解：{template_name}·{quality}",
        ]
        if returns:
            lines.append(f"回收：{' '.join(returns)}")
        else:
            lines.append("未回收任何材料")

        return True, "\n".join(lines)
