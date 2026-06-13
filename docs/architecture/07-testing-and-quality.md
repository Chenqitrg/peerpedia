# 07 — Testing & Quality

> Test architecture, coverage gaps, known issues, technical debt.

## 1. Test Infrastructure

| Layer | Framework | Files | Tests | Config |
|-------|-----------|-------|-------|--------|
| Frontend (unit) | Vitest + jsdom | 52 | 557 | `vitest.config.ts` |
| Frontend (type) | vue-tsc | — | — | `tsconfig.json` |
| Backend | pytest | ~30 | 540 | `pyproject.toml` |
| Rust | cargo test | ~5 | 16 | `Cargo.toml` |
| Lint (Python) | ruff | — | — | `pyproject.toml` |
| Type (Python) | mypy | — | — | `pyproject.toml` |
| Lint (JS) | eslint | — | — | `eslint.config.js` |
| Format (Rust) | rustfmt + clippy | — | — | `Cargo.toml` |
| CI | GitHub Actions | 10 jobs | — | `.github/workflows/ci.yml` |

## 2. Frontend Test Patterns

### Pattern 1: Composables (pure logic testing)

```typescript
// useOffline.test.ts
vi.mock('../useNetworkStatus', () => ({ useNetworkStatus: vi.fn() }))
function setOnline(online: boolean) {
  mockedUseNetworkStatus.mockReturnValue({
    isOnline: { value: online },
    isSynced: { value: online },
    connectionState: { value: online ? 'synced' : 'idle' },
    ping: vi.fn(),
  })
}
it('all features canRead returns true when online', () => {
  setOnline(true)
  const { canRead } = useOffline()
  expect(canRead('pool')).toBe(true)
})
```

### Pattern 2: Component tests (mount + assert)

```typescript
// SyncButton.test.ts
vi.mock('@/composables/useNetworkStatus', () => ({
  useNetworkStatus: () => ({
    connectionState: ref('idle'),
    flash: ref(false),
    connect: vi.fn(),
    disconnect: vi.fn(),
  }),
}))
it('renders idle state with WifiOff icon', () => {
  const wrapper = mount(SyncButton)
  expect(wrapper.find('.sync-dot--idle').exists()).toBe(true)
})
```

### Pattern 3: Page tests (full mount + router)

```typescript
// TabE2E.test.ts — black-box E2E
const router = createRouter({ routes, history: createMemoryHistory() })
const wrapper = mount(App, { global: { plugins: [router, pinia] } })
router.push('/edit?new=1')
await flushPromises()
expect(wrapper.text()).toContain('Untitled')
```

### Pattern 4: xspec tests (behavior spec)

```typescript
// SchoolsPage.xspec.test.ts — SPECIFICATION: Follow data on server
// Online: REST API. Offline: grayed button.
mockIsOnline.value = false
const wrapper = mount(SchoolsPage)
expect(wrapper.find('[data-testid="follow-btn"]').attributes('disabled')).toBeDefined()
```

## 3. Mock Complexity

The `useNetworkStatus` mock appears in 13 test files. After the three-state sync button refactor, every mock needs these properties:

```typescript
{
  isOnline: { value: true },      // backward compat
  isSynced: { value: true },       // new API
  connectionState: { value: 'synced' }, // for useOffline, useBookmarkToggle
  flash: { value: false },         // for SyncButton
  connect: vi.fn(),                // SyncButton click
  disconnect: vi.fn(),             // SyncButton click
  ping: vi.fn(),                   // App.vue onMounted
}
```

**Problem:** Adding a new export to `useNetworkStatus` requires updating 13 mock files. This is a design smell — the singleton pattern creates wide coupling.

## 4. Known Test Gaps

### G1: No SyncButton integration test

`SyncButton.test.ts` tests the component in isolation (mocked useNetworkStatus). There's no test that mounts NavBar (which uses real SyncButton) and tests the full connect → synced flow through the actual state machine.

### G2: No client.ts interceptor tests

`client.ts` has 540 backend tests covering API behavior, but no frontend test verifies that the axios interceptors correctly call `notifySuccess()`/`notifyFailure()` with the right state.

### G3: No useArticleSync + useNetworkStatus integration test

The two sync systems are tested independently. No test verifies that `useArticleSync` correctly reads `isOnline` from `useNetworkStatus` and transitions to `offline` when not synced.

### G4: No cross-tab/keep-alive tests

The tab system and keep-alive behavior are tested implicitly through `TabE2E.test.ts`, but edge cases like "two editor tabs, one dirty, close the clean one first" are not covered.

### G5: No error path tests for compilation

The Markdown compilation pipeline has no test for edge case math strings (nested $, escaped $, code blocks containing $). The Typst compilation has no test for timeout or sidecar crash.

## 5. TypeScript Strictness

`tsconfig.json` uses `strict: true` but `vue-tsc --noEmit` reports several pre-existing errors:
- `UserPage.vue`: possibly null drafts, missing properties
- `useArticleStore.test.ts`: type mismatches in test fixtures
- `useUserStore.ts`: type mismatch on string|null

These don't block the build (Vite doesn't type-check) but indicate incomplete type coverage.

## 6. Known Technical Debt

### TD1: NetworkStatusBadge deleted but no migration

`NetworkStatusBadge.vue` was deleted in the three-state sync button refactor. If any external code or future page references it by name (e.g., dynamic import), it will fail at runtime with no compile-time error.

### TD2: Backward compat `isOnline` name

`isOnline` is exported as an alias for `isSynced`. The name `isOnline` is misleading — it means "user confirmed server reachable by tapping a button," not "browser reports online." 9 files still use this name. Refactoring them all would be a large but low-risk cleanup.

### TD3: DESIGN.en.md partially outdated

Section 2.5 still describes auto-ping behavior ("Starts offline, flips online on first successful ping"). Updated in the last commit but the three-state model description is new and hasn't been reviewed against the actual implementation.

### TD4: No E2E test suite

All tests are unit/component tests. There's no Playwright or Cypress suite that drives the actual browser/Tauri app. Cross-page flows (login → create article → save → publish) are untested.

### TD5: Backend test database is in-memory SQLite

All backend tests use `sqlite:///:memory:`. This is fast but doesn't test file-system behavior (Git repos on disk). Git manager tests could pass while real disk operations fail.

### TD6: No performance regression tests

No benchmark suite. No test for "the app boots in under 2 seconds" or "the editor doesn't lag on 10K-word documents." Performance is verified manually.

## 7. CI Pipeline (10 Jobs)

```
GitHub Actions:
  Backend:
    - pytest (Python 3.12)
    - ruff check
    - mypy
  Frontend:
    - eslint
    - vitest
    - vue-tsc --noEmit
    - vite build (verify)
  Rust:
    - cargo clippy
    - cargo fmt --check
    - cargo test
```

All blocking on PR. No deployment step. No artifact publishing. No cross-platform Tauri build.
