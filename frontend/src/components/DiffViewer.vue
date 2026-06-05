<script setup lang="ts">
import { ref, watch, computed, onMounted } from 'vue'
import { getHistory, getDiff } from '../api/articles'
import type { CommitInfo, ArticleDiff } from '../api/types'
import { html } from 'diff2html'
import 'diff2html/bundles/css/diff2html.min.css'

const props = defineProps<{
  articleId: string
}>()

// ---- State ----
const loading = ref(true)
const error = ref<string | null>(null)
const commits = ref<CommitInfo[]>([])
const hash1 = ref<string>('')
const hash2 = ref<string>('')
const diffText = ref<string>('')
const diffFiles = ref<string[]>([])

// ---- Computed ----
const hasHistory = computed(() => commits.value.length > 0)
const canCompare = computed(() => hash1.value && hash2.value && hash1.value !== hash2.value)

// ---- Methods ----
async function fetchHistory() {
  loading.value = true
  error.value = null
  try {
    const data = await getHistory(props.articleId)
    commits.value = data.commits ?? []
    if (commits.value.length >= 2) {
      hash1.value = commits.value[0].hash
      hash2.value = commits.value[1].hash
    } else if (commits.value.length === 1) {
      hash1.value = commits.value[0].hash
      hash2.value = ''
    }
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Failed to load history'
  } finally {
    loading.value = false
  }
}

async function fetchDiff() {
  if (!canCompare.value) return
  error.value = null
  try {
    const data: ArticleDiff = await getDiff(props.articleId, hash1.value, hash2.value)
    diffText.value = data.diff_text
    diffFiles.value = data.files ?? []
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Failed to load diff'
  }
}

// ---- Side effect: re-fetch diff when selection changes ----
watch([hash1, hash2], () => {
  if (canCompare.value) {
    fetchDiff()
  }
})

onMounted(() => {
  fetchHistory()
})

// ---- Build rendered HTML ----
const diffHtml = computed(() => {
  if (!diffText.value) return ''
  try {
    return html(diffText.value, {
      outputFormat: 'side-by-side',
      drawFileList: true,
      matching: 'lines',
    })
  } catch {
    return ''
  }
})

// ---- Helper for commit label ----
function commitLabel(c: CommitInfo): string {
  const short = c.hash.substring(0, 7)
  const msg = c.message.length > 50 ? c.message.substring(0, 50) + '...' : c.message
  let label = `${short} — ${msg}`
  if (c.score) {
    const avg = (c.score.originality + c.score.rigor + c.score.completeness +
                 c.score.pedagogy + c.score.impact) / 5
    label += ` [${avg.toFixed(1)}]`
  }
  return label
}
</script>

<template>
  <div class="diff-viewer animate-fade-in">
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-lg font-heading font-semibold text-ink">History / Diff</h2>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="space-y-3 animate-pulse">
      <div class="skeleton h-10 w-full rounded-card" />
      <div class="skeleton h-64 w-full rounded-card" />
    </div>

    <!-- Error -->
    <div
      v-else-if="error"
      class="card p-4 border-l-4"
      :class="['border-danger']"
    >
      <p class="text-sm text-ink-muted">{{ error }}</p>
      <button
        class="btn-outline btn-sm mt-2"
        @click="fetchHistory"
      >
        Retry
      </button>
    </div>

    <!-- Empty state -->
    <div
      v-else-if="!hasHistory"
      class="card p-6 text-center"
    >
      <p class="text-ink-muted text-sm">No commits yet. Save your article to create a history.</p>
    </div>

    <!-- Diff controls + content -->
    <template v-else>
      <!-- Commit selectors -->
      <div class="flex flex-col sm:flex-row gap-3 mb-4">
        <div class="flex-1">
          <label class="block text-xs text-ink-muted mb-1 font-medium">Base (older)</label>
          <select
            v-model="hash1"
            class="w-full rounded-card border border-surface-300 bg-white px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-primary-400"
          >
            <option
              v-for="c in commits"
              :key="c.hash"
              :value="c.hash"
            >
              {{ commitLabel(c) }}
            </option>
          </select>
        </div>
        <div class="flex-1">
          <label class="block text-xs text-ink-muted mb-1 font-medium">Head (newer)</label>
          <select
            v-model="hash2"
            class="w-full rounded-card border border-surface-300 bg-white px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-primary-400"
          >
            <option value="" disabled>Select a commit…</option>
            <option
              v-for="c in commits"
              :key="c.hash"
              :value="c.hash"
            >
              {{ commitLabel(c) }}
            </option>
          </select>
        </div>
      </div>

      <!-- Diff rendering -->
      <div
        v-if="diffText && diffHtml"
        class="card overflow-hidden"
      >
        <div class="diff2html-wrapper" v-html="diffHtml" />
      </div>

      <!-- Wait for selection -->
      <div
        v-else-if="!error"
        class="card p-6 text-center"
      >
        <p class="text-ink-muted text-sm">
          {{ hash1 && hash2 ? 'Loading diff…' : 'Select two different commits to compare.' }}
        </p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.diff2html-wrapper :deep(.d2h-file-header) {
  @apply bg-surface-100 px-3 py-2 border-b border-surface-200;
}
.diff2html-wrapper :deep(.d2h-file-name) {
  @apply text-sm font-medium text-ink;
}
.diff2html-wrapper :deep(.d2h-code-line) {
  @apply text-xs leading-relaxed;
}
.diff2html-wrapper :deep(.d2h-ins) {
  @apply bg-green-50;
}
.diff2html-wrapper :deep(.d2h-del) {
  @apply bg-red-50;
}
.diff2html-wrapper :deep(.d2h-code-side-line) {
  @apply text-xs leading-relaxed;
}
.diff2html-wrapper :deep(.d2h-code-side-linenumber) {
  @apply text-[10px] text-ink-subtle;
}
</style>
