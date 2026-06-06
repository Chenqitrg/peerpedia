# PeerPedia（知诸网）— 完整设计文档

> 2026-06-06 · 含全部已实现功能 · 一份文档即可复刻

---

## 1. 愿景

PeerPedia 是学术出版的 GitHub。文章是 git 仓库，评审是社区评分，质量通过沉淀池自然筛选。

**终极目标：** 取代 arXiv 和传统学术期刊。让 Wikipedia 的开放协作 + arXiv 的预印本规模 + 期刊的同行评审质量，三者合一。

**当前阶段：** 用科普和历史内容打磨产品，从内容消费市场切入，再向上渗透学术圈。

### 竞争差异

| | 传统期刊 | arXiv | Wikipedia | PeerPedia |
|---|---|---|---|---|
| 质量控制 | 编辑垄断 | 无 | 编辑战 | **社区评分 + 沉淀池** |
| 发表速度 | 6-18 月 | 即时 | 即时 | 即时 → 沉淀 → 出池 |
| 版本历史 | 无 | v1/v2 | 有 | **Git 全历史 + diff** |
| 评分 | 无 | 无 | 无 | **五维 O/R/C/P/I** |
| 收费 | APC 数千美元 | 免费 | 免费 | 免费 |
| 内容许可 | 出版社持有 | 作者保留 | CC BY-SA | CC BY-SA 4.0 |

---

## 2. 架构

PeerPedia 采用双层架构：Tauri 桌面版负责离线写作和本地存储，Web 版负责社区协作和评审机制。两者共享相同的 Vue 3 前端。

```
Phase 1（冷启动 — Tauri Desktop）
┌──────────────────────────────────────────────────────────┐
│  Vue 3 → IPC → Rust commands → SQLite + Git（本地）       │
│  离线写作、本地编译、版本控制                               │
└──────────────────────────────────────────────────────────┘
                         ↕ 可选同步（Slice 2）

Phase 2+（社区 — Web）
┌──────────────────────────────────────────────────────────┐
│  Vue 3 SPA → REST → FastAPI → SQLite + Git（服务器）       │
│  沉淀池、社区评审、信誉系统、AI 交融                          │
└──────────────────────────────────────────────────────────┘
```

### 技术栈

| 层 | 桌面版 (Phase 1) | Web 版 (Phase 2+) |
|---|---|---|
| Shell | Tauri 2.x (Rust) | — |
| 前端 | Vue 3 + TS + Vite + Tailwind | Vue 3 + TS + Vite + Tailwind |
| 后端 | Rust (rusqlite, bcrypt, libgit2) | Python 3.12+, FastAPI, SQLAlchemy |
| 存储 | SQLite + Git 仓库（本地） | SQLite + Git 仓库（服务器） |
| 编译 | Typst CLI, Python Markdown | Typst CLI, Python Markdown |
| 认证 | bcrypt + SQLite（本地账号） | JWT（bcrypt, 24h 过期） |

### 项目结构

```
peerpedia/
├── core/peerpedia_core/        # 业务逻辑库（无 Web 依赖）
│   ├── config/params.py        # 可调参数（沉池天数、评分权重等）
│   ├── storage/db/             # SQLAlchemy ORM（7 实体）+ CRUD（6 模块）
│   ├── storage/git_backend.py  # Git 操作（init/commit/history/diff/fork）
│   ├── storage/compiler.py     # Markdown/Typst 编译后端
│   ├── workflow/               # scoring, sedimentation, reputation
│   └── types/                  # scores, messages
├── backend/peerpedia_api/      # FastAPI REST API
│   ├── main.py                 # 入口 + CORS + background task（auto-publish）
│   ├── routes/                 # 11 路由模块
│   ├── schemas/                # Pydantic 请求/响应模型
│   ├── deps.py                 # FastAPI 依赖注入
│   └── helpers.py              # 共享工具函数
├── frontend/                   # Vue 3 SPA + Tauri
│   ├── src/
│   │   ├── api/                # Axios API 模块 + types.ts
│   │   ├── components/         # 11 组件
│   │   ├── composables/        # useBookmarkToggle, useTauri, useStatusMap
│   │   ├── pages/              # 10 页面（含 LoginPage）
│   │   ├── router/             # Vue Router + auth guards
│   │   ├── stores/             # Pinia（user, article, pool）
│   │   └── utils/math.ts       # KaTeX 渲染
│   └── src-tauri/              # Tauri Rust backend
│       └── src/
│           ├── main.rs         # Tauri entry
│           ├── commands.rs     # IPC handlers
│           ├── local_auth.rs   # 本地账号 CRUD + bcrypt
│           └── local_store.rs  # 草稿 + 文章缓存 SQLite
├── seed.py                     # 演示数据（23 users）
├── docs/DESIGN.md              # 本文档
└── docs/api-contract.json      # OpenAPI 规范
```

---

## 3. 数据模型

### 3.1 Article（文章）

```python
class Article(Base):
    id = Column(String, primary_key=True, default=uuid4)
    title = Column(String, default="")
    abstract = Column(String, nullable=True)
    keywords = Column(JSONList)          # ["physics", "quantum"]
    categories = Column(JSONList)        # ["theory", "experiment"]
    status = Column(String, default="draft")  # draft | sedimentation | published
    score = Column(JSONDict)             # {originality: 4.5, rigor: 3.2, ...} — 缓存最新 commit 评分
    compiled_format = Column(String)     # "html" | "svg"
    compiled_output = Column(String)     # 编译后的 HTML/SVG
    compiled_pages = Column(JSONList)    # 多页 SVG 时使用
    sink_start = Column(DateTime)
    sink_duration_days = Column(Integer, default=7)
    sink_extended_count = Column(Integer, default=0)
    forked_from = Column(String, nullable=True)  # 派生来源 article_id
    fork_count = Column(Integer, default=0)
    authors = Column(JSONList, default=[])       # [user_id, ...]
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
```

**文章状态机：** `draft → sedimentation → published`
- draft：仅作者自己可见（个人页）
- sedimentation：进入沉淀池，关注网络内可见
- published：公开发布

### 3.2 Review（评审）

```python
class Review(Base):
    id = Column(String, primary_key=True)
    article_id = Column(String, ForeignKey("articles.id"))
    commit_hash = Column(String)           # 关联到特定 commit
    reviewer_id = Column(String, ForeignKey("users.id"))
    scope = Column(String)                 # "pool"（池内匿名）| "published"（实名）
    scores = Column(JSONDict)              # FiveDimScores
    contributions = Column(JSONDict, nullable=True)  # 仅自评：{author_id: {dim: ratio}}
    thread = Column(JSONList, default=[])  # [{author_id, author_name, content, created_at}]
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    
    __table_args__ = (UniqueConstraint("article_id", "reviewer_id", "scope", "commit_hash"),)
```

**评审规则：**
- 每人对同一篇文章的同一 commit、同一 scope 只能有一条评审
- scope 分离：同一人可以有一条 pool（匿名）+ 一条 published（实名）
- 文章出池后，pool 评审冻结不可修改
- 池内评审匿名名**永不泄露**
- 自评始终显示实名

### 3.3 User（用户）

```python
class User(Base):
    id = Column(String, primary_key=True)
    username = Column(String, unique=True)       # 登录标识
    password_hash = Column(String)               # bcrypt
    email = Column(String, nullable=True)
    name = Column(String)                        # 显示名
    anonymous_name = Column(String, default="")  # 池内固定匿名名
    affiliation = Column(String, default="")
    expertise = Column(JSONList, default=[])
    avatar_url = Column(String, nullable=True)
    contact = Column(String, nullable=True)
    reputation = Column(JSONDict, default={})    # {professionalism, objectivity, collaboration, pedagogy}
    created_at = Column(DateTime)
```

### 3.4 其他实体

**Follow:** `(follower_id, followed_id)` — 关注关系

**Bookmark:** `(user_id, article_id)` — 收藏关系

**MergeProposal:** fork 文章发起合并请求。字段：`fork_article_id`, `target_article_id`, `proposer_id`, `status`（open/accepted/rejected）, `thread`

**Citation:** `(from_article_id, to_article_id, forward_prob, backward_prob)` — 引用关系图

---

## 4. 核心机制

### 4.1 Git 驱动的文章管理

每篇文章是 `~/.peerpedia/articles/{id}/` 下的独立 git 仓库。

**操作映射：**
- 创建文章 → `init_article_repo(id)` + 首次 commit
- 编辑 → `commit_article(repo, msg, author, email)` → 新 commit
- 派生 → `shutil.copytree(src, dst)` + 新 DB record（authors=[当前用户], forked_from=原文id）
- 历史 → `get_commit_history(repo)` → 返回 commit 列表
- Diff → `git diff hash1 hash2` → diff2html 渲染
- 回滚 → `commit_article(repo, msg, author, email)` 写入回滚内容

**文章内容文件：** `article.md` 或 `article.typ`

### 4.2 五维评分

所有评审使用五个维度，每维 0-5 分：

| 维度 | 衡量 |
|---|---|
| **O**riginality（原创性）| 贡献有多新颖？ |
| **R**igor（严谨性）| 方法和论证是否可靠？ |
| **C**ompleteness（完整性）| 工作是否详尽、自包含？ |
| **P**edagogy（教学性）| 写作是否清晰易懂？ |
| **I**mpact（影响力）| 对该领域有多重要？ |

**评分计算：** 每个 commit 独立评分。社区评审权重 0.85，自评权重 0.15。`compute_article_score_for_commit()` 按 commit_hash 筛选评审，加权平均。

### 4.3 沉淀池

新文章/编辑进入沉淀池，等待社区评审。评分影响出池速度：

- 初始天数：新文章 7 天，编辑 3 天
- 高分缩短时间（最低 2 天），低分延长时间（最长 180 天）
- 作者可自行延期（每次 +7 天，累计不超过 180 天）
- 出池时若无社区评审 → 每维扣分（penalty）
- 出池后状态变为 published，pool 评审冻结
- 后台每 60 秒自动扫描并发布到期文章

**可见范围：** 仅关注网络内（following + followers）

**排序：** 按剩余天数降序——快出池的在下面（视觉上"沉下去"）

### 4.4 盲审与身份保护

| 场景 | 显示名称 |
|---|---|
| 池内评审（scope=pool）| `anonymous_name`（固定匿名名，**永不泄露**）|
| 池外评审（scope=published）| `name`（实名）|
| 自评 | 始终显示 `name`（实名，作者身份已公开）|

- 同一人对同一文章可同时有 pool（匿名）+ published（实名）两条记录
- 文章出池后 pool 评审冻结，不可修改
- published 评审是新的独立记录
- 自评置顶，accent 色左边框

### 4.5 信誉系统（后端就绪，前端待接入）

- 4 维信誉：professionalism, objectivity, collaboration, pedagogy
- 文章 5 维评分 → 映射 → 作者 4 维信誉
- 状态加权：published(1.0) > sedimentation(0.7) > draft(0.3)
- 新评分与旧信誉按 0.3 权重平滑融合
- 评审权重 = 1.0 + author_weight × (avg_rep - 3.0) / 2.0

---

### 4.6 离线优先设计（Phase 1 — Tauri Desktop）

**设计原则：** 本地操作立即完成，远程同步异步进行。类似 GitHub Desktop——commit 不等待网络，push 稍后处理。

**本地账号系统：**
- bcrypt 密码哈希 + SQLite 存储
- 多账号切换（同一设备上 alice/bob 各自登录）
- 远程绑定可选——本地账号永远可用，绑定服务器账号是增量操作
- 离线状态下灰色头像 + "离线"标签，在线状态彩色头像

**草稿系统：**
- 多草稿管理（不限数量，SQLite 持久化）
- Markdown / Typst 格式切换
- 草稿隔离——不同账号互相不可见
- 从 Web 版的 localStorage 迁移到 Tauri 的 SQLite

**文章缓存：**
- 已发布文章缓存到本地 SQLite（离线可读）
- 缓存是只读快照——编辑需要在线 fork

**Slice 1/2 范围：**

| Slice | 包含 | 推迟 |
|-------|------|------|
| **Slice 1** | 本地账号 CRUD、草稿 save/load/list、文章缓存、LoginPage、useTauri、NavBar 连接状态 | — |
| **Slice 2** | Typst 本地编译、Sync engine、后端 `/auth/bind` + `/sync/batch`、Git 引擎 | — |
| **Slice 3** | P2P 分布式存储、离线评审、AI 辅助写作 | — |

**IPC 设计：** Vue 通过 `useTauri()` composable 调用 Rust，Web 模式下 composable fallback 为空操作。Vue 组件不感知底层差异。

## 5. 功能规范

### 5.1 首页 `/`

**未登录：** 品牌页 — PeerPedia logo + 标语 + Sign In / Create Account 按钮

**已登录：** 关注动态 Feed
- 来源：关注用户的新文章（sedimentation + published，不含 draft）
- 每篇文章显示 ArticleCard（标题/作者/预览/评分/状态/进度条/操作按钮）
- 分页（页码模式）
- 登录后自动加载；通过 AuthModal 登录后自动刷新 Feed

### 5.2 编辑页 `/edit` `/edit/:id` 🔒

参照 Overleaf 的左右分栏布局。**全宽**（突破全局 max-w-content）。

**工具栏：**
- MD / Typst 格式切换
- 💾 Save — 保存草稿到后端（`publish: false`），状态保持 draft
- 🚀 Publish — 弹出 self-review 面板 → 提交到沉淀池（`publish: true`）
- 下载源码 / 下载 PDF

**Self-review 面板（发布时）：**
- Commit message（**必填**，不写不给过）
- 五维评分星星（O/R/C/P/I，可点击）
- 标题/摘要/关键词/领域
- "Publish to Pool" 按钮

**分隔条：** 可拖拽（mousedown/mousemove/mouseup），范围 20%-80%

**编译预览：** `POST /compile-preview` → KaTeX 渲染（Markdown）或 SVG（Typst）

**暂存：** 自动存 localStorage，恢复草稿

### 5.3 文章页 `/articles/:id`

**上方元数据栏（窄）：**

| 元素 | 行为 |
|---|---|
| 标题 | 纯文本 |
| 作者列表 | 可点击 → 用户页 |
| 状态标签 | draft/sedimentation/published |
| 5 维评分 | 数字显示 |
| History | → 历史页 |
| Fork | → fork API → 编辑页 |
| Edit | 仅作者可见 → 编辑页 |
| Extend | 仅作者 + 沉淀中可见 → 延期 7 天 |
| Source / PDF | 下载 |
| Bookmark | toggle 星形 |

**下方双选项卡：**
- **Body** — 编译后的 HTML/SVG（含 KaTeX 渲染）
- **Comments** — 完整评审系统（见 5.4）

### 5.4 评审系统

**提交评审：** 非作者登录用户 → 五维星星 + 文本框 + Submit Review

**评审卡片：**
- 显示评审人名称（匿名/实名/Author）、五维分数数字、时间
- 自己的评审置顶（accent 色左边框 + "(you)" 标签）
- Hover 分数 → 展开为可编辑星星，移开恢复数字
- 修改分数即时生效（乐观更新）

**Thread 对话：**
- 每条评审下方有 Thread 下拉（Chevron 展开/折叠）
- iMessage 风格聊天气泡（作者左对齐深色，回复者右对齐 accent 色）
- 参与者：文章作者 + 该评审的评审人
- 旁观者只读，看到 "Only the author and reviewer can participate in this thread"
- 自己的评审无 Thread 时显示 "Start a conversation..." 输入框

### 5.5 沉淀池 `/pool` 🔒

关注网络内的 sedimentation 文章。ArticleCard 列表 + 进度条（已过/总天数）。按剩余天数降序。

### 5.6 用户页 `/users/:id`

**上方：** 头像 + 姓名 + 机构 + 4 维声誉 + 粉丝/关注数（可展开） + Edit Profile（仅本人，disabled "Coming soon"）

**下方：** 该用户的所有文章（含 draft，仅本人可见）

### 5.7 历史页 `/articles/:id/history`

commit 时间线图 + 点击两个节点 → diff2html side-by-side diff + 回滚按钮

### 5.8 引用页 `/articles/:id/citations`

引用 DAG：References（本文引用的） + Cited by（引用本文的）。点击跳转。

### 5.9 搜索 `/search?q=`

全文搜索，ArticleCard 列表。空状态/加载/错误全处理。

### 5.10 Schools `/schools`

全局用户目录，按文章数降序。头像、机构、声誉、专长标签、Follow 按钮。

### 5.11 书签 `/bookmarks` 🔒

收藏的文章列表，ArticleCard。切换书签即时乐观更新（失败回滚）。

---

## 6. API 契约

所有端点前缀：`/api/v1`

### 认证

| 方法 | 端点 | 认证 | 说明 |
|------|------|------|------|
| POST | `/auth/register` | 无 | body: `{username, password, email, name}` → `{user, token}` |
| POST | `/auth/login` | 无 | body: `{username, password}` → `{user, token}` |
| GET | `/auth/me` | Bearer | → `{user}` |

### 文章

| 方法 | 端点 | 认证 | 说明 |
|------|------|------|------|
| GET | `/articles` | 可选 | `?status=&author_id=&page=&size=` |
| POST | `/articles` | Bearer | 创建 + 发布到池 |
| GET | `/articles/{id}` | 可选 | 详情（含 score, sink_eta, is_bookmarked） |
| PUT | `/articles/{id}` | Bearer | 编辑。`publish: true` 进池，`false` 保持 draft |
| GET | `/articles/{id}/source` | 无 | 原始源码 |
| GET | `/articles/{id}/history` | 无 | commit 列表（含 parents + per-commit score） |
| GET | `/articles/{id}/diff/{h1}/{h2}` | 无 | diff_text + files |
| POST | `/articles/{id}/fork` | Bearer | 派生 → `{id, forked_from, status: "draft"}` |
| POST | `/articles/{id}/rollback/{hash}` | Bearer | 回滚 |
| PUT | `/articles/{id}/sink-extension` | Bearer | body: `{extra_days}` |
| GET | `/articles/{id}/has-forked` | Bearer | → `{has_forked, fork_article_id}` |
| GET | `/articles/{id}/download/source` | 无 | 下载源码文件 |
| GET | `/articles/{id}/download/pdf` | 无 | Typst→PDF, Markdown→HTML |

### 评审

| 方法 | 端点 | 认证 | 说明 |
|------|------|------|------|
| GET | `/articles/{id}/reviews` | 无 | 评审列表（含 reviewer_name + author_name） |
| POST | `/articles/{id}/reviews` | Bearer | 创建/更新。scope 由后端根据 article.status 判断 |
| POST | `/articles/{id}/reviews/{rid}/messages` | Bearer | Thread 回复。body: `{content}` |

### 社交

| 方法 | 端点 | 认证 | 说明 |
|------|------|------|------|
| GET | `/feed` | 可选 | 关注人文章（仅 sedimentation + published） |
| GET | `/pool` | 可选 | 关注网络沉淀池 |
| GET/POST/DELETE | `/bookmarks` | Bearer | 收藏列表/添加/删除 |
| GET | `/users` | 无 | 用户列表（含 article_count + reputation） |
| GET | `/users/{id}` | 无 | 用户详情 |
| PUT | `/users/{id}` | Bearer | 编辑资料 |
| GET | `/users/{id}/followers` | 无 | 粉丝列表 |
| GET | `/users/{id}/following` | 无 | 关注列表 |
| POST | `/users/{id}/follow` | Bearer | 关注 |
| DELETE | `/users/{id}/follow` | Bearer | 取关 |

### 编译与搜索

| 方法 | 端点 | 认证 | 说明 |
|------|------|------|------|
| POST | `/compile-preview` | 无 | body: `{content, format}` → HTML/SVG |
| POST | `/compile-download` | 无 | body: `{content, format}` → 文件下载 |
| GET | `/search?q=` | 无 | 全文搜索 |

### 合并

| 方法 | 端点 | 认证 | 说明 |
|------|------|------|------|
| POST | `/articles/{id}/merge-proposals` | Bearer | 发起合并请求 |
| GET | `/articles/{id}/merge-proposals` | 无 | 合并请求列表 |
| POST | `/articles/{id}/merge-proposals/{pid}/accept` | Bearer | 接受合并 |
| POST | `/articles/{id}/merge-proposals/{pid}/reject` | Bearer | 拒绝合并 |

### Tauri IPC 命令（Phase 1 桌面版）

所有 IPC 命令通过 `useTauri()` composable 调用，底层是 `invoke()`。Web 模式下 composable 返回 no-op。

| IPC 命令 | 参数 | 返回 | 说明 |
|----------|------|------|------|
| `create_account` | `{username, password, email, name}` | `{id, username}` | 创建本地账号 |
| `login` | `{username, password}` | `{id, username}` | 本地登录验证 |
| `list_accounts` | — | `[{id, username}]` | 列出本机所有账号 |
| `save_draft` | `{id, account_id, title, content, format}` | `{id, updated_at}` | 保存/更新草稿 |
| `list_drafts` | `{account_id}` | `[{id, title, updated_at}]` | 列出账号草稿 |
| `get_draft` | `{id}` | `{id, title, content, format}` | 获取草稿内容 |
| `delete_draft` | `{id}` | `{ok: true}` | 删除草稿 |
| `cache_article` | `{id, article_json}` | `{ok: true}` | 缓存已发布文章 |
| `get_cached_article` | `{id}` | `{article_json} or null` | 读取缓存文章 |

---

## 7. 前端设计系统

**设计哲学：** Cold Academic Minimal — 暗色、严肃、突出内容

**颜色：**
- 页背景 `#0d1117`，卡片 `#161b22`，分割线 `#21262d`
- 主文字 `#b0b8c4`，次要文字 `#8b949e`
- accent `#7b8c9e`（钢蓝灰），success `#5c7c6e`
- 评审星星金色 `#f0c040`

**字体：** EB Garamond（标题） + Inter（正文） + JetBrains Mono（代码）

**组件类（main.css）：** `.card`, `.card-interactive`, `.btn`, `.btn-primary`, `.btn-outline`, `.btn-ghost`, `.btn-sm`, `.input`, `.label`, `.badge-*`, `.skeleton`, `.prose-custom`

**动画：** `animate-fade-in`, `animate-slide-up`；尊重 `prefers-reduced-motion`

---

## 8. 路由

| 路径 | 页面 | 认证 |
|------|------|------|
| `/` | HomePage | 无 |
| `/edit` | EditorPage（新建）| 🔒 |
| `/edit/:id` | EditorPage（编辑）| 🔒 |
| `/articles/:id` | ArticlePage | 无 |
| `/articles/:id/history` | HistoryPage | 无 |
| `/articles/:id/citations` | CitationsPage | 无 |
| `/users/:id` | UserPage | 无 |
| `/schools` | SchoolsPage | 无 |
| `/pool` | PoolPage | 🔒 |
| `/search?q=` | SearchPage | 无 |
| `/bookmarks` | BookmarksPage | 🔒 |

路由守卫：未登录访问 🔒 路由 → 重定向首页 + 弹出 AuthModal

---

## 9. 测试

```bash
# 后端 156 tests
.venv/bin/python -m pytest backend/ -q

# 前端 108 tests
cd frontend && npx vitest run
```

---

## 10. 运行

```bash
# Web 后端
.venv/bin/python -c "
from peerpedia_core.storage.db.engine import get_engine, init_db
init_db(get_engine('sqlite:///peerpedia.db'))
"
python seed.py                    # 23 位科学家，密码 666666
uvicorn peerpedia_api.main:app --port 8080 --reload

# Web 前端
cd frontend && npm run dev        # → http://localhost:5173

# Tauri 桌面版（开发模式）
cd frontend && npm run tauri dev  # → Tauri 窗口
```

### Demo 用户（23 位科学家，密码 666666）

| 用户名 | 用户名 | 用户名 |
|--------|--------|--------|
| einstein | feynman | chandra |
| bohr | heisenberg | schrodinger |
| dirac | born | noether |
| lovelace | vonneumann | turing |
| shannon | hopper | curie |
| franklin | hodgkin | crick |
| cajal | goldmanrakic | popper |
| kuhn | putnam | |

---

## 11. 路线图

| 优先级 | 功能 | 阶段 |
|--------|------|------|
| **P0** | Tauri Slice 1：本地账号 + 离线编辑器 + 文章缓存 | Phase 1 |
| 中 | Tauri Slice 2：Typst 编译 + Sync Engine + 远程绑定 | Phase 1 |
| 中 | 信誉加权评分（后端已就绪，前端待接入） | Phase 2 |
| 低 | Profile 编辑页 | Phase 2 |
| 延后 | P2P 分布式存储（IPFS） | Phase 3 |
| 延后 | AI 辅助评审/写作 | Phase 3 |
| 延后 | LaTeX 支持 | Phase 3 |
| 延后 | 生产部署（Docker, CI/CD, 公网 URL） | Phase 3 |

---

## 12. 开发注意事项

- **模板修改后必须重启服务器** — uvicorn --reload 不监听 .html
- **ORM 加列会清空 SQLite DB** — 改完跑 `python seed.py` 恢复
- **新 UI 组件必须同时写 CSS** — 否则渲染无样式
- **Markdown 数学公式处理顺序：** `_protect_math → _render_markdown → _restore_math`
- **v-html 不执行 `<script>`** — KaTeX 必须在客户端用 `renderMathInHtml()` 手动渲染
- **ruff --fix 会删除 facade re-exports** — import 行加 `# noqa: F401`
- **seed.py 使用相对路径 `sqlite:///peerpedia.db`** — 必须在项目根目录运行
- **Tauri IPC 命令通过 `useTauri()` composable 调用** — Web 模式下 composable 返回 no-op，不影响现有 Web 功能
- **Vue 组件不感知 Tauri/Web 差异** — 所有平台判断封装在 composable 中
