# Code Self-Review: Architecture Audit Verification

> 2026-06-13 · Branch: fix/fork-500-identity-sync · Per architecture booklet issues

## Result Summary

| Category | Count |
|----------|-------|
| Confirmed real | 8 |
| Partially true (overstated) | 3 |
| Wrong/false | 0 |
| **New issues found (missed by audit)** | **2** |

## Issue-by-Issue

### Critical/High — Verified

| ID | Issue | Stated | Actual | Evidence |
|----|-------|--------|--------|----------|
| I8 | SQLite bottleneck | High | **Low** | `tokio::sync::Mutex` + WAL mode. Correct for single-user. Not a bottleneck. |
| I9 | No rate limiting | High | **Low** | Zero rate-limit code. But backend is localhost-only — no external exposure. |
| I13 | CSP null | High | **Medium** | `tauri.conf.json:25` — `"csp": null`. Real risk, but typical for Tauri. |
| T1 | Phone model bypass | High | **Low** | Guard is watertight. No bypass found. App.vue watcher is downstream, not a bypass. |
| T4 | Sync naming confusion | High | **High** | Confirmed. `isOnline` = `isSynced` alias. `syncState` in useArticleSync has its own `'synced'`. |

### Medium — Verified

| ID | Issue | Stated | Actual | Evidence |
|----|-------|--------|--------|----------|
| I1 | localStorage token | Medium | **Low** | Desktop-only, no XSS vector. Medium only for web deployment. |
| I3 | pendingCreds infinite retry | Medium | **Low** | NOT infinite. Retries once per `isSynced` transition. Bounded by user interaction. |
| I5 | EditorPage 789 lines | Medium | **Low** | Correct count. Could decompose but not a functional issue. |
| I16 | No Markdown PDF | Medium | **Medium** | Confirmed. DownloadButton: Markdown compiled → `.html` only. Typst → `.pdf`. |
| I17 | Typst no progress | Medium | **Low** | Confirmed. spawn_blocking returns final result only. No progress events. |
| I19 | Math regex | Medium | **Low** | Regex uses negative lookbehinds. Correct for modern browsers. Edge cases exist but rare. |

### Verified/Confirmed

| ID | Issue | Evidence |
|----|-------|----------|
| I10 | JWT fallback secret | `deps.py:13-19` — `os.environ.get("JWT_SECRET")` + `"peerpedia-dev-secret"` fallback + warning |
| I12 | Typst spawn_blocking | `commands.rs:531,544` — correctly uses `tokio::task::spawn_blocking` |
| I15 | export_article exists | `local_git.rs:151-191` — creates tar.gz, wired via IPC command |

## New Issues Found (Missed by Architecture Docs)

### N1 — `isOnline` naming causes concrete bug in useArticleSync

**File:** `frontend/src/composables/useArticleSync.ts:35,42`

```typescript
const { isOnline } = useNetworkStatus()  // actually isSynced alias
// ...
if (!isOnline.value) return 'offline'
```

`isOnline` is `isSynced` — it means "user tapped connect and ping succeeded." It does NOT mean "network is reachable now."

**Bug scenario:** User taps SyncButton → synced. Then server goes down. `isOnline` stays `true` (state is still 'synced' — nothing auto-disconnected). `useArticleSync` reports `'upload'` or `'synced'` instead of `'offline'`. The actual API call fails with an opaque error instead of showing the offline UI state.

**Fix:** `useArticleSync` should catch API failures and set state to `'offline'`, OR `notifyFailure()` should be called on API errors while synced (which it already does — S6 auto-disconnect). The gap is: if the server goes down silently (no API call in progress), there's no detection. This is inherent to the phone model — no background polling means no server-down detection between API calls.

### N2 — `client.ts` interceptor fragility

**File:** `frontend/src/api/client.ts:30`

```typescript
_getNS().notifySuccess()  // called on EVERY successful response
```

While the guard prevents `idle → synced` promotion, this pattern creates hidden coupling. If any code path ever calls `connect()` programmatically (no current path does, but future refactors might), the next axios response could race with `ping()` and silently promote to `synced` before the ping completes.

**Risk:** Low today (no programmatic connect() calls). Architectural fragility — the interceptor shouldn't call `notifySuccess()` at all if the user didn't initiate a connection check. Consider renaming or splitting: `notifyApiSuccess()` vs `notifyConnectSuccess()`.

## Final Verdict

**Code quality:** The implementation is solid. The guards are correct. No bypasses exist. The phone model is properly enforced.

**Architecture docs:** Mostly accurate. Severity ratings were inflated — many "High" issues are Low in the single-user desktop context. Two issues (I3 infinite retry, T1 bypass) were wrong about the mechanism but the underlying concern was valid.

**Action items from this review:**
1. ~~I10 JWT secret~~ — Not a problem (env var exists)
2. ~~T1 phone bypass~~ — No bypass exists
3. ~~I3 infinite retry~~ — Not infinite
4. **N1** — `useArticleSync` offline detection gap when server silently goes down. Inherent to phone model. Accept as design tradeoff or add periodic liveness check on synced state.
5. **N2** — Consider renaming `notifySuccess()` to clarify it's only for connect-attempt success.

NO UNRESOLVED DECISIONS
