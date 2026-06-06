<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps<{
  reputation: { professionalism: number; objectivity: number; collaboration: number; pedagogy: number } | null
  showLabel?: boolean
}>()

const DIMS = [
  { key: 'professionalism' as const, short: 'P', full: 'rofessionalism' },
  { key: 'objectivity' as const, short: 'O', full: 'bjectivity' },
  { key: 'collaboration' as const, short: 'C', full: 'ollaboration' },
  { key: 'pedagogy' as const, short: 'R', full: 'eadability' },
] as const
</script>

<template>
  <span v-if="reputation" class="inline-flex items-center gap-x-2.5 text-xs leading-none">
    <span v-if="showLabel" class="text-ink-muted font-semibold">{{ t('common.reputation') }}</span>
    <span
      v-for="dim in DIMS"
      :key="dim.key"
      class="rep-dim inline-flex items-center cursor-default text-ink-muted"
    >
      <span class="short">{{ dim.short }}</span>
      <span class="full">{{ dim.full }}</span>
      <span>:{{ reputation[dim.key] }}</span>
    </span>
  </span>
  <span v-else class="text-xs text-ink-muted">—</span>
</template>

<style scoped>
.rep-dim .full {
  display: inline-block;
  max-width: 0;
  overflow: hidden;
  white-space: nowrap;
  vertical-align: bottom;
  transition: max-width 0.3s ease;
}

.rep-dim:hover .full {
  max-width: 120px;
}

.rep-dim:hover {
  color: #58a6ff;
}
</style>
