"""融合系统回归测试：原罪（残缺）+ 无罪（残缺）→ 天罪

背景 Bug：config_manager._load_items_data 加载 dict 型 forging_recipes.json 时，
会把 key（forge_053a/forge_053b）替换为配方 name（"原罪"/"无罪"），导致 forge()
写入实例的 source_recipe 是配方名。fuse() 曾用 ID 常量 {"forge_053a","forge_053b"}
校验 → 恒失败。修复后改用 template_name 判断。本测试防止该问题回归。
"""
import json
from pathlib import Path

from astrbot_plugin_monixiuxian2.config_manager import ConfigManager
from astrbot_plugin_monixiuxian2.models import Player
from astrbot_plugin_monixiuxian2.core.forging_manager import ForgingManager

_PLUGIN_DIR = Path(__file__).resolve().parent.parent

QUAL_ORDER = ["下品", "中品", "上品", "极品"]
QUAL_MULT = {"下品": 0.85, "中品": 1.0, "上品": 1.2, "极品": 1.5}


# ── 内存桩：语义复刻 weapon_instances 表与储物戒扣减 ──

class _StubRing:
    async def discard_item(self, player, item_name, count):
        items = player.get_storage_ring_items()
        if item_name not in items or items[item_name] < count:
            return False, "数量不足"
        rest = items[item_name] - count
        if rest <= 0:
            items.pop(item_name, None)
        else:
            items[item_name] = rest
        player.set_storage_ring_items(items)
        return True, ""


class _StubDbExt:
    def __init__(self):
        self.instances = {}

    async def create_weapon_instance(self, user_id, data):
        d = dict(data)
        d["user_id"] = user_id  # DB 独立列
        d["affixes"] = json.dumps(d.get("affixes", []), ensure_ascii=False)  # DB TEXT
        d["is_equipped"] = 0
        d["in_storage"] = 1
        self.instances[data["instance_id"]] = d
        return data["instance_id"]

    async def get_weapon_instance(self, instance_id):
        v = self.instances.get(instance_id)
        return dict(v) if v else None

    async def delete_weapon_instance(self, user_id, instance_id):
        self.instances.pop(instance_id, None)
        return True


class _StubDb:
    async def update_player(self, player):
        pass


def _make_player():
    p = Player(user_id="tester", user_name="测试道人")
    p.forging_level = 55
    p.set_storage_ring_items({
        "精铁": 40, "龙骨髓": 7, "星辉晶砂": 14, "赤炎石": 5, "混沌源石": 3,
        "亡者之息": 8, "幽魂草": 8, "魔核碎片": 5, "九幽寒铁": 3,
        "百年灵草": 15, "月光粉尘": 6, "玄冰之核": 3, "妖丹": 1,
    })
    return p


def _make_mgr():
    cm = ConfigManager(_PLUGIN_DIR)
    dbe = _StubDbExt()
    mgr = ForgingManager(_StubDb(), dbe, cm, _StubRing())

    def resolve(name):
        for rid, rcp in cm.forging_recipes.items():
            if rcp.get("name") == name or rid == name:
                return rid
        return None

    return cm, dbe, mgr, resolve


async def _forge(mgr, p, resolve, name):
    ok, msg = await mgr.forge(p, resolve(name), 1)
    assert ok, f"锻造 {name} 失败：{msg}"
    iid = [i for i, v in mgr.db_extended.instances.items()
           if v["template_name"].startswith(name)][-1]
    return iid, mgr.db_extended.instances[iid]


async def test_fuse_sin_plus_innocence_produces_tianzui():
    """原罪+无罪 → 融合成功：品质取最高、属性=天罪模板×最高倍率、来源删除。"""
    cm, dbe, mgr, resolve = _make_mgr()
    p = _make_player()

    id_yz, inst_yz = await _forge(mgr, p, resolve, "原罪")
    id_wz, inst_wz = await _forge(mgr, p, resolve, "无罪")
    affix_yz = json.loads(inst_yz["affixes"])
    affix_wz = json.loads(inst_wz["affixes"])

    ok, msg = await mgr.fuse(p, id_yz, id_wz)
    assert ok, f"融合失败：{msg}"  # 修复前此处恒返回 "❌ 融合需要一把…"
    assert "天罪" in msg

    tz = [v for v in dbe.instances.values() if v["template_name"] == "天罪"]
    assert len(tz) == 1
    tz = tz[-1]

    # 品质取两把中最高
    best_q = max(inst_yz["quality"], inst_wz["quality"], key=QUAL_ORDER.index)
    assert tz["quality"] == best_q
    assert tz["source_recipe"] == "forge_053_fusion"

    # 属性 = 天罪模板 × 最高品质倍率
    template = cm.weapons_data["天罪"]
    mult = QUAL_MULT[best_q]
    assert abs(tz["atk_bonus"] - template["atk_bonus"] * mult) < 1e-9
    assert tz["crit_rate"] == round(template["crit_rate"] * mult)

    # 来源两把已被删除
    assert id_yz not in dbe.instances and id_wz not in dbe.instances

    # 词条继承：为两把来源词条的并集，同 attr 取高值
    expected = {}
    for a in affix_yz + affix_wz:
        attr = a["attr"]
        if attr not in expected or a["val"] > expected[attr]["val"]:
            expected[attr] = a
    inherited = {a["attr"]: a for a in json.loads(tz["affixes"])}
    assert inherited == expected


async def test_fuse_rejects_wrong_pair():
    """非 原罪+无罪 组合必须被拒绝（防回归：修复不能放宽校验）。"""
    cm, dbe, mgr, resolve = _make_mgr()
    p = _make_player()
    id_yz, _ = await _forge(mgr, p, resolve, "原罪")
    id_other, _ = await _forge(mgr, p, resolve, "誓约胜利之剑")

    ok, msg = await mgr.fuse(p, id_yz, id_other)
    assert not ok
    assert "残缺" in msg
