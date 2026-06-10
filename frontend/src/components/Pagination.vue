<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps<{
  page: number
  totalPages: number
}>()

const emit = defineEmits<{
  change: [page: number]
}>()
</script>

<template>
  <div
    v-if="totalPages > 1"
    class="flex items-center justify-center gap-2 pt-6 pb-4"
  >
    <button
      class="flex items-center justify-center w-8 h-8 rounded-lg text-xs font-mono
             text-ink-muted hover:text-ink hover:bg-[#21262d]
             disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
      :disabled="page <= 1"
      @click="emit('change', page - 1)"
      :aria-label="t('ui.previousPage')"
    >
      &lsaquo;
    </button>

    <button
      v-for="p in totalPages"
      :key="p"
      class="flex items-center justify-center w-8 h-8 rounded-lg text-xs font-mono
             transition-colors duration-200"
      :class="p === page
        ? 'bg-accent text-page font-bold'
        : 'text-ink-muted hover:text-ink hover:bg-[#21262d]'"
      @click="emit('change', p)"
    >
      {{ p }}
    </button>

    <button
      class="flex items-center justify-center w-8 h-8 rounded-lg text-xs font-mono
             text-ink-muted hover:text-ink hover:bg-[#21262d]
             disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
      :disabled="page >= totalPages"
      @click="emit('change', page + 1)"
      :aria-label="t('ui.nextPage')"
    >
      &rsaquo;
    </button>
  </div>
</template>
