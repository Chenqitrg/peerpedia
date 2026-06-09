# VSCode-Style Tab System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a VSCode-style left-sidebar tab drawer that lets authors open multiple editor/article tabs simultaneously, switch between them without losing state, and gets a save-confirmation dialog when closing dirty tabs.

**Architecture:** A Pinia store (`useTabStore`) manages tab state and persists to localStorage. A `TabDrawer` overlay component sits on the left edge — collapsed to a 4px trigger strip by default, expands on hover to show tabs. `App.vue` renders the drawer and expands `KeepAlive` to cache both `EditorPage` and `ArticlePage` by route key. `EditorPage` syncs its `isClean` state to the store; `ArticlePage` registers its title on mount. A `router.afterEach` guard auto-registers tabs for `/edit` and `/article` routes.

**Tech Stack:** Vue 3, TypeScript, Pinia, Vue Router, Tailwind CSS, lucide-vue-next icons, vitest

---

### Task 1: Tab type definitions

**Files:**
- Create: `frontend/src/stores/useTabStore.ts`

- [ ] **Step 1: Create the store with types and skeleton**

```typescript
import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { loadJSON, saveJSON } from '../composables/useLocalStorage'

export interface Tab {
  id: string           // equals routePath, e.g. "/edit/abc123"
  type: 'editor' | 'article'
  title: string
  dirty: boolean
  icon: 'edit' | 'eye'
}

const STORAGE_KEY = 'peerpedia_tabs'

export const useTabStore = defineStore('tab', () => {
  const tabs = ref<Tab[]>([])
  const activeTabId = ref<string | null>(null)
  const pendingCloseTabId = ref<string | null>(null)

  // ── Helpers ──────────────────────────────────────────────

  function persist(): void {
    saveJSON(STORAGE_KEY, {
      tabs: tabs.value.map(t => ({ id: t.id, type: t.type, title: t.title, icon: t.icon })),
      activeTabId: activeTabId.value,
    })
  }

  function findTab(routePath: string): Tab | undefined {
    return tabs.value.find(t => t.id === routePath)
  }

  function getAdjacentTabId(closedId: string): string | null {
    const idx = tabs.value.findIndex(t => t.id === closedId)
    if (idx === -1) return null
    // Prefer the tab to the right, fall back to the left, then null
    if (idx < tabs.value.length - 1) return tabs.value[idx + 1].id
    if (idx > 0) return tabs.value[idx - 1].id
    return null
  }

  // ── Actions ──────────────────────────────────────────────

  function openTab(to: { path: string; params: Record<string, string> }): void {
    const routePath = to.path.startsWith('/articles/')
      ? to.path.replace('/articles/', '/article/')
      : to.path

    // Only track /edit and /article routes
    if (!routePath.startsWith('/edit') && !routePath.startsWith('/article')) return

    const existing = findTab(routePath)
    if (existing) {
      activeTabId.value = routePath
      persist()
      return
    }

    const type = routePath.startsWith('/edit') ? 'editor' : 'article'
    tabs.value.push({
      id: routePath,
      type,
      title: type === 'editor' ? 'Untitled' : 'Loading...',
      dirty: false,
      icon: type === 'editor' ? 'edit' : 'eye',
    })
    activeTabId.value = routePath
    persist()
  }

  function activateTab(tabId: string): void {
    const router = useRouter()
    activeTabId.value = tabId
    persist()
    router.push(tabId)
  }

  function updateTab(tabId: string, patch: Partial<Pick<Tab, 'title' | 'dirty'>>): void {
    const tab = findTab(tabId)
    if (!tab) return
    if (patch.title !== undefined) tab.title = patch.title
    if (patch.dirty !== undefined) tab.dirty = patch.dirty
    persist()
  }

  function closeTab(tabId: string): { shouldPrompt: boolean; nextTabId: string | null } {
    const tab = findTab(tabId)
    if (!tab) return { shouldPrompt: false, nextTabId: null }

    if (tab.dirty) {
      pendingCloseTabId.value = tabId
      return { shouldPrompt: true, nextTabId: null }
    }

    return removeTab(tabId)
  }

  function clearPendingClose(): void {
    pendingCloseTabId.value = null
  }

  function removeTab(tabId: string): { shouldPrompt: false; nextTabId: string | null } {
    const nextTabId = getAdjacentTabId(tabId)
    const wasActive = activeTabId.value === tabId

    tabs.value = tabs.value.filter(t => t.id !== tabId)

    if (wasActive) {
      if (nextTabId) {
        activeTabId.value = nextTabId
        const router = useRouter()
        router.push(nextTabId)
      } else {
        activeTabId.value = null
        const router = useRouter()
        router.push('/')
      }
    }

    persist()
    return { shouldPrompt: false, nextTabId }
  }

  function restoreTabs(): void {
    const saved = loadJSON<{ tabs: Tab[]; activeTabId: string | null }>(STORAGE_KEY)
    if (!saved || !saved.tabs || saved.tabs.length === 0) return

    tabs.value = saved.tabs.map(t => ({ ...t, dirty: false }))
    activeTabId.value = saved.activeTabId

    if (saved.activeTabId) {
      const router = useRouter()
      router.push(saved.activeTabId)
    }
  }

  return {
    tabs,
    activeTabId,
    pendingCloseTabId,
    openTab,
    activateTab,
    updateTab,
    closeTab,
    removeTab,
    clearPendingClose,
    restoreTabs,
  }
})
```

- [ ] **Step 2: Write the store unit test**

```bash
mkdir -p frontend/src/stores/__tests__
```

Create `frontend/src/stores/__tests__/useTabStore.test.ts`:

```typescript
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useTabStore } from '../useTabStore'

const mockPush = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush }),
}))

describe('useTabStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    mockPush.mockClear()
  })

  describe('openTab', () => {
    it('adds a new editor tab for /edit route', () => {
      const store = useTabStore()
      store.openTab({ path: '/edit', params: {} })
      expect(store.tabs).toHaveLength(1)
      expect(store.tabs[0].type).toBe('editor')
      expect(store.tabs[0].title).toBe('Untitled')
      expect(store.tabs[0].dirty).toBe(false)
      expect(store.activeTabId).toBe('/edit')
    })

    it('adds a new article tab for /article route', () => {
      const store = useTabStore()
      store.openTab({ path: '/article/abc123', params: { id: 'abc123' } })
      expect(store.tabs).toHaveLength(1)
      expect(store.tabs[0].type).toBe('article')
      expect(store.tabs[0].icon).toBe('eye')
    })

    it('normalizes /articles/ to /article/', () => {
      const store = useTabStore()
      store.openTab({ path: '/articles/abc123', params: { id: 'abc123' } })
      expect(store.tabs[0].id).toBe('/article/abc123')
    })

    it('activates existing tab instead of creating duplicate', () => {
      const store = useTabStore()
      store.openTab({ path: '/edit/abc', params: { id: 'abc' } })
      store.openTab({ path: '/edit/abc', params: { id: 'abc' } })
      expect(store.tabs).toHaveLength(1)
    })

    it('ignores non-tab routes', () => {
      const store = useTabStore()
      store.openTab({ path: '/pool', params: {} })
      expect(store.tabs).toHaveLength(0)
    })
  })

  describe('activateTab', () => {
    it('sets activeTabId and navigates', () => {
      const store = useTabStore()
      store.activateTab('/edit/abc')
      expect(store.activeTabId).toBe('/edit/abc')
      expect(mockPush).toHaveBeenCalledWith('/edit/abc')
    })
  })

  describe('updateTab', () => {
    it('updates title and dirty on existing tab', () => {
      const store = useTabStore()
      store.openTab({ path: '/edit/abc', params: { id: 'abc' } })
      store.updateTab('/edit/abc', { title: 'My Draft', dirty: true })
      expect(store.tabs[0].title).toBe('My Draft')
      expect(store.tabs[0].dirty).toBe(true)
    })

    it('is a no-op for unknown tab', () => {
      const store = useTabStore()
      expect(() => store.updateTab('/edit/nonexistent', { title: 'X' })).not.toThrow()
    })
  })

  describe('closeTab', () => {
    it('removes clean tab immediately', () => {
      const store = useTabStore()
      store.openTab({ path: '/article/1', params: { id: '1' } })
      const result = store.closeTab('/article/1')
      expect(result.shouldPrompt).toBe(false)
      expect(store.tabs).toHaveLength(0)
    })

    it('returns shouldPrompt=true and sets pendingCloseTabId for dirty tab', () => {
      const store = useTabStore()
      store.openTab({ path: '/edit/abc', params: { id: 'abc' } })
      store.updateTab('/edit/abc', { dirty: true })
      const result = store.closeTab('/edit/abc')
      expect(result.shouldPrompt).toBe(true)
      expect(store.pendingCloseTabId).toBe('/edit/abc')
      expect(store.tabs).toHaveLength(1) // not removed yet
      // clearPendingClose resets it
      store.clearPendingClose()
      expect(store.pendingCloseTabId).toBeNull()
    })
  })

  describe('removeTab', () => {
    it('navigates to adjacent tab when closing active tab', () => {
      const store = useTabStore()
      store.openTab({ path: '/edit/a', params: { id: 'a' } })
      store.openTab({ path: '/edit/b', params: { id: 'b' } })
      store.openTab({ path: '/edit/c', params: { id: 'c' } })
      store.activateTab('/edit/b')
      mockPush.mockClear()
      store.removeTab('/edit/b')
      expect(store.tabs.map(t => t.id)).toEqual(['/edit/a', '/edit/c'])
      // Should navigate to right neighbor (/edit/c)
      expect(mockPush).toHaveBeenCalledWith('/edit/c')
    })

    it('navigates to home when closing last tab', () => {
      const store = useTabStore()
      store.openTab({ path: '/edit/x', params: { id: 'x' } })
      store.removeTab('/edit/x')
      expect(store.activeTabId).toBeNull()
      expect(mockPush).toHaveBeenCalledWith('/')
    })
  })

  describe('restoreTabs', () => {
    it('restores tabs from localStorage', () => {
      localStorage.setItem('peerpedia_tabs', JSON.stringify({
        tabs: [
          { id: '/edit/a', type: 'editor', title: 'Draft A', icon: 'edit' },
          { id: '/article/b', type: 'article', title: 'Article B', icon: 'eye' },
        ],
        activeTabId: '/edit/a',
      }))
      const store = useTabStore()
      store.restoreTabs()
      expect(store.tabs).toHaveLength(2)
      expect(store.tabs[0].dirty).toBe(false) // dirty always reset on restore
      expect(store.activeTabId).toBe('/edit/a')
      expect(mockPush).toHaveBeenCalledWith('/edit/a')
    })

    it('is a no-op when localStorage is empty', () => {
      const store = useTabStore()
      store.restoreTabs()
      expect(store.tabs).toHaveLength(0)
    })
  })
})
```

- [ ] **Step 3: Run tests, verify they pass**

```bash
cd frontend && npx vitest run src/stores/__tests__/useTabStore.test.ts
```

Expected: 12 tests pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/stores/useTabStore.ts frontend/src/stores/__tests__/useTabStore.test.ts
git commit -m "feat: add useTabStore for VSCode-style tab management
Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: TabDrawer component

**Files:**
- Create: `frontend/src/components/TabDrawer.vue`

- [ ] **Step 1: Write the component test**

Create `frontend/src/components/__tests__/TabDrawer.test.ts`:

```typescript
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useTabStore } from '../../stores/useTabStore'
import TabDrawer from '../TabDrawer.vue'

const mockPush = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush }),
}))

describe('TabDrawer', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    mockPush.mockClear()
  })

  it('renders nothing when no tabs are open', () => {
    const wrapper = mount(TabDrawer)
    expect(wrapper.find('.tab-drawer-trigger').exists()).toBe(false)
  })

  it('renders trigger strip and tabs when tabs are open', () => {
    const store = useTabStore()
    store.openTab({ path: '/edit/abc', params: { id: 'abc' } })
    store.updateTab('/edit/abc', { title: 'My Draft' })
    store.openTab({ path: '/article/xyz', params: { id: 'xyz' } })
    store.updateTab('/article/xyz', { title: 'A Great Paper' })

    const wrapper = mount(TabDrawer)
    expect(wrapper.find('.tab-drawer-trigger').exists()).toBe(true)
    const tabItems = wrapper.findAll('.tab-drawer-item')
    expect(tabItems).toHaveLength(2)
    expect(tabItems[0].text()).toContain('My Draft')
    expect(tabItems[1].text()).toContain('A Great Paper')
  })

  it('highlights the active tab', () => {
    const store = useTabStore()
    store.openTab({ path: '/edit/a', params: { id: 'a' } })
    store.openTab({ path: '/edit/b', params: { id: 'b' } })
    store.activateTab('/edit/a')

    const wrapper = mount(TabDrawer)
    const items = wrapper.findAll('.tab-drawer-item')
    expect(items[0].classes()).toContain('tab-drawer-item--active')
    expect(items[1].classes()).not.toContain('tab-drawer-item--active')
  })

  it('shows dirty dot on dirty editor tabs', () => {
    const store = useTabStore()
    store.openTab({ path: '/edit/abc', params: { id: 'abc' } })
    store.updateTab('/edit/abc', { dirty: true })

    const wrapper = mount(TabDrawer)
    expect(wrapper.find('.tab-drawer-dirty-dot').exists()).toBe(true)
  })

  it('emits close-tab when close button is clicked', async () => {
    const store = useTabStore()
    store.openTab({ path: '/edit/abc', params: { id: 'abc' } })

    const wrapper = mount(TabDrawer)
    // Expand drawer first (trigger mouseenter)
    await wrapper.find('.tab-drawer-trigger').trigger('mouseenter')
    await wrapper.vm.$nextTick()

    const closeBtn = wrapper.find('.tab-drawer-close-btn')
    expect(closeBtn.exists()).toBe(true)
    await closeBtn.trigger('click')
    expect(wrapper.emitted('close-tab')).toBeTruthy()
    expect(wrapper.emitted('close-tab')![0]).toEqual(['/edit/abc'])
  })
})
```

- [ ] **Step 2: Write the minimal component to pass tests**

Create `frontend/src/components/TabDrawer.vue`:

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { useTabStore } from '../stores/useTabStore'
import { Edit, Eye, X } from 'lucide-vue-next'

const tabStore = useTabStore()
const expanded = ref(false)
let collapseTimer: ReturnType<typeof setTimeout> | null = null

const emit = defineEmits<{
  (e: 'close-tab', tabId: string): void
}>()

function onTriggerEnter() {
  if (collapseTimer) { clearTimeout(collapseTimer); collapseTimer = null }
  expanded.value = true
}

function onDrawerLeave() {
  collapseTimer = setTimeout(() => { expanded.value = false }, 200)
}

function onDrawerEnter() {
  if (collapseTimer) { clearTimeout(collapseTimer); collapseTimer = null }
}

function iconComponent(icon: 'edit' | 'eye') {
  return icon === 'edit' ? Edit : Eye
}
</script>

<template>
  <div v-if="tabStore.tabs.length > 0" class="tab-drawer-container">
    <!-- Collapsed trigger strip -->
    <div
      class="tab-drawer-trigger"
      @mouseenter="onTriggerEnter"
    />

    <!-- Expanded drawer overlay -->
    <Transition name="drawer-slide">
      <div
        v-if="expanded"
        class="tab-drawer-panel"
        @mouseenter="onDrawerEnter"
        @mouseleave="onDrawerLeave"
      >
        <!-- Header -->
        <div class="tab-drawer-header">
          <span class="tab-drawer-header-title">Open Tabs</span>
          <span class="tab-drawer-header-count">{{ tabStore.tabs.length }}</span>
        </div>

        <!-- Tab list -->
        <div class="tab-drawer-list">
          <button
            v-for="tab in tabStore.tabs"
            :key="tab.id"
            class="tab-drawer-item"
            :class="{ 'tab-drawer-item--active': tab.id === tabStore.activeTabId }"
            @click="tabStore.activateTab(tab.id)"
          >
            <component :is="iconComponent(tab.icon)" class="tab-drawer-item-icon" :size="16" stroke-width="2" />
            <span class="tab-drawer-item-title">{{ tab.title }}</span>
            <span v-if="tab.dirty" class="tab-drawer-dirty-dot" />
            <button
              class="tab-drawer-close-btn"
              @click.stop="emit('close-tab', tab.id)"
            >
              <X :size="14" stroke-width="2" />
            </button>
          </button>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.tab-drawer-container {
  position: relative;
  z-index: 40;
}

.tab-drawer-trigger {
  position: fixed;
  left: 0;
  top: 4rem; /* below NavBar (~3rem + spacing) */
  bottom: 0;
  width: 4px;
  background: transparent;
  transition: background-color 150ms ease;
  cursor: default;
  z-index: 41;
}
.tab-drawer-trigger:hover {
  background-color: rgba(88, 166, 255, 0.3); /* accent/30 */
}

.tab-drawer-panel {
  position: fixed;
  left: 0;
  top: 4rem;
  bottom: 0;
  width: 220px;
  background-color: #161b22; /* bg-card */
  border-right: 1px solid #30363d; /* border-divider */
  box-shadow: 4px 0 16px rgba(0, 0, 0, 0.4);
  z-index: 42;
  display: flex;
  flex-direction: column;
}

.tab-drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 12px 8px;
  border-bottom: 1px solid #30363d;
}
.tab-drawer-header-title {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #8b949e; /* text-ink-muted */
}
.tab-drawer-header-count {
  font-size: 11px;
  font-weight: 600;
  color: #8b949e;
  background: #21262d;
  border-radius: 9999px;
  padding: 1px 6px;
}

.tab-drawer-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}

.tab-drawer-item {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 6px 8px 6px 8px;
  background: transparent;
  border: none;
  border-left: 2px solid transparent;
  color: #8b949e;
  font-size: 13px;
  cursor: pointer;
  transition: background-color 100ms ease, color 100ms ease;
  text-align: left;
}
.tab-drawer-item:hover {
  background-color: #21262d;
  color: #e6edf3; /* text-ink */
}
.tab-drawer-item--active {
  background-color: rgba(88, 166, 255, 0.12); /* bg-accent/15 via hex for clarity */
  border-left-color: #58a6ff; /* accent */
  color: #e6edf3;
}
.tab-drawer-item--active:hover {
  background-color: rgba(88, 166, 255, 0.18);
}

.tab-drawer-item-icon {
  flex-shrink: 0;
  opacity: 0.7;
}

.tab-drawer-item-title {
  flex: 1;
  min-width: 0;
  line-height: 1.4;
  word-break: break-word;
}

.tab-drawer-dirty-dot {
  flex-shrink: 0;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #58a6ff; /* accent */
}

.tab-drawer-close-btn {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: inherit;
  cursor: pointer;
  opacity: 0;
  transition: opacity 100ms ease;
}
.tab-drawer-item:hover .tab-drawer-close-btn {
  opacity: 1;
}
.tab-drawer-close-btn:hover {
  background-color: rgba(255, 255, 255, 0.1);
}

/* Transition */
.drawer-slide-enter-active,
.drawer-slide-leave-active {
  transition: transform 150ms ease;
}
.drawer-slide-enter-from,
.drawer-slide-leave-to {
  transform: translateX(-100%);
}
</style>
```

- [ ] **Step 3: Run tests, verify they pass**

```bash
cd frontend && npx vitest run src/components/__tests__/TabDrawer.test.ts
```

Expected: 5 tests pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/TabDrawer.vue frontend/src/components/__tests__/TabDrawer.test.ts
git commit -m "feat: add TabDrawer component - left sidebar overlay with hover expand
Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Integrate into App.vue

**Files:**
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/main.ts` (register navigation guard)

- [ ] **Step 1: Update App.vue template and script**

The existing `App.vue` template:

```vue
<template>
  <div id="app" class="min-h-screen bg-page flex flex-col">
    <NavBar />
    <main
      :class="isEditorPage
        ? 'flex-1 w-full px-2 pt-24 pb-2'
        : 'flex-1 w-full max-w-content mx-auto px-4 sm:px-6 lg:px-8 pt-24 pb-12'"
    >
      <router-view v-slot="{ Component, route }">
        <keep-alive include="EditorPage">
          <component :is="Component" :key="route.path" />
        </keep-alive>
      </router-view>
    </main>
    <AuthModal />
  </div>
</template>
```

Script changes: import TabDrawer, import useTabStore, add tabStore.restoreTabs() to onMounted, add router.afterEach for auto-tab registration.

New `App.vue` script:

```typescript
<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import NavBar from './components/NavBar.vue'
import AuthModal from './components/AuthModal.vue'
import TabDrawer from './components/TabDrawer.vue'
import { useUserStore } from './stores/useUserStore'
import { useTabStore } from './stores/useTabStore'
import { loadString, remove } from './composables/useLocalStorage'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const tabStore = useTabStore()

const isEditorPage = computed(() => route.path.startsWith('/edit'))

// Auto-register tabs on navigation
router.afterEach((to) => {
  if (to.path.startsWith('/edit') || to.path.startsWith('/article') || to.path.startsWith('/articles')) {
    tabStore.openTab({ path: to.path, params: to.params as Record<string, string> })
  }
})

// Handle close-tab event from TabDrawer
function onCloseTab(tabId: string) {
  const result = tabStore.closeTab(tabId)
  if (result.shouldPrompt) {
    // Navigate to the dirty tab first so EditorPage can show the confirm dialog
    tabStore.activeTabId = tabId
    router.push(tabId)
    // EditorPage watches pendingCloseTabId to trigger the confirm dialog (see Task 4)
  }
}

// Restore session and tabs on mount
onMounted(async () => {
  await userStore.restoreSession()
  tabStore.restoreTabs()
  // Check if we should show auth modal (set by router guard)
  if (loadString('showAuthModal') === 'true') {
    remove('showAuthModal')
    userStore.showAuthModal = true
  }
})
</script>
```

New template:

```vue
<template>
  <div id="app" class="min-h-screen bg-page flex flex-col">
    <NavBar />
    <div class="flex-1 relative">
      <TabDrawer @close-tab="onCloseTab" />
      <main
        :class="isEditorPage
          ? 'w-full px-2 pt-24 pb-2'
          : 'w-full max-w-content mx-auto px-4 sm:px-6 lg:px-8 pt-24 pb-12'"
      >
        <router-view v-slot="{ Component, route }">
          <keep-alive :include="['EditorPage', 'ArticlePage']">
            <component :is="Component" :key="route.path" />
          </keep-alive>
        </router-view>
      </main>
    </div>
    <AuthModal />
  </div>
</template>
```

Key changes:
1. Wrapped `<main>` in a `<div class="flex-1 relative">` — provides positioning context for the fixed drawer
2. Added `<TabDrawer @close-tab="onCloseTab" />` before `<main>`
3. Changed `KeepAlive` include from `"EditorPage"` to `["EditorPage", "ArticlePage"]`
4. Added `router.afterEach` to auto-register tabs for `/edit`, `/article`, `/articles` routes
5. Added `tabStore.restoreTabs()` in `onMounted`
6. `isEditorPage` layout now uses `w-full` without `flex-1` (flex-1 is on the parent wrapper)

- [ ] **Step 2: Update App.test.ts**

Read the existing test, then add tests for the tab integration:

```bash
cd frontend && npx vitest run src/__tests__/App.test.ts
```

Since App.test.ts tests App.vue integration (NavBar, auth), update it to also verify TabDrawer renders when tabs are present and the KeepAlive include list includes ArticlePage. Add a mock for `useTabStore`:

```typescript
// Add to existing mocks in App.test.ts
vi.mock('@/stores/useTabStore', () => ({
  useTabStore: () => ({
    tabs: [{ id: '/edit/test', type: 'editor', title: 'Test', dirty: false, icon: 'edit' }],
    activeTabId: '/edit/test',
    openTab: vi.fn(),
    closeTab: vi.fn().mockReturnValue({ shouldPrompt: false, nextTabId: null }),
    removeTab: vi.fn(),
    activateTab: vi.fn(),
    updateTab: vi.fn(),
    restoreTabs: vi.fn(),
  }),
}))
```

Add test:

```typescript
it('renders TabDrawer when tabs are open', () => {
  const wrapper = mount(App, { ... })
  expect(wrapper.findComponent({ name: 'TabDrawer' }).exists()).toBe(true)
})
```

- [ ] **Step 3: Run full test suite to catch regressions**

```bash
cd frontend && npx vitest run
```

Expected: existing tests pass. New tab-related tests pass. No regressions.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.vue frontend/src/__tests__/App.test.ts
git commit -m "feat: integrate TabDrawer into App.vue with auto-tab registration
Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Wire EditorPage to tab system

**Files:**
- Modify: `frontend/src/pages/EditorPage.vue`

- [ ] **Step 1: Read current EditorPage.vue to identify exact insertion points**

The file is at `frontend/src/pages/EditorPage.vue`. Key areas to modify:

1. **Import**: add `import { useTabStore } from '../stores/useTabStore'`
2. **Store init**: add `const tabStore = useTabStore()` after existing store declarations
3. **Register on mount**: in `onMounted`, add `tabStore.openTab({ path: route.path, params: route.params as Record<string, string> })`
4. **Sync dirty/title**: add a `watch` block after `isClean` definition

```typescript
// After line 74 (isClean computed), add:
// ── Tab integration ─────────────────────────────────────────────
const tabStore = useTabStore()

// Sync dirty state and title to tab store
watch([isClean, title], ([clean, t]) => {
  tabStore.updateTab(route.path, { dirty: !clean, title: t || 'Untitled' })
}, { immediate: true })

// Check for pending close request from TabDrawer
const pendingClose = ref(false)
watch(() => tabStore.pendingCloseTabId, (pendingId) => {
  if (pendingId === route.path) {
    pendingClose.value = true
  }
})
```

5. **Close confirmation UI**: Add a modal near the save button area. This shows when `pendingClose` is true:

In the template, add after the existing commit popup `<Transition>` block (around line 530, after the commit message popup closing tag):

```vue
<!-- Close confirmation dialog -->
<Transition name="slide-up">
  <div
    v-if="pendingClose"
    class="absolute top-full right-0 mt-2 z-50 bg-card border border-divider rounded-lg shadow-2xl p-4 w-72 animate-fade-in"
  >
    <p class="text-xs text-ink-muted mb-3">You have unsaved changes. Save before closing?</p>
    <div class="flex items-center gap-2">
      <button
        class="flex-1 text-xs text-ink-muted hover:text-ink hover:bg-[#21262d] rounded-lg py-1.5 transition-colors"
        @click="pendingClose = false; tabStore.clearPendingClose()"
      >Cancel</button>
      <button
        class="flex-1 text-xs text-[#d73a49] hover:bg-[#d73a49]/10 rounded-lg py-1.5 transition-colors"
        @click="pendingClose = false; tabStore.clearPendingClose(); tabStore.removeTab(route.path)"
      >Discard</button>
      <button
        class="flex-1 text-xs font-semibold bg-accent text-[#0d1117] rounded-lg py-1.5 hover:brightness-110 transition-all"
        @click="handleSaveAndClose"
      >Save &amp; Close</button>
    </div>
  </div>
</Transition>
```

6. **Save & Close handler**: Add this function:

```typescript
async function handleSaveAndClose() {
  await saveDraft()
  pendingClose.value = false
  tabStore.clearPendingClose()
  tabStore.removeTab(route.path)
}
```

This dialog is positioned relative to the toolbar (the parent div with the save button), similar to the commit popup.

- [ ] **Step 2: Update EditorPage test**

In `frontend/src/pages/__tests__/EditorPage.test.ts`, add:

1. Mock `useTabStore`:

```typescript
const mockTabOpenTab = vi.fn()
const mockTabUpdateTab = vi.fn()
const mockTabRemoveTab = vi.fn()
const mockTabCloseTab = vi.fn().mockReturnValue({ shouldPrompt: false, nextTabId: null })
const mockTabPendingCloseId = { value: null as string | null }

vi.mock('@/stores/useTabStore', () => ({
  useTabStore: () => ({
    tabs: [],
    activeTabId: { value: null },
    pendingCloseTabId: mockTabPendingCloseId,
    openTab: mockTabOpenTab,
    closeTab: mockTabCloseTab,
    removeTab: mockTabRemoveTab,
    activateTab: vi.fn(),
    updateTab: mockTabUpdateTab,
    clearPendingClose: vi.fn(),
    restoreTabs: vi.fn(),
  }),
}))
```

2. Add tests:

```typescript
it('registers tab on mount', async () => {
  mockRoute.params.id = 'test-article'
  mount(EditorPage, { ... })
  await flushPromises()
  expect(mockTabOpenTab).toHaveBeenCalled()
})

it('syncs dirty state to tab store', async () => {
  mockRoute.params.id = undefined
  const wrapper = mount(EditorPage, { ... })
  await flushPromises()
  // Initially clean
  expect(mockTabUpdateTab).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ dirty: false }))
})
```

- [ ] **Step 3: Run tests**

```bash
cd frontend && npx vitest run src/pages/__tests__/EditorPage.test.ts
```

Expected: All existing EditorPage tests pass + new tab tests pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/EditorPage.vue frontend/src/pages/__tests__/EditorPage.test.ts
git commit -m "feat: wire EditorPage to tab system - dirty sync + close confirmation
Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Wire ArticlePage to tab system

**Files:**
- Modify: `frontend/src/pages/ArticlePage.vue`

- [ ] **Step 1: Add tab registration and title sync**

Changes to `ArticlePage.vue` script:

1. **Import**: add `import { useTabStore } from '../stores/useTabStore'`
2. **Store init**: add `const tabStore = useTabStore()` after existing declarations (~line 33)
3. **Register on mount**: In `onMounted`, after `loadArticle`, add:

```typescript
// In the onMounted function, after loadArticle(id); loading.value = false:
tabStore.openTab({ path: route.path, params: route.params as Record<string, string> })
```

4. **Update title**: In the `loadArticle` function, after `article.value` is set and we have the title:

Add a `watch` on the article title:

```typescript
// After article load completes, sync title to tab store
watch(() => article.value?.title, (title) => {
  if (title) {
    tabStore.updateTab(route.path, { title })
  }
}, { immediate: true })
```

The exact insertion: after line ~40 (`const id = route.params.id as string`), add the tabStore line. After the `loadArticle` function definition, add the watch.

- [ ] **Step 2: Update ArticlePage test**

In `frontend/src/pages/__tests__/ArticlePage.test.ts`, add the mock:

```typescript
const mockTabOpenTab = vi.fn()
const mockTabUpdateTab = vi.fn()

vi.mock('@/stores/useTabStore', () => ({
  useTabStore: () => ({
    tabs: [],
    activeTabId: { value: null },
    pendingCloseTabId: { value: null },
    openTab: mockTabOpenTab,
    closeTab: vi.fn().mockReturnValue({ shouldPrompt: false, nextTabId: null }),
    removeTab: vi.fn(),
    activateTab: vi.fn(),
    updateTab: mockTabUpdateTab,
    clearPendingClose: vi.fn(),
    restoreTabs: vi.fn(),
  }),
}))
```

Add test:

```typescript
it('registers tab on mount and updates title', async () => {
  mount(ArticlePage, { ... })
  await flushPromises()
  expect(mockTabOpenTab).toHaveBeenCalled()
  expect(mockTabUpdateTab).toHaveBeenCalledWith(
    expect.any(String),
    expect.objectContaining({ title: 'A Study on Quantum Error Correction' })
  )
})
```

- [ ] **Step 3: Run tests**

```bash
cd frontend && npx vitest run src/pages/__tests__/ArticlePage.test.ts
```

Expected: All existing ArticlePage tests pass + new test passes.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ArticlePage.vue frontend/src/pages/__tests__/ArticlePage.test.ts
git commit -m "feat: wire ArticlePage to tab system - auto-register tab + title sync
Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Full integration test & manual verification

- [ ] **Step 1: Run the full test suite**

```bash
cd frontend && npx vitest run
```

Expected: All ~341 tests pass. Zero regressions.

- [ ] **Step 2: Start dev server and manually verify**

```bash
cd frontend && npm run dev
```

Manual test checklist (from design spec §11):

1. Open http://localhost:5173 → login → click "New Article" → type content → **verify**: left edge has a 4px subtle strip
2. Hover the strip → **verify**: drawer slides out showing "Untitled" tab with edit icon
3. Edit content → **verify**: blue dirty dot appears on the tab
4. Navigate to an article (click a link or search) → **verify**: article opens as a second tab in the drawer, URL changes
5. Switch back to the editor tab via the drawer → **verify**: content is preserved, dirty dot still visible
6. Close a clean article tab via × → **verify**: tab removes, adjacent tab activates
7. Close a dirty editor tab via × → **verify**: confirmation dialog appears → click "Discard" → tab closes
8. Open editor tab again, edit, close via × → click "Save & Close" → **verify**: draft saved, tab closes
9. Open 3 tabs → refresh browser → **verify**: all 3 tabs restored (dirty dots reset, content loaded from persistence)
10. Navigate to home page → **verify**: drawer stays visible with tabs, no tab highlighted as active

- [ ] **Step 3: Commit any final adjustments**

```bash
git add -A && git commit -m "chore: final integration adjustments for tab system
Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```
