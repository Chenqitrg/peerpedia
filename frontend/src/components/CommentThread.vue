<script setup lang="ts">
defineProps<{
  messages: { author_id: string; content: string; created_at: string }[]
}>()

function initials(name: string): string {
  return (name || '?')[0].toUpperCase()
}

function timeAgo(date: string): string {
  if (!date) return ''
  const diff = Date.now() - new Date(date).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}d ago`
  return new Date(date).toLocaleDateString()
}
</script>

<template>
  <div class="comment-thread space-y-4">
    <div v-if="messages.length === 0" class="card p-8 text-center">
      <svg class="w-10 h-10 text-ink-subtle mx-auto mb-2" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
      </svg>
      <p class="text-sm text-ink-muted">No comments yet.</p>
    </div>

    <div
      v-for="(msg, i) in messages"
      :key="i"
      class="flex gap-3"
    >
      <!-- Avatar -->
      <div class="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center shrink-0 mt-0.5">
        <span class="text-xs font-bold text-primary-600">{{ initials(msg.author_id) }}</span>
      </div>

      <!-- Bubble -->
      <div class="flex-1 min-w-0">
        <div class="flex items-baseline gap-2 mb-1">
          <span class="text-sm font-semibold text-ink">{{ msg.author_id }}</span>
          <span class="text-xs text-ink-subtle">{{ timeAgo(msg.created_at) }}</span>
        </div>
        <div class="bg-surface-100 rounded-lg px-4 py-2.5 text-sm text-ink leading-relaxed">
          {{ msg.content }}
        </div>
      </div>
    </div>
  </div>
</template>
