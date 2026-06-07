<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '../stores/useUserStore'
import { useTauri } from '../composables/useTauri'
import { useOffline } from '../composables/useOffline'
import { saveString } from '../composables/useLocalStorage'
import {
  Bookmark,
  Waypoints,
  FilePlus,
  Search,
  User,
  ChevronDown,
  Wifi,
  WifiOff,
  Landmark,
  Waves,
} from 'lucide-vue-next'

const router = useRouter()
const userStore = useUserStore()
const tauri = useTauri()
const { canRead } = useOffline()
const { t, locale } = useI18n()
const searchQuery = ref('')
const mobileOpen = ref(false)
const avatarPopover = ref(false)
const avatarRef = ref<HTMLElement | null>(null)

// Close popover on outside click.
function onDocClick(e: MouseEvent) {
  if (avatarRef.value && !avatarRef.value.contains(e.target as Node)) {
    avatarPopover.value = false
  }
}
onMounted(() => document.addEventListener('click', onDocClick))
onUnmounted(() => document.removeEventListener('click', onDocClick))

const isLoggedIn = computed(() => !!userStore.viewer)

// Connection status: Tauri/dev-mock=local, Web=online/offline
const connectionStatus = computed(() => {
  if (tauri.isTauri.value || tauri.isBrowserLocal.value) return 'local'
  if (userStore.viewer) return 'online'
  return 'offline'
})

function toggleLocale() {
  locale.value = locale.value === 'zh-CN' ? 'en-US' : 'zh-CN'
  saveString('locale', locale.value)
}

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

function openAuth() {
  userStore.showAuthModal = true
}

function goToProfile() {
  avatarPopover.value = false
  router.push(`/user/${userStore.viewer!.id}`)
}

function handleLogout() {
  avatarPopover.value = false
  userStore.logout()
  router.push('/')
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
        class="flex items-center gap-1.5 text-sm font-heading font-bold text-ink hover:text-ink transition-colors duration-200 no-underline shrink-0"
        @click="close"
      >
        <Waypoints class="w-3.5 h-3.5 text-accent" stroke-width="1.5" />
        <span class="hidden sm:inline brand-logo text-sm">{{ t('nav.brand') }}</span>
      </router-link>

      <!-- Search (desktop) — only when logged in -->
      <form
        v-if="isLoggedIn"
        class="hidden md:flex items-center flex-1 max-w-md mx-4"
        @submit="handleSearch"
      >
        <div class="relative w-full">
          <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-ink-muted pointer-events-none" stroke-width="2" />
          <input
            v-model="searchQuery"
            type="text"
            :placeholder="t('nav.searchPlaceholder')"
            class="w-full pl-9 pr-3 py-1.5 text-xs
                   bg-[#0d1117] border border-divider rounded-lg
                   text-ink placeholder:text-ink-muted
                   focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent
                   transition-colors duration-200"
          />
        </div>
      </form>

<!-- Actions — logged in -->
      <div v-if="isLoggedIn" class="flex items-center gap-1">
        <!-- Connection status -->
        <span
          class="flex items-center justify-center w-8 h-8 rounded-lg"
          :class="{
            'text-green-500': connectionStatus === 'online',
            'text-ink-muted': connectionStatus === 'offline' || connectionStatus === 'local',
          }"
          :title="connectionStatus === 'local' ? 'Local mode' : connectionStatus === 'online' ? 'Connected' : 'Offline'"
        >
          <Wifi v-if="connectionStatus === 'online'" class="w-4 h-4" stroke-width="2" />
          <WifiOff v-else class="w-4 h-4" stroke-width="2" />
        </span>
        <!-- Language toggle -->
        <button
          class="flex items-center justify-center w-8 h-8 rounded-lg
                 text-xs font-semibold
                 text-ink-muted hover:text-ink hover:bg-[#21262d]
                 transition-colors duration-200"
          :aria-label="locale === 'zh-CN' ? 'Switch to English' : '切换到中文'"
          @click="toggleLocale"
        >
          {{ locale === 'zh-CN' ? 'EN' : '中' }}
        </button>

        <router-link
          to="/bookmarks"
          class="flex items-center justify-center w-8 h-8 rounded-lg
                 text-ink-muted hover:text-ink hover:bg-[#21262d]
                 transition-colors duration-200"
          :aria-label="t('nav.bookmarks')"
          @click="close"
        >
          <Bookmark class="w-4 h-4" stroke-width="2" />
        </router-link>

        <router-link
          to="/edit"
          class="flex items-center justify-center w-8 h-8 rounded-lg
                 text-ink-muted hover:text-ink hover:bg-[#21262d]
                 transition-colors duration-200"
          :aria-label="t('nav.newArticle')"
          @click="close"
        >
          <FilePlus class="w-4 h-4" stroke-width="2" />
        </router-link>

        <router-link
          v-if="canRead('schools')"
          to="/schools"
          class="flex items-center justify-center w-8 h-8 rounded-lg
                 text-ink-muted hover:text-ink hover:bg-[#21262d]
                 transition-colors duration-200"
          :aria-label="t('nav.schools')"
          :title="t('nav.schools')"
          @click="close"
        >
          <Landmark class="w-4 h-4" stroke-width="2" />
        </router-link>
        <span
          v-else
          class="flex items-center justify-center w-8 h-8 rounded-lg
                 text-ink-muted/30 cursor-not-allowed"
          :title="t('nav.schools') + ' — offline'"
        >
          <Landmark class="w-4 h-4" stroke-width="2" />
        </span>

        <router-link
          v-if="canRead('pool')"
          to="/pool"
          class="flex items-center justify-center w-8 h-8 rounded-lg
                 text-accent hover:text-accent hover:bg-accent/10
                 transition-colors duration-200"
          :aria-label="t('nav.pool')"
          :title="t('nav.pool')"
          @click="close"
        >
          <Waves class="w-4 h-4" stroke-width="2" />
        </router-link>
        <span
          v-else
          class="flex items-center justify-center w-8 h-8 rounded-lg
                 text-accent/30 cursor-not-allowed"
          :title="t('nav.pool') + ' — offline'"
        >
          <Waves class="w-4 h-4" stroke-width="2" />
        </span>

        <!-- Avatar + popover (ref on container includes both button and dropdown) -->
        <div ref="avatarRef" class="relative ml-1">
          <button
            class="flex items-center gap-1 px-1.5 py-1 rounded-lg
                   text-ink-muted hover:text-ink hover:bg-[#21262d]
                   transition-colors duration-200"
            @click="avatarPopover = !avatarPopover"
          >
            <User class="w-4 h-4" stroke-width="2" />
            <ChevronDown class="w-3 h-3" stroke-width="2" />
          </button>

          <!-- Popover -->
          <div
            v-if="avatarPopover"
            class="absolute right-0 top-full mt-2 w-48 bg-card border border-divider rounded-xl shadow-xl py-1 animate-fade-in"
          >
            <div class="px-4 py-2 text-sm text-ink border-b border-divider">
              {{ userStore.viewer?.username || userStore.viewer?.name }}
            </div>
            <button
              class="w-full text-left px-4 py-2 text-sm text-ink-muted hover:text-ink hover:bg-[#21262d] transition-colors"
              @click="goToProfile"
            >
              {{ t('nav.profile') }}
            </button>
            <button
              class="w-full text-left px-4 py-2 text-sm text-ink-muted hover:text-ink hover:bg-[#21262d] transition-colors"
              @click="handleLogout"
            >
              {{ t('nav.logout') }}
            </button>
          </div>
        </div>

        <!-- Mobile hamburger -->
        <button
          class="md:hidden flex items-center justify-center w-8 h-8 rounded-lg
                 text-ink-muted hover:text-ink hover:bg-[#21262d]
                 transition-colors duration-200 ml-1"
          :aria-expanded="mobileOpen"
          :aria-label="t('nav.toggleMenu')"
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

      <!-- Actions — not logged in -->
      <div v-else class="flex items-center gap-1">
        <!-- Language toggle -->
        <button
          class="flex items-center justify-center w-8 h-8 rounded-lg
                 text-xs font-semibold
                 text-ink-muted hover:text-ink hover:bg-[#21262d]
                 transition-colors duration-200"
          :aria-label="locale === 'zh-CN' ? 'Switch to English' : '切换到中文'"
          @click="toggleLocale"
        >
          {{ locale === 'zh-CN' ? 'EN' : '中' }}
        </button>
        <button
          class="flex items-center gap-1.5 px-4 py-1.5 text-sm font-semibold
                 bg-accent text-[#0d1117] rounded-lg
                 hover:brightness-110 transition-all duration-200"
          @click="openAuth"
        >
          {{ t('nav.signIn') }}
        </button>
      </div>
    </div>

    <!-- Mobile menu -->
    <div
      v-if="mobileOpen"
      class="md:hidden border-t border-divider px-4 py-3 flex flex-col gap-2 animate-slide-up"
    >
      <form @submit="handleSearch" class="mb-2" v-if="isLoggedIn">
        <div class="relative w-full">
          <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-ink-muted pointer-events-none" stroke-width="2" />
          <input
            v-model="searchQuery"
            type="text"
            :placeholder="t('nav.searchPlaceholder')"
            class="w-full pl-9 pr-3 py-2 text-sm
                   bg-[#0d1117] border border-divider rounded-lg
                   text-ink placeholder:text-ink-muted
                   focus:outline-none focus:ring-1 focus:ring-accent"
          />
        </div>
      </form>
      <template v-if="isLoggedIn">
        <router-link to="/" class="nav-link-mobile" @click="close">{{ t('nav.home') }}</router-link>
        <router-link to="/schools" class="nav-link-mobile" @click="close">{{ t('nav.schools') }}</router-link>
        <router-link to="/pool" class="nav-link-mobile" @click="close">{{ t('nav.pool') }}</router-link>
        <router-link to="/bookmarks" class="nav-link-mobile" @click="close">{{ t('nav.bookmarks') }}</router-link>
        <router-link to="/edit" class="nav-link-mobile" @click="close">{{ t('nav.newArticle') }}</router-link>
        <button class="nav-link-mobile text-left" @click="handleLogout">{{ t('nav.logout') }}</button>
      </template>
      <button v-else class="nav-link-mobile text-left" @click="openAuth">{{ t('nav.signIn') }}</button>
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

.brand-logo {
  font-family: 'EB Garamond', 'LXGW WenKai', 'Noto Serif SC', serif;
  font-weight: 700;
  letter-spacing: 0.05em;
}
</style>
