# PeerPedia · 知诸网

[![codecov](https://codecov.io/gh/Chenqitrg/peerpedia/branch/main/graph/badge.svg)](https://codecov.io/gh/Chenqitrg/peerpedia)

**Peer review as infrastructure. An open protocol for how knowledge is filtered, not a platform for how it's sold.**

同行评审即基础设施。知识如何被筛选，应当是一个开放的协议，而非一个公司的产品。

---

## The Problem · 问题

Academia runs on a broken loop:

```
Scholar writes paper   →  free labor
Scholar submits         →  gives away copyright for free
Scholar reviews         →  free labor
University buys journal →  millions of dollars per year
Scholar reads own paper →  paywalled
```

arXiv solved **distribution**. But it didn't solve **filtering** — the problem of deciding what's worth reading. Peer review is still owned by publishers who understand nothing about the science. They just run the mailing list.

**Why can't peer review itself be infrastructure?** Like TCP/IP, but for knowledge filtering.

---

## Strategy · 策略

**Phase 1 — Tauri Desktop（冷启动）✅**
A better notebook. Offline Markdown/Typst writing + Git version control + local SQLite. 5MB install, 30MB RAM. Useful alone — the key to cold-start users.

**Phase 1.5 — Polish & Ship（打磨分发）✅ v0.2.3 → v0.3.0**
Delete, diff view, Typst SVG + PDF, draft search, editor UX (save-as-commit, VSCode-style tab system), CodeMirror 6, git-first architecture. Follow/bookmark with server as source of truth (REST API), offline cache via article_cache. Article sync (L4): auto-backup to server, conflict resolution. Multi-author articles, fork/merge workflow, real git merge for proposals. Schools page with follow state. Desktop app is solid.

**Phase 2 — Score arXiv（包围城市）**
Community scoring layer on top of preprints. A quality filter that doesn't belong to any publisher.

**Phase 3 — Replace Peer Review（夺取政权）**
When reputation + scoring infrastructure exists and people trust it, journals become obsolete. Peer review is no longer a service — it's a protocol.

---

## Architecture · 架构

```
Phase 1 + 1.5（Tauri Desktop — 离线写作 + 打磨）
┌─────────────────────────────────────────────────────────┐
│  Vue 3 → IPC → Rust → SQLite + Git（本地）                │
│  离线写作 · 客户端编译 · 版本控制 · 浏览即缓存               │
│  git-first 写入 · 关注走服务器 API · 文章自动备份           │
└─────────────────────────────────────────────────────────┘

Phase 2+（Web — 社区协作）
┌─────────────────────────────────────────────────────────┐
│  Vue 3 SPA → REST → FastAPI → SQLite + Git（服务器）       │
│  沉淀池 · 社区评审 · 信誉系统 · 引用图 · 关注/信息流         │
└─────────────────────────────────────────────────────────┘
```

### Stack · 技术栈

| Layer | Technology |
|-------|-----------|
| Desktop Shell | Tauri 2.x (Rust) |
| Frontend | Vue 3, TypeScript, Vite, Tailwind CSS, Pinia, vue-i18n |
| Backend (Web) | Python 3.12+, FastAPI, SQLAlchemy, SQLite |
| Backend (Desktop) | Rust, rusqlite, bcrypt, libgit2 |
| Storage | SQLite + Git repositories |
| Compilation | Markdown: client-side (marked + KaTeX). Typst: Tauri sidecar CLI |
| Auth | JWT (Web) / bcrypt + SQLite (Desktop) |
| Source of Truth | Git = Source of Truth, DB = Index |

**Author Identity · 作者身份:** Git commit email (`{UUID}@peerpedia`) is the author addressing key. Username is display-only. Authors are derived from git commit history, not stored as a mutable DB field. Fork copies git history → authors = original ∪ forker. Merge joins git histories → authors = target ∪ fork.

### DB Schema · 数据模型（9 entities）

| Table | Purpose |
|-------|---------|
| `articles` | Core article metadata (title, status, score, etc.) |
| `article_authors` | Article ↔ User join (replaces JSON `authors` field) |
| `users` | Account + reputation |
| `reviews` | Five-dimension scores per (article, reviewer, scope, commit) |
| `review_messages` | Threaded discussion under reviews (replaces JSON `thread` field) |
| `follows` | User follow relationships |
| `bookmarks` | User bookmarks |
| `merge_proposals` | Fork → merge workflow. Now executes real git merge (not just status change) |
| `citations` | Article → Article citation edges |

Key architecture decision: **all relationships use proper join tables**, not JSON columns. `article_authors` and `review_messages` replace the old `authors` and `thread` JSON fields. Compile output is generated on-demand with filesystem cache — never stored in the database.

Post-merge, article authors are rebuilt from merged git history.

---

## Quick Start · 快速开始

### Prerequisites

- Python 3.12+, Node.js 18+, Rust (for Tauri)
- [Typst](https://github.com/typst/typst) CLI (for PDF compilation)

### Web Backend

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python seed.py          # 23 demo users, password: 666666
uvicorn peerpedia_api.main:app --port 8080 --reload
```

### Web Frontend

```bash
cd frontend && npm install && npm run dev   # → http://localhost:5173
```

### Tauri Desktop

```bash
cd frontend && npm run tauri dev
```

### Demo Users · 演示用户（23 位科学家）

| Name | Username | Password |
|------|----------|----------|
| Albert Einstein | `einstein` | `666666` |
| Marie Curie | `curie` | `666666` |
| Alan Turing | `turing` | `666666` |
| Ada Lovelace | `lovelace` | `666666` |
| Richard Feynman | `feynman` | `666666` |
| Emmy Noether | `noether` | `666666` |
| Claude Shannon | `shannon` | `666666` |
| Rosalind Franklin | `franklin` | `666666` |
| …and 15 more | `bohr`, `heisenberg`, `schrodinger`, `dirac`, `born`, `vonneumann`, `hopper`, `hodgkin`, `crick`, `cajal`, `goldmanrakic`, `popper`, `kuhn`, `putnam`, `chandra` | `666666` |

---

## Tester Onboarding · 测试者上手

> For testers joining the 2-person experiment. Give this README to your Claude — it has everything needed to guide you.

### Prerequisites

1. **[Tailscale](https://tailscale.com/download)** — create a free account, install the app, and ask the dev for the network invite link.
2. **Python 3.12+, Node.js 18+, Rust** — required for Tauri. Install via [rustup](https://rustup.rs/) and your system package manager.
3. **[Typst](https://github.com/typst/typst)** CLI — `brew install typst` (macOS) or follow the GitHub releases.

### Setup

```bash
# 1. Clone and install
git clone https://github.com/Chenqitrg/peerpedia.git
cd peerpedia
python -m venv .venv && source .venv/bin/activate
pip install -e "core/" -e "backend/.[dev]"
cd frontend && npm install

# 2. Configure server address — copy .env.example, replace with Tailscale IP
cp .env.example .env
# Edit .env: VITE_API_BASE_URL=http://100.x.x.x:8080  ← dev's Tailscale IP

# 3. Start Tauri
npm run tauri dev
```

### Demo Users · 演示用户

Register your own account, or use these for multi-user testing:

| Name | Username | Password |
|------|----------|----------|
| Albert Einstein | `einstein` | `666666` |
| Richard Feynman | `feynman` | `666666` |
| …and 21 more | see list above | `666666` |

### What to Test · 测试重点

**Explore freely — no script.** Try anything a real user would do. But here are the high-risk areas:

- **Fork → Merge flow**: Fork someone's article, edit, propose merge, accept. Check authors at each step.
- **Offline/Online switching**: Toggle the sync button, see what breaks.
- **Multi-account**: Register your own account, then switch to a demo user.
- **Editor**: Save drafts, publish, Typst vs Markdown, diff view.
- **Edge cases**: Empty title, very long content, rapid clicking.

### Reporting Bugs · 报 Bug

Send the dev:
1. **What you did** (steps to reproduce)
2. **What you expected**
3. **What happened instead**
4. **Screenshot or copy-paste any error messages** from the terminal where you ran `npm run tauri dev`

---

## Core Concepts · 核心概念

### Articles as Git Repositories · 文章即 Git 仓库

Every article is an independent Git repository. Fork, edit, merge, rollback — complete version history, forever.

**Save = Commit.** In the editor, saving triggers a Git commit. Each save captures a versioned snapshot. Download filenames embed the commit hash (e.g., `My_Article-a1b2c3d.html`). Downloads are disabled until the first save, ensuring every download is tied to a specific committed version.

### Five-Dimensional Scoring · 五维评分（O/R/C/P/I）

| Dim | Name | Measures |
|-----|------|----------|
| **O** | Originality · 原创性 | How novel is the contribution? |
| **R** | Rigor · 严谨性 | Are the methods sound? |
| **C** | Completeness · 完整性 | Is the work self-contained? |
| **P** | Pedagogy · 可读性 | Well-written and accessible? |
| **I** | Impact · 影响力 | How significant for the field? |

### Sedimentation Pool · 沉淀池

New articles enter the pool for community review. Higher scores → shorter review. Lower scores → longer review. Anonymous during pool phase. Auto-publishes when the timer expires.

### Reputation · 信誉系统（P/O/C/R）

Reputation grows across four dimensions: Professionalism, Objectivity, Collaboration, Readability.

### Offline Capability · 离线能力

Phase 1 Tauri desktop is fully offline-capable:
- Browse = cache: every article you read is cached locally
- Bookmark = full cache: bookmarked articles include reviews + history
- **Auto-backup: every save silently syncs to server (draft, never auto-published)**
- **Conflict resolution: when server version differs from local, forced Keep Local / Use Remote choice**
- Network status: three-state sync button (phone model) — tap to check server reachability, green glow when connected, red flash on failure. User controls connection; no background polling.
- **Local follow graph**: follow/unfollow stored in local SQLite, works fully offline
- Network-dependent features (pool, online search) show clear offline states, not errors
- Schools page available in Tauri mode via server API, local follows reflected in UI
- Local account system: bcrypt + SQLite, no server needed

---

## Project Structure · 项目结构

```
peerpedia/
├── frontend/                   # Vue 3 SPA + Tauri
│   ├── src/
│   │   ├── api/                # Axios API modules + types.ts
│   │   ├── components/         # 17 components (SyncButton, ReviewPanel, ScoreBadges, etc.)
│   │   ├── composables/        # useLocalStorage, useTauri, useNetworkStatus, useOffline, etc.
│   │   ├── locales/            # i18n (zh-CN, en-US)
│   │   ├── pages/              # 10 pages
│   │   ├── router/             # Vue Router + auth guards
│   │   └── stores/             # Pinia (user, article, pool, review)
│   └── src-tauri/              # Tauri Rust backend
│       └── src/
│           ├── main.rs         # Tauri entry
│           ├── commands.rs     # IPC handlers
│           ├── db.rs           # SQLite database layer
│           ├── local_auth.rs   # Local account CRUD + bcrypt
│           ├── local_git.rs    # Local Git operations (init/commit/history)
│           └── local_store.rs  # Drafts + article cache
├── backend/                    # FastAPI server
│   └── peerpedia_api/
│       ├── routes/             # 12 route modules
│       ├── schemas/            # Pydantic request/response models
│       └── tests/              # Integration tests
├── core/                       # Business logic
│   └── peerpedia_core/
│       ├── storage/db/         # SQLAlchemy ORM (9 entities) + CRUD
│       ├── storage/git_backend.py
│       ├── storage/compiler.py
│       └── workflow/           # scoring, sedimentation, reputation
├── scripts/
│   └── migrate_architecture.py # P0 schema migration
├── docs/
│   ├── DESIGN.md               # Design document (Chinese)
│   ├── DESIGN.en.md            # Design document (English)
│   └── api-contract.json       # OpenAPI 3.1 specification
└── seed.py                     # Demo data seeder (23 users)
```

---

## Testing · 测试

```bash
# Backend (540 tests)
python -m pytest backend/tests/ core/tests/ -q

# Frontend (522 tests)
cd frontend && npx vitest run

# Rust (16 tests)
cd frontend/src-tauri && cargo test
```

**CI Pipeline:** 10 jobs across 3 languages (pytest, ruff, mypy, eslint, vitest, vue-tsc, vite verify, clippy, rustfmt, cargo test). See `.github/workflows/ci.yml`.

---

## Roadmap · 路线图

See [`docs/plan_reshape.md`](docs/plan_reshape.md) for the detailed engineering plan across all phases.

| Phase | Focus | Status |
|-------|-------|--------|
| **1 — Desktop MVP** | Offline writing, local git, session auth, profile with drafts | ✅ Done |
| **1.5 — Polish & Ship** | Delete, word-level diff, Typst SVG+PDF, FTS5 search, editor UX, per-save commit, article sync (auto-backup + conflict resolution) | ✅ Done |
| **2 — Score arXiv** | Community scoring, sedimentation pool, reputation | 🔜 Next |
| **3 — P2P Network** | Content-addressed storage, peer-to-peer distribution | 🔮 Future |

---

## Contributing · 参与贡献

We need designers, engineers, writers, and thinkers. Read `docs/DESIGN.en.md` for design philosophy, check `CLAUDE.md` for conventions, follow TDD.

---

## License · 许可

MIT. Content: CC BY-SA 4.0.

---

## Recent Changes (v0.3.0) · 近期变更

| Change | Description |
|--------|-------------|
| Multi-author articles | `article_authors` join table replaces JSON `authors` field. Authors derived from git history, not mutable DB field. |
| Fork & merge workflow | Fork creates a full git history copy; merge executes real git merge (not just status change). Authors rebuilt post-merge. |
| Identity sync | Git commit email (`{UUID}@peerpedia`) as author addressing key. Username is display-only. |
| Real git merge for proposals | `merge_proposals` now performs actual git merge + author rebuild from merged history. |

---

*"走向更好的学术 — To a better academia."*
