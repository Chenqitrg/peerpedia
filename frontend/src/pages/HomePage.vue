<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useUserStore } from '../stores/useUserStore'
import { fetchFeed } from '../api/feed'
import { addBookmark, removeBookmark } from '../api/bookmarks'
import ArticleCard from '../components/ArticleCard.vue'
import type { ArticleSummary } from '../api/types'
import { BookOpen } from 'lucide-vue-next'

const userStore = useUserStore()

const isLoggedIn = computed(() => !!userStore.viewer)

const articles = ref<ArticleSummary[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20
const loading = ref(false)
const error = ref('')

const totalPages = ref(1)

function openAuth() {
  userStore.showAuthModal = true
}

async function loadFeed(page: number) {
  if (!userStore.viewer) return
  loading.value = true
  error.value = ''
  try {
    const data = await fetchFeed(userStore.viewer?.id)
    const items = data.articles ?? []
    articles.value = items
    total.value = data.total ?? items.length
    totalPages.value = Math.max(1, Math.ceil(total.value / pageSize))
    currentPage.value = page
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Failed to load feed'
    articles.value = []
  } finally {
    loading.value = false
  }
}

function goToPage(page: number) {
  if (page < 1 || page > totalPages.value) return
  loadFeed(page)
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function handleToggleBookmark(articleId: string, currentlyBookmarked: boolean) {
  if (!userStore.viewer) return
  try {
    if (currentlyBookmarked) {
      await removeBookmark(articleId, userStore.viewer.id)
    } else {
      await addBookmark(userStore.viewer.id, articleId)
    }
    const article = articles.value.find(a => a.id === articleId)
    if (article) {
      article.is_bookmarked = !currentlyBookmarked
    }
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Failed to update bookmark'
  }
}

onMounted(() => {
  loadFeed(1)
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

      <!-- Pagination -->
      <div
        v-if="totalPages > 1"
        class="flex items-center justify-center gap-2 pt-6 pb-4"
      >
        <button
          class="flex items-center justify-center w-8 h-8 rounded-lg text-xs font-mono
                 text-ink-muted hover:text-ink hover:bg-[#21262d]
                 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          :disabled="currentPage <= 1"
          @click="goToPage(currentPage - 1)"
          aria-label="Previous page"
        >
          &lsaquo;
        </button>

        <button
          v-for="p in totalPages"
          :key="p"
          class="flex items-center justify-center w-8 h-8 rounded-lg text-xs font-mono
                 transition-colors duration-200"
          :class="p === currentPage
            ? 'bg-accent text-[#0d1117] font-bold'
            : 'text-ink-muted hover:text-ink hover:bg-[#21262d]'"
          @click="goToPage(p)"
        >
          {{ p }}
        </button>

        <button
          class="flex items-center justify-center w-8 h-8 rounded-lg text-xs font-mono
                 text-ink-muted hover:text-ink hover:bg-[#21262d]
                 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          :disabled="currentPage >= totalPages"
          @click="goToPage(currentPage + 1)"
          aria-label="Next page"
        >
          &rsaquo;
        </button>
      </div>
    </div>
    </template>
  </div>
</template>
