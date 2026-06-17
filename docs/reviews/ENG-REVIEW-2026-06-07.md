# PeerPedia Engineering Review — Codebase Architecture Assessment

**Date:** 2026-06-06  
**Branch:** main  
**Scope:** Full codebase architecture, code quality, reusability, and simplicity  
**Requested by:** 评价代码的架构，屎山性，复用性，简洁性

---

## 1. Architecture Review

### 1.1 Component Size Distribution

| File | Lines | % of Category | Concern |
|------|-------|---------------|---------|
| ArticlePage.vue | 697 | 27.5% of pages | God component |
| EditorPage.vue | 619 | 24.4% of pages | God component |
| articles.py (backend) | 494 | 35.3% of routes | God module |
| **Top 3** | **1,810** | **—** | **Disproportionate concentration** |

ArticlePage + EditorPage = 52% of all page code across 2 of 11 pages. Backend `articles.py` = 35% of all route code in 1 of 11 modules.

### 1.2 Layer Violations — Pages Bypassing Stores

Pages import directly from `api/` instead of going through Pinia stores:

```
ArticlePage.vue: getArticle, getArticleSource, getHistory, forkArticle, extendSink, createMergeProposal (from api/articles)
ArticlePage.vue: getReviews, createReview, postReviewMessage (from api/reviews)
ArticlePage.vue: compilePreview (from api/compile)
EditorPage.vue:   compilePreview, compileDownload (from api/compile)
EditorPage.vue:   getArticleSource (from api/articles)
SearchPage.vue:   searchArticles (from api/search)
HistoryPage.vue:  getHistory, getDiff, rollbackArticle (from api/articles)
```

**Consequence:** API response shapes, error handling, and loading states are duplicated in every page. Changing an API endpoint requires touching N pages instead of 1 store.

### 1.3 localStorage Scattered Across 7 Files

```
main.ts:           locale
App.vue:           showAuthModal
useUserStore.ts:   token, viewer
NavBar.vue:        locale
api/client.ts:     token (auth header)
EditorPage.vue:    draft content
router/index.ts:   viewer, intendedRoute, showAuthModal
```

No single abstraction owns localStorage access. The same key could be written with different formats from different places.

---

## 2. Code Quality Review

### 2.1 Type Safety Escape Hatches

25 `as any` casts in source, 9 `: any` annotations, 7 `Record<string, unknown>`:

| Location | Pattern | Severity |
|----------|---------|----------|
| EditorPage:528 | `(scores as any)[key]` | P1 — runtime crash possible |
| EditorPage:218 | `const body: Record<string, unknown>` | P2 — entire API body untyped |
| EditorPage:232 | `let result: any` | P2 — return value untyped |
| ArticleCard:42 | `authors?.map((a: any) => a.name)` | P2 — author type erased |
| client.ts:32 | `detail.map((d: any) => {...})` | P2 — error shape untyped |
| useArticleStore:25 | `Record<string, unknown>` | P2 — store API untyped |

### 2.2 Error Handling — Copy-Paste Pattern

Every page repeats the same block:
```typescript
} catch (e: any) {
  errorMsg.value = e.response?.data?.detail || 'Something failed'
}
```

Appears in: EditorPage (×4), ArticlePage (×2), HistoryPage, UserListPage, AuthModal (×2), useBookmarkToggle (×2). 12+ identical error-handling blocks, each hardcoded with English fallback strings.

### 2.3 Duplicated Score Rendering

Two divergent implementations for the same concept:
- **ArticlePage:589-612** — Inline `<template>` with `mouseenter`/`mouseleave`, `onDimEnter`/`onDimLeave`, `hoveredDim`, `hoverTimer` (~50 lines)
- **ScoreBadges.vue (51 lines)** — Reusable component used for others' reviews

The hover-to-edit pattern is locked inside ArticlePage and cannot be reused on EditorPage's self-review panel or anywhere else.

---

## 3. Test Review

### 3.1 Coverage Asymmetry

| Layer | Tests | Key Gaps |
|-------|-------|----------|
| Backend API | 157 (strong) | Search lacks performance/scale tests |
| Frontend API modules | 43 (adequate) | — |
| Frontend components | 19 (weak) | NavBar, ArticleCard, AuthModal, RadarChart — many have 0 passing tests |
| Frontend pages | 39 (moderate) | PoolPage, BookmarksPage, CitationsPage, HistoryPage — tests exist but most fail |

14 of 23 test files (61%) show failed tests in the most recent vitest results — the test suite has bitrotted.

### 3.2 Missing Test Patterns

- **No interaction tests** for the score hover-to-edit flow (mouseenter → StarRating reveal → click → revert)
- **No error state tests** for API failures on any page (we just added the first ones)
- **No i18n tests** — no test verifies Chinese/English rendering
- **No accessibility tests** — no keyboard navigation, ARIA, or focus management coverage

---

## 4. Performance Review

### 4.1 Backend Search: O(n) Python Filtering

`backend/peerpedia_api/routes/search.py:53`:
```python
for a in articles_q.all():  # loads every article into memory
    if category_lower:
        cats = [c.lower() for c in (a.categories or [])]
    if q_lower:
        source = _read_source(a.id)  # opens a FILE for each article
```

With 1,000 articles: 1,000 DB rows + 1,000 file reads per search. The phase 2 plan should move this to SQL `LIKE` + JSON functions.

### 4.2 No Backend Caching

No ETags, no `Cache-Control` headers, no Redis/memory cache. Every page load re-fetches and re-compiles article content. Compiled HTML is stored in the DB (`compiled_output` column) which is a reasonable cache, but source re-fetch + re-compile still happens on cache miss.

---

## 5. 屎山程度 (Spaghetti Assessment)

**Current score: 4/10** (1 = pristine, 10 = total rewrite needed)

**What's clean:**
- Backend route separation is good — 11 focused route modules
- Pinia stores have clear ownership (user, article, pool)
- Vue 3 Composition API used consistently
- API contract (`docs/api-contract.json`) is maintained
- Git-driven article storage is a clean architectural choice

**What's become spaghetti:**
- ArticlePage and EditorPage are god components that own too many concerns
- localStorage access is scattered without abstraction
- Error handling is copy-pasted 12+ times
- Type safety escape hatches (`as any`) are used as a crutch rather than fixing the underlying types
- Pages bypass stores for API calls, creating N×M coupling

**The trend line:** Each new feature adds lines to the god components rather than extracting sub-components. The contribution slider, merge button, and search filters were all added inline. This is the standard trajectory of a vibe-coded MVP — it works, but each addition increases the refactoring cost.

---

## 6. What Already Exists (Reuse Opportunities)

| Problem | Existing Solution | Currently Used? |
|---------|-------------------|-----------------|
| Async loading state | `useAsyncResource` composable | Only SearchPage |
| Bookmark toggle | `useBookmarkToggle` composable | SearchPage + ArticlePage (inconsistently) |
| Draft persistence | `useDraftPersistence` composable (exists in codebase) | EditorPage uses inline localStorage instead |
| Score display | `ScoreBadges` component | ArticlePage (others' reviews only) |
| Error display | `ErrorState` component | Only SearchPage |
| Loading skeleton | `SkeletonCard` component | Only SearchPage + ArticlePage |
| Status labels | `useStatusMap` composable | ArticlePage only |

**Key insight:** The codebase HAS good abstractions (composables, shared components) but they're used inconsistently. The pattern is: the first page builds it right, later pages copy-paste inline.

---

## 7. NOT in Scope (Explicitly Deferred)

- **Tauri Slice 2** (Typst local compilation, Sync engine) — DESIGN.md §4.6
- **Reputation-weighted scoring UI** — back end ready, front end pending
- **Profile edit page** — low priority
- **P2P/IPFS storage** — Phase 3
- **AI-assisted review/writing** — Phase 3
- **Production deployment** (Docker, CI/CD) — Phase 3
- **God component refactor** — deferred until Slice 2 when Tauri compilation forces EditorPage restructuring

---

## 8. Top Recommendations

1. **Extract `<SelfReviewPanel>` from EditorPage** — the publish modal (100+ lines of template + 60 lines of logic) is a self-contained concern. This is the lowest-hanging fruit for reducing EditorPage complexity.

2. **Route all API calls through stores** — pages should call `articleStore.fetchArticle(id)`, not `getArticle(id)` directly. This centralizes loading/error state and makes the pages thinner.

3. **Create a `useLocalStorage` composable** — one place that owns `getItem`/`setItem`/`removeItem` with typed keys. Replace scattered localStorage calls in 7 files.

4. **Add proper TypeScript types for API request/response bodies** — eliminate `Record<string, unknown>` and `as any` casts. The `docs/api-contract.json` already defines these shapes — generate types from it.

5. **Integrate hover-to-edit into ScoreBadges** — add an `editable` prop so both ArticlePage and EditorPage use the same component.

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| Eng Review | `/plan-eng-review` | Architecture & code quality | 1 | ISSUES_OPEN | 8 findings, 0 critical gaps |

---

## Decisions Made (2026-06-06)

| D# | Decision | Choice |
|----|----------|--------|
| D1 | God component extraction | **Extract now** — `<SelfReviewPanel>` from EditorPage, `<ReviewList>` from ArticlePage |
| D2 | Store-as-gateway pattern | **Enforce** — pages call stores, stores call API modules |
| D3 | Type safety | **Add typed interfaces now** — replace `Record<string, unknown>` and `as any` |

---

## Implementation Tasks

- [x] **T1 (P1)** — Extract `<SelfReviewPanel>` from EditorPage.vue ✅ `5cacbe6`
- [x] **T2 (P1)** — Extract `<ReviewPanel>` from ArticlePage.vue ✅ `766defc`
- [x] **T3 (P1)** — Route review API calls through useReviewStore ✅ `e19ad22`
- [x] **T4 (P1)** — Add typed API interfaces ✅ `5cacbe6`
- [ ] **T5 (P2)** — Create `useLocalStorage` composable → branch `finish-code-review-tasks`
- [ ] **T6 (P2)** — Integrate hover-to-edit into `ScoreBadges` → branch `finish-code-review-tasks`
- [ ] **T7 (P3)** — Move backend search to SQL-level filtering → branch `finish-code-review-tasks`

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| Eng Review | `/plan-eng-review` | Architecture & code quality | 1 | ISSUES_OPEN | 8 findings, 7 tasks created, 3 decisions resolved |

**VERDICT:** Architecture review complete. 3 structural decisions resolved. 7 implementation tasks filed (3 P1, 2 P2, 1 P3). Ready to implement.
