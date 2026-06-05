<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/useUserStore'
import { fetchBookmarks, removeBookmark } from '../api/bookmarks'
import { getArticle } from '../api/articles'
import ArticleCard from '../components/ArticleCard.vue'
import type { ArticleSummary, Bookmark } from '../api/types'
import { Bookmark as BookmarkIcon, ArrowLeft } from 'lucide-vue-next'

const router = useRouter()
const userStore = useUserStore()

const articles = ref<ArticleSummary[]>([])
const loading = ref(false)
const error = ref('')

onMounted(() => {
  loadBookmarks()
})

async function loadBookmarks() {
  if (!userStore.viewer) {
    error.value = 'Please log in to view bookmarks'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const bookmarks: Bookmark[] = await fetchBookmarks(userStore.viewer.id)
    const results = await Promise.all(
      bookmarks.map((b: Bookmark) => getArticle(b.article_id).catch(() => null)),
    )
    articles.value = results.filter((r): r is ArticleSummary => r !== null)
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Failed to load bookmarks'
  } finally {
    loading.value = false
  }
}

async function handleToggleBookmark(articleId: string, currentlyBookmarked: boolean) {
  if (!userStore.viewer) return
  try {
    if (currentlyBookmarked) {
      await removeBookmark(articleId, userStore.viewer.id)
      articles.value = articles.value.filter(a => a.id !== articleId)
    }
  } catch {
    // silently fail
  }
}
</script>

<template>
  <div class="bookmarks-page animate-fade-in">
    <h1 class="text-display-md text-ink mb-2">Bookmarks</h1>
    <p class="text-sm text-ink-muted mb-6">Your saved articles</p>

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
      <button v-if="error !== 'Please log in to view bookmarks'" class="btn-outline mt-4" @click="loadBookmarks">
        Retry
      </button>
      <router-link v-else to="/" class="btn-primary mt-4 no-underline inline-block">
        Back to Home
      </router-link>
    </div>

    <!-- Empty -->
    <div v-else-if="articles.length === 0" class="card p-12 text-center">
      <BookmarkIcon class="w-12 h-12 text-ink-muted/40 mx-auto mb-3" stroke-width="1.5" />
      <p class="text-ink-muted mb-4">No bookmarks yet.</p>
      <p class="text-xs text-ink-muted/60">Bookmark articles to save them for later.</p>
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
