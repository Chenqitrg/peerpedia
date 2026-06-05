<script setup lang="ts">
import { ref, onMounted, watch, computed, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getArticle, getArticleSource, getHistory, forkArticle } from '../api/articles'
import { getReviews as fetchReviews, createReview, postReviewMessage } from '../api/reviews'
import { compilePreview } from '../api/compile'
import { useUserStore } from '../stores/useUserStore'
import { useStatusMap } from '../composables/useStatusMap'
import type { ArticleDetail, ReviewOut } from '../api/types'
import FiveDimForm from '../components/FiveDimForm.vue'
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
  FileDown,
  FileText,
  Star,
  Send,
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const article = ref<ArticleDetail | null>(null)
const reviews = ref<ReviewOut[]>([])
const compiledHtml = ref('')
const reviewsLoading = ref(false)
const loading = ref(true)
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

// ── Reply state ─────────────────────────────────────────────────────────

const replyTexts = reactive<Record<string, string>>({})
const sendingReplies = reactive<Record<string, boolean>>({})

// ── Sorted reviews (self-reviews first) ─────────────────────────────────

const sortedReviews = computed(() => {
  return [...reviews.value].sort((a, b) => {
    if (a.is_self_review && !b.is_self_review) return -1
    if (!a.is_self_review && b.is_self_review) return 1
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  })
})

// ── Lifecycle ───────────────────────────────────────────────────────────

onMounted(async () => {
  try {
    article.value = await getArticle(id)
    await loadCompiledContent()
    loadReviews()
  } catch (e) {
    console.error('Failed to load article:', e)
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

async function handleSubmitReview() {
  if (!userStore.viewer) return
  submittingReview.value = true
  reviewFormError.value = ''
  reviewFormSuccess.value = ''
  try {
    const history = await getHistory(id)
    const latestHash = history.commits?.[0]?.hash || 'unknown'
    await createReview(id, {
      article_id: id,
      commit_hash: latestHash,
      scope: article.value?.status === 'published' ? 'published' : 'pool',
      scores: { ...reviewScores.value },
    })
    reviewFormSuccess.value = 'Review submitted'
    await loadReviews()
  } catch (e: any) {
    reviewFormError.value = e.userMessage || 'Failed to submit review'
  } finally {
    submittingReview.value = false
  }
}

async function handleReply(reviewId: string) {
  const text = replyTexts[reviewId]?.trim()
  if (!text) return
  sendingReplies[reviewId] = true
  try {
    await postReviewMessage(id, reviewId, { content: text })
    replyTexts[reviewId] = ''
    await loadReviews()
  } catch {
    // silently fail for reply
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

function handleSinkExtension() {
  if (article.value) {
    article.value.days_remaining = (article.value.days_remaining ?? 0) + 7
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
          <!-- Review submission form (logged-in non-authors only) -->
          <div v-if="canUserReview" class="border border-divider rounded-lg p-4 mb-6">
            <h4 class="text-sm font-semibold text-ink mb-3">
              {{ myExistingReview ? 'Update Your Review' : 'Submit Your Review' }}
            </h4>
            <FiveDimForm v-model="reviewScores" />
            <p v-if="reviewFormError" class="text-xs text-[#d73a49] mt-3">{{ reviewFormError }}</p>
            <p v-if="reviewFormSuccess" class="text-xs text-green-400 mt-3">{{ reviewFormSuccess }}</p>
            <button
              class="mt-3 px-4 py-1.5 text-xs font-semibold bg-accent text-[#0d1117] rounded-lg
                     hover:brightness-110 transition-all duration-200 disabled:opacity-50"
              :disabled="submittingReview"
              @click="handleSubmitReview"
            >
              {{ submittingReview ? 'Submitting...' : (myExistingReview ? 'Update Review' : 'Submit Review') }}
            </button>
          </div>

          <!-- Sign in prompt -->
          <div v-if="!userStore.viewer" class="text-xs text-ink-muted/60 mb-4">
            <button class="text-accent hover:underline" @click="userStore.showAuthModal = true">
              Sign in
            </button>
            to submit a review.
          </div>

          <!-- No reviews -->
          <div v-if="sortedReviews.length === 0" class="text-ink-muted text-sm">
            No reviews yet.
          </div>

          <!-- Review list -->
          <div v-else class="space-y-4">
            <div
              v-for="review in sortedReviews"
              :key="review.id"
              class="border rounded-lg p-4"
              :class="review.is_self_review
                ? 'border-accent/40 border-l-2 border-l-accent'
                : 'border-divider'"
            >
              <div class="flex items-center justify-between mb-2">
                <span class="text-sm font-semibold text-ink">
                  {{ review.is_self_review ? 'Author' : review.reviewer_name || review.reviewer_id?.substring(0, 8) }}
                  <span v-if="review.is_self_review" class="text-xs text-ink-muted/60 font-normal ml-1">(self-review)</span>
                </span>
                <span class="text-xs text-ink-muted">
                  {{ new Date(review.created_at).toLocaleDateString() }}
                </span>
              </div>
              <!-- Scores -->
              <div class="flex items-center gap-3 mb-3 text-xs font-mono">
                <span class="text-accent">O:{{ review.scores.originality }}</span>
                <span class="text-ink-muted">R:{{ review.scores.rigor }}</span>
                <span class="text-ink-muted">C:{{ review.scores.completeness }}</span>
                <span class="text-ink-muted">P:{{ review.scores.pedagogy }}</span>
                <span class="text-ink-muted">I:{{ review.scores.impact }}</span>
              </div>
              <!-- Thread messages -->
              <div v-if="review.thread && review.thread.length" class="space-y-2 border-t border-divider pt-3">
                <div
                  v-for="msg in review.thread"
                  :key="msg.created_at"
                  class="text-sm text-ink-muted pl-3 border-l-2 border-divider"
                >
                  <span class="text-xs text-ink-muted/60">
                    {{ (msg as any).author_name || msg.author_id?.substring(0, 8) }}
                  </span>
                  <p class="mt-0.5">{{ msg.content }}</p>
                </div>
              </div>
              <!-- Reply input (article author only) -->
              <div v-if="isOwnArticle" class="border-t border-divider pt-3 mt-3">
                <div class="flex items-center gap-2">
                  <input
                    v-model="replyTexts[review.id]"
                    type="text"
                    :placeholder="sendingReplies[review.id] ? 'Sending...' : 'Reply...'"
                    class="flex-1 bg-[#0d1117] border border-divider rounded px-3 py-1.5 text-xs
                           text-ink placeholder:text-ink-muted/50
                           focus:outline-none focus:ring-1 focus:ring-accent"
                    @keyup.enter="handleReply(review.id)"
                  />
                  <button
                    class="flex items-center justify-center w-7 h-7 rounded
                           text-ink-muted hover:text-accent hover:bg-accent/10
                           transition-colors duration-200"
                    :disabled="!replyTexts[review.id]?.trim() || sendingReplies[review.id]"
                    @click="handleReply(review.id)"
                  >
                    <Send class="w-3.5 h-3.5" stroke-width="2" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- Error state -->
    <div v-else class="card p-12 text-center">
      <p class="text-ink-muted">Article not found.</p>
    </div>
  </div>
</template>
