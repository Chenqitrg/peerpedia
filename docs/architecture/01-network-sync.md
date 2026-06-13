# 01 — Network & Sync Layer

> The most complex subsystem. Two separate state machines, one button, one interceptor. Read this before touching any network-related code.

## 1. Architecture Diagram

```
                        ┌──────────────────────────┐
                        │     SyncButton.vue         │
                        │  (V1 corner-dot, 32×32)   │
                        │  States: idle/connecting/  │
                        │  synced/flash              │
                        └──────────┬───────────────┘
                                   │ connect() / disconnect()
                                   ▼
┌──────────────────────────────────────────────────────┐
│              useNetworkStatus.ts                      │
│  Module-level singleton. All callers share state.    │
│                                                      │
│  connectionState: Ref<'idle'|'connecting'|'synced'>  │
│  flash: Ref<boolean>          (500ms red on timeout) │
│  isSynced: ComputedRef<boolean>                      │
│  isOnline: ComputedRef<boolean> (backward compat)    │
│                                                      │
│  connect()    → connecting, ping(), arm 10s timer    │
│  disconnect() → idle, clear timer                    │
│  ping()       → fetch /health → notifySuccess/Fail   │
│  notifySuccess() → only promotes from 'connecting'   │
│  notifyFailure() → idle+flash from 'connecting',     │
│                    idle (no flash) from 'synced',    │
│                    no-op from 'idle'                 │
└──────┬───────────────────────┬──────────────────────┘
       │                       │
       ▼                       ▼
┌──────────────┐    ┌──────────────────────────┐
│  client.ts    │    │  useOffline.ts             │
│  Axios inter- │    │  canRead(feature) → bool   │
│  ceptors:     │    │  canWrite(feature) → bool  │
│  - request:   │    │  isLocalOnly() → bool      │
│    attach     │    │  getFallback(feature)→ str │
│    Bearer     │    │                            │
│  - response:  │    │  Reads connectionState     │
│    notifySucc │    │  directly. Synced → full   │
│    ess() on   │    │  access. Not synced →      │
│    every OK   │    │  matrix lookup.            │
│  - error:     │    └──────────────────────────┘
│    notifyFail │
│    ure() on   │    ┌──────────────────────────┐
│    ERR_NETWORK│    │  useArticleSync.ts         │
└──────────────┘    │  5-state machine:          │
                    │  upload/synced/conflict/   │
                    │  offline/loading           │
                    │                            │
                    │  Reads isOnline from       │
                    │  useNetworkStatus. If      │
                    │  !isOnline → 'offline'.    │
                    │  Auto-uploads on save.     │
                    └──────────────────────────┘
```

## 2. Connection State Machine — Full Specification

### 2.1 States

| State | `connectionState` | `isSynced` | `isOnline` | Visual (SyncButton) |
|-------|-------------------|------------|------------|---------------------|
| Idle | `'idle'` | false | false | Gray WifiOff, gray corner dot |
| Connecting | `'connecting'` | false | false | White Wifi pulsing, white corner dot pulsing |
| Synced | `'synced'` | true | true | Blue Wifi glow (#79c0ff), blue corner dot |
| Flash | `'idle'` + `flash=true` | false | false | Red WifiOff, red corner dot (500ms then → idle) |

### 2.2 Transitions (Complete)

```
                    ┌─── connect() ───┐
                    │   (user tap)    │
                    ▼                 │
  idle ──────────────────► connecting │
   ▲                       │    │     │
   │                       │    │     │
   │    ┌──────────────────┘    │     │
   │    │ ping() OK             │     │
   │    │ → notifySuccess()     │     │
   │    │ (only if connecting)  │     │
   │    ▼                       │     │
   │  synced ◄──────────────────┘     │
   │    │                             │
   │    │ disconnect() (user tap)     │
   │    │ OR notifyFailure()          │
   │    │   (ERR_NETWORK, S6)         │
   │    ▼                             │
   └── idle                            │
        ▲                             │
        │ ping() fails or 10s timeout │
        │ → notifyFailure()           │
        │ → flash=true (500ms)        │
        └─────────────────────────────┘

navigator.onLine → false: disconnect() called synchronously
```

### 2.3 Guards (Critical — do not remove)

```typescript
// notifySuccess — only promotes from 'connecting'
// Prevents: (a) stale ping promises after disconnect
//           (b) axios interceptor auto-connecting without user tap
function notifySuccess() {
  if (connectionState.value !== 'connecting') return  // ← THE GUARD
  connectionState.value = 'synced'
  if (connectTimer !== null) { clearTimeout(connectTimer); connectTimer = null }
}

// notifyFailure — acts from 'connecting' (flash) or 'synced' (auto-disconnect)
// No-op from 'idle' (nothing to disconnect)
function notifyFailure() {
  if (connectionState.value === 'idle') return          // ← THE GUARD
  const wasConnecting = connectionState.value === 'connecting'
  connectionState.value = 'idle'
  if (connectTimer !== null) { clearTimeout(connectTimer); connectTimer = null }
  if (wasConnecting) {
    flash.value = true
    if (flashTimer !== null) clearTimeout(flashTimer)
    flashTimer = setTimeout(() => { flash.value = false }, 500)
  }
}
```

**Why the guards matter:**

| Scenario | Without Guard | With Guard |
|----------|--------------|------------|
| User taps connect, server fast, user cancels before response | Stale ping sets state to synced after user disconnected | notifySuccess sees state=idle, returns. Button stays idle. ✓ |
| HomePage loads articles (API call succeeds) | notifySuccess() from axios interceptor sets synced. User never tapped. | notifySuccess sees state=idle, returns. Only user tap can promote. ✓ |
| User synced, network drops, API fails with ERR_NETWORK | notifyFailure() sets idle + flash. Confusing flash when user didn't initiate. | notifyFailure sees wasConnecting=false, sets idle without flash. Clean. ✓ |
| User idle, API fails with ERR_NETWORK | notifyFailure() sets idle (already idle). No-op but wastes CPU. | notifyFailure sees state=idle, returns immediately. ✓ |
| User taps connect while navigator.onLine=false | ping() synchronously sets idle. Timer still armed. 10s later fires. | Guard in connect() checks state after ping(). Timer NOT armed. ✓ |

### 2.4 Edge Cases

**EC1: Double-tap connect.** `connect()` checks `if (connectionState.value === 'connecting') return`. Second tap is a no-op. User must cancel first.

**EC2: Tap connect while navigator.onLine=false.** `ping()` synchronously detects `!navigator.onLine`, sets state to idle, returns. Timer is NOT armed (guarded). User sees a flash of white then immediate gray. This is confusing — the button "connects" then immediately disconnects. **Known UX issue: no visual distinction between "offline" and "idle".**

**EC3: Server responds after timeout.** 10s timer fires → notifyFailure() → idle + flash. But the ping() promise is still pending. When it resolves, notifySuccess() sees state=idle → returns (guard). The successful response is silently discarded.

**EC4: Browser tab goes offline.** `window.addEventListener('offline', disconnect)` fires. State → idle. No flash (not from connecting). The user sees the button revert to gray without explanation. **Known UX issue.**

**EC5: Axios cancel (from old cooldown).** `client.ts` line 35 checks `axios.isCancel(error)` and returns early — does NOT call notifyFailure(). Canceled requests don't affect state. Good.

## 3. Axios Interceptor Flow (client.ts)

```
Request interceptor:
  1. Attach Bearer token from localStorage('token')
  2. (Old: shouldTry() cooldown guard — REMOVED)
  3. Send request

Response interceptor (success):
  1. notifySuccess() — called on EVERY successful response
  2. With guard: no-op if state != 'connecting'
  3. This means: API calls don't auto-connect the user
     → User must explicitly tap SyncButton
     → But: if user IS connecting, API success counts as proof

Response interceptor (error):
  1. axios.isCancel() → skip (suppressed request, not real error)
  2. ERR_NETWORK / Network Error → notifyFailure() + userMessage
  3. HTTP errors → extract detail from response body
  4. 422 → parse Pydantic validation errors into user-friendly string
```

## 4. Offline Capability System (useOffline.ts)

### How it decides

```typescript
function isLocalOnly(): boolean {
  // True only when: Tauri mode AND not synced to server
  return ('__TAURI__' in window || URLSearchParams.has('tauri'))
    && connectionState.value !== 'synced'
}

function canRead(feature: string): boolean {
  if (isLocalOnly() && NETWORK_ONLY_FEATURES.has(feature)) return false  // hard block
  if (connectionState.value === 'synced') return true                    // full access
  return offlineMatrix[feature]?.read !== 'blocked'                     // matrix lookup
}
```

### Nuance: 'connecting' state behavior

When `connectionState === 'connecting'`:
- `isLocalOnly()` returns the Tauri check result (step 2: `connectionState.value !== 'synced'` is true)
- `canRead/canWrite` skip step 2 (`synced` is false) and fall through to matrix
- Network-only features remain blocked during the ~1-2s connection attempt
- **No visual loading state** on disabled buttons during this window

### Where it's used

Every page component calls `useOffline()` to gate server-dependent UI:
- NavBar: `canRead('schools')`, `canRead('pool')` — shows gray disabled icons
- EditorPage: `canWrite('editor.publish_pool')` — disables publish button
- HomePage: `canRead('feed.online')` — decides feed source
- ArticlePage: follow button disabled when offline

## 5. Article Sync (useArticleSync.ts — L4)

### State Machine (separate from connection sync)

```
                    ┌── !isOnline ──► offline
                    │
  compute() ────────┼── no server_article_id ──► upload
  (runs on every   │
   reactive change) ├── server_hash == local ──► synced
                    │
                    └── server_hash != local ──► conflict
```

### How it connects to connection sync

```typescript
const { isOnline } = useNetworkStatus()  // backward compat: isSynced alias

function compute(): SyncState {
  if (!articleId) return 'offline'
  if (!isOnline.value) return 'offline'   // ← depends on user tapping SyncButton
  if (!serverArticleId) return 'upload'
  if (serverHash === localHead) return 'synced'
  return 'conflict'
}
```

**Critical dependency:** If the user never taps SyncButton, `isOnline` is always false, `compute()` always returns `'offline'`. Articles never auto-upload. **This is by design but may surprise users who expect auto-backup.**

### Push flow

```typescript
async function pushUpdate(): Promise<void> {
  // Called after every save in EditorPage (if server_article_id exists)
  const payload = { content, title, commit_message, commit_hash: localHead }
  const resp = await apiClient.put(`/articles/${serverArticleId}`, payload)
  // Server responds with new server_commit_hash
  // If hashes match → synced. If not → conflict.
}
```

## 6. Design Tensions & Open Questions

### T1: Phone model vs. auto-detect

**Current:** User must tap SyncButton. API calls don't auto-connect. `notifySuccess()` guarded.

**Argument for phone model:** No background polling. User controls when connection is checked. Clean mental model. Works offline for long periods without network noise.

**Argument against:** Button lies — page components load data from server (successfully) while button shows "not connected." User must discover and learn to tap SyncButton. `useArticleSync` depends on `isOnline` — articles never sync until user taps.

**Unresolved:** Should the first successful API call auto-promote from idle to synced? The axios interceptor already calls `notifySuccess()` — the guard is the only thing blocking it. Removing the idle guard would make the button honest while preserving explicit Connect/Disconnect control.

### T2: `connecting` is invisible to useOffline

During the ~1-2s `connecting` state, server-dependent buttons are disabled with no "checking..." indicator. The user sees gray icons and may click Connect, see the button pulse white, but the disabled buttons don't change until synced.

### T3: `isOnline` backward compat masks design

9 files destructure `isOnline` from `useNetworkStatus()`. They get `isSynced` (alias). This works but `isOnline` is a misleading name — it means "user confirmed server reachable by tapping a button," not "browser reports online." The naming hides the design intent.

### T4: Two sync systems, confusing names

| Term | System | Meaning |
|------|--------|---------|
| `synced` | Connection | Server reachable |
| `synced` | Article | Server hash matches local |
| `isSynced` | Connection | `connectionState === 'synced'` |
| `syncState` | Article | `'upload' \| 'synced' \| 'conflict' \| 'offline' \| 'loading'` |

A developer seeing `syncState === 'synced'` and `isSynced.value === true` must understand they're from completely different systems with different semantics.

## 7. File Reference

| File | Lines | Role |
|------|-------|------|
| `useNetworkStatus.ts` | 77 | Connection state machine, module singleton |
| `SyncButton.vue` | 128 | V1 corner-dot icon button, 32×32 |
| `client.ts` | 63 | Axios instance, interceptors |
| `useOffline.ts` | 76 | Feature capability matrix |
| `useArticleSync.ts` | ~120 | Article sync state machine |
| `useBookmarkToggle.ts` | 130 | Bookmark toggle with sync dependency |
| `NavBar.vue` | 443 | Top nav, hosts SyncButton |
| `App.vue` | 168 | Root, auth sync watcher |
