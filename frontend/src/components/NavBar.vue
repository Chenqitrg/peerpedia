<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/useUserStore'
import {
  Bookmark,
  BookOpen,
  FilePlus,
  Search,
  User,
  LogIn,
  LogOut,
} from 'lucide-vue-next'

const router = useRouter()
const userStore = useUserStore()
const searchQuery = ref('')
const mobileOpen = ref(false)

const isLoggedIn = computed(() => !!userStore.viewer)

function toggle() {
  mobileOpen.value = !mobileOpen.value
}

function close() {
  mobileOpen.value = false
}

function handleSearch(e: Event) {
  e.preventDefault()
  if (searchQuery.value.trim()) {
    router.push(`/search?q=${encodeURIComponent(searchQuery.value.trim())}`)
    searchQuery.value = ''
    close()
  }
}

function goToProfile() {
  if (userStore.viewer) {
    router.push(`/user/${userStore.viewer.id}`)
  } else {
    // Prompt to create/login user
    router.push('/')
  }
  close()
}
</script>

<template>
  <nav
    class="fixed top-4 left-1/2 -translate-x-1/2 z-50
           w-[calc(100%-2rem)] max-w-content
           bg-card/80 backdrop-blur-xl
           border border-divider
           rounded-xl shadow-lg shadow-black/20"
    role="navigation"
    aria-label="Main navigation"
  >
    <div class="flex items-center justify-between h-12 px-4">
      <!-- Brand -->
      <router-link
        to="/"
        class="flex items-center gap-2 text-base font-heading font-bold text-ink hover:text-ink transition-colors duration-200 no-underline shrink-0"
        @click="close"
      >
        <BookOpen class="w-4 h-4 text-accent" stroke-width="2" />
        <span class="hidden sm:inline">PeerPedia</span>
      </router-link>

      <!-- Search (desktop) -->
      <form
        class="hidden md:flex items-center flex-1 max-w-md mx-4"
        @submit="handleSearch"
      >
        <div class="relative w-full">
          <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-ink-muted pointer-events-none" stroke-width="2" />
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Search articles..."
            class="w-full pl-9 pr-3 py-1.5 text-xs
                   bg-[#0d1117] border border-divider rounded-lg
                   text-ink placeholder:text-ink-muted
                   focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent
                   transition-colors duration-200"
          />
        </div>
      </form>

      <!-- Actions -->
      <div class="flex items-center gap-1">
        <router-link
          to="/bookmarks"
          class="flex items-center justify-center w-8 h-8 rounded-lg
                 text-ink-muted hover:text-ink hover:bg-[#21262d]
                 transition-colors duration-200"
          aria-label="Bookmarks"
          @click="close"
        >
          <Bookmark class="w-4 h-4" stroke-width="2" />
        </router-link>

        <button
          class="flex items-center justify-center w-8 h-8 rounded-lg
                 text-ink-muted hover:text-ink hover:bg-[#21262d]
                 transition-colors duration-200"
          aria-label="Profile"
          @click="goToProfile"
        >
          <User class="w-4 h-4" stroke-width="2" />
        </button>

        <router-link
          to="/edit"
          class="flex items-center justify-center w-8 h-8 rounded-lg
                 text-ink-muted hover:text-ink hover:bg-[#21262d]
                 transition-colors duration-200"
          aria-label="New Article"
          @click="close"
        >
          <FilePlus class="w-4 h-4" stroke-width="2" />
        </router-link>

        <router-link
          to="/pool"
          class="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 ml-1
                 text-xs font-semibold text-accent
                 border border-accent/30 rounded-lg
                 hover:bg-accent/10 transition-colors duration-200 no-underline"
          @click="close"
        >
          Pool
        </router-link>

        <!-- Mobile hamburger -->
        <button
          class="md:hidden flex items-center justify-center w-8 h-8 rounded-lg
                 text-ink-muted hover:text-ink hover:bg-[#21262d]
                 transition-colors duration-200 ml-1"
          :aria-expanded="mobileOpen"
          aria-label="Toggle navigation menu"
          @click="toggle"
        >
          <svg v-if="!mobileOpen" class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
          <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>

    <!-- Mobile menu -->
    <div
      v-if="mobileOpen"
      class="md:hidden border-t border-divider px-4 py-3 flex flex-col gap-2 animate-slide-up"
    >
      <form @submit="handleSearch" class="mb-2">
        <div class="relative w-full">
          <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-ink-muted pointer-events-none" stroke-width="2" />
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Search articles..."
            class="w-full pl-9 pr-3 py-2 text-sm
                   bg-[#0d1117] border border-divider rounded-lg
                   text-ink placeholder:text-ink-muted
                   focus:outline-none focus:ring-1 focus:ring-accent"
          />
        </div>
      </form>
      <router-link to="/" class="nav-link-mobile" @click="close">Home</router-link>
      <router-link to="/pool" class="nav-link-mobile" @click="close">Pool</router-link>
      <router-link to="/bookmarks" class="nav-link-mobile" @click="close">Bookmarks</router-link>
      <router-link to="/edit" class="nav-link-mobile" @click="close">New Article</router-link>
      <button
        v-if="userStore.viewer"
        class="nav-link-mobile text-left"
        @click="goToProfile"
      >
        Profile
      </button>
    </div>
  </nav>
</template>

<style scoped>
.nav-link-mobile {
  @apply block px-4 py-2.5 text-sm font-semibold text-ink-muted
         hover:text-ink hover:bg-[#21262d] rounded-lg
         transition-colors duration-200
         no-underline;
}
</style>
