# PeerPedia (知诸网) — Complete Design Document

> 2026-06-06 · All implemented features · One document to replicate

---

## 1. Vision

PeerPedia is the GitHub of academic publishing. Articles are git repos, reviews are community scores, quality emerges through a sedimentation pool.

**End goal:** Replace arXiv and traditional academic journals. Combine Wikipedia's open collaboration + arXiv's preprint scale + journals' peer review quality — all three in one.

**Current stage:** Polish the product with popular science and history content. Enter through the content consumption market, then climb upstream into academia.

### Competitive differentiation

| | Traditional Journals | arXiv | Wikipedia | PeerPedia |
|---|---|---|---|---|
| Quality control | Editor monopoly | None | Edit wars | **Community scoring + sedimentation pool** |
| Publication speed | 6-18 months | Instant | Instant | Instant → sediment → publish |
| Version history | None | v1/v2 | Yes | **Full Git history + diff** |
| Scoring | None | None | None | **Five-dimension O/R/C/P/I** |
| Cost | $thousands APC | Free | Free | Free |
| Content license | Publisher-owned | Author-retained | CC BY-SA | CC BY-SA 4.0 |

---

## 2. Architecture

PeerPedia uses a dual architecture: Tauri desktop for offline writing and local storage, Web for community collaboration and review mechanisms. Both share the same Vue 3 frontend.

```
Phase 1 (Cold-start — Tauri Desktop)
┌──────────────────────────────────────────────────────────┐
│  Vue 3 → IPC → Rust commands → SQLite + Git (local)       │
│  Offline writing, local compilation, version control       │
└──────────────────────────────────────────────────────────┘
                         ↕ Optional sync (Slice 2)

Phase 2+ (Community — Web)
┌──────────────────────────────────────────────────────────┐
│  Vue 3 SPA → REST → FastAPI → SQLite + Git (server)       │
│  Sedimentation pool, community review, reputation, AI     │
└──────────────────────────────────────────────────────────┘
```

### Tech stack

| Layer | Desktop (Phase 1) | Web (Phase 2+) |
|---|---|---|
| Shell | Tauri 2.x (Rust) | — |
| Frontend | Vue 3 + TS + Vite + Tailwind | Vue 3 + TS + Vite + Tailwind |
| Backend | Rust (rusqlite, bcrypt, libgit2) | Python 3.12+, FastAPI, SQLAlchemy |
| Storage | SQLite + Git repos (local) | SQLite + Git repos (server) |
| Compilation | Typst CLI, Python Markdown | Typst CLI, Python Markdown |
| Auth | bcrypt + SQLite (local accounts) | JWT (bcrypt, 24h expiry) |

### Project structure

```
peerpedia/
├── core/peerpedia_core/        # Business logic library (no web deps)
│   ├── config/params.py        # Tunable parameters
│   ├── storage/db/             # SQLAlchemy ORM (7 entities) + CRUD (6 modules)
│   ├── storage/git_backend.py  # Git ops (init/commit/history/diff/fork)
│   ├── storage/compiler.py     # Markdown/Typst compilation backend
│   ├── workflow/               # scoring, sedimentation, reputation
│   └── types/                  # scores, messages
├── backend/peerpedia_api/      # FastAPI REST API
│   ├── main.py                 # Entry + CORS + background task (auto-publish)
│   ├── routes/                 # 11 route modules
│   ├── schemas/                # Pydantic request/response models
│   ├── deps.py                 # FastAPI dependency injection
│   └── helpers.py              # Shared utilities
├── frontend/                   # Vue 3 SPA + Tauri
│   ├── src/
│   │   ├── api/                # Axios API modules + types.ts
│   │   ├── components/         # 14 components (SelfReviewPanel, ReviewPanel, etc.)
│   │   ├── composables/        # useLocalStorage, useTauri, useDraftPersistence, useBookmarkToggle, useStatusMap, useAsyncResource
│   │   ├── pages/              # 11 pages
│   │   ├── router/             # Vue Router + auth guards
│   │   ├── stores/             # Pinia (user, article, pool, review)
│   │   ├── utils/markdown.ts   # Client-side Markdown compilation (marked + KaTeX)
│   │   └── utils/math.ts       # KaTeX rendering helpers
│   └── src-tauri/              # Tauri Rust backend
│       └── src/
│           ├── main.rs         # Tauri entry
│           ├── commands.rs     # IPC handlers
│           ├── db.rs           # SQLite database layer
│           ├── local_auth.rs   # Local account CRUD + bcrypt
│           └── local_store.rs  # Drafts + article cache SQLite
├── .github/workflows/ci.yml    # CI pipeline (11 jobs, 3 languages)
├── seed.py                     # Demo data (23 users)
├── docs/DESIGN.md              # This document (Chinese)
├── docs/DESIGN.en.md           # This document (English)
└── docs/api-contract.json      # OpenAPI specification
```

---

## 3. Data Model

### 3.1 Article

```python
class Article(Base):
    id = Column(String, primary_key=True, default=uuid4)
    title = Column(String, default="")
    abstract = Column(String, nullable=True)
    keywords = Column(JSONList)          # ["physics", "quantum"]
    categories = Column(JSONList)        # ["theory", "experiment"]
    status = Column(String, default="draft")  # draft | sedimentation | published
    score = Column(JSONDict)             # Latest commit score cache
    compiled_format = Column(String)     # "html" | "svg"
    compiled_output = Column(String)     # Compiled HTML/SVG
    compiled_pages = Column(JSONList)    # Multi-page SVG
    sink_start = Column(DateTime)
    sink_duration_days = Column(Integer, default=7)
    sink_extended_count = Column(Integer, default=0)
    forked_from = Column(String, nullable=True)
    fork_count = Column(Integer, default=0)
    authors = Column(JSONList, default=[])
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
```

**Status machine:** `draft → sedimentation → published`
- draft: visible to author only
- sedimentation: visible to follow network
- published: publicly visible

### 3.2 Review

```python
class Review(Base):
    id = Column(String, primary_key=True)
    article_id = Column(String, ForeignKey("articles.id"))
    commit_hash = Column(String)
    reviewer_id = Column(String, ForeignKey("users.id"))
    scope = Column(String)                 # "pool" (anonymous) | "published" (real name)
    scores = Column(JSONDict)              # FiveDimScores
    contributions = Column(JSONDict, nullable=True)
    thread = Column(JSONList, default=[])
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    __table_args__ = (UniqueConstraint("article_id", "reviewer_id", "scope", "commit_hash"),)
```

**Review rules:**
- One review per person per article per commit per scope
- scope separation: one pool (anonymous) + one published (real name)
- After article publishes: pool reviews freeze
- Pool anonymous names **never leak**
- Self-reviews always show real name

### 3.3 User

```python
class User(Base):
    id = Column(String, primary_key=True)
    username = Column(String, unique=True)
    password_hash = Column(String)               # bcrypt
    email = Column(String, nullable=True)
    name = Column(String)
    anonymous_name = Column(String, default="")  # Fixed pool anonymous name
    affiliation = Column(String, default="")
    expertise = Column(JSONList, default=[])
    avatar_url = Column(String, nullable=True)
    contact = Column(String, nullable=True)
    reputation = Column(JSONDict, default={})
    created_at = Column(DateTime)
```

### 3.4 Other entities

**Follow:** `(follower_id, followed_id)` — follow relationships

**Bookmark:** `(user_id, article_id)` — bookmark relationships

**MergeProposal:** fork article merge request. Fields: `fork_article_id`, `target_article_id`, `proposer_id`, `status` (open/accepted/rejected), `thread`

**Citation:** `(from_article_id, to_article_id, forward_prob, backward_prob)` — citation graph

---

## 4. Core Mechanisms

### 4.1 Git-driven article management

Each article is an independent git repo under `~/.peerpedia/articles/{id}/`.

**Operation mapping:**
- Create article → `init_article_repo(id)` + first commit
- Edit → `commit_article(repo, msg, author, email)` → new commit
- Fork → `shutil.copytree(src, dst)` + new DB record
- History → `get_commit_history(repo)` → commit list
- Diff → `git diff hash1 hash2` → diff2html rendering
- Rollback → `commit_article(repo, msg, author, email)` writes rollback content

**Article content file:** `article.md` or `article.typ`

### 4.2 Five-Dimensional Scoring

All reviews use five dimensions, 0-5 each:

| Dim | Name | What it measures |
|---|---|---|
| **O** | Originality | How novel is the contribution? |
| **R** | Rigor | Are methods and arguments sound? |
| **C** | Completeness | Is the work thorough and self-contained? |
| **P** | Pedagogy | Is it well-written and accessible? |
| **I** | Impact | How significant for the field? |

**Score calculation:** Each commit scored independently. Community review weight 0.85, self-review weight 0.15. `compute_article_score_for_commit()` filters reviews by commit_hash, computes weighted average.

### 4.3 Sedimentation Pool

New articles enter the sedimentation pool for community review. Scores affect exit speed:

- Initial duration: 7 days (new articles), 3 days (edits)
- High scores shorten (min 2 days), low scores extend (max 180 days)
- Authors may extend (+7 days each time, cumulative ≤ 180 days)
- If no community reviews at publish time → penalty per dimension
- After publish: status → published, pool reviews freeze
- Background task auto-publishes expired articles every 60 seconds

**Visibility:** Follow network only (following + followers)

**Ordering:** By remaining days descending — soon-to-exit at the bottom (visual "sedimentation")

### 4.4 Blind Review and Identity Protection

| Scenario | Display Name |
|---|---|
| Pool review (scope=pool) | `anonymous_name` (fixed, **never leaked**) |
| Published review (scope=published) | `name` (real name) |
| Self-review | Always `name` (real name, author already public) |

- Same person can have pool (anonymous) + published (real) records for same article
- After publish: pool review freezes, cannot modify
- Published review is a new independent record
- Self-review pinned to top with accent left border

### 4.5 Reputation System (backend ready, frontend pending)

- 4 dimensions: professionalism, objectivity, collaboration, pedagogy
- Article 5-dim scores → mapped → author 4-dim reputation
- Status weighting: published(1.0) > sedimentation(0.7) > draft(0.3)
- New scores blended with old reputation at 0.3 weight
- Review weight = 1.0 + author_weight × (avg_rep - 3.0) / 2.0

### 4.6 Offline-First Design (Phase 1 — Tauri Desktop)

**Design principle:** Local operations complete immediately, remote sync happens asynchronously. Like GitHub Desktop — commit doesn't wait for network, push follows later.

**Local account system:**
- bcrypt password hashing + SQLite storage
- Multi-account switching (alice/bob on same device)
- Remote binding optional — local account always works, server binding is additive
- Gray avatar + "offline" label when disconnected, color avatar when online

**Draft system:**
- Multi-draft management (unlimited, SQLite-persisted)
- Markdown / Typst format toggle
- Draft isolation — accounts cannot see each other's drafts
- Migration: localStorage (Web) → SQLite (Tauri)

**Article cache:**
- Published articles cached to local SQLite (read offline)
- Cache is read-only snapshot — editing requires online fork

**Slice 1/2 scope:**

| Slice | Includes | Deferred |
|-------|----------|----------|
| **Slice 1** | Local account CRUD, draft save/load/list, article cache, LoginPage, useTauri, NavBar connection state | — |
| **Slice 2** | Typst local compilation, Sync engine, backend `/auth/bind` + `/sync/batch`, Git engine | — |
| **Slice 3** | P2P distributed storage, offline review, AI-assisted writing | — |

**IPC design:** Vue calls Rust via `useTauri()` composable. In Web mode, composable falls back to no-op. Vue components are unaware of the underlying platform.

---

## 5. Feature Specification

### 5.1 Home `/`

**Not logged in:** Brand page — PeerPedia logo + tagline + Sign In / Create Account buttons

**Logged in:** Following activity Feed
- Sources: articles from followed users (sedimentation + published, excludes draft)
- Each article renders ArticleCard
- Pagination
- Auto-load on login; refresh after AuthModal login

### 5.2 Editor `/edit` `/edit/:id` 🔒

Overleaf-inspired split-pane layout. **Full-width** (breaks global max-w-content).

**Toolbar:**
- MD / Typst format toggle
- 💾 Save — save draft to backend (`publish: false`), stay draft
- 🚀 Publish — self-review panel → submit to pool (`publish: true`)
- Download source / Download PDF

**Self-review panel (when publishing):**
- Commit message (**required**)
- Five-dim score stars (O/R/C/P/I, clickable)
- Title / Abstract / Keywords / Categories
- Contributions slider (per-author allocation)
- "Publish to Pool" button

**Splitter:** Draggable (mousedown/mousemove/mouseup), range 20%-80%

**Compilation preview:** `POST /compile-preview` → KaTeX rendering (Markdown) or SVG (Typst)

**Drafts:** Auto-save to localStorage / SQLite, restore on reload

### 5.3 Article Page `/articles/:id`

**Metadata bar (narrow):**

| Element | Behavior |
|---|---|
| Title | Text |
| Authors | Clickable → user page |
| Status badge | draft/sedimentation/published |
| 5-dim scores | Numeric display |
| History | → history page |
| Fork | → fork API → editor |
| Edit | Author-only → editor |
| Extend | Author-only + in pool → +7 days |
| Merge | Visible when article is a fork → propose merge |
| Source / PDF | Download |
| Bookmark | Toggle star |

**Dual tabs below:**
- **Body** — compiled HTML/SVG with KaTeX rendering
- **Comments** — full review system (see 5.4)

### 5.4 Review System

**Submit review:** Non-author logged-in → five-dim stars + text box + Submit Review

**Review card:**
- Shows reviewer name (anonymous/real/Author), scores, timestamp
- Own review pinned to top (accent left border + "(you)" label)
- Hover scores → ScoreBadges expands to editable stars (`editable` prop), mouse-out restores numbers
- Score changes take effect immediately (optimistic update via Pinia store)

**Thread discussions:**
- Thread dropdown under each review (Chevron expand/collapse)
- iMessage-style chat bubbles (author left-aligned dark, replier right-aligned accent)
- Participants: article author + that review's reviewer
- Bystanders read-only: "Only the author and reviewer can participate in this thread"
- Empty thread on own review shows "Start a conversation..." input

### 5.5 Sedimentation Pool `/pool` 🔒

Follow network's sedimentation articles. ArticleCard list + progress bar (elapsed/total days). Ordered by remaining days descending.

### 5.6 User Page `/users/:id`

**Top:** Avatar + name + affiliation + 4-dim reputation + follower/following count (expandable) + Edit Profile (self only, disabled "Coming soon")

**Bottom:** All user's articles (includes draft, self only)

### 5.7 History Page `/articles/:id/history`

Commit timeline graph + click two nodes → diff2html side-by-side diff + rollback button

### 5.8 Citations Page `/articles/:id/citations`

Citation DAG: References (this article cites) + Cited by (articles citing this). Click to navigate.

### 5.9 Search `/search?q=`

Full-text search with SQL-level filtering: category (JSON column LIKE), title (ILIKE), content (compiled_output ILIKE + source file fallback), sort (newest/score), pagination (LIMIT/OFFSET with accurate COUNT). ArticleCard list. Empty/loading/error states handled.

### 5.10 Schools `/schools`

Global user directory, ordered by article count descending. Avatar, affiliation, reputation, expertise tags, Follow button.

### 5.11 Bookmarks `/bookmarks` 🔒

Bookmarked article list, ArticleCard. Toggle bookmark updates optimistically (rolls back on failure).

---

## 6. API Contract

All endpoints prefixed: `/api/v1`

### Auth

| Method | Endpoint | Auth | Description |
|------|------|------|------|
| POST | `/auth/register` | None | body: `{username, password, email, name}` → `{user, token}` |
| POST | `/auth/login` | None | body: `{username, password}` → `{user, token}` |
| GET | `/auth/me` | Bearer | → `{user}` |

### Articles

| Method | Endpoint | Auth | Description |
|------|------|------|------|
| GET | `/articles` | Optional | `?status=&author_id=&page=&size=` |
| POST | `/articles` | Bearer | Create + publish to pool |
| GET | `/articles/{id}` | Optional | Detail (score, sink_eta, is_bookmarked) |
| PUT | `/articles/{id}` | Bearer | Edit. `publish: true` → pool, `false` → draft |
| GET | `/articles/{id}/source` | None | Raw source code |
| GET | `/articles/{id}/history` | None | Commit list (parents + per-commit score) |
| GET | `/articles/{id}/diff/{h1}/{h2}` | None | diff_text + files |
| POST | `/articles/{id}/fork` | Bearer | Fork → `{id, forked_from, status: "draft"}` |
| POST | `/articles/{id}/rollback/{hash}` | Bearer | Rollback |
| PUT | `/articles/{id}/sink-extension` | Bearer | body: `{extra_days}` |
| GET | `/articles/{id}/has-forked` | Bearer | → `{has_forked, fork_article_id}` |
| GET | `/articles/{id}/download/source` | None | Download source file |
| GET | `/articles/{id}/download/pdf` | None | Typst→PDF, Markdown→HTML |

### Reviews

| Method | Endpoint | Auth | Description |
|------|------|------|------|
| GET | `/articles/{id}/reviews` | None | Review list (reviewer_name + author_name) |
| POST | `/articles/{id}/reviews` | Bearer | Create/update. scope auto-determined by article.status |
| POST | `/articles/{id}/reviews/{rid}/messages` | Bearer | Thread reply. body: `{content}` |

### Social

| Method | Endpoint | Auth | Description |
|------|------|------|------|
| GET | `/feed` | Optional | Followed users' articles |
| GET | `/pool` | Optional | Follow network pool |
| GET/POST/DELETE | `/bookmarks` | Bearer | CRUD |
| GET | `/users` | None | User list (article_count + reputation) |
| GET | `/users/{id}` | None | User detail |
| PUT | `/users/{id}` | Bearer | Edit profile |
| GET | `/users/{id}/followers` | None | Follower list |
| GET | `/users/{id}/following` | None | Following list |
| POST | `/users/{id}/follow` | Bearer | Follow |
| DELETE | `/users/{id}/follow` | Bearer | Unfollow |

### Compilation & Search

| Method | Endpoint | Auth | Description |
|------|------|------|------|
| POST | `/compile-preview` | None | body: `{content, format}` → HTML/SVG |
| POST | `/compile-download` | None | body: `{content, format}` → file download |
| GET | `/search?q=` | None | Full-text search. Optional: `category`, `sort` |

### Merge

| Method | Endpoint | Auth | Description |
|------|------|------|------|
| POST | `/articles/{id}/merge-proposals` | Bearer | Create merge request |
| GET | `/articles/{id}/merge-proposals` | None | List merge requests |
| POST | `/articles/{id}/merge-proposals/{pid}/accept` | Bearer | Accept merge |
| POST | `/articles/{id}/merge-proposals/{pid}/reject` | Bearer | Reject merge |

### Tauri IPC Commands (Phase 1 Desktop)

All IPC commands called via `useTauri()` composable, backed by `invoke()`. No-op in Web mode.

| IPC Command | Params | Returns | Description |
|---|---|---|---|
| `create_account` | `{username, password, email, name}` | `{id, username}` | Create local account |
| `login` | `{username, password}` | `{id, username}` | Local login |
| `list_accounts` | — | `[{id, username}]` | List all accounts on device |
| `save_draft` | `{id, account_id, title, content, format}` | `{id, updated_at}` | Save/update draft |
| `list_drafts` | `{account_id}` | `[{id, title, updated_at}]` | List account drafts |
| `get_draft` | `{id}` | `{id, title, content, format}` | Get draft content |
| `delete_draft` | `{id}` | `{ok: true}` | Delete draft |
| `cache_article` | `{id, article_json}` | `{ok: true}` | Cache published article |
| `get_cached_article` | `{id}` | `{article_json} or null` | Read cached article |

---

## 7. Frontend Design System

**Design philosophy:** Cold Academic Minimal — dark, serious, content-forward

**Colors:**
- Page bg `#0d1117`, Card `#161b22`, Divider `#21262d`
- Primary text `#b0b8c4`, Secondary text `#8b949e`
- Accent `#7b8c9e` (steel blue-gray), Success `#5c7c6e`
- Review stars `#f0c040` (gold)

**Typography:** EB Garamond (headings) + Inter (body) + JetBrains Mono (code)

**Component classes (main.css):** `.card`, `.card-interactive`, `.btn`, `.btn-primary`, `.btn-outline`, `.btn-ghost`, `.btn-sm`, `.input`, `.label`, `.badge-*`, `.skeleton`, `.prose-custom`

**Animation:** `animate-fade-in`, `animate-slide-up`; respects `prefers-reduced-motion`

---

## 8. Routes

| Path | Page | Auth |
|------|------|------|
| `/` | HomePage | None |
| `/edit` | EditorPage (new) | 🔒 |
| `/edit/:id` | EditorPage (edit) | 🔒 |
| `/articles/:id` | ArticlePage | None |
| `/articles/:id/history` | HistoryPage | None |
| `/articles/:id/citations` | CitationsPage | None |
| `/users/:id` | UserPage | None |
| `/schools` | SchoolsPage | None |
| `/pool` | PoolPage | 🔒 |
| `/search?q=` | SearchPage | None |
| `/bookmarks` | BookmarksPage | 🔒 |

Route guard: unauthenticated access to 🔒 routes → redirect to home + AuthModal

---

## 9. Testing

```bash
# Backend 166 tests
.venv/bin/python -m pytest backend/ -q

# Frontend 172 tests
cd frontend && npx vitest run
```

---

## 10. Running

```bash
# Web backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python seed.py                      # 23 scientists, password 666666
uvicorn peerpedia_api.main:app --port 8080 --reload

# Web frontend
cd frontend && npm run dev          # → http://localhost:5173

# Tauri desktop (dev mode)
cd frontend && npm run tauri dev    # → Tauri window
```

### Demo users (23 scientists, password 666666)

| Username | Username | Username |
|----------|----------|----------|
| einstein | feynman | chandra |
| bohr | heisenberg | schrodinger |
| dirac | born | noether |
| lovelace | vonneumann | turing |
| shannon | hopper | curie |
| franklin | hodgkin | crick |
| cajal | goldmanrakic | popper |
| kuhn | putnam | |

---

## 11. Roadmap

| Priority | Feature | Phase |
|----------|---------|-------|
| **P0** | Tauri Slice 1: local accounts + offline editor + article cache | Phase 1 |
| Medium | Tauri Slice 2: Typst compilation + Sync Engine + remote binding | Phase 1 |
| Medium | Reputation-weighted scoring (backend ready, frontend pending) | Phase 2 |
| Low | Profile edit page | Phase 2 |
| Deferred | P2P distributed storage (IPFS) | Phase 3 |
| Deferred | AI-assisted review/writing | Phase 3 |
| Deferred | LaTeX support | Phase 3 |
| Deferred | Production deployment (Docker, CI/CD, public URL) | Phase 3 |

---

## 12. Development Notes

- **Restart server after template changes** — uvicorn --reload doesn't watch .html
- **ORM column additions silently destroy SQLite DB** — run `python seed.py` after schema changes
- **New UI components must ship with CSS** — otherwise render unstyled
- **Math rendering order:** `_protect_math → _render_markdown → _restore_math`
- **v-html doesn't execute `<script>`** — KaTeX must be client-rendered via `renderMathInHtml()`
- **ruff --fix deletes facade re-exports** — append `# noqa: F401` to import lines
- **seed.py uses relative path `sqlite:///peerpedia.db`** — must run from project root
- **Tauri IPC via `useTauri()` composable** — no-op in Web mode, no impact on existing Web features
- **Vue components are platform-agnostic** — all platform logic encapsulated in composables

---

## 13. Offline Behavior Matrix (Phase 1 — Tauri Desktop)

PeerPedia Tauri 桌面版的核心承诺：**一个人用也爽**。离线时，所有与"自己"相关的功能正常工作；需要协作的功能优雅降级，显示明确的状态提示。

### 13.1 Design Principles

1. **Local-first, network-optional** — 本地操作立即完成，远程同步异步发生
2. **Graceful degradation** — 功能不可用时灰色 + 提示文案，不隐藏、不报错、不白屏
3. **Bookmark = cache** — 收藏即全量本地缓存，用户不需要理解"缓存"概念
4. **Browse = cache** — 看过的文章自动缓存，离线 feed = 浏览历史

### 13.2 Network Detection

导航栏右上角显示网络状态图标（在线绿色 / 离线灰色）。

- **机制**：每 30s ping `GET /health`，2 次连续失败 → 离线，恢复 → 在线
- **Tauri 模式**：Rust 端发起 HTTP ping，通过 IPC 推送状态到 Vue
- **Web 模式**：`navigator.onLine` + `fetch('/health')` 兜底

### 13.3 Offline Capability Matrix

每个功能在离线时有三种能力级别：

| Level | 含义 | UI 表现 |
|-------|------|---------|
| `full` | 完全可用，与在线无区别 | 正常 |
| `readonly` | 可查看已缓存内容，不可写入 | 输入区灰色 + 提示文案 |
| `blocked` | 完全不可用 | 灰色遮罩 + "需要联网" |

**逐功能矩阵：**

| Feature | 离线 Read | 离线 Write | 数据来源 | 备注 |
|---------|----------|-----------|---------|------|
| **首页 Feed** | `full` | `full` | 本地 browsing_history 表 | 无历史时显示空状态；在线关注网络 feed 不可用 |
| **收藏夹** | `full` | `full` | 全量缓存（bookmark 触发） | 收藏的文章含完整评论 + 历史 |
| **搜索** | `full` (本地) | `full` | 本地 SQLite（缓存 + 自己文章 + drafts） | 搜索栏标签自动显示"本地"；在线扩展为"全网" |
| **沉淀池** | `blocked` | `blocked` | — | 显示"无网络，进不去" |
| **Schools** | `blocked` | `blocked` | — | 显示"无网络，进不去" |
| **个人主页（自己）** | `full` | `full` | 本地数据（自己文章 + drafts + 评分） | 与线上完全相同 |
| **个人主页（他人已缓存）** | `full` | `blocked` | 缓存的 user profile | 可看 profile 和文章列表；关注/粉丝列表不可点击跳转 |
| **个人主页（他人未缓存）** | `blocked` | `blocked` | — | "离线不可用" |
| **文章编辑器** | `full` | `full` | 本地 draft + 本地编译 | 仅"发布到沉淀池"按钮灰色 |
| **编译/下载** | `full` | `full` | 本地工具（marked/KaTeX/Typst sidecar） | 不依赖服务器 |
| **文章内容** | `full` | — | 本地缓存 | 浏览即缓存 |
| **文章评论** | `readonly` | `blocked` | 缓存评论（跟随文章缓存） | 输入框灰色 + "需要联网才能评论" |
| **文章 Fork** | `blocked` | `blocked` | — | 灰色 + "需要联网" |
| **文章历史** | `full` (到缓存点) | `blocked` | 文章缓存时 snapshot 的 git log | 截止到缓存那一刻的历史 |

### 13.4 Per-Page Behavior

#### 13.4.1 首页 `/`

- **在线**：关注用户的活动 feed（与现在相同）
- **离线**：显示浏览历史，按访问时间倒序。来源：`browsing_history` SQLite 表
- **空状态**：既无网络也无历史时，显示"离线模式 — 去探索文章吧，看过的会出现在这里"
- 导航栏网络图标实时反映状态

#### 13.4.2 文章编辑页 `/edit` `/edit/:id`

- 所有编辑功能正常（Markdown/Typst 编写、预览、保存草稿）
- **编译**：Markdown 用 marked + KaTeX 客户端渲染，Typst 用 Tauri sidecar CLI
- **下载**：源码/PDF 下载调用本地工具
- **发布到沉淀池**：按钮灰色，不可点击，hover 显示"需要联网才能发布到沉淀池"
- 保存 = 存本地 SQLite draft，个人主页可见

#### 13.4.3 文章页面 `/articles/:id`

- 文章内容、源码、预览：本地缓存，正常可用
- **评论 tab**：显示缓存评论（只读），输入框灰色 + "需要联网才能评论"
- **Fork 按钮**：灰色 + "需要联网"
- **作者链接**：若作者已缓存 → 可点击跳转；未缓存 → 灰色不可点击
- **历史页**：显示截止到缓存时刻的 commit 历史，diff 正常

#### 13.4.4 个人主页 `/users/:id`

- **自己的主页**：与线上完全相同（自己的文章、drafts、评分、关注/粉丝列表）
- **他人主页（已缓存）**：可见 profile + 文章列表。关注/粉丝列表显示数量和头像，但不可点击跳转
- **他人主页（未缓存）**："离线不可用"
- 评分继承上次联网时的 snapshot

#### 13.4.5 沉淀池 `/pool`

- 整个页面显示"无网络，进不去"，无法进入

#### 13.4.6 Schools `/schools`

- 整个页面显示"无网络，进不去"，无法进入

#### 13.4.7 搜索 `/search`

- 自动根据网络状态切换搜索范围
- **离线**：搜索本地数据库（缓存文章 + 自己文章 + drafts），标签显示"本地"
- **在线**：扩展搜索到关注网络，标签显示"全网"

#### 13.4.8 收藏夹 `/bookmarks`

- 完全正常，收藏 = 全量缓存（文章内容 + 评论 + 历史）
- 可以添加/移除收藏（本地操作）

### 13.5 Data Layer Additions

#### 13.5.1 Browsing History (Rust SQLite)

```sql
CREATE TABLE browsing_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL,
    article_id TEXT NOT NULL,
    article_title TEXT NOT NULL DEFAULT '',
    visited_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(account_id, article_id)
);
```

IPC commands：
- `record_visit(account_id, article_id, title)` → `{ok: true}` — 浏览文章时自动调用
- `get_history(account_id, page, size)` → `[{article_id, title, visited_at}, ...]` — 离线 feed 的数据源

#### 13.5.2 Article Full Cache (Rust local_store.rs)

增强现有 `cache_article` IPC，支持全量缓存：

```
cache_article_full(id, article_json_with_reviews_and_authors) → {ok: true}
```

缓存内容：article metadata + compiled_output + reviews[] + author profiles[]。

#### 13.5.3 /health Endpoint (FastAPI)

```python
@router.get("/health")
async def health_check():
    return {"ok": True}
```

轻量 ping，不查数据库，30s 间隔。

### 13.6 Architecture: Offline Composables

```
Vue Pages (只调用 useOffline，不自己判断 isOnline)
    ↓
useOffline(feature) composable     ← 集中式能力查询
  - canRead(): boolean              ← 查矩阵
  - canWrite(): boolean             ← 查矩阵
  - fallbackMessage(): string       ← 查矩阵
    ↓
useNetworkStatus() composable      ← 网络检测
  - isOnline: Ref<boolean>
  - startPing() / stopPing()
    ↓
┌──────────────┬──────────────────┐
│ Tauri 模式    │ Web 模式          │
│ Rust HTTP ping│ fetch(/health)   │
│ + IPC push    │ + setInterval     │
└──────────────┴──────────────────┘
```

### 13.7 i18n Keys (新增)

```json
{
  "offline": {
    "status_online": "在线",
    "status_offline": "离线",
    "feed_hint": "离线模式 — 这里显示你最近看过的文章",
    "feed_empty": "还没有浏览记录 — 去探索文章吧",
    "comment_hint": "需要联网才能评论",
    "fork_hint": "需要联网才能 Fork",
    "publish_hint": "需要联网才能发布到沉淀池",
    "pool_hint": "无网络，无法访问沉淀池",
    "schools_hint": "无网络，无法访问 Schools",
    "user_hint": "离线不可用",
    "search_local": "本地",
    "search_network": "全网"
  }
}
```
