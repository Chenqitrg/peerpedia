# PeerPedia Design Document

> 2026-06-06 — consolidated from design/*, STATUS.md, frontend/need.md, and implementation reality

## Product Vision

PeerPedia is GitHub for academic publishing. Articles are git repositories. Review is community scoring. Quality surfaces through a sedimentation pool, not editorial boards.

**Values:**
- Promote the spread of math/physics notes and quality content
- If the reputation mechanism works, eventually replace academic publishers
- All content free, CC BY-SA 4.0 by default

**Competitive position (content strategy):**
Don't compete with journals on publishing. Compete on **content consumption**. Popular science and history readers outnumber academic paper readers by three orders of magnitude.

| | Traditional | arXiv | Wikipedia | PeerPedia |
|---|---|---|---|---|
| Quality control | Editorial monopoly | None | Edit wars | Community scoring + sedimentation |
| Speed | 6-18 months | Instant | Instant | Instant → pool → published |
| Trust | Brand | Individual | Not citable | Scores + reviews + reputation |
| Content | Papers | Preprints | Encyclopedia | Science + history + papers |
| Version history | None | v1/v2 only | Yes | Git full history |
| 5D scoring | No | No | No | Yes |

## Architecture

```
frontend/ (Vue 3 + TS + Tailwind, :5173) → REST JSON → backend/ (FastAPI, :8080) → core/ (peerpedia_core)
```

| Layer | Stack |
|-------|-------|
| Frontend | Vue 3, TypeScript, Vite, Tailwind CSS, Pinia, VueUse, KaTeX |
| Backend | Python 3, FastAPI, SQLAlchemy, SQLite |
| Storage | Git repositories (one per article at `~/.peerpedia/articles/{id}/`) |
| Auth | JWT (bcrypt, 24h expiry) |
| Compilation | Typst → SVG/PDF, Python Markdown → HTML |

## Core Concepts

### Articles as Git Repositories
Every article is a git repo. Writing, editing, forking, and merging all map to git operations: complete version history, side-by-side diffs, fork → modify → merge proposal (like GitHub PRs), immutable audit trail.

### Five-Dimensional Scoring
All reviews use five dimensions (0-5 each):

| Dim | Measures |
|-----|----------|
| **O**riginality | How novel is the contribution? |
| **R**igor | Are methods and arguments sound? |
| **C**ompleteness | Is the work thorough and self-contained? |
| **P**edagogy | Is it well-written and accessible? |
| **I**mpact | How significant is this for the field? |

### Sedimentation Pool
New articles enter the pool for a configurable period (default 7 days for new, 3 for edits). During this time:
- Community members submit anonymous reviews (fixed anonymous name, **never revealed**)
- Higher scores shorten the time (min 2 days); lower scores extend it (max 180 days)
- No community reviews → penalty applied at publish time
- Authors can rebut each review via thread replies
- Author's self-review always shows real name
- Pool visible only to follow network (followers + following)
- When timer expires: publishes or sinks

### Article Lifecycle
```
draft → (publish) → sedimentation → (timer expires) → published
                         ↑
                    edit re-enters pool
```
- **draft**: private, only visible to author on their user page
- **sedimentation**: in pool, visible to follow network
- **published**: public, visible to all

### Blind Review with Identity Protection
- Pool reviews: anonymous (reviewer's `anonymous_name` shown). Stays anonymous **forever**.
- Published reviews: real names.
- Self-reviews: always real name (author identity already public).
- One person can have both a pool (anonymous) and published (real-name) review on the same article.
- Pool review freezes when article publishes; published review is a new independent record.

### Reputation System (planned)
Authors and reviewers earn reputation across four dimensions: Professionalism, Objectivity, Collaboration, Pedagogy. Higher reputation → greater voting weight in pool. Backend infrastructure exists (`compute_author_reputation`, `get_reviewer_weight`), not yet weighted into scoring.

## Feature Checklist

### Implemented ✅

**Navigation & Pages (10 pages):**
- Home (feed from followed users, welcome page for guests, pagination)
- Editor (split-pane Markdown/Typst editor, live compile preview, KaTeX math)
- Article (compiled content, scores, reviews, thread discussions, citation graph, fork/merge)
- Pool (sedimentation articles from network, countdown timers)
- User profile (articles, reputation radar, followers/following)
- History (commit timeline, diff viewer between any two commits)
- Search (full-text, keyword/fulltext)
- Bookmarks (saved articles with optimistic toggle)
- Citations (reference/cited-by DAG, click-to-navigate)
- Schools (global user directory, follow buttons, sorted by article count)

**Article Operations:**
- Create: Markdown or Typst, title/abstract/keywords/categories, self-review (5D scores), publishes to pool
- Edit: content + metadata, new git commit, optional re-enter pool. **Save as draft** (private) or **publish to pool**.
- Fork: clones git repo, creates new article with fork marker, author = current user
- Merge: fork → edit → propose merge to original
- History: full commit timeline, diff between any two hashes (diff2html side-by-side)
- Rollback: create new commit reverting to previous state

**Review System:**
- Submit review: 5D star rating + optional comment
- Thread discussions: author + reviewer can reply (iMessage-style bubbles), bystanders read-only
- Hover-to-edit: own review scores editable on hover, restored on mouseleave
- Per-commit independent scoring
- Scope separation: pool (anonymous) vs published (real name)

**Auth:**
- Register/login/logout with JWT (localStorage)
- Router guards for auth-required pages
- Session restore on page reload
- Auth modal for unauthenticated actions

**Compilation:**
- Typst → SVG (preview) / PDF (download)
- Markdown → HTML with KaTeX math (display `$$` and inline `$`)
- Math rendering unified in `utils/math.ts`

**Social:**
- Follow/unfollow users
- Bookmark articles (optimistic toggle with rollback)
- Activity feed from followed users

**Design System:** Cold Academic Minimal dark theme
- Colors: `#0d1117` page, `#161b22` card, `#b0b8c4` ink, `#7b8c9e` accent
- Fonts: EB Garamond (headings), Inter (body), JetBrains Mono (code)
- Components: `.card`, `.btn-*`, `.input`, `.badge-*`, `.skeleton`, `.prose-custom`

### Not Yet Implemented ❌

| Priority | Feature |
|----------|---------|
| Medium | Reputation-weighted scoring in pool |
| Low | Profile editing page |
| Low | Follow notification |
| Deferred | P2P distributed storage (IPFS or similar) |
| Deferred | Federated identity (ORCID, institutional login) |
| Deferred | AI-assisted review |
| Deferred | LaTeX support |
| Deferred | Production deployment (Docker, CI/CD, public URL) |

## API Contract

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/feed` | optional | Articles from followed users (sedimentation + published only) |
| GET | `/articles` | optional | List articles with optional `status`, `author_id` filters |
| POST | `/articles` | required | Create article and publish to pool |
| GET | `/articles/{id}` | optional | Article detail |
| PUT | `/articles/{id}` | required | Edit article. `publish: true` to re-enter pool, `false` to save draft |
| GET | `/articles/{id}/source` | none | Raw source content |
| GET | `/articles/{id}/history` | none | Commit history |
| GET | `/articles/{id}/diff/{h1}/{h2}` | none | Diff between two commits |
| POST | `/articles/{id}/fork` | required | Fork article |
| POST | `/articles/{id}/publish` | required | Manually publish to pool |
| PUT | `/articles/{id}/sink-extension` | required | Extend sink time |
| GET | `/articles/{id}/has-forked` | required | Check if user already forked |
| POST | `/articles/{id}/rollback/{hash}` | required | Rollback to commit |
| GET | `/articles/{id}/reviews` | none | All reviews |
| POST | `/articles/{id}/reviews` | required | Create/update review |
| POST | `/articles/{id}/reviews/{rid}/messages` | required | Reply in review thread |
| GET | `/articles/{id}/citations` | none | Citation graph |
| POST | `/articles/{id}/citations/click` | required | Record citation click |
| GET | `/pool` | required | Sedimentation pool (network only) |
| GET | `/users` | none | List all users |
| GET/PUT | `/users/{id}` | required | Get/update user profile |
| POST | `/users/{id}/follow` | required | Follow user |
| DELETE | `/users/{id}/follow` | required | Unfollow |
| GET | `/users/{id}/followers` | none | List followers |
| GET | `/users/{id}/following` | none | List following |
| GET/POST/DELETE | `/bookmarks` | required | List/add/remove bookmarks |
| POST | `/auth/register` | none | Register new user |
| POST | `/auth/login` | none | Login, returns JWT |
| GET | `/auth/me` | required | Current user profile |
| POST | `/compile-preview` | none | Compile raw content (Markdown→HTML, Typst→SVG) |
| POST | `/compile-download` | none | Compile and download (Markdown→HTML, Typst→PDF) |
| GET | `/search` | none | Full-text search |
| POST | `/merge/{fork_id}/to/{target_id}` | required | Propose merge |
| GET/PUT | `/merge/{id}` | required | Get/resolve merge proposal |

## Testing

| Layer | Tests | Command |
|-------|-------|---------|
| Backend | 199 | `.venv/bin/python -m pytest core/tests/ backend/tests/ -q` |
| Frontend | 101 | `cd frontend && npx vitest run` |
| **Total** | **300** | |

## Running

```bash
# Backend
.venv/bin/uvicorn peerpedia_api.main:app --port 8080 --reload

# Frontend
cd frontend && npm run dev    # → http://localhost:5173

# Seed demo data (8 users, password: 666666)
.venv/bin/python seed.py
```

See `TEST_USERS.txt` for demo account list.
