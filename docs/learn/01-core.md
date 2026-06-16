# Core 模块

> Python 层。PeerPedia 的大脑——DB 模型、业务逻辑、Git 存储、编译管线都在这里。

## 一句话职责

**管理所有数据和业务规则。** backend 只做 HTTP 翻译，frontend 只做 UI，真正的决策全在 core。

## 模块地图

```
core/peerpedia_core/
├── storage/
│   ├── db/              # SQLAlchemy 模型 + CRUD
│   │   ├── models.py    # 7 个实体 + 1 个 join table
│   │   ├── engine.py    # DB 连接 + JSONDict/JSONList 类型
│   │   ├── crud_article.py
│   │   ├── crud_user.py
│   │   ├── crud_review.py
│   │   ├── crud_bookmark.py
│   │   ├── crud_citation.py
│   │   ├── crud_merge.py
│   │   └── session_utils.py
│   ├── git_backend.py   # 每篇文章一个独立 git repo
│   └── compiler.py      # Typst + Markdown 编译后端
├── workflow/
│   ├── scoring.py       # 文章评分聚合（加权平均）
│   ├── sedimentation.py # 沉淀池逻辑（限时评审 → 自动发布）
│   └── reputation.py    # 用户信誉计算（文章分 → 信誉分）
├── config/
│   └── params.py        # 所有可调参数（单一事实来源）
└── types/
    └── scores.py        # FiveDimScores + ReputationScores
```

## 依赖关系（分层架构）

```
        ┌───────────────────┐
        │  backend/routes/  │  ← HTTP 层（不在 core 里，但依赖 core）
        └────────┬──────────┘
                 │ 调用
                 ▼
   ┌─────────────────────────────┐
   │         workflow/           │  ← 业务逻辑层
   │  scoring  sedimentation     │
   │  reputation                 │
   └────────────┬────────────────┘
                │ 依赖（调 CRUD、调 Git）
                ▼
   ┌─────────────────────────────┐
   │         storage/            │  ← 数据持久化层
   │  ┌──────┐ ┌──────┐ ┌─────┐ │
   │  │ db/  │ │ git_ │ │comp-│ │  ← 三个子模块互不依赖
   │  │models│ │backend│ │iler │ │
   │  │crud_*│ │.py   │ │.py  │ │
   │  └──────┘ └──────┘ └─────┘ │
   └────────────┬────────────────┘
                │ 依赖（读配置、用类型）
                ▼
   ┌─────────────────────────────┐
   │  config/params.py           │  ← 所有可调参数（单例）
   │  types/scores.py            │  ← 纯数据类型（无外部依赖）
   └─────────────────────────────┘
```

箭头约定：`上层 ──► 下层` = 上层依赖下层（上层 import 下层、上层调下层）。

- **backend 依赖 core**：路由调 workflow 和 storage
- **workflow 依赖 storage**：scoring/sedimentation/reputation 调 CRUD 和 Git
- **storage 内部互不依赖**：db、git_backend、compiler 各自独立
- **config/types 在最底层**：被所有层依赖，自身无外部依赖

## 7 个实体 + 1 个 join table：各自存在哪

```
┌─────────────────────────────────────────────────────────┐
│                    Git Repos                            │
│  ~/.peerpedia/articles/{id}/                            │
│                                                         │
│  ★ 文章内容（article.md / article.typ）                  │
│  ★ 评审数据（reviews/{id}/scores.json + thread.md）       │
│  ★ 文章分数（从 reviews 聚合得出，存在 scores.json）      │
│  ★ 完整历史（git log）                                   │
│  ★ 作者信息（git commit author）                         │
└─────────────────────────────────────────────────────────┘
                        ↕ DB 是缓存/索引
┌─────────────────────────────────────────────────────────┐
│                    SQLite DB                            │
│                                                         │
│  users —— 用户账号、信誉分            ← 只在 DB          │
│  articles —— 文章元数据、score 缓存    ← 内容在 Git       │
│  article_authors —— 作者关联          ← 从 Git 重建      │
│  reviews —— 评审缓存                  ← 源文件在 Git     │
│  follows —— 关注关系                  ← 只在 DB          │
│  bookmarks —— 书签                    ← 只在 DB          │
│  citations —— 引用关系                ← 只在 DB          │
│  merge_proposals —— 合并提议          ← 只在 DB          │
└─────────────────────────────────────────────────────────┘
```

核心规则：
- **Git 是事实来源（Source of Truth）**——文章内容、评审、分数、历史的权威版本在 Git
- **DB 是索引/缓存**——用于快速查询、排序、过滤，可以从 Git 重建
- **users/follows/bookmarks 是纯 DB 数据**——没有 Git 对应物

```

### Article（文章）
- **内容存在 Git 里**（`~/.peerpedia/articles/{id}/`），数据库只存元数据
- 状态机：`draft → sedimentation → published`
- 评分存在 `score` JSON 字段（FiveDimScores 的 dict）
- `compiled_format/output/pages` 是编译缓存——issue #81 计划移除
- `forked_from` + `fork_count` 支持 fork 工作流
- `last_author_rebuild_hash` 追踪 Git 作者同步状态

### ArticleAuthor（作者关联）
- **独立的 join table**，不是 JSON 字段。这是从 gpt_review P0-2 修过来的
- 复合主键 `(article_id, author_id)`
- `position` 字段控制作者排序

### User（用户）
- `username` 是登录标识，unique
- `password_hash` 是 bcrypt
- `reputation` 存为 JSON dict（ReputationScores）

### Review（评审）
- 唯一约束：`(article_id, reviewer_id, scope, commit_hash)` —— 同一个 reviewer 对同一个 commit 只能评一次
- `scores` 是 FiveDimScores dict
- `thread` 是 JSON list——**这是一个已知问题（gpt_review P0-1），JSON 列不能查询、不能索引**
- `contributions` 记录每个作者的贡献比例

### Follow / Bookmark
- 标准的多对多关联表
- Follow 是用户关注用户，Bookmark 是用户收藏文章

### MergeProposal
- fork 合并工作流：作者 A fork 了作者 B 的文章，改完发起 merge proposal
- `status: open → accepted/rejected`
- `thread` 同样是 JSON list

### Citation
- 文章之间的引用关系
- `forward_prob` / `backward_prob` 表示引用方向和概率

## 双层存储：Git 是事实来源，DB 是索引

这是 PeerPedia 最核心的架构决策（ADR-007）。

| 存什么 | 权威来源 | 索引/缓存 | 为什么 |
|--------|----------|-----------|--------|
| 文章内容 | Git repo | — | 不可变、可追溯、可 fork |
| 评审 + 分数 | Git repo（`scores.json`） | DB（reviews 表、articles.score） | 不可变审计 trail、可从 Git 重建 DB |
| 作者关联 | Git commit author | DB（article_authors 表） | Git 是权威、DB 方便查询 |
| 用户/关注/书签 | DB | — | 纯关系数据，不需要版本历史 |

### Git → DB 的数据流

```
用户提交评审
  → _write_review_to_git_blocking()
    → 写 scores.json + thread.md 到 Git repo
    → git commit（不可变记录）
  → 成功后才写 DB
    → crud_review.upsert_review()（缓存）
    → compute_article_score() → 更新 Article.score（缓存）
    → compute_author_reputation() → 更新 User.reputation（DB only）
```

**Git-first 原则**：如果 Git 写入失败，DB 不写。DB 数据可以从 Git 重建。

- 每篇文章一个独立 repo，存在 `~/.peerpedia/articles/{id}/`
- bundle sync：用 `git bundle` 做增量同步（create → HTTP 传输 → apply）
- merge 走 `git merge --ff-only`，冲突抛 `MergeConflictError`

## 三大 workflow

### 1. Scoring（评分）

```
Review.scores (5维) × reviewer_weight
        ↓
  compute_article_score()
        ↓
  Article.score (加权平均)
```

- 自评权重 0.15，社区评审权重 0.85
- reviewer_weight 来自信誉分：`1.0 + 0.2 × (avg_rep - 3.0) / 2.0`
  - 信誉 5.0 的 reviewer，评分权重 1.2
  - 信誉 1.0 的 reviewer，评分权重 0.8
- 所有 commit 的 review 都参与聚合（编辑不再清空评分）

### 2. Sedimentation（沉淀池）

```
draft → 作者点"提交评审" → sedimentation（限时）
        ↓
   池内接受社区评审
        ↓
   到期自动发布 → published
```

- 新文章默认 7 天沉淀期，编辑后重新进入 3 天
- 零评审惩罚：没人评审的文章，每个维度扣 0.5 分
- 作者可以延长沉淀期（`extend_sink`），最多 180 天
- `publish_ready_articles()` 批量发布，两阶段提交（先改文章状态，再重算信誉）

### 3. Reputation（信誉）

```
Article.score (5维) × status_weight
        ↓
  映射到 Reputation (4维)
        ↓
  与现有信誉混合（EMA，权重 0.3）
```

5 维 → 4 维映射：
- professionalism ← avg(originality, rigor)
- objectivity ← completeness
- collaboration ← avg(originality, impact)
- pedagogy ← pedagogy

权重按文章状态：published=1.0, sedimentation=0.7, draft=0.3

## 编译管线

```
源文件 (.typ / .md)
    ↓ detect_format()
    ↓ extract_frontmatter()  ← 解析 YAML 元数据
    ↓
CompilerBackend.compile()
    ├── TypstBackend  → subprocess typst compile → PDF/SVG/PNG
    └── MarkdownBackend → protect_math → render_markdown → restore_math → HTML
```

Markdown 编译的关键顺序（来自 lessons-learned #6）：
1. `_protect_math()` — 用占位符替换 `$...$`
2. `_render_markdown()` — Markdown → HTML
3. `_restore_math()` — 恢复公式并包裹 KaTeX span

**顺序错了公式就坏了。**

## 已知高风险边界

1. **Review.thread 是 JSON 列**（gpt_review P0-1）。不能查询、不能索引。如果评审讨论变多，这是第一个要修的东西。
2. **Article.compiled_* 是编译缓存**（issue #81）。缓存不应该存在主数据表里。
3. **MergeProposal.thread 也是 JSON 列**。同上。
4. **CommentParams.max_length = 300**（issue #87）。评论被截断，用户已经在抱怨。
5. **Git 作者从 email 前缀推导 user_id**（`email.split("@")[0]`）。如果 email 前缀和 user_id 不一致，作者关联就断了。
6. **Article.score 是 JSON dict 不是结构化类型**。虽然 FiveDimScores 有 dataclass，但存到 DB 时序列化成了 dict。

## 入口文件

| 想做什么 | 从哪里开始 |
|----------|-----------|
| 加一个新实体 | `storage/db/models.py` |
| 改评分算法 | `workflow/scoring.py` |
| 调参数 | `config/params.py` |
| 加编译格式 | `storage/compiler.py`（实现 CompilerBackend） |
| 改 Git 操作 | `storage/git_backend.py` |
