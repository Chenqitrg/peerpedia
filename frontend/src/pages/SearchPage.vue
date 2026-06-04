<script setup lang="ts">
import { ref } from 'vue'

const query = ref('')
const results = ref<any[]>([])
const loading = ref(false)
const searched = ref(false)

async function search() {
  if (!query.value.trim()) return
  loading.value = true
  searched.value = true
  try {
    const { searchArticles } = await import('../api/search')
    const data = await searchArticles(query.value)
    results.value = data.articles ?? data ?? []
  } catch {
    results.value = []
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="search-page max-w-content animate-fade-in">
    <h1 class="text-display-md text-ink mb-2">Search</h1>
    <p class="text-ink-muted mb-8">Search across articles, reviews, and authors.</p>

    <!-- Search bar -->
    <form class="flex gap-3 mb-8" @submit.prevent="search">
      <div class="relative flex-1">
        <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-ink-subtle" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
        </svg>
        <input
          v-model="query"
          type="search"
          class="input pl-10"
          placeholder="Search articles, authors, keywords..."
        />
      </div>
      <button type="submit" class="btn-primary" :disabled="loading">
        {{ loading ? 'Searching...' : 'Search' }}
      </button>
    </form>

    <!-- Loading -->
    <div v-if="loading" class="space-y-4">
      <div v-for="i in 3" :key="i" class="card p-5 animate-pulse">
        <div class="skeleton h-5 w-2/3 mb-3" />
        <div class="skeleton h-4 w-1/3" />
      </div>
    </div>

    <!-- Results -->
    <div v-else-if="searched" class="space-y-4">
      <p class="text-sm text-ink-muted mb-4">{{ results.length }} result{{ results.length !== 1 ? 's' : '' }}</p>

      <div v-if="results.length === 0" class="card p-12 text-center">
        <svg class="w-14 h-14 text-ink-subtle mx-auto mb-3" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
        </svg>
        <p class="text-ink-muted">No results found for "{{ query }}"</p>
      </div>

      <router-link
        v-for="r in results"
        :key="r.id"
        :to="`/article/${r.id}`"
        class="card-interactive p-5 block no-underline"
      >
        <h3 class="text-lg font-heading font-semibold text-ink mb-1">
          {{ r.title || 'Untitled' }}
        </h3>
        <p v-if="r.authors?.length" class="text-sm text-ink-muted">
          {{ r.authors.map((a: any) => a.name).join(', ') }}
        </p>
      </router-link>
    </div>

    <!-- Empty state (no search yet) -->
    <div v-else class="card p-12 text-center">
      <svg class="w-16 h-16 text-ink-subtle mx-auto mb-4" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
      </svg>
      <p class="text-ink-muted">Enter a search term to find articles.</p>
    </div>
  </div>
</template>
