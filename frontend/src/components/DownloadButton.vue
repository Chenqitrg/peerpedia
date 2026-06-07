<script setup lang="ts">
import { ref } from 'vue'
import { Loader, FileDown, FileText } from 'lucide-vue-next'
import { parseMarkdown } from '../utils/markdown'

const props = withDefaults(defineProps<{
  format: 'source' | 'compiled'
  content: string
  contentFormat?: string
  filename?: string
  disabled?: boolean
}>(), {
  contentFormat: 'markdown',
  disabled: false,
})

const downloading = ref(false)

async function handleDownload() {
  if (downloading.value || props.disabled) return
  downloading.value = true
  try {
    const ext = props.format === 'source'
      ? (props.contentFormat === 'typst' ? '.typ' : '.md')
      : '.html'

    let data: string
    if (props.format === 'compiled' && props.contentFormat === 'markdown') {
      const html = parseMarkdown(props.content)
      data = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${props.filename || 'Article'}</title></head><body>${html}</body></html>`
    } else {
      data = props.content
    }

    const name = props.filename
      ? `${props.filename.replace(/[^a-zA-Z0-9一-鿿_-]/g, '_')}.${ext === '.html' ? 'html' : ext.replace('.', '')}`
      : `article.${ext === '.html' ? 'html' : ext.replace('.', '')}`

    const blob = new Blob([data], {
      type: props.format === 'compiled' ? 'text/html' : 'text/plain',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = name
    a.click()
    URL.revokeObjectURL(url)
  } finally {
    setTimeout(() => { downloading.value = false }, 800)
  }
}
</script>

<template>
  <button
    :aria-label="format === 'source' ? 'Download source' : 'Download HTML'"
    :title="format === 'source' ? 'Download source' : 'Download HTML'"
    :disabled="downloading || disabled"
    class="flex items-center gap-1 px-2.5 py-1 text-xs text-ink-muted hover:text-ink hover:bg-[#21262d] rounded-md transition-colors cursor-pointer disabled:opacity-50"
    @click="handleDownload"
  >
    <Loader v-if="downloading" class="w-3 h-3 animate-spin" stroke-width="2" />
    <FileDown v-else-if="format === 'source'" class="w-3 h-3" stroke-width="2" />
    <FileText v-else class="w-3 h-3" stroke-width="2" />
    {{ downloading ? '...' : (format === 'source' ? 'Source' : 'HTML') }}
  </button>
</template>
