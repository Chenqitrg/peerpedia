<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { useArticleStore } from '../stores/useArticleStore'
import { useUserStore } from '../stores/useUserStore'
import { useDraftPersistence } from '../composables/useDraftPersistence'
import { parseMarkdown } from '../utils/markdown'
import SelfReviewPanel from '../components/SelfReviewPanel.vue'
import {
  Bookmark,
  BookmarkCheck,
  Eye,
  EyeOff,
  FileDown,
  Play,
  Save,
  Send,
  FileText,
} from 'lucide-vue-next'


const route = useRoute()
const router = useRouter()
const articleStore = useArticleStore()
const userStore = useUserStore()
const { t } = useI18n()

import { getArticleSource } from '../api/articles'
import type { ArticleCreatePayload, ArticleUpdatePayload } from '../api/types'

const editId = computed(() => route.params.id as string | undefined)
const isEdit = computed(() => !!editId.value)

// Editor state
const title = ref('')
const content = ref('')
const format = ref<'markdown' | 'typst'>('markdown')
const previewHtml = ref('')
const previewLoading = ref(false)
const compiling = ref(false)

// Side panel
const showSelfReview = ref(false)
const commitMsg = ref('')
const scores = ref({ originality: 3, rigor: 3, completeness: 3, pedagogy: 3, impact: 3 })
const keywords = ref('')
const categories = ref('')
const abstract = ref('')
const contributions = ref<Record<string, number>>({})

// UI state
const submitting = ref(false)
const errorMsg = ref('')
const successMsg = ref('')
const savedMsg = ref(false)
const showPreview = ref(true)

// Split panel resize
const splitRatio = ref(50)
const isDragging = ref(false)
const splitterEl = ref<HTMLElement | null>(null)

function onSplitterMouseDown(e: MouseEvent) {
  isDragging.value = true
  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onMouseUp)
  e.preventDefault()
}
function onMouseMove(e: MouseEvent) {
  if (!isDragging.value) return
  const container = splitterEl.value?.parentElement
  if (!container) return
  const rect = container.getBoundingClientRect()
  const pct = ((e.clientX - rect.left) / rect.width) * 100
  splitRatio.value = Math.min(80, Math.max(20, pct))
}
function onMouseUp() {
  isDragging.value = false
  document.removeEventListener('mousemove', onMouseMove)
  document.removeEventListener('mouseup', onMouseUp)
}

const DRAFT_KEY = computed(() => `editor-draft-${editId.value || 'new'}`)
const DRAFT_ID_KEY = computed(() => `editor-draft-id-${editId.value || 'new'}`)
const totalContribution = computed(() =>
  Object.values(contributions.value).reduce((sum, v) => sum + v, 0)
)

// Draft persistence — Tauri IPC when available, REST + localStorage fallback.
const draftPersistence = useDraftPersistence()
const currentDraftId = ref<string | undefined>(
  editId.value as string | undefined || localStorage.getItem(DRAFT_ID_KEY.value) || undefined
)

onMounted(() => {
  if (isEdit.value) {
    loadExistingArticle()
  } else {
    restoreDraft()
  }
})

async function loadExistingArticle() {
  try {
    await articleStore.fetchArticle(editId.value!)
    const a = articleStore.currentArticle
    if (a) {
      title.value = a.title || ''
    }
    // Load source content from git repo (needed for forks and editing existing articles)
    const src = await getArticleSource(editId.value!)
    content.value = src.content
    format.value = src.format as 'markdown' | 'typst'
  } catch (e: any) {
    errorMsg.value = 'Failed to load article'
  }
}

async function restoreDraft() {
  // Restore the Tauri draft ID from localStorage (persisted across refreshes).
  const savedId = localStorage.getItem(DRAFT_ID_KEY.value)
  if (savedId) currentDraftId.value = savedId

  // Try Tauri persistence first with the real draft ID.
  const accountId = userStore.viewer?.id || 'local'
  const lookupId = currentDraftId.value || DRAFT_KEY.value
  const result = await draftPersistence.load(lookupId)

  if (result && result.content !== undefined) {
    title.value = result.title || ''
    content.value = result.content || ''
    format.value = (result.format as 'markdown' | 'typst') || 'markdown'
  }

  // Also try localStorage as backup.
  const saved = localStorage.getItem(DRAFT_KEY.value)
  if (saved) {
    try {
      const parsed = JSON.parse(saved)
      if (!title.value) title.value = parsed.title || ''
      if (!content.value) content.value = parsed.content || ''
      if (!format.value || format.value === 'markdown') format.value = parsed.format || 'markdown'
      scores.value = parsed.scores || { originality: 3, rigor: 3, completeness: 3, pedagogy: 3, impact: 3 }
      keywords.value = parsed.keywords || ''
      categories.value = parsed.categories || ''
      abstract.value = parsed.abstract || ''
    } catch {
      // ignore corrupt draft
    }
  }
}

async function saveDraft() {
  const accountId = userStore.viewer?.id || 'local'

  // Persist via Tauri or REST (handled by useDraftPersistence).
  const result = await draftPersistence.save(
    accountId,
    title.value,
    content.value,
    format.value,
    currentDraftId.value,
  )
  if (result && result.id) {
    currentDraftId.value = result.id
    // Persist the Tauri draft ID so it survives page refresh.
    localStorage.setItem(DRAFT_ID_KEY.value, result.id)
  }

  // Also save to localStorage as offline backup (works in both modes).
  const draft = {
    title: title.value,
    content: content.value,
    format: format.value,
    scores: scores.value,
    keywords: keywords.value,
    categories: categories.value,
    abstract: abstract.value,
  }
  localStorage.setItem(DRAFT_KEY.value, JSON.stringify(draft))
  savedMsg.value = true
  setTimeout(() => { savedMsg.value = false }, 2000)
}

async function handleCompile() {
  if (!content.value.trim()) return
  compiling.value = true
  previewHtml.value = ''
  errorMsg.value = ''
  try {
    if (format.value === 'markdown') {
      previewHtml.value = parseMarkdown(content.value)
    } else {
      // Typst: requires Tauri sidecar (Slice 2) for local compilation.
      // Web: on-going — no browser-native Typst→HTML path yet.
      previewHtml.value = '<p class="text-ink-muted text-sm">Typst preview available in Tauri desktop (Slice 2). Write in Markdown for live preview.</p>'
    }
  } catch (e: any) {
    errorMsg.value = e.message || 'Compile failed'
  } finally {
    compiling.value = false
  }
}

async function handleSaveDraft() {
  await saveDraft()
  if (!userStore.viewer) return
  if (!editId.value) return  // can't save unsaved article to backend
  if (!commitMsg.value.trim()) {
    errorMsg.value = 'Commit message is required'
    return
  }
  submitting.value = true
  errorMsg.value = ''
  successMsg.value = ''
  try {
    await articleStore.updateArticle(editId.value, {
      title: title.value,
      content: content.value,
      commit_message: commitMsg.value.trim(),
      publish: false,
    })
    savedMsg.value = true
    setTimeout(() => { savedMsg.value = false }, 2000)
  } catch (e: any) {
    errorMsg.value = e.response?.data?.detail || 'Save failed'
  } finally {
    submitting.value = false
  }
}

function handlePublish() {
  if (userStore.viewer && !(userStore.viewer.id in contributions.value)) {
    // Only initialize contributions if not already set — preserves user adjustments
    contributions.value = { ...contributions.value, [userStore.viewer.id]: 100 }
  }
  showSelfReview.value = true
}

async function handleSubmitToPool() {
  if (!content.value.trim()) {
    errorMsg.value = 'Content is required'
    return
  }
  if (!commitMsg.value.trim()) {
    errorMsg.value = 'Commit message is required — summarize your changes'
    return
  }
  if (!userStore.viewer) {
    errorMsg.value = 'Please log in first'
    return
  }

  submitting.value = true
  errorMsg.value = ''
  successMsg.value = ''

  try {
    const body: ArticleCreatePayload | ArticleUpdatePayload = {
      title: title.value,
      abstract: abstract.value || title.value,
      content: content.value,
      format: format.value,
      commit_message: commitMsg.value.trim(),
      self_review: { ...scores.value },
      authors: [userStore.viewer.id],
      publish: true,
      keywords: keywords.value ? keywords.value.split(',').map((k: string) => k.trim()).filter(Boolean) : [],
      categories: categories.value ? categories.value.split(',').map((c: string) => c.trim()).filter(Boolean) : [],
      contributions: { ...contributions.value },
    }

    let result: { id: string }
    if (isEdit.value) {
      result = await articleStore.updateArticle(editId.value!, body)
      successMsg.value = 'Article updated and submitted to pool!'
    } else {
      result = await articleStore.createArticle(body)
      successMsg.value = 'Article created and submitted to pool!'
      localStorage.removeItem(DRAFT_KEY.value)
      setTimeout(() => {
        router.push(`/articles/${result.id}`)
      }, 1500)
    }
    showSelfReview.value = false
  } catch (e: any) {
    errorMsg.value = e.response?.data?.detail || 'Submission failed'
  } finally {
    submitting.value = false
  }
}

function handleDownload(dlFormat: 'source' | 'pdf') {
  if (editId.value) {
    // Saved article: use the download endpoints
    window.open(`/api/v1/articles/${editId.value}/download/${dlFormat}`, '_blank')
  } else if (dlFormat === 'pdf') {
    // New article PDF: call compile-download endpoint
    handleCompileDownload()
  } else {
    // New article source: download raw content as file
    const ext = format.value === 'typst' ? '.typ' : '.md'
    const blob = new Blob([content.value], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `article${ext}`
    a.click()
    URL.revokeObjectURL(url)
  }
}

async function handleCompileDownload() {
  if (!content.value.trim()) {
    errorMsg.value = 'Nothing to download — editor is empty'
    return
  }
  if (format.value === 'markdown') {
    // Render markdown to HTML and open in a new window for browser print → PDF.
    const html = parseMarkdown(content.value)
    const printWindow = window.open('', '_blank')
    if (printWindow) {
      printWindow.document.write(`<!DOCTYPE html><html><head><title>${title.value || 'Article'}</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
        <style>body{max-width:800px;margin:2rem auto;font-family:serif;line-height:1.6;color:#1a1a1a;}
        pre{background:#f5f5f5;padding:1rem;border-radius:4px;overflow-x:auto;}</style></head>
        <body>${html}</body></html>`)
      printWindow.document.close()
      setTimeout(() => printWindow.print(), 500)
    }
  } else {
    // Typst PDF: requires Tauri sidecar (Slice 2). Web: on-going.
    errorMsg.value = 'Typst PDF export available in Tauri desktop (Slice 2). Markdown articles can print to PDF via browser.'
  }
}

defineExpose({ contributions, handlePublish, showSelfReview, totalContribution })
</script>

<template>
  <div class="editor-page flex flex-col h-[calc(100vh-6rem)] animate-fade-in">
    <!-- Top toolbar -->
    <div class="flex items-center justify-between px-4 py-2 bg-card border border-divider rounded-t-lg mb-0">
      <div class="flex items-center gap-3 flex-1 min-w-0">
        <!-- Title input (editable only on create) -->
        <input
          v-if="!isEdit"
          v-model="title"
          type="text"
          placeholder="Article title..."
          class="flex-1 min-w-0 bg-transparent border-none text-base font-heading font-semibold text-ink
                 placeholder:text-ink-muted/50 focus:outline-none"
        />
        <span
          v-else
          class="text-base font-heading font-semibold text-ink truncate"
        >
          {{ title || 'Untitled' }}
        </span>
      </div>

      <div class="flex items-center gap-1.5 shrink-0">
        <!-- Draft save -->
        <div class="relative">
          <button
            class="flex items-center justify-center w-8 h-8 rounded-lg
                   text-ink-muted hover:text-ink hover:bg-[#21262d]
                   transition-colors duration-200"
            :aria-label="t('editor.saveDraft')"
            :title="t('editor.saveDraft')"
            :disabled="submitting"
            @click="handleSaveDraft"
          >
            <Save class="w-4 h-4" stroke-width="2" />
          </button>
          <span
            v-if="savedMsg"
            class="absolute -bottom-6 left-1/2 -translate-x-1/2 text-xs text-success whitespace-nowrap"
          >
            Saved
          </span>
        </div>

        <!-- Format toggle -->
        <div class="flex items-center bg-[#0d1117] border border-divider rounded-lg overflow-hidden ml-1">
          <button
            class="px-2.5 py-1 text-xs font-mono transition-colors"
            :class="format === 'markdown'
              ? 'bg-accent text-[#0d1117] font-semibold'
              : 'text-ink-muted hover:text-ink'"
            @click="format = 'markdown'"
          >
            MD
          </button>
          <button
            class="px-2.5 py-1 text-xs font-mono transition-colors"
            :class="format === 'typst'
              ? 'bg-accent text-[#0d1117] font-semibold'
              : 'text-ink-muted hover:text-ink'"
            @click="format = 'typst'"
          >
            Typst
          </button>
        </div>

        <div class="w-px h-5 bg-divider mx-1" />

        <!-- Toggle preview -->
        <button
          class="flex items-center justify-center w-8 h-8 rounded-lg
                 text-ink-muted hover:text-ink hover:bg-[#21262d]
                 transition-colors duration-200"
          :aria-label="showPreview ? 'Hide preview' : 'Show preview'"
          :title="showPreview ? 'Hide preview' : 'Show preview'"
          @click="showPreview = !showPreview"
        >
          <Eye v-if="showPreview" class="w-4 h-4" stroke-width="2" />
          <EyeOff v-else class="w-4 h-4" stroke-width="2" />
        </button>

        <!-- Compile -->
        <button
          class="flex items-center justify-center w-8 h-8 rounded-lg
                 text-ink-muted hover:text-accent hover:bg-accent/10
                 transition-colors duration-200"
          :aria-label="t('editor.compile')"
          :title="t('editor.compile')"
          :disabled="compiling || !content.trim()"
          @click="handleCompile"
        >
          <Play class="w-4 h-4" stroke-width="2" />
        </button>

        <!-- Download source button (left side) -->
        <button
          class="flex items-center justify-center w-8 h-8 rounded-lg
                 text-ink-muted hover:text-ink hover:bg-[#21262d]
                 transition-colors duration-200"
          :aria-label="t('editor.typst')"
          :title="t('editor.typst')"
          @click="handleDownload('source')"
        >
          <FileDown class="w-4 h-4" stroke-width="2" />
        </button>

        <!-- Download PDF button (right side) -->
        <button
          class="flex items-center justify-center w-8 h-8 rounded-lg
                 text-ink-muted hover:text-ink hover:bg-[#21262d]
                 transition-colors duration-200"
          :aria-label="t('editor.download')"
          :title="t('editor.download')"
          @click="handleDownload('pdf')"
        >
          <FileText class="w-4 h-4" stroke-width="2" />
        </button>

        <div class="w-px h-5 bg-divider mx-1" />

        <!-- Publish button -->
        <button
          class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold
                 bg-accent text-[#0d1117] rounded-lg
                 hover:brightness-110 transition-all duration-200"
          :disabled="submitting"
          @click="handlePublish"
        >
          <Send class="w-3.5 h-3.5" stroke-width="2" />
          {{ isEdit ? t('editor.submitPool') : t('editor.publish') }}
        </button>
      </div>
    </div>

    <!-- Messages -->
    <div v-if="errorMsg" class="px-4 py-2 text-xs text-ink-muted bg-card border-x border-divider">
      {{ errorMsg }}
    </div>
    <div v-if="successMsg" class="px-4 py-2 text-xs text-success bg-card border-x border-divider">
      {{ successMsg }}
    </div>

    <!-- Split editor/preview -->
    <div class="flex flex-1 border-x border-divider overflow-hidden">
      <!-- Editor area (left) -->
      <div
        class="flex flex-col"
        :style="{ width: showPreview ? `${splitRatio}%` : '100%' }"
      >
        <textarea
          v-model="content"
          class="flex-1 w-full bg-[#0d1117] text-ink font-mono text-sm leading-relaxed
                 p-4 resize-none border-none focus:outline-none
                 placeholder:text-ink-muted/30"
          :placeholder="format === 'markdown'
            ? '# Title\n\nWrite your article in Markdown...'
            : '= Title\n\nWrite your article in Typst...'"
          spellcheck="false"
        />
      </div>

      <!-- Draggable divider -->
      <div
        v-if="showPreview"
        ref="splitterEl"
        class="w-1 bg-divider cursor-col-resize hover:bg-accent/50 transition-colors shrink-0 relative"
        :class="{ 'bg-accent': isDragging }"
        @mousedown="onSplitterMouseDown"
      />

      <!-- Preview area (right) -->
      <div
        v-if="showPreview"
        class="flex flex-col overflow-hidden"
        :style="{ width: `${100 - splitRatio}%` }"
      >
        <div class="flex-1 overflow-y-auto bg-[#0d1117] p-4">
          <div v-if="compiling" class="flex items-center justify-center h-full text-ink-muted text-sm">
            Compiling...
          </div>
          <div
            v-else-if="previewHtml"
            class="prose-custom max-w-none"
            v-html="previewHtml"
          />
          <div
            v-else
            class="flex items-center justify-center h-full text-ink-muted/40 text-xs"
          >
            {{ t('editor.preview') }} <Play class="w-3 h-3 inline mx-1" stroke-width="2" /> 
          </div>
        </div>
      </div>
    </div>

    <!-- Bottom bar -->
    <div class="flex items-center justify-between px-4 py-1.5 bg-card border border-divider rounded-b-lg text-xs text-ink-muted">
      <span>{{ format.toUpperCase() }}</span>
      <span>{{ content.length }} characters</span>
    </div>

    <!-- Self-review panel -->
    <SelfReviewPanel
      v-model="showSelfReview"
      v-model:commit-msg="commitMsg"
      v-model:scores="scores"
      v-model:keywords="keywords"
      v-model:categories="categories"
      v-model:abstract="abstract"
      v-model:contributions="contributions"
      :total-contribution="totalContribution"
      :submitting="submitting"
      @submit="handleSubmitToPool"
    />
  </div>
</template>
