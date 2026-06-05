# Frontend Code Cleanup & Productionization

**Date:** 2026-06-06
**Branch:** main
**Status:** designed, pending implementation

## Context

PeerPedia's frontend (~4,500 lines, 37 files) works but carries significant code duplication
and dead weight from earlier iterations. The architecture assessment found:

- 8 pages each hand-roll identical loading/error/data fetching patterns (~10 lines each)
- HomePage and SearchPage duplicate the same pagination UI (~35 lines each)
- 3 components and 2 composables/stores are dead code using an obsolete CSS system
- Error handling is inconsistent: 2 pages silently swallow errors
- The bookmark optimistic update doesn't roll back on failure

This spec covers a lightweight refactor: extract shared abstractions, delete dead code,
fix bugs. No architectural overhaul (no VueQuery, no component library, no EditorPage
rewrite).

## Changes

### 1. Install VueUse

Add `@vueuse/core` as a dependency. Use `useAsyncState` to replace the manual
loading/error/data pattern duplicated across 8 pages.

```bash
cd frontend && npm install @vueuse/core
```

`useAsyncState` is tree-shakable — only the imported function is bundled.

### 2. Adopt `useAsyncState` in 8 pages

**Before** (duplicated in every page):

```typescript
const loading = ref(true)
const error = ref<string | null>(null)
const data = ref<SomeType | null>(null)

async function fetch() {
  loading.value = true
  error.value = null
  try {
    data.value = await apiCall()
  } catch (e: any) {
    error.value = e.userMessage || e.message || 'Failed'
  } finally {
    loading.value = false
  }
}
onMounted(() => fetch())
```

**After:**

```typescript
import { useAsyncState } from '@vueuse/core'

const { state: data, isLoading: loading, error: rawError, execute } = useAsyncState(
  () => apiCall(),
  null,
  { immediate: false }
)

// Wrap raw error for display
const error = computed(() => {
  const e = rawError.value as any
  return e?.userMessage || e?.message || null
})
onMounted(() => execute())
// execute() also serves as the retry handler: @click="execute"
```

**Pages affected:** HomePage, PoolPage, SearchPage, BookmarksPage, UserPage,
HistoryPage, CitationsPage, SchoolsPage.

### 3. Extract `<Pagination>` component

**New file:** `frontend/src/components/Pagination.vue`

Props: `page: number`, `totalPages: number`
Emits: `change(page: number)`

Removes ~35 lines of duplicated template from HomePage.vue and SearchPage.vue.

### 4. Delete dead code

| File | Reason |
|------|--------|
| `components/CommentThread.vue` | Replaced by inline code in ArticlePage.vue; uses stale CSS classes |
| `components/DiffViewer.vue` | Replaced by inline code in HistoryPage.vue; uses stale CSS classes |
| `components/MarkdownRenderer.vue` | 7-line unused wrapper; Markdown rendered by backend compilation |
| `composables/usePagination.ts` | Never imported; pages use local refs for pagination state |
| `stores/usePoolStore.ts` | Never imported; PoolPage uses local refs + direct API calls |

**Remove from `stores/useArticleStore.ts`:** the `loading` field (declared but never read).

**Keep for future use:** `components/RadarChart.vue`, `components/ReviewModal.vue` (WIP).

### 5. Fix bugs

**Bookmark optimistic update rollback** (`composables/useBookmarkToggle.ts`):

Save previous state before toggling; restore on API failure.

**ArticlePage error differentiation** (`pages/ArticlePage.vue`):

Distinguish 404 ("Article not found") from network errors ("Cannot reach server")
instead of showing "Article not found" for all error types.

**Edit Profile button** (`pages/UserPage.vue`):

Add `disabled` attribute and "Coming soon" tooltip. Remove the empty stub function body.

### 6. Verification after each step

After every logical unit, run the full test suite:

```bash
# Backend
.venv/bin/python -m pytest core/tests/ backend/tests/ -q

# Frontend
cd frontend && npx vitest run
```

**Baseline:** 199 backend tests + 116 frontend tests. Zero regressions expected.

## NOT in scope

- VueQuery / TanStack Query — larger architectural change, deferred
- Component library (shadcn-vue, PrimeVue) — deferred
- EditorPage refactor (CodeMirror, split-pane mobile support) — deferred
- Toast/notification system — next phase
- E2E tests — next phase
- i18n — not needed yet (English-only product)

## Files touched

```
frontend/src/
├── composables/
│   ├── useBookmarkToggle.ts → MODIFIED (rollback fix)
│   └── usePagination.ts    → DELETED (dead code)
├── components/
│   ├── Pagination.vue      → NEW
│   ├── CommentThread.vue   → DELETED
│   ├── DiffViewer.vue      → DELETED
│   └── MarkdownRenderer.vue → DELETED
├── stores/
│   ├── usePoolStore.ts     → DELETED
│   └── useArticleStore.ts  → MODIFIED (remove unused `loading`)
└── pages/
    ├── ArticlePage.vue     → MODIFIED (error differentiation)
    ├── UserPage.vue        → MODIFIED (Edit Profile disabled)
    ├── HomePage.vue        → MODIFIED (useAsyncState + Pagination)
    ├── PoolPage.vue        → MODIFIED (useAsyncState)
    ├── SearchPage.vue      → MODIFIED (useAsyncState + Pagination)
    ├── BookmarksPage.vue   → MODIFIED (useAsyncState)
    ├── HistoryPage.vue     → MODIFIED (useAsyncState)
    ├── CitationsPage.vue   → MODIFIED (useAsyncState)
    └── SchoolsPage.vue     → MODIFIED (useAsyncState)
```

## Verification

1. `cd frontend && npx vitest run` — all 116 tests pass
2. `cd backend && .venv/bin/python -m pytest core/tests/ backend/tests/ -q` — all 199 tests pass
3. `npm run build` — production build succeeds with no new warnings
4. Manual smoke test: browse HomePage → paginate → open ArticlePage → bookmark toggle → search → user profile
