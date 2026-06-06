<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '../stores/useUserStore'
import { fetchFeed } from '../api/feed'
import { useAsyncResource } from '../composables/useAsyncResource'
import { useBookmarkToggle } from '../composables/useBookmarkToggle'
import ArticleCard from '../components/ArticleCard.vue'
import SkeletonCard from '../components/SkeletonCard.vue'
import ErrorState from '../components/ErrorState.vue'
import Pagination from '../components/Pagination.vue'
import type { FeedResponse } from '../api/types'
import { Waypoints } from 'lucide-vue-next'

const userStore = useUserStore()
const { t } = useI18n()
const isLoggedIn = computed(() => !!userStore.viewer)

const pageSize = 20
const currentPage = ref(1)

const { data: feed, loading, error, execute: loadFeed } = useAsyncResource(
  () => fetchFeed(),
  null as FeedResponse | null,
  { immediate: false, resetOnExecute: false },
)

const articles = computed(() => feed.value?.articles ?? [])
const total = computed(() => feed.value?.total ?? 0)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

const { toggle: handleToggleBookmark } = useBookmarkToggle(articles, (_msg: string) => {})

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
  if (isLoggedIn.value && !userStore.isTauriMode) loadFeed()
})

// Re-fetch feed when user logs in (modal doesn't remount the page)
// Skip in Tauri mode — no server to fetch from.
watch(isLoggedIn, (loggedIn) => {
  if (loggedIn && !userStore.isTauriMode) loadFeed()
})
</script>

<template>
  <div class="home-page animate-fade-in">
    <!-- Welcome state — not logged in -->
    <div v-if="!isLoggedIn" class="flex flex-col items-center justify-center min-h-[60vh] text-center">
      <Waypoints class="w-12 h-12 text-accent mb-6" stroke-width="1.5" />
      <h1 class="text-display-lg font-heading font-bold text-ink mb-3">
        {{ t('nav.brand') }}
      </h1>
      <p class="text-lg text-ink-muted mb-8 max-w-md">
        {{ t('home.tagline') }}
      </p>
      <div class="flex items-center gap-3">
        <button
          class="px-6 py-2 text-sm font-semibold bg-accent text-[#0d1117] rounded-lg
                 hover:brightness-110 transition-all duration-200"
          @click="openAuth"
        >
          {{ t('nav.signIn') }}
        </button>
        <button
          class="px-6 py-2 text-sm font-semibold text-accent border border-accent/30 rounded-lg
                 hover:bg-accent/10 transition-all duration-200"
          @click="openAuth"
        >
          {{ t('nav.createAccount') }}
        </button>
      </div>
    </div>

    <!-- Page header (logged in) -->
    <template v-if="isLoggedIn">
    <header class="mb-8">
      <h1 class="text-display-md text-ink mb-2">{{ t('home.feed') }}</h1>
      <p class="text-sm text-ink-muted">
        {{ t('home.feedSubtitle') }}
      </p>
    </header>

    <!-- Loading -->
    <SkeletonCard v-if="loading" />

    <!-- Error -->
    <ErrorState v-else-if="error" :message="error" @retry="loadFeed()" />

    <!-- Empty -->
    <div v-else-if="articles.length === 0" class="card p-12 text-center">
      <p class="text-ink-muted mb-4">{{ t('home.empty') }}</p>
      <p class="text-xs text-ink-muted/60 mb-6">
        {{ t('home.emptyHint') }}
      </p>
      <router-link to="/edit" class="btn-primary no-underline">{{ t('home.createArticle') }}</router-link>
    </div>

    <!-- Article list -->
    <div v-else class="space-y-4">
      <ArticleCard
        v-for="article in articles"
        :key="article.id"
        :article="article"
        @toggle-bookmark="handleToggleBookmark"
      />

      <Pagination :page="currentPage" :totalPages="totalPages" @change="goToPage" />
    </div>
    </template>
  </div>
</template>
