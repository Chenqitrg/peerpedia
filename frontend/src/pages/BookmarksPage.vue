<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '../stores/useUserStore'
import { useOffline } from '../composables/useOffline'
import { saveJSON, loadJSON } from '../composables/useLocalStorage'
import { fetchBookmarks } from '../api/bookmarks'
import { getArticle } from '../api/articles'
import { useBookmarkToggle } from '../composables/useBookmarkToggle'
import { useAsyncResource } from '../composables/useAsyncResource'
import ArticleCard from '../components/ArticleCard.vue'
import SkeletonCard from '../components/SkeletonCard.vue'
import ErrorState from '../components/ErrorState.vue'
import type { ArticleSummary, Bookmark } from '../api/types'
import { Bookmark as BookmarkIcon, WifiOff } from 'lucide-vue-next'

const router = useRouter()
const userStore = useUserStore()
const { t } = useI18n()
const { isLocalOnly } = useOffline()

const articles = ref<ArticleSummary[]>([])
const isOfflineCache = ref(false)

const { loading, error, execute: loadBookmarks } = useAsyncResource(
  async () => {
    if (!userStore.viewer) throw new Error(t('bookmarks.authError'))

    const cacheKey = `bookmarks-${userStore.viewer.id}`

    // Offline: load ArticleSummary[] directly from localStorage.
    if (isLocalOnly()) {
      const cached = loadJSON<ArticleSummary[]>(cacheKey)
      if (cached && cached.length > 0) {
        isOfflineCache.value = true
        articles.value = cached
        return cached
      }
      articles.value = []
      return []
    }

    // Online: fetch bookmarks, resolve to ArticleSummary, cache full data.
    const bookmarks: Bookmark[] = await fetchBookmarks()
    isOfflineCache.value = false
    const results = await Promise.all(
      bookmarks.map((b: Bookmark) => getArticle(b.article_id).catch(() => null)),
    )
    const resolved = results.filter((r): r is any => r !== null) as ArticleSummary[]
    saveJSON(cacheKey, resolved)
    articles.value = resolved
    return resolved
  },
  null,
  { immediate: true },
)

const { remove: handleToggleBookmark } = useBookmarkToggle(articles)
</script>

<template>
  <div class="bookmarks-page animate-fade-in">
    <div class="flex items-center justify-between mb-2">
      <h1 class="text-display-md text-ink">{{ t('bookmarks.title') }}</h1>
      <span
        v-if="isOfflineCache"
        class="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-[#21262d] text-ink-muted/60"
        :data-tooltip="t('offline.local_mode_hint')"
      >
        <WifiOff class="w-3 h-3" stroke-width="2" />
        {{ t('offline.cached') }}
      </span>
    </div>
    <p class="text-sm text-ink-muted mb-6">{{ t('bookmarks.subtitle') }}</p>

    <!-- Loading -->
    <SkeletonCard v-if="loading" />

    <!-- Error -->
    <ErrorState
      v-else-if="error"
      :message="error"
      :back-to-home="error === t('bookmarks.authError')"
      @retry="loadBookmarks()"
    />

    <!-- Empty -->
    <div v-else-if="articles.length === 0" class="card p-12 text-center">
      <BookmarkIcon class="w-12 h-12 text-ink-muted/40 mx-auto mb-3" stroke-width="1.5" />
      <p class="text-ink-muted mb-4">{{ t('bookmarks.empty') }}</p>
      <p class="text-xs text-ink-muted/60">{{ t('bookmarks.emptyHint') }}</p>
    </div>

    <!-- Article list -->
    <div v-else class="space-y-4">
      <ArticleCard
        v-for="article in articles"
        :key="article.id"
        :article="article"
        @toggle-bookmark="handleToggleBookmark"
      />
    </div>
  </div>
</template>
