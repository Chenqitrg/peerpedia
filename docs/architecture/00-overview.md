# 00 — Architecture Overview

> 2026-06-13 · PeerPedia (知诸网) · Architecture Booklet

## 1. What PeerPedia Actually Is

PeerPedia is a **single-user offline-first Markdown/Typst editor** that happens to sync to a server. Think Obsidian + Git + arXiv, not GitHub.com.

Phase 1 (now): Tauri desktop app. One user, one machine, optional server. Write offline, sync when connected.
Phase 2 (planned): Web community — sedimentation pool, peer review, reputation.

The architecture follows one rule: **Git is source of truth. Database is an index.** Article content lives in `~/.peerpedia/articles/{uuid}/` as bare Git repos. The SQLite database stores metadata (title, status, scores) for fast queries. If the database burns down, rebuild it from Git.

## 2. Actual File Map

```
peerpedia/
├── frontend/                          # Vue 3 SPA + Tauri shell
│   ├── src/
│   │   ├── api/                       # Axios modules + types
│   │   │   ├── client.ts              # Axios instance, interceptors, token attach
│   │   │   ├── articles.ts            # CRUD + fork + publish
│   │   │   ├── auth.ts                # login, register, profile sync
│   │   │   ├── bookmarks.ts           # add/remove/list
│   │   │   ├── follow.ts              # follow/unfollow
│   │   │   ├── reviews.ts             # submit/update reviews
│   │   │   ├── search.ts              # local + network search
│   │   │   ├── compile.ts             # compile-preview API
│   │   │   ├── feed.ts                # activity feed
│   │   │   ├── pool.ts                # sedimentation pool
│   │   │   ├── schools.ts             # user listing
│   │   │   └── types.ts               # All TS interfaces
│   │   ├── assets/
│   │   │   └── main.css               # Tailwind + base styles
│   │   ├── components/                # 17 components (was 18, NetworkStatusBadge deleted)
│   │   │   ├── SyncButton.vue         # Three-state connection button (NEW)
│   │   │   ├── NavBar.vue             # Top nav: brand, search, SyncButton, actions, avatar
│   │   │   ├── AuthModal.vue          # Login/register modal
│   │   │   ├── TabDrawer.vue          # VSCode-style tab sidebar
│   │   │   ├── ArticleCard.vue        # Article list item with sync conflict icon
│   │   │   ├── DiffView.vue           # Word-level git diff overlay
│   │   │   ├── ReviewPanel.vue        # Five-dimension review form
│   │   │   ├── ScoreBadges.vue        # O/R/C/P/I score display
│   │   │   ├── RadarChart.vue         # Radar chart for scores
│   │   │   ├── FiveDimForm.vue        # Score input form
│   │   │   ├── StarRating.vue         # Star rating widget
│   │   │   ├── DownloadButton.vue     # Multi-format download (idle/loading/disabled)
│   │   │   ├── DeleteButton.vue       # Delete with confirmation (idle/confirm/deleting)
│   │   │   ├── CodeEditor.vue         # CodeMirror 6 wrapper
│   │   │   ├── ThreadReplyInput.vue   # Review thread reply
│   │   │   └── ArticleCardSkeleton.vue # Loading skeleton
│   │   ├── composables/              # Shared stateful logic (Vue composables)
│   │   │   ├── useNetworkStatus.ts    # Module-level singleton: connectionState machine
│   │   │   ├── useOffline.ts          # Feature capability matrix: canRead/canWrite
│   │   │   ├── useArticleSync.ts      # L4 sync: upload/synced/conflict/offline/loading
│   │   │   ├── useBookmarkToggle.ts   # Shared bookmark toggle + local cache
│   │   │   ├── useTauri.ts            # Tauri IPC bridge + browser-local mock
│   │   │   ├── useLocalStorage.ts     # JSON/save/load wrappers
│   │   │   ├── useDraftPersistence.ts # Draft save/load via Tauri or localStorage
│   │   │   ├── useFollowCache.ts      # Local follow state cache
│   │   │   └── useAsyncResource.ts    # Generic async data fetcher with loading states
│   │   ├── pages/                     # 10 page components
│   │   │   ├── HomePage.vue           # Activity feed (online) + local articles
│   │   │   ├── EditorPage.vue         # Markdown/Typst editor with split preview
│   │   │   ├── ArticlePage.vue        # Article view + diff conflict overlay
│   │   │   ├── SearchPage.vue         # Local + network search
│   │   │   ├── SchoolsPage.vue        # User discovery with follow
│   │   │   ├── UserPage.vue           # User profile + articles + drafts
│   │   │   ├── UserListPage.vue       # Follower/following list
│   │   │   ├── PoolPage.vue           # Sedimentation pool
│   │   │   ├── BookmarksPage.vue      # Bookmarked articles
│   │   │   └── HistoryPage.vue        # Article version history
│   │   ├── router/
│   │   │   └── index.ts              # Vue Router with auth guards + tab tracking
│   │   ├── stores/                    # Pinia stores
│   │   │   ├── useUserStore.ts        # Auth state, viewer, token, account sync
│   │   │   ├── useTabStore.ts         # VSCode-style tab management
│   │   │   └── useArticleStore.ts     # Article cache
│   │   ├── utils/
│   │   │   ├── markdown.ts            # KaTeX protect→parse→restore→render pipeline
│   │   │   └── time.ts               # Relative time formatting
│   │   ├── locales/
│   │   │   ├── en-US.json            # English translations
│   │   │   └── zh-CN.json            # Chinese translations
│   │   └── App.vue                    # Root: NavBar, TabDrawer, router-view, auth sync watcher
│   ├── index.html
│   ├── vite.config.ts
│   ├── vitest.config.ts              # jsdom environment, 52 test files
│   ├── tailwind.config.ts
│   └── src-tauri/                    # Rust backend
│       ├── src/
│       │   ├── main.rs               # Tauri entry, command registration
│       │   ├── local_auth.rs          # bcrypt + SQLite account management
│       │   ├── local_store.rs         # Draft/article CRUD via SQLite
│       │   ├── local_git.rs           # Git init, commit, log, diff, show
│       │   ├── commands.rs            # Tauri IPC command handlers
│       │   └── store.rs              # SQLite connection management
│       ├── Cargo.toml
│       └── tauri.conf.json
├── backend/                           # Python FastAPI server
│   ├── peerpedia_api/
│   │   ├── main.py                   # FastAPI app, CORS, routers
│   │   ├── routers/                  # REST endpoint handlers
│   │   │   ├── articles.py           # CRUD, fork, publish, history, diff
│   │   │   ├── auth.py               # Register, login, profile sync
│   │   │   ├── users.py              # List, profile, follow
│   │   │   ├── reviews.py            # Submit, list reviews
│   │   │   ├── search.py             # Full-text search
│   │   │   ├── feed.py               # Activity feed
│   │   │   ├── pool.py               # Sedimentation pool
│   │   │   ├── bookmarks.py          # Bookmark CRUD
│   │   │   ├── citations.py          # Citation graph + click tracking
│   │   │   ├── compile.py            # Compile Markdown/Typst on-demand
│   │   │   ├── merge.py              # Merge proposals
│   │   │   └── health.py             # Health check endpoint
│   │   ├── models.py                 # SQLAlchemy models (9 entities)
│   │   ├── schemas.py                # Pydantic request/response schemas
│   │   ├── database.py               # SQLAlchemy engine + session
│   │   ├── git_manager.py            # Server-side Git operations
│   │   ├── auth.py                   # JWT creation/verification
│   │   └── compile_backends/         # Markdown + Typst compilers
│   └── tests/                        # 540 pytest tests
├── core/                              # Python shared config library
│   └── peerpedia_core/config/params.py
├── docs/
│   ├── DESIGN.en.md                  # High-level design document
│   ├── DESIGN.md                     # Chinese version
│   ├── architecture/                 # THIS BOOKLET
│   └── api-contract.json             # OpenAPI 3.0 spec
└── seed.py                           # Database seeder
```

## 3. Critical Architecture Decisions

### 3.1 Module-Level Singletons

Several composables use module-level `ref()` variables — all callers share the same reactive state. This avoids prop drilling but creates hidden coupling:

| Composable | Singleton State | Consumers |
|------------|----------------|-----------|
| `useNetworkStatus` | `connectionState`, `flash`, `connectTimer` | 15+ files |
| `useUserStore` (Pinia) | `viewer`, `token`, `localToken` | 20+ files |
| `useTabStore` (Pinia) | `tabs[]`, `activeTabId` | 5 files |

**Risk:** Any component can mutate global state. Tests must call `_resetForTest()` to avoid leakage. The singleton pattern is convenient but makes testing harder and creates implicit dependencies.

### 3.2 The Two Sync Systems

There are **two completely separate sync mechanisms** with confusingly similar names:

| System | States | Controls | Composable |
|--------|--------|----------|------------|
| **Connection sync** | idle / connecting / synced | User taps SyncButton | `useNetworkStatus` |
| **Article sync** | upload / synced / conflict / offline / loading | Auto on save | `useArticleSync` |

Connection sync answers: "Can I reach the server?" Article sync answers: "Is this article's local version the same as the server's?"

**Design tension:** Connection sync exports `isOnline` (backward compat alias for `isSynced`). Article sync reads `isOnline` to determine `offline` state. If the user never taps SyncButton, `isOnline` is always `false`, so `useArticleSync` always returns `offline`. **Articles never auto-upload until the user discovers and taps the SyncButton.** This is intentional (phone model) but may surprise users.

### 3.3 Offline Capability Matrix

`useOffline.ts` defines a fixed capability matrix for every feature:

```
                    | canRead | canWrite
feed                | full    | full        (local-only)
feed.online         | blocked | blocked     (server required)
article.content     | full    | full        (local-only)
article.comments    | readonly| blocked     (read cache, write needs server)
article.fork        | blocked | blocked     (server required)
article.publish     | blocked | blocked     (server required)
pool                | blocked | blocked     (server required)
schools             | blocked | blocked     (server required)
search.local        | full    | full        (local FTS5)
search.network      | blocked | blocked     (server required)
user.self           | full    | full        (local accounts)
user.follow_graph   | readonly| blocked     (read cache, write needs server)
editor              | full    | full        (local saves)
editor.publish_pool | blocked | blocked     (server required)
compile             | full    | full        (client-side)
bookmarks           | full    | full        (local cache)
```

`canRead`/`canWrite` check three conditions in order:
1. `isLocalOnly() && NETWORK_ONLY_FEATURES.has(feature)` → false (hard block)
2. `connectionState.value === 'synced'` → true (server confirmed reachable)
3. Matrix lookup → returns capability

**Edge case:** When `connectionState` is `connecting` (transient), step 2 is false, step 3 runs. Network-only features remain blocked during the ~1-2 second connection attempt. This is correct but the user sees no loading indication on disabled buttons.

### 3.4 Data Flow: Article Save + Sync

```
User types → EditorPage (Vue) → Ctrl+S
  → handleSaveDraft()
    → Tauri: IPC → Rust local_store.save_draft() → SQLite
       → Rust local_git.commit() → git repo
    → Web: PUT /api/v1/articles/{id} → FastAPI
       → git_manager.commit() → DB insert
  → useArticleSync.pushUpdate() [if server_article_id exists]
    → PUT /api/v1/articles/{id} → compare commit hashes
      → match: synced
      → mismatch: conflict → show GitCompare icon
```

## 4. Key Numbers

| Metric | Value |
|--------|-------|
| Source files (.ts/.vue/.py/.rs) | ~170 |
| Frontend tests | 557 (vitest, 52 files) |
| Backend tests | 540 (pytest) |
| Rust tests | 16 (cargo test) |
| Database entities | 9 |
| Vue components | 17 |
| Pinia stores | 3 |
| Composables | 9 |
| Pages | 10 |
| API endpoints | ~30 |

## 5. Where This Document Set Goes

1. **01-network-sync.md** — The full network layer: state machines, axios interceptors, offline detection, article sync
2. **02-stores-and-state.md** — Pinia stores, composable patterns, module singletons, auth flow
3. **03-pages-and-routing.md** — Page component responsibilities, data loading, tab system, keep-alive
4. **04-backend-api.md** — FastAPI structure, endpoint details, database models, auth flow
5. **05-tauri-rust.md** — Rust IPC commands, local Git, local auth, local store
6. **06-compilation.md** — Markdown/Typst compilation pipeline, caching, on-demand compile
7. **07-testing-and-quality.md** — Test architecture, coverage gaps, known issues, technical debt
