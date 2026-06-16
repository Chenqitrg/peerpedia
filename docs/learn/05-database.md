# Database 模块

> SQLite 数据层。7 个实体 + 1 个 join table 的 schema、关系和迁移。

## 一句话职责

**存元数据和缓存。** 文章内容、评审、分数的权威版本在 Git。SQLite 存用户/关系 + 缓存文章/评审数据用于快速查询。

## ER 图（7 实体 + 1 Join Table）

```
   ┌──────────────┐
   │    users     │
   │ id (PK)      │
   │ username UQ  │
   │ reputation   │◄── JSON
   └──────┬───────┘
          │ 1:N
          ├──────────────────────────────┐
          ▼               ▼              ▼
   ┌──────────────┐┌──────────┐  ┌──────────────┐
   │article_      ││ follows  │  │   reviews    │
   │authors       ││          │  │              │
   │article_id PK ││follower  │  │ id (PK)      │
   │author_id  PK ││followed  │  │ article_id ──┼──┐
   │position      │└──────────┘  │ reviewer_id──┼──┤
   └──────┬───────┘              │ scores (JSON)│  │
          │ N:1                  │ thread (JSON)│  │
          ▼                      └──────────────┘  │
   ┌──────────────┐                                │
   │   articles   │◄───────────────────────────────┘
   │ id (PK)      │
   │ status       │──► draft → sedimentation → published
   │ score (JSON) │
   │ compiled_*   │◄── 缓存（issue #81 计划移除）
   │ forked_from  │
   └──────┬───────┘
          │ 1:N
          ├─────────────────┬──────────────┐
          ▼                 ▼              ▼
   ┌──────────┐    ┌──────────────┐┌──────────────┐
   │bookmarks │    │merge_proposal││  citations   │
   │user_id   │    │id (PK)       ││ from_id  PK  │
   │article_id│    │fork_id       ││ to_id    PK  │
   └──────────┘    │target_id     ││ fwd_prob     │
                   │thread (JSON) ││ back_prob    │
                   └──────────────┘└──────────────┘
```

- **粗线箭头** = 外键关系（`──►` 指向父表 PK）
- **article_authors 是独立的 join table**，不是 JSON 字段
- **JSON 列（标 ◄── JSON）**：articles.score, reviews.thread, merge_proposals.thread
- **compiled_* 是缓存混入**，不属于主数据

## Schema 全景

```
articles ──< article_authors >── users
   │              │                   │
   │              │              follows (follower → followed)
   │              │
   ├── reviews (article_id, reviewer_id, scope, commit_hash)
   ├── bookmarks (user_id, article_id)
   ├── citations (from_article → to_article)
   └── merge_proposals (fork → target, proposer)
```

## 表结构

### articles

| 列 | 类型 | 用途 |
|----|------|------|
| id | TEXT PK | UUID |
| title | TEXT | 文章标题 |
| abstract | TEXT | 摘要 |
| keywords | JSON | 关键词列表 |
| categories | JSON | 分类列表 |
| status | TEXT | draft / sedimentation / published |
| score | JSON | FiveDimScores dict |
| compiled_format | TEXT | 编译格式缓存（html/svg） |
| compiled_output | TEXT | 编译输出缓存 |
| compiled_pages | JSON | 多页 SVG 缓存 |
| sink_start | DATETIME | 沉淀开始时间 |
| sink_duration_days | INT | 沉淀天数（默认 7） |
| sink_extended_count | INT | 延长次数 |
| forked_from | TEXT | fork 来源 |
| fork_count | INT | 被 fork 次数 |
| last_author_rebuild_hash | TEXT | 作者重建标记 |
| created_at / updated_at | DATETIME | 时间戳 |

**注意：`compiled_*` 字段是编译缓存混入主数据。** issue #81 计划迁移出去。

### article_authors（join table）

| 列 | 类型 | 用途 |
|----|------|------|
| article_id | TEXT PK FK | 文章 |
| author_id | TEXT PK FK | 作者 |
| position | INT | 排序 |

唯一约束：`(article_id, author_id)`

### users

| 列 | 类型 | 用途 |
|----|------|------|
| id | TEXT PK | UUID |
| username | TEXT UNIQUE | 登录标识 |
| password_hash | TEXT | bcrypt |
| email | TEXT | 邮箱（格式验证） |
| name | TEXT | 显示名 |
| anonymous_name | TEXT | 匿名显示名 |
| affiliation | TEXT | 所属机构 |
| expertise | JSON | 专长列表 |
| avatar_url | TEXT | 头像 |
| contact | TEXT | 联系方式 |
| reputation | JSON | ReputationScores dict |

### reviews

| 列 | 类型 | 用途 |
|----|------|------|
| id | TEXT PK | UUID |
| article_id | TEXT FK | 被评文章 |
| commit_hash | TEXT | 评审的 commit |
| reviewer_id | TEXT FK | 评审人 |
| scope | TEXT | "pool" / "published" |
| scores | JSON | FiveDimScores dict |
| contributions | JSON | 作者贡献比例 |
| thread | JSON | 讨论串（list[dict]） |

唯一约束：`(article_id, reviewer_id, scope, commit_hash)` —— 同一 reviewer 对同一 commit 只能评一次。

### follows / bookmarks

标准多对多关联表。Follow 是 `(follower_id, followed_id)`，Bookmark 是 `(user_id, article_id)`。

### merge_proposals

| 列 | 类型 | 用途 |
|----|------|------|
| id | TEXT PK | UUID |
| fork_article_id | TEXT FK | fork 的文章 |
| target_article_id | TEXT FK | 目标文章 |
| proposer_id | TEXT FK | 提议人 |
| status | TEXT | open / accepted / rejected |
| thread | JSON | 讨论串 |

### citations

| 列 | 类型 | 用途 |
|----|------|------|
| from_article_id | TEXT PK FK | 引用方 |
| to_article_id | TEXT PK FK | 被引用方 |
| forward_prob | FLOAT | 正向引用概率 |
| backward_prob | FLOAT | 反向引用概率 |

## JSON 列的问题

三个 JSON 列是已知技术债：

| 列 | 所在表 | 问题 |
|----|--------|------|
| thread | reviews | 不能查询讨论内容、不能索引 |
| thread | merge_proposals | 同上 |
| score | articles | 虽然是 dict 但实际是结构化数据 |

gpt_review 的 P0-1 建议：`thread` 应该拆成 `thread_messages` 表。`score` 可以在 article 上展开为 5 个列，或者接受 JSON（因为评分维度是固定的 5 维）。

## DB 引擎配置

```python
# core/peerpedia_core/storage/db/engine.py
Base = declarative_base()
JSONDict = Column(JSON)    # dict → JSON 列
JSONList = Column(JSON)    # list → JSON 列

def init_db(db_url: str):
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)

def migrate_db(engine):
    # 手写迁移逻辑，不是 alembic
```

## 迁移机制

没有 alembic。`migrate_db()` 是一段手写的 Python 代码，直接在 `Base.metadata.create_all()` 之后运行：

1. 检查已有列是否存在
2. 如果不存在 → `ALTER TABLE ADD COLUMN`
3. 创建缺失的索引

**这是高风险操作。** 如果迁移中途失败，没有回滚机制。生产环境需要先备份 DB。

## Tauri 端的独立 schema

Tauri 有自己的 SQLite schema（`db.rs`，版本 10），和 core 的 SQLAlchemy models **完全不共享**。两者各自定义、各自迁移。

Tauri 的表：
- `local_accounts`（不是 users）
- `drafts`（不是 articles）
- `article_cache`（只读快照）
- `browsing_history`
- `sessions`

## 已知问题

1. **没有共享 schema 定义**。改一个表要改两处（Python models + Rust db.rs）。
2. **没有 migration 工具**。手写的 migrate_db() + 手写的 db.rs 版本迁移。
3. **JSON 列不能查询**。thread 内容无法搜索。
4. **score 是 JSON dict**。虽然 FiveDimScores 有 dataclass，但存到 DB 时序列化成了 dict——类型信息丢失。

## 入口文件

| 想做什么 | 从哪里开始 |
|----------|-----------|
| 改 schema | `core/peerpedia_core/storage/db/models.py` |
| 改迁移 | `core/peerpedia_core/storage/db/engine.py` + `db.rs` |
| 加 JSON 类型 | `core/peerpedia_core/storage/db/engine.py` |
