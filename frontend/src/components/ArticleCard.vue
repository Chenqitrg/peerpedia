<script setup lang="ts">
defineProps<{
  article: {
    id: string
    title: string
    status: string
    authors: string[]
    score?: { originality: number; rigor: number; completeness: number; pedagogy: number; impact: number } | null
    fork_count?: number
    review_count?: number
  }
}>()

function statusBadge(status: string): string {
  switch (status) {
    case 'published': return 'badge-published'
    case 'review':
    case 'in_review': return 'badge-review'
    default: return 'badge-draft'
  }
}
</script>

<template>
  <article class="card-interactive p-5 animate-fade-in">
    <router-link
      :to="`/article/${article.id}`"
      class="no-underline hover:no-underline"
    >
      <h3 class="text-lg font-heading font-semibold text-ink mb-2 line-clamp-2">
        {{ article.title || 'Untitled' }}
      </h3>
    </router-link>

    <p class="text-sm text-ink-muted mb-3">
      {{ article.authors.join(', ') }}
    </p>

    <div class="flex items-center gap-3">
      <span :class="statusBadge(article.status)">{{ article.status }}</span>

      <div v-if="article.score" class="flex items-center gap-3 text-xs text-ink-muted ml-auto">
        <span v-if="article.score" class="flex items-center gap-3">
          <span>O:{{ article.score.originality }}</span>
          <span>R:{{ article.score.rigor }}</span>
          <span>C:{{ article.score.completeness }}</span>
          <span>P:{{ article.score.pedagogy }}</span>
          <span>I:{{ article.score.impact }}</span>
        </span>
        <span v-if="article.review_count != null" class="flex items-center gap-1">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
          {{ article.review_count }}
        </span>
        <span v-if="article.fork_count != null" class="flex items-center gap-1">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
          </svg>
          {{ article.fork_count }}
        </span>
      </div>
    </div>
  </article>
</template>
