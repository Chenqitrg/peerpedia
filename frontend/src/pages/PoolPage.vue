<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useAsyncState } from '@vueuse/core'
import { getPool } from '../api/pool'
import { useBookmarkToggle } from '../composables/useBookmarkToggle'
import ArticleCard from '../components/ArticleCard.vue'
import type { PoolResponse } from '../api/types'

const { state: pool, isLoading: loading, error: rawError, execute: loadPool } = useAsyncState(
  () => getPool(),
  null as PoolResponse | null,
  { immediate: false }
)

const poolArticles = computed(() => pool.value?.articles ?? [])

const error = computed(() => {
  const e = rawError.value as any
  return e?.userMessage || e?.response?.data?.detail || ''
})

const { toggle: handleToggleBookmark } = useBookmarkToggle(
  computed(() => poolArticles.value),
  (_msg: string) => {}
)

onMounted(() => loadPool())
</script>

<template>
  <div class="pool-page animate-fade-in">
    <header class="mb-8">
      <h1 class="text-display-md text-ink mb-2">Review Pool</h1>
      <p class="text-sm text-ink-muted">
        Articles from your network awaiting review
      </p>
    </header>

    <!-- Loading -->
    <div v-if="loading" class="space-y-4">
      <div v-for="i in 3" :key="i" class="card p-5 animate-pulse">
        <div class="skeleton h-5 w-2/3 mb-3" />
        <div class="skeleton h-4 w-1/3 mb-2" />
        <div class="skeleton h-3 w-full mb-4" />
        <div class="skeleton h-3 w-3/4" />
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="card p-8 text-center">
      <p class="text-ink-muted">{{ error }}</p>
      <button class="btn-outline mt-4" @click="loadPool()">Retry</button>
    </div>

    <!-- Empty -->
    <div v-else-if="poolArticles.length === 0" class="card p-12 text-center">
      <p class="text-ink-muted mb-4">Pool is empty.</p>
      <p class="text-xs text-ink-muted/60 mb-6">
        All articles have been reviewed. Check back later.
      </p>
      <router-link to="/" class="btn-primary no-underline">Back to Home</router-link>
    </div>

    <!-- Pool list -->
    <div v-else class="space-y-4">
      <ArticleCard
        v-for="article in poolArticles"
        :key="article.id"
        :article="article"
        @toggle-bookmark="handleToggleBookmark"
      />
    </div>
  </div>
</template>
