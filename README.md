# PeerPedia

**Decentralized academic publishing — where articles sink or swim by merit alone.**

PeerPedia is an open-source platform that combines Git-backed version control with blind peer review and community-driven scoring. Think: GitHub meets arXiv, with a built-in reputation system.

_This is an on-going Vibe-coding project with Claude code + Deepseek V4, awaiting for your contribution_

---

## Why PeerPedia?

Academic publishing is broken. Journals charge thousands for access. Reviewers work for free. Authors wait months for decisions. And the incentives reward prestige over quality.

PeerPedia replaces the journal with a **sedimentation pool**: every article enters an anonymous review period. Community members rate it on five dimensions. High-quality work surfaces faster; low-quality work sinks. No editors. No paywalls. Just merit.

| Problem | PeerPedia Solution |
|---------|-------------------|
| Paywalled knowledge | All articles free, CC BY-SA 4.0 |
| Opaque peer review | Transparent 5D scoring (O/R/C/P/I) |
| No version history | Git-native: every edit is a commit |
| Centralized gatekeeping | Community-governed sedimentation pool |
| Weak author incentives | Reputation system rewards quality reviewing |
| Siloed platforms | Fork, merge, cite — like GitHub for science |

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
| Frontend | Vue 3, TypeScript, Vite, Tailwind CSS, Pinia |
| Backend | Python 3, FastAPI, SQLAlchemy, SQLite |
| Storage | Git repositories (one per article) |
| Auth | JWT (bcrypt passwords, 24h expiry) |
| Compilation | Typst (→ SVG/PDF), Python Markdown (→ HTML) |
| Math | KaTeX (display + inline) |

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

Every article is an independent Git repository. Writing, editing, forking, and merging all map to Git operations. This means:
- Complete version history, forever
- Side-by-side diffs between any two versions
- Fork → modify → merge proposal workflow (just like GitHub PRs)
- Immutable audit trail for every change

### Five-Dimensional Scoring

All reviews use five dimensions:

| Dimension | What it measures |
|-----------|-----------------|
| **O**riginality | How novel is the contribution? |
| **R**igor | Are the methods and arguments sound? |
| **C**ompleteness | Is the work thorough and self-contained? |
| **P**edagogy | Is it well-written and accessible? |
| **I**mpact | How significant is this for the field? |

### Sedimentation Pool

New articles enter a **sedimentation pool** for a fixed period (default 7 days). During this time:
- Community members submit anonymous reviews
- Higher scores **shorten** the time; lower scores **extend** it (up to 180 days)
- Authors can rebut each review via thread replies
- When the timer expires, the article is **published** (or sinks if score is too low)

The pool is visible only to your follow network (followers + following), not the entire public.

### Blind Review with Identity Protection

- **Pool reviews**: Anonymous (reviewer's `anonymous_name` is shown). These stay anonymous **forever** — even after the article is published — to prevent cross-referencing attacks that could deanonymize reviewers.
- **Published reviews**: Real names.
- **Self-reviews**: Always show the author's real name. The author's identity is already public.

### Reputation System (planned)

Authors and reviewers earn reputation across four dimensions:
- **Professionalism** — quality of submitted work
- **Objectivity** — fairness of reviews given
- **Collaboration** — constructive engagement in discussions
- **Pedagogy** — clarity of writing and explanations

Higher reputation → greater voting weight in the sedimentation pool.

---

## Features

### Implemented

- Markdown + Typst editing with live preview
- Git-backed version history with diff viewer (diff2html, side-by-side)
- 5D scoring (self-review at submission + community review)
- Sedimentation pool with configurable timers
- Article forking + merge proposals
- Citation graph (references + citations, click-to-navigate)
- JWT authentication (register, login, session restore)
- User profiles with reputation radar chart
- Bookmarks, follow/unfollow, activity feed
- Full-text search
- Source + PDF download (Typst → PDF, Markdown → HTML)
- Thread-based review discussions (author rebuttal)
- Self-review identity protection (real name, not anonymous)

### Roadmap

| Priority | Feature | Status |
|----------|---------|--------|
| 🔴 | Commit message required on submit/edit | Planned |
| 🔴 | Pool review freeze after article publishes | Planned |
| 🔴 | History timestamps with second precision | Planned |
| 🟡 | Reputation-weighted scoring | Planned |
| 🟡 | AI-assisted review (bias detection, quality checks) | Planned |
| 🟡 | LaTeX support | Planned |
| 🟢 | P2P distributed storage (IPFS or similar) | Research |
| 🟢 | Federated identity (ORCID, institutional login) | Research |
| 🟢 | Production deployment guide (Docker, CI/CD) | Research |

---

## Project Structure

```
peerpedia/
├── frontend/                  # Vue 3 SPA
│   └── src/
│       ├── api/               # Axios API modules (13 files)
│       ├── components/        # Reusable Vue components
│       ├── composables/       # Shared logic (useBookmarkToggle, etc.)
│       ├── pages/             # Route pages (10 pages)
│       ├── router/            # Vue Router + auth guards
│       └── stores/            # Pinia state management
├── backend/                   # FastAPI server
│   └── peerpedia_api/
│       ├── routes/            # REST endpoints (11 route modules)
│       ├── schemas/           # Pydantic models
│       └── tests/             # Integration tests
├── core/                      # Business logic library
│   └── peerpedia_core/
│       ├── storage/           # Git backend + SQLAlchemy ORM
│       ├── workflow/          # Scoring, reputation, sedimentation
│       └── config/            # Parameters and settings
├── design/
│   ├── brainstorm.md              # Product vision brainstorm (source of truth)
│   └── self-test-checklist.md     # Manual QA test script
├── docs/
│   └── DESIGN.md                  # Consolidated design doc (architecture, features, API)
├── frontend/
│   ├── need.md                    # Requirements specification (Chinese)
│   └── comment_need.md            # Review UI requirements (Chinese)
└── seed.py                        # Demo data seeder
```

---

## Testing

```bash
# Backend (195 tests)
cd backend
python -m pytest core/tests/ backend/tests/ -q

# Frontend (116 tests)
cd frontend
npm test -- --run
```

---

## Contributing

PeerPedia is in active early development. We welcome contributions!

**Good first issues:**
- UI polish (dark theme consistency across components)
- Test coverage for edge cases
- Documentation improvements
- Typst/Markdown compilation enhancements

**Before contributing:**
1. Read `design/outline.md` for the feature philosophy
2. Read `frontend/need.md` for the API contract and requirements
3. Check `CLAUDE.md` for development conventions

All contributions should include tests (TDD preferred).

---

## Vision

> A world where academic knowledge flows freely, quality is determined by community consensus rather than editorial boards, and every researcher — regardless of institution or nationality — has equal opportunity to contribute and be recognized.

PeerPedia is not just a platform. It's an experiment in whether decentralized governance can produce better academic outcomes than the centralized journal system we've relied on for 300 years.

If that sounds interesting, [join us](#contributing).

---

## License

MIT — Protocol is free, reference implementation is MIT.

Content published via PeerPedia is CC BY-SA 4.0 by default.

---

*"To a better academia."*
