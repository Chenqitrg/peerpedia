<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useAsyncState } from '@vueuse/core'
import { useRoute, useRouter } from 'vue-router'
import { searchArticles } from '../api/search'
import { useUserStore } from '../stores/useUserStore'
import { useBookmarkToggle } from '../composables/useBookmarkToggle'
import ArticleCard from '../components/ArticleCard.vue'
import Pagination from '../components/Pagination.vue'
import type { SearchResult } from '../api/types'
import { Search } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const query = ref('')
const searched = ref(false)
const currentPage = ref(1)
const pageSize = 20

const { state: result, isLoading: loading, error: rawError, execute: doSearch } = useAsyncState(
  async () => {
    if (!query.value.trim()) return null
    return await searchArticles(query.value)
  },
  null as SearchResult | null,
  { immediate: false }
)

const results = computed(() => result.value?.articles ?? [])
const total = computed(() => result.value?.total ?? 0)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

const error = computed(() => {
  const e = rawError.value as any
  return e?.userMessage || ''
})

const { toggle: handleToggleBookmark } = useBookmarkToggle(computed(() => results.value))

onMounted(() => {
  const q = route.query.q as string
  if (q) {
    query.value = q
    searched.value = true
    doSearch()
  }
})

watch(() => route.query.q, (newQ) => {
  if (newQ && newQ !== query.value) {
    query.value = newQ as string
    searched.value = true
    doSearch()
  }
})

function executeSearch(page: number) {
  currentPage.value = page
  searched.value = true
  doSearch()
}

function handleSearch(e: Event) {
  e.preventDefault()
  if (query.value.trim()) {
    router.push(`/search?q=${encodeURIComponent(query.value.trim())}`)
  }
}

function goToPage(page: number) {
  if (page < 1 || page > totalPages.value) return
  executeSearch(page)
  window.scrollTo({ top: 0, behavior: 'smooth' })
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

    <!-- Error -->
    <div v-else-if="error" class="card p-8 text-center">
      <p class="text-ink-muted">{{ error }}</p>
      <button class="btn-outline mt-4" @click="doSearch()">Retry</button>
    </div>

    <!-- Results -->
    <div v-else-if="searched && !error" class="space-y-4">
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

        <Pagination :page="currentPage" :totalPages="totalPages" @change="goToPage" />
      </template>
    </div>

    <!-- Initial state -->
    <div v-else class="card p-12 text-center">
      <Search class="w-12 h-12 text-ink-muted/40 mx-auto mb-3" stroke-width="1.5" />
      <p class="text-ink-muted">Enter a search term to find articles.</p>
    </div>
  </div>
</template>
