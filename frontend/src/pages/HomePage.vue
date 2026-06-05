<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAsyncState } from '@vueuse/core'
import { useUserStore } from '../stores/useUserStore'
import { fetchFeed } from '../api/feed'
import { useBookmarkToggle } from '../composables/useBookmarkToggle'
import ArticleCard from '../components/ArticleCard.vue'
import Pagination from '../components/Pagination.vue'
import type { FeedResponse } from '../api/types'
import { BookOpen } from 'lucide-vue-next'

const userStore = useUserStore()
const isLoggedIn = computed(() => !!userStore.viewer)

const pageSize = 20
const currentPage = ref(1)

const { state: feed, isLoading: loading, error: rawError, execute: loadFeed } = useAsyncState(
  () => fetchFeed(),
  null as FeedResponse | null,
  { immediate: false, resetOnExecute: false },
)

const articles = computed(() => feed.value?.articles ?? [])
const total = computed(() => feed.value?.total ?? 0)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const error = computed(() => {
  if (!rawError.value) return ''
  const e = rawError.value as any
  return e.response?.data?.detail || 'Failed to load feed'
})

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
  if (isLoggedIn.value) loadFeed()
})
</script>

<template>
  <div class="home-page animate-fade-in">
    <!-- Welcome state — not logged in -->
    <div v-if="!isLoggedIn" class="flex flex-col items-center justify-center min-h-[60vh] text-center">
      <BookOpen class="w-12 h-12 text-accent mb-6" stroke-width="1.5" />
      <h1 class="text-display-lg font-heading font-bold text-ink mb-3">
        PeerPedia
      </h1>
      <p class="text-lg text-ink-muted mb-8 max-w-md">
        To a better academia
      </p>
      <div class="flex items-center gap-3">
        <button
          class="px-6 py-2 text-sm font-semibold bg-accent text-[#0d1117] rounded-lg
                 hover:brightness-110 transition-all duration-200"
          @click="openAuth"
        >
          Sign In
        </button>
        <button
          class="px-6 py-2 text-sm font-semibold text-accent border border-accent/30 rounded-lg
                 hover:bg-accent/10 transition-all duration-200"
          @click="openAuth"
        >
          Create Account
        </button>
      </div>
    </div>

    <!-- Page header (logged in) -->
    <template v-if="isLoggedIn">
    <header class="mb-8">
      <h1 class="text-display-md text-ink mb-2">Feed</h1>
      <p class="text-sm text-ink-muted">
        Latest articles from your network
      </p>
    </header>

    <!-- Loading -->
    <div v-if="loading" class="space-y-4">
      <div v-for="i in 3" :key="i" class="card p-5 animate-pulse">
        <div class="skeleton h-6 w-2/3 mb-3" />
        <div class="skeleton h-4 w-1/3 mb-2" />
        <div class="skeleton h-4 w-1/2 mb-4" />
        <div class="skeleton h-3 w-full" />
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="card p-8 text-center">
      <p class="text-ink-muted">{{ error }}</p>
      <button class="btn-outline mt-4" @click="loadFeed(1)">Retry</button>
    </div>

    <!-- Empty -->
    <div v-else-if="articles.length === 0" class="card p-12 text-center">
      <p class="text-ink-muted mb-4">No articles in your feed yet.</p>
      <p class="text-xs text-ink-muted/60 mb-6">
        Follow other users or create your own article to get started.
      </p>
      <router-link to="/edit" class="btn-primary no-underline">Create an Article</router-link>
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
