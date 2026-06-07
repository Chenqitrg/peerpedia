<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { useOffline } from '../composables/useOffline'
import { searchArticles } from '../api/search'
import { useUserStore } from '../stores/useUserStore'
import { useAsyncResource } from '../composables/useAsyncResource'
import { useBookmarkToggle } from '../composables/useBookmarkToggle'
import ArticleCard from '../components/ArticleCard.vue'
import SkeletonCard from '../components/SkeletonCard.vue'
import ErrorState from '../components/ErrorState.vue'
import Pagination from '../components/Pagination.vue'
import type { SearchResult } from '../api/types'
import { Search } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const { t } = useI18n()
const { canRead, getFallback } = useOffline()

const searchScope = computed(() => canRead('search.network') ? 'search_network' : 'search_local')

const query = ref('')
const category = ref('')
const sort = ref('')
const searched = ref(false)
const currentPage = ref(1)
const pageSize = 20

const CATEGORIES = ['physics', 'math', 'biology', 'cs', 'chemistry', 'engineering']

const { data: result, loading, error, execute: doSearch } = useAsyncResource(
  async () => {
    if (!query.value.trim() && !category.value) return null
    return await searchArticles({
      q: query.value.trim(),
      category: category.value,
      sort: sort.value,
      page: currentPage.value,
      size: pageSize,
    })
  },
  null as SearchResult | null,
  { immediate: false },
)

const results = computed(() => result.value?.articles ?? [])
const total = computed(() => result.value?.total ?? 0)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

const { toggle: handleToggleBookmark } = useBookmarkToggle(results)

onMounted(() => {
  const q = route.query.q as string
  const cat = route.query.category as string
  const s = route.query.sort as string
  if (q) query.value = q
  if (cat) category.value = cat
  if (s) sort.value = s
  // Trigger search if any filter param is present AND network search is available
  if ((q || cat) && canRead('search.network')) {
    searched.value = true
    doSearch()
  }
})

// Watch all query params to support browser back/forward navigation
watch(
  () => ({ q: route.query.q, category: route.query.category, sort: route.query.sort }),
  (params) => {
    const q = (params.q as string) || ''
    const cat = (params.category as string) || ''
    const s = (params.sort as string) || ''
    // Only update if values actually changed to avoid infinite loops
    if (q !== query.value || cat !== category.value || s !== sort.value) {
      query.value = q
      category.value = cat
      sort.value = s
      if (q || cat) {
        searched.value = true
        doSearch()
      }
    }
  },
)

function executeSearch(page: number) {
  if (!canRead('search.network')) return
  currentPage.value = page
  searched.value = true
  doSearch()
}

function handleSearch(e: Event) {
  e.preventDefault()
  const params = new URLSearchParams()
  if (query.value.trim()) params.set('q', query.value.trim())
  if (category.value) params.set('category', category.value)
  if (sort.value) params.set('sort', sort.value)
  if (params.toString()) {
    router.push(`/search?${params.toString()}`)
  }
}

function goToPage(page: number) {
  if (page < 1 || page > totalPages.value) return
  executeSearch(page)
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

defineExpose({ query, category, sort, doSearch })
</script>

<template>
  <div class="search-page animate-fade-in">
    <div class="flex items-center justify-between mb-2">
      <h1 class="text-display-md text-ink">{{ t('search.title') }}</h1>
      <span class="text-xs px-2 py-0.5 rounded-full"
        :class="canRead('search.network') ? 'bg-accent/15 text-accent' : 'bg-[#21262d] text-ink-muted/60'">
        {{ t(`offline.${searchScope}`) }}
      </span>
    </div>
    <p class="text-sm text-ink-muted mb-6">{{ t('search.subtitle') }}</p>

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
          :placeholder="t('nav.searchPlaceholder')"
        />
      </div>
      <button
        type="submit"
        class="flex items-center gap-1.5 px-4 py-2 text-sm font-semibold
               bg-accent text-[#0d1117] rounded-lg
               hover:brightness-110 transition-all duration-200"
        :disabled="loading || (!query.trim() && !category)"
      >
        {{ loading ? t('search.searching') : t('search.title') }}
      </button>
    </form>

    <!-- Filters -->
    <div class="flex flex-wrap items-center gap-3 mb-6">
      <label class="flex items-center gap-1.5 text-xs text-ink-muted">
        <span>{{ t('search.category') }}</span>
        <select
          v-model="category"
          class="bg-card border border-divider rounded px-2 py-1 text-xs text-ink
                 focus:outline-none focus:ring-1 focus:ring-accent"
          @change="executeSearch(1)"
        >
          <option value="">{{ t('search.all') }}</option>
          <option v-for="cat in CATEGORIES" :key="cat" :value="cat">
            {{ cat.charAt(0).toUpperCase() + cat.slice(1) }}
          </option>
        </select>
      </label>
      <label class="flex items-center gap-1.5 text-xs text-ink-muted">
        <span>{{ t('search.sort') }}</span>
        <select
          v-model="sort"
          class="bg-card border border-divider rounded px-2 py-1 text-xs text-ink
                 focus:outline-none focus:ring-1 focus:ring-accent"
          @change="executeSearch(1)"
        >
          <option value="">{{ t('search.relevance') }}</option>
          <option value="newest">{{ t('search.newest') }}</option>
          <option value="score">{{ t('search.score') }}</option>
        </select>
      </label>
    </div>

    <!-- Loading -->
    <SkeletonCard v-if="loading" />

    <!-- Error -->
    <ErrorState v-else-if="error" :message="error" @retry="doSearch()" />

    <!-- Results -->
    <div v-else-if="searched && !error" class="space-y-4">
      <p class="text-sm text-ink-muted mb-4">
        {{ total }} {{ t('search.results') }} for "{{ query }}"
      </p>

      <div v-if="results.length === 0" class="card p-12 text-center">
        <Search class="w-12 h-12 text-ink-muted/40 mx-auto mb-3" stroke-width="1.5" />
        <p class="text-ink-muted">{{ t('search.noResults') }}</p>
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
      <p class="text-ink-muted">{{ t('search.placeholder') }}</p>
    </div>
  </div>
</template>
