# PeerPedia · 知诸网

**Peer review as infrastructure. An open protocol for how knowledge is filtered, not a platform for how it's sold.**

---

## The Problem

Academia runs on a broken loop:

```
Scholar writes paper   →  free labor
Scholar submits to publisher  →  gives away copyright for free
Scholar reviews for publisher  →  free labor
University buys journal back  →  millions of dollars per year
Scholar reads own paper  →  paywalled
```

The scholar writes. The scholar reviews. The scholar pays. The publisher owns the envelope.

arXiv solved **distribution**. But it didn't solve **filtering** — the problem of deciding what's worth reading. Today, filtering is still peer review, and peer review is still owned by publishers who understand nothing about the science. They just run the mailing list.

**Why can't peer review itself be infrastructure?** Not a service run by a company. A protocol. Like TCP/IP, but for knowledge filtering. Anyone can build on it. No one owns it.

That's what PeerPedia is trying to build.

---

> 🚧 **Early-stage, vibe-coded, and looking for contributors.** Built with Claude Code + DeepSeek V4. Many things work, many are rough, many are missing entirely. The hardest problem is not the code — it's bootstrapping a user base and network effect. If you care about open knowledge, [join us](#contributing). We need designers, engineers, writers, and thinkers.

---

## The Roadmap: 农村包围城市，武装夺取政权

We're not going to replace Elsevier tomorrow. The strategy — borrowing from Mao — is **surround the cities from the countryside, seize power through armed struggle.** The "cities" are elite journals, prestige institutions, and the publisher monopoly. The "countryside" is individual scholars, small labs, and the global majority of researchers who are locked out of the prestige economy.

**Phase 1 — A better notebook.** Interconnected note-taking with Git history. Fork ideas. Merge improvements. Cite anything. Build a user base by being genuinely useful to individual scholars, not institutions. *Build the base in the countryside.*

**Phase 1 的载体是 Tauri 桌面版。** 离线 Markdown/Typst 写作 + Git 版本控制 + 本地 SQLite 存储。5MB 体积、30MB 内存。一个人用也爽——这是吸引冷启动用户的关键。Web 版保留给社区功能。

**Phase 2 — Score arXiv.** The millions of preprints on arXiv have no quality signal. A community-driven scoring layer — one that anyone can query, audit, or build on — gives readers a filter that doesn't belong to any publisher. *Surround the cities. Start building parallel infrastructure that makes the old system visibly inadequate.*

**Phase 3 — Replace peer review.** Once reputation and scoring infrastructure exists, and people trust it, the journal's last function becomes obsolete. Peer review is no longer a service. It's a protocol. *Seize the means of filtering.*

Every phase is useful on its own. Each one builds the network for the next. You don't beat publishers by attacking them. You make them irrelevant by building something better underneath.

---

## Why PeerPedia?

Knowledge should flow freely and build on itself. Instead of isolated documents in silos, PeerPedia lets you:

- **Connect** notes and articles through citations, forks, and merges
- **Evolve** ideas with full Git history — every edit is tracked, diffable, rollbackable
- **Review** each other's work anonymously in a sedimentation pool
- **Build reputation** that reflects contribution quality, not institutional prestige

| Problem | PeerPedia |
|---------|-----------|
| Isolated note-taking | Citation graph — every article can reference and be referenced |
| No version history | Git-native: fork, edit, merge, rollback |
| Opaque feedback | Transparent 5-dimension scoring (O/R/C/P/I) |
| No author incentives | Reputation system (P/O/C/R) rewards quality work |
| English-only | Full Chinese/English bilingual interface (知诸网) |

---

## Architecture

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

**Offline capability**: Phase 1 desktop is fully offline-capable. See `docs/DESIGN.en.md` Section 13 for the complete offline behavior matrix.

### Stack

| Layer | Technology |
|-------|-----------|
| Desktop Shell | Tauri 2.x (Rust) |
| Frontend | Vue 3, TypeScript, Vite, Tailwind CSS, Pinia, vue-i18n |
| Backend (Web) | Python 3, FastAPI, SQLAlchemy, SQLite |
| Backend (Desktop) | Rust, rusqlite, bcrypt, libgit2 |
| Storage (Desktop) | SQLite + Git repositories（本地） |
| Storage (Web) | SQLite + Git repositories（服务器） |
| Auth | JWT (Web) / bcrypt + SQLite (Desktop) |
| Compilation | Markdown: client-side (marked + KaTeX). Typst: Tauri sidecar CLI (Slice 2) |
| Math | KaTeX |

---

## Quick Start

### Prerequisites
- Python 3.12+
- Node.js 18+
- Rust (for Tauri desktop)
- [Typst](https://github.com/typst/typst) CLI (for PDF compilation)

### Web Backend

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Seed demo data (23 users, password: 666666)
python seed.py

# Run server
uvicorn peerpedia_api.main:app --port 8080 --reload
```

### Web Frontend

```bash
cd frontend
npm install
npm run dev    # → http://localhost:5173
```

### Tauri Desktop（开发模式）

```bash
cd frontend
npm run tauri dev    # → 启动 Tauri 窗口
```

### Demo Users（23 位科学家）

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

## Core Concepts

### Articles as Git Repositories

Every article is an independent Git repository. Writing, editing, forking, and merging all map to Git operations:

- Complete version history, forever
- Side-by-side diffs between any two versions (diff2html)
- Fork → modify → merge proposal workflow
- Immutable audit trail for every change

### Five-Dimensional Scoring

All reviews use five dimensions:

| Dim | Name | What it measures |
|-----|------|-----------------|
| **O** | Originality | How novel is the contribution? |
| **R** | Rigor | Are the methods and arguments sound? |
| **C** | Completeness | Is the work thorough and self-contained? |
| **P** | Pedagogy | Is it well-written and accessible? |
| **I** | Impact | How significant is this for the field? |

### Sedimentation Pool (沉淀池)

New articles enter a **sedimentation pool** for community review:

- Higher scores **shorten** the review period; lower scores **extend** it
- Reviews are anonymous during the pool phase
- Authors can rebut each review via thread replies
- When the timer expires, the article is **published**

The pool is visible to your follow network (followers + following).

### Reputation System

Authors and reviewers earn reputation across four dimensions:

| Dim | Name | What it measures |
|-----|------|-----------------|
| **P** | Professionalism | Quality and integrity of contributions |
| **O** | Objectivity | Fairness and accuracy of reviews |
| **C** | Collaboration | Constructive engagement with peers |
| **R** | Readability | Clarity and accessibility of writing |

Higher reputation → greater voting weight in the pool.

---

## Features

### Desktop（Phase 1 — 冷启动）

- **Offline-first writing**：Markdown/Typst editing with live preview, local compilation, no network needed
- **Local Git version control**：fork, history, diff — full audit trail on your machine
- **Graceful degradation**：network-dependent features (pool, schools, comments) show clear "offline" states instead of errors
- **Browse = cache**：every article you read is automatically cached for offline access; your offline feed is your reading history
- **Bookmark = full cache**：bookmarked articles are cached with complete reviews and history — your offline library
- **Local account system**：bcrypt + SQLite, multi-account switching, no server needed
- **Network status indicator**：real-time online/offline icon in navbar
- Typst → PDF via Tauri sidecar (Slice 2, on-going)
- 5MB install, 30MB RAM

### Web（Phase 2+ — 社区）

- 5D scoring (O/R/C/P/I) with hover-to-edit ScoreBadges
- Sedimentation pool with configurable timers
- Article forking + merge proposals
- Citation graph (references + citations, click-to-navigate)
- JWT authentication (register, login, session restore)
- User profiles with compact ReputationBadges (P/O/C/R)
- Follow/unfollow, activity feed, bookmarks
- Full-text search with category/sort filters and pagination
- Thread-based review discussions（含多轮双作者对话）
- Merge proposals for forked articles
- Contribution slider in publish panel（per-author allocation）
- Chinese/English bilingual UI (vue-i18n, 90+ keys)
- LXGW WenKai calligraphic brand font + Noto Serif SC headings
- Waypoints constellation icon as brand mark + Tauri app icon
- Client-side Markdown compilation (marked + KaTeX, no server round-trip)
- CI pipeline: 11 jobs across Python, TypeScript, Rust
- Typed localStorage abstraction (`useLocalStorage`) — centralized I/O for 8 consumers

---

## Project Structure

```
peerpedia/
├── frontend/                  # Vue 3 SPA + Tauri
│   ├── src/
│   │   ├── api/               # Axios API modules
│   │   ├── components/        # 14 components (SelfReviewPanel, ReviewPanel, etc.)
│   │   ├── composables/       # Shared logic (useLocalStorage, useTauri, useDraftPersistence, useBookmarkToggle, useStatusMap, useAsyncResource)
│   │   ├── locales/           # i18n (zh-CN, en-US)
│   │   ├── pages/             # Route pages（含 LoginPage）
│   │   ├── router/            # Vue Router + auth guards
│   │   └── stores/            # Pinia (user, article, pool, review)
│   └── src-tauri/             # Tauri Rust backend
│       └── src/
│           ├── main.rs        # Tauri entry
│           ├── commands.rs    # IPC handlers
│           ├── local_auth.rs  # 本地账号 CRUD + bcrypt
│           └── local_store.rs # 草稿 + 文章缓存 SQLite
├── backend/                   # FastAPI server
│   └── peerpedia_api/
│       ├── routes/            # REST endpoints
│       ├── schemas/           # Pydantic models
│       └── tests/             # Integration tests
├── core/                      # Business logic
│   └── peerpedia_core/
│       ├── storage/           # Git backend + SQLAlchemy ORM
│       ├── workflow/          # Scoring, reputation, sedimentation
│       └── config/            # Parameters
├── docs/
│   ├── DESIGN.md              # Design document
│   └── api-contract.json      # OpenAPI 3.1 specification
└── seed.py                    # Demo data seeder（23 users）

---

## Testing

```bash
# Backend (166 tests)
source .venv/bin/activate
python -m pytest backend/tests/ -q

# Frontend (172 tests, 28 test files)
cd frontend
npx vitest run

# Rust (Tauri backend — requires Rust toolchain)
cd frontend/src-tauri
cargo test
```

**CI Pipeline:** 11 jobs across 3 languages. Every PR must pass pytest, vitest, ruff, clippy, vue-tsc, rustfmt, and a build smoke test. See `.github/workflows/ci.yml`.

---

## Contributing

**We need you.** Seriously. This project has ambition far beyond its current resources.

### What we're missing

- **UI/UX polish** — many screens work but don't feel great yet
- **Accessibility** — keyboard nav, screen readers, focus management
- **Performance** — bundle size, lazy loading, API response caching
- **Testing** — coverage is decent but far from comprehensive
- **Mobile** — it works but wasn't designed for small screens
- **Error handling** — edge cases abound, graceful degradation is spotty
- **Deployment** — no Docker, no CI/CD pipeline, no production guide
- **Security audit** — JWT works but hasn't been externally reviewed
- **Documentation** — DESIGN.md exists but needs more detail
- **i18n** — Chinese/English translations need refinement

### How to start

1. Read `docs/DESIGN.md` for design philosophy
2. Check `CLAUDE.md` for development conventions
3. Pick an issue or propose something you care about
4. Follow TDD: write failing test → implement → refactor

No contribution is too small. Fix a typo. Translate a string. Write a test. Every bit helps.

---

## License

MIT. Content published via PeerPedia is CC BY-SA 4.0 by default.

---

*"走向更好的学术 — To a better academia."*
