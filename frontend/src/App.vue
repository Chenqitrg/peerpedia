<template>
  <div id="app" class="min-h-screen bg-page flex flex-col">
    <NavBar />
    <main
      :class="isEditorPage
        ? 'flex-1 w-full px-2 pt-24 pb-2'
        : 'flex-1 w-full max-w-content mx-auto px-4 sm:px-6 lg:px-8 pt-24 pb-12'"
    >
      <router-view />
    </main>
    <AuthModal />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import NavBar from './components/NavBar.vue'
import AuthModal from './components/AuthModal.vue'
import { useUserStore } from './stores/useUserStore'
import { loadString, remove } from './composables/useLocalStorage'

const route = useRoute()
const userStore = useUserStore()

const isEditorPage = computed(() => route.path.startsWith('/edit'))

// Restore session on app mount
onMounted(async () => {
  await userStore.restoreSession()
  // Check if we should show auth modal (set by router guard)
  if (loadString('showAuthModal') === 'true') {
    remove('showAuthModal')
    userStore.showAuthModal = true
  }
})
</script>
