<script setup lang="ts">
import { ref } from 'vue'

const mobileOpen = ref(false)

function toggle() {
  mobileOpen.value = !mobileOpen.value
}

function close() {
  mobileOpen.value = false
}
</script>

<template>
  <nav
    class="fixed top-0 left-0 right-0 z-50 bg-white/95 backdrop-blur-sm border-b border-gray-200 shadow-navbar"
    role="navigation"
    aria-label="Main navigation"
  >
    <div class="max-w-content mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex items-center justify-between h-16">
        <!-- Brand -->
        <router-link
          to="/"
          class="flex items-center gap-2 text-xl font-heading font-bold text-primary-700 hover:text-primary-800 transition-colors duration-200 no-underline"
          @click="close"
        >
          <svg class="w-7 h-7" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
            <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
          </svg>
          PeerPedia
        </router-link>

        <!-- Desktop links -->
        <div class="hidden md:flex items-center gap-1">
          <router-link to="/" class="nav-link" active-class="nav-link-active">Home</router-link>
          <router-link to="/pool" class="nav-link" active-class="nav-link-active">Pool</router-link>
          <router-link to="/search" class="nav-link" active-class="nav-link-active">Search</router-link>
        </div>

        <!-- Mobile hamburger -->
        <button
          class="md:hidden btn-ghost p-2"
          :aria-expanded="mobileOpen"
          aria-label="Toggle navigation menu"
          @click="toggle"
        >
          <svg v-if="!mobileOpen" class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
          <svg v-else class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <!-- Mobile menu -->
      <div
        v-if="mobileOpen"
        class="md:hidden border-t border-gray-200 py-3 flex flex-col gap-1 animate-slide-up"
      >
        <router-link to="/" class="nav-link-mobile" @click="close">Home</router-link>
        <router-link to="/pool" class="nav-link-mobile" @click="close">Pool</router-link>
        <router-link to="/search" class="nav-link-mobile" @click="close">Search</router-link>
      </div>
    </div>
  </nav>
</template>

<style scoped>
.nav-link {
  @apply px-3 py-2 text-sm font-semibold text-ink-muted rounded-lg
         hover:text-ink hover:bg-gray-100
         transition-colors duration-200
         no-underline;
}
.nav-link-active {
  @apply text-primary-700 bg-primary-50 hover:bg-primary-100;
}
.nav-link-mobile {
  @apply block px-4 py-2.5 text-base font-semibold text-ink-muted
         hover:text-ink hover:bg-gray-100 rounded-lg
         transition-colors duration-200
         no-underline;
}
</style>
