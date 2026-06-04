# PeerPedia Status — 2026-06-05

Architecture redesigned. Old monolithic FastAPI+Jinja2 app replaced with 3-layer architecture.

## Architecture

```
frontend/ (Vue 3 + Vite, port 5173) → HTTP JSON → backend/ (FastAPI, port 8080) → core/ (peerpedia_core)
```

## Test counts

| Layer | Tests | Command |
|-------|-------|---------|
| Backend (core + api) | 173 | `.venv/bin/python3 -m pytest core/tests/ backend/tests/` |
| Frontend | 66 | `cd frontend && npm test` |
| **Total** | **239** | |

## Done

- **Core**: params, types, 7 DB models, 6 CRUD modules (incl. upsert_review), git_backend, compiler (Typst SVG support), workflow (scoring, sedimentation)
- **Backend**: 10 route modules, schemas, CORS, deps
- **Frontend**: API layer (7 modules), 3 Pinia stores, 7 components, 6 pages (incl. functional EditorPage for create+edit), router, App.vue
- **Git**: init repo on create, commit content, history, diff, fork, rollback
- **E2E verified**: create user → article → git commit → pool → history
- **Bugs fixed**: 24 found in review, all fixed
- **Old code cleaned**: peerpedia_core_old/, peerpedia/, tests/, demo_review.py removed
- **Stale peerpedia_core/ root dir removed** (was shadowing core/peerpedia_core)
- **PUT /articles/{id}**: edit content → new git commit → re-enter pool → upsert self-review
- **Typst compile**: route wired to TypstBackend (SVG format); graceful 500 if CLI not installed
- **Seed data script**: `seed.py` with 8 users, 6 articles, 10 follows, 6 reviews, 4 bookmarks; idempotent
- **Rendered diff**: DiffViewer.vue with side-by-side diff2html, wired into ArticlePage; 7 tests
- **Reputation mechanism**: compute_author_reputation, get_reviewer_weight, recalculate_all_reputations; 14 tests; wired into review submission
- **Bookmarks UI**: tabs (Latest/Favorites) on HomePage; bookmark fetch + article display
- **CSS audit**: 13 design system issues fixed (hardcoded colors → semantic tokens, max-w-content, etc.)

## Remaining

| Priority | Task |
|----------|------|
| Low | DELETE article, Upload endpoint, Feed with content |

## Quick start

```bash
cd /Users/chenqimeng/Projects/peerpedia

# Init database and seed demo data
.venv/bin/python3 -c "
from peerpedia_core.storage.db.engine import get_engine, init_db
init_db(get_engine('sqlite:///peerpedia.db'))
"
.venv/bin/python3 seed.py

# Backend
.venv/bin/uvicorn backend.peerpedia_api.main:app --host 0.0.0.0 --port 8080 --reload

# Frontend
cd frontend && npm run dev

# Tests
.venv/bin/python3 -m pytest core/tests/ backend/tests/
cd frontend && npm test
```

## Project structure

```
peerpedia/
├── core/          peerpedia_core library (business logic, storage)
├── backend/       FastAPI REST API (JSON only)
├── frontend/      Vue 3 + Vite (port 5173)
├── seed.py        demo data seeder
├── design/        outline.md
└── docs/          specs and plans
```

## Design docs

- `design/outline.md` — product requirements
- `.claude/plans/humming-leaping-hartmanis.md` — architecture plan
