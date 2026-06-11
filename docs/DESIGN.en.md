# PeerPedia (知诸网) — Design Document

> 2026-06-11 · v0.2.2 · L4 follow: Tauri Rust follow commands (follow_user, unfollow_user, is_following, get_following, get_followers) with local SQLite storage · Schools page follow state persistence · User profile fallback for server users in Tauri mode · Article visibility in Tauri+online mode

---

## 1. Vision

PeerPedia is the GitHub of academic publishing. Articles are Git repositories. Reviews are community scores. Quality emerges through a sedimentation pool.

**Goal:** Replace arXiv and traditional journals. Combine Wikipedia's open collaboration, arXiv's preprint scale, and peer review quality — all three in one.

---

## 2. Architecture

### 2.1 Dual Architecture

```
Phase 1 + 1.5 (Tauri Desktop — MVP + Polish)
┌─────────────────────────────────────────────────────────┐
│  Vue 3 → IPC → Rust → SQLite + Git (local)               │
│  Offline writing · client compilation · version control   │
│  Browse = cache · Bookmark = full cache                   │
└─────────────────────────────────────────────────────────┘

Phase 2+ (Web — community)
┌─────────────────────────────────────────────────────────┐
│  Vue 3 SPA → REST → FastAPI → SQLite + Git (server)       │
│  Sedimentation pool · community review · reputation       │
└─────────────────────────────────────────────────────────┘
```

### 2.2 Tech Stack

| Layer | Desktop (Phase 1) | Web (Phase 2+) |
|---|---|---|
| Shell | Tauri 2.x (Rust) | — |
| Frontend | Vue 3 + TS + Vite + Tailwind | Vue 3 + TS + Vite + Tailwind |
| Backend | Rust (rusqlite, bcrypt, libgit2) | Python 3.12+, FastAPI, SQLAlchemy |
| Storage | SQLite + Git repos (local) | SQLite + Git repos (server) |
| Compilation | Markdown: client-side (marked + KaTeX). Typst: Tauri sidecar | Markdown: client-side (marked + KaTeX). Typst: server compiler |
| Auth | bcrypt + SQLite (local accounts) | JWT (bcrypt, 24h expiry) |
| Math | KaTeX | KaTeX |

### 2.3 Source of Truth

**Git is the source of truth. Database is an index.**

The write path for all article content follows this invariant:

```
User request → Git commit (content) → success → DB upsert (metadata index)
                ↓ failure
              Return error (no DB write)
```

- Article content (Markdown/Typst source) lives in Git repositories at `~/.peerpedia/articles/{id}/`.
- Database stores metadata (title, status, score, relationships) for fast queries.
- If the database is lost, it can be rebuilt from Git repositories. Git retains fork/diff/merge history.
- Compile output is **never** stored in the database — it is generated on-demand with a filesystem cache.

### 2.3-bis Git-First Content Loading (2026-06-10)

Article content in Tauri mode is now read directly from git (`git_show`) on every page load, not from the draft cache. This ensures rollback and other git operations are immediately visible — no cache chain to go stale.

```
Before: git → article_cache → draft → compiled_output → UI  (stale after rollback)
After:  git → content (git_show) → compile → UI            (always fresh)
        draft → metadata only (title, author, format)
```

The `article_cache` SQLite table is an optional network-speed optimization, never a content authority. ArticlePage in Tauri mode skips it entirely and sources content from git.

### 2.4 Article Sync (L4)

Every save in Tauri mode auto-uploads the article to the server as a private draft (like a GitHub private repo). Publish is a separate, explicit action.

```
Save → auto POST/PUT /articles (status=draft)
     → server_article_id + server_commit_hash stored locally

Next save → local HEAD ≠ server_commit_hash → GitCompare icon
     → "Keep Local" = PUT local changes to server
     → "Use Remote" = git rollback to server version
     → Both resolve the conflict and update server_commit_hash

Publish → POST /articles/{id}/publish → enters sedimentation pool
```

**Design principles:**
- No manual Upload button — backup is automatic and silent
- Draft ≠ published — articles on the server stay private until explicitly published
- Conflict resolution IS sync — no separate Push/Pull, just compare hashes
- Follow works fully offline via local SQLite in Tauri mode, with server sync deferred to Phase 2. Bookmark requires server connection — offline shows disabled state, not silent failure.

### 2.5 Offline Architecture

Phase 1 desktop is fully offline-capable (with L4 auto-backup when online):

- **Browse = cache**: every article read is automatically cached in local SQLite.
- **Bookmark = full cache**: bookmarked articles cache reviews + citation graph.
- **Network status**: `useNetworkStatus` with Wifi/WifiOff icon. Starts offline, flips online on first successful ping — no 60s window where offline features incorrectly appear accessible.
- **Network-blocked features**: `useOffline` permanently blocks pool and search.network in local/Tauri mode. Schools is available in Tauri mode (user list fetched from server API). Follow/unfollow works locally via Tauri IPC. These offline features show a disabled state (grayed icons with tooltip), not an error after navigation.
- **Save = Git commit**: every draft save creates or updates a local Git repository (`local_git.rs`). Commit history is available offline via `git log`.
- **Download = committed artifact**: download filenames embed the 7-char commit hash (e.g., `Title-a1b2c3d.pdf`). Downloads are disabled until the first save — every downloaded file is tied to a committed version. Source downloads use `.typ`/`.md` extension, compiled Markdown → `.html`, compiled Typst → `.pdf` (via server-side `/compile-download` API). In the article page, labels are shown; in the editor toolbar, icons only with instant tooltips.
- **Save-as-commit**: each save in Tauri/local mode triggers a git commit. The commit message popup opens for every save — `commitMsg` is cleared after each successful commit, forcing a fresh message per save.
- **Save button state**: the save button is disabled (grayed out, `opacity-30`) when no unsaved changes exist (`isClean` computed compares content/title against last saved state).
- **Local accounts**: bcrypt + SQLite, multi-account switching, no server required.
- **Client-side compilation**: Markdown → HTML via `marked` + KaTeX. The compilation pipeline (protect math → parse markdown → restore math → render KaTeX) runs entirely in the browser.

Key composables: `useNetworkStatus`, `useOffline`, `useTauri`, `useDraftPersistence`.
Key Rust modules: `local_auth`, `local_store`, `local_git`.

---

## 3. Data Model — 9 Entities

All relationships use proper join tables. No relationship data is stored as JSON.

### 3.1 Article

```python
class Article(Base):
    __tablename__ = "articles"

    id = Column(String, primary_key=True, default=uuid4)
    title = Column(String, default="")
    abstract = Column(String, nullable=True)
    keywords = Column(JSONList)               # ["physics", "quantum"]
    categories = Column(JSONList)             # ["theory", "experiment"]
    status = Column(String, default="draft")  # draft | sedimentation | published
    score = Column(JSONDict)                  # FiveDimScores cache (recalculated in Phase 2)
    compiled_format = Column(String)          # "html" | "svg" (format hint, not output)
    sink_start = Column(DateTime)
    sink_duration_days = Column(Integer, default=7)
    sink_extended_count = Column(Integer, default=0)
    forked_from = Column(String, nullable=True)
    fork_count = Column(Integer, default=0)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
```

- `authors` is **not** a column — use `article_authors` join table.
- `compiled_output` / `compiled_pages` are **not** stored — compile is on-demand with filesystem cache.
- `score` will be demoted from DB column to computed property in Phase 2.
- JSONList/JSONDict are SQLAlchemy TypeDecorators storing JSON strings in SQLite. Used only for fixed-shape data (keywords, categories, scores) — **never** for relationships.

### 3.2 ArticleAuthor

```python
class ArticleAuthor(Base):
    __tablename__ = "article_authors"
    __table_args__ = (UniqueConstraint("article_id", "author_id"),)

    article_id = Column(String, ForeignKey("articles.id"), primary_key=True)
    author_id = Column(String, ForeignKey("users.id"), primary_key=True)
    position = Column(Integer, default=0)    # preserves author ordering
    created_at = Column(DateTime)
```

Replaces the old `Article.authors` JSON field. Enables efficient "find articles by author" via SQL join.

### 3.3 Review

```python
class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("article_id", "reviewer_id", "scope", "commit_hash"),
    )

    id = Column(String, primary_key=True)
    article_id = Column(String, ForeignKey("articles.id"))
    commit_hash = Column(String)
    reviewer_id = Column(String, ForeignKey("users.id"))
    scope = Column(String)                   # "pool" (anonymous) | "published" (real name)
    scores = Column(JSONDict)                # FiveDimScores
    contributions = Column(JSONDict, nullable=True)  # per-author contribution ratios
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
```

- `thread` is **not** a column — use `review_messages` table.
- `contributions`: dict[author_id → {O, R, C, P, I}] with each dimension 0-1.

### 3.4 ReviewMessage

```python
class ReviewMessage(Base):
    __tablename__ = "review_messages"

    id = Column(String, primary_key=True, default=uuid4)
    review_id = Column(String, ForeignKey("reviews.id"))
    parent_id = Column(String, ForeignKey("review_messages.id"), nullable=True)
    author_id = Column(String, ForeignKey("users.id"))
    content = Column(String)
    created_at = Column(DateTime)
```

Replaces the old `Review.thread` JSON field. Supports pagination, search, and concurrent writes. Threaded via `parent_id` self-referencing FK.

### 3.5 User

```python
class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=uuid4)
    username = Column(String, unique=True)
    password_hash = Column(String)           # bcrypt
    email = Column(String, nullable=True)
    name = Column(String)
    anonymous_name = Column(String, default="")
    affiliation = Column(String, default="")
    expertise = Column(JSONList, default=[])
    avatar_url = Column(String, nullable=True)
    contact = Column(String, nullable=True)
    reputation = Column(JSONDict, default={})  # P/O/C/R scores
    created_at = Column(DateTime)
```

### 3.6 Follow, Bookmark, MergeProposal, Citation

```python
class Follow(Base):
    follower_id = Column(String, FK("users.id"), primary_key=True)
    followed_id = Column(String, FK("users.id"), primary_key=True)

class Bookmark(Base):
    user_id = Column(String, FK("users.id"), primary_key=True)
    article_id = Column(String, FK("articles.id"), primary_key=True)

class MergeProposal(Base):
    id = Column(String, primary_key=True)
    fork_article_id = Column(String, FK("articles.id"))
    target_article_id = Column(String, FK("articles.id"))
    proposer_id = Column(String, FK("users.id"))
    status = Column(String, default="open")  # open | accepted | rejected
    created_at = Column(DateTime)
    resolved_at = Column(DateTime, nullable=True)

class Citation(Base):
    from_article_id = Column(String, FK("articles.id"), primary_key=True)
    to_article_id = Column(String, FK("articles.id"), primary_key=True)
```

All pure join tables. No JSON. No probability fields (removed in P0 refactor). MergeProposal thread deferred to Phase 2.

### 3.7 Entity Relationship Diagram

```
articles ──< article_authors >── users
articles ──< reviews >── review_messages
articles ──< bookmarks >── users
articles ──< citations ── articles
articles ──< merge_proposals >── users
users ──< follows ── users
```

---

## 4. Scoring System

### 4.1 Five-Dimension Article Scores (O/R/C/P/I)

| Dim | Name | Range | Measures |
|-----|------|-------|----------|
| O | Originality | 0-5 | How novel is the contribution? |
| R | Rigor | 0-5 | Are methods and arguments sound? |
| C | Completeness | 0-5 | Is the work thorough and self-contained? |
| P | Pedagogy | 0-5 | Is it well-written and accessible? |
| I | Impact | 0-5 | How significant for the field? |

### 4.2 Four-Dimension Reputation (P/O/C/R)

| Dim | Name | Measures |
|-----|------|----------|
| P | Professionalism | Quality and integrity of contributions |
| O | Objectivity | Fairness and accuracy of reviews |
| C | Collaboration | Constructive engagement |
| R | Readability | Clarity and accessibility |

Reputation determines voting weight in the pool.

### 4.3 Sedimentation Pool

1. Article enters pool with `sink_start` timestamp.
2. Sink duration is a function of average review score: higher scores → shorter wait.
3. Reviews during pool phase use anonymous names.
4. When timer expires → auto-publish via `publish_ready_articles()` background task.
5. Articles with zero community reviews receive a penalty to their score.

---

## 5. Compilation

### 5.1 Client-Side Pipeline (Default for Markdown)

Markdown compilation uses a four-stage pipeline in `frontend/src/utils/markdown.ts`:

```
protect math → marked.parse() → restore math → renderMathInHtml()
```

**Math protection** replaces `$$...$$` and `$...$` with unique placeholders (`PEERPEDIA-MATH-D0`, etc.) to prevent `marked` from corrupting LaTeX. Two critical fixes:
- Placeholders use hyphens (`PEERPEDIA-MATH-D0`) because `marked`'s GFM parser interpreted underscores (`_MATH_`) as emphasis markers.
- `restoreMath` uses `split/join` instead of `String.replace()` because JavaScript's `replace()` interprets `$$` in the replacement string as a literal `$`, collapsing KaTeX display-mode delimiters.

### 5.2 On-Demand with Filesystem Cache

Compile output is **never** stored in the database. The compile endpoint generates HTML/SVG on each request and caches the result to disk:

```
~/.peerpedia/cache/{article_id}/{commit_hash}.{html|svg}
```

- Cache key = `commit_hash` — same commit always produces the same output.
- Cache miss → MarkdownBackend or TypstBackend compiles → write cache.
- Clean cache: `rm -rf ~/.peerpedia/cache/`.
- Compiler upgrades: delete cache, next request triggers recompile.
- Markdown: ~50ms. Typst: ~500ms. Cache hit: ~1ms.

### 5.3 Supported Formats

| Format | Desktop (Phase 1) | Web (Phase 2+) |
|--------|------------------|----------------|
| Markdown → HTML | Client-side (marked + KaTeX) | Client-side (marked + KaTeX) |
| Typst → SVG | Tauri sidecar CLI ✅ | Server compiler |
| Typst → PDF | Tauri sidecar CLI (TODO) | Server compiler |

---

## 6. API Design

### 6.1 REST Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/register` | Register |
| POST | `/api/v1/auth/login` | Login (returns JWT) |
| GET | `/api/v1/articles` | List articles (status, author, page filters) |
| POST | `/api/v1/articles` | Create article as draft (Git commit + DB metadata; publish via `/publish`) |
| GET | `/api/v1/articles/{id}` | Article detail |
| PUT | `/api/v1/articles/{id}` | Update article |
| GET | `/api/v1/articles/{id}/source` | Raw Markdown/Typst source |
| GET | `/api/v1/articles/{id}/history` | Git commit history |
| GET | `/api/v1/articles/{id}/diff/{h1}/{h2}` | Side-by-side diff |
| POST | `/api/v1/articles/{id}/fork` | Fork article |
| POST | `/api/v1/articles/{id}/publish` | Publish to pool |
| GET | `/api/v1/articles/{id}/reviews` | List reviews |
| POST | `/api/v1/articles/{id}/reviews` | Submit/update review |
| POST | `/api/v1/articles/{id}/reviews/{rid}/messages` | Post thread reply |
| GET | `/api/v1/articles/{id}/citations` | Citation graph |
| POST | `/api/v1/citations/click` | Record citation click |
| POST | `/api/v1/articles/{id}/merge-proposals` | Create merge proposal |
| GET | `/api/v1/search` | Full-text search |
| POST | `/api/v1/compile-preview` | Compile Markdown/Typst → HTML/SVG |
| GET | `/api/v1/users` | List users |
| GET | `/api/v1/users/{id}` | User profile + follow/rep |
| POST | `/api/v1/users/{id}/follow` | Follow user |
| DELETE | `/api/v1/users/{id}/follow` | Unfollow user |
| GET | `/api/v1/pool` | Sedimentation pool feed |
| GET | `/api/v1/feed` | Activity feed |

### 6.2 Key API Changes (P0 Refactor)

| Change | Old | New |
|--------|-----|-----|
| ArticleDetail response | includes `compiled_output`, `compiled_pages` | removed — use `/compile-preview` |
| Article authors | `authors: list[str]` in JSON | `ArticleAuthor` join table (API still returns `list[AuthorInfo]`) |
| Review thread | `thread: list[dict]` in JSON | `ReviewMessage` table (API still returns `list[ThreadMessageOut]`) |
| Citation edge | includes `forward_prob`, `backward_prob` | removed |
| MergeProposal | includes `thread` | removed (deferred) |

---

## 7. Testing

### 7.1 Test Counts

| Suite | Tests | Framework |
|-------|-------|-----------|
| Backend | 384 | pytest |
| Frontend | 492 | vitest |
| Rust | 79 | cargo test |

### 7.2 CI Pipeline

10 jobs across 3 languages: pytest, ruff, mypy, eslint, vitest, vue-tsc, vite verify, clippy, rustfmt, cargo test. All blocking on PR. Config: `.github/workflows/ci.yml`.

---

## 8. Deployment & Migration

### 8.1 Database Migration

When upgrading from the old schema (JSON fields), run:

```bash
python scripts/migrate_architecture.py --db sqlite:///peerpedia.db
```

The script is idempotent — safe to run multiple times. It:
1. Creates `article_authors` and `review_messages` tables
2. Migrates JSON data to join tables
3. Rebuilds `articles`, `reviews`, `merge_proposals`, `citations` tables without deprecated columns

### 5.4 Diff View with Word-Level Highlighting

The diff view (`DiffView.vue`) compares two git commits and renders changes with:
- **Line-level colors**: deletions in red (`text-danger`, `bg-danger/10`), additions in green (`text-success`, `bg-success/10`)
- **Word-level diff**: LCS-based token matching within paired del↔add lines. Changed words are wrapped in `<span class="diff-word-del">` (red background + line-through) or `<span class="diff-word-add">` (green background)
- **Git noise filtering**: `\ No newline at end of file` markers are stripped in both the Rust parser (`local_git.rs`) and the frontend component to prevent breaking del↔add pairing
- **Unpaired lines**: standalone deletions/additions get full-line `<span>` wrapper so they remain visible

### 8.2 Future: SQLite → PostgreSQL

SQLite is the Phase 1 database. Phase 2 will migrate to PostgreSQL. No business logic depends on SQLite-specific features.

---

### 8.3 Storage Model — Open Question

**Current design:** The server stores a complete Git repository per article at `~/.peerpedia/articles/{uuid}/`. Article IDs are UUIDs.

**Open question:** Should the server store only a repo ID (content hash) instead of the full repository? This would:
- Enable P2P transition — articles addressable by content hash, repo fetched on-demand from distributed storage.
- Reduce server storage — deduplication by content hash, server keeps only metadata + hash pointer.

**Tradeoff:** UUIDs are simpler for now. Content-hash addressing is the right primitive for Phase 2/3 but requires changes to the routing, resolution, and sync layers. Decision deferred.

## 9. Roadmap

The detailed engineering plan is maintained in [`docs/plan_reshape.md`](plan_reshape.md).

### Phase 1.5 — Polish & Ship (Complete)

| Priority | Feature | Status |
|----------|---------|--------|
| P0 | Delete articles | ✅ |
| P0 | Diff view (with word-level highlighting) | ✅ |
| P0 | Typst compilation (SVG preview) | ✅ |
| P0 | Typst compilation (PDF download) | ✅ |
| P0 | Draft search (FTS5) | ✅ |
| P0 | Editor UX (keep-alive, split pane, save states, per-save commit msg, VSCode-style tab system) | ✅ |
| P1 | CodeMirror 6 Markdown editor (syntax highlight, auto-indent, bracket matching) | ✅ |
| P0 | Distribute & user testing | ⬜ |
| P1 | arXiv mirror with scoring | ⬜ |
| P1 | Tags & categories | ⬜ |
| P2 | AI agent (exploratory) | ⬜ |

### Phase 3 — P2P Network (Future)

| Component | Description |
|-----------|-------------|
| Index Server | Maps content hash → peer addresses |
| Peer Client | Embedded in Tauri desktop, serves cached articles |
| Content Hash | SHA-256 of article source → `peerpedia://<hash>` |
| Sync Engine | Background pull/push of popular articles |

---

## 10. Configuration

All tunable parameters live in `core/peerpedia_core/config/params.py`:

- `sink.new_article_default_days` — default pool duration
- `sink.edit_article_default_days` — pool duration on edit
- `sink.max_days` — maximum pool extension
- `score.no_review_penalty()` — penalty for zero community reviews
- `score.score_to_sink_multiplier(avg)` — maps average score to sink duration

---

*Last updated: 2026-06-11 · 384 backend tests · 492 frontend tests · 79 Rust tests · 9 DB entities · L4 article sync (auto-backup + conflict resolution) · Draft-first creation*
