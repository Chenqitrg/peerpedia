<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import StarRating from './StarRating.vue'

const { t } = useI18n()

const props = withDefaults(defineProps<{
  score: { originality: number; rigor: number; completeness: number; pedagogy: number; impact: number } | null
  highlightFirst?: boolean
  showLabel?: boolean
  editable?: boolean
}>(), {
  editable: false,
})

const emit = defineEmits<{
  'update-score': [dimKey: string, value: number]
}>()

const DIMS = [
  { key: 'originality' as const, short: 'O', full: 'riginality' },
  { key: 'rigor' as const, short: 'R', full: 'igor' },
  { key: 'completeness' as const, short: 'C', full: 'ompleteness' },
  { key: 'pedagogy' as const, short: 'P', full: 'edagogy' },
  { key: 'impact' as const, short: 'I', full: 'mpact' },
] as const

// ── Hover-to-edit state (only used when editable) ───────────────────────

const hoveredDim = ref<string | null>(null)
const hoverTimer = ref<ReturnType<typeof setTimeout> | null>(null)

function onDimEnter(dimKey: string) {
  if (!props.editable || !props.score) return
  if (hoverTimer.value) { clearTimeout(hoverTimer.value); hoverTimer.value = null }
  hoveredDim.value = dimKey
}

function onDimLeave() {
  if (!props.editable) return
  hoverTimer.value = setTimeout(() => { hoveredDim.value = null }, 100)
}
</script>

<template>
  <span v-if="score" class="inline-flex items-center gap-x-2.5 text-xs leading-none">
    <span v-if="showLabel" class="text-ink-muted font-semibold">{{ t('article.scores') }}</span>
    <span
      v-for="(dim, idx) in DIMS"
      :key="dim.key"
      class="score-dim inline-flex items-center"
      :class="[
        highlightFirst && idx === 0 ? 'text-accent font-semibold' : 'text-ink-muted',
        editable ? 'cursor-default' : 'cursor-default',
      ]"
      @mouseenter="onDimEnter(dim.key)"
      @mouseleave="onDimLeave"
    >
      <!-- Editable mode: show StarRating on hover -->
      <template v-if="editable && hoveredDim === dim.key">
        <span class="text-ink-muted mr-0.5">
          {{ dim.short }}<span class="full">{{ dim.full }}</span>
        </span>
        <StarRating
          :modelValue="score[dim.key]"
          size="sm"
          @update:modelValue="v => emit('update-score', dim.key, v)"
        />
      </template>
      <!-- Non-editable / not hovered: show label:value -->
      <template v-else>
        <span class="short">{{ dim.short }}</span>
        <span class="full">{{ dim.full }}</span>
        <span>:{{ score[dim.key] }}</span>
      </template>
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
