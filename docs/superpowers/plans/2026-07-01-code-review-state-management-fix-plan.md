# 状态管理与 @player_required 一致性修复方案

> **日期:** 2026-07-01  
> **来源:** 代码质量审查  
> **优先级:** P1 — 涉及游戏状态安全

---

## 1. 概述

当前项目存在**两层状态检查系统**：

1. `@player_required` 装饰器 (`handlers/utils.py:149-207`) — 检查 `user_cd.type != IDLE` + `player.state == "修炼中"` + 贷款状态
2. 各 handler 自行检查（部分只检查 `user_cd.type`，部分只检查 `player.state`，部分完全不检查）

**问题**: 10+ 个 handler 绕过 `@player_required` 装饰器，自行实现的检查不一致，导致状态绕过漏洞。同时 `_is_command_allowed` 用 `startswith` 匹配过于宽松。

---

## 2. 问题清单

### 2.1 绕过 @player_required 的 Handler

| Handler 文件 | 所有方法绕过 | 已检查 user_cd | 已检查 player.state | 检查贷款 |
|---|---|---|---|---|
| `rift_handlers.py` | ✅ 全部 | ❌ | ❌ | ❌ |
| `boss_handlers.py` | ✅ 全部 | ❌ | ❌ | ❌ |
| `dungeon_handlers.py` | ✅ 全部 | ❌ | ❌ | ❌ |
| `impart_handlers.py` | ✅ 全部 | ❌ | ❌ | ❌ |
| `combat_handlers.py` | ✅ 全部(注) | ✅ | ❌ | ❌ |
| `sect_handlers.py` | ✅ 多数 | ✅ | ❌ | ❌ |
| `ranking_handlers.py` | ✅ handle_rank_sect_contribution | ❌ | ❌ | ❌ |

> 注: combat_handlers 检查了 `user_cd.type` 但未检查 `player.state == "修炼中"`

### 2.2 命令匹配过于宽松 (🟡 MAJ-7)

`_is_command_allowed` 用 `startswith` 匹配命令名：
```python
for cmd in allowed_commands:
    if message_text.startswith(cmd):
        return True
```
"存入" → 匹配"存入所有""存入abc"。当前白名单无冲突，但未来添加短前缀时会有安全风险。

### 2.3 命令别名耦合 (🔴 CRIT-17)

`"卸下炼丹炉"` 注册为 `"装备炼丹炉"` 的别名，方法体内通过 `"卸下" in msg` 判断行为。框架可能剥离别名前缀导致行为错误。

### 2.4 Boss 挑战未设忙碌状态 (🟡 MAJ-4)

`challenge_boss` 检查了 `user_cd.type` 但从未将玩家设为忙碌，战斗期间可并发发起多次挑战。

---

## 3. 修复方案

### 3.1 统一状态检查层（Phase 1 — 架构改进）

**当前架构问题**: `@player_required` 装饰器工作量太大（同时检查 player 存在、状态、贷款、忙碌、修炼），导致许多 handler 选择绕过。

**方案**: 将 `@player_required` 拆分为**两层**：

```python
# handlers/utils.py

# 第一层：轻量级装饰器 — 仅检查 player 是否存在 + 加载 player 对象
def require_player(func):
    @wraps(func)
    async def wrapper(self, event, *args, **kwargs):
        player = await self.db.get_player_by_id(event.get_sender_id())
        if not player:
            yield event.plain_result(f"道友尚未踏入仙途，请发送「我要修仙」开启你的旅程。")
            return
        async for result in func(self, player, event, *args, **kwargs):
            yield result
    return wrapper


# 第二层：完整状态检查装饰器（在原 @player_required 基础上）
# 只用于需要防止忙碌/修炼状态的命令
def require_idle(func):
    @wraps(func)
    async def wrapper(self, player, event, *args, **kwargs):
        # 检查忙碌状态
        user_cd = await self.db.ext.get_user_cd(player.user_id)
        if user_cd and user_cd.type != UserStatus.IDLE:
            yield event.plain_result(f"道友当前正在「{UserStatus.get_name(user_cd.type)}」中...")
            return
        if player.state == "修炼中":
            yield event.plain_result(f"道友当前正在「修炼中」...")
            return
        async for result in func(self, player, event, *args, **kwargs):
            yield result
    return wrapper
```

用法变更：

```python
# 只读/浏览命令 — 仅需 @require_player
@require_player
async def handle_rank_list(self, player, event):
    ...

# 需要空闲状态的写操作 — 叠加 @require_player + @require_idle
@require_player
@require_idle  # 补充检查，防止忙碌状态修改数据
async def handle_start_cultivation(self, player, event):
    ...
```

### 3.2 绕过 handler 的适配（Phase 2 — 增量修复）

对绕过 `@player_required` 的 handler，根据操作类型分层采用：

| 当前绕过 | 适用装饰器 | 操作类型示例 |
|---|---|---|
| `boss_handlers.py` | `@require_player` + 战斗前手动 `set_user_busy` | 写操作（扣血、奖励） |
| `dungeon_handlers.py` | `@require_player` + `@require_idle` | 写操作（副本状态变更） |
| `rift_handlers.py` | `@require_player` + `@require_idle` | 写操作（探索结算） |
| `combat_handlers.py` | `@require_player` + 补充 `player.state` 检查 | 写操作（PVP HP 变更） |
| `sect_handlers.py` | `@require_player` + 读操作不加 `@require_idle`、写操作加 | 混合（列表只读 / 捐献写） |
| `impart_handlers.py` | `@require_player` | 读操作（信息查看） |
| `ranking_handlers.py` | `@require_player` | 读操作 |

### 3.3 _is_command_allowed 精确匹配（P1）

将 `startswith` 改为**前缀匹配 + 边界检查**：

```python
def _is_command_allowed(message_text: str, allowed_commands: list) -> bool:
    text = message_text.lstrip()
    for cmd in allowed_commands:
        if text == cmd or text.startswith(cmd + " "):
            return True
    return False
```

这样 `存入` 不再匹配 `存入所有`（因为 `存入所有` 以 `存入` 开头但下一个字符不是空格）。

### 3.4 命令别名分离（P1）

**问题**: `"装备炼丹炉"` 和 `"卸下炼丹炉"` 注册为别名，靠子串匹配区分。

**方案**: 拆分为两个独立的命令注册：

```python
# 注册
@filter.command("装备炼丹炉")
async def handle_equip_furnace(self, event, furnace_name=""):
    ...

@filter.command("卸下炼丹炉")
async def handle_unequip_furnace(self, event):
    ...
```

### 3.5 Boss 挑战忙碌状态 (P1)

在 `challenge_boss` 中加 `try/finally` 包裹：

```python
async def challenge_boss(self, player, event):
    await self.db.ext.set_user_busy(player.user_id, UserStatus.FIGHTING)
    try:
        # ... 战斗逻辑 ...
    finally:
        await self.db.ext.set_user_free(player.user_id)
```

需要在 `UserStatus` 中新增 `FIGHTING` 枚举值（或复用 `EXPLORING`/`TRADING` 中语义匹配的）。

---

## 4. 影响范围

| 组件 | 影响 | 风险 |
|---|---|---|
| `handlers/utils.py` | `@player_required` 拆分为两层 | 中 — 需更新所有装饰器调用 |
| 14 个 handler 文件 | 装饰器替换 + 部分改为分层检查 | 中 — 每处需验证逻辑等价 |
| `UserStatus` | 新增 FIGHTING 枚举 | 低 |
| `managers/boss_manager.py` | challenge_boss 加 busy 状态 | 低 |
| `BUSY_STATE_ALLOWED_COMMANDS` | `_is_command_allowed` 语义改变 | 低 |

---

## 5. 实施建议

1. **Phase 1**: 先修复 `_is_command_allowed` 精确匹配 + 命令别名分离（低风险立即受益）
2. **Phase 2**: 拆分 `@player_required` 装饰器（架构改动，需要测试覆盖）
3. **Phase 3**: 逐个 handler 适配分层装饰器（按绕过严重度排序：boss > dungeon > combat > rift > sect）

### 测试策略

- 每个 handler 的状态转换至少有一个用例覆盖
- `_is_command_allowed` 新增测试：`"存入"` 不匹配 `"存入所有"`，`"存入"` 匹配 `"存入 abc"`

---

## 6. 相关代码审查发现

| 编号 | 原文标题 | 严重度 | 覆盖 |
|---|---|---|---|
| CRIT-4 | 10+ handler 绕过 @player_required | 🔴 | ✅ 3.1, 3.2 |
| CRIT-7 | Boss 战未设忙碌状态 | 🔴 | ✅ 3.5 |
| CRIT-17 | 装备/卸下炼丹炉命令别名耦合 | 🔴 | ✅ 3.4 |
| MAJ-7 | _is_command_allowed startswith 过于宽松 | 🟡 | ✅ 3.3 |
