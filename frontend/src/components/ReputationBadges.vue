<script setup lang="ts">
import { BadgeCheck, Scale, Handshake, MessageSquareText } from 'lucide-vue-next'

defineProps<{
  reputation: { professionalism: number; objectivity: number; collaboration: number; pedagogy: number } | null
  showLabel?: boolean
}>()

const DIMS = [
  { key: 'professionalism' as const, icon: BadgeCheck, title: 'Professionalism' },
  { key: 'objectivity' as const, icon: Scale, title: 'Objectivity' },
  { key: 'collaboration' as const, icon: Handshake, title: 'Collaboration' },
  { key: 'pedagogy' as const, icon: MessageSquareText, title: 'Readability' },
] as const
</script>

<template>
  <span v-if="reputation" class="inline-flex items-center gap-x-2.5 text-xs leading-none flex-wrap gap-y-1">
    <span
      v-for="dim in DIMS"
      :key="dim.key"
      class="inline-flex items-center gap-1 text-accent"
      :title="`${dim.title}: ${reputation[dim.key]}`"
    >
      <component :is="dim.icon" class="w-3.5 h-3.5" stroke-width="1.5" />
      <span class="font-mono">{{ reputation[dim.key] }}</span>
    </span>
  </span>
  <span v-else class="text-xs text-ink-muted">—</span>
</template>
