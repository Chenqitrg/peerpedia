<script setup lang="ts">
import { ref, onMounted, watch, computed, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { useOffline } from '../composables/useOffline'
import { getArticle, getArticleSource, getHistory, forkArticle, extendSink, createMergeProposal } from '../api/articles'
import { compilePreview } from '../api/compile'
import { addBookmark, removeBookmark } from '../api/bookmarks'
import { useUserStore } from '../stores/useUserStore'
import { useTauri } from '../composables/useTauri'
import { useNetworkStatus } from '../composables/useNetworkStatus'
import { useArticleTab } from '../composables/useTabIntegration'
import { useTabStore } from '../stores/useTabStore'
import { useReviewStore } from '../stores/useReviewStore'
import { getStatusInfo, useStatusLabel } from '../composables/useStatusMap'
import type { ArticleDetail, ReviewOut } from '../api/types'
import DownloadButton from '../components/DownloadButton.vue'
import ReviewPanel from '../components/ReviewPanel.vue'
import DeleteButton from '../components/DeleteButton.vue'
import ScoreBadges from '../components/ScoreBadges.vue'
import { renderMathInHtml } from '../utils/math'
import { sanitizeTypstSvg } from '../utils/typst'
import {
  Bookmark,
  BookmarkCheck,
  History,
  Edit,
  GitFork,
  GitMerge,
  GitCommitHorizontal,
  Clock,
  MessageSquare,
  Eye,
  ArrowLeft,
  GitCompare,
  Check,
  X,
  Loader,
} from 'lucide-vue-next'
import { useArticleSync } from '../composables/useArticleSync'
import { useFollowCache } from '../composables/useFollowCache'
import DiffView from '../components/DiffView.vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const tabStore = useTabStore()
const reviewStore = useReviewStore()
const { t } = useI18n()
const { canRead, canWrite, getFallback } = useOffline()

const article = ref<ArticleDetail | null>(null)
const compiledHtml = ref('')
const loading = ref(true)
const errorMessage = ref('')
const activeTab = ref<'body' | 'comments'>('body')
const articleFormat = ref<'markdown' | 'typst'>('markdown')
const articleSourceContent = ref('')
const isForked = ref(false)

const id = route.params.id as string

// This component instance is ALWAYS for this specific article (enforced by
// :key="route.path" in the router-view). Capture the id at setup — it never
// changes for this instance.
const myArticleId = id

// Tab integration — register this article as a tab and sync title
const articleBodyRef = ref<HTMLElement | null>(null)
const articleTabId = tabStore.ensureTab('article', route.fullPath)
useArticleTab(articleTabId, computed(() => article.value?.title), articleBodyRef)

const isOwnArticle = computed(() => article.value?.is_own_article ?? false)

function handleDeleted() {
  router.push(`/user/${userStore.viewer?.id}`)
}

const isBookmarked = computed(() => article.value?.is_bookmarked ?? false)
const articleAuthorIds = computed(() => article.value?.authors.map(a => a.id) ?? [])
// Cached article detection (Tauri offline mode).
const tauri = useTauri()
const isFromCache = ref(false)
const cachedAt = ref<string | null>(null)
const commitHash = ref('')

const statusLabel = useStatusLabel(() => article.value?.status ?? '')
const statusClass = computed(() => getStatusInfo(article.value?.status ?? '').class)

// ── Review submission form ─────────────────────────────────────────────

const reviewScores = ref({ originality: 3, rigor: 3, completeness: 3, pedagogy: 3, impact: 3 })
const submittingReview = ref(false)
const reviewFormError = ref('')
const reviewFormSuccess = ref('')

// User's existing review (for pre-filling if already reviewed)
const myExistingReview = computed(() => {
  if (!userStore.viewer) return null
  return reviewStore.reviews.find(r => r.reviewer_id === userStore.viewer!.id) ?? null
})

const canUserReview = computed(() => {
  return userStore.viewer && !isOwnArticle.value
})

// ── Review comment state ─────────────────────────────────────────────────

const reviewComment = ref('')

// ── Reply state ─────────────────────────────────────────────────────────

const replyTexts = reactive<Record<string, string>>({})
const replyErrors = reactive<Record<string, string>>({})
const sendingReplies = reactive<Record<string, boolean>>({})
const expandedThreads = reactive(new Set<string>())

// ── Helpers ─────────────────────────────────────────────────────────────

function isMyReview(review: ReviewOut): boolean {
  return userStore.viewer != null && review.reviewer_id === userStore.viewer.id
}

// ── Sorted reviews (current user's review first, then self-reviews, then by date) ──

const sortedReviews = computed(() => {
  return [...reviewStore.reviews]
    .map(r => ({ r, ts: new Date(r.created_at).getTime() }))
    .sort((a, b) => {
      // Current user's review always first
      const aIsMine = isMyReview(a.r)
      const bIsMine = isMyReview(b.r)
      if (aIsMine && !bIsMine) return -1
      if (!aIsMine && bIsMine) return 1
      // Then self-reviews
      if (a.r.is_self_review && !b.r.is_self_review) return -1
      if (!a.r.is_self_review && b.r.is_self_review) return 1
      // Then by date
      return b.ts - a.ts
    })
    .map(x => x.r)
})

// ── Offline fallback: build ArticleDetail from Tauri/dev-mock draft ──────

function buildArticleFromDraft(draft: { id: string; account_id: string; title: string; content: string; format: string; updated_at: string }): ArticleDetail {
  const viewerId = userStore.viewer?.id
  return {
    id: draft.id,
    title: draft.title || 'Untitled',
    status: 'draft' as const,
    authors: [{ id: draft.account_id, name: userStore.viewer?.name || userStore.viewer?.username || draft.account_id, anonymous_name: '' }],
    commit_hash: '',
    fork_count: 0,
    forked_from: null,
    commit_count: 1,
    compiled_format: draft.format,
    compiled_output: draft.content,  // use raw content as compiled output
    compiled_pages: null,
    score: null,
    sink_eta: null,
    days_remaining: null,
    sink_duration_days: null,
    review_count: 0,
    is_bookmarked: false,
    is_own_article: viewerId === draft.account_id,
    created_at: draft.updated_at,
    updated_at: draft.updated_at,
  }
}

// ── Shared article loader (REST API with Tauri/dev-mock fallback) ─────────

async function loadArticle(articleId: string) {
  // 1. Try REST API first.
  try {
    article.value = await getArticle(articleId)
    commitHash.value = article.value.commit_hash || ''
    await loadCompiledContent()
    loadReviews()
    // Cache explicitly opened article for offline reading.
    if (articleSourceContent.value) {
      useFollowCache().setCachedArticle(articleId, article.value, {
        content: articleSourceContent.value,
        format: articleFormat.value,
      }).catch(() => {})
    }
    return
  } catch (e: any) {
    // 2. In Tauri/dev-mock mode: try cached article first, then draft, then git.
    //    Git is the source of truth — no cache chain to get stale.
    const isOffline = tauri.isTauri.value || tauri.isBrowserLocal.value
    if (isOffline) {
      // Try cached article (explicitly opened earlier).
      const cache = useFollowCache()
      const cached = await cache.getCachedArticle(articleId)
      if (cached) {
        article.value = cached.detail
        articleFormat.value = cached.source.format as 'markdown' | 'typst'
        articleSourceContent.value = cached.source.content
        if (cached.source.content) {
          const { parseMarkdown } = await import('../utils/markdown')
          compiledHtml.value = parseMarkdown(cached.source.content)
        }
        loadReviews()
        return
      }
      // Try local draft (own articles).
      const draft = await tauri.getDraft({ id: articleId })
      if (draft && !('error' in draft)) {
        const draftData = draft as { id: string; account_id: string; title: string; content: string; format: string; updated_at: string }
        article.value = buildArticleFromDraft(draftData)
        // Always get latest content + hash from git (source of truth)
        try {
          const history = await tauri.gitHistory({ article_id: articleId })
          if (history && !('error' in history) && Array.isArray(history) && history.length > 0) {
            commitHash.value = history[0].hash
            const gitContent = await tauri.gitShow({ article_id: articleId, commit_hash: commitHash.value })
            if (gitContent && typeof gitContent === 'string' && !gitContent.startsWith('{')) {
              article.value.compiled_output = gitContent
            }
          }
        } catch { /* keep draft content as fallback */ }
        await loadCompiledContent()
        return
      }
    }

    // 3. Neither source worked — show error.
    if (isOffline) {
      errorMessage.value = 'Could not open article. Try saving a draft first.'
    } else {
      const status = e?.response?.status
      if (status === 404) {
        errorMessage.value = 'Article not found.'
      } else {
        errorMessage.value = e.userMessage || 'Failed to load article. Is the server running?'
      }
    }
  }
}

// ── Lifecycle ───────────────────────────────────────────────────────────

onMounted(async () => {
  loadSyncMeta()
  try {
    await loadArticle(id)
  } finally {
    loading.value = false
  }
})

watch(() => route.params.id, async (newId) => {
  // With :key="route.path", this component instance owns exactly one article.
  // When navigating to a different article, Vue fires this watch BEFORE
  // onDeactivated — isActive guards don't work. Compare against the captured id.
  if (!newId || newId !== myArticleId) return
  loading.value = true
  reviewStore.reviews = []
  compiledHtml.value = ''
  activeTab.value = 'body'
  isFromCache.value = false
  cachedAt.value = null
  try {
    await loadArticle(newId as string)
  } finally {
    loading.value = false
  }
})

async function loadCompiledContent() {
  if (!article.value) return
  const isLocal = tauri.isTauri.value || tauri.isBrowserLocal.value

  let srcContent: string
  let srcFormat: string

  // In local/Tauri mode, content was already sourced from git in loadArticle.
  // compiled_output = git content (source of truth), not stale draft cache.
  if (isLocal) {
    srcContent = article.value.compiled_output || ''
    srcFormat = article.value.compiled_format || 'markdown'
    // Server articles (not local drafts): fetch source from server for compilation.
    if (!srcContent) {
      try {
        const src = await getArticleSource(id)
        srcContent = src.content
        srcFormat = src.format
      } catch {
        compiledHtml.value = ''
        return
      }
    }
  } else {
    // Web mode: fetch source from server to determine real format.
    // compiled_format is never populated in the DB (on-demand compile).
    try {
      const src = await getArticleSource(id)
      srcContent = src.content
      srcFormat = src.format
    } catch {
      compiledHtml.value = ''
      return
    }
  }
  articleFormat.value = srcFormat as 'markdown' | 'typst'
  articleSourceContent.value = srcContent

  const isTypst = srcFormat === 'typst'

  // ── Typst articles ────────────────────────────────────────────────
  if (isTypst) {
    if (isLocal) {
      try {
        const result = await tauri.compileTypst({ content: srcContent, format: 'typst' })
        if (result && typeof result === 'string') {
          compiledHtml.value = `<div class="typst-preview">${sanitizeTypstSvg(result)}</div>`
        } else if (result && typeof result === 'object' && 'error' in result) {
          compiledHtml.value = `<div class="typst-preview-error text-[#d73a49] p-4 font-mono text-sm">${(result as { error: string }).error}</div>`
        }
      } catch {
        compiledHtml.value = ''
      }
      return
    }

    // Web mode: compile Typst → SVG via server API
    try {
      const result = await compilePreview({ content: srcContent, format: 'typst' })
      compiledHtml.value = sanitizeTypstSvg(result.output)
    } catch {
      compiledHtml.value = ''
    }
    return
  }

  // ── Markdown articles ─────────────────────────────────────────────
  if (isLocal) {
    if (srcContent) {
      const { parseMarkdown } = await import('../utils/markdown')
      compiledHtml.value = parseMarkdown(srcContent)
    }
    return
  }

  // Web mode: prefer server-side compiled_output, else compile via API
  if (article.value.compiled_output) {
    compiledHtml.value = renderMathInHtml(article.value.compiled_output)
  } else {
    try {
      const result = await compilePreview({ content: srcContent, format: 'markdown' })
      compiledHtml.value = renderMathInHtml(result.output)
    } catch {
      compiledHtml.value = ''
    }
  }
}

async function loadReviews() {
  await reviewStore.fetchReviews(id)
}

const { isOnline } = useNetworkStatus()

// ── L4 Article sync ─────────────────────────────────────────────────────
const draftSyncMeta = ref<{ server_article_id?: string | null; server_commit_hash?: string | null } | null>(null)
const localHeadHash = ref<string | null>(null)
const showDiff = ref(false)
const remoteContent = ref('')
const localContent = ref('')
const diffError = ref<string | null>(null)

const draftId = () => myArticleId
const sid = () => draftSyncMeta.value?.server_article_id
const sch = () => draftSyncMeta.value?.server_commit_hash
const lh = () => localHeadHash.value

const {
  syncState,
  pushing,
  upload,
  pushUpdate,
  useRemote,
  getContentAtCommit,
  clearError: clearSyncError,
} = useArticleSync(draftId, sid, sch, lh)

async function loadSyncMeta() {
  if (!tauri.isTauri.value) return
  const result = await tauri.getDraft({ id: myArticleId })
  if (result && !('error' in result)) {
    draftSyncMeta.value = result as { server_article_id?: string | null; server_commit_hash?: string | null }
  }
  const history = await tauri.gitHistory({ article_id: myArticleId })
  if (history && !('error' in history) && Array.isArray(history) && history.length > 0) {
    localHeadHash.value = history[0].hash
  }
}

async function openDiffView() {
  const remoteHash = sch()
  const localHash = lh()
  if (!remoteHash || !localHash) {
    diffError.value = t('sync.cannotLoadDiff')
    return
  }
  const [remote, local] = await Promise.all([
    getContentAtCommit(remoteHash),
    getContentAtCommit(localHash),
  ])
  if (remote === null || local === null) {
    diffError.value = t('sync.cannotReadVersions')
    return
  }
  remoteContent.value = remote
  localContent.value = local
  showDiff.value = true
}

async function handleKeepLocal() {
  const ok = await pushUpdate()
  if (ok) {
    showDiff.value = false
    await loadSyncMeta()
    refreshArticle()
  }
}

async function handleUseRemote() {
  const remoteHash = sch()
  if (!remoteHash) return
  const ok = await useRemote(remoteHash)
  if (ok) {
    showDiff.value = false
    await loadSyncMeta()
    refreshArticle()
  }
}

function refreshArticle() {
  loadArticle(myArticleId)
  loadReviews()
}

async function toggleBookmark() {
  if (!article.value || !userStore.viewer) return

  // Silently ignore self-bookmark
  if (article.value.is_own_article) return

  const wasBookmarked = article.value.is_bookmarked
  article.value.is_bookmarked = !wasBookmarked

  // If server is reachable but we have no token, try to sync local creds first
  const needsSync = (userStore.isTauriMode || userStore.isBrowserLocal)
    && isOnline.value
    && !userStore.token?.value

  if (needsSync) {
    const synced = await userStore.trySyncServerAuth()
    if (!synced || !userStore.token?.value) {
      article.value.is_bookmarked = wasBookmarked
      return
    }
  }

  try {
    if ((tauri.isTauri.value || tauri.isBrowserLocal.value) && !isOnline.value) {
      if (wasBookmarked) {
        await tauri.removeBookmark({ user_id: userStore.viewer.id, article_id: article.value.id })
      } else {
        await tauri.addBookmark({ user_id: userStore.viewer.id, article_id: article.value.id })
      }
    } else {
      if (wasBookmarked) {
        await removeBookmark(article.value.id)
      } else {
        await addBookmark(article.value.id)
      }
    }
  } catch {
    article.value.is_bookmarked = wasBookmarked
  }
}

function toggleThread(reviewId: string) {
  if (expandedThreads.has(reviewId)) {
    expandedThreads.delete(reviewId)
  } else {
    expandedThreads.add(reviewId)
  }
}

async function handleSubmitReview() {
  if (!userStore.viewer) return
  submittingReview.value = true
  reviewFormError.value = ''
  reviewFormSuccess.value = ''
  const comment = reviewComment.value.trim()
  if (comment) reviewComment.value = ''
  try {
    const commitHash = (await getHistory(id)).commits?.[0]?.hash || 'unknown'
    const scope = article.value?.status === 'published' ? 'published' : 'pool' as const
    await reviewStore.submitReview(id, commitHash, scope, reviewScores.value, comment)
    reviewFormSuccess.value = t('article.reviewSubmitted')
  } catch (e: any) {
    reviewFormError.value = e.userMessage || 'Failed to submit review'
    if (comment) reviewComment.value = comment
  } finally {
    submittingReview.value = false
  }
}

async function updateSingleScore(reviewId: string, dim: string, value: number) {
  if (!userStore.viewer) return
  const oldValue = reviewStore.optimisticUpdateScore(reviewId, dim, value)
  if (oldValue === undefined) return
  try {
    const review = reviewStore.reviews.find(r => r.id === reviewId)!
    await reviewStore.updateScore(id, reviewId, review.commit_hash,
      review.scope as 'pool' | 'published', review.scores)
  } catch {
    reviewStore.revertScore(reviewId, dim, oldValue)
    reviewFormError.value = 'Failed to update score'
    setTimeout(() => { reviewFormError.value = '' }, 3000)
  }
}

async function handleReply(reviewId: string) {
  const text = replyTexts[reviewId]?.trim()
  if (!text) return
  sendingReplies[reviewId] = true
  replyErrors[reviewId] = ''
  try {
    await reviewStore.sendReply(id, reviewId, text)
    replyTexts[reviewId] = ''
  } catch {
    replyErrors[reviewId] = 'Failed to send'
    setTimeout(() => { replyErrors[reviewId] = '' }, 3000)
  } finally {
    sendingReplies[reviewId] = false
  }
}

function goBack() {
  // HistoryPage's goBack was fixed to use router.back(), so the infinite
  // loop ArticlePage ↔ HistoryPage is resolved. router.back() now correctly
  // returns to whichever page the user came from (UserPage, home, etc.).
  router.back()
}

function goToHistory() {
  router.push(`/articles/${id}/history`)
}

function goToEdit() {
  router.push(`/edit/${id}`)
}

async function handleFork() {
  if (!userStore.viewer) return
  try {
    const result = await forkArticle(id)
    isForked.value = true
    router.push(`/edit/${result.id}`)
  } catch (e) {
    console.error('Fork failed:', e)
  }
}

async function handleSinkExtension() {
  if (!article.value) return
  try {
    const result = await extendSink(id, { extra_days: 7 })
    article.value.days_remaining = result.days_remaining
  } catch (e) {
    console.error('Sink extension failed:', e)
  }
}

const mergeSubmitting = ref(false)
const mergeError = ref('')

async function handleMerge() {
  if (!article.value?.forked_from || !userStore.viewer) return
  mergeSubmitting.value = true
  mergeError.value = ''
  try {
    await createMergeProposal(article.value.forked_from, {
      fork_article_id: article.value.id,
      proposer_id: userStore.viewer.id,
    })
    router.push(`/articles/${article.value.forked_from}`)
  } catch (e) {
    mergeError.value = 'Merge proposal failed'
    console.error('Merge proposal failed:', e)
  } finally {
    mergeSubmitting.value = false
  }
}

defineExpose({ updateSingleScore, reviewStore, mergeError })
</script>

<template>
  <div class="article-page animate-fade-in">
    <!-- Back button -->
    <button
      class="flex items-center gap-1.5 text-sm text-ink-muted hover:text-ink mb-4 transition-colors duration-200"
      :aria-label="t('article.back')"
      @click="goBack"
    >
      <ArrowLeft class="w-4 h-4" stroke-width="2" />
      {{ t('common.back') }}
    </button>
    <!-- Loading -->
    <div v-if="loading" class="space-y-4 animate-pulse">
      <div class="skeleton h-8 w-3/4 mb-2" />
      <div class="skeleton h-5 w-1/2 mb-4" />
      <div class="skeleton h-3 w-full mb-2" />
      <div class="skeleton h-3 w-full" />
    </div>

    <template v-else-if="article">
      <!-- Google Scholar-style narrow top bar -->
      <div class="bg-card border border-divider rounded-lg p-4 mb-6">
        <!-- Status & bookmark row -->
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center gap-2">
            <span :class="statusClass">{{ statusLabel }}</span>
            <span v-if="article.forked_from" class="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-mono text-neutral bg-neutral/10 rounded">
              <GitFork class="w-3 h-3" stroke-width="2" />
              {{ t('card.forkBadge') }}
            </span>
            <span v-if="isFromCache && cachedAt" class="inline-flex items-center gap-1 px-2 py-0.5 text-xs text-ink-muted bg-[#21262d] rounded" :data-tooltip="'This article was cached and may be outdated'">
              <Clock class="w-3 h-3" stroke-width="2" />
              Cached {{ cachedAt }}
            </span>
          </div>
          <button
            v-if="!isOwnArticle"
            class="flex items-center justify-center w-7 h-7 rounded
                   text-ink-muted hover:text-accent hover:bg-accent/10
                   transition-colors duration-200"
            :aria-label="isBookmarked ? t('card.removeBookmark') : t('card.addBookmark')"
            :data-tooltip="isBookmarked ? t('card.removeBookmark') : t('card.addBookmark')"
            @click="toggleBookmark"
          >
            <BookmarkCheck v-if="isBookmarked" class="w-4 h-4 text-accent" stroke-width="2" />
            <Bookmark v-else class="w-4 h-4" stroke-width="2" />
          </button>
        </div>

        <!-- Title -->
        <h1 class="text-display-md font-heading font-bold text-ink mb-3 leading-tight">
          {{ article.title || t('card.untitled') }}
          <button
            v-if="syncState === 'conflict'"
            class="sync-icon-btn inline-flex align-middle ml-2"
            :title="t('sync.conflictTooltip')"
            @click="openDiffView"
          >
            <GitCompare :size="18" stroke-width="2" class="text-warning" />
          </button>
        </h1>

        <!-- Authors -->
        <div class="flex flex-wrap items-center gap-1.5 mb-3">
          <template v-for="(author, idx) in article.authors" :key="author.id">
            <router-link
              :to="`/user/${author.id}`"
              class="text-sm text-accent hover:text-accent-hover hover:underline no-underline"
            >
              {{ author.name }}
            </router-link>
            <span v-if="idx < article.authors.length - 1" class="text-ink-muted">,</span>
          </template>
        </div>

        <!-- Metadata + actions row -->
        <div class="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-ink-muted">
          <span class="flex items-center gap-1">
            <GitFork class="w-3 h-3" stroke-width="2" />
            {{ article.fork_count }} {{ t('common.forks') }}
          </span>
          <span class="flex items-center gap-1">
            <MessageSquare class="w-3 h-3" stroke-width="2" />
            {{ article.review_count }} {{ t('article.reviews') }}
          </span>
          <span v-if="article.days_remaining != null" class="flex items-center gap-1">
            <Clock class="w-3 h-3" stroke-width="2" />
            {{ article.days_remaining }}{{ t('card.dRemaining') }}
          </span>
          <span v-if="commitHash" class="flex items-center gap-1">
            <GitCommitHorizontal class="w-3 h-3" stroke-width="2" />
            <span class="font-mono">{{ commitHash.slice(0, 7) }}</span>
          </span>

          <div class="flex-1" />

          <!-- Action buttons -->
          <div class="flex items-center gap-1">
            <button
              class="flex items-center gap-1 px-2.5 py-1 text-xs text-ink-muted hover:text-ink hover:bg-[#21262d] rounded-md transition-colors"
              @click="goToHistory"
            >
              <History class="w-3 h-3" stroke-width="2" />
              {{ t('article.history') }}
            </button>

            <button
              v-if="isOwnArticle"
              class="flex items-center gap-1 px-2.5 py-1 text-xs text-ink-muted hover:text-ink hover:bg-[#21262d] rounded-md transition-colors"
              @click="goToEdit"
            >
              <Edit class="w-3 h-3" stroke-width="2" />
              {{ t('card.edit') }}
            </button>

            <DeleteButton
              v-if="isOwnArticle"
              :article-id="article?.id ?? ''"
              :author-id="article?.authors?.[0]?.id"
              @deleted="handleDeleted"
            />

            <button
              class="flex items-center gap-1 px-2.5 py-1 text-xs rounded-md transition-colors"
              :class="canWrite('article.fork')
                ? 'text-ink-muted hover:text-ink hover:bg-[#21262d]'
                : 'text-ink-muted/40 cursor-not-allowed'"
              :disabled="!canWrite('article.fork')"
              :data-tooltip="!canWrite('article.fork') ? t(getFallback('article.fork')) : ''"
              @click="handleFork"
            >
              <GitFork class="w-3 h-3" stroke-width="2" />
              {{ t('article.fork') }}
            </button>

            <DownloadButton
              format="source"
              :content="articleSourceContent"
              :content-format="articleFormat"
              :filename="article?.title"
              :commit-hash="commitHash"
              show-label
            />
            <DownloadButton
              format="compiled"
              :content="articleSourceContent"
              :content-format="articleFormat"
              :filename="article?.title"
              :commit-hash="commitHash"
              show-label
            />
            <DownloadButton
              format="repo"
              :content="''"
              :content-format="articleFormat"
              :article-id="article?.id"
              :filename="article?.title"
              :commit-hash="commitHash"
              show-label
            />

            <button
              v-if="isOwnArticle && article.status === 'sedimentation'"
              class="flex items-center gap-1 px-2.5 py-1 text-xs text-ink-muted hover:text-ink hover:bg-[#21262d] rounded-md transition-colors"
              @click="handleSinkExtension"
            >
              <Clock class="w-3 h-3" stroke-width="2" />
              Extend
            </button>

            <button
              v-if="isOwnArticle && article.forked_from"
              class="flex items-center gap-1 px-2.5 py-1 text-xs text-accent hover:text-accent/80 hover:bg-accent/10 rounded-md transition-colors"
              :aria-label="t('article.proposeMerge')"
              :disabled="mergeSubmitting"
              @click="handleMerge"
            >
              <GitMerge class="w-3 h-3" stroke-width="2" />
              {{ mergeSubmitting ? 'Proposing...' : 'Merge' }}
            </button>
            <span v-if="mergeError" class="text-[10px] text-[#d73a49] ml-2">{{ mergeError }}</span>
          </div>
        </div>

        <!-- Scores row -->
        <div class="flex items-center gap-3 mt-3 pt-3 border-t border-divider">
          <ScoreBadges :score="article.score" :highlight-first="true" :show-label="true" />
        </div>
      </div>

      <!-- Tab switcher -->
      <div class="flex items-center border-b border-divider mb-6">
        <button
          class="px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-[1px]"
          :class="activeTab === 'body'
            ? 'text-accent border-accent'
            : 'text-ink-muted border-transparent hover:text-ink'"
          @click="activeTab = 'body'"
        >
          <Eye class="w-3.5 h-3.5 inline mr-1.5" stroke-width="2" />
          {{ t('article.body') }}
        </button>
        <button
          class="px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-[1px]"
          :class="activeTab === 'comments'
            ? 'text-accent border-accent'
            : 'text-ink-muted border-transparent hover:text-ink'"
          @click="activeTab = 'comments'"
        >
          <MessageSquare class="w-3.5 h-3.5 inline mr-1.5" stroke-width="2" />
          {{ t('article.comments') }} ({{ article.review_count }})
        </button>
      </div>

      <!-- Tab content -->
      <div v-if="activeTab === 'body'" class="card p-6">
        <div
          ref="articleBodyRef"
          v-if="compiledHtml"
          class="prose-custom max-w-none"
          v-html="compiledHtml"
        />
        <p v-else class="text-ink-muted text-sm">
          No compiled content available.
        </p>
      </div>

      <div v-else class="card p-6">
        <ReviewPanel
          v-model:review-scores="reviewScores"
          v-model:review-comment="reviewComment"
          :sorted-reviews="sortedReviews"
          :reviews-loading="reviewStore.loading"
          :can-user-review="canUserReview"
          :my-existing-review="myExistingReview"
          :is-own-article="isOwnArticle"
          :viewer-id="userStore.viewer?.id ?? null"
          :article-author-ids="articleAuthorIds"
          :submitting-review="submittingReview"
          :review-form-error="reviewFormError"
          :review-form-success="reviewFormSuccess"
          :expanded-threads="expandedThreads"
          :reply-texts="replyTexts"
          :reply-errors="replyErrors"
          :sending-replies="sendingReplies"
          @submit-review="handleSubmitReview"
          @update-score="updateSingleScore"
          @send-reply="handleReply"
          @toggle-thread="toggleThread"
          @sign-in="userStore.showAuthModal = true"
        />
      </div>
    </template>

    <!-- Error state -->
    <div v-else class="card p-12 text-center">
      <p class="text-ink-muted">{{ errorMessage || 'Article not found.' }}</p>
    </div>

    <!-- L4 Diff View overlay -->
    <Teleport to="body">
      <div v-if="showDiff" class="diff-overlay" @click.self="showDiff = false">
        <div class="diff-panel">
          <div class="diff-header">
            <h3>{{ t('sync.diffTitle') }}</h3>
            <span class="text-xs text-ink-muted">{{ t('sync.diffSubtitle') }}</span>
            <button class="sync-close-btn" @click="showDiff = false">
              <X :size="18" stroke-width="2" />
            </button>
          </div>
          <div v-if="diffError" class="diff-error">
            {{ diffError }}
            <button @click="diffError = null">{{ t('sync.close') }}</button>
          </div>
          <div v-else-if="remoteContent && localContent" class="diff-content">
            <div class="diff-pane">
              <div class="diff-pane-label">{{ t('sync.remoteVersion') }}</div>
              <pre class="diff-pane-text">{{ remoteContent }}</pre>
            </div>
            <div class="diff-pane">
              <div class="diff-pane-label">{{ t('sync.localVersion') }}</div>
              <pre class="diff-pane-text">{{ localContent }}</pre>
            </div>
          </div>
          <div class="diff-actions">
            <button
              class="btn-primary"
              :disabled="pushing"
              @click="handleKeepLocal"
            >
              <Loader v-if="pushing" :size="16" stroke-width="2" class="animate-spin" />
              <Check v-else :size="16" stroke-width="2" />
              {{ t('sync.keepLocal') }}
            </button>
            <button
              class="btn-secondary"
              :disabled="pushing"
              @click="handleUseRemote"
            >
              <X :size="16" stroke-width="2" />
              {{ t('sync.useRemote') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.sync-icon-btn {
  display: inline-flex; align-items: center; justify-content: center;
  width: 28px; height: 28px; border: none; border-radius: 6px;
  background: transparent; cursor: pointer;
  transition: background-color 150ms ease;
}
.sync-icon-btn:hover { background-color: rgba(123, 140, 158, 0.15); }
.text-warning { color: #9e6a03; }

.diff-overlay {
  position: fixed; inset: 0; z-index: 100;
  background: rgba(0, 0, 0, 0.8);
  display: flex; align-items: center; justify-content: center;
}
.diff-panel {
  width: 90vw; max-width: 1200px; max-height: 90vh;
  background: #0d1117; border: 1px solid #30363d; border-radius: 12px;
  display: flex; flex-direction: column; overflow: hidden;
}
.diff-header {
  display: flex; align-items: center; gap: 12px;
  padding: 16px 20px; border-bottom: 1px solid #30363d;
}
.diff-header h3 { flex: 1; margin: 0; font-size: 16px; color: #e6edf3; }
.sync-close-btn { background: none; border: none; color: #8b949e; cursor: pointer; }
.diff-error { padding: 16px; color: #f85149; }
.diff-content { display: flex; flex: 1; overflow: hidden; }
.diff-pane { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.diff-pane + .diff-pane { border-left: 1px solid #30363d; }
.diff-pane-label { padding: 8px 16px; font-size: 12px; color: #8b949e; border-bottom: 1px solid #30363d; }
.diff-pane-text {
  flex: 1; overflow: auto; padding: 16px;
  font-family: monospace; font-size: 13px; color: #e6edf3; white-space: pre-wrap;
}
.diff-actions {
  display: flex; gap: 12px; padding: 16px 20px;
  border-top: 1px solid #30363d; justify-content: flex-end;
}
.btn-primary {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 16px; border: none; border-radius: 6px;
  background: #7b8c9e; color: #0d1117; font-weight: 600;
  cursor: pointer; font-size: 13px;
}
.btn-primary:hover { filter: brightness(1.15); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 16px; border: 1px solid #30363d; border-radius: 6px;
  background: #21262d; color: #e6edf3; font-size: 13px; cursor: pointer;
}
.btn-secondary:hover { background: #30363d; }
</style>
