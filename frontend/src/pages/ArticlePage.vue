<script setup lang="ts">
import { ref, onMounted, watch, computed, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getArticle, getArticleSource, getHistory, forkArticle, extendSink } from '../api/articles'
import { getReviews as fetchReviews, createReview, postReviewMessage } from '../api/reviews'
import { compilePreview } from '../api/compile'
import { useUserStore } from '../stores/useUserStore'
import { useStatusMap } from '../composables/useStatusMap'
import type { ArticleDetail, ReviewOut, ThreadMessage } from '../api/types'
import StarRating from '../components/StarRating.vue'
import ThreadReplyInput from '../components/ThreadReplyInput.vue'
import { SCORE_DIMS } from '../api/constants'
import katex from 'katex'
import {
  Bookmark,
  BookmarkCheck,
  History,
  Edit,
  GitFork,
  GitMerge,
  Clock,
  MessageSquare,
  Eye,
  ChevronRight,
  ChevronDown,
  FileDown,
  FileText,
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const article = ref<ArticleDetail | null>(null)
const reviews = ref<ReviewOut[]>([])
const compiledHtml = ref('')
const reviewsLoading = ref(false)
const loading = ref(true)
const errorMessage = ref('')
const activeTab = ref<'body' | 'comments'>('body')
const isForked = ref(false)

const id = route.params.id as string

const isOwnArticle = computed(() => article.value?.is_own_article ?? false)
const isBookmarked = computed(() => article.value?.is_bookmarked ?? false)

const { statusLabel, statusClass } = useStatusMap(() => article.value?.status ?? '')

// ── Review submission form ─────────────────────────────────────────────

const reviewScores = ref({ originality: 3, rigor: 3, completeness: 3, pedagogy: 3, impact: 3 })
const submittingReview = ref(false)
const reviewFormError = ref('')
const reviewFormSuccess = ref('')

// User's existing review (for pre-filling if already reviewed)
const myExistingReview = computed(() => {
  if (!userStore.viewer) return null
  return reviews.value.find(r => r.reviewer_id === userStore.viewer!.id) ?? null
})

const canUserReview = computed(() => {
  return userStore.viewer && !isOwnArticle.value
})

// ── Hover-to-edit state ──────────────────────────────────────────────────

const hoveredDim = ref<string | null>(null)
const hoverTimer = ref<ReturnType<typeof setTimeout> | null>(null)
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

function canReplyInThread(review: ReviewOut): boolean {
  if (!userStore.viewer) return false
  return isOwnArticle.value || review.reviewer_id === userStore.viewer.id
}

function onDimEnter(review: ReviewOut, dimKey: string) {
  if (!isMyReview(review)) return
  if (hoverTimer.value) { clearTimeout(hoverTimer.value); hoverTimer.value = null }
  hoveredDim.value = review.id + ':' + dimKey
}

function onDimLeave() {
  hoverTimer.value = setTimeout(() => { hoveredDim.value = null }, 100)
}

// ── Sorted reviews (current user's review first, then self-reviews, then by date) ──

const sortedReviews = computed(() => {
  return [...reviews.value]
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

// ── Lifecycle ───────────────────────────────────────────────────────────

onMounted(async () => {
  try {
    article.value = await getArticle(id)
    await loadCompiledContent()
    loadReviews()
  } catch (e: any) {
    const status = e?.response?.status
    if (status === 404) {
      errorMessage.value = 'Article not found.'
    } else {
      errorMessage.value = e.userMessage || 'Failed to load article. Is the server running?'
    }
  } finally {
    loading.value = false
  }
})

watch(() => route.params.id, async (newId) => {
  if (!newId) return
  loading.value = true
  reviews.value = []
  compiledHtml.value = ''
  activeTab.value = 'body'
  try {
    article.value = await getArticle(newId as string)
    await loadCompiledContent()
    loadReviews()
  } catch (e) {
    console.error('Failed to load article:', e)
  } finally {
    loading.value = false
  }
})

function renderMathInHtml(html: string): string {
  // Replace katex-display spans with KaTeX rendered output
  let result = html
  // Display math: <span class="katex-display">$$...$$</span>
  result = result.replace(/<span class="katex-display">\$\$(.+?)\$\$<\/span>/gs, (_, tex) => {
    try {
      return katex.renderToString(tex.trim(), { displayMode: true, throwOnError: false })
    } catch { return _ }
  })
  // Inline math: <span class="katex-inline">$...$</span>
  result = result.replace(/<span class="katex-inline">\$(.+?)\$<\/span>/gs, (_, tex) => {
    try {
      return katex.renderToString(tex.trim(), { displayMode: false, throwOnError: false })
    } catch { return _ }
  })
  return result
}

async function loadCompiledContent() {
  if (!article.value) return
  let html = ''
  if (article.value.compiled_output) {
    html = article.value.compiled_output
  } else {
    try {
      const src = await getArticleSource(id)
      const result = await compilePreview({ content: src.content, format: src.format as 'markdown' | 'typst' })
      html = result.output
    } catch {
      compiledHtml.value = ''
      return
    }
  }
  compiledHtml.value = renderMathInHtml(html)
}

async function loadReviews() {
  reviewsLoading.value = true
  try {
    reviews.value = await fetchReviews(id)
  } catch {
    reviews.value = []
  } finally {
    reviewsLoading.value = false
  }
}

function toggleBookmark() {
  if (article.value) {
    article.value.is_bookmarked = !article.value.is_bookmarked
  }
}

function toggleThread(reviewId: string) {
  if (expandedThreads.has(reviewId)) {
    expandedThreads.delete(reviewId)
  } else {
    expandedThreads.add(reviewId)
  }
}

function isAuthorMessage(msg: ThreadMessage): boolean {
  if (!article.value) return false
  const authorIds = article.value.authors.map(a => a.id)
  return authorIds.includes(msg.author_id)
}

async function handleSubmitReview() {
  if (!userStore.viewer) return
  submittingReview.value = true
  reviewFormError.value = ''
  reviewFormSuccess.value = ''
  const comment = reviewComment.value.trim()
  // Clear comment early to prevent duplicate on retry
  if (comment) reviewComment.value = ''
  try {
    const commitHash = (await getHistory(id)).commits?.[0]?.hash || 'unknown'
    const result = await createReview(id, {
      article_id: id,
      commit_hash: commitHash,
      scope: article.value?.status === 'published' ? 'published' : 'pool',
      scores: { ...reviewScores.value },
    })
    if (comment) {
      try {
        await postReviewMessage(id, result.id, { content: comment })
      } catch {
        reviewFormError.value = 'Review submitted but comment failed to send. You can reply in the thread.'
      }
    }
    if (!reviewFormError.value) reviewFormSuccess.value = 'Review submitted'
    await loadReviews()
  } catch (e: any) {
    reviewFormError.value = e.userMessage || 'Failed to submit review'
    // Restore comment so user can retry
    if (comment) reviewComment.value = comment
  } finally {
    submittingReview.value = false
  }
}

async function updateSingleScore(reviewId: string, dim: string, value: number) {
  if (!userStore.viewer) return
  const review = reviews.value.find(r => r.id === reviewId)
  if (!review) return
  const updatedScores = { ...review.scores, [dim]: value }
  // Optimistic update — update local state immediately
  review.scores = updatedScores
  try {
    await createReview(id, {
      article_id: id,
      commit_hash: review.commit_hash,
      scope: review.scope as 'pool' | 'published',
      scores: updatedScores,
    })
  } catch {
    // Revert on failure
    review.scores = { ...review.scores, [dim]: review.scores[dim as keyof typeof review.scores] }
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
    await postReviewMessage(id, reviewId, { content: text })
    replyTexts[reviewId] = ''
    await loadReviews()
  } catch {
    replyErrors[reviewId] = 'Failed to send'
    setTimeout(() => { replyErrors[reviewId] = '' }, 3000)
  } finally {
    sendingReplies[reviewId] = false
  }
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
</script>

<template>
  <div class="article-page animate-fade-in">
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
              fork
            </span>
          </div>
          <button
            class="flex items-center justify-center w-7 h-7 rounded
                   text-ink-muted hover:text-accent hover:bg-accent/10
                   transition-colors duration-200"
            :aria-label="isBookmarked ? 'Remove bookmark' : 'Add bookmark'"
            :title="isBookmarked ? 'Remove bookmark' : 'Add bookmark'"
            @click="toggleBookmark"
          >
            <BookmarkCheck v-if="isBookmarked" class="w-4 h-4 text-accent" stroke-width="2" />
            <Bookmark v-else class="w-4 h-4" stroke-width="2" />
          </button>
        </div>

        <!-- Title -->
        <h1 class="text-display-md font-heading font-bold text-ink mb-3 leading-tight">
          {{ article.title || 'Untitled' }}
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
            {{ article.fork_count }} forks
          </span>
          <span class="flex items-center gap-1">
            <MessageSquare class="w-3 h-3" stroke-width="2" />
            {{ article.review_count }} reviews
          </span>
          <span v-if="article.days_remaining != null" class="flex items-center gap-1">
            <Clock class="w-3 h-3" stroke-width="2" />
            {{ article.days_remaining }}d remaining in pool
          </span>

          <div class="flex-1" />

          <!-- Action buttons -->
          <div class="flex items-center gap-1">
            <button
              class="flex items-center gap-1 px-2.5 py-1 text-xs text-ink-muted hover:text-ink hover:bg-[#21262d] rounded-md transition-colors"
              @click="goToHistory"
            >
              <History class="w-3 h-3" stroke-width="2" />
              History
            </button>

            <button
              v-if="isOwnArticle"
              class="flex items-center gap-1 px-2.5 py-1 text-xs text-ink-muted hover:text-ink hover:bg-[#21262d] rounded-md transition-colors"
              @click="goToEdit"
            >
              <Edit class="w-3 h-3" stroke-width="2" />
              Edit
            </button>

            <button
              class="flex items-center gap-1 px-2.5 py-1 text-xs text-ink-muted hover:text-ink hover:bg-[#21262d] rounded-md transition-colors"
              @click="handleFork"
            >
              <GitFork class="w-3 h-3" stroke-width="2" />
              Fork
            </button>

            <a
              :href="`/api/v1/articles/${id}/download/source`"
              aria-label="Download source"
              class="flex items-center gap-1 px-2.5 py-1 text-xs text-ink-muted hover:text-ink hover:bg-[#21262d] rounded-md transition-colors no-underline"
            >
              <FileDown class="w-3 h-3" stroke-width="2" />
              Source
            </a>

            <a
              :href="`/api/v1/articles/${id}/download/pdf`"
              aria-label="Download PDF"
              class="flex items-center gap-1 px-2.5 py-1 text-xs text-ink-muted hover:text-ink hover:bg-[#21262d] rounded-md transition-colors no-underline"
            >
              <FileText class="w-3 h-3" stroke-width="2" />
              PDF
            </a>

            <button
              v-if="isOwnArticle && article.status === 'sedimentation'"
              class="flex items-center gap-1 px-2.5 py-1 text-xs text-ink-muted hover:text-ink hover:bg-[#21262d] rounded-md transition-colors"
              @click="handleSinkExtension"
            >
              <Clock class="w-3 h-3" stroke-width="2" />
              Extend
            </button>
          </div>
        </div>

        <!-- Scores row -->
        <div v-if="article.score" class="flex items-center gap-3 mt-3 pt-3 border-t border-divider">
          <span class="text-xs text-ink-muted font-semibold">Scores</span>
          <span class="text-xs font-mono text-accent font-semibold">O:{{ article.score.originality }}</span>
          <span class="text-xs font-mono text-ink-muted">R:{{ article.score.rigor }}</span>
          <span class="text-xs font-mono text-ink-muted">C:{{ article.score.completeness }}</span>
          <span class="text-xs font-mono text-ink-muted">P:{{ article.score.pedagogy }}</span>
          <span class="text-xs font-mono text-ink-muted">I:{{ article.score.impact }}</span>
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
          Body
        </button>
        <button
          class="px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-[1px]"
          :class="activeTab === 'comments'
            ? 'text-accent border-accent'
            : 'text-ink-muted border-transparent hover:text-ink'"
          @click="activeTab = 'comments'"
        >
          <MessageSquare class="w-3.5 h-3.5 inline mr-1.5" stroke-width="2" />
          Comments ({{ article.review_count }})
        </button>
      </div>

      <!-- Tab content -->
      <div v-if="activeTab === 'body'" class="card p-6">
        <div
          v-if="compiledHtml"
          class="prose-custom max-w-none"
          v-html="compiledHtml"
        />
        <p v-else class="text-ink-muted text-sm">
          No compiled content available.
        </p>
      </div>

      <div v-else class="card p-6">
        <div v-if="reviewsLoading" class="text-ink-muted text-sm">Loading comments...</div>

        <div v-else>
          <!-- Review submission form (logged-in non-author, no review yet) -->
          <div v-if="canUserReview && !myExistingReview" class="mb-6 p-4 border border-divider rounded-lg">
            <p class="text-xs text-ink-muted mb-3 font-medium">Write a review</p>
            <div class="flex flex-wrap items-center gap-x-3 gap-y-1 mb-3">
              <span v-for="dim in SCORE_DIMS" :key="dim.key" class="inline-flex items-center gap-1">
                <span class="text-xs text-ink-muted font-mono w-3 text-right">{{ dim.label }}</span>
                <StarRating
                  :modelValue="reviewScores[dim.key]"
                  size="sm"
                  @update:modelValue="v => reviewScores[dim.key] = v"
                />
              </span>
            </div>
            <!-- Comment input -->
            <textarea
              v-model="reviewComment"
              rows="2"
              placeholder="Write a comment (optional)..."
              class="w-full bg-[#0d1117] border border-divider rounded-lg px-3 py-2 text-xs
                     text-ink placeholder:text-ink-muted/50 resize-none
                     focus:outline-none focus:ring-1 focus:ring-accent mb-3"
            ></textarea>
            <div class="flex items-center justify-between">
              <button
                class="px-4 py-1.5 text-xs font-semibold bg-accent text-[#0d1117] rounded-md
                       hover:brightness-110 transition-all duration-200 disabled:opacity-50"
                :disabled="submittingReview"
                @click="handleSubmitReview"
              >
                {{ submittingReview ? 'Submitting...' : 'Submit Review' }}
              </button>
              <p v-if="reviewFormError" class="text-xs text-[#d73a49]">{{ reviewFormError }}</p>
              <p v-if="reviewFormSuccess" class="text-xs text-green-400">{{ reviewFormSuccess }}</p>
            </div>
          </div>

          <!-- Sign in prompt -->
          <div v-if="!userStore.viewer" class="text-xs text-ink-muted/60 mb-4">
            <button class="text-accent hover:underline" @click="userStore.showAuthModal = true">
              Sign in
            </button>
            to submit a review.
          </div>

          <!-- No reviews -->
          <div v-if="sortedReviews.length === 0 && !canUserReview" class="text-ink-muted text-sm">
            No reviews yet.
          </div>

          <!-- Review list -->
          <div v-if="sortedReviews.length > 0" class="space-y-3">
            <div
              v-for="review in sortedReviews"
              :key="review.id"
              class="border rounded-lg p-4"
              :class="isMyReview(review)
                ? 'border-accent/40 border-l-2 border-l-accent'
                : 'border-divider'"
            >
              <!-- Header -->
              <div class="flex items-center justify-between mb-3">
                <span class="text-sm font-semibold text-ink">
                  {{ review.is_self_review ? 'Author' : review.reviewer_name || review.reviewer_id?.substring(0, 8) }}
                  <span v-if="review.is_self_review" class="text-xs text-ink-muted/60 font-normal ml-1">(self-review)</span>
                  <span v-if="isMyReview(review) && !review.is_self_review" class="text-xs text-accent/80 font-normal ml-1">(you)</span>
                </span>
                <span class="text-xs text-ink-muted">
                  {{ new Date(review.created_at).toLocaleString() }}
                </span>
              </div>

              <!-- Score row: hover-to-edit for my review, static text for others -->
              <div class="flex flex-wrap items-center gap-x-3 gap-y-1 mb-3 text-xs font-mono">
                <span
                  v-for="dim in SCORE_DIMS"
                  :key="dim.key"
                  class="inline-flex items-center gap-0.5"
                  :class="isMyReview(review) ? 'cursor-default' : ''"
                  @mouseenter="onDimEnter(review, dim.key)"
                  @mouseleave="onDimLeave()"
                >
                  <template v-if="hoveredDim === review.id + ':' + dim.key && isMyReview(review)">
                    <span class="text-ink-muted text-xs">{{ dim.label }}&nbsp;</span>
                    <StarRating
                      :modelValue="review.scores[dim.key]"
                      size="sm"
                      @update:modelValue="v => updateSingleScore(review.id, dim.key, v)"
                    />
                  </template>
                  <template v-else>
                    <span :class="dim.key === 'originality' ? 'text-accent font-semibold' : 'text-ink-muted'">
                      {{ dim.label }}:{{ review.scores[dim.key] }}
                    </span>
                  </template>
                </span>
              </div>

              <!-- Thread drawer (shown for all reviews that have messages) -->
              <div v-if="review.thread && review.thread.length">
                <button
                  class="flex items-center gap-1.5 text-xs text-ink-muted hover:text-ink transition-colors"
                  @click="toggleThread(review.id)"
                >
                  <ChevronDown
                    v-if="expandedThreads.has(review.id)"
                    class="w-3.5 h-3.5 transition-transform duration-200"
                  />
                  <ChevronRight
                    v-else
                    class="w-3.5 h-3.5 transition-transform duration-200"
                  />
                  Thread ({{ review.thread.length }})
                </button>

                <!-- iMessage-style messages -->
                <div v-if="expandedThreads.has(review.id)" class="mt-3 space-y-3">
                  <div
                    v-for="(msg, msgIdx) in review.thread"
                    :key="msg.author_id + ':' + msg.created_at + ':' + msgIdx"
                    class="flex"
                    :class="isAuthorMessage(msg) ? 'justify-start' : 'justify-end'"
                  >
                    <div
                      class="max-w-[75%] rounded-xl px-3 py-2 text-sm"
                      :class="isAuthorMessage(msg)
                        ? 'bg-[#21262d] text-ink rounded-bl-md'
                        : 'bg-accent/15 border border-accent/30 text-ink rounded-br-md'"
                    >
                      <span class="text-[10px] text-ink-muted/50 block mb-0.5">
                        {{ msg.author_name || msg.author_id?.substring(0, 8) }}
                      </span>
                      <p class="leading-relaxed">{{ msg.content }}</p>
                    </div>
                  </div>

                  <!-- Reply input (only author + reviewer can reply) -->
                  <div v-if="canReplyInThread(review)">
                    <ThreadReplyInput
                      v-model="replyTexts[review.id]"
                      :disabled="sendingReplies[review.id]"
                      @send="handleReply(review.id)"
                    />
                    <p v-if="replyErrors[review.id]" class="text-[10px] text-[#d73a49] mt-1">{{ replyErrors[review.id] }}</p>
                  </div>

                  <!-- Read-only indicator for bystanders -->
                  <p v-else-if="userStore.viewer" class="text-[10px] text-ink-muted/40 italic">
                    Only the author and reviewer can participate in this thread.
                  </p>
                </div>
              </div>

              <!-- Empty thread: input to start conversation (only on my review) -->
              <div v-if="isMyReview(review) && (!review.thread || !review.thread.length)" class="mt-2">
                <ThreadReplyInput
                  v-model="replyTexts[review.id]"
                  placeholder="Start a conversation..."
                  :disabled="sendingReplies[review.id]"
                  @send="handleReply(review.id)"
                />
                <p v-if="replyErrors[review.id]" class="text-[10px] text-[#d73a49] mt-1">{{ replyErrors[review.id] }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- Error state -->
    <div v-else class="card p-12 text-center">
      <p class="text-ink-muted">{{ errorMessage || 'Article not found.' }}</p>
      <button v-if="errorMessage && !errorMessage.includes('not found')" class="btn-outline mt-4" @click="loadArticle()">Retry</button>
    </div>

  </div>
</template>
