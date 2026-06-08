<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { useOffline } from '../composables/useOffline'
import { useArticleStore } from '../stores/useArticleStore'
import { useUserStore } from '../stores/useUserStore'
import { useDraftPersistence } from '../composables/useDraftPersistence'
import { useSplitPane } from '../composables/useSplitPane'
import { useTauri } from '../composables/useTauri'
import { loadString, saveString, saveJSON, remove } from '../composables/useLocalStorage'
import { parseMarkdown } from '../utils/markdown'
import DownloadButton from '../components/DownloadButton.vue'
import SelfReviewPanel from '../components/SelfReviewPanel.vue'
import {
  ArrowLeft,
  Bookmark,
  BookmarkCheck,
  Eye,
  EyeOff,
  GitCommitHorizontal,
  History,
  Play,
  Save,
  Send,
} from 'lucide-vue-next'


const route = useRoute()
const router = useRouter()
const articleStore = useArticleStore()
const userStore = useUserStore()
const { t } = useI18n()
const { canWrite, getFallback } = useOffline()

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
const commitHash = ref('')
// Track saved state to detect unsaved edits
const savedContent = ref('')
const savedTitle = ref('')
const isClean = computed(() => content.value === savedContent.value && title.value === savedTitle.value)

/** True after first save — enables download per design doc: '只要保存过，就应该是亮的'.
 *  Uses currentDraftId (set after first successful save) instead of commitHash,
 *  because git commit may not always succeed (e.g., running before login). */
const hasSaved = computed(() => !!currentDraftId.value || !!commitHash.value)

// Split panel resize
const { splitRatio, splitterEl, isDragging, onSplitterMouseDown } = useSplitPane()

const draftUid = computed(() => userStore.viewer?.id || 'anonymous')
const DRAFT_KEY = computed(() => `editor-draft-${draftUid.value}-${editId.value || 'new'}`)
const DRAFT_ID_KEY = computed(() => `editor-draft-id-${draftUid.value}-${editId.value || 'new'}`)
const totalContribution = computed(() =>
  Object.values(contributions.value).reduce((sum, v) => sum + v, 0)
)

// Draft persistence — Tauri IPC when available, REST + localStorage fallback.
const draftPersistence = useDraftPersistence()
const tauri = useTauri()
const currentDraftId = ref<string | undefined>(
  isEdit.value ? (editId.value as string | undefined) : undefined
)

onMounted(() => {
  if (isEdit.value) {
    loadExistingArticle()
  } else {
    // New article: do NOT restore DRAFT_ID_KEY from localStorage — that would
    // resurrect a draft from a previous session when the user explicitly
    // clicked "New Article". Drafts are accessible from the UserPage profile.
    // The save button will create a fresh draft on first click.
    remove(DRAFT_ID_KEY.value)
    remove(DRAFT_KEY.value)
    currentDraftId.value = undefined
  }
})

async function loadExistingArticle() {
  // 1. Try REST API first.
  try {
    await articleStore.fetchArticle(editId.value!)
    const a = articleStore.currentArticle
    if (a) {
      title.value = a.title || ''
      commitHash.value = a.commit_hash || ''
    }
    const src = await getArticleSource(editId.value!)
    content.value = src.content
    format.value = src.format as 'markdown' | 'typst'
    savedContent.value = src.content
    savedTitle.value = title.value
    return
  } catch (e: any) {
    // 2. In Tauri/dev-mock mode, fall back to local draft storage.
    if (tauri.isTauri.value || tauri.isBrowserLocal.value) {
      const accountId = userStore.viewer?.id || 'local'
      const draft = await draftPersistence.load(editId.value!, accountId)
      if (draft && draft.content !== undefined) {
        title.value = draft.title || ''
        content.value = draft.content || ''
        format.value = (draft.format as 'markdown' | 'typst') || 'markdown'
        savedContent.value = content.value
        savedTitle.value = title.value
        // Populate commit hash from local git
        try {
          const history = await tauri.gitHistory({ article_id: editId.value! })
          if (history && !('error' in history) && Array.isArray(history) && history.length > 0) {
            commitHash.value = history[0].hash
          }
        } catch { /* optional */ }
        return
      }
    }
    errorMsg.value = 'Failed to load article'
  }
}

async function restoreDraft() {
  // Restore the Tauri draft ID from localStorage (persisted across refreshes).
  const savedId = loadString(DRAFT_ID_KEY.value)
  if (savedId) currentDraftId.value = savedId

  // Only restore if we have a real draft ID (not a new document).
  if (!currentDraftId.value) return

  // Try Tauri persistence first with the real draft ID.
  const accountId = userStore.viewer?.id || 'local'
  const result = await draftPersistence.load(currentDraftId.value, accountId)

  if (result && !('error' in result) && result.content !== undefined) {
    title.value = result.title || ''
    content.value = result.content || ''
    format.value = (result.format as 'markdown' | 'typst') || 'markdown'
  } else {
    // Stored draft ID no longer exists (e.g., deleted or session expired).
    // Clear the stale keys so next visit starts fresh.
    remove(DRAFT_ID_KEY.value)
    remove(DRAFT_KEY.value)
    currentDraftId.value = undefined
  }
}

async function saveDraft() {
  const accountId = userStore.viewer?.id || 'local'
  const author = userStore.viewer?.name || userStore.viewer?.username || 'local'

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
    saveString(DRAFT_ID_KEY.value, result.id)

    // In local mode, save = git commit.
    if (tauri.isTauri.value || tauri.isBrowserLocal.value) {
      const msg = commitMsg.value.trim() || 'Save draft'
      try {
        if (!currentDraftId.value || currentDraftId.value === result.id) {
          // Check if git repo exists; if not, init
          const history = await tauri.gitHistory({ article_id: result.id })
          if (history && !('error' in history) && Array.isArray(history) && history.length > 0) {
            const r = await tauri.gitCommit({ article_id: result.id, content: content.value, format: format.value, commit_message: msg, author })
            if (r && r.hash) commitHash.value = r.hash
          } else {
            const r = await tauri.gitInit({ article_id: result.id, content: content.value, format: format.value, commit_message: msg, author })
            if (r && r.hash) commitHash.value = r.hash
          }
        }
      } catch { /* git ops optional — draft is still saved */ }
    }
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
  saveJSON(DRAFT_KEY.value, draft)
  savedContent.value = content.value
  savedTitle.value = title.value
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
    } else if (tauri.isTauri.value || tauri.isBrowserLocal.value) {
      // Typst: use Tauri local compilation
      const svg = await tauri.compileTypst({
        content: content.value,
        format: format.value,
      })
      if (svg && !('error' in svg)) {
        // Wrap SVG for display in the preview area
        previewHtml.value = `<div class="typst-preview">${svg}</div>`
      } else {
        errorMsg.value = 'Compilation failed'
      }
    } else {
      previewHtml.value = '<p class="text-ink-muted text-sm">Typst preview available in Tauri desktop mode. Use Markdown for browser preview.</p>'
    }
  } catch (e: any) {
    errorMsg.value = e.message || 'Compile failed'
  } finally {
    compiling.value = false
  }
}

// Commit message popup
const showCommitPopup = ref(false)
const tempCommitMsg = ref('')

function openCommitPopup() {
  tempCommitMsg.value = commitMsg.value
  showCommitPopup.value = true
}

async function confirmSaveWithCommit() {
  commitMsg.value = tempCommitMsg.value.trim() || 'Save draft'
  showCommitPopup.value = false
  await saveDraft()
}

async function handleSaveDraft() {
  // In local mode, require a commit message
  if ((tauri.isTauri.value || tauri.isBrowserLocal.value) && !commitMsg.value.trim()) {
    openCommitPopup()
    return
  }
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
      remove(DRAFT_KEY.value)
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

defineExpose({ contributions, handlePublish, showSelfReview, totalContribution })
</script>

<template>
  <div class="editor-page flex flex-col h-[calc(100vh-6rem)] animate-fade-in">
    <!-- Top toolbar -->
    <div class="flex items-center justify-between px-4 py-2 bg-card border border-divider rounded-t-lg mb-0">
      <button
        class="flex items-center justify-center w-8 h-8 rounded-lg
               text-ink-muted hover:text-ink hover:bg-[#21262d]
               transition-colors duration-200 shrink-0"
        aria-label="Back"
        @click="router.back()"
      >
        <ArrowLeft class="w-4 h-4" stroke-width="2" />
      </button>
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
            :data-tooltip="t('editor.saveDraft')"
            :disabled="submitting"
            @click="handleSaveDraft"
          >
            <Save class="w-4 h-4" stroke-width="2" />
          </button>
          <!-- Commit message popup -->
          <Transition name="slide-up">
            <div
              v-if="showCommitPopup"
              class="absolute top-full right-0 mt-2 z-50 bg-card border border-divider rounded-xl shadow-2xl p-4 w-72 animate-fade-in"
            >
              <p class="text-xs text-ink-muted mb-2">{{ t('editor.commitMessage') }} <span class="text-[#d73a49]">*</span></p>
              <input
                v-model="tempCommitMsg"
                type="text"
                :placeholder="t('editor.commitMessagePlaceholder')"
                class="w-full bg-[#0d1117] border border-divider rounded-lg px-3 py-2 text-sm text-ink placeholder:text-ink-muted/50 focus:outline-none focus:ring-1 focus:ring-accent mb-3"
                @keyup.enter="confirmSaveWithCommit"
              />
              <div class="flex items-center gap-2">
                <button
                  class="flex-1 text-xs text-ink-muted hover:text-ink hover:bg-[#21262d] rounded-lg py-1.5 transition-colors"
                  @click="showCommitPopup = false"
                >{{ t('editor.cancel') }}</button>
                <button
                  class="flex-1 text-xs font-semibold bg-accent text-[#0d1117] rounded-lg py-1.5 hover:brightness-110 transition-all"
                  @click="confirmSaveWithCommit"
                >{{ t('editor.saveDraft') }}</button>
              </div>
            </div>
          </Transition>
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
          :data-tooltip="showPreview ? 'Hide preview' : 'Show preview'"
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
          :data-tooltip="t('editor.compile')"
          :disabled="compiling || !content.trim()"
          @click="handleCompile"
        >
          <Play class="w-4 h-4" stroke-width="2" />
        </button>

        <!-- Download source -->
        <DownloadButton
          format="source"
          :content="content"
          :content-format="format"
          :filename="title"
          :disabled="!hasSaved || !isClean || !content.trim()"
          :commit-hash="commitHash"
          :disabled-reason="!hasSaved ? 'Save to enable download' : !isClean ? 'Unsaved changes — save to download' : undefined"
        />
        <!-- Download compiled HTML -->
        <DownloadButton
          format="compiled"
          :content="content"
          :content-format="format"
          :filename="title"
          :disabled="!hasSaved || !isClean || !content.trim()"
          :commit-hash="commitHash"
          :disabled-reason="!hasSaved ? 'Save to enable download' : !isClean ? 'Unsaved changes — save to download' : undefined"
        />

        <!-- History — show after first save even for new articles -->
        <router-link
          v-if="isEdit || currentDraftId"
          :to="`/articles/${editId || currentDraftId}/history`"
          class="flex items-center justify-center w-8 h-8 rounded-lg
                 text-ink-muted hover:text-ink hover:bg-[#21262d]
                 transition-colors duration-200"
          :aria-label="t('article.history')"
          :data-tooltip="t('article.history')"
        >
          <History class="w-4 h-4" stroke-width="2" />
        </router-link>

        <div class="w-px h-5 bg-divider mx-1" />

        <!-- Publish to pool -->
        <button
          class="flex items-center justify-center w-8 h-8 rounded-lg
                 transition-colors duration-200"
          :class="canWrite('editor.publish_pool')
            ? 'text-accent hover:text-accent hover:bg-accent/10'
            : 'text-ink-muted/30 cursor-not-allowed'"
          :disabled="submitting || !canWrite('editor.publish_pool')"
          :aria-label="t('editor.publish')"
          :data-tooltip="canWrite('editor.publish_pool') ? t('editor.publish') : t(getFallback('editor.publish_pool'))"
          @click="handlePublish"
        >
          <Send class="w-4 h-4" stroke-width="2" />
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
      <div class="flex items-center gap-3">
        <span>{{ format.toUpperCase() }}</span>
        <span v-if="commitHash" class="flex items-center gap-1 font-mono">
          <GitCommitHorizontal class="w-3 h-3" stroke-width="2" />
          {{ commitHash.slice(0, 7) }}
        </span>
      </div>
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
