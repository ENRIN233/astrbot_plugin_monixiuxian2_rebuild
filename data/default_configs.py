# data/default_configs.py

SECT_CONFIG = {
    "create_cost": 10000,
    "create_level_required": 3, # 筑基
    "positions": {
        "0": {"name": "宗主", "permission": 10},
        "1": {"name": "长老", "permission": 8},
        "2": {"name": "亲传弟子", "permission": 5},
        "3": {"name": "内门弟子", "permission": 2},
        "4": {"name": "外门弟子", "permission": 1}
    },
    "scale_ratio": 10, # 1灵石 = 10建设度
    # 攻击修炼配置
    "practice": {
        "base_cost": 500000,           # 1级灵石成本（50万起步）
        "cost_growth": 1.22,           # 每级成本增长系数（满50级总成本约21亿）
        "atk_per_level": 0.04,         # 每级攻击力提升百分比
        "max_level": 50,               # 最大修炼等级
        "construction_per_level": 10000 # 每级所需宗门建设度上限（25级需25万建设度）
    },
    # 丹房配置
    "elixir_room": {
        "claim_contribution_required": 500,  # 领取丹药最低贡献
        "levels": {
            "1": {"name": "黄级丹房", "upgrade_cost_scale": 100000,  "upgrade_cost_stone": 500000,
                   "daily_pills": 1, "pill_rank_max": 1},
            "2": {"name": "玄级丹房", "upgrade_cost_scale": 250000, "upgrade_cost_stone": 1000000,
                   "daily_pills": 2, "pill_rank_max": 2},
            "3": {"name": "地级丹房", "upgrade_cost_scale": 500000, "upgrade_cost_stone": 2500000,
                   "daily_pills": 3, "pill_rank_max": 3},
            "4": {"name": "天级丹房", "upgrade_cost_scale": 1000000, "upgrade_cost_stone": 5000000,
                   "daily_pills": 4, "pill_rank_max": 4},
            "5": {"name": "仙级丹房", "upgrade_cost_scale": 2000000, "upgrade_cost_stone": 10000000,
                   "daily_pills": 5, "pill_rank_max": 5}
        },
        "maintenance_cost_per_level": 10000  # 每级每日维护费（资材），5级日耗5万
    },
    # 资材发放配置
    "material_distribution": {
        "hour": 12,       # 每日发放时间（小时）
        "rate": 0.1       # 倍率：建设度 * rate = 发放资材
    },
    # 自动换宗主配置
    "auto_owner_change": {
        "inactive_days": 7  # 宗主离线天数触发自动传位
    },
    # 宗门改名配置
    "rename": {
        "cost_contribution": 500  # 改名消耗贡献度
    }
}

BOSS_CONFIG = {
    "spawn_interval": 3600,
    "levels": [
        {"name": "练气", "level_index": 0,  "hp_mult": 1.0,  "atk_mult": 1.0,  "reward_mult": 1.0},
        {"name": "筑基", "level_index": 3,  "hp_mult": 1.5,  "atk_mult": 1.2,  "reward_mult": 1.5},
        {"name": "金丹", "level_index": 6,  "hp_mult": 2.0,  "atk_mult": 1.5,  "reward_mult": 2.0},
        {"name": "元婴", "level_index": 9,  "hp_mult": 2.5,  "atk_mult": 1.8,  "reward_mult": 2.5},
        {"name": "化神", "level_index": 12, "hp_mult": 3.0,  "atk_mult": 2.0,  "reward_mult": 3.0},
        {"name": "炼虚", "level_index": 15, "hp_mult": 4.0,  "atk_mult": 2.5,  "reward_mult": 4.0},
        {"name": "合体", "level_index": 18, "hp_mult": 5.0,  "atk_mult": 3.0,  "reward_mult": 5.0},
        {"name": "大乘", "level_index": 21, "hp_mult": 6.0,  "atk_mult": 3.5,  "reward_mult": 6.0},
        {"name": "神火", "level_index": 24, "hp_mult": 7.5,  "atk_mult": 4.0,  "reward_mult": 7.5},
        {"name": "真一", "level_index": 27, "hp_mult": 9.0,  "atk_mult": 4.5,  "reward_mult": 9.0},
        {"name": "圣祭", "level_index": 30, "hp_mult": 11.0, "atk_mult": 5.0,  "reward_mult": 11.0},
        {"name": "天神", "level_index": 33, "hp_mult": 13.0, "atk_mult": 5.5,  "reward_mult": 13.0},
        {"name": "虚道", "level_index": 36, "hp_mult": 16.0, "atk_mult": 6.0,  "reward_mult": 16.0},
        {"name": "斩我", "level_index": 39, "hp_mult": 19.0, "atk_mult": 7.0,  "reward_mult": 19.0},
        {"name": "混沌", "level_index": 42, "hp_mult": 23.0, "atk_mult": 8.0,  "reward_mult": 23.0},
        {"name": "创世", "level_index": 45, "hp_mult": 28.0, "atk_mult": 9.5,  "reward_mult": 28.0},
        {"name": "金仙", "level_index": 48, "hp_mult": 34.0, "atk_mult": 11.0, "reward_mult": 34.0},
        {"name": "轮回", "level_index": 51, "hp_mult": 41.0, "atk_mult": 13.0, "reward_mult": 41.0},
        {"name": "虚神", "level_index": 54, "hp_mult": 50.0, "atk_mult": 15.0, "reward_mult": 50.0},
        {"name": "仙帝", "level_index": 57, "hp_mult": 60.0, "atk_mult": 18.0, "reward_mult": 60.0},
    ]
}

RIFT_CONFIG = {
    "open_hour_start": 10,
    "open_hour_end": 21,
    "rifts": [
        {"id": 1, "name": "青云秘境", "duration": 1800, "spawn_weight": 30, "reward_stone": 800000, "reward_exp": 2200},
        {"id": 2, "name": "幽冥鬼域", "duration": 2700, "spawn_weight": 25, "reward_stone": 1440000, "reward_exp": 3840},
        {"id": 3, "name": "太古遗迹", "duration": 4500, "spawn_weight": 20, "reward_stone": 2320000, "reward_exp": 7800},
        {"id": 4, "name": "玄冰地宫", "duration": 3600, "spawn_weight": 15, "reward_stone": 3600000, "reward_exp": 14820},
        {"id": 5, "name": "上古遗迹", "duration": 5400, "spawn_weight": 10, "reward_stone": 3960000, "reward_exp": 16302},
    ]
}

ALCHEMY_CONFIG = {
    "recipes": {
        "1": {
            "name": "聚气丹",
            "level_required": 0,
            "materials": {"灵草": 3, "灵石": 100},
            "success_rate": 80,
            "effect": {"type": "exp", "value": 1000},
            "desc": "增加1000修为"
        },
        "2": {
            "name": "筑基丹",
            "level_required": 2,
            "materials": {"灵草": 5, "灵石": 500},
            "success_rate": 60,
            "effect": {"type": "exp", "value": 5000},
            "desc": "增加5000修为"
        },
        "3": {
            "name": "金丹",
            "level_required": 5,
            "materials": {"灵草": 10, "灵石": 2000},
            "success_rate": 40,
            "effect": {"type": "exp", "value": 20000},
            "desc": "增加20000修为"
        },
        "4": {
            "name": "回春丹",
            "level_required": 1,
            "materials": {"灵草": 2, "灵石": 200},
            "success_rate": 70,
            "effect": {"type": "hp_restore", "value": 50},
            "desc": "恢复50%气血"
        },
        "5": {
            "name": "聚灵丹",
            "level_required": 1,
            "materials": {"灵草": 2, "灵石": 200},
            "success_rate": 70,
            "effect": {"type": "mp_restore", "value": 50},
            "desc": "恢复50%真元"
        },
    }
}

DUNGEON_CONFIG = {
    "dungeons": [],
    "global": {
        "max_runs_per_day": -1,
        "run_expire_hours": 24,
        "overdraft_warning_pct": 0.5
    }
}
