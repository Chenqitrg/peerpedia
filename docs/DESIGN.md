# PeerPedia（知诸网）— 设计文档

> 2026-06-07 · 全部已实现功能 · 架构债已修复

---

## 1. 愿景

PeerPedia 是学术出版的 GitHub。文章是 Git 仓库，评审是社区评分，质量通过沉淀池自然筛选。

**目标：** 取代 arXiv 和传统期刊。让 Wikipedia 的开放协作 + arXiv 的预印本规模 + 期刊的同行评审质量，三者合一。

---

## 2. 架构

### 2.1 双层架构

```
Phase 1（冷启动 — Tauri Desktop）
┌─────────────────────────────────────────────────────────┐
│  Vue 3 → IPC → Rust → SQLite + Git（本地）               │
│  离线写作 · 客户端编译 · 版本控制                           │
│  浏览即缓存 · 收藏即完整缓存                                │
└─────────────────────────────────────────────────────────┘

Phase 2+（社区 — Web）
┌─────────────────────────────────────────────────────────┐
│  Vue 3 SPA → REST → FastAPI → SQLite + Git（服务器）       │
│  沉淀池 · 社区评审 · 信誉系统                               │
└─────────────────────────────────────────────────────────┘
```

### 2.2 技术栈

| 层 | 桌面版 (Phase 1) | Web 版 (Phase 2+) |
|---|---|---|
| Shell | Tauri 2.x (Rust) | — |
| 前端 | Vue 3 + TS + Vite + Tailwind | Vue 3 + TS + Vite + Tailwind |
| 后端 | Rust (rusqlite, bcrypt, libgit2) | Python 3.12+, FastAPI, SQLAlchemy |
| 存储 | SQLite + Git 仓库（本地） | SQLite + Git 仓库（服务器） |
| 编译 | Markdown: 客户端 (marked + KaTeX). Typst: Tauri sidecar | Markdown: 客户端 (marked + KaTeX). Typst: 服务端编译 |
| 认证 | bcrypt + SQLite（本地账号） | JWT（bcrypt, 24h 过期） |
| 数学 | KaTeX | KaTeX |

### 2.3 真相源（Source of Truth）

**Git 是真相源，数据库是索引。**

文章内容的写入路径遵循以下不变式：

```
用户请求 → Git commit（内容）→ 成功 → DB upsert（元数据索引）
              ↓ 失败
           返回错误（不写 DB）
```

- 文章内容（Markdown/Typst 源码）存储在 `~/.peerpedia/articles/{id}/` 的 Git 仓库中。
- 数据库存储元数据（标题、状态、评分、关系）用于快速查询。
- 数据库丢失可从 Git 重建。Git 保留 fork/diff/merge 历史。
- 编译结果**绝不**存入数据库——按需生成，文件系统缓存。

### 2.4 离线架构

Phase 1 桌面版完全离线可用：

- **浏览即缓存**：阅读的每篇文章自动缓存到本地 SQLite。
- **收藏即完整缓存**：收藏文章缓存评审 + 引用图。
- **网络状态**：`useNetworkStatus` 以 Wifi/WifiOff 图标显示。启动时默认为离线，首次 ping 成功后翻转为在线——消除 60s 窗口期内离线功能被误放行的 bug。
- **网络功能封锁**：`useOffline` 在本地/Tauri 模式下永久封锁 pool、schools、search.network。这些功能在导航栏显示为灰色禁用图标（带 tooltip），而非点到之后才报错。
- **保存即 Git commit**：每次保存草稿创建或更新本地 Git 仓库（`local_git.rs`），离线可用 `git log` 查看提交历史。
- **本地账号**：bcrypt + SQLite，多账号切换，无需服务器。
- **客户端编译**：Markdown → HTML 通过 `marked` + KaTeX 在浏览器内完成。编译管线（保护数学 → 解析 Markdown → 恢复数学 → 渲染 KaTeX）全程本地运行。

核心 composables：`useNetworkStatus`、`useOffline`、`useTauri`、`useDraftPersistence`。
核心 Rust 模块：`local_auth`、`local_store`、`local_git`。

---

## 3. 数据模型 — 9 个实体

所有关系数据使用关联表，禁止 JSON 存储关系。

### 3.1 Article（文章）

```python
class Article(Base):
    __tablename__ = "articles"

    id = Column(String, primary_key=True, default=uuid4)
    title = Column(String, default="")
    abstract = Column(String, nullable=True)
    keywords = Column(JSONList)               # ["物理", "量子"]
    categories = Column(JSONList)             # ["理论", "实验"]
    status = Column(String, default="draft")  # draft | sedimentation | published
    score = Column(JSONDict)                  # 五维评分缓存（Phase 2 改为实时计算）
    compiled_format = Column(String)          # "html" | "svg"（格式提示，非输出内容）
    sink_start = Column(DateTime)
    sink_duration_days = Column(Integer, default=7)
    sink_extended_count = Column(Integer, default=0)
    forked_from = Column(String, nullable=True)
    fork_count = Column(Integer, default=0)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
```

- `authors` **不是**字段——使用 `article_authors` 关联表。
- `compiled_output` / `compiled_pages` **不存储**——编译按需生成，文件系统缓存。
- `score` 将在 Phase 2 从 DB 字段降级为计算属性。
- JSONList/JSONDict 是 SQLAlchemy TypeDecorator，将 JSON 字符串存入 SQLite。仅用于固定结构数据——**绝不**用于关系。

### 3.2 ArticleAuthor（文章作者关联）

```python
class ArticleAuthor(Base):
    __tablename__ = "article_authors"
    __table_args__ = (UniqueConstraint("article_id", "author_id"),)

    article_id = Column(String, ForeignKey("articles.id"), primary_key=True)
    author_id = Column(String, ForeignKey("users.id"), primary_key=True)
    position = Column(Integer, default=0)    # 保留作者顺序
    created_at = Column(DateTime)
```

替代旧的 `Article.authors` JSON 字段。支持通过 SQL join 高效查询"某作者的文章"。

### 3.3 Review（评审）

```python
class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("article_id", "reviewer_id", "scope", "commit_hash"),
    )

    id = Column(String, primary_key=True)
    article_id = Column(String, ForeignKey("articles.id"))
    commit_hash = Column(String)
    reviewer_id = Column(String, ForeignKey("users.id"))
    scope = Column(String)                   # "pool"（匿名）| "published"（实名）
    scores = Column(JSONDict)                # 五维评分
    contributions = Column(JSONDict, nullable=True)  # 每位作者的贡献比例
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
```

- `thread` **不是**字段——使用 `review_messages` 表。
- `contributions`: dict[author_id → {O, R, C, P, I}]，每维 0-1。

### 3.4 ReviewMessage（评审讨论）

```python
class ReviewMessage(Base):
    __tablename__ = "review_messages"

    id = Column(String, primary_key=True, default=uuid4)
    review_id = Column(String, ForeignKey("reviews.id"))
    parent_id = Column(String, ForeignKey("review_messages.id"), nullable=True)
    author_id = Column(String, ForeignKey("users.id"))
    content = Column(String)
    created_at = Column(DateTime)
```

替代旧的 `Review.thread` JSON 字段。支持分页、搜索和并发写入。通过 `parent_id` 自引用外键实现嵌套回复。

### 3.5 User（用户）

```python
class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=uuid4)
    username = Column(String, unique=True)
    password_hash = Column(String)           # bcrypt
    email = Column(String, nullable=True)
    name = Column(String)                    # 真实姓名
    anonymous_name = Column(String, default="")  # 池内匿名
    affiliation = Column(String, default="")
    expertise = Column(JSONList, default=[])
    avatar_url = Column(String, nullable=True)
    contact = Column(String, nullable=True)
    reputation = Column(JSONDict, default={})  # P/O/C/R 信誉分
    created_at = Column(DateTime)
```

### 3.6 Follow、Bookmark、MergeProposal、Citation

```python
class Follow(Base):
    follower_id = Column(String, FK("users.id"), primary_key=True)
    followed_id = Column(String, FK("users.id"), primary_key=True)

class Bookmark(Base):
    user_id = Column(String, FK("users.id"), primary_key=True)
    article_id = Column(String, FK("articles.id"), primary_key=True)

class MergeProposal(Base):
    id = Column(String, primary_key=True)
    fork_article_id = Column(String, FK("articles.id"))
    target_article_id = Column(String, FK("articles.id"))
    proposer_id = Column(String, FK("users.id"))
    status = Column(String, default="open")  # open | accepted | rejected
    created_at = Column(DateTime)
    resolved_at = Column(DateTime, nullable=True)

class Citation(Base):
    from_article_id = Column(String, FK("articles.id"), primary_key=True)
    to_article_id = Column(String, FK("articles.id"), primary_key=True)
```

全部为纯关联表。无 JSON。无概率字段（P0 重构已移除）。MergeProposal 的讨论功能推迟至 Phase 2。

### 3.7 实体关系图

```
articles ──< article_authors >── users
articles ──< reviews >── review_messages
articles ──< bookmarks >── users
articles ──< citations ── articles
articles ──< merge_proposals >── users
users ──< follows ── users
```

---

## 4. 评分系统

### 4.1 五维文章评分（O/R/C/P/I）

| 维度 | 名称 | 范围 | 衡量内容 |
|------|------|------|----------|
| O | 原创性 | 0-5 | 贡献的新颖程度 |
| R | 严谨性 | 0-5 | 方法和论证是否可靠 |
| C | 完整性 | 0-5 | 工作是否周全自洽 |
| P | 可读性 | 0-5 | 写作是否清晰易懂 |
| I | 影响力 | 0-5 | 对该领域的重要性 |

### 4.2 四维信誉分（P/O/C/R）

| 维度 | 名称 | 衡量内容 |
|------|------|----------|
| P | 专业性 | 贡献的质量和诚信 |
| O | 客观性 | 评审的公正性和准确性 |
| C | 协作性 | 建设性参与 |
| R | 可读性 | 写作的清晰度和可及性 |

信誉分决定沉淀池中的投票权重。

### 4.3 沉淀池（Sedimentation Pool）

1. 文章进入池中，带 `sink_start` 时间戳。
2. 沉淀时长 = 平均评分的函数：分数越高 → 等待越短。
3. 池内评审使用匿名。
4. 计时到期 → 通过 `publish_ready_articles()` 后台任务自动发布。
5. 零社区评审的文章将受到扣分惩罚。

---

## 5. 编译系统

### 5.1 客户端编译管线（Markdown 默认路径）

Markdown 编译在 `frontend/src/utils/markdown.ts` 中使用四阶段管线：

```
保护数学 → marked.parse() → 恢复数学 → renderMathInHtml()
```

**数学保护**：将 `$$...$$` 和 `$...$` 替换为唯一占位符（`PEERPEDIA-MATH-D0` 等），防止 `marked` 破坏 LaTeX。两个关键修复：
- 占位符使用连字符（`PEERPEDIA-MATH-D0`），因为 `marked` 的 GFM 解析器会将下划线（`_MATH_`）误解析为斜体标记。
- `restoreMath` 使用 `split/join` 而非 `String.replace()`，因为 JavaScript 的 `replace()` 会将替换字符串中的 `$$` 解释为字面 `$`，导致 KaTeX 显示模式分隔符坍缩。

### 5.2 按需编译 + 文件系统缓存

编译结果**绝不存入数据库**。编译端点每次请求时生成 HTML/SVG 并缓存至磁盘：

```
~/.peerpedia/cache/{article_id}/{commit_hash}.{html|svg}
```

- 缓存键 = `commit_hash`——同一 commit 始终产生相同输出。
- 缓存未命中 → MarkdownBackend 或 TypstBackend 编译 → 写入缓存。
- 清理缓存：`rm -rf ~/.peerpedia/cache/`。
- 编译器升级：删除缓存，下次请求触发重编译。
- Markdown: ~50ms。Typst: ~500ms。缓存命中: ~1ms。

### 5.3 支持格式

| 格式 | 桌面版 (Phase 1) | Web 版 (Phase 2+) |
|--------|------------------|----------------|
| Markdown → HTML | 客户端 (marked + KaTeX) | 客户端 (marked + KaTeX) |
| Typst → SVG | Tauri sidecar CLI | 服务端编译器 |
| Typst → PDF | Tauri sidecar CLI | 服务端编译器 |

---

## 6. API 设计

### 6.1 REST 端点

| 方法 | 路径 | 说明 |
|--------|------|------|
| POST | `/api/v1/auth/register` | 注册 |
| POST | `/api/v1/auth/login` | 登录（返回 JWT） |
| GET | `/api/v1/articles` | 文章列表（状态/作者/分页筛选） |
| POST | `/api/v1/articles` | 创建文章（Git commit + DB 元数据） |
| GET | `/api/v1/articles/{id}` | 文章详情 |
| PUT | `/api/v1/articles/{id}` | 更新文章 |
| GET | `/api/v1/articles/{id}/source` | 原始 Markdown/Typst 源码 |
| GET | `/api/v1/articles/{id}/history` | Git 提交历史 |
| GET | `/api/v1/articles/{id}/diff/{h1}/{h2}` | 逐行对比 |
| POST | `/api/v1/articles/{id}/fork` | Fork 文章 |
| POST | `/api/v1/articles/{id}/publish` | 发布到沉淀池 |
| GET | `/api/v1/articles/{id}/reviews` | 评审列表 |
| POST | `/api/v1/articles/{id}/reviews` | 提交/更新评审 |
| POST | `/api/v1/articles/{id}/reviews/{rid}/messages` | 发送讨论回复 |
| GET | `/api/v1/articles/{id}/citations` | 引用图 |
| POST | `/api/v1/citations/click` | 记录引用点击 |
| POST | `/api/v1/articles/{id}/merge-proposals` | 创建合并提案 |
| GET | `/api/v1/search` | 全文搜索 |
| POST | `/api/v1/compile-preview` | 编译 Markdown/Typst → HTML/SVG |
| GET | `/api/v1/users` | 用户列表 |
| GET | `/api/v1/users/{id}` | 用户资料 + 关注/信誉 |
| POST | `/api/v1/users/{id}/follow` | 关注用户 |
| DELETE | `/api/v1/users/{id}/follow` | 取消关注 |
| GET | `/api/v1/pool` | 沉淀池动态 |
| GET | `/api/v1/feed` | 关注动态 |

### 6.2 P0 重构 API 变更

| 变更 | 旧 | 新 |
|--------|-----|-----|
| ArticleDetail 响应 | 含 `compiled_output`, `compiled_pages` | 已移除——使用 `/compile-preview` |
| 文章作者 | JSON 中的 `authors: list[str]` | `ArticleAuthor` 关联表（API 仍返回 `list[AuthorInfo]`） |
| 评审讨论 | JSON 中的 `thread: list[dict]` | `ReviewMessage` 表（API 仍返回 `list[ThreadMessageOut]`） |
| 引用边 | 含 `forward_prob`, `backward_prob` | 已移除 |
| MergeProposal | 含 `thread` | 已移除（推迟至 Phase 2） |

---

## 7. 测试

### 7.1 测试数量

| 套件 | 测试数 | 框架 |
|-------|-------|-----------|
| 后端 | 120 | pytest |
| 前端 | 252 | vitest |
| Rust | 53 | cargo test |

### 7.2 CI 流水线

3 种语言共 10 个 job：pytest、ruff、mypy、eslint、vitest、vue-tsc、vite verify、clippy、rustfmt、cargo test。全部阻塞 PR 合并。配置：`.github/workflows/ci.yml`。

---

## 8. 部署与迁移

### 8.1 数据库迁移

从旧 schema（JSON 字段）升级时，运行：

```bash
python scripts/migrate_architecture.py --db sqlite:///peerpedia.db
```

脚本幂等——可安全多次运行。执行：
1. 创建 `article_authors` 和 `review_messages` 表
2. 将 JSON 数据迁移到关联表
3. 重建不含废弃列的 `articles`、`reviews`、`merge_proposals`、`citations` 表

### 8.2 未来：SQLite → PostgreSQL

SQLite 是 Phase 1 数据库。Phase 2 将迁移至 PostgreSQL。无业务逻辑依赖 SQLite 特性。

---

### 8.3 存储模型 — 待决策

**当前设计：** 服务器在 `~/.peerpedia/articles/{uuid}/` 下为每篇文章存储完整 Git 仓库。文章 ID 为 UUID。

**待决策：** 服务器是否应只存储 repo ID（内容哈希）而非完整仓库？这样做可以：
- 顺利过渡到 P2P——文章通过内容哈希寻址，仓库按需从分布式存储拉取。
- 减少服务器存储负担——按内容哈希去重，服务器仅保留元数据 + 哈希指针。

**权衡：** UUID 当前最简单。内容哈希寻址是 Phase 2/3 的正确原语，但需要改动路由、解析和同步层。决策推迟至 Phase 2。

## 9. 配置

所有可调参数位于 `core/peerpedia_core/config/params.py`：

- `sink.new_article_default_days` — 新文章默认池内天数
- `sink.edit_article_default_days` — 编辑后默认池内天数
- `sink.max_days` — 最大延期天数
- `score.no_review_penalty()` — 零社区评审惩罚
- `score.score_to_sink_multiplier(avg)` — 平均分映射到沉淀时长

---

*最后更新: 2026-06-07 · 120 后端测试 · 252 前端测试 · 53 Rust 测试 · 9 个 DB 实体*
