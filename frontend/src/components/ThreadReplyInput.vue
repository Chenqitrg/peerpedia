<script setup lang="ts">
import { Send } from 'lucide-vue-next'

const props = withDefaults(defineProps<{
  modelValue: string
  placeholder?: string
  disabled?: boolean
}>(), { placeholder: 'Reply...', disabled: false })

const emit = defineEmits<{
  'update:modelValue': [value: string]
  send: []
}>()

function handleSend() {
  if (!props.modelValue.trim() || props.disabled) return
  emit('send')
}
</script>

<template>
  <div class="flex items-center gap-2 pt-1">
    <input
      :value="modelValue"
      type="text"
      :placeholder="disabled ? 'Sending...' : placeholder"
      class="flex-1 bg-[#0d1117] border border-divider rounded-lg px-3 py-1.5 text-xs
             text-ink placeholder:text-ink-muted/50
             focus:outline-none focus:ring-1 focus:ring-accent"
      @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
      @keyup.enter="handleSend"
    />
    <button
      class="flex items-center justify-center w-7 h-7 rounded-lg
             text-ink-muted hover:text-accent hover:bg-accent/10
             transition-colors duration-200"
      :disabled="!modelValue.trim() || disabled"
      @click="handleSend"
    >
      <Send class="w-3.5 h-3.5" stroke-width="2" />
    </button>
  </div>
</template>
