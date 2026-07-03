# 数据模型与数据访问层修复方案

> **日期:** 2026-07-01  
> **来源:** 代码质量审查  
> **优先级:** P1 — 涉及数据正确性和迁移安全性

---

## 1. 概述

数据层存在 **类型不一致、方法返回值错误、资源管理缺陷、迁移死代码、DDL 滥用** 等问题。这些问题不影响核心功能但累积技术债务，持续降低数据可靠性和系统健壮性。

---

## 2. 问题清单

### 🔴 阻塞级

| ID | 问题 | 文件:行 | 描述 |
|---|---|---|---|
| D1 | `add_player_skill` 始终返回 True | `database_extended.py:935-946` | `INSERT OR IGNORE` 不检查 rowcount，调用方无法区分"新获得"与"已存在" |
| D2 | `has_resurrection_pill` 类型不一致 | `models.py:145` | Python `str` vs DB `INTEGER`，默认 0 返回 int |
| D3 | `delete_player_cascade` 遗漏 5 张关联表 | `data_manager.py:277-305` | player_skills, dungeon_runs, gm_compensation, trades, consignment 未清理 |
| D4 | V10 迁移 f-string 拼接列名 | `migration.py:466-468` | 列名含保留字时 SQL 错误 |
| D5 | `complete_bounty` 不检查 rowcount | `database_extended.py:623-629` | 永远返回 True，无活跃悬赏也返回成功 |

### 🟡 重要级

| ID | 问题 | 文件:行 | 描述 |
|---|---|---|---|
| D6 | JSON getter 修改模型状态 | `models.py:203-227` | `get_permanent_pill_gains` 在 getter 中写入 `self` 字段，纯读操作产生副作用 |
| D7 | cursor 未用 async with 管理 | `database_extended.py:277,290,939,950,1051` | 依赖 GC 回收 cursor |
| D8 | 返回类型注解错误 | `data_manager.py:132,145` | `-> Player` 标注但返回 `None` |
| D9 | `auto_commit` 参数不统一 | `database_extended.py` 多处 | sect/boss/bounty/gift 等模块方法无 auto_commit 参数 |
| D10 | 每次查询前调用 `CREATE TABLE IF NOT EXISTS` | `database_extended.py` 多处 | `get_active_bounty` / `get_system_config` 等每次执行 DDL |
| D11 | V24 迁移死代码 | `migration.py:1529,1532` | `new_phy_dmg` 双重赋值 |
| D12 | `get_expired_bounty` 用 fetchone 但可能多行 | `database_extended.py:613-621` | 语义不明确 |

### 🟢 建议级

| ID | 问题 | 文件:行 | 描述 |
|---|---|---|---|
| D13 | `type` 作为字段名遮蔽内置函数 | `models_extended.py:147` | `UserCd.type` 遮蔽 `builtins.type` |
| D14 | 文件头注释错误 | `models_extended.py:1` | 应写 `models_extended.py` |
| D15 | V28 迁移循环内 import json | `migration.py:1640` | import 在 for 循环体内部 |
| D16 | `get_bank_account` 返回裸 dict | `database_extended.py:535-544` | 与其他方法返回 dataclass 不一致 |
| D17 | 全员 BEGIN 非 IMMEDIATE | 数据层全部写方法 | DEFERRED 模式高并发可能死锁（已在事务安全方案覆盖） |

---

## 3. 修复方案

### 3.1 add_player_skill 返回 rowcount 检查 (P0)

```python
# database_extended.py
async def add_player_skill(self, user_id: str, skill_name: str) -> bool:
    try:
        cursor = await self.conn.execute(
            "INSERT OR IGNORE INTO player_skills (user_id, skill_name) VALUES (?, ?)",
            (user_id, skill_name)
        )
        await self.conn.commit()
        return cursor.rowcount > 0  # True=新获得, False=已存在
    except Exception:
        await self.conn.rollback()
        return False
```

### 3.2 has_resurrection_pill 类型统一 (P0)

**方案**: 统一为 `str` 类型：

```sql
-- 新增迁移 v40
ALTER TABLE players RENAME COLUMN has_resurrection_pill TO has_resurrection_pill_old;
ALTER TABLE players ADD COLUMN has_resurrection_pill TEXT NOT NULL DEFAULT '';
UPDATE players SET has_resurrection_pill = CASE 
    WHEN has_resurrection_pill_old = 1 OR has_resurrection_pill_old = '回生丹' THEN '回生丹'
    WHEN has_resurrection_pill_old = '涅槃重生丹' THEN '涅槃重生丹'
    ELSE ''
END;
```

```python
# models.py
has_resurrection_pill: str = ""  # "" = 无, "回生丹" / "涅槃重生丹"
```

### 3.3 delete_player_cascade 补全表 (P0)

已包含在事务安全方案 3.3 中，在此列出确认。新增清理表：

- `player_skills`
- `dungeon_runs`
- `trades`（UPDATE 标记取消）
- `consignment_listings`（DELETE）
- `gm_compensation_claims`

### 3.4 V10 迁移 SQL 安全 (P1)

```python
# migration.py — 使用方括号引用列名
from sqlite3 import _sqlite_valid_column_name

# 方案 A: 使用 SQLite 的方括号引用
columns_quoted = ', '.join(f'"{col}"' for col in columns_to_keep)
await conn.execute(f"""
    INSERT INTO players_new ({columns_quoted})
    SELECT {columns_quoted} FROM players
""")

# 方案 B: 逐列构建（更安全，更啰嗦）
placeholders = ', '.join('?' for _ in columns_to_keep)
await conn.execute(
    f"INSERT INTO players_new ({', '.join(columns_to_keep)}) "
    f"SELECT * FROM (SELECT {placeholders} FROM players)",
    ...  # 需要逐列映射
)
```

推荐方案 A，因为 `columns_to_keep` 来自 `PRAGMA table_info`（SQLite 内部），不涉及用户输入，方括号引用已足够。

### 3.5 complete_bounty 检查 rowcount (P1)

```python
async def complete_bounty(self, user_id: str) -> bool:
    cursor = await self.conn.execute(
        "UPDATE bounty_tasks SET status = 2 WHERE user_id = ? AND status = 1",
        (user_id,)
    )
    await self.conn.commit()
    return cursor.rowcount > 0
```

### 3.6 JSON getter 消除副作用 (P1)

```python
# models.py — 分离读取和迁移逻辑
def get_permanent_pill_gains(self) -> dict:
    """读取永久丹药增益。只读，不修改模型状态。"""
    if not self.permanent_pill_gains:
        return {}
    return json.loads(self.permanent_pill_gains)

def migrate_permanent_pill_gains(self) -> bool:
    """执行旧格式自动迁移，返回 False 表示无需迁移。"""
    gains = json.loads(self.permanent_pill_gains) if self.permanent_pill_gains else {}
    migrated = self._do_migrate(gains)
    if migrated:
        self.permanent_pill_gains = json.dumps(gains, ensure_ascii=False)
    return migrated
```

所有需要自动迁移的调用点显式调用 `migrate_permanent_pill_gains()` + `update_player()`。

### 3.7 cursor 上下文管理 (P2)

```python
# 修改前
cursor = await self.conn.execute(sql, params)
row = await cursor.fetchone()

# 修改后
async with self.conn.execute(sql, params) as cursor:
    row = await cursor.fetchone()
```

涉及文件：`database_extended.py` 中 5 处：

| 方法 | 行号 |
|---|---|
| `update_boss_hp_if_active` | 277 |
| `try_defeat_boss` | 290 |
| `add_player_skill` | 939 |
| `remove_player_skill` | 950 |
| `claim_compensation` | 1051 |

### 3.8 返回类型注解修正 (P2)

```python
# data_manager.py
async def get_player_by_id(self, user_id: str) -> Optional[Player]:
async def get_player_by_name(self, user_name: str) -> Optional[Player]:
```

### 3.9 auto_commit 参数补齐 (P2)

为以下方法统一添加 `auto_commit: bool = True` 参数：

- sect 系列：`create_sect`, `update_sect`, `delete_sect`
- boss 系列：`update_boss`, `defeat_boss` 等
- bounty 系列：`complete_bounty`, `cancel_bounty`
- gift 系列：`delete_pending_gift`, `cleanup_expired_gifts`
- player_sect 系列：`update_player_sect_info`, `update_player_sect_contribution`

### 3.10 移除冗余 DDL (P2)

```python
# database_extended.py — 添加类级别缓存
class DataBaseExt:
    def __init__(self, ...):
        ...
        self._tables_ensured: Set[str] = set()
    
    async def ensure_bounty_tables(self):
        if "bounty" in self._tables_ensured:
            return
        await self._create_table_bounty()
        self._tables_ensured.add("bounty")
```

### 3.11 迁移清理 (P2)

| 问题 | 修复 |
|---|---|
| V24 死代码行 1529 `new_phy_dmg = map_value(...)` | 删除该行 |
| V28 循环内 `import json as _json` | 移到文件顶部 |
| `get_expired_bounty fetchone` 语义 | 加 `ORDER BY id DESC LIMIT 1` 或改为返回 `List[dict]` |

### 3.12 命名与注释修复 (P3)

| 问题 | 修复 |
|---|---|
| `type` 字段遮蔽内置函数 | 改名为 `cd_type`（需要更新所有引用） |
| `models_extended.py` 注释 | `# models.py` → `# models_extended.py` |
| `get_bank_account` 返回裸 dict | 创建 `BankAccount` dataclass 并返回 |

---

## 4. 影响范围

| 组件 | 影响 | 风险 |
|---|---|---|
| `data/database_extended.py` | 5 处 cursor 上下文管理、auto_commit 参数补齐、DDL 缓存 | 中 — 改点多需回归 |
| `data/data_manager.py` | 类型注解修正 | 低 |
| `data/migration.py` | V10 SQL 引用、V24 死代码、V28 import | 低 |
| `models.py` | JSON getter 分离读/迁移、has_resurrection_pill 统一为 str | 中 — 影响所有调用方 |
| `models_extended.py` | type→cd_type 改名 | 高 — 需全局替换 |

**关于 `type→cd_type` 的命名更改**: 该修改影响面广（涉及 `UserCd.type` 的所有引用），建议与"状态管理修复方案"中的装饰器拆分同步进行，统一安排一次大规模重构。

---

## 5. 实施建议

1. **Phase 1（立即修复）**: `add_player_skill` rowcount、`complete_bounty` rowcount、类型注解修正（低风险，立即受益）
2. **Phase 2**: `has_resurrection_pill` 类型统一（新增 v40 迁移）、JSON getter 副作用消除
3. **Phase 3**: cursor 上下文管理、auto_commit 补齐、DDL 缓存
4. **Phase 4**: V10/V24/V28 迁移清理、`type→cd_type` 全局改名

---

## 6. 相关代码审查发现

| 编号 | 原文标题 | 严重度 | 覆盖 |
|---|---|---|---|
| D1 | add_player_skill 始终返回 True | 🔴 | ✅ 3.1 |
| D2 | has_resurrection_pill 类型不一致 | 🔴 | ✅ 3.2 |
| D3 | delete_player_cascade 遗漏 5 张表 | 🔴 | ✅ 3.3 |
| D4 | V10 f-string 拼接列名 | 🔴 | ✅ 3.4 |
| D5 | complete_bounty 不检查 rowcount | 🔴 | ✅ 3.5 |
| D6 | JSON getter 副作用 | 🟡 | ✅ 3.6 |
| D7 | cursor 未用 async with | 🟡 | ✅ 3.7 |
| D8 | 类型注解错误 | 🟡 | ✅ 3.8 |
| D9 | auto_commit 参数不统一 | 🟡 | ✅ 3.9 |
| D10 | 每次查询前 DDL | 🟡 | ✅ 3.10 |
| D11 | V24 死代码 | 🟡 | ✅ 3.11 |
| D12 | fetchone 语义不明确 | 🟡 | ✅ 3.11 |
| D13 | type 字段遮蔽内置函数 | 🟢 | ✅ 3.12 |
| D14 | 文件头注释错误 | 🟢 | ✅ 3.12 |
| D15 | 循环内 import | 🟢 | ✅ 3.11 |
| D16 | 返回裸 dict | 🟢 | ✅ 3.12 |
