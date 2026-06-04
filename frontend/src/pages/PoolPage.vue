<script setup lang="ts">
import { onMounted } from 'vue'
import { usePoolStore } from '../stores/usePoolStore'

const store = usePoolStore()

onMounted(() => {
  store.fetchPool()
})

function avgScore(score: Record<string, number>): string {
  const vals = Object.values(score).filter((v) => typeof v === 'number')
  if (!vals.length) return '-'
  return (vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1)
}
</script>

<template>
  <div class="pool-page animate-fade-in">
    <header class="mb-8">
      <h1 class="text-display-md text-ink mb-2">Review Pool</h1>
      <p class="text-ink-muted">Articles awaiting peer review. Your feedback strengthens the community.</p>
    </header>

    <!-- Loading -->
    <div v-if="store.loading" class="space-y-4">
      <div v-for="i in 3" :key="i" class="card p-5 animate-pulse">
        <div class="skeleton h-5 w-2/3 mb-3" />
        <div class="skeleton h-4 w-1/3 mb-2" />
        <div class="skeleton h-4 w-1/4" />
      </div>
    </div>

    <!-- Empty -->
    <div v-else-if="store.poolArticles.length === 0" class="card p-12 text-center">
      <svg class="w-16 h-16 text-ink-subtle mx-auto mb-4" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
      <h3 class="text-xl font-heading font-semibold text-ink mb-2">Pool is empty</h3>
      <p class="text-ink-muted mb-4">All articles have been reviewed. Check back later.</p>
      <router-link to="/" class="btn-primary no-underline">Back to Home</router-link>
    </div>

    <!-- Pool list -->
    <div v-else class="space-y-4">
      <router-link
        v-for="a in store.poolArticles"
        :key="a.id"
        :to="`/article/${a.id}`"
        class="card-interactive p-5 flex items-center justify-between gap-4 no-underline"
      >
        <div class="min-w-0 flex-1">
          <h3 class="text-lg font-heading font-semibold text-ink mb-1 line-clamp-1">
            {{ a.title || 'Untitled' }}
          </h3>
          <p v-if="a.authors?.length" class="text-sm text-ink-muted">
            {{ a.authors.map((au: any) => au.name).join(', ') }}
          </p>
        </div>

        <div class="flex items-center gap-3 shrink-0">
          <span v-if="a.score" class="flex items-center gap-1 text-sm text-ink-muted">
            <svg class="w-4 h-4 text-star" fill="currentColor" viewBox="0 0 20 20">
              <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
            </svg>
            {{ avgScore(a.score) }}
          </span>
          <svg class="w-5 h-5 text-ink-subtle shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
          </svg>
        </div>
      </router-link>
    </div>
  </div>
</template>
