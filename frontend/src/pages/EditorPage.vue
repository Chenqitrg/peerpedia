<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { useOffline } from '../composables/useOffline'
import { defineAsyncComponent } from 'vue'
const CodeEditor = defineAsyncComponent(() => import('../components/CodeEditor.vue'))
import { useArticleStore } from '../stores/useArticleStore'
import { useUserStore } from '../stores/useUserStore'
import { useDraftPersistence } from '../composables/useDraftPersistence'
import { useCommitFlow } from '../composables/useCommitFlow'
import { useSplitPane } from '../composables/useSplitPane'
import { useTauri } from '../composables/useTauri'
import { useEditorTab } from '../composables/useTabIntegration'
import { useTabStore } from '../stores/useTabStore'
import { loadString, saveString, saveJSON, remove } from '../composables/useLocalStorage'
import { parseMarkdown } from '../utils/markdown'
import { sanitizeTypstSvg } from '../utils/typst'
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
const tabStore = useTabStore()
const { t } = useI18n()

const { canWrite, getFallback } = useOffline()

import { getArticleSource } from '../api/articles'
import type { ArticleCreatePayload, ArticleUpdatePayload } from '../api/types'

const editId = computed(() => route.params.id as string | undefined)
const isEdit = computed(() => !!editId.value)

// Editor state
const title = ref('')
const content = ref('')
const format = ref<'markdown' | 'typst'>(
  (route.query.format as 'markdown' | 'typst') || 'markdown'
)
const previewHtml = ref('')
const previewLoading = ref(false)
const compiling = ref(false)
const compileResult = ref<{ type: 'svg' | 'error'; content: string } | null>(null)
const loadingArticle = ref(false)

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

// Tab integration — register this editor as a tab and sync state
const editorAreaRef = ref<HTMLElement | null>(null)
const tabId = tabStore.ensureTab('editor', route.fullPath)
useEditorTab(tabId, title, isClean, editorAreaRef)

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

function onSaveAndClose(e: Event) {
  const detail = (e as CustomEvent).detail
  if (detail?.tabId !== tabId) return  // not for this instance
  handleSaveDraft()
}

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
  window.addEventListener('keydown', onKeydown)
  window.addEventListener('tab-save-and-close', onSaveAndClose)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('tab-save-and-close', onSaveAndClose)
})

// Cmd+S / Ctrl+S → compile preview (only when editor area is focused)
function onKeydown(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key === 's') {
    // Ignore if focus is outside the editor (e.g., in a modal or other input)
    const active = document.activeElement
    if (active && !active.closest('.editor-page')) return
    e.preventDefault()
    handleCompile()
  }
}

// When NavBar navigates to /edit?new=1, reset editor state for a fresh start.
// With unique KeepAlive keys (route.fullPath), each "New Article" click creates
// a brand new component instance. The { immediate: true } watch fires on the
// initial mount to clear any stale state. We guard with didReset to prevent
// re-triggering on KeepAlive reactivation (which would clear the user's work).
let didReset = false
watch(() => route.query.new, (val) => {
  if (val === '1' && !didReset) {
    didReset = true
    title.value = ''
    content.value = ''
    previewHtml.value = ''
    commitHash.value = ''
    savedContent.value = ''
    savedTitle.value = ''
    commitMsg.value = ''
    scores.value = { originality: 3, rigor: 3, completeness: 3, pedagogy: 3, impact: 3 }
    keywords.value = ''
    categories.value = ''
    abstract.value = ''
    contributions.value = {}
    currentDraftId.value = undefined
    remove(DRAFT_ID_KEY.value)
    remove(DRAFT_KEY.value)
  }
}, { immediate: true })

async function loadExistingArticle() {
  loadingArticle.value = true
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
    // 2. In Tauri/dev-mock mode, read from git first (canonical source),
    //    then fall back to local draft storage.
    if (tauri.isTauri.value || tauri.isBrowserLocal.value) {
      // Try gitShow for the latest commit content.
      try {
        const history = await tauri.gitHistory({ article_id: editId.value! })
        if (history && !('error' in history) && Array.isArray(history) && history.length > 0) {
          const latestHash = history[0].hash
          const gitContent = await tauri.gitShow({ article_id: editId.value!, commit_hash: latestHash })
          if (gitContent && typeof gitContent === 'string') {
            content.value = gitContent
            format.value = 'markdown' // gitShow returns raw content; infer format from draft metadata
            commitHash.value = latestHash
            // Try draft metadata for title and format
            const accountId = userStore.viewer?.id || 'local'
            const draft = await draftPersistence.load(editId.value!, accountId)
            if (draft && draft.title) title.value = draft.title
            if (draft && draft.format) format.value = draft.format as 'markdown' | 'typst'
            savedContent.value = content.value
            savedTitle.value = title.value
            return
          }
        }
      } catch { /* gitShow failed — fall through to draft persistence */ }

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
  } finally {
    loadingArticle.value = false
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

/** Git-backed save for Tauri/local mode — git is source of truth (DESIGN.md §2.3). */
async function persistToGit(accountId: string, author: string, msg: string): Promise<boolean> {
  const existingId = currentDraftId.value

  if (!existingId) {
    // New draft — create persistence entry first to get an ID, then gitInit.
    const result = await draftPersistence.save(
      accountId, title.value, content.value, format.value, undefined,
    )
    if (!result || !result.id) { errorMsg.value = 'Failed to create draft'; return false }
    currentDraftId.value = result.id
    saveString(DRAFT_ID_KEY.value, result.id)

    try {
      const r = await tauri.gitInit({ article_id: result.id, content: content.value, format: format.value, commit_message: msg, author })
      if (r && 'hash' in r) commitHash.value = r.hash
    } catch (e: unknown) {
      errorMsg.value = e instanceof Error ? e.message : 'Git init failed — draft saved without version history'
    }
    return true
  }

  // Existing draft — git commit FIRST, then update DB index.
  try {
    const history = await tauri.gitHistory({ article_id: existingId })
    const hasRepo = history && !('error' in history) && Array.isArray(history) && history.length > 0
    if (hasRepo) {
      const r = await tauri.gitCommit({ article_id: existingId, content: content.value, format: format.value, commit_message: msg, author })
      if (r && 'hash' in r) { commitHash.value = r.hash }
      else { errorMsg.value = 'Git commit failed — draft not saved'; return false }
    } else {
      const r = await tauri.gitInit({ article_id: existingId, content: content.value, format: format.value, commit_message: msg, author })
      if (r && 'hash' in r) { commitHash.value = r.hash }
      else { errorMsg.value = 'Git init failed — draft not saved'; return false }
    }
  } catch (e: unknown) {
    errorMsg.value = e instanceof Error ? e.message : 'Git operation failed — draft not saved'
    return false
  }

  // Git succeeded — update the DB index.
  await draftPersistence.save(accountId, title.value, content.value, format.value, existingId)
  return true
}

/** Persist via REST API + localStorage fallback (web mode). */
async function persistToWeb(accountId: string) {
  const result = await draftPersistence.save(
    accountId, title.value, content.value, format.value, currentDraftId.value,
  )
  if (result && result.id) {
    currentDraftId.value = result.id
    saveString(DRAFT_ID_KEY.value, result.id)
  }
  saveJSON(DRAFT_KEY.value, {
    title: title.value, content: content.value, format: format.value,
    scores: scores.value, keywords: keywords.value,
    categories: categories.value, abstract: abstract.value,
  })
}

function markSaved() {
  savedContent.value = content.value
  savedTitle.value = title.value
  savedMsg.value = true
  setTimeout(() => { savedMsg.value = false }, 2000)
}

async function saveDraft() {
  const accountId = userStore.viewer?.id || 'local'
  const author = userStore.viewer?.name || userStore.viewer?.username || 'local'

  if (tauri.isTauri.value || tauri.isBrowserLocal.value) {
    const msg = commitMsg.value.trim() || 'Save draft'
    const ok = await persistToGit(accountId, author, msg)
    if (!ok) return
    commitMsg.value = ''
    markSaved()
    return
  }

  await persistToWeb(accountId)
  markSaved()
}

async function handleCompile() {
  if (!content.value.trim()) return
  compiling.value = true
  previewHtml.value = ''
  compileResult.value = null
  errorMsg.value = ''
  try {
    if (format.value === 'markdown') {
      previewHtml.value = parseMarkdown(content.value)
    } else if (tauri.isTauri.value || tauri.isBrowserLocal.value) {
      // Typst: use Tauri local compilation
      const result = await tauri.compileTypst({
        content: content.value,
        format: format.value,
      })
      if (result && typeof result === 'string') {
        compileResult.value = { type: 'svg', content: sanitizeTypstSvg(result) }
      } else {
        const errMsg = (result && typeof result === 'object' && 'error' in result)
          ? (result as { error: string }).error
          : 'Compilation failed'
        compileResult.value = { type: 'error', content: errMsg }
        errorMsg.value = errMsg
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

// Commit message popup — extracted to useCommitFlow composable
const { showCommitPopup, tempCommitMsg, openCommitPopup, confirmCommit, cancelCommit } =
  useCommitFlow(async (msg: string) => { commitMsg.value = msg; await saveDraft() })

async function handleSaveDraft() {
  // In local mode, require a commit message
  if ((tauri.isTauri.value || tauri.isBrowserLocal.value) && !commitMsg.value.trim()) {
    openCommitPopup(commitMsg.value)
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
        class="flex items-center justify-center w-9 h-9 rounded-lg
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
            class="flex items-center justify-center w-9 h-9 rounded-lg
                   text-ink-muted hover:text-ink hover:bg-[#21262d]
                   transition-colors duration-200
                   disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-transparent disabled:hover:text-ink-muted"
            :aria-label="t('editor.saveDraft')"
            :data-tooltip="t('editor.saveDraft')"
            :disabled="submitting || isClean"
            @click="handleSaveDraft"
          >
            <Save class="w-4 h-4" stroke-width="2" />
          </button>
          <!-- Commit message popup -->
          <Transition name="slide-up">
            <div
              v-if="showCommitPopup"
              class="absolute top-full right-0 mt-2 z-50 bg-card border border-divider rounded-lg shadow-2xl p-4 w-72 animate-fade-in"
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
                  @click="cancelCommit()"
                >{{ t('editor.cancel') }}</button>
                <button
                  class="flex-1 text-xs font-semibold bg-accent text-[#0d1117] rounded-lg py-1.5 hover:brightness-110 transition-all"
                  @click="confirmCommit"
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

        <div class="w-px h-5 bg-divider mx-1" />

        <!-- Toggle preview -->
        <button
          class="flex items-center justify-center w-9 h-9 rounded-lg
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
          class="flex items-center justify-center w-9 h-9 rounded-lg
                 text-ink-muted hover:text-accent hover:bg-accent/10
                 transition-colors duration-200"
          :aria-label="t('editor.compile')"
          :data-tooltip="t('editor.compile') + ' (⌘S)'"
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
        <!-- Download repo bundle -->
        <DownloadButton
          format="repo"
          :content="content"
          :article-id="editId || currentDraftId"
          :filename="title"
          :disabled="!hasSaved || !isClean || !content.trim()"
          :commit-hash="commitHash"
          :disabled-reason="!hasSaved ? 'Save to enable download' : !isClean ? 'Unsaved changes — save to download' : undefined"
        />

        <!-- History — show after first save even for new articles -->
        <router-link
          v-if="isEdit || currentDraftId"
          :to="`/articles/${editId || currentDraftId}/history`"
          class="flex items-center justify-center w-9 h-9 rounded-lg
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
          class="flex items-center justify-center w-9 h-9 rounded-lg
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
    <div class="flex flex-1 border-x border-divider overflow-hidden border-t">
      <!-- Editor area (left) -->
      <div
        ref="editorAreaRef"
        class="flex flex-col"
        :style="{ width: showPreview ? `${splitRatio}%` : '100%' }"
      >
        <!-- Loading skeleton -->
        <div v-if="loadingArticle" class="flex-1 w-full bg-[#0d1117] p-4 animate-pulse">
          <div class="h-4 bg-[#21262d] rounded w-3/4 mb-3" />
          <div class="h-4 bg-[#21262d] rounded w-1/2 mb-3" />
          <div class="h-4 bg-[#21262d] rounded w-5/6 mb-3" />
          <div class="h-4 bg-[#21262d] rounded w-2/3" />
        </div>
        <CodeEditor
          v-model="content"
          :format="format"
          :placeholder="format === 'markdown'
            ? '# Title\n\nWrite your article in Markdown...'
            : '= Title\n\nWrite your article in Typst...'"
          class="flex-1 w-full"
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
          <div v-if="compiling" class="flex items-center justify-center h-full text-ink-muted text-sm gap-2">
            <span class="inline-block w-4 h-4 border-2 border-ink-muted/30 border-t-accent rounded-full animate-spin" />
            Compiling...
          </div>
          <!-- Typst compile result (SVG or error) -->
          <div v-else-if="compileResult?.type === 'svg'" class="typst-preview" v-html="compileResult.content" />
          <div v-else-if="compileResult?.type === 'error'" class="typst-preview-error text-[#d73a49] p-4 font-mono text-sm">
            {{ compileResult.content }}
          </div>
          <!-- Markdown HTML preview -->
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
