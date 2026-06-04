<script setup lang="ts">
import StarRating from './StarRating.vue'

const props = defineProps<{
  modelValue: { originality: number; rigor: number; completeness: number; pedagogy: number; impact: number }
}>()
const emit = defineEmits<{ 'update:modelValue': [value: typeof props.modelValue] }>()

const dimensions = ['originality', 'rigor', 'completeness', 'pedagogy', 'impact'] as const

function updateDimension(dim: typeof dimensions[number], value: number) {
  emit('update:modelValue', { ...props.modelValue, [dim]: value })
}
</script>

<template>
  <fieldset class="five-dim-form space-y-4">
    <legend class="label mb-4">Five-Dimension Review</legend>
    <div
      v-for="dim in dimensions"
      :key="dim"
      class="dimension-row flex items-center justify-between gap-4 py-2 px-3 rounded-lg hover:bg-surface-100 transition-colors duration-150"
    >
      <span class="dimension-label text-sm font-semibold text-ink min-w-[110px]">
        {{ dim.charAt(0).toUpperCase() + dim.slice(1) }}
      </span>
      <StarRating
        class="dimension-rating"
        :modelValue="modelValue[dim]"
        @update:modelValue="(v: number) => updateDimension(dim, v)"
      />
      <span class="text-sm font-bold text-primary-600 w-6 text-right">
        {{ modelValue[dim] || 0 }}
      </span>
    </div>
  </fieldset>
</template>
