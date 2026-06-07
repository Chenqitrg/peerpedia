<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import StarRating from './StarRating.vue'
import {
  Lightbulb,
  FlaskConical,
  CheckCheck,
  BookOpen,
  TrendingUp,
} from 'lucide-vue-next'

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
  { key: 'originality' as const, icon: Lightbulb, label: 'Originality' },
  { key: 'rigor' as const, icon: FlaskConical, label: 'Rigor' },
  { key: 'completeness' as const, icon: CheckCheck, label: 'Completeness' },
  { key: 'pedagogy' as const, icon: BookOpen, label: 'Pedagogy' },
  { key: 'impact' as const, icon: TrendingUp, label: 'Impact' },
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
  <span v-if="score" class="inline-flex items-center gap-x-2.5 text-xs leading-none flex-wrap gap-y-1">
    <span v-if="showLabel" class="text-ink-muted font-semibold">{{ t('article.scores') }}</span>
    <span
      v-for="(dim, idx) in DIMS"
      :key="dim.key"
      class="inline-flex items-center gap-1 transition-colors"
      :class="[
        highlightFirst && idx === 0 ? 'text-accent' : 'text-ink-muted',
        editable ? 'cursor-default' : 'cursor-default',
      ]"
      :title="dim.label"
      @mouseenter="onDimEnter(dim.key)"
      @mouseleave="onDimLeave"
    >
      <!-- Editable mode: show StarRating on hover -->
      <template v-if="editable && hoveredDim === dim.key">
        <component :is="dim.icon" class="w-3 h-3" stroke-width="2" />
        <StarRating
          :modelValue="score[dim.key]"
          size="sm"
          @update:modelValue="v => emit('update-score', dim.key, v)"
        />
      </template>
      <!-- Static display: icon + value (compact) -->
      <template v-else>
        <component :is="dim.icon" class="w-3 h-3" stroke-width="2" />
        <span class="font-mono">{{ score[dim.key] }}</span>
      </template>
    </span>
  </span>
  <span v-else class="text-xs text-ink-muted">—</span>
</template>
