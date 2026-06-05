# PeerPedia Status — 2026-06-05

Architecture redesigned. Old monolithic FastAPI+Jinja2 app replaced with 3-layer architecture.

## Architecture

```
frontend/ (Vue 3 + Vite, port 5173) → HTTP JSON → backend/ (FastAPI, port 8080) → core/ (peerpedia_core)
```

## Test counts

| Layer | Tests | Command |
|-------|-------|---------|
| Backend (core + api) | 194 | `.venv/bin/python3 -m pytest core/tests/ backend/tests/` |
| Frontend | 116 | `cd frontend && npm test` |
| **Total** | **310** | |

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
- **Per-commit independent scoring**: compute_article_score_for_commit filters reviews by commit_hash, UniqueConstraint updated
- **API contract alignment**: 18 gaps resolved between backend schemas and frontend types (ArticleSummary expansion, author resolution, bookmark status, etc.)
- **9 frontend pages**: Home, Editor, Article, User, Pool, History, Search, Bookmarks, Citations
- **PDF download endpoint**: GET /articles/{id}/download/pdf (Typst→PDF, Markdown→HTML)
- **Bookmark toggle API integration**: All 5 pages now call addBookmark/removeBookmark API (was local-only stub)
- **Design system**: Cold Academic Minimal (9 colors, #0d1117, #7b8c9e accent, EB Garamond/Inter/JetBrains Mono)
- **Authentication system**: backend (JWT + bcrypt, 3 auth endpoints) + frontend (AuthModal, NavBar auth states, router guards, store)
- **Article page download buttons**: Source + PDF download on article metadata bar
- **HomePage welcome state**: unauthenticated visitors see brand landing page with Sign In/Register
- **EditorPage fixes**: functional splitter drag (20%-80%), separate Source/PDF download buttons always visible
- **Seed data**: 8 demo users with usernames, password `666666` (memo in TEST_USERS.txt)
- **need.md refreshed**: all status markers consistent with actual implementation
- **Review UI redesign**: sharp StarRating stars (gold, HeroIcon path), hover-to-edit scores on own review, Thread dropdowns on all reviews (iMessage style), reply gate (author + reviewer only), review form with comment input, empty thread state
- **Schools page**: global user directory at `/schools` — avatar, affiliation, article count, reputation, expertise tags, follow button. UserSummary expanded with article_count + reputation

## Remaining

| Priority | Task |
|----------|------|
| Medium | `POST /compile-download` endpoint (new article PDF download) |
| Low | `GET /articles/{id}/has-forked` and `POST /articles/{id}/publish` endpoints not wired in frontend |
| Deferred | P2P distributed storage |
| Deferred | AI integration |

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
