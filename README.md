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
frontend/ (Vue 3 + TypeScript + Tailwind)  →  REST JSON  →  backend/ (FastAPI + Python)
                                                              ↓
                                                         core/ (peerpedia_core)
                                                         · Git-backed storage
                                                         · Scoring engine
                                                         · Reputation system
```

### Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vue 3, TypeScript, Vite, Tailwind CSS, Pinia, vue-i18n |
| Backend | Python 3, FastAPI, SQLAlchemy, SQLite |
| Storage | Git repositories (one per article) |
| Auth | JWT (bcrypt passwords) |
| Compilation | Typst (→ SVG/PDF), Python Markdown (→ HTML) |
| Math | KaTeX |

---

## Quick Start

### Prerequisites
- Python 3.12+
- Node.js 18+
- [Typst](https://github.com/typst/typst) CLI (for PDF compilation)

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Seed demo data (8 users, password: 666666)
python ../seed.py

# Run server
uvicorn peerpedia_api.main:app --port 8080 --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev    # → http://localhost:5173
```

### Demo Users

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

### Implemented

- Markdown + Typst editing with live preview and split-pane
- Git-backed version history with side-by-side diff viewer
- 5D scoring (O/R/C/P/I) with hover-to-expand ScoreBadges
- Sedimentation pool with configurable timers
- Article forking + merge proposals
- Citation graph (references + citations, click-to-navigate)
- JWT authentication (register, login, session restore)
- User profiles with compact ReputationBadges (P/O/C/R)
- Follow/unfollow, activity feed, bookmarks
- Full-text search
- Source + PDF download (Typst → PDF, Markdown → HTML)
- Thread-based review discussions
- Chinese/English bilingual UI (vue-i18n, 80+ keys)
- LXGW WenKai calligraphic brand font + Noto Serif SC headings
- Waypoints constellation icon as brand mark

---

## Project Structure

```
peerpedia/
├── frontend/                  # Vue 3 SPA
│   └── src/
│       ├── api/               # Axios API modules
│       ├── components/        # Reusable components (ScoreBadges, UserCard, etc.)
│       ├── composables/       # Shared logic (useBookmarkToggle, useAsyncResource)
│       ├── locales/           # i18n (zh-CN, en-US)
│       ├── pages/             # Route pages
│       ├── router/            # Vue Router + auth guards
│       └── stores/            # Pinia state
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
└── seed.py                    # Demo data seeder
```

---

## Testing

```bash
# Backend
cd backend
source ../.venv/bin/activate
python -m pytest tests/ -q

# Frontend
cd frontend
npm test -- --run
```

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

## Vision

The long game: **replace academic publishers and break the monopoly of prestige.**

Today, a handful of publishers control what counts as knowledge. They charge universities millions for access to research their own faculty produced. They gatekeep careers through journal prestige rather than merit. And they've held this position for 300 years because there was no alternative infrastructure.

PeerPedia is that alternative. Not next year. Not in five years. But the pieces are on the table:

- **Git-native articles** replace publisher versioning
- **Community scoring** replaces editorial gatekeeping
- **Anonymous review** eliminates prestige bias
- **Reputation** replaces impact factors
- **Free and open** replaces paywalls

We're a long way from that. Right now we need help making the basics solid. But every pull request moves the needle.

> A world where knowledge connects freely — every idea can link to, build upon, and refine every other idea. Quality emerges from community consensus, not gatekeepers. Every contributor earns recognition proportional to their impact. No one profits from locking knowledge behind walls.

*"走向更好的学术 — To a better academia."*

---

## License

MIT. Content published via PeerPedia is CC BY-SA 4.0 by default.

---

*"走向更好的学术 — To a better academia."*
