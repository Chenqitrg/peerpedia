<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { searchArticles } from '../api/search'
import { useUserStore } from '../stores/useUserStore'
import { addBookmark, removeBookmark } from '../api/bookmarks'
import ArticleCard from '../components/ArticleCard.vue'
import type { ArticleSummary } from '../api/types'
import { Search, ArrowLeft } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const query = ref('')
const results = ref<ArticleSummary[]>([])
const total = ref(0)
const loading = ref(false)
const searched = ref(false)
const currentPage = ref(1)
const totalPages = ref(1)
const pageSize = 20

onMounted(() => {
  const q = route.query.q as string
  if (q) {
    query.value = q
    doSearch(1)
  }
})

watch(() => route.query.q, (newQ) => {
  if (newQ && newQ !== query.value) {
    query.value = newQ as string
    doSearch(1)
  }
})

async function doSearch(page: number) {
  if (!query.value.trim()) return
  loading.value = true
  searched.value = true
  try {
    const data = await searchArticles(query.value)
    const items = data.articles ?? []
    results.value = items
    total.value = data.total ?? items.length
    totalPages.value = Math.max(1, Math.ceil(total.value / pageSize))
    currentPage.value = page
  } catch {
    results.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function handleSearch(e: Event) {
  e.preventDefault()
  if (query.value.trim()) {
    router.push(`/search?q=${encodeURIComponent(query.value.trim())}`)
  }
}

function goToPage(page: number) {
  if (page < 1 || page > totalPages.value) return
  doSearch(page)
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
    const article = results.value.find(a => a.id === articleId)
    if (article) article.is_bookmarked = !currentlyBookmarked
  } catch {
    // silently fail for search page
  }
}
</script>

<template>
  <div class="search-page animate-fade-in">
    <h1 class="text-display-md text-ink mb-2">Search</h1>
    <p class="text-sm text-ink-muted mb-6">Search across articles, reviews, and authors.</p>

    <!-- Search bar -->
    <form class="flex gap-3 mb-8" @submit="handleSearch">
      <div class="relative flex-1">
        <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-muted pointer-events-none" stroke-width="2" />
        <input
          v-model="query"
          type="search"
          class="w-full pl-10 pr-3 py-2 text-sm bg-card border border-divider rounded-lg
                 text-ink placeholder:text-ink-muted/50
                 focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent
                 transition-colors duration-200"
          placeholder="Search articles, authors, keywords..."
        />
      </div>
      <button
        type="submit"
        class="flex items-center gap-1.5 px-4 py-2 text-sm font-semibold
               bg-accent text-[#0d1117] rounded-lg
               hover:brightness-110 transition-all duration-200"
        :disabled="loading || !query.trim()"
      >
        {{ loading ? 'Searching...' : 'Search' }}
      </button>
    </form>

    <!-- Loading -->
    <div v-if="loading" class="space-y-4">
      <div v-for="i in 3" :key="i" class="card p-5 animate-pulse">
        <div class="skeleton h-5 w-2/3 mb-3" />
        <div class="skeleton h-4 w-1/3 mb-2" />
        <div class="skeleton h-3 w-full" />
      </div>
    </div>

    <!-- Results -->
    <div v-else-if="searched" class="space-y-4">
      <p class="text-sm text-ink-muted mb-4">
        {{ total }} result{{ total !== 1 ? 's' : '' }} for "{{ query }}"
      </p>

      <div v-if="results.length === 0" class="card p-12 text-center">
        <Search class="w-12 h-12 text-ink-muted/40 mx-auto mb-3" stroke-width="1.5" />
        <p class="text-ink-muted">No results found</p>
      </div>

      <template v-else>
        <ArticleCard
          v-for="article in results"
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
            class="flex items-center justify-center w-8 h-8 rounded-lg text-xs font-mono transition-colors duration-200"
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
      </template>
    </div>

    <!-- Initial state -->
    <div v-else class="card p-12 text-center">
      <Search class="w-12 h-12 text-ink-muted/40 mx-auto mb-3" stroke-width="1.5" />
      <p class="text-ink-muted">Enter a search term to find articles.</p>
    </div>
  </div>
</template>
