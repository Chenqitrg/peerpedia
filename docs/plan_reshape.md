# Phase 1.5 → Phase 2 Reshape · 打磨 → 上线重塑

> **Phase 1.5:** Polish desktop mode. **Phase 2:** Go online with community scoring.

---

## Phase 1.5 — Remaining P0 / P1 · 剩余待做项

### Forward / Share Paper · 转发论文 (P0)

Share any article via a portable file or link.

| Layer | Implementation |
|-------|---------------|
| **Rust** | `export_article(conn, id)` — bundles article source + metadata + git history into a `.peerpedia` package. New Tauri commands: `export_article(id) → path`, `import_article(path) → article_id`. |
| **Frontend** | "Share" button on ArticlePage + UserPage. Options: Export file (`.peerpedia`), Copy deep link (`peerpedia://<hash>`), OS share sheet. |
| **Format** | `.peerpedia` = SQLite DB containing `meta` table, `content` table, optional `git` blob. Typically <1 MB. |
| **Testing** | Rust: export → import → verify article restored. |

### Editor Experience · 编辑器体验 (P0)

| Requirement | Approach |
|-------------|----------|
| **Ctrl+S → compile** | Add keyboard shortcut. `Ctrl+S` (Cmd+S on Mac) triggers `handleCompile()`. Show "Compiled ✓" toast. |
| **Syntax highlighting** | Integrate CodeMirror 6. Markdown mode + Typst mode. Line numbers, bracket matching. |
| **Auto-complete & indentation** | CodeMirror plugins for Markdown references, Typst functions, smart indent. |
| **Auto-save** | Debounced save (2s after last keystroke) via `useDraftPersistence`. "Saving…" / "Saved" indicator. |

### Distribute & Get Feedback · 分发与评测 (P0)

| Task | Details |
|------|---------|
| **Build for distribution** | `cargo tauri build` → `.dmg` (macOS), `.deb`/`.AppImage` (Linux), `.msi` (Windows). |
| **CI/CD** | GitHub Actions: build on tag push (`v*`), upload artifacts. |
| **Onboarding** | First-launch tutorial, sample articles, "What is PeerPedia?" tooltip. |
| **Feedback channel** | GitHub Issues template + in-app "Send feedback" link. |

### arXiv Mirror · arXiv 镜像 (P1)

| Layer | Implementation |
|-------|---------------|
| **Backend** | arXiv API OAI-PMH harvester → `articles` table with `source='arxiv'` flag. |
| **Frontend** | "Browse arXiv" page with category search. Offline cache of last N papers. |

### Tags / Categories · 分类标签 (P1)

| Layer | Implementation |
|-------|---------------|
| **Schema** | `tags(id, name, color)` + `article_tags(article_id, tag_id)` join table. |
| **Frontend** | Tag editor in ArticlePage, color badges, filter by tag on UserPage. |

### AI Agent (Exploratory · 探索中)

- Use cases: "Summarize this draft", "Suggest improvements", "Find related papers"
- Architecture: Plugin-based AI provider interface. Local-first: `llama.cpp` sidecar.
- Risk: Dependency bloat, API costs, privacy. Decision deferred.

### ✅ Phase 1.5 Completed

| Feature | Commit |
|---------|--------|
| Delete articles | `4cce509` |
| Diff view (side-by-side) | `6164305` |
| Draft search (FTS5) | `6164305` |
| Typst SVG preview (▶ button) | `0d226ca` |
| Editor UX (keep-alive, split pane — partial) | `9640323` |
| Mutex deadlock fix | `49fabeb` |

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

*Last updated: 2026-06-09 · Completed P0 items moved to git history. See README.md for current status.*
