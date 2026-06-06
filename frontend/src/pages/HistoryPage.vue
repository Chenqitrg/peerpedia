<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { getHistory, getDiff, rollbackArticle } from '../api/articles'
import { useAsyncResource } from '../composables/useAsyncResource'
import ErrorState from '../components/ErrorState.vue'
import ScoreBadges from '../components/ScoreBadges.vue'
import type { CommitInfo, ArticleDiff, ArticleHistory } from '../api/types'
import {
  GitCommitHorizontal,
  GitBranch,
  RotateCcw,
  ChevronLeft,
  ChevronRight,
  FileText,
  ArrowLeft,
} from 'lucide-vue-next'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const id = route.params.id as string

const selectedHash1 = ref<string | null>(null)
const selectedHash2 = ref<string | null>(null)
const diffResult = ref<ArticleDiff | null>(null)
const diffLoading = ref(false)
const rollingBack = ref<string | null>(null)
const rollbackError = ref('')

const { data: history, loading, error, execute: loadHistory } = useAsyncResource(
  () => getHistory(id),
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
    const data = await getDiff(id, selectedHash1.value, selectedHash2.value)
    diffResult.value = data
  } catch (e) {
    console.error('Failed to load diff:', e)
    diffResult.value = null
  } finally {
    diffLoading.value = false
  }
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
  router.push(`/articles/${id}`)
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
                :title="`Select ${commit.hash.substring(0, 7)}`"
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
        <div
          v-if="diffResult.diff_text"
          class="bg-[#0d1117] border border-divider rounded-lg p-4 overflow-x-auto"
        >
          <pre class="text-xs font-mono text-ink leading-relaxed whitespace-pre-wrap">{{ diffResult.diff_text }}</pre>
        </div>
        <p v-else class="text-xs text-ink-muted">{{ t('history.noDiff') }}</p>
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
