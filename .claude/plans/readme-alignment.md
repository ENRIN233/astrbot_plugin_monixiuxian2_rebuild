# Plan: README.md 全面对齐插件实际代码

## Context

当前 README.md 标注版本为 v3.2.1，但 metadata.yaml 和 misc_handler.py 均为 v4.0.0。此外，README 中缺少多个已在代码中实现的系统和指令，项目结构描述过时，配置文件说明不完整。需要将 README 严格对齐实际代码状态。

## 差异分析

### 1. 版本号不一致
- README: v3.2.1 → 实际: v4.0.0

### 2. README 缺少的指令系统（代码已实现）

| 缺失系统 | 指令 | 对应 handler |
|----------|------|-------------|
| 🔮 神通系统 | 神通列表/我的神通/装备神通/卸下神通/神通信息 | skill_handler.py |
| 🏆 成就系统 | 成就列表/装备成就/卸下成就 | achievement_handler.py |
| 🎁 GM补偿 | 补偿（玩家领取） | gm_handlers.py |
| 🔍 物品查看 | 查看 <名称> | shop_handler.py |
| 💊 丹药信息 | 丹药信息 | pill_handler.py |
| 🪙 炼金 | 炼金 <物品名> [数量] | storage_ring_handler.py |
| ❌ 丢弃 | 丢弃 | storage_ring_handler.py |
| 💎 升级会员 | 升级会员 | bank_handlers.py |
| 🔒 禁用/启用物品 | 禁用物品/启用物品/禁用列表 | main.py (admin) |
| 👑 生成Boss | 生成Boss | boss_handlers.py |

### 3. README 遗漏的宗门子指令
- 踢出成员
- 宗主传位
- 宗门任务
- 职位变更

### 4. GM指令不完整
README 缺少：`GM补偿`、`禁用物品`、`启用物品`、`禁用列表`

### 5. 灵田灵草数量
README 列出5种，实际代码有8种（+天山雪莲/太乙仙草/混沌神莲）

### 6. 后台任务数量
README 未提及后台任务，CLAUDE.md 说5个，实际 main.py 有8个

### 7. 项目结构描述过时
README 的目录树缺少 `core/`、`managers/`、`data/`、`utils/`、`tests/`、`scripts/`、`docs/` 等目录

### 8. 配置文件说明不完整
README 列出4个，实际有14+个 JSON 配置文件

### 9. 存入/取出/取出所有
代码中常量已定义但未注册 @filter.command，README 不应列出这些作为独立指令（`存入`已禁用，`取出`/`取出所有`未注册）

### 10. 丹药背包
已合并到储物戒显示（`handle_show_pills` 委托给 `storage_ring_handler.handle_storage_ring`）

## 实施步骤

### Step 1: 更新头部信息
- 版本号 v3.2.1 → v4.0.0
- 更新 latest changelog 为 v4.0.0 古风视觉重构

### Step 2: 补全特色功能表
- 新增神通系统、成就系统到独有系统表

### Step 3: 补全指令大全所有分类
按实际代码的 97 条指令，补全以下内容：
- 入门 & 基础：确认所有6条指令
- 装备丹药：新增 `丹药信息`、`查看`
- 神通系统：新增整个分类（5条指令）
- 商店系统：确认现有指令
- 储物戒：新增 `炼金`、`丢弃`，移除未注册的 `存入`/`取出`/`取出所有`
- 银行：新增 `升级会员`
- 宗门：补全 `踢出成员`/`宗主传位`/`宗门任务`/`职位变更`
- 战斗竞技：新增 `生成Boss`（管理员）
- 成就系统：新增整个分类（3条指令）
- GM指令：补全 `GM补偿`/`禁用物品`/`启用物品`/`禁用列表`
- 玩家指令：新增 `补偿`

### Step 4: 更新灵田灵草表
5种 → 8种，添加 天山雪莲/太乙仙草/混沌神莲

### Step 5: 更新配置说明
列出全部 14+ 个配置文件

### Step 6: 更新项目结构
反映实际四层架构：main.py → handlers/ → core/ + managers/ → data/

### Step 7: 新增后台任务说明
列出 8 个后台任务及其功能

### Step 8: 更新更新日志
保留现有历史日志，确保 v4.0.0 在最前面

## 关键文件

- `README.md` — 唯一需要修改的文件
- `metadata.yaml` — 版本参考 (v4.0.0)
- `main.py` — 指令注册权威来源 (97条)
- `handlers/misc_handler.py` — 帮助文本参考 (v4.0.0)
- `config/` — 配置文件列表参考

## 验证方式

1. 逐条比对 README 中列出的每条指令与 main.py 中 @filter.command 注册
2. 确认版本号与 metadata.yaml 一致
3. 确认配置文件列表与 config/ 目录实际文件一致
4. 确认项目结构与实际目录一致
