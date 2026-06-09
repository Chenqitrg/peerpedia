<script setup lang="ts">
import { shallowRef, computed } from 'vue'
import { Codemirror } from 'vue-codemirror'
import { markdown } from '@codemirror/lang-markdown'
import { oneDark } from '@codemirror/theme-one-dark'
import { EditorView } from 'codemirror'
import type { Extension } from '@codemirror/state'

const props = defineProps<{
  modelValue: string
  format: 'markdown' | 'typst'
  placeholder?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const codemirrorView = shallowRef<EditorView>()

const extensions = computed<Extension[]>(() => {
  const exts: Extension[] = [oneDark]
  exts.push(markdown())
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
  <div v-if="format === 'markdown'" class="flex-1 w-full font-mono cm-wrapper">
    <Codemirror
      :model-value="modelValue"
      :extensions="extensions"
      :placeholder="placeholder"
      :indent-with-tab="true"
      :tab-size="2"
      @ready="onReady"
      @update:model-value="onUpdate"
    />
  </div>
  <slot v-else name="typst-fallback" />
</template>

<style>
/* Override oneDark background to match app page bg */
.cm-wrapper .cm-editor {
  background: #0d1117;
}
.cm-wrapper .cm-editor .cm-scroller {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}
</style>
