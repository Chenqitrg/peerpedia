# PeerPedia · 知诸网

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

**Phase 1 — Tauri Desktop（冷启动）**
A better notebook. Offline Markdown/Typst writing + Git version control + local SQLite. 5MB install, 30MB RAM. Useful alone — the key to cold-start users.

**Phase 2 — Score arXiv（包围城市）**
Community scoring layer on top of preprints. A quality filter that doesn't belong to any publisher.

**Phase 3 — Replace Peer Review（夺取政权）**
When reputation + scoring infrastructure exists and people trust it, journals become obsolete. Peer review is no longer a service — it's a protocol.

---

## Architecture · 架构

```
Phase 1（Tauri Desktop — 离线写作）
┌─────────────────────────────────────────────────────────┐
│  Vue 3 → IPC → Rust → SQLite + Git（本地）                │
│  离线写作 · 客户端编译 · 版本控制 · 浏览即缓存               │
└─────────────────────────────────────────────────────────┘

Phase 2+（Web — 社区协作）
┌─────────────────────────────────────────────────────────┐
│  Vue 3 SPA → REST → FastAPI → SQLite + Git（服务器）       │
│  沉淀池 · 社区评审 · 信誉系统 · 引用图                      │
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
| Compilation | Markdown: client-side (marked + KaTeX). Typst: SVG preview via Tauri sidecar CLI + `typst compile` |
| Auth | JWT (Web) / bcrypt + SQLite (Desktop) |
| Source of Truth | Git = Source of Truth, DB = Index |

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
| `merge_proposals` | Fork → merge workflow |
| `citations` | Article → Article citation edges |

Key architecture decision: **all relationships use proper join tables**, not JSON columns. `article_authors` and `review_messages` replace the old `authors` and `thread` JSON fields. Compile output is generated on-demand with filesystem cache — never stored in the database.

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
- Network status indicator shows real-time online/offline state
- Network-dependent features (pool, schools) show clear offline states, not errors
- Local account system: bcrypt + SQLite, no server needed

---

## Project Structure · 项目结构

```
peerpedia/
├── frontend/                   # Vue 3 SPA + Tauri
│   ├── src/
│   │   ├── api/                # Axios API modules + types.ts
│   │   ├── components/         # 17 components (ReviewPanel, NetworkStatusBadge, ScoreBadges, etc.)
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
# Backend (120 tests)
python -m pytest backend/tests/ core/tests/ -q

# Frontend (319 tests)
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
| **2 — Polish & Ship** | Delete articles, diff view, Typst preview, draft search, editor UX | 🚧 In progress |
| **3 — P2P Network** | Index server, content-addressed storage, peer-to-peer distribution | 🔮 Future |

---

## Contributing · 参与贡献

We need designers, engineers, writers, and thinkers. Read `docs/DESIGN.en.md` for design philosophy, check `CLAUDE.md` for conventions, follow TDD.

---

## License · 许可

MIT. Content: CC BY-SA 4.0.

---

*"走向更好的学术 — To a better academia."*
