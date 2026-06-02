# Plan: 更新帮助文本 + 网页指令 + 推送GitHub

## 差异分析

### misc_handler.py 帮助文本需要添加的指令

| 缺失指令 | 应添加位置 | 已注册 |
|----------|-----------|--------|
| `丹药信息 <名>` | 装备丹药 | CMD_PILL_INFO |
| `查看 <名称>` | 装备丹药 | CMD_VIEW_ITEM |
| `丢弃 <物品名>` | 储物戒 | CMD_DISCARD_ITEM |
| `炼金 <物品名> [数量]` | 储物戒 | inline "炼金" |
| `升级会员` | 银行 | CMD_UPGRADE_VIP |
| `宗门任务` | 宗门 | CMD_SECT_TASK |
| `踢出成员 <@某人>` | 宗门 | CMD_SECT_KICK |
| `宗主传位 <@某人>` | 宗门 | CMD_SECT_TRANSFER |
| `职位变更 <@某人> <职位>` | 宗门 | CMD_SECT_POSITION |
| `生成Boss` | 战斗竞技 | CMD_SPAWN_BOSS |
| 成就系统(3条) | 新增分类 | CMD_ACHIEVEMENT_LIST/EQUIP/UNEQUIP |
| GM指令(15条) | 新增分类 | CMD_GM_* + 禁用/启用 |

### docs/app.js 网页需要修改

| 变更 | 说明 |
|------|------|
| 移除 `存入`/`取出`/`取出所有` | 常量定义但未注册 @filter.command |
| 添加 `炼金`/`丢弃` | 到储物戒组 |
| 添加 `升级会员` | 到灵石银行组 |
| 新增成就系统组 | 3条指令 |
| 添加 `GM补偿` | 到管理员指令组 |
| 更新指令总数 | 121 → 实际数量 |

## 修改文件

1. `handlers/misc_handler.py` — 帮助文本
2. `docs/app.js` — 网页指令列表
3. `handlers/utils.py` — 不需改动（COMMAND_FOOTERS 已包含正确内容）

## 推送

git add → git commit → git push
