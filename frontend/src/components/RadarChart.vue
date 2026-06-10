<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps<{
  scores: { originality: number; rigor: number; completeness: number; pedagogy: number; impact: number }
}>()

const dims = ['originality', 'rigor', 'completeness', 'pedagogy', 'impact'] as const
const size = 200
const cx = size / 2
const cy = size / 2
const radius = 80

function angle(index: number, total: number) {
  return (Math.PI * 2 * index) / total - Math.PI / 2
}

const points = computed(() => {
  return dims.map((dim, i) => {
    const value = props.scores[dim] / 5
    const a = angle(i, dims.length)
    const r = radius * value
    return { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a), label: dim.charAt(0).toUpperCase() + dim.slice(1) }
  })
})

const polygonPoints = computed(() => points.value.map((p) => `${p.x},${p.y}`).join(' '))

const gridPolygons = computed(() => {
  const levels = [0.2, 0.4, 0.6, 0.8, 1.0]
  return levels.map((level) => {
    return dims
      .map((_, i) => {
        const a = angle(i, dims.length)
        const r = radius * level
        return `${cx + r * Math.cos(a)},${cy + r * Math.sin(a)}`
      })
      .join(' ')
  })
})

const axisLines = computed(() => {
  return dims.map((_, i) => {
    const a = angle(i, dims.length)
    return { x2: cx + radius * Math.cos(a), y2: cy + radius * Math.sin(a) }
  })
})
</script>

<template>
  <svg :width="size" :height="size" viewBox="0 0 200 200" class="radar-chart" role="img" :aria-label="t('ui.radarChart')">
    <!-- Grid -->
    <polygon
      v-for="(grid, gi) in gridPolygons"
      :key="gi"
      :points="grid"
      fill="none"
      class="stroke-gray-200"
      stroke-width="0.5"
    />
    <!-- Axes -->
    <line
      v-for="(line, li) in axisLines"
      :key="li"
      :x1="cx"
      :y1="cy"
      :x2="line.x2"
      :y2="line.y2"
      class="stroke-gray-200"
      stroke-width="0.5"
    />
    <!-- Data polygon -->
    <polygon :points="polygonPoints" class="fill-primary-600/20 stroke-primary-600" stroke-width="2" />
    <!-- Labels -->
    <text
      v-for="(pt, ti) in points"
      :key="ti"
      :x="pt.x"
      :y="pt.y - 6"
      text-anchor="middle"
      class="axis-label fill-ink-muted font-body"
      font-size="9"
    >{{ pt.label }}</text>
  </svg>
</template>
