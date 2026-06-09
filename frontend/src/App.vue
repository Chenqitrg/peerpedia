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
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
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

// ── Tab auto-registration ──────────────────────────────────────

router.afterEach((to) => {
  if (to.path.startsWith('/edit') || to.path.startsWith('/article') || to.path.startsWith('/articles')) {
    // Pass fullPath so editor tabs with different ?new=1&_t=X get unique ids.
    // Article paths get normalized: /articles/foo → /article/foo.
    const rawPath = to.fullPath
    tabStore.openTab(rawPath)
  }
})

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

  // Navigate to the dirty tab so its EditorPage instance becomes active
  tabStore.activeTabId = tabId
  await router.push(tabId)
  await nextTick()

  // Dispatch save event — EditorPage listens and calls handleSaveDraft(),
  // which opens the commit dialog (Tauri) or saves directly (web).
  window.dispatchEvent(new CustomEvent('tab-save-and-close', { detail: { tabId } }))

  // Watch for save completion — when dirty becomes false, close the tab
  const unwatch = watch(() => {
    const tab = tabStore.tabs.find(t => t.id === tabId)
    if (tab && !tab.dirty) {
      tabStore.removeTab(tabId)
      closingTabId.value = null
      unwatch()
    }
  })
}

// ── Restore session and tabs on mount ──────────────────────────

onMounted(async () => {
  await userStore.restoreSession()
  tabStore.restoreTabs()
  if (loadString('showAuthModal') === 'true') {
    remove('showAuthModal')
    userStore.showAuthModal = true
  }
})
</script>
