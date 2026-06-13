# 03 — Pages & Routing

> Page component responsibilities, data loading patterns, tab system, keep-alive.

## 1. Route Map

```
/                    → HomePage       (feed + local articles)
/edit                → EditorPage     (Markdown/Typst editor)
/article/:id         → ArticlePage    (article view + diff)
/articles/:id        → redirect → /article/:id
/search              → SearchPage     (local + network search)
/schools             → SchoolsPage    (user discovery + follow)
/user/:id            → UserPage       (profile + articles + drafts)
/user/:id/followers  → UserListPage   (follower list)
/user/:id/following  → UserListPage   (following list)
/pool                → PoolPage       (sedimentation pool)
/bookmarks           → BookmarksPage  (bookmarked articles)
/history/:id         → HistoryPage    (article commit history)
```

## 2. Router Features

**Auth guards:** `beforeEach` checks `userStore.viewer` for protected routes. If unauthenticated, redirects to home and shows AuthModal. `showAuthModal` flag in localStorage survives page reload.

**Tab tracking:** `afterEach` calls `tabStore.activateTabByRoute(fullPath)` for `/edit`, `/article`, `/articles` routes. Editor tabs use `fullPath` (includes `?new=1&_t=X`) for unique IDs. Article paths normalize `/articles/foo` → `/article/foo`.

**keepAliveVersion:** `beforeEach` bumps `keepAliveVersion` when navigating to a tab-tracked page with zero open tabs. This clears stale `<keep-alive>` instances from previously closed tabs.

## 3. Page Component Patterns

### Pattern A: `useAsyncResource` + local refs (SchoolsPage, UserPage, PoolPage)

```typescript
const { data, loading, error, refresh } = useAsyncResource(
  () => apiCall(params),
  { immediate: isOnline.value }  // skip if offline
)
// Watch connectionState for lazy load
watch(isSynced, (online) => { if (online) refresh() })
```

### Pattern B: Direct composable usage (EditorPage, ArticlePage)

```typescript
// EditorPage — uses 4 composables
const { canWrite, isLocalOnly } = useOffline()
const { isOnline } = useNetworkStatus()
const { upload: autoUpload } = useArticleSync(draftId, sid, sch, lh)
const { saveDraft, loadDraft } = useDraftPersistence()

// Local state
const content = ref('')
const title = ref('')
const isClean = computed(() => content.value === lastSaved.value)
```

### Pattern C: Multi-composable page (HomePage)

```typescript
const { isOnline } = useNetworkStatus()
const { canRead } = useOffline()
const { toggle: toggleBookmark } = useBookmarkToggle(articles, onError)

// Two data sources
const localArticles = ref<ArticleSummary[]>([])    // Tauri IPC
const feedArticles = ref<ArticleSummary[]>([])      // REST API

// Conditional fetch
if (!isOnline.value && userStore.viewer) {
  // Load local cache
}
```

## 4. EditorPage — Most Complex Page

### Component Tree

```
EditorPage
├── CodeEditor (CodeMirror 6)
│   └── Markdown/Typst source
├── Preview Panel (split-pane)
│   ├── Markdown: client-side compile (marked + KaTeX)
│   └── Typst: server-side compile (/compile-preview)
├── Save Button
│   └── handleSaveDraft()
│       ├── Tauri: IPC → Rust save_draft → git commit
│       └── Web: PUT /articles/{id}
│       └── → useArticleSync.pushUpdate() (if server_article_id)
├── Format Picker (Markdown / Typst) — shown on new article
├── Commit Message Popup — per-save commit message
├── DownloadButton — disabled until first save, embeds commit hash
└── DeleteButton — idle/confirm/deleting states
```

### Save Flow

```
User types → Ctrl+S or click Save
  → handleSaveDraft()
    → if (isClean) return (no unsaved changes)
    → Tauri: ipc.save_draft({ id, title, content, format })
      → Rust: local_store.save_draft() → SQLite
      → Rust: local_git.commit(message) → git repo
      → return { hash: 'abc1234' }
    → Web: PUT /api/v1/articles/{id}
    → set server_article_id, server_commit_hash
    → _tryAutoUpload() → useArticleSync.pushUpdate()
      → compare hashes → synced or conflict
    → tabStore.updateTabTitle(tabId, title)
    → isClean = true, save button grays out
```

## 5. Tab System (TabDrawer.vue)

### Behavior Spec

- **Create:** Navigating to `/edit` or `/article/:id` creates a tab via `ensureTab()`
- **Unique IDs:** Editor tabs use `fullPath` (includes `?new=1&_t=timestamp`), article tabs use normalized path
- **Activate:** `afterEach` router hook calls `activateTabByRoute()`
- **Close clean:** Tab closes immediately (no unsaved changes)
- **Close dirty:** Confirmation dialog: "Save before closing?" → Save & Close / Discard / Cancel
- **Close last tab:** If last tab closed, `keepAliveVersion++` to clear cache

### Save & Close Flow (App.vue)

```
User clicks "Save & Close"
  → app navigates to the dirty tab's route
  → dispatches CustomEvent 'tab-save-and-close'
  → EditorPage listens → calls handleSaveDraft()
  → watch: tab.dirty becomes false → tabStore.removeTab(tabId)
```

## 6. ArticlePage — Sync Conflict UI

### Diff View Overlay

When `syncState === 'conflict'`, ArticlePage shows a GitCompare icon next to the title. Clicking opens a full-screen diff overlay (Teleported to body):

```
┌────────────────────────────────────────────┐
│  Diff: Remote vs Local                      │
│  ┌──────────────┐  ┌──────────────┐        │
│  │ Remote        │  │ Local         │        │
│  │ (server ver)  │  │ (your ver)    │        │
│  │               │  │               │        │
│  └──────────────┘  └──────────────┘        │
│                                             │
│  [Keep Local (PUT)]    [Use Remote (rollback)]│
└────────────────────────────────────────────┘
```

Word-level diff via LCS-based token matching. Deletions in red, additions in green, changed words highlighted within lines.

## 7. Loading & Error Patterns

### Loading States

| Pattern | Used By |
|---------|---------|
| `useAsyncResource.loading` → skeleton | SchoolsPage, UserPage, PoolPage |
| Spinner icon (`Loader` + `animate-spin`) | DownloadButton, DeleteButton, SyncButton (pulsing dot) |
| Opacity 50% + cursor-not-allowed | All disabled buttons |
| Skeleton cards (`ArticleCardSkeleton`) | HomePage, SearchPage |

### Error States

| Pattern | Used By |
|---------|---------|
| Error banner (fixed top) | App.vue (syncError) |
| Toast-like message | None (not implemented) |
| Inline error text | AuthModal (form errors) |
| Silent fallback + log | useBookmarkToggle (rollback optimistic update) |
| userMessage on axios error | All API calls (client.ts interceptor) |

### What's Missing

- **No toast/notification system.** Errors appear as banner or inline text only. No non-blocking notification for transient errors.
- **No retry UI.** Failed API calls show error but offer no "Retry" button. User must refresh the page or re-trigger the action.
- **No offline queue.** Operations attempted while offline fail silently (with console logs). No queue for retry-when-online.

## 8. Design Issues

### I5: EditorPage is ~700 lines

The editor page handles: Markdown editing, Typst compilation, save/auto-upload, commit messages, download, delete, format picking, preview panel, and keyboard shortcuts. It should be split into composables.

### I6: `useAsyncResource` re-fetches on every mount

If a page is cached by `<keep-alive>`, re-navigating to it doesn't re-mount, so `useAsyncResource` doesn't re-fetch. But if the page is NOT cached (most list pages), every navigation triggers a new API call. No stale-while-revalidate pattern.

### I7: Conflict resolution requires full page refresh

After "Keep Local" or "Use Remote" in ArticlePage's diff overlay, the article re-fetches. If the fetch fails, the user sees stale data with no indication.
