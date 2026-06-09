<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader, FileDown, FileCode, Package } from 'lucide-vue-next'
import { parseMarkdown } from '../utils/markdown'
import { compileDownload } from '../api/compile'
import { useTauri } from '../composables/useTauri'

const { t } = useI18n()

const props = withDefaults(defineProps<{
  format: 'source' | 'compiled' | 'repo'
  content: string
  contentFormat?: string
  filename?: string
  commitHash?: string
  articleId?: string
  disabled?: boolean
  disabledReason?: string
  showLabel?: boolean
}>(), {
  contentFormat: 'markdown',
  disabled: false,
  showLabel: false,
})

const tauri = useTauri()

const downloading = ref(false)

const tooltipText = computed(() => {
  if (props.disabled && props.disabledReason) return props.disabledReason
  if (props.showLabel) return undefined
  if (props.format === 'repo') return 'Download repo (.git bundle)'
  if (props.format === 'source') {
    return props.contentFormat === 'typst' ? 'Download source (.typ)' : 'Download source (.md)'
  }
  return props.contentFormat === 'typst' ? 'Download compiled (.pdf)' : 'Download compiled (.html)'
})

async function handleDownload() {
  if (downloading.value || props.disabled) return
  downloading.value = true
  try {
    const base = (props.filename || 'article')
      .replace(/[/\\]/g, '-')
      .replace(/\.\./g, '')
      .replace(/[^a-zA-Z0-9 _-]/g, '')
      .replace(/\s+/g, '_')
      .replace(/_+/g, '_')
      .replace(/^[._-]+|[._-]+$/g, '')
      || 'article'

    const hashSuffix = props.commitHash ? `-${props.commitHash.slice(0, 7)}` : ''

    if (props.format === 'repo') {
      if (!props.articleId) return
      if (tauri.isTauri.value || tauri.isBrowserLocal.value) {
        // Tauri/local: Rust creates tar.gz, returns base64 → blob download
        const result = await tauri.exportArticle({ article_id: props.articleId })
        if (result && typeof result === 'string') {
          const binary = Uint8Array.from(atob(result), c => c.charCodeAt(0))
          const blob = new Blob([binary], { type: 'application/gzip' })
          const url = URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = url
          a.download = `${base}${hashSuffix}.tar.gz`
          a.click()
          URL.revokeObjectURL(url)
        }
      } else {
        // Web mode: server endpoint
        window.open(`/api/v1/articles/${props.articleId}/download/repo`, '_blank')
      }
      return
    }

    if (props.format === 'compiled' && props.contentFormat === 'typst') {
      if (tauri.isTauri.value || tauri.isBrowserLocal.value) {
        // Tauri/local: compile Typst → PDF via Rust sidecar (no REST backend needed)
        const base64 = await tauri.compileTypstPdf({ content: props.content })
        const binary = Uint8Array.from(atob(base64), c => c.charCodeAt(0))
        const pdfBlob = new Blob([binary], { type: 'application/pdf' })
        const url = URL.createObjectURL(pdfBlob)
        const a = document.createElement('a')
        a.href = url
        a.download = `${base}${hashSuffix}.pdf`
        a.click()
        URL.revokeObjectURL(url)
      } else {
        // Web mode: call server to compile → PDF
        const response = await compileDownload(props.content, 'typst')
        const pdfBlob = response.data instanceof Blob
          ? response.data
          : new Blob([response.data], { type: 'application/pdf' })
        const url = URL.createObjectURL(pdfBlob)
        const a = document.createElement('a')
        a.href = url
        a.download = `${base}${hashSuffix}.pdf`
        a.click()
        URL.revokeObjectURL(url)
      }
    } else {
      // Markdown compiled or source download — client-side
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

      const name = `${base}${hashSuffix}.${ext}`
      const blob = new Blob([data], {
        type: props.format === 'compiled' ? 'text/html' : 'text/plain',
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = name
      a.click()
      URL.revokeObjectURL(url)
    }
  } finally {
    setTimeout(() => { downloading.value = false }, 800)
  }
}
</script>

<template>
  <button
    :aria-label="format === 'repo'
      ? 'Download repo (.git bundle)'
      : format === 'source'
        ? (contentFormat === 'typst' ? 'Download source (.typ)' : 'Download source (.md)')
        : (contentFormat === 'typst' ? 'Download compiled (.pdf)' : 'Download compiled (.html)')"
    :data-tooltip="tooltipText"
    :disabled="downloading || disabled"
    class="flex items-center gap-1 rounded-md transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent disabled:hover:text-ink-muted"
    :class="showLabel
      ? 'px-2.5 py-1 text-xs text-ink-muted hover:text-ink hover:bg-[#21262d]'
      : 'justify-center w-8 h-8 rounded-lg text-ink-muted hover:text-ink hover:bg-[#21262d]'"
    @click="handleDownload"
  >
    <Loader v-if="downloading" class="w-4 h-4 animate-spin" stroke-width="2" />
    <template v-else>
      <FileCode v-if="format === 'source'" class="w-4 h-4" :class="{ 'w-3 h-3': showLabel }" stroke-width="2" />
      <FileDown v-else-if="format === 'compiled'" class="w-4 h-4" :class="{ 'w-3 h-3': showLabel }" stroke-width="2" />
      <Package v-else class="w-4 h-4" :class="{ 'w-3 h-3': showLabel }" stroke-width="2" />
      <span v-if="showLabel">{{ format === 'repo' ? 'Repo' : format === 'source' ? t('download.source') : (contentFormat === 'typst' ? 'PDF' : t('download.compiled')) }}</span>
    </template>
  </button>
</template>
