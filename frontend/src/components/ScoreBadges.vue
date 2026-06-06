<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps<{
  score: { originality: number; rigor: number; completeness: number; pedagogy: number; impact: number } | null
  highlightFirst?: boolean
  showLabel?: boolean
}>()

const DIMS = [
  { key: 'originality' as const, short: 'O', full: 'riginality' },
  { key: 'rigor' as const, short: 'R', full: 'igor' },
  { key: 'completeness' as const, short: 'C', full: 'ompleteness' },
  { key: 'pedagogy' as const, short: 'P', full: 'edagogy' },
  { key: 'impact' as const, short: 'I', full: 'mpact' },
] as const
</script>

<template>
  <span v-if="score" class="inline-flex items-center gap-x-2.5 text-xs leading-none">
    <span v-if="showLabel" class="text-ink-muted font-semibold">{{ t('article.scores') }}</span>
    <span
      v-for="(dim, idx) in DIMS"
      :key="dim.key"
      class="score-dim inline-flex items-center cursor-default"
      :class="highlightFirst && idx === 0 ? 'text-accent font-semibold' : 'text-ink-muted'"
    >
      <span class="short">{{ dim.short }}</span>
      <span class="full">{{ dim.full }}</span>
      <span>:{{ score[dim.key] }}</span>
    </span>
  </span>
  <span v-else class="text-xs text-ink-muted">—</span>
</template>

<style scoped>
.score-dim .full {
  display: inline-block;
  max-width: 0;
  overflow: hidden;
  white-space: nowrap;
  vertical-align: bottom;
  transition: max-width 0.3s ease;
}

.score-dim:hover .full {
  max-width: 100px;
}
</style>
