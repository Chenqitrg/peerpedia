<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useArticleStore } from '../stores/useArticleStore'
import { useUserStore } from '../stores/useUserStore'
import { apiClient } from '../api/client'
import {
  Bookmark,
  BookmarkCheck,
  Eye,
  EyeOff,
  FileDown,
  Play,
  Save,
  Send,
  SlidersHorizontal,
  FileText,
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const articleStore = useArticleStore()
const userStore = useUserStore()

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
const scores = ref({ originality: 3, rigor: 3, completeness: 3, pedagogy: 3, impact: 3 })
const keywords = ref('')
const categories = ref('')
const abstract = ref('')

// UI state
const submitting = ref(false)
const errorMsg = ref('')
const successMsg = ref('')
const savedMsg = ref(false)
const showPreview = ref(true)

// Split panel resize
const splitRatio = ref(50)

const DRAFT_KEY = computed(() => `editor-draft-${editId.value || 'new'}`)

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
  } catch (e: any) {
    errorMsg.value = 'Failed to load article'
  }
}

function restoreDraft() {
  const saved = localStorage.getItem(DRAFT_KEY.value)
  if (saved) {
    try {
      const parsed = JSON.parse(saved)
      title.value = parsed.title || ''
      content.value = parsed.content || ''
      format.value = parsed.format || 'markdown'
      scores.value = parsed.scores || { originality: 3, rigor: 3, completeness: 3, pedagogy: 3, impact: 3 }
      keywords.value = parsed.keywords || ''
      categories.value = parsed.categories || ''
      abstract.value = parsed.abstract || ''
    } catch {
      // ignore corrupt draft
    }
  }
}

function saveDraft() {
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
    const res = await apiClient.post('/compile-preview', {
      content: content.value,
      format: format.value,
    })
    previewHtml.value = res.data.output || res.data.content || ''
  } catch (e: any) {
    errorMsg.value = e.response?.data?.detail || 'Compile failed'
  } finally {
    compiling.value = false
  }
}

function handlePublish() {
  showSelfReview.value = true
}

async function handleSubmitToPool() {
  if (!content.value.trim()) {
    errorMsg.value = 'Content is required'
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
    const body: Record<string, unknown> = {
      title: title.value,
      abstract: abstract.value || title.value,
      content: content.value,
      format: format.value,
      self_review: { ...scores.value },
      authors: [userStore.viewer.id],
      keywords: keywords.value ? keywords.value.split(',').map((k: string) => k.trim()).filter(Boolean) : [],
      categories: categories.value ? categories.value.split(',').map((c: string) => c.trim()).filter(Boolean) : [],
    }

    let result: any
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

function handleDownload(format: 'source' | 'pdf') {
  // Download via API or backup method
  if (editId.value) {
    window.open(`/api/v1/articles/${editId.value}/download/${format}`, '_blank')
  }
}
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
            aria-label="Save draft"
            title="Save draft"
            @click="saveDraft"
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
          aria-label="Compile"
          title="Compile"
          :disabled="compiling || !content.trim()"
          @click="handleCompile"
        >
          <Play class="w-4 h-4" stroke-width="2" />
        </button>

        <!-- Download buttons -->
        <template v-if="editId">
          <button
            class="flex items-center justify-center w-8 h-8 rounded-lg
                   text-ink-muted hover:text-ink hover:bg-[#21262d]
                   transition-colors duration-200"
            aria-label="Download source"
            title="Download source"
            @click="handleDownload('source')"
          >
            <FileDown class="w-4 h-4" stroke-width="2" />
          </button>
        </template>

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
          {{ isEdit ? 'Submit' : 'Publish' }}
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
        class="w-1 bg-divider cursor-col-resize hover:bg-accent/50 transition-colors shrink-0 relative"
        @mousedown.prevent=""
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
            Click <Play class="w-3 h-3 inline mx-1" stroke-width="2" /> to compile preview
          </div>
        </div>
      </div>
    </div>

    <!-- Bottom bar -->
    <div class="flex items-center justify-between px-4 py-1.5 bg-card border border-divider rounded-b-lg text-xs text-ink-muted">
      <span>{{ format.toUpperCase() }}</span>
      <span>{{ content.length }} characters</span>
    </div>

    <!-- Self-review panel (slide-in) -->
    <Transition name="slide-up">
      <div
        v-if="showSelfReview"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
        @click.self="showSelfReview = false"
      >
        <div class="bg-card border border-divider rounded-xl shadow-2xl w-full max-w-lg mx-4 p-6 animate-fade-in">
          <h3 class="text-lg font-heading font-semibold text-ink mb-1">Self Assessment</h3>
          <p class="text-xs text-ink-muted mb-5">Rate your article before submitting to the pool.</p>

          <!-- 5-dim scores -->
          <div class="space-y-3 mb-5">
            <label class="text-xs font-semibold text-ink-muted">Scores (1-5)</label>
            <div class="grid grid-cols-5 gap-2">
              <div v-for="(_, key) in scores" :key="key" class="text-center">
                <div class="text-xs text-ink-muted mb-1 capitalize">{{ key.substring(0, 4) }}</div>
                <select
                  v-model="(scores as any)[key]"
                  class="w-full bg-[#0d1117] border border-divider rounded text-center text-sm text-ink py-1.5 focus:outline-none focus:ring-1 focus:ring-accent"
                >
                  <option v-for="n in 5" :key="n" :value="n">{{ n }}</option>
                </select>
              </div>
            </div>
          </div>

          <!-- Keywords -->
          <div class="mb-3">
            <label class="text-xs font-semibold text-ink-muted block mb-1">Keywords</label>
            <input
              v-model="keywords"
              type="text"
              placeholder="e.g. quantum, computing, algorithms"
              class="w-full bg-[#0d1117] border border-divider rounded px-3 py-1.5 text-sm text-ink placeholder:text-ink-muted/50 focus:outline-none focus:ring-1 focus:ring-accent"
            />
          </div>

          <!-- Categories -->
          <div class="mb-3">
            <label class="text-xs font-semibold text-ink-muted block mb-1">Categories</label>
            <input
              v-model="categories"
              type="text"
              placeholder="e.g. cs.AI, math.NT"
              class="w-full bg-[#0d1117] border border-divider rounded px-3 py-1.5 text-sm text-ink placeholder:text-ink-muted/50 focus:outline-none focus:ring-1 focus:ring-accent"
            />
          </div>

          <!-- Abstract -->
          <div class="mb-5">
            <label class="text-xs font-semibold text-ink-muted block mb-1">Abstract</label>
            <textarea
              v-model="abstract"
              rows="3"
              placeholder="Brief summary of your article..."
              class="w-full bg-[#0d1117] border border-divider rounded px-3 py-1.5 text-sm text-ink placeholder:text-ink-muted/50 focus:outline-none focus:ring-1 focus:ring-accent resize-none"
            />
          </div>

          <!-- Actions -->
          <div class="flex items-center gap-3">
            <button
              class="btn-outline flex-1"
              @click="showSelfReview = false"
            >
              Cancel
            </button>
            <button
              class="btn-primary flex-1"
              :disabled="submitting"
              @click="handleSubmitToPool"
            >
              {{ submitting ? 'Submitting...' : 'Publish to Pool' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>
