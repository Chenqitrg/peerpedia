# 02 — Stores & State Management

> Pinia stores, composable patterns, module singletons, auth flow. How state moves through the app.

## 1. State Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                     App.vue (root)                       │
│  Owns: auth sync watcher, keepAliveVersion, close dialog │
│  Watches: isSynced → triggers trySyncServerAuth()       │
└──────────┬────────────────────────────┬─────────────────┘
           │                            │
    ┌──────▼──────┐              ┌──────▼──────┐
    │  Pinia Stores│              │ Composables  │
    │  (global)    │              │ (module-singleton refs) │
    └──────┬──────┘              └──────┬──────┘
           │                            │
    ┌──────▼────────────────────────────▼─────────────────┐
    │              Page Components                         │
    │  Each page: imports stores + composables,            │
    │  manages its own local refs for UI state             │
    └─────────────────────────────────────────────────────┘
```

## 2. Pinia Stores

### 2.1 useUserStore — Auth & Account Sync

**File:** `stores/useUserStore.ts` (~200 lines)

The most complex store. Manages authentication across Tauri (local) and server (JWT).

```
State:
  showAuthModal: boolean        // AuthModal visibility
  viewer: User | null           // Currently logged-in user
  token: string | null          // Server JWT token
  localToken: Ref<string | null> // Tauri local account token (not Pinia — raw ref)
  hasPendingCreds: boolean      // Tauri creds waiting for server sync
  syncError: string | null      // Error banner message
  isTauriMode: boolean          // Running in Tauri?
  isBrowserLocal: boolean       // Browser-local mock mode?

Key actions:
  restoreSession()              // On mount: restore from localStorage
  login(username, password)     // Tauri: local_auth. Web: apiLogin
  register(...)                 // Create account
  logout()                      // Clear state, remove tokens
  trySyncServerAuth()           // Push local Tauri creds to server
  syncProfileToServer()         // Best-effort profile sync
  refreshViewer()               // Re-fetch user from API

Computed:
  isLoggedIn                    // !!viewer
```

**Auth flows:**

```
Tauri mode:
  register() → local_auth IPC → SQLite (local) → save token to localStorage
  login()    → local_auth IPC → SQLite (local) → save token to localStorage
  trySyncServerAuth()
    → apiRegister() or apiLogin() with stored creds
    → save JWT to localStorage
    → syncProfileToServer()

Web mode:
  register() → POST /auth/register → JWT → localStorage
  login()    → POST /auth/login    → JWT → localStorage
```

**App.vue watcher:**
```typescript
watch([isSynced, () => userStore.localToken?.value, () => userStore.hasPendingCreds],
  ([online, localTok, pending]) => {
    if (online && (localTok || pending)) {
      userStore.trySyncServerAuth()
    }
  }
)
```

This means: when the user taps SyncButton and gets synced, any pending Tauri credentials are automatically pushed to the server. Before the sync button change, this fired on `isOnline` (auto-ping). Now it fires only when the user explicitly connects.

### 2.2 useTabStore — VSCode-Style Tabs

**File:** `stores/useTabStore.ts` (~150 lines)

Manages the tab bar (TabDrawer.vue) — each open article/editor gets a tab.

```
State:
  tabs: Tab[]                  // Array of open tabs
  activeTabId: string | null   // Currently active tab

Tab shape:
  { id: string,                // UUID
    title: string,             // "Untitled" or article title
    routePath: string,         // /edit?id=xxx or /article/xxx
    dirty: boolean,            // Unsaved changes?
    icon: 'edit' | 'article' }

Key actions:
  ensureTab(route, title, icon) // Create or find tab
  activateTabByRoute(fullPath)  // Set active on navigation
  closeTab(tabId)              // Close: clean→remove, dirty→prompt
  removeTab(tabId)             // Force remove
  findById(tabId)              // Lookup
  updateTabTitle(tabId, title) // After save, update "Untitled" → real title
```

**Keep-alive interaction:** App.vue uses `<keep-alive :include="['EditorPage', 'ArticlePage']">` with a `keepAliveVersion` ref. When all tabs are closed and a new tab-tracked route is navigated to, `keepAliveVersion` is bumped to clear stale cached component instances.

### 2.3 useArticleStore — Article Cache

**File:** `stores/useArticleStore.ts` (~60 lines)

Lightweight article cache, mainly used by ArticleCard and list pages.

```
State:
  cache: Map<string, ArticleSummary>

Actions:
  getArticle(id) → cache lookup or API fetch
  setArticle(article) → write to cache
```

## 3. Module-Level Singleton Composables

### 3.1 Pattern

Several composables use module-level `ref()` instead of Pinia stores. All importers share the same reactive state:

```typescript
// useNetworkStatus.ts — module scope (not inside function)
const connectionState: Ref<ConnectionState> = ref('idle')
const flash: Ref<boolean> = ref(false)
let connectTimer: ReturnType<typeof setTimeout> | null = null

export function useNetworkStatus() {
  _setupListeners()
  return { connectionState, flash, isSynced, isOnline, ... }
}
```

Every caller gets the same `connectionState` ref. Changing it in one component changes it everywhere.

### 3.2 Singleton Composables Table

| Composable | Singleton State | Why Singleton? |
|------------|----------------|----------------|
| `useNetworkStatus` | `connectionState`, `flash` | Global connection state — one truth |
| `useTauri` | Detects Tauri once | `window.__TAURI__` doesn't change |
| `useUserStore` (Pinia) | `viewer`, `token` | One logged-in user |

### 3.3 Risks of Singleton Pattern

**Test leakage:** `_resetForTest()` must be called in `beforeEach` to prevent test A's state from leaking into test B. If a test forgets, state corruption is silent — tests pass but for the wrong reason.

**Implicit coupling:** Any component can mutate `connectionState`. If a page calls `disconnect()` directly (none do currently), it affects the SyncButton in NavBar. This is by design but makes debugging harder.

**SSR incompatibility:** Module-level state survives across requests in SSR. Not relevant now (Tauri desktop), but would break if moving to SSR.

## 4. Composable Dependency Graph

```
useNetworkStatus (module singleton)
  ├── useOffline (reads connectionState)
  │     ├── NavBar (canRead/canWrite)
  │     ├── EditorPage (canWrite)
  │     ├── HomePage (canRead)
  │     ├── ArticlePage (canRead/write)
  │     ├── SchoolsPage (canRead/write)
  │     └── UserPage (canRead/write)
  ├── useArticleSync (reads isOnline)
  │     ├── EditorPage (pushUpdate, upload)
  │     └── ArticlePage (syncState, useRemote, keepLocal)
  ├── useBookmarkToggle (reads connectionState)
  │     ├── HomePage
  │     ├── PoolPage
  │     ├── UserPage
  │     ├── SearchPage
  │     └── BookmarksPage
  ├── client.ts (calls notifySuccess/notifyFailure)
  │     └── all API modules (articles, auth, bookmarks, ...)
  └── App.vue (reads isSynced, calls ping)
```

**Key:** `useNetworkStatus` is imported by 15+ files. Changing its API requires updating mocks in ~13 test files.

## 5. Auth State Flow (Detailed)

```
App mount
  → userStore.restoreSession()
    → localStorage('viewer')     → viewer
    → localStorage('token')      → server JWT
    → localStorage('localToken') → Tauri local token
    → Set isTauriMode / isBrowserLocal

  → tabStore.restoreTabs()
    → localStorage('tabs') → tabs[]

  → ping() (in onMounted)
    → fetch /health → notifySuccess/Failure

Watch: [isSynced, localToken, hasPendingCreds]
  → if synced + (localToken || pendingCreds)
    → trySyncServerAuth()
      → apiLogin(stored username, password)
        → success: save JWT, clear pendingCreds
        → 404: apiRegister(stored username, password)
          → success: save JWT
          → 409: clear pendingCreds (conflict — already exists)
          → 422: save pendingCreds for retry
        → failure: set syncError
```

## 6. localStorage Keys (Complete)

| Key | Value | Set By |
|-----|-------|--------|
| `token` | Server JWT string | useUserStore |
| `localToken` | Tauri local token | useUserStore |
| `viewer` | JSON: User object | useUserStore |
| `tabs` | JSON: Tab[] | useTabStore |
| `locale` | 'en-US' or 'zh-CN' | NavBar toggle |
| `showAuthModal` | 'true' | Router guard |
| `bookmarks-{viewerId}` | JSON: ArticleSummary[] | useBookmarkToggle |
| `follow_cache-{viewerId}` | JSON: following IDs | useFollowCache |

**No encryption.** JWT and local tokens are stored in plain text in localStorage. This is acceptable for a local desktop app (file system permissions provide security), but would need hardening for a shared-machine scenario.

## 7. Design Issues

### I1: Token storage — plain text

JWT tokens in localStorage are vulnerable to XSS. Tauri's webview is isolated (no browser extensions), so risk is low. But if the app ever adds user-generated HTML rendering (article preview), this becomes a real attack vector.

### I2: `restoreSession` is async but not awaited in all paths

If `restoreSession()` hasn't resolved when a page component reads `userStore.viewer`, the component may render as logged-out briefly, then flash to logged-in. This causes a "flash of unauthenticated content."

### I3: `pendingCreds` — fragile retry

When server sync fails with 422, credentials are saved to localStorage as `pendingCreds`. On next `isSynced` change, they're retried. But if the server is permanently rejecting these creds (e.g., username taken by another user), they'll be retried forever with no user-facing error beyond the sync banner.

### I4: No state persistence for connectionState

`connectionState` is in-memory only (module ref). If the user closes and reopens the app, it resets to `idle`. The user must tap SyncButton again. This is intentional (phone model — you "hang up" when you close the app) but adds a startup step every time.
