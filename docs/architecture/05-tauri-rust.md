# 05 — Tauri & Rust Layer

> Desktop shell: IPC bridge, local Git, local auth, local SQLite. Everything works offline.

## 1. Architecture

```
Vue 3 Frontend
  │  invoke('command_name', { args })
  ▼
Tauri IPC Bridge (commands.rs)
  │  Deserializes args, calls Rust functions
  ▼
┌─────────────────────────────────────────────┐
│  Rust Backend                                │
│                                              │
│  local_auth.rs     local_store.rs            │
│  (bcrypt + SQLite) (draft CRUD)              │
│       │                 │                    │
│       └────────┬────────┘                    │
│                ▼                             │
│         store.rs (SQLite connection pool)     │
│                                              │
│  local_git.rs                                │
│  (git2 library: init, commit, log, diff,    │
│   show, rollback)                            │
│       │                                      │
│       ▼                                      │
│  ~/.peerpedia/articles/{uuid}/ (bare repos)  │
└─────────────────────────────────────────────┘
```

## 2. IPC Commands

All frontend→Rust calls go through Tauri's `invoke()`:

| Command | Args | Returns | Description |
|---------|------|---------|-------------|
| `register` | username, password, name | User | Create local account |
| `login` | username, password | User + token | Authenticate locally |
| `save_draft` | id, title, content, format | { hash } | Save to SQLite + git commit |
| `get_draft` | id | Draft | Load draft from SQLite |
| `list_drafts` | account_id | Draft[] | All drafts for account |
| `delete_draft` | id | void | Remove from SQLite |
| `git_history` | article_id | Commit[] | Commit log |
| `git_show` | article_id, hash | string | File content at commit |
| `git_diff` | article_id, h1, h2 | DiffResult | Word-level diff |
| `compile_typst` | content | string (SVG) | Typst → SVG via sidecar |
| `compile_typst_pdf` | content | bytes (PDF) | Typst → PDF via sidecar |

## 3. local_auth.rs — Account Management

```
Schema (SQLite):
  CREATE TABLE accounts (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
  )
```

**Password hashing:** bcrypt with default cost (12 rounds). Passwords never leave the local machine (no network transmission in Tauri mode).

**Multi-account:** Multiple accounts can be created locally. Switching requires logout + login. No simultaneous multi-account sessions.

**Token:** After authentication, a random token is generated and stored in localStorage. This token is used to identify the current session, not for server auth.

## 4. local_store.rs — Draft Persistence

```
Schema (SQLite):
  CREATE TABLE drafts (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    title TEXT DEFAULT '',
    content TEXT DEFAULT '',
    format TEXT DEFAULT 'markdown',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
  )
```

**Save flow:** `save_draft()` → UPSERT draft → `local_git.commit()` → return commit hash.

**Why SQLite + Git:** SQLite stores the latest version for fast retrieval. Git stores the full version history. SQLite is the cache, Git is the source of truth.

## 5. local_git.rs — Git Operations

Uses the `git2` crate (libgit2 bindings). All operations on bare repos.

```
~/.peerpedia/
├── articles/
│   ├── {uuid1}/     # bare git repo
│   │   ├── HEAD
│   │   ├── refs/
│   │   └── objects/
│   ├── {uuid2}/
│   └── ...
├── cache/
│   └── {uuid}/{hash}.{html|svg}  # Compilation cache
└── peerpedia.db    # SQLite database
```

**Key operations:**

- `init(id)`: `git_repository_init(&path, false)` — bare repo
- `commit(content, title, message)`: Write blob → create tree → create commit → update ref
- `log(id)`: `revwalk` from HEAD → list of (hash, message, author, timestamp)
- `show(id, hash)`: Read blob at commit → return content as string
- `diff(id, h1, h2)`: `git_diff_tree_to_tree` → parse hunks → word-level token matching
- `rollback(id, hash)`: `git_reference_set_target` → move HEAD to hash

**Word-level diff:** The diff function does LCS-based token matching on paired delete↔add lines. Changed words within lines are marked as `diff-word-del` (red, line-through) and `diff-word-add` (green). Git noise (`\ No newline at end of file`) is filtered. This is used by the DiffView.vue component in conflict resolution.

## 6. Typst Compilation (Sidecar)

Tauri sidecar: a precompiled Typst CLI binary bundled with the app.

```
compile_typst(content: string) → SVG string
  1. Write content to temp file
  2. Spawn: typst compile temp.typ --format svg
  3. Read output SVG
  4. Return to frontend

compile_typst_pdf(content: string) → PDF bytes
  1. Write content to temp file
  2. Spawn: typst compile temp.typ --format pdf
  3. Read output PDF
  4. Return to frontend as base64
```

**Limitation:** Typst compilation is synchronous (blocks Tauri command thread). For large documents (>50 pages), this can freeze the UI for several seconds. No progress indication.

## 7. Tauri Configuration

```json
// tauri.conf.json
{
  "build": {
    "devUrl": "http://localhost:5173",
    "frontendDist": "../dist"
  },
  "app": {
    "security": {
      "csp": null  // No CSP — needs tightening before distribution
    }
  }
}
```

**CSP:** Currently null. This means the webview accepts any script/style source. Should be restricted before distribution to prevent XSS in case of user-generated content rendering.

## 8. Browser-Local Mock Mode

For development without Tauri: append `?tauri` to URL. `useTauri.ts` detects this and provides mock implementations:

```typescript
if (isBrowserLocal) {
  // Mock: save to localStorage instead of Tauri IPC
  // Mock: git operations return fake hashes
  // Mock: auth uses browser localStorage
}
```

This allows full frontend development without Rust compilation.

## 9. Design Issues

### I12: Typst compilation has no progress indicator

Typst subprocess calls are correctly wrapped in `tokio::task::spawn_blocking` (per `commands.rs` line 8-10), so they don't block the async runtime. However, the frontend receives no progress updates during compilation — the user sees a spinner with no indication of how long it will take.

### I13: No CSP

`csp: null` in Tauri config means no Content Security Policy. If user-generated content is ever rendered in the webview (e.g., article preview with embedded scripts), this is an XSS vector.

### I14: SQLite connection not pooled

`store.rs` creates a single SQLite connection. All Tauri commands share it. SQLite allows concurrent reads but serializes writes. If a write is in progress, reads block. For a single-user desktop app this is fine, but it could cause micro-stutters during auto-save.

### I15: Export exists but no automated backup

`local_git.rs:151` has `export_article()` which creates a tar.gz of an article's Git repo, exposed via IPC command. Manual export works. However, there's no automated/background backup — users must remember to export. Server-synced articles are recoverable; local-only drafts rely on manual export.
