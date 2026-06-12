<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { useOffline } from '../composables/useOffline'
import { searchArticles } from '../api/search'
import { useUserStore } from '../stores/useUserStore'
import { useTauri } from '../composables/useTauri'
import { useAsyncResource } from '../composables/useAsyncResource'
import { useBookmarkToggle } from '../composables/useBookmarkToggle'
import ArticleCard from '../components/ArticleCard.vue'
import SkeletonCard from '../components/SkeletonCard.vue'
import ErrorState from '../components/ErrorState.vue'
import Pagination from '../components/Pagination.vue'
import type { SearchResult } from '../api/types'
import { Search } from 'lucide-vue-next'

const route = useRoute()
const userStore = useUserStore()
const tauri = useTauri()
const { t } = useI18n()
const { canRead, getFallback, isLocalOnly } = useOffline()

const isLocalMode = computed(() =>
  route.query.mode === 'local' || isLocalOnly()
)
const degraded = ref(false)
const searchScope = computed(() =>
  isLocalMode.value ? 'search_local'
  : degraded.value ? 'search_degraded'
  : canRead('search.network') ? 'search_network'
  : 'search_local'
)

const query = ref('')
const searched = ref(false)
const currentPage = ref(1)
const pageSize = 20

const { data: result, loading, error, execute: doSearch } = useAsyncResource(
  async () => {
    if (!query.value.trim()) return null
    if (isLocalMode.value) {
      const [drafts, cached] = await Promise.all([
        tauri.searchDrafts({ q: query.value.trim(), account_id: userStore.viewer?.id }),
        tauri.searchCachedArticles({ q: query.value.trim() }),
      ])
      const draftList = (drafts && !('error' in drafts) && Array.isArray(drafts)) ? drafts : []
      const cacheList = (cached && !('error' in cached) && Array.isArray(cached)) ? cached : []
      const seen = new Set<string>()
      const merged: any[] = []
      for (const d of draftList) {
        if (!seen.has(d.id)) { seen.add(d.id); merged.push(d) }
      }
      for (const c of cacheList) {
        if (!seen.has(c.id)) { seen.add(c.id); merged.push(c) }
      }
      return {
        articles: merged.map(m => ({
          id: m.id,
          title: m.title || 'Untitled',
          status: 'draft' as const,
          authors: [{ id: userStore.viewer?.id || '', name: userStore.viewer?.name || '', anonymous_name: '' }],
          content_preview: '',
          commit_hash: '',
          fork_count: 0,
          forked_from: null,
          commit_count: 0,
          score: null,
          days_remaining: null,
          sink_duration_days: null,
          is_bookmarked: false,
          is_own_article: userStore.viewer?.id != null,
          created_at: m.updated_at,
          updated_at: m.updated_at,
          abstract: null,
        })),
        total: merged.length,
      }
    }
    degraded.value = false
    try {
      return await searchArticles({
        q: query.value.trim(),
        page: currentPage.value,
        size: pageSize,
      })
    } catch {
      // Network search failed — fall back to local
      degraded.value = true
      const [drafts, cached] = await Promise.all([
        tauri.searchDrafts({ q: query.value.trim(), account_id: userStore.viewer?.id }),
        tauri.searchCachedArticles({ q: query.value.trim() }),
      ])
      const draftList = (drafts && !('error' in drafts) && Array.isArray(drafts)) ? drafts : []
      const cacheList = (cached && !('error' in cached) && Array.isArray(cached)) ? cached : []
      const seen = new Set<string>()
      const merged: any[] = []
      for (const d of draftList) {
        if (!seen.has(d.id)) { seen.add(d.id); merged.push(d) }
      }
      for (const c of cacheList) {
        if (!seen.has(c.id)) { seen.add(c.id); merged.push(c) }
      }
      return {
        articles: merged.map(m => ({
          id: m.id,
          title: m.title || 'Untitled',
          status: 'draft' as const,
          authors: [{ id: userStore.viewer?.id || '', name: userStore.viewer?.name || '', anonymous_name: '' }],
          content_preview: '',
          commit_hash: '',
          fork_count: 0,
          forked_from: null,
          commit_count: 0,
          score: null,
          days_remaining: null,
          sink_duration_days: null,
          is_bookmarked: false,
          is_own_article: userStore.viewer?.id != null,
          created_at: m.updated_at,
          updated_at: m.updated_at,
          abstract: null,
        })),
        total: merged.length,
      }
    }
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
  if (q) query.value = q
  if (q && (canRead('search.network') || isLocalMode.value)) {
    searched.value = true
    doSearch()
  }
})

watch(
  () => route.query.q as string,
  (val) => {
    const v = val || ''
    if (v !== query.value) {
      query.value = v
      if (v) { searched.value = true; doSearch() }
    }
  },
)

function executeSearch(page: number) {
  if (!canRead('search.network') && !isLocalMode.value) return
  currentPage.value = page
  searched.value = true
  doSearch()
}

function goToPage(page: number) {
  if (page < 1 || page > totalPages.value) return
  executeSearch(page)
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

defineExpose({ query, doSearch })
</script>

<template>
  <div class="search-page animate-fade-in">
    <div class="flex items-center gap-3 mb-6">
      <h1 class="text-lg font-heading font-semibold text-ink">
        <template v-if="query">{{ query }}</template>
        <template v-else>{{ t('search.title') }}</template>
      </h1>
      <span
        class="text-[10px] px-2 py-0.5 rounded-full font-semibold uppercase tracking-wider"
        :class="searchScope === 'search_local' ? 'bg-[#21262d] text-ink-muted/60' : searchScope === 'search_degraded' ? 'bg-amber-600/15 text-amber-400' : 'bg-accent/15 text-accent'"
      >
        {{ searchScope === 'search_degraded' ? 'Local (fallback)' : searchScope === 'search_local' ? 'Local' : 'Network' }}
      </span>
    </div>

    <SkeletonCard v-if="loading" />

    <ErrorState v-else-if="error" :message="error" @retry="doSearch()" />

    <div v-else-if="searched && !error">
      <p class="text-sm text-ink-muted mb-4">
        {{ total }} {{ t('search.results') }}
      </p>

      <div v-if="results.length === 0" class="card p-12 text-center">
        <Search class="w-10 h-10 text-ink-muted/30 mx-auto mb-3" stroke-width="1.5" />
        <p class="text-ink-muted text-sm">{{ t('search.noResults') }}</p>
      </div>

      <div v-else class="space-y-4">
        <ArticleCard
          v-for="article in results"
          :key="article.id"
          :article="article"
          @toggle-bookmark="handleToggleBookmark"
        />
        <Pagination :page="currentPage" :totalPages="totalPages" @change="goToPage" />
      </div>
    </div>

    <div v-else class="card p-12 text-center">
      <Search class="w-10 h-10 text-ink-muted/30 mx-auto mb-3" stroke-width="1.5" />
      <p class="text-ink-muted text-sm">{{ t('search.placeholder') }}</p>
    </div>
  </div>
</template>
