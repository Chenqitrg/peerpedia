<script setup lang="ts">
import FiveDimForm from './FiveDimForm.vue'
import { X } from 'lucide-vue-next'

defineProps<{
  visible: boolean
  existingReview: boolean
  submitting: boolean
  error: string
  success: string
  modelValue: { originality: number; rigor: number; completeness: number; pedagogy: number; impact: number }
}>()

const emit = defineEmits<{
  'update:modelValue': [value: { originality: number; rigor: number; completeness: number; pedagogy: number; impact: number }]
  'submit': []
  'close': []
}>()

function onOverlayClick(e: MouseEvent) {
  if ((e.target as HTMLElement).classList.contains('modal-overlay')) {
    emit('close')
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="modal-overlay fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm"
      @click="onOverlayClick"
    >
      <div class="w-full max-w-md bg-card border border-divider rounded-xl shadow-2xl p-6 animate-fade-in">
        <!-- Header -->
        <div class="flex items-center justify-between mb-5">
          <h3 class="text-lg font-semibold text-ink">
            {{ existingReview ? 'Update Your Review' : 'Write a Review' }}
          </h3>
          <button
            class="flex items-center justify-center w-6 h-6 rounded text-ink-muted hover:text-ink hover:bg-[#21262d] transition-colors"
            @click="emit('close')"
          >
            <X class="w-4 h-4" stroke-width="2" />
          </button>
        </div>

        <!-- Five-dim form -->
        <FiveDimForm
          :modelValue="modelValue"
          @update:modelValue="(v) => emit('update:modelValue', v)"
        />

        <!-- Messages -->
        <p v-if="error" class="text-xs text-danger mt-4">{{ error }}</p>
        <p v-if="success" class="text-xs text-green-400 mt-4">{{ success }}</p>

        <!-- Actions -->
        <div class="flex items-center justify-end gap-3 mt-5 pt-4 border-t border-divider">
          <button
            class="px-4 py-1.5 text-xs font-semibold text-ink-muted hover:text-ink hover:bg-[#21262d] rounded-lg transition-colors"
            @click="emit('close')"
          >
            Cancel
          </button>
          <button
            class="px-4 py-1.5 text-xs font-semibold bg-accent text-page rounded-lg
                   hover:brightness-110 transition-all duration-200 disabled:opacity-50"
            :disabled="submitting"
            @click="emit('submit')"
          >
            {{ submitting ? 'Submitting...' : (existingReview ? 'Update Review' : 'Submit Review') }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
