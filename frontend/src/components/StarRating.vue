<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const props = withDefaults(defineProps<{
  modelValue: number
  readonly?: boolean
  size?: 'sm' | 'md'
  color?: string
}>(), { readonly: false, size: 'md', color: '#f0c040' })

const emit = defineEmits<{ 'update:modelValue': [value: number] }>()

const svgClass = props.size === 'sm' ? 'w-3 h-3' : 'w-4 h-4'
const gapClass = props.size === 'sm' ? 'gap-0' : 'gap-0.5'

function setRating(value: number) {
  if (!props.readonly) emit('update:modelValue', value)
}
</script>

<template>
  <div
    class="star-rating inline-flex items-center"
    :class="gapClass"
    :style="{ '--star-filled': color, '--star-empty': color + '30' }"
    role="radiogroup"
    :aria-label="t('ui.rating')"
  >
    <component
      v-for="i in 5"
      :key="i"
      :is="readonly ? 'span' : 'button'"
      :type="readonly ? undefined : 'button'"
      :class="[
        i <= modelValue ? 'star-filled' : 'star-empty',
        readonly ? 'star-readonly' : 'star-btn',
      ]"
      :aria-label="`${i} star${i !== 1 ? 's' : ''}`"
      :aria-checked="i === modelValue"
      :role="readonly ? undefined : 'radio'"
      @click="setRating(i)"
    >
      <!-- Sharp 5-point star (HeroIcon path, 24x24 viewBox) — no bezier curves -->
      <svg :class="svgClass" viewBox="0 0 24 24" :fill="i <= modelValue ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="1.5">
        <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
      </svg>
    </component>
  </div>
</template>

<style scoped>
.star-btn {
  @apply cursor-pointer p-0 rounded transition-all duration-150
         focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent;
  background: none;
  border: none;
}
.star-readonly {
  @apply p-0;
  background: none;
  border: none;
}
.star-filled {
  color: var(--star-filled, #f0c040);
}
.star-btn.star-filled:hover {
  filter: brightness(1.2);
}
.star-empty {
  color: var(--star-empty, rgba(176, 184, 196, 0.3));
}
.star-btn.star-empty:hover {
  color: var(--star-filled, #f0c040);
}
</style>
