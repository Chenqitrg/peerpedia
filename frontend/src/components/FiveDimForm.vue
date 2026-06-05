<script setup lang="ts">
import StarRating from './StarRating.vue'
import { SCORE_DIMS, type ScoreDimKey } from '../api/constants'

const props = defineProps<{
  modelValue: { originality: number; rigor: number; completeness: number; pedagogy: number; impact: number }
}>()
const emit = defineEmits<{ 'update:modelValue': [value: typeof props.modelValue] }>()

function updateDimension(dim: ScoreDimKey, value: number) {
  emit('update:modelValue', { ...props.modelValue, [dim]: value })
}
</script>

<template>
  <fieldset class="five-dim-form space-y-0.5">
    <div
      v-for="dim in SCORE_DIMS"
      :key="dim.key"
      class="flex items-center gap-2 py-0.5 rounded hover:bg-[#21262d] transition-colors duration-150"
    >
      <span class="text-xs text-ink-muted w-20 shrink-0">{{ dim.fullLabel }}</span>
      <StarRating
        size="sm"
        :modelValue="modelValue[dim.key]"
        @update:modelValue="(v: number) => updateDimension(dim.key, v)"
      />
    </div>
  </fieldset>
</template>
