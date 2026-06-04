<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useArticleStore } from '../stores/useArticleStore'
import { useUserStore } from '../stores/useUserStore'
import { fetchBookmarks } from '../api/bookmarks'
import { getArticle } from '../api/articles'
import type { Bookmark } from '../api/types'

const store = useArticleStore()
const userStore = useUserStore()

const activeTab = ref<'latest' | 'favorites'>('latest')
const favArticles = ref<any[]>([])
const favLoading = ref(false)

onMounted(() => {
  store.fetchArticles()
})

watch(activeTab, (tab) => {
  if (tab === 'favorites' && userStore.viewer) {
    fetchFavorites()
  }
})

async function fetchFavorites() {
  if (!userStore.viewer) return
  favLoading.value = true
  favArticles.value = []
  try {
    const bookmarks = await fetchBookmarks(userStore.viewer.id)
    const results = await Promise.all(
      bookmarks.map((b: Bookmark) => getArticle(String(b.article_id)))
    )
    favArticles.value = results
  } catch (e) {
    console.error('Failed to load favorites:', e)
  } finally {
    favLoading.value = false
  }
}

function statusBadge(status: string): string {
  switch (status) {
    case 'published': return 'badge-published'
    case 'review':
    case 'in_review': return 'badge-review'
    default: return 'badge-draft'
  }
}

function avgScore(score: Record<string, number>): string {
  const vals = Object.values(score).filter((v) => typeof v === 'number')
  if (!vals.length) return '-'
  return (vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1)
}
</script>

<template>
  <div class="home-page animate-fade-in">
    <!-- Hero -->
    <section class="py-10 md:py-16">
      <h1 class="text-display md:text-display text-ink mb-4">
        PeerPedia
      </h1>
      <p class="text-lg md:text-xl text-ink-muted max-w-2xl">
        A community-driven platform for peer review and scholarly collaboration.
        Discover, review, and contribute to academic articles.
      </p>
      <div class="flex gap-3 mt-6">
        <router-link to="/edit" class="btn-primary btn-lg no-underline">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
          </svg>
          New Article
        </router-link>
        <router-link to="/pool" class="btn-outline btn-lg no-underline">
          Browse Pool
        </router-link>
      </div>
    </section>

    <!-- Article list -->
    <section>
      <h2 class="text-2xl font-heading font-semibold text-ink mb-6">Latest Articles</h2>

      <!-- Loading -->
      <div v-if="store.loading" class="space-y-4">
        <div v-for="i in 3" :key="i" class="card p-5 animate-pulse">
          <div class="skeleton h-6 w-2/3 mb-3" />
          <div class="skeleton h-4 w-1/3 mb-2" />
          <div class="skeleton h-4 w-1/4" />
        </div>
      </div>

      <!-- Empty -->
      <div v-else-if="store.articles.length === 0" class="card p-12 text-center">
        <svg class="w-16 h-16 text-ink-subtle mx-auto mb-4" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
        </svg>
        <h3 class="text-xl font-heading font-semibold text-ink mb-2">No articles yet</h3>
        <p class="text-ink-muted mb-4">Be the first to contribute to PeerPedia.</p>
        <router-link to="/edit" class="btn-primary no-underline">Create an Article</router-link>
      </div>

      <!-- Article cards -->
      <div v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <article
          v-for="a in store.articles"
          :key="a.id"
          class="card-interactive p-5 animate-fade-in"
        >
          <router-link
            :to="`/article/${a.id}`"
            class="no-underline hover:no-underline"
          >
            <h3 class="text-lg font-heading font-semibold text-ink mb-2 line-clamp-2">
              {{ a.title || 'Untitled' }}
            </h3>
          </router-link>
          <p
            v-if="a.authors?.length"
            class="text-sm text-ink-muted mb-3"
          >
            {{ a.authors.map((au: any) => au.name).join(', ') }}
          </p>
          <div class="flex items-center gap-2">
            <span :class="statusBadge(a.status)">{{ a.status }}</span>
            <span v-if="a.score" class="text-xs text-ink-subtle flex items-center gap-1">
              <svg class="w-3.5 h-3.5 text-star" fill="currentColor" viewBox="0 0 20 20">
                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
              </svg>
              {{ avgScore(a.score) }}
            </span>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>
