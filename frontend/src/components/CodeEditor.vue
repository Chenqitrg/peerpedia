<script setup lang="ts">
import { shallowRef, computed } from 'vue'
import { Codemirror } from 'vue-codemirror'
import { markdown } from '@codemirror/lang-markdown'
import { oneDark } from '@codemirror/theme-one-dark'
import type { EditorView } from 'codemirror'

const props = defineProps<{
  modelValue: string
  format: 'markdown' | 'typst'
  placeholder?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const codemirrorView = shallowRef<EditorView>()

const extensions = computed(() => {
  const exts: any[] = [oneDark]
  if (props.format === 'markdown') {
    exts.push(markdown())
  }
  return exts
})

function onReady(view: EditorView) {
  codemirrorView.value = view
}

function onUpdate(value: string) {
  emit('update:modelValue', value)
}

defineExpose({ codemirrorView })
</script>

<template>
  <Codemirror
    v-if="format === 'markdown'"
    :model-value="modelValue"
    :extensions="extensions"
    :placeholder="placeholder"
    :indent-with-tab="true"
    :tab-size="2"
    @ready="onReady"
    @update:model-value="onUpdate"
  />
  <slot v-else name="typst-fallback" />
</template>
