<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader, FileDown, FileCode } from 'lucide-vue-next'
import { parseMarkdown } from '../utils/markdown'

const { t } = useI18n()

const props = withDefaults(defineProps<{
  format: 'source' | 'compiled'
  content: string
  contentFormat?: string
  filename?: string
  commitHash?: string
  disabled?: boolean
  disabledReason?: string
  showLabel?: boolean
}>(), {
  contentFormat: 'markdown',
  disabled: false,
  showLabel: false,
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

    const base = (props.filename || 'article')
      .replace(/[/\\]/g, '-')
      .replace(/\.\./g, '')
      .replace(/[^a-zA-Z0-9 _-]/g, '')
      .replace(/\s+/g, '_')
      .replace(/_+/g, '_')
      .replace(/^[._-]+|[._-]+$/g, '')
      || 'article'

    // Append short commit hash if available
    const hashSuffix = props.commitHash ? `-${props.commitHash.slice(0, 7)}` : ''
    const suffix = props.format === 'compiled' ? 'html' : (props.contentFormat === 'typst' ? 'typ' : 'md')
    const name = `${base}${hashSuffix}.${suffix}`

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
    :aria-label="format === 'source' ? 'Download source (.md)' : 'Download compiled (.html)'"
    :title="(disabled && disabledReason) ? disabledReason : (showLabel ? undefined : (format === 'source' ? 'Download source (.md)' : 'Download compiled (.html)'))"
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
      <FileDown v-else class="w-4 h-4" :class="{ 'w-3 h-3': showLabel }" stroke-width="2" />
      <span v-if="showLabel">{{ format === 'source' ? t('download.source') : t('download.compiled') }}</span>
    </template>
  </button>
</template>
