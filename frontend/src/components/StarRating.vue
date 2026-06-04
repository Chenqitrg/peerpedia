<script setup lang="ts">
defineProps<{ modelValue: number }>()
const emit = defineEmits<{ 'update:modelValue': [value: number] }>()

function setRating(value: number) {
  emit('update:modelValue', value)
}
</script>

<template>
  <div class="star-rating flex items-center gap-0.5" role="radiogroup" aria-label="Rating">
    <button
      v-for="i in 5"
      :key="i"
      type="button"
      class="star-btn"
      :class="i <= modelValue ? 'star-filled' : 'star-empty'"
      :aria-label="`${i} star${i !== 1 ? 's' : ''}`"
      :aria-checked="i === modelValue"
      role="radio"
      @click="setRating(i)"
    >
      <svg class="w-6 h-6" viewBox="0 0 20 20" :fill="i <= modelValue ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="1.5">
        <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
      </svg>
    </button>
  </div>
</template>

<style scoped>
.star-btn {
  @apply cursor-pointer p-0.5 rounded transition-all duration-150
         focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-primary-500;
  background: none;
  border: none;
}
.star-filled {
  @apply text-star;
}
.star-filled:hover {
  @apply brightness-90;
}
.star-empty {
  @apply text-star-empty;
}
.star-empty:hover {
  @apply text-star;
}
</style>
