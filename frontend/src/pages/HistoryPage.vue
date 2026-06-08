<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { getHistory, rollbackArticle } from '../api/articles'
import { useTauri, type CommitEntry } from '../composables/useTauri'
import DiffView from '../components/DiffView.vue'
import type { DiffResult } from '../components/DiffView.vue'
import { useAsyncResource } from '../composables/useAsyncResource'
import ErrorState from '../components/ErrorState.vue'
import ScoreBadges from '../components/ScoreBadges.vue'
import type { ArticleHistory } from '../api/types'
import {
  GitBranch,
  RotateCcw,
  ArrowLeft,
} from 'lucide-vue-next'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const id = route.params.id as string
const tauri = useTauri()

const selectedHash1 = ref<string | null>(null)
const selectedHash2 = ref<string | null>(null)
const diffResult = ref<DiffResult | null>(null)
const diffLoading = ref(false)
const rollingBack = ref<string | null>(null)
const rollbackError = ref('')

const isLocal = computed(() => tauri.isTauri.value || tauri.isBrowserLocal.value)

const { data: history, loading, error, execute: loadHistory } = useAsyncResource(
  async () => {
    // In local mode, fetch from local git history
    if (isLocal.value) {
      const entries = await tauri.gitHistory({ article_id: id })
      if (entries && !('error' in entries) && Array.isArray(entries)) {
        const commits = (entries as CommitEntry[]).map(e => ({
          hash: e.hash,
          message: e.message,
          author: e.author,
          timestamp: e.timestamp,
        }))
        return { commits } as ArticleHistory
      }
    }
    return getHistory(id)
  },
  null as ArticleHistory | null,
  { immediate: true },
)

const commits = computed(() => history.value?.commits ?? [])

const sortedCommits = computed(() => [...commits.value].reverse())

function toggleCommitSelect(hash: string) {
  if (!selectedHash1.value) {
    selectedHash1.value = hash
    selectedHash2.value = null
    diffResult.value = null
  } else if (selectedHash1.value === hash) {
    selectedHash1.value = null
    diffResult.value = null
  } else if (!selectedHash2.value) {
    selectedHash2.value = hash
    loadDiff()
  } else {
    // Both selected, reset
    selectedHash1.value = hash
    selectedHash2.value = null
    diffResult.value = null
  }
}

async function loadDiff() {
  if (!selectedHash1.value || !selectedHash2.value) return
  diffLoading.value = true
  try {
    if (isLocal.value) {
      // In local mode, use Tauri's structured git_diff
      const data = await tauri.gitDiff({
        article_id: id,
        hash1: selectedHash1.value,
        hash2: selectedHash2.value,
      })
      if (data && !('error' in data)) {
        diffResult.value = data as unknown as DiffResult
      } else {
        diffResult.value = null
      }
    } else {
      // Web mode: fetch REST diff, parse into DiffResult format
      const { getDiff } = await import('../api/articles')
      const data = await getDiff(id, selectedHash1.value!, selectedHash2.value!)
      if (data?.diff_text) {
        diffResult.value = parseUnifiedDiff(data.diff_text, data.files || [])
      } else {
        diffResult.value = null
      }
    }
  } catch (e) {
    console.error('Failed to load diff:', e)
    diffResult.value = null
  } finally {
    diffLoading.value = false
  }
}

/** Parse `git diff` unified output into structured DiffResult for the DiffView component. */
function parseUnifiedDiff(diffText: string, files: string[]): DiffResult {
  const hunks: DiffResult['hunks'] = []
  let currentHunk: DiffResult['hunks'][number] | null = null
  let oldLine = 0
  let newLine = 0

  for (const line of diffText.split('\n')) {
    const hunkMatch = line.match(/^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$/)
    if (hunkMatch) {
      if (currentHunk) hunks.push(currentHunk)
      const oldStart = parseInt(hunkMatch[1])
      const newStart = parseInt(hunkMatch[3])
      oldLine = oldStart
      newLine = newStart
      currentHunk = {
        old_start: oldStart,
        old_lines: parseInt(hunkMatch[2] || '1'),
        new_start: newStart,
        new_lines: parseInt(hunkMatch[4] || '1'),
        header: (hunkMatch[5] || '').trim(),
        lines: [],
      }
    } else if (currentHunk) {
      if (line.startsWith('+') && !line.startsWith('+++')) {
        currentHunk.lines.push({
          line_type: 'add',
          content: line.slice(1),
          old_lineno: null,
          new_lineno: newLine,
        })
        newLine++
      } else if (line.startsWith('-') && !line.startsWith('---')) {
        currentHunk.lines.push({
          line_type: 'del',
          content: line.slice(1),
          old_lineno: oldLine,
          new_lineno: null,
        })
        oldLine++
      } else if (!line.startsWith('diff --git') && !line.startsWith('index ') && !line.startsWith('---') && !line.startsWith('+++')) {
        currentHunk.lines.push({
          line_type: 'ctx',
          content: line,
          old_lineno: oldLine,
          new_lineno: newLine,
        })
        oldLine++
        newLine++
      }
    }
  }
  if (currentHunk) hunks.push(currentHunk)
  return { files, hunks }
}

async function handleRollback(hash: string) {
  if (!confirm(`Rollback to ${hash.substring(0, 7)}? This will create a new commit reverting to this state.`)) return
  rollingBack.value = hash
  try {
    await rollbackArticle(id, hash)
    // Reload history
    await loadHistory()
  } catch (e: any) {
    rollbackError.value = e.response?.data?.detail || 'Rollback failed'
  } finally {
    rollingBack.value = null
  }
}

function goBack() {
  router.back()
}
</script>

<template>
  <div class="history-page animate-fade-in">
    <!-- Header -->
    <div class="flex items-center gap-3 mb-6">
      <button
        class="flex items-center justify-center w-8 h-8 rounded-lg
               text-ink-muted hover:text-ink hover:bg-[#21262d] transition-colors"
        aria-label="Back to article"
        @click="goBack"
      >
        <ArrowLeft class="w-4 h-4" stroke-width="2" />
      </button>
      <div>
        <h1 class="text-display-md text-ink mb-2">{{ t('article.history') }}</h1>
        <p class="text-xs text-ink-muted">{{ t('history.subtitle') }}</p>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="space-y-3 animate-pulse">
      <div v-for="i in 4" :key="i" class="flex items-center gap-3">
        <div class="skeleton w-8 h-8 rounded-full" />
        <div class="skeleton h-5 flex-1" />
      </div>
    </div>

    <!-- Error -->
    <ErrorState v-else-if="error" :message="error" @retry="loadHistory()" />

    <template v-else>
      <!-- Commit graph -->
      <div class="card p-4 mb-6">
        <div class="space-y-0">
          <div
            v-for="(commit, idx) in sortedCommits"
            :key="commit.hash"
            class="flex items-start gap-3 py-2.5"
            :class="idx < sortedCommits.length - 1 ? 'border-b border-divider' : ''"
          >
            <!-- Timeline dot -->
            <div class="flex flex-col items-center shrink-0 pt-0.5">
              <div
                class="w-3 h-3 rounded-full border-2 cursor-pointer transition-colors"
                :class="commit.hash === selectedHash1 || commit.hash === selectedHash2
                  ? 'bg-accent border-accent'
                  : 'bg-card border-ink-muted hover:border-accent'"
                :data-tooltip="`Select ${commit.hash.substring(0, 7)}`"
                @click="toggleCommitSelect(commit.hash)"
              />
              <div
                v-if="idx < sortedCommits.length - 1"
                class="w-0.5 h-6 bg-divider"
              />
            </div>

            <!-- Commit info -->
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-0.5">
                <span class="text-sm font-mono font-semibold text-accent">
                  {{ commit.hash.substring(0, 7) }}
                </span>
                <span v-if="commit.parents?.length" class="flex items-center gap-0.5 text-xs text-ink-muted">
                  <GitBranch class="w-3 h-3" stroke-width="2" />
                  {{ commit.parents.length }} {{ commit.parents.length > 1 ? t('history.parents') : t('history.parent') }}
                </span>
              </div>
              <p class="text-sm text-ink leading-snug">
                {{ commit.message }}
              </p>
              <div class="flex items-center gap-3 text-xs text-ink-muted mt-1">
                <span>{{ commit.author }}</span>
                <span>{{ new Date(commit.timestamp).toLocaleString() }}</span>
              </div>

              <!-- Score badge -->
              <div
                v-if="commit.score"
                class="flex items-center gap-2 mt-1.5 text-xs font-mono text-ink-muted"
              >
                <ScoreBadges :score="commit.score" :highlight-first="true" />
              </div>
            </div>

            <!-- Rollback button -->
            <button
              class="flex items-center gap-1 px-2.5 py-1 text-xs text-ink-muted
                     hover:text-ink hover:bg-[#21262d] rounded-md
                     transition-colors shrink-0"
              :aria-label="t('history.rollbackAria')"
              :disabled="rollingBack === commit.hash"
              @click="handleRollback(commit.hash)"
            >
              <RotateCcw class="w-3 h-3" stroke-width="2" />
              {{ rollingBack === commit.hash ? t('history.rollingBack') : t('history.rollback') }}
            </button>
          </div>
        </div>
      </div>

      <!-- Selected commits info -->
      <div
        v-if="selectedHash1 && !selectedHash2"
        class="card p-4 mb-6 text-center text-sm text-ink-muted"
      >
        {{ t('history.selectSecondCommit') }}
      </div>

      <!-- Diff viewer -->
      <div v-if="diffResult" class="card p-4 mb-6">
        <h3 class="text-sm font-heading font-semibold text-ink mb-3">
          {{ t('history.diff') }}: {{ String(selectedHash1).substring(0, 7) }} → {{ String(selectedHash2).substring(0, 7) }}
        </h3>
        <DiffView :diff="diffResult" />
      </div>

      <!-- Loading diff -->
      <div
        v-if="diffLoading"
        class="card p-8 text-center text-sm text-ink-muted"
      >
        {{ t('history.loadingDiff') }}
      </div>
    </template>
  </div>
</template>
