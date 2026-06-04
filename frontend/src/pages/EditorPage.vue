<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useArticleStore } from '../stores/useArticleStore'
import { useUserStore } from '../stores/useUserStore'
import FiveDimForm from '../components/FiveDimForm.vue'
import { apiClient } from '../api/client'

const route = useRoute()
const router = useRouter()
const articleStore = useArticleStore()
const userStore = useUserStore()

const editId = computed(() => route.params.id as string | undefined)
const isEdit = computed(() => !!editId.value)

const title = ref('')
const abstract = ref('')
const content = ref('')
const format = ref<'markdown' | 'typst'>('markdown')
const scores = ref({ originality: 3, rigor: 3, completeness: 3, pedagogy: 3, impact: 3 })
const submitting = ref(false)
const previewHtml = ref('')
const previewLoading = ref(false)
const errorMsg = ref('')
const successMsg = ref('')

onMounted(async () => {
  if (isEdit.value) {
    await articleStore.fetchArticle(editId.value!)
    const a = articleStore.currentArticle
    if (a) {
      title.value = a.title || ''
      // Load content from git history's latest file
      try {
        const hist = await import('../api/articles').then(m => m.getHistory(editId.value!))
        if (hist.commits?.length) {
          // Content is fetched via compile endpoint or direct git read
          // For now set placeholder; real content needs a GET /articles/{id}/content endpoint
        }
      } catch { /* content load is best-effort for now */ }
    }
  }
})

async function handlePreview() {
  if (!content.value.trim()) return
  previewLoading.value = true
  previewHtml.value = ''
  errorMsg.value = ''
  try {
    const res = await apiClient.post('/compile-preview', {
      content: content.value,
      format: format.value,
    })
    previewHtml.value = res.data.content || res.data.output || ''
  } catch (e: any) {
    errorMsg.value = e.response?.data?.detail || 'Preview failed'
  } finally {
    previewLoading.value = false
  }
}

async function handleSubmit() {
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
      abstract: abstract.value,
      content: content.value,
      format: format.value,
      self_review: { ...scores.value },
      authors: [userStore.viewer.id],
    }

    if (isEdit.value) {
      await articleStore.updateArticle(editId.value!, body)
      successMsg.value = 'Article updated and submitted to pool!'
    } else {
      const result = await articleStore.createArticle(body)
      successMsg.value = 'Article created and submitted to pool!'
      // Navigate to the new article
      setTimeout(() => {
        router.push(`/article/${result.id}`)
      }, 1000)
    }
  } catch (e: any) {
    errorMsg.value = e.response?.data?.detail || 'Submission failed'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="editor-page max-w-content animate-fade-in">
    <header class="mb-8">
      <h1 class="text-display-md text-ink mb-2">
        {{ isEdit ? 'Edit Article' : 'Create Article' }}
      </h1>
      <p class="text-ink-muted">Write, review, and publish your scholarly work.</p>
    </header>

    <!-- Messages -->
    <div v-if="errorMsg" class="card bg-danger/10 border border-danger/20 p-4 mb-6 text-danger text-sm">
      {{ errorMsg }}
    </div>
    <div v-if="successMsg" class="card bg-success/10 border border-success/20 p-4 mb-6 text-success text-sm">
      {{ successMsg }}
    </div>

    <div class="space-y-6">
      <!-- Title -->
      <div>
        <label for="editor-title" class="label">Title</label>
        <input
          id="editor-title"
          v-model="title"
          type="text"
          class="input text-lg"
          placeholder="Enter article title..."
        />
      </div>

      <!-- Format toggle -->
      <div>
        <label class="label">Format</label>
        <div class="flex gap-2">
          <button
            :class="format === 'markdown' ? 'btn-primary btn-sm' : 'btn-ghost btn-sm'"
            @click="format = 'markdown'"
          >
            Markdown
          </button>
          <button
            :class="format === 'typst' ? 'btn-primary btn-sm' : 'btn-ghost btn-sm'"
            @click="format = 'typst'"
          >
            Typst
          </button>
        </div>
      </div>

      <!-- Abstract -->
      <div>
        <label for="editor-abstract" class="label">Abstract</label>
        <textarea
          id="editor-abstract"
          v-model="abstract"
          rows="4"
          class="input font-mono text-sm"
          placeholder="Write a brief abstract..."
        />
      </div>

      <!-- Content editor -->
      <div>
        <label for="editor-content" class="label">Content ({{ format }})</label>
        <textarea
          id="editor-content"
          v-model="content"
          rows="20"
          class="input font-mono text-sm"
          :placeholder="format === 'markdown' ? '# Heading\n\nWrite your article in Markdown...' : '= Heading\n\nWrite your article in Typst...'"
        />
      </div>

      <!-- Self-review -->
      <div class="card p-5">
        <h3 class="text-lg font-heading font-semibold text-ink mb-3">Self-Review</h3>
        <p class="text-sm text-ink-muted mb-4">
          Rate your own article across five dimensions (1–5). This helps seed the review pool.
        </p>
        <FiveDimForm v-model="scores" />
      </div>

      <!-- Preview -->
      <div v-if="previewHtml" class="card p-5">
        <h3 class="text-lg font-heading font-semibold text-ink mb-3">Preview</h3>
        <div class="prose-custom border rounded-lg p-4 bg-white" v-html="previewHtml" />
      </div>

      <!-- Actions -->
      <div class="flex items-center gap-3 pt-4 border-t border-gray-200">
        <button
          class="btn-primary"
          :disabled="submitting"
          @click="handleSubmit"
        >
          <svg v-if="submitting" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
          </svg>
          {{ submitting ? 'Submitting...' : (isEdit ? 'Submit Edit to Pool' : 'Publish to Pool') }}
        </button>
        <button
          class="btn-outline"
          :disabled="previewLoading || !content.trim()"
          @click="handlePreview"
        >
          <svg v-if="previewLoading" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
            <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          {{ previewLoading ? 'Compiling...' : 'Preview' }}
        </button>
        <button class="btn-ghost" @click="router.back()">Cancel</button>
      </div>
    </div>
  </div>
</template>
