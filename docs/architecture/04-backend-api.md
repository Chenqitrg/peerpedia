# 04 — Backend & API

> FastAPI server, database models, auth flow, Git operations. Phase 2 web backend, also serves Phase 1 Tauri clients.

## 1. Server Architecture

```
FastAPI (main.py)
├── CORS middleware (allows localhost:5173, tauri://localhost)
├── JWT auth dependency (get_current_user)
├── Routers (14 modules)
│   ├── /api/v1/auth/*        — register, login, profile sync
│   ├── /api/v1/articles/*     — CRUD, fork, publish, history, diff, source
│   ├── /api/v1/users/*        — list, profile, follow/unfollow
│   ├── /api/v1/reviews/*      — submit, list, thread messages
│   ├── /api/v1/search         — full-text search
│   ├── /api/v1/feed*          — activity feed, feed cache
│   ├── /api/v1/pool*          — sedimentation pool
│   ├── /api/v1/bookmarks*     — CRUD
│   ├── /api/v1/citations*     — citation graph, click tracking
│   ├── /api/v1/compile*       — on-demand Markdown/Typst compilation
│   ├── /api/v1/merge*         — merge proposals
│   └── /health                — health check (no auth)
├── SQLAlchemy (SQLite)
│   └── 9 entity models
├── Git Manager (git_manager.py)
│   └── Bare repos at ~/.peerpedia/articles/{uuid}/
└── Compile Backends
    ├── MarkdownBackend (marked + KaTeX, server-side for PDF)
    └── TypstBackend (typst CLI, SVG + PDF)
```

## 2. Database Models (9 Entities)

```
articles ──< article_authors >── users
articles ──< reviews >── review_messages
articles ──< bookmarks >── users
articles ──< citations ── articles
articles ──< merge_proposals >── users
users ──< follows ── users
```

### Key Model Details

**Article:**
- `id`: UUID string (not auto-increment — matches git repo name)
- `status`: 'draft' | 'sedimentation' | 'published'
- `score`: JSON dict {O, R, C, P, I} — cache, recalculated from reviews
- `forked_from`, `fork_count`: fork tracking
- `sink_start`, `sink_duration_days`: sedimentation pool timing
- `compiled_format`: 'html' | 'svg' — format hint, NOT the output
- **Not stored:** `compiled_output`, `compiled_pages` — on-demand compile

**ArticleAuthor:**
- Join table with `position` column for author ordering
- `UniqueConstraint(article_id, author_id)`
- Replaces old `Article.authors` JSON field

**Review:**
- `scope`: 'pool' (anonymous) | 'published' (real name)
- `scores`: JSON dict {O, R, C, P, I}
- `contributions`: dict[author_id → {O, R, C, P, I}] — per-author ratios
- `UniqueConstraint(article_id, reviewer_id, scope, commit_hash)`
- One review per reviewer per commit per scope

**ReviewMessage:**
- Threaded via `parent_id` self-referencing FK
- Replaces old `Review.thread` JSON field

**User:**
- `reputation`: JSON dict {P, O, C, R} — four-dimension reputation
- `anonymous_name`: used for pool reviews
- `password_hash`: bcrypt

## 3. Auth Flow

### Registration
```
POST /api/v1/auth/register
  Body: { username, password, name, email? }
  → bcrypt(password) → password_hash
  → INSERT user
  → create_jwt(user_id) → 24h expiry
  → Response: { user, token }
```

### Login
```
POST /api/v1/auth/login
  Body: { username, password }
  → SELECT user WHERE username
  → bcrypt.check(password, password_hash)
  → create_jwt(user_id)
  → Response: { user, token }
```

### JWT Structure
```python
payload = {
  'sub': user_id,
  'exp': now + 24h,
  'iat': now
}
token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
```

### Auth Dependency
```python
async def get_current_user(token: str = Header(...)) -> User:
    payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
    user = db.query(User).filter(User.id == payload['sub']).first()
    if not user: raise HTTPException(401)
    return user
```

### Profile Sync (L4)
```
PUT /api/v1/auth/profile
  → Updates user.name, user.email, user.affiliation, user.expertise
  → Best-effort: called after trySyncServerAuth()
  → Used to push local Tauri profile changes to server
```

## 4. Article Operations

### Create (POST /api/v1/articles)
```
1. Generate UUID
2. git_manager.init_repo(article_id) → bare git repo
3. git_manager.commit(content, title, commit_message) → commit_hash
4. INSERT article (id, title, status='draft', commit_hash)
5. INSERT article_authors
6. Return ArticleDetail
```

### Update (PUT /api/v1/articles/{id})
```
1. Verify auth (article owner)
2. git_manager.commit(content, title, commit_message) → new_hash
3. UPDATE article metadata
4. Return ArticleDetail with new commit_hash
```

### Fork (POST /api/v1/articles/{id}/fork)
```
1. Clone source repo
2. Create new repo with forked_from = source.id
3. Increment source.fork_count
4. Return new ArticleDetail
```

### Publish (POST /api/v1/articles/{id}/publish)
```
1. Verify auth (article owner)
2. Verify status = 'draft'
3. SET status = 'sedimentation', sink_start = now()
4. Sink duration based on score (higher score → shorter wait)
5. Background task publish_ready_articles() auto-publishes when timer expires
```

## 5. Git Manager

**Storage:** Bare Git repos at `~/.peerpedia/articles/{uuid}/`

**Operations:**
- `init_repo(id)`: `git init --bare`
- `commit(content, title, message)`: Write content to file, `git add`, `git commit -m "title: message"`
- `get_history(id)`: `git log --format=...` → list of commits
- `get_content(id, commit_hash?)`: `git show {hash}:article.md` (or .typ)
- `get_diff(id, hash1, hash2)`: `git diff hash1..hash2`
- `rollback(id, hash)`: `git reset --hard hash`

**Design note:** Git repos are bare — no working tree. Content is written via `git hash-object` + `git update-ref`. This avoids checkout overhead.

## 6. Health Endpoint

```
GET /health → { "status": "ok" }
```

- No database query (pure HTTP response)
- Used by useNetworkStatus.ping() for connectivity check
- Description updated: "on-demand connectivity checks (user-initiated SyncButton tap)"

## 7. API Contract

Full OpenAPI 3.0 spec at `docs/api-contract.json`. Autogenerated from FastAPI + manual annotations.

Key endpoints summary:

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /auth/register | No | Register + get JWT |
| POST | /auth/login | No | Login + get JWT |
| PUT | /auth/profile | Yes | Sync Tauri profile to server |
| GET | /articles | No | List (drafts invisible to others) |
| POST | /articles | Yes | Create draft |
| GET | /articles/{id} | No | Detail (drafts: owner only) |
| PUT | /articles/{id} | Yes | Update (owner only) |
| DELETE | /articles/{id} | Yes | Delete (owner only) |
| GET | /articles/{id}/source | No | Raw Markdown/Typst source |
| GET | /articles/{id}/history | No | Git commit history |
| GET | /articles/{id}/diff/{h1}/{h2} | No | Git diff |
| POST | /articles/{id}/fork | Yes | Fork article |
| POST | /articles/{id}/publish | Yes | Publish to pool (owner only) |
| POST | /articles/{id}/reviews | Yes | Submit/update review |
| GET | /articles/{id}/reviews | No | List reviews |
| POST | /articles/{id}/reviews/{rid}/messages | Yes | Post thread reply |
| GET | /search?q=&mode= | No | Full-text search |
| GET | /users | No | List users |
| GET | /users/{id} | No | User profile |
| POST | /users/{id}/follow | Yes | Follow |
| DELETE | /users/{id}/follow | Yes | Unfollow |
| GET | /feed | No | Activity feed |
| GET | /feed/cache | Yes | Lightweight offline cache |
| GET | /pool | No | Sedimentation pool |
| GET | /bookmarks | Yes | List bookmarks |
| POST | /bookmarks/{id} | Yes | Add bookmark |
| DELETE | /bookmarks/{id} | Yes | Remove bookmark |
| GET | /citations/{id} | No | Citation graph |
| POST | /citations/click | No | Record citation click |
| POST | /compile-preview | No | Compile Markdown/Typst |
| GET | /health | No | Health check |

## 8. Design Issues

### I8: SQLite in production

SQLite is the Phase 1 database. It handles concurrent reads well but serializes writes. With one user per Tauri instance, this is fine. With multiple web users writing simultaneously, SQLite's write lock becomes a bottleneck. Migration path to PostgreSQL is documented but not started.

### I9: No rate limiting

No rate limiting on any endpoint. `/health` could be hammered. Auth endpoints have no brute-force protection. Acceptable for solo developer phase, critical before public launch.

### I10: JWT fallback secret for development

`JWT_SECRET` comes from `os.environ.get("JWT_SECRET")` with fallback to `"peerpedia-dev-secret"` + `warnings.warn()`. Standard dev pattern. Production deployment must set the env var.

### I11: Git repos grow unbounded

Every article save creates a new commit. No GC, no pruning, no size limits. A single article edited 1000 times has 1000 commits in its bare repo. At ~1KB per commit (metadata), this is negligible. At 1MB per content change, this adds up. No cleanup strategy exists.
