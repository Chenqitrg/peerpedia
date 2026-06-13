# PeerPedia Architecture Booklet

> 2026-06-13 · 8 chapters · Honest technical documentation

## Chapters

| # | File | What's Covered |
|---|------|---------------|
| 00 | [overview](00-overview.md) | Project vision, file map, architecture diagram, key decisions, numbers |
| 01 | [network-sync](01-network-sync.md) | Connection state machine, SyncButton, axios interceptors, offline capability, article sync. **Two separate sync systems with confusing names.** |
| 02 | [stores-and-state](02-stores-and-state.md) | Pinia stores, composable singletons, auth flow, localStorage keys, dependency graph |
| 03 | [pages-and-routing](03-pages-and-routing.md) | Route map, page component patterns, tab system, editor save flow, what's missing |
| 04 | [backend-api](04-backend-api.md) | FastAPI structure, 9 entity models, auth flow, article operations, Git manager, all endpoints |
| 05 | [tauri-rust](05-tauri-rust.md) | IPC commands, local auth, local store, local git, Typst sidecar, browser-local mock |
| 06 | [compilation](06-compilation.md) | Markdown pipeline (protect→parse→restore→render), Typst sidecar, filesystem cache |
| 07 | [testing-and-quality](07-testing-and-quality.md) | Test architecture, coverage gaps, known technical debt, CI pipeline |

## Design Issues Index

Every chapter ends with an "Issues" section. Here's the full list:

| # | Issue | Chapter | Severity |
|---|-------|---------|----------|
| I1 | JWT in localStorage — XSS risk if user HTML rendering added | 02 | Medium |
| I2 | `restoreSession` race condition — flash of unauthenticated content | 02 | Low |
| I3 | `pendingCreds` infinite retry on permanent failure | 02 | Medium |
| I4 | `connectionState` lost on app restart — reset to idle | 02 | Low |
| I5 | EditorPage is ~700 lines — needs composable extraction | 03 | Medium |
| I6 | `useAsyncResource` re-fetches on every mount — no SWR | 03 | Low |
| I7 | Conflict resolution requires full page refresh — stale on failure | 03 | Low |
| I8 | SQLite — tokio::sync::Mutex + WAL, correct for single-user | 04 | Low |
| I9 | No rate limiting — localhost-only, no external exposure | 04 | Low |
| I10 | JWT fallback secret for dev — must set env var in production | 04 | Low |
| I11 | Git repos grow unbounded — no GC, no pruning | 04 | Low |
| I12 | Typst compilation has no progress indicator | 05 | Low |
| I13 | No CSP in Tauri config — real risk, typical for Tauri | 05 | Medium |
| I14 | SQLite connection not pooled — writes block reads | 05 | Low |
| I15 | Export exists (export_article) but no automated backup | 05 | Low |
| I16 | No Markdown→PDF on desktop — server-only path | 06 | Medium |
| I17 | Typst no progress indicator — spawn_blocking returns final only | 06 | Low |
| I18 | Compilation cache never expires — unbounded growth | 06 | Low |
| I19 | Math protection is regex-based — edge case dollar signs | 06 | Low |
| T1 | Phone model: guard verified watertight, no bypass exists | 01 | Low |
| T2 | `connecting` invisible to useOffline — no loading state | 01 | Medium |
| T3 | `isOnline` backward compat masks design intent | 01 | Medium |
| T4 | Two sync systems with confusing naming overlap | 01 | High |
| G1 | No SyncButton integration test with real state machine | 07 | Medium |
| G2 | No client.ts interceptor tests | 07 | Medium |
| G3 | No useArticleSync + useNetworkStatus integration test | 07 | Medium |
| N1 | `isOnline` naming → useArticleSync offline detection gap (server-down while synced) | 01 | Medium |
| N2 | client.ts interceptor calls notifySuccess() on every response — fragile coupling | 01 | Low |
| TD1-6 | Various technical debt items | 07 | — |

## How to Use This

**For ChatGPT/Claude review:** Paste chapters 00-07 in order. Ask: "Find contradictions, design flaws, and things that will break in production."

**For onboarding:** Read 00 first, then jump to whichever chapter covers your task.

**For design review:** Focus on chapters 01 (network) and 02 (state) — these have the most unresolved tensions.

**For security review:** Search "Issue" across all chapters. I10 (JWT secret) and I13 (CSP) are the highest priority.
