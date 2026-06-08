# Phase 2 Reshape · 第二阶段重塑

> **Goal:** Polish local mode into a shippable desktop app. Learn the system deeply. Prepare for online.

---

## P0 — Polish Single-User Mode · 打磨单机模式

### 1. Delete Articles · 删除文章 (P0)

| Layer | Implementation |
|-------|---------------|
| **Rust** | `delete_article(conn, id, account_id)` — removes git repo + DB row. New Tauri command `delete_draft` already exists; extend to also clean `~/.peerpedia/articles/{id}/` directory. |
| **Frontend** | Delete button on UserPage article cards + ArticlePage. Confirmation dialog. Optimistic removal from list. |
| **Testing** | Rust: `test_delete_article_removes_git_repo`. Vitest: click delete → confirm → article disappears. |

### 2. Diff View · 差异对比 (P0)

| Layer | Implementation |
|-------|---------------|
| **Rust** | `get_diff_between` already exists in `git_backend.py`. For Tauri mode: side-by-side diff via `git diff` CLI output parsed into structured format (hunks, lines, added/removed). |
| **Frontend** | New `DiffView.vue` component with split-pane layout. Highlighted insertions (green) / deletions (red). Line numbers. Scroll sync between panes. |
| **Testing** | Rust: verify diff parsing. Vitest: component renders correct hunks. |

### 3. Typst Compile · Typst 编译 (P0)

| Layer | Implementation |
|-------|---------------|
| **Rust** | Use `std::process::Command` to spawn `typst` CLI — already partially implemented. Add: compilation error capture, progress callback via Tauri events, cached output invalidation on source change. |
| **Frontend** | Compile button shows progress spinner. Error messages rendered inline below editor. On success, auto-open preview pane with rendered SVG/HTML. |
| **Testing** | Rust: mock typst CLI output. Vitest: compile button → spinner → result. |

### 4. Editor Experience · 编辑器体验 (P0)

| Requirement | Approach |
|-------------|----------|
| **Ctrl+S → compile** | Add keyboard shortcut listener. `Ctrl+S` (Cmd+S on Mac) triggers `handleCompile()`. Show "Compiled ✓" toast. |
| **Syntax highlighting** | Integrate CodeMirror 6 (lightweight, extensible) or Monaco (VS Code engine). Markdown mode + Typst mode. Line numbers, bracket matching. |
| **Auto-complete & indentation** | CodeMirror plugins: `@codemirror/autocomplete` for Markdown references (`[title](`), Typst functions. `@codemirror/indent` for smart indent. |
| **Auto-save** | Debounced save (2s after last keystroke) via `useDraftPersistence`. Indicator shows "Saving…" / "Saved" / "Unsaved changes". |

### 5. Distribute & Get Feedback · 分发与评测 (P0)

| Task | Details |
|------|---------|
| **Build for distribution** | `cargo tauri build` — produces `.dmg` (macOS), `.deb`/`.AppImage` (Linux), `.msi` (Windows). Sign with Apple Developer ID for macOS. |
| **CI/CD** | GitHub Actions: trigger build on tag push (`v*`). Upload artifacts to release. |
| **Onboarding** | First-launch tutorial overlay. Sample articles pre-loaded. Clear "What is PeerPedia?" tooltip. |
| **Feedback channel** | GitHub Issues template for bug reports + feature requests. In-app "Send feedback" link. |

### 6. Draft Search · 草稿搜索 (P0)

| Layer | Implementation |
|-------|---------------|
| **Rust** | SQLite FTS5 full-text search on `drafts` table: `CREATE VIRTUAL TABLE drafts_fts USING fts5(title, content, tokenize='porter')`. Trigger-based sync with `drafts` table. |
| **Frontend** | Search bar in UserPage header. Typeahead dropdown showing matching drafts. Results grouped by title match vs content match. |
| **Testing** | Rust: insert draft → FTS query returns it. Vitest: type in search → results appear. |

### 7. arXiv Mirror · arXiv 镜像 (P1)

| Layer | Implementation |
|-------|---------------|
| **Backend (Python)** | arXiv API OAI-PMH harvester: `arxiv.py` fetches metadata + abstract daily. Stores in `articles` table with `source='arxiv'` flag. |
| **Frontend** | "Browse arXiv" page — newest papers, search by categories (astro-ph, quant-ph, cs.AI…). Each card: title, authors, abstract, link to PDF. Community scoring (Phase 2 feature, show placeholder). |
| **Offline** | Cache last N papers locally. "Download for offline reading" button on each card. |

### 8. Tags / Categories · 分类标签 (P1)

| Layer | Implementation |
|-------|---------------|
| **Schema** | New `tags` table: `(id, name, color)`. Join table `article_tags: (article_id, tag_id)`. Same pattern as `article_authors`. |
| **Frontend** | Tag editor in ArticlePage sidebar. Multi-select autocomplete. Color-coded badges. Filter by tag on UserPage. |

### 9. AI Agent (Exploratory · 探索中)

| Aspect | Consideration |
|--------|--------------|
| **Use case** | "Summarize this draft", "Suggest improvements", "Find related papers from arXiv mirror". |
| **Architecture** | Plugin-based: AI provider interface (OpenAI-compatible API). Local-first: `llama.cpp` via sidecar binary for offline use. |
| **Risk** | Dependency bloat, API costs, privacy concerns. Decision deferred to Phase 2 mid-point review. |

---

## P1 — Understand the System · 理解系统

Before scaling to multi-user, document the complete architecture:

| Module | Input | Output | Boundaries |
|--------|-------|--------|------------|
| **`peerpedia_core`** | Markdown/Typst source | Compiled HTML/SVG/PDF | Clean abstraction: source format → compiled output |
| **`peerpedia_api`** | HTTP request | JSON response | REST contract: `/api/v1/...` |
| **`storage/git_backend`** | Article content + metadata | Git commit | Source of truth: Git repo is canonical |
| **`storage/db`** | CRUD operations | SQL rows | Index only: rebuildable from Git |
| **`workflow/scoring`** | Review scores | Article score + reputation | Pure function: input scores → output reputation |
| **Tauri IPC** | Frontend command | Rust Result | Serialization boundary: serde + AppError |
| **`local_store`** | Draft/cache operations | SQLite rows | Local only: not synced to server |

### Key Interfaces to Formalize

- `GitBackend` trait (Rust) / protocol (Python) — abstracts git operations for testing
- `Storage` trait — local SQLite vs server API
- `Compiler` trait — Markdown vs Typst, local vs server
- `AuthProvider` trait — JWT (web) vs session token (desktop)

---

## P2 — Prepare for Online · 为线上做准备

| Task | Details | Cost |
|------|---------|------|
| **Rent server** | Hetzner CX22 (€4/mo) or DigitalOcean droplet ($6/mo). Single VPS for Phase 2. | ~$10/mo |
| **Domain** | `peerpedia.org` or `peerpedia.dev`. ~$12/yr. Configure Cloudflare DNS + HTTPS. | ~$12/yr |
| **Write deployment plan** | Docker Compose: FastAPI + SQLite + Caddy reverse proxy. `docker-compose.yml` in repo root. `Dockerfile` for backend. GitHub Actions → Docker Hub → VPS pull. | 1-2 days |
| **Write scaling plan** | When >100 users: PostgreSQL migration. Redis cache for compiled output. CDN for static assets. | Deferred to Phase 3 |
| **Multi-user auth** | Web: JWT (existing). Desktop → Web sync: OAuth device flow + encrypted sync channel. | Deferred to Phase 3 |

---

# Phase 3 Reshape · 第三阶段重塑

> **Vision:** Server stores only index. Content is P2P.

### Content Distribution

```
┌──────────┐    ┌──────────┐    ┌──────────┐
│ Author A │    │ Reader B │    │ Reader C │    ← Each has full article repo
│ (has art)│    │ (cached) │    │ (wants)  │
└────┬─────┘    └────┬─────┘    └────┬─────┘
     │              │               │
     └──────────────┴───────────────┘
              ↑
         Index Server
    (only has {hash → owner})

Flow: Reader C requests article → Index Server says "ask A or B" →
      Reader C requests from nearest peer → peer responds with content
```

### Key Components

| Component | Role |
|-----------|------|
| **Index Server** | Maps content hash → list of peer addresses. Lightweight — stateless, cacheable. |
| **Peer Client** | Embedded in Tauri desktop. Registers with Index Server on startup. Serves cached articles via HTTP or WebRTC. |
| **Content Hash** | SHA-256 of article source + metadata. Addressable: `peerpedia://<hash>` |
| **Sync** | Background sync: pull popular articles from peers automatically. Push own articles to Index Server on publish. |

### Migration Path

1. Phase 2 stores content in Git repos on a central server (current model).
2. Phase 3 adds P2P layer: content-addressed storage + Index Server.
3. Central server becomes just another peer — no single point of failure.
4. Users can self-host their own Index Server if desired.

---

*Last updated: 2026-06-08 · See README.md and docs/DESIGN.en.md for current architecture.*
