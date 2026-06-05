# Frontend Code Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate duplicated loading/error/data patterns across 8 pages, extract shared Pagination component, delete 3 dead components and 2 dead files, fix bookmark rollback bug and error handling gaps.

**Architecture:** Install VueUse (`@vueuse/core`) and replace hand-rolled data fetching with `useAsyncState` in 8 pages. Extract duplicated pagination UI from HomePage/SearchPage into a shared `<Pagination>` component. Delete dead code using obsolete CSS classes. Fix bugs in bookmark toggle and ArticlePage error display.

**Tech Stack:** Vue 3, TypeScript, Pinia, VueUse (`useAsyncState`), Vitest, pytest

---

### Task 1: Install VueUse

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Install @vueuse/core**

```bash
cd frontend && npm install @vueuse/core
```

Expected: package.json updated with `@vueuse/core` in dependencies.

- [ ] **Step 2: Verify install**

```bash
cd frontend && npx vitest run 2>&1 | tail -5
```

Expected: 115/116 pass (same baseline; FiveDimForm.test.ts has a pre-existing CSS class mismatch).

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: install @vueuse/core for useAsyncState"
```

---

### Task 2: Create Pagination component

**Files:**
- Create: `frontend/src/components/Pagination.vue`

- [ ] **Step 1: Write the component**

```vue
<!-- frontend/src/components/Pagination.vue -->
<script setup lang="ts">
defineProps<{
  page: number
  totalPages: number
}>()

const emit = defineEmits<{
  change: [page: number]
}>()
</script>

<template>
  <div
    v-if="totalPages > 1"
    class="flex items-center justify-center gap-2 pt-6 pb-4"
  >
    <button
      class="flex items-center justify-center w-8 h-8 rounded-lg text-xs font-mono
             text-ink-muted hover:text-ink hover:bg-[#21262d]
             disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
      :disabled="page <= 1"
      @click="emit('change', page - 1)"
      aria-label="Previous page"
    >
      &lsaquo;
    </button>

    <button
      v-for="p in totalPages"
      :key="p"
      class="flex items-center justify-center w-8 h-8 rounded-lg text-xs font-mono
             transition-colors duration-200"
      :class="p === page
        ? 'bg-accent text-[#0d1117] font-bold'
        : 'text-ink-muted hover:text-ink hover:bg-[#21262d]'"
      @click="emit('change', p)"
    >
      {{ p }}
    </button>

    <button
      class="flex items-center justify-center w-8 h-8 rounded-lg text-xs font-mono
             text-ink-muted hover:text-ink hover:bg-[#21262d]
             disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
      :disabled="page >= totalPages"
      @click="emit('change', page + 1)"
      aria-label="Next page"
    >
      &rsaquo;
    </button>
  </div>
</template>
```

- [ ] **Step 2: Run frontend tests**

```bash
cd frontend && npx vitest run 2>&1 | tail -5
```

Expected: 115/116 pass (new component is unused, no regression).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/Pagination.vue
git commit -m "feat: add Pagination component — shared page navigation UI"
```

---

### Task 3: Migrate HomePage to useAsyncState + Pagination

**Files:**
- Modify: `frontend/src/pages/HomePage.vue`

- [ ] **Step 1: Replace script section**

Replace lines 1-58 (the entire `<script setup>` block) with:

```vue
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAsyncState } from '@vueuse/core'
import { useUserStore } from '../stores/useUserStore'
import { fetchFeed } from '../api/feed'
import { useBookmarkToggle } from '../composables/useBookmarkToggle'
import ArticleCard from '../components/ArticleCard.vue'
import Pagination from '../components/Pagination.vue'
import type { ArticleSummary, FeedResponse } from '../api/types'
import { BookOpen } from 'lucide-vue-next'

const userStore = useUserStore()
const isLoggedIn = computed(() => !!userStore.viewer)

const pageSize = 20
const currentPage = ref(1)

const { state: feed, isLoading: loading, error: rawError, execute: loadFeed } = useAsyncState(
  () => fetchFeed(),
  null as FeedResponse | null,
  { immediate: false }
)

const articles = computed(() => feed.value?.articles ?? [])
const total = computed(() => feed.value?.total ?? 0)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

const error = computed(() => {
  const e = rawError.value as any
  return e?.userMessage || e?.response?.data?.detail || ''
})

const { toggle: handleToggleBookmark } = useBookmarkToggle(
  computed(() => articles.value),
  (_msg: string) => {}
)

function openAuth() {
  userStore.showAuthModal = true
}

function goToPage(page: number) {
  if (page < 1 || page > totalPages.value) return
  currentPage.value = page
  loadFeed()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

onMounted(() => {
  if (isLoggedIn.value) loadFeed()
})
</script>
```

Note: `articles` changes from `ref<ArticleSummary[]>` to `computed` — pass `computed(() => articles.value)` to `useBookmarkToggle` since it expects `Ref<ArticleSummary[]>`.

- [ ] **Step 2: Replace pagination block in template**

Delete lines 133-172 (the `<div v-if="totalPages > 1">` block) and replace with:

```vue
<Pagination :page="currentPage" :totalPages="totalPages" @change="goToPage" />
```

- [ ] **Step 3: Run frontend tests**

```bash
cd frontend && npx vitest run 2>&1 | tail -5
```

Expected: 115/116 pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/HomePage.vue
git commit -m "refactor: migrate HomePage to useAsyncState + Pagination component"
```

---

### Task 4: Migrate SearchPage to useAsyncState + Pagination

**Files:**
- Modify: `frontend/src/pages/SearchPage.vue`

- [ ] **Step 1: Replace script section**

Replace lines 1-72 with:

```vue
<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useAsyncState } from '@vueuse/core'
import { useRoute, useRouter } from 'vue-router'
import { searchArticles } from '../api/search'
import { useUserStore } from '../stores/useUserStore'
import { useBookmarkToggle } from '../composables/useBookmarkToggle'
import ArticleCard from '../components/ArticleCard.vue'
import Pagination from '../components/Pagination.vue'
import type { ArticleSummary, SearchResult } from '../api/types'
import { Search } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const query = ref('')
const searched = ref(false)
const currentPage = ref(1)
const pageSize = 20

const { state: result, isLoading: loading, error: rawError, execute: doSearch } = useAsyncState(
  async () => {
    if (!query.value.trim()) return null
    return await searchArticles(query.value)
  },
  null as SearchResult | null,
  { immediate: false }
)

const results = computed(() => result.value?.articles ?? [])
const total = computed(() => result.value?.total ?? 0)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

const error = computed(() => {
  const e = rawError.value as any
  return e?.userMessage || ''
})

const { toggle: handleToggleBookmark } = useBookmarkToggle(computed(() => results.value))

onMounted(() => {
  const q = route.query.q as string
  if (q) {
    query.value = q
    searched.value = true
    doSearch()
  }
})

watch(() => route.query.q, (newQ) => {
  if (newQ && newQ !== query.value) {
    query.value = newQ as string
    searched.value = true
    doSearch()
  }
})

async function executeSearch(page: number) {
  currentPage.value = page
  searched.value = true
  await doSearch()
}

function handleSearch(e: Event) {
  e.preventDefault()
  if (query.value.trim()) {
    router.push(`/search?q=${encodeURIComponent(query.value.trim())}`)
  }
}

function goToPage(page: number) {
  if (page < 1 || page > totalPages.value) return
  executeSearch(page)
  window.scrollTo({ top: 0, behavior: 'smooth' })
}
</script>
```

- [ ] **Step 2: Replace pagination block in template**

Delete lines 132-168 (the `<div v-if="totalPages > 1">` block) and replace with:

```vue
<Pagination :page="currentPage" :totalPages="totalPages" @change="goToPage" />
```

- [ ] **Step 3: Add error state in template**

After the loading block (line 111 `</div>`), add:

```vue
<!-- Error -->
<div v-else-if="error" class="card p-8 text-center">
  <p class="text-ink-muted">{{ error }}</p>
  <button class="btn-outline mt-4" @click="doSearch()">Retry</button>
</div>
```

Change `v-else-if="searched"` on line 114 to `v-else-if="searched && !error"`.

- [ ] **Step 4: Run frontend tests**

```bash
cd frontend && npx vitest run 2>&1 | tail -5
```

Expected: 115/116 pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/SearchPage.vue
git commit -m "refactor: migrate SearchPage to useAsyncState + Pagination, add error state"
```

---

### Task 5: Migrate remaining 6 pages to useAsyncState

**Files:**
- Modify: `frontend/src/pages/PoolPage.vue`
- Modify: `frontend/src/pages/BookmarksPage.vue`
- Modify: `frontend/src/pages/UserPage.vue`
- Modify: `frontend/src/pages/HistoryPage.vue`
- Modify: `frontend/src/pages/CitationsPage.vue`
- Modify: `frontend/src/pages/SchoolsPage.vue`

Each page follows the same pattern: replace `loading`/`error` refs + try/catch/finally with `useAsyncState`.

- [ ] **Step 1: Migrate PoolPage.vue**

Replace the script's data-fetching section. The core change:

```typescript
// Before
const loading = ref(true)
const error = ref<string | null>(null)
const articles = ref<ArticleSummary[]>([])
onMounted(async () => {
  try {
    const data = await getPool()
    articles.value = data.articles ?? []
  } catch (e: any) {
    error.value = e.userMessage || 'Failed to load pool'
  } finally {
    loading.value = false
  }
})

// After
import { useAsyncState } from '@vueuse/core'
const { state: pool, isLoading: loading, error: rawError, execute } = useAsyncState(
  () => getPool(),
  null as PoolResponse | null,
  { immediate: false }
)
const articles = computed(() => pool.value?.articles ?? [])
const error = computed(() => {
  const e = rawError.value as any
  return e?.userMessage || ''
})
onMounted(() => execute())
```

Template: change `@click="loadPool"` retry to `@click="execute()"`.

- [ ] **Step 2: Migrate BookmarksPage.vue**

Same pattern. Key: the error state template already exists with a Retry button — wire it to `execute()`.

- [ ] **Step 3: Migrate UserPage.vue**

Same pattern for the main `loadUser()` function. Keep `loadFollowers()` and `loadFollowing()` as-is (they use a toggle pattern that's different from the loading/error/data triplet).

- [ ] **Step 4: Migrate HistoryPage.vue**

Same pattern. HistoryPage already has loading/error/empty states — just replace the refs and try/catch.

- [ ] **Step 5: Migrate CitationsPage.vue**

Same pattern.

- [ ] **Step 6: Migrate SchoolsPage.vue**

Same pattern. SchoolsPage currently has no error state — add one using the `error` computed from `useAsyncState`:

```vue
<div v-else-if="error" class="card p-8 text-center">
  <p class="text-ink-muted">{{ error }}</p>
  <button class="btn-outline mt-4" @click="execute()">Retry</button>
</div>
```

- [ ] **Step 7: Run frontend tests after each page**

```bash
cd frontend && npx vitest run 2>&1 | tail -5
```

Expected: 115/116 pass after each page migration.

- [ ] **Step 8: Commit each page individually**

```bash
git add frontend/src/pages/PoolPage.vue && git commit -m "refactor: migrate PoolPage to useAsyncState"
git add frontend/src/pages/BookmarksPage.vue && git commit -m "refactor: migrate BookmarksPage to useAsyncState"
# ... etc for each page
```

---

### Task 6: Delete dead components

**Files:**
- Delete: `frontend/src/components/CommentThread.vue`
- Delete: `frontend/src/components/DiffViewer.vue`
- Delete: `frontend/src/components/MarkdownRenderer.vue`

- [ ] **Step 1: Delete the files**

```bash
rm frontend/src/components/CommentThread.vue
rm frontend/src/components/DiffViewer.vue
rm frontend/src/components/MarkdownRenderer.vue
```

- [ ] **Step 2: Run frontend tests to confirm no imports break**

```bash
cd frontend && npx vitest run 2>&1 | tail -5
```

Expected: 115/116 pass. These components are never imported (verified via grep in design phase).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/CommentThread.vue frontend/src/components/DiffViewer.vue frontend/src/components/MarkdownRenderer.vue
git commit -m "chore: remove dead components (CommentThread, DiffViewer, MarkdownRenderer) — replaced by inline code"
```

---

### Task 7: Delete dead composable and store

**Files:**
- Delete: `frontend/src/composables/usePagination.ts`
- Delete: `frontend/src/stores/usePoolStore.ts`
- Modify: `frontend/src/stores/useArticleStore.ts`

- [ ] **Step 1: Delete dead files**

```bash
rm frontend/src/composables/usePagination.ts
rm frontend/src/stores/usePoolStore.ts
```

- [ ] **Step 2: Remove unused `loading` field from useArticleStore**

In `frontend/src/stores/useArticleStore.ts`, remove line 10 (`const loading = ref(false)`), remove `loading` from the return object (line 47), and remove `loading.value = true` (line 13) and `loading.value = false` (line 19).

The store becomes:

```typescript
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getArticles, getArticle, createArticle, updateArticle } from '../api/articles'
import type { ArticleListParams } from '../api/articles'

export const useArticleStore = defineStore('article', () => {
  const articles = ref<any[]>([])
  const total = ref(0)
  const currentArticle = ref<any>(null)

  async function fetchArticles(params?: ArticleListParams) {
    try {
      const data = await getArticles(params)
      articles.value = data.articles ?? data
      total.value = data.total ?? 0
    } catch {
      // errors surface to caller via useAsyncState
    }
  }

  async function fetchArticle(id: string) {
    currentArticle.value = await getArticle(id)
  }

  async function createArticleAction(body: Record<string, unknown>) {
    const newArticle = await createArticle(body)
    articles.value.push(newArticle)
    return newArticle
  }

  async function updateArticleAction(id: string, body: Record<string, unknown>) {
    const updated = await updateArticle(id, body)
    const idx = articles.value.findIndex((a: any) => a.id === id)
    if (idx !== -1) articles.value[idx] = updated
    if (currentArticle.value?.id === id) currentArticle.value = updated
    return updated
  }

  return {
    articles,
    total,
    currentArticle,
    fetchArticles,
    fetchArticle,
    createArticle: createArticleAction,
    updateArticle: updateArticleAction,
  }
})
```

- [ ] **Step 3: Run frontend tests**

```bash
cd frontend && npx vitest run 2>&1 | tail -5
```

Expected: 115/116 pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/composables/usePagination.ts frontend/src/stores/usePoolStore.ts frontend/src/stores/useArticleStore.ts
git commit -m "chore: remove dead code — usePagination, usePoolStore, unused loading field"
```

---

### Task 8: Fix bookmark optimistic update rollback

**Files:**
- Modify: `frontend/src/composables/useBookmarkToggle.ts`

- [ ] **Step 1: Rewrite the toggle function with rollback**

Replace the `toggle` function (lines 19-36) with:

```typescript
async function toggle(articleId: string, currentlyBookmarked: boolean) {
  if (!userStore.viewer) return
  const article = articles.value.find(a => a.id === articleId)
  if (!article) return

  const previous = article.is_bookmarked
  article.is_bookmarked = !currentlyBookmarked

  try {
    if (currentlyBookmarked) {
      await removeBookmark(articleId)
    } else {
      await addBookmark(articleId)
    }
  } catch (e: any) {
    article.is_bookmarked = previous
    if (onError) {
      onError(e.userMessage || 'Failed to update bookmark')
    }
  }
}
```

Key change: save `previous` value before toggling, restore on failure. Also find the article first and bail if not found (avoids silent no-op).

- [ ] **Step 2: Run bookmark-related tests**

```bash
cd frontend && npx vitest run src/composables/__tests__ 2>&1 | tail -10
```

Expected: all composable tests pass.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/composables/useBookmarkToggle.ts
git commit -m "fix: bookmark optimistic update — rollback on API failure"
```

---

### Task 9: Fix ArticlePage error differentiation

**Files:**
- Modify: `frontend/src/pages/ArticlePage.vue`

- [ ] **Step 1: Add error ref and distinguish error types**

In the `<script setup>`, add an `errorMessage` ref:

```typescript
// Add after existing refs (around line 38)
const errorMessage = ref('')
```

In the `onMounted` (around line 122), replace the bare `catch`:

```typescript
onMounted(async () => {
  try {
    article.value = await getArticle(id)
    await loadCompiledContent()
    loadReviews()
  } catch (e: any) {
    const status = e?.response?.status
    if (status === 404) {
      errorMessage.value = 'Article not found.'
    } else {
      errorMessage.value = e.userMessage || 'Failed to load article. Is the server running?'
    }
  } finally {
    loading.value = false
  }
})
```

- [ ] **Step 2: Update the error template**

Replace line 667-669:

```vue
<!-- Error state -->
<div v-else class="card p-12 text-center">
  <p class="text-ink-muted">{{ errorMessage || 'Article not found.' }}</p>
  <button v-if="errorMessage && !errorMessage.includes('not found')" class="btn-outline mt-4" @click="loadArticle()">Retry</button>
</div>
```

- [ ] **Step 3: Run frontend tests**

```bash
cd frontend && npx vitest run 2>&1 | tail -5
```

Expected: 115/116 pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ArticlePage.vue
git commit -m "fix: ArticlePage — distinguish 404 vs network errors, add Retry button"
```

---

### Task 10: Add disabled "Coming soon" to Edit Profile button

**Files:**
- Modify: `frontend/src/pages/UserPage.vue`

- [ ] **Step 1: Replace the Edit Profile button**

Replace lines 180-187 with:

```vue
<!-- Edit profile button (self only) — coming soon -->
<button
  v-if="isSelf"
  class="btn-outline btn-sm shrink-0 opacity-50 cursor-not-allowed"
  disabled
  title="Coming soon"
>
  <Edit class="w-3.5 h-3.5" stroke-width="2" />
  Edit Profile
</button>
```

Remove the `goToEditProfile` function (lines 95-97).

- [ ] **Step 2: Run frontend tests**

```bash
cd frontend && npx vitest run 2>&1 | tail -5
```

Expected: 115/116 pass.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/UserPage.vue
git commit -m "fix: Edit Profile button — disabled with Coming soon tooltip"
```

---

### Task 11: Final verification

- [ ] **Step 1: Run full test suite**

```bash
# Frontend tests
cd frontend && npx vitest run 2>&1 | tail -5

# Backend tests
.venv/bin/python -m pytest core/tests/ backend/tests/ -q
```

Expected: 115/116 frontend pass, 199/199 backend pass.

- [ ] **Step 2: Build check**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

Expected: build succeeds with no new errors.

- [ ] **Step 3: Verify deleted imports**

```bash
cd frontend && grep -r "CommentThread\|DiffViewer\|MarkdownRenderer\|usePagination\|usePoolStore" src/ --include="*.vue" --include="*.ts" | grep -v "__tests__" | grep -v node_modules
```

Expected: no output (no remaining imports of deleted files).

- [ ] **Step 4: Commit if any final cleanup needed**
