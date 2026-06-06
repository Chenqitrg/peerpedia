# PeerPedia · 知诸网

**An interconnected note-taking platform — where ideas link, evolve, and are judged on merit.**

PeerPedia combines Git-backed version control with community review and scoring. Think: a knowledge graph meets collaborative notebook, with reputation-weighted peer assessment.

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

PeerPedia is in active development. Contributions welcome!

**Before contributing:**
1. Read `docs/DESIGN.md` for design philosophy
2. Check `CLAUDE.md` for development conventions
3. Follow TDD: write failing test → implement → refactor

---

## Vision

> A world where knowledge connects freely — every idea can link to, build upon, and refine every other idea. Quality emerges from community consensus, not gatekeepers. Every contributor earns recognition proportional to their impact.

PeerPedia is an experiment in whether interconnected, community-governed knowledge can outperform the siloed platforms we've relied on for decades.

---

## License

MIT. Content published via PeerPedia is CC BY-SA 4.0 by default.

---

*"走向更好的学术 — To a better academia."*
