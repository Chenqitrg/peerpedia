<script setup lang="ts">
import { shallowRef, computed } from 'vue'
import { Codemirror } from 'vue-codemirror'
import { markdown } from '@codemirror/lang-markdown'
import { oneDark } from '@codemirror/theme-one-dark'
import { EditorView } from 'codemirror'
import { StreamLanguage } from '@codemirror/language'
import { tags } from '@lezer/highlight'
import type { Extension } from '@codemirror/state'

// Pure-JavaScript Typst syntax highlighting via StreamLanguage.
// Avoids WASM dependency which fails in WKWebView (Tauri on macOS).
const typstLanguage = StreamLanguage.define({
  token(stream) {
    // Line comment
    if (stream.match('//')) {
      stream.skipToEnd()
      return 'lineComment'
    }
    // Block comment
    if (stream.match('/*')) {
      while (!stream.eol()) {
        if (stream.match('*/')) return 'blockComment'
        stream.next()
      }
      return 'blockComment'
    }
    // Heading — leading = signs
    if (stream.sol()) {
      if (stream.match(/^=+/)) {
        return 'heading'
      }
    }
    // Math mode $...$
    if (stream.match('$')) {
      while (!stream.eol() && !stream.match('$')) {
        if (stream.peek() === '\\') stream.next()
        stream.next()
      }
      return 'string'
    }
    // Function/macro call #identifier
    if (stream.match('#')) {
      if (stream.match(/[a-zA-Z_][a-zA-Z0-9_-]*/)) {
        return 'keyword'
      }
      stream.next()
      return null
    }
    // Content block [...]
    if (stream.match('[')) {
      return 'bracket'
    }
    if (stream.match(']')) {
      return 'bracket'
    }
    // Label <...>
    if (stream.match('<')) {
      if (stream.match(/[a-zA-Z_][a-zA-Z0-9_-]*/)) {
        if (stream.match('>')) return 'labelName'
      }
      stream.next()
      return null
    }
    // Reference @name
    if (stream.match('@')) {
      stream.match(/[a-zA-Z_][a-zA-Z0-9_-]*/)
      return 'labelName'
    }
    // *bold* and _italic_
    if (stream.match('*')) {
      if (stream.peek() !== '*') {
        while (!stream.eol() && stream.peek() !== '*') {
          stream.next()
        }
        stream.match('*')
        return 'strong'
      }
      stream.next()
      return null
    }
    if (stream.match('_')) {
      while (!stream.eol() && stream.peek() !== '_') {
        stream.next()
      }
      stream.match('_')
      return 'emphasis'
    }
    // String literal
    if (stream.match('"')) {
      while (!stream.eol() && !stream.match('"')) {
        if (stream.peek() === '\\') stream.next()
        stream.next()
      }
      return 'string'
    }
    // Set/show rule
    if (stream.match(/#(set|show)\b/)) {
      return 'keyword'
    }
    stream.next()
    return null
  },
  languageData: {
    closeBrackets: { brackets: ['[', '{', '(', '"', '$'] },
    commentTokens: { line: '//', block: { open: '/*', close: '*/' } },
  },
})

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
  if (props.format === 'typst') {
    exts.push(typstLanguage)
  } else {
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
  <div class="flex-1 w-full font-mono cm-wrapper">
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
