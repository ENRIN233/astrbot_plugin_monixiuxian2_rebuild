# 并发安全与事务完整性修复方案

> **日期:** 2026-07-01  
> **来源:** 代码质量审查 (code-review 2026-07-01)  
> **优先级:** P0 (最高) — 涉及数据安全和并发损坏

---

## 1. 概述

本次代码审查发现 **大量并发安全缺口**：赠予系统无事务、Boss 击败与奖励发放分离、级联删除无事务包裹、update_player 全字段覆盖等。这些缺陷可能导致**物品复制、数据丢失、状态不一致**等严重问题。

本文档覆盖 🔴 阻塞级 10 项 + 🟡 重要级 6 项 + 🟢 建议级 2 项，按修复优先级组织。

---

## 2. 问题清单与根因分析

### 2.1 赠予系统并发竞争 (🔴 CRIT-1/CRIT-2)

**问题**: `handle_accept_gift` 与 `handle_reject_gift` 并发时可致物品复制；创建赠予时先取物后入库，异常可致丢物。

**根因**: 赠予流程（create → accept/reject → delete）**全程无事务、无 CAS、无锁**。`get_pending_gift` 是普通 SELECT，`delete_pending_gift` 是简单 DELETE，不检查 rowcount。

**涉及文件**:
- `handlers/storage_ring_handler.py:314-404`
- `data/database_extended.py` — `get_pending_gift`, `delete_pending_gift`, `create_pending_gift`

### 2.2 Boss 击败与奖励发放分离 (🔴 CRIT-12)

**问题**: `try_defeat_boss` 用 CAS 标记 Boss 已击败并立即 commit，后续物品/灵石发放失败时不可回滚。

**根因**: CAS 提交和奖励发放是两个独立事务，进程崩溃时玩家打完 Boss 拿不到奖励。

**涉及文件**: `managers/boss_manager.py:239-302`, `data/database_extended.py:284-294`

### 2.3 级联删除无事务 (🔴 CRIT-8/CRIT-9/CRIT-13)

**问题**: `delete_player_cascade` 执行 13 条 SQL 但无 `BEGIN IMMEDIATE`；`safe_execute` 静默吞异常；遗漏 5 张关联表。

**根因**: 每条 SQL 独立提交，中途崩溃的数据残留；`safe_execute` 使调用方不知删除失败。

**涉及文件**: `data/data_manager.py:277-305`

### 2.4 update_player 全字段覆盖 (🔴 CRIT-20)

**问题**: `update_player` 将 Player 所有字段写回 DB。两个协程同时操作不同 JSON 字段（storage_ring_items vs pills_inventory），后者覆盖前者。

**根因**: 全字段写入而非逐字段差异更新；JSON 字段的 read-modify-write 非原子。

**涉及文件**: `data/data_manager.py:157-267`

### 2.5 关键路径多步操作无事务 (🔴 CRIT-3/CRIT-5/CRIT-14/CRIT-15)

**问题**: 战斗前持久化属性、秘境结算回滚后内存与 DB 不一致、突破贷款过时数据——均因多步操作未在同一事务中。

**根因**: 数据层 `auto_commit` 参数不统一，组合原子操作时容易意外提前提交。

**涉及文件**: 
- `combat_handlers.py:93-104`
- `rift_manager.py:383-399`
- `breakthrough_manager.py:403-422`

### 2.6 宗门资材发放与宗主传位非原子 (🔴 CRIT-2/CRIT-3)

**问题**: 资材发放（逐宗门 update）与 dedup key 写入不在同一事务；宗主传位三步更新无事务。

**涉及文件**: `main.py:803-810, 878-883`

### 2.7 赌博/修炼/签到/储物戒/突破消耗无事务 (🟡 MAJ-2/3/5/6/9/10)

**涉及文件**: `gambling_handler.py:143-151`, `player_handler.py:328-329,532-550`, `breakthrough_handler.py:211-212`, `storage_ring_handler.py:450-451`

### 2.8 数据层 BEGIN IMMEDIATE 缺失 (🟡 MAJ-8/9/10)

**问题**: data_manager.py 和 database_extended.py 所有写方法使用隐式事务（auto-commit）或 `BEGIN`（DEFERRED），高并发下可能死锁。

### 2.9 terminate 未等待后台任务 (🔴 CRIT-1)

**问题**: `terminate()` `cancel()` 后立即关闭 DB，后台任务可能仍在执行 DB 操作。

**涉及文件**: `main.py:399-417`

---

## 3. 修复方案

### 3.1 赠予系统 — CAS 并发防护（P0）

**目标**: 消除物品复制和丢物的竞态窗口。

**方案**:

```python
# data/database_extended.py — 新增方法

async def claim_pending_gift(self, gift_id: int, receiver_id: str) -> Optional[dict]:
    """CAS 领取赠予：只有 status='pending' 且 receiver=receiver_id 才能领取"""
    await self.conn.execute("BEGIN IMMEDIATE")
    try:
        cursor = await self.conn.execute(
            "UPDATE pending_gifts SET status = 'claimed' "
            "WHERE id = ? AND receiver_id = ? AND status = 'pending'",
            (gift_id, receiver_id)
        )
        if cursor.rowcount == 0:
            await self.conn.rollback()
            return None  # 已被他人领取或不存在
        
        cursor = await self.conn.execute(
            "SELECT * FROM pending_gifts WHERE id = ?", (gift_id,)
        )
        row = await cursor.fetchone()
        await self.conn.commit()
        return dict(row) if row else None
    except Exception:
        await self.conn.rollback()
        raise

async def reject_pending_gift(self, gift_id: int, sender_id: str) -> bool:
    """CAS 拒绝赠予：只有 sender=sender_id 才能拒绝"""
    await self.conn.execute("BEGIN IMMEDIATE")
    try:
        cursor = await self.conn.execute(
            "UPDATE pending_gifts SET status = 'rejected' "
            "WHERE id = ? AND sender_id = ? AND status = 'pending'",
            (gift_id, sender_id)
        )
        success = cursor.rowcount > 0
        await self.conn.commit()
        return success
    except Exception:
        await self.conn.rollback()
        raise
```

**handler 改动**:

```python
# handlers/storage_ring_handler.py

async def handle_accept_gift(self, player, event):
    gift_id = ...  # 从参数或数据库获取
    gift = await self.db.ext.claim_pending_gift(gift_id, player.user_id)
    if not gift:
        yield event.plain_result("赠予记录不存在或已被他人领取。")
        return
    # gift 已在事务中被保护，安全地存储物品
    await self.storage_ring_manager.store_item(player, gift["item_name"])
```

**创建赠予修复** — 用事务包裹 retrieve_item + create_pending_gift：

```python
await self.db.conn.execute("BEGIN IMMEDIATE")
try:
    await self.storage_ring_manager.retrieve_item(sender, item_name, auto_commit=False)
    await self.db.ext.create_pending_gift(sender_id, receiver_id, item_name, auto_commit=False)
    await self.db.conn.commit()
except Exception:
    await self.db.conn.rollback()
    raise
```

### 3.2 Boss 击败事务合并（P0）

**目标**: Boss CAS 标记 + 奖励发放为原子操作。

**方案** — 在 `data/database_extended.py` 新增原子方法：

```python
async def defeat_boss_and_reward(self, boss_id: str, player: Player, 
                                  items: List[str], gold: int, exp: int) -> bool:
    """原子操作：标记 Boss 已击败 + 发放奖励"""
    await self.conn.execute("BEGIN IMMEDIATE")
    try:
        # CAS 标记 Boss 已击败
        cursor = await self.conn.execute(
            "UPDATE boss SET status = 0 WHERE boss_id = ? AND status = 1",
            (boss_id,)
        )
        if cursor.rowcount == 0:
            await self.conn.rollback()
            return False  # Boss 已被其他人击败
        
        # 发放奖励
        player.gold += gold
        player.experience += exp
        await self.update_player(player, auto_commit=False)
        for item in items:
            await self.storage_ring_manager.store_item(player, item, auto_commit=False)
        
        await self.conn.commit()
        return True
    except Exception:
        await self.conn.rollback()
        raise
```

**Boss 挑战修复** — 同时设置忙碌状态防止并发：

```python
async def challenge_boss(self, player, event):
    # 先设置忙碌
    await self.db.ext.set_user_busy(player.user_id, UserStatus.FIGHTING)
    try:
        # 战斗逻辑...
        success = await self.db.ext.defeat_boss_and_reward(boss_id, player, items, gold, exp)
        # ...
    finally:
        await self.db.ext.set_user_free(player.user_id)
```

### 3.3 delete_player_cascade 事务保护 + 补全表（P0）

**目标**: 级联删除为原子操作 + 不遗漏关联表。

**方案**:

```python
# data/data_manager.py

async def delete_player_cascade(self, user_id: str) -> bool:
    await self.conn.execute("BEGIN IMMEDIATE")
    try:
        tables = [
            ("DELETE FROM player_skills WHERE user_id = ?", (user_id,)),
            ("DELETE FROM dungeon_runs WHERE user_id = ?", (user_id,)),
            ("UPDATE trades SET status = 'cancelled' WHERE (initiator_id = ? OR target_id = ?) AND status = 'pending'", (user_id, user_id)),
            ("DELETE FROM consignment_listings WHERE seller_id = ?", (user_id,)),
            ("DELETE FROM gm_compensation_claims WHERE user_id = ?", (user_id,)),
            ("DELETE FROM pending_gifts WHERE sender_id = ? OR receiver_id = ?", (user_id, user_id)),
            ("UPDATE bank_loans SET status = 'bad_debt' WHERE user_id = ? AND status = 'active'", (user_id,)),
            ("DELETE FROM bank_accounts WHERE user_id = ?", (user_id,)),
            ("DELETE FROM user_cd WHERE user_id = ?", (user_id,)),
            ("DELETE FROM player_buffs WHERE user_id = ?", (user_id,)),
            ("DELETE FROM player_daily_activity WHERE user_id = ?", (user_id,)),
            ("DELETE FROM bounty_tasks WHERE user_id = ?", (user_id,)),
            ("DELETE FROM achievement_progress WHERE user_id = ?", (user_id,)),
            # players 表最后删除
            ("DELETE FROM players WHERE user_id = ?", (user_id,)),
        ]
        for sql, params in tables:
            await self.conn.execute(sql, params)
        
        await self.conn.commit()
        return True
    except Exception:
        await self.conn.rollback()
        raise
```

### 3.4 update_player 差异更新 + 乐观锁（P0）

**目标**: 防止协程间全字段覆盖。

**方案（阶段一 — 立即措施）**:

为 Player 模型添加 `__dirty_fields` 跟踪，`update_player` 只写变化的字段：

```python
# models.py
@dataclass
class Player:
    # ... 现有字段 ...
    
    def __post_init__(self):
        self._dirty_fields: Set[str] = set()
    
    def mark_dirty(self, field: str) -> None:
        self._dirty_fields.add(field)

# setter 示例
@storage_ring_items.setter
def storage_ring_items(self, value):
    self._storage_ring_items = value
    self.mark_dirty("storage_ring_items")
```

**方案（阶段二 — 推荐）**:

添加版本号乐观锁：

```sql
ALTER TABLE players ADD COLUMN version INTEGER NOT NULL DEFAULT 1;
```

```python
async def update_player(self, player: Player, auto_commit: bool = True):
    old_version = player.version
    player.version += 1
    cursor = await self.conn.execute(
        "UPDATE players SET ..., version = version + 1 "
        "WHERE user_id = ? AND version = ?",
        (..., player.user_id, old_version)
    )
    if cursor.rowcount == 0:
        raise ConcurrentModificationError(f"Player {player.user_id} was modified by another coroutine")
```

### 3.5 关键路径多步操作统一事务（P1）

**规则**: 所有组合多步 DB 写操作必须使用 `BEGIN IMMEDIATE` + `auto_commit=False`。

**具体修复点**:

| 位置 | 操作 | 方案 |
|---|---|---|
| `combat_handlers.py:93-104` | 战斗前持久化属性 | 延迟持久化到战斗结束后 |
| `rift_manager.py:383-399` | 秘境结算 | 确保 player 对象从事务内重新读取 |
| `breakthrough_manager.py:403-422` | 突破贷款还款 | 从事务内重新 query player |
| `gambling_handler.py:143-151` | 赌博灵石变更 | 包裹 BEGIN IMMEDIATE |
| `player_handler.py:328-329` | 修炼状态设置 | 合并为一条 SQL 或事务 |
| `breakthrough_handler.py:211-212` | 突破 + 丹药消耗 | 包裹 BEGIN IMMEDIATE |
| `player_handler.py:532-550` | 签到里程碑 | 包裹 BEGIN IMMEDIATE |
| `storage_ring_handler.py:450-451` | 储物戒升级 | 包裹 BEGIN IMMEDIATE |
| `main.py:803-810` | 宗门资材发放 | 资材 + dedup key 同一事务 |
| `main.py:878-883` | 宗主传位 | 三步更新同一事务 |
| `alchemy_handlers.py:105-106` | 炼丹炉装备 | 包裹 BEGIN IMMEDIATE |
| `combat_handlers.py:172-173` | 决斗 HP/MP 更新 | 包裹 BEGIN IMMEDIATE |

### 3.6 数据层 BEGIN IMMEDIATE 统一（P1）

**目标**: data_manager.py 和 database_extended.py 中所有写操作使用 `BEGIN IMMEDIATE` 替代 `BEGIN`。

**修改策略**: 创建统一的事务上下文管理器：

```python
# data/database_extended.py — 新增
@asynccontextmanager
async def immediate_transaction(self):
    await self.conn.execute("BEGIN IMMEDIATE")
    try:
        yield
        await self.conn.commit()
    except Exception:
        await self.conn.rollback()
        raise
```

然后逐个方法从 `auto_commit=True` 迁移到使用 `immediate_transaction()`。**新增方法默认使用 IMMEDIATE**；已有方法采用增量替换（优先替换操作 JSON 字段的高频路径）。

### 3.7 cursor 上下文管理（P2）

**目标**: 杜绝未关闭的 cursor 累积。

**方案**: 统一将 `cursor = await self.conn.execute(...)` 改为 `async with self.conn.execute(...) as cursor:`。

涉及方法：`update_boss_hp_if_active`, `try_defeat_boss`, `add_player_skill`, `remove_player_skill`, `claim_compensation`。

### 3.8 terminate 优雅关闭（P0）

**方案**:

```python
# main.py
async def terminate(self):
    tasks = []
    if self.boss_task:
        self.boss_task.cancel()
        tasks.append(self.boss_task)
    # ... 其他任务 ...
    
    # 等待所有后台任务完成
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    
    await self.db.close()
```

同时为每个后台任务添加正确的 CancelledError 处理：

```python
try:
    while True:
        await do_work()
except asyncio.CancelledError:
    await cleanup()  # 释放资源
    raise  # 重新抛出让 gather 知道
```

---

## 4. 影响范围

| 组件 | 影响 | 风险等级 |
|---|---|---|
| `data/database_extended.py` | 新增 CAS 方法 + 事务上下文管理器 + auto_commit 参数补齐 | 中（新方法不改变旧行为） |
| `data/data_manager.py` | update_player 差异更新 / 乐观锁；delete_player_cascade 重写 | 高（影响所有数据操作） |
| `handlers/storage_ring_handler.py` | 赠予流程重写 | 中（需验证逻辑等价） |
| `managers/boss_manager.py` | Boss 战流程改为原子操作 | 中 |
| `main.py` | terminate 优雅关闭；宗门资材/传位改为事务 | 低 |
| `gambling_handler.py`, `player_handler.py` 等 | 加事务包裹 | 低 |

---

## 5. 实施建议

### 实施顺序

1. **Phase 1（第一轮迭代）— 最高风险修复**
   - `delete_player_cascade` 事务保护 + 补全表
   - 赠予系统 CAS 防护
   - `terminate` 优雅关闭
   - 数据层 `immediate_transaction` 上下文管理器

2. **Phase 2 — 核心数据路径**
   - Boss 击败事务合并
   - `update_player` 差异更新
   - 修炼状态原子设置

3. **Phase 3 — 其余路径**
   - 赌博、签到、宗门等事务包裹
   - cursor 上下文管理

### 测试策略

- 每项修改至少有一个测试用例覆盖
- 赠予 CAS 需测试并发竞争场景（两个协程同时 accept 同一赠予）
- Boss 击败需测试 CAS 失败回退（另一玩家已击败）
- `delete_player_cascade` 需验证所有关联表的内容

---

## 6. 相关代码审查发现

| 编号 | 原文标题 | 严重度 | 本方案覆盖 |
|---|---|---|---|
| CRIT-1 | 赠予系统并发竞态可致物品复制 | 🔴 | ✅ 3.1 |
| CRIT-2 | 赠予创建时先取物后入库可致丢物 | 🔴 | ✅ 3.1 |
| CRIT-3 | 战斗前提前持久化属性 | 🔴 | ✅ 3.5 |
| CRIT-5 | 弃道重修删除操作无事务保护 | 🔴 | ✅ 3.3 |
| CRIT-12 | Boss 战击败流程无事务保护 | 🔴 | ✅ 3.2 |
| CRIT-13 | 删除玩家级联操作无事务保护 | 🔴 | ✅ 3.3 |
| CRIT-14 | 秘境物品掉落事务中误吞异常 | 🔴 | ✅ 3.5 |
| CRIT-15 | 突破贷款读取到过时 player | 🔴 | ✅ 3.5 |
| CRIT-20 | update_player 全字段覆盖 | 🔴 | ✅ 3.4 |
| MAJ-1 | 赌博系统灵石变更无事务 | 🟡 | ✅ 3.5 |
| MAJ-2 | 突破后消耗丹药与突破分离 | 🟡 | ✅ 3.5 |
| MAJ-3 | 状态设置两条独立写入 | 🟡 | ✅ 3.5 |
| MAJ-5 | 储物戒升级无事务 | 🟡 | ✅ 3.5 |
| MAJ-6 | 签到里程碑发放无事务 | 🟡 | ✅ 3.5 |
| MAJ-8 | 数据层缺少 BEGIN IMMEDIATE | 🟡 | ✅ 3.6 |
| MAJ-10 | 宗门资材与传位非原子 | 🟡 | ✅ 3.5 |
