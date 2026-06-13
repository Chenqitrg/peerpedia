<!-- SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors -->
<!-- SPDX-License-Identifier: CC-BY-NC-SA-4.0 -->

<template>
  <div id="app" class="min-h-screen bg-page flex flex-col">
    <NavBar />
    <!-- Server sync error banner -->
    <div
      v-if="userStore.syncError"
      class="fixed top-16 left-1/2 -translate-x-1/2 z-50
             bg-[#d73a49]/10 border border-[#d73a49]/30 rounded-lg px-4 py-2
             text-sm text-[#d73a49] max-w-content w-[calc(100%-2rem)]"
    >
      {{ userStore.syncError }}
      <button class="ml-2 text-ink-muted hover:text-ink" @click="userStore.syncError = null">✕</button>
    </div>
    <div class="flex-1 relative">
      <TabDrawer @close-tab="onCloseTab" />
      <main
        :class="isEditorPage
          ? 'w-full px-2 pt-24 pb-2'
          : 'w-full max-w-content mx-auto px-4 sm:px-6 lg:px-8 pt-24 pb-12'"
      >
        <router-view v-slot="{ Component, route }">
          <keep-alive :include="['EditorPage', 'ArticlePage']" :key="'ka-' + keepAliveVersion">
            <component :is="Component" :key="route.fullPath" />
          </keep-alive>
        </router-view>
      </main>
    </div>

    <!-- Close confirmation dialog (shown when closing a dirty tab) -->
    <Transition name="slide-up">
      <div
        v-if="showCloseDialog"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
        @click.self="cancelClose"
      >
        <div class="bg-card border border-divider rounded-lg shadow-2xl p-5 w-80 animate-fade-in">
          <p class="text-sm text-ink mb-4">You have unsaved changes. Save before closing?</p>
          <div class="flex items-center gap-2">
            <button class="flex-1 text-xs text-ink-muted hover:text-ink hover:bg-[#21262d] rounded-lg py-2 transition-colors" @click="cancelClose">Cancel</button>
            <button class="flex-1 text-xs text-[#d73a49] hover:bg-[#d73a49]/10 rounded-lg py-2 transition-colors" @click="discardClose">Discard</button>
            <button class="flex-1 text-xs font-semibold bg-accent text-[#0d1117] rounded-lg py-2 hover:brightness-110 transition-all" @click="saveAndClose">Save &amp; Close</button>
          </div>
        </div>
      </div>
    </Transition>

    <AuthModal />
    <ReconnectDialog
      v-if="showReconnect"
      :items="pendingOps"
      @resolve="onResolvePending"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import NavBar from './components/NavBar.vue'
import AuthModal from './components/AuthModal.vue'
import TabDrawer from './components/TabDrawer.vue'
import ReconnectDialog from './components/ReconnectDialog.vue'
import { useUserStore } from './stores/useUserStore'
import { useArticleStore } from './stores/useArticleStore'
import { useTabStore } from './stores/useTabStore'
import { deleteArticle } from './api/articles'
import { loadString, remove } from './composables/useLocalStorage'
import { useNetworkStatus } from './composables/useNetworkStatus'
import { useTauri } from './composables/useTauri'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const tabStore = useTabStore()
const { ping, isSynced } = useNetworkStatus()

const isEditorPage = computed(() => route.path.startsWith('/edit'))

// KeepAlive cache version — bumped when navigating to a tab-tracked page
// with no open tabs. This clears stale cached instances (from previously
// closed tabs) before the new page's ensureTab creates a fresh tab.
const keepAliveVersion = ref(0)
const isTabRoute = (p: string) =>
  p.startsWith('/edit') || p.startsWith('/article') || p.startsWith('/articles')
router.beforeEach((to, from) => {
  if (isTabRoute(to.path) && tabStore.tabs.length === 0) {
    keepAliveVersion.value++
  }
})

// ── Tab activation on navigation ──────────────────────────────
// Tab creation is handled by each page component (ensureTab in setup).

router.afterEach((to) => {
  if (to.path.startsWith('/edit') || to.path.startsWith('/article') || to.path.startsWith('/articles')) {
    // Pass fullPath so editor tabs with different ?new=1&_t=X get unique ids.
    // Article paths get normalized: /articles/foo → /article/foo.
    tabStore.activateTabByRoute(to.fullPath)
  }
})

// ── L4: Auto-sync local account to server when network or login state changes ──
watch(
  [isSynced, () => userStore.localToken, () => userStore.hasPendingCreds],
  ([online, localTok, pending]) => {
    console.log('[App] isSynced:', online, 'localToken:', !!localTok, 'pendingCreds:', pending)
    if (online && (localTok || pending)) {
      console.log('[App] calling trySyncServerAuth')
      userStore.trySyncServerAuth()
    }
  },
  { immediate: true },
)

// ── Reconnect: check pending ops when network comes back ─────────
const tauri = useTauri()
const pendingOps = ref<{ id: string; title: string; op_type: string; updated_at: string; offline_since?: string | null }[]>([])
const showReconnect = ref(false)

watch(isSynced, async (online) => {
  if (!online || !tauri.isTauri.value) return
  const ops = await tauri.getPendingOps({ account_id: userStore.viewer?.id || 'local' })
  if (ops && Array.isArray(ops) && !('error' in ops) && ops.length > 0) {
    pendingOps.value = ops
    showReconnect.value = true
  }
})

const articleStore = useArticleStore()

async function onResolvePending(id: string, action: 'push' | 'discard' | 'confirm_delete' | 'restore') {
  const draft = await tauri.getDraft({ id })
  if (action === 'push') {
    if (draft && !('error' in draft)) {
      try {
        await articleStore.createArticle({
          id: draft.id,
          title: draft.title,
          content: draft.content,
          format: (draft.format as 'markdown' | 'typst') || 'markdown',
          commit_message: 'Offline save',
          self_review: { originality: 3, rigor: 3, completeness: 3, pedagogy: 3, impact: 3 },
        })
      } catch (e: unknown) { console.warn('Push failed:', e) }
    }
  } else if (action === 'confirm_delete') {
    try { await deleteArticle(id) } catch (e: unknown) { console.warn('Delete failed:', e) }
    try { await tauri.deleteArticle({ id, account_id: userStore.viewer?.id || 'local' }) } catch { /* best-effort */ }
  } else if (action === 'discard') {
    // Discard: remove local draft + git repo, no server push.
    try { await tauri.deleteArticle({ id, account_id: userStore.viewer?.id || 'local' }) } catch { /* best-effort */ }
  }
  // restore: just clear the pending marker, keep data
  await tauri.clearPending({ id })
  pendingOps.value = pendingOps.value.filter(o => o.id !== id)
  if (pendingOps.value.length === 0) showReconnect.value = false
}

// ── Close confirmation dialog (dirty tabs) ─────────────────────

const showCloseDialog = ref(false)
const closingTabId = ref<string | null>(null)

function onCloseTab(tabId: string) {
  const result = tabStore.closeTab(tabId)
  if (result.shouldPrompt) {
    closingTabId.value = tabId
    showCloseDialog.value = true
  }
}

function cancelClose() {
  showCloseDialog.value = false
  closingTabId.value = null
}

function discardClose() {
  showCloseDialog.value = false
  if (closingTabId.value) tabStore.removeTab(closingTabId.value)
  closingTabId.value = null
}

async function saveAndClose() {
  showCloseDialog.value = false
  const tabId = closingTabId.value
  if (!tabId) return

  // Navigate to the dirty tab so its EditorPage instance becomes active.
  // Must use tab.routePath — tabId is a UUID, not a URL path.
  const tab = tabStore.findById(tabId)
  if (!tab) { closingTabId.value = null; return }
  tabStore.activeTabId = tabId
  await router.push(tab.routePath)
  await nextTick()

  // Dispatch save event — EditorPage listens and calls handleSaveDraft(),
  // which opens the commit dialog (Tauri) or saves directly (web).
  window.dispatchEvent(new CustomEvent('tab-save-and-close', { detail: { tabId } }))

  // Watch for save completion — when dirty becomes false, close the tab
  const unwatch = watch(
    () => tabStore.tabs.find(t => t.id === tabId)?.dirty,
    (dirty) => {
      if (dirty === false) {
        tabStore.removeTab(tabId)
        closingTabId.value = null
        unwatch()
      }
    },
  )
}

// ── Restore session and tabs on mount ──────────────────────────

onMounted(async () => {
  ping()
  await userStore.restoreSession()
  tabStore.restoreTabs()
  if (loadString('showAuthModal') === 'true') {
    remove('showAuthModal')
    userStore.showAuthModal = true
  }
})
</script>
