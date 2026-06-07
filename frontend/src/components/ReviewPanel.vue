<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useOffline } from '../composables/useOffline'
import StarRating from './StarRating.vue'
import ScoreBadges from './ScoreBadges.vue'
import ThreadReplyInput from './ThreadReplyInput.vue'
import { SCORE_DIMS } from '../api/constants'
import type { ReviewOut, FiveDimScores } from '../api/types'
import { ChevronRight, ChevronDown } from 'lucide-vue-next'

const { t } = useI18n()
const { canWrite, getFallback } = useOffline()

// ── Two-way bound form fields ──────────────────────────────────────────

const reviewScores = defineModel<FiveDimScores>('reviewScores', { required: true })
const reviewComment = defineModel<string>('reviewComment', { default: '' })

// ── One-way props ──────────────────────────────────────────────────────

defineProps<{
  sortedReviews: ReviewOut[]
  reviewsLoading: boolean
  canUserReview: boolean
  myExistingReview: ReviewOut | null
  isOwnArticle: boolean
  viewerId: string | null
  articleAuthorIds: string[]
  submittingReview: boolean
  reviewFormError: string
  reviewFormSuccess: string
  expandedThreads: Set<string>
  replyTexts: Record<string, string>
  replyErrors: Record<string, string>
  sendingReplies: Record<string, boolean>
}>()

// ── Emits ──────────────────────────────────────────────────────────────

const emit = defineEmits<{
  'submit-review': []
  'update-score': [reviewId: string, dim: string, value: number]
  'send-reply': [reviewId: string]
  'toggle-thread': [reviewId: string]
  'sign-in': []
}>()
</script>

<template>
  <div>
    <div v-if="reviewsLoading" class="text-ink-muted text-sm">Loading comments...</div>

    <div v-else>
      <!-- Review submission form -->
      <!-- Offline: cannot write comments -->
      <div v-if="canUserReview && !myExistingReview && !canWrite('article.comments')" class="mb-6 p-4 border border-divider rounded-lg opacity-50 cursor-not-allowed">
        <p class="text-xs text-ink-muted mb-2 font-medium">Write a review</p>
        <p class="text-xs text-ink-muted/60">{{ t(getFallback('article.comments')) }}</p>
      </div>

      <div v-else-if="canUserReview && !myExistingReview" class="mb-6 p-4 border border-divider rounded-lg">
        <p class="text-xs text-ink-muted mb-3 font-medium">Write a review</p>
        <div class="flex flex-wrap items-center gap-x-3 gap-y-1 mb-3">
          <span v-for="dim in SCORE_DIMS" :key="dim.key" class="inline-flex items-center gap-1">
            <span class="text-xs text-ink-muted font-mono w-3 text-right">{{ dim.label }}</span>
            <StarRating
              :modelValue="reviewScores[dim.key]"
              size="sm"
              @update:modelValue="v => reviewScores = { ...reviewScores, [dim.key]: v }"
            />
          </span>
        </div>
        <textarea
          v-model="reviewComment"
          rows="2"
          :placeholder="t('article.commentPlaceholder')"
          class="w-full bg-[#0d1117] border border-divider rounded-lg px-3 py-2 text-xs
                 text-ink placeholder:text-ink-muted/50 resize-none
                 focus:outline-none focus:ring-1 focus:ring-accent mb-3"
        ></textarea>
        <div class="flex items-center justify-between">
          <button
            class="px-4 py-1.5 text-xs font-semibold bg-accent text-[#0d1117] rounded-md
                   hover:brightness-110 transition-all duration-200 disabled:opacity-50"
            :disabled="submittingReview"
            @click="emit('submit-review')"
          >
            {{ submittingReview ? 'Submitting...' : 'Submit Review' }}
          </button>
          <p v-if="reviewFormError" class="text-xs text-[#d73a49]">{{ reviewFormError }}</p>
          <p v-if="reviewFormSuccess" class="text-xs text-green-400">{{ reviewFormSuccess }}</p>
        </div>
      </div>

      <!-- Sign in prompt -->
      <div v-if="!viewerId" class="text-xs text-ink-muted/60 mb-4">
        <button class="text-accent hover:underline" @click="emit('sign-in')">
          Sign in
        </button>
        to submit a review.
      </div>

      <!-- No reviews yet -->
      <div v-if="sortedReviews.length === 0 && !canUserReview" class="text-ink-muted text-sm">
        No reviews yet.
      </div>

      <!-- Review list -->
      <div v-if="sortedReviews.length > 0" class="space-y-3">
        <div
          v-for="review in sortedReviews"
          :key="review.id"
          class="border rounded-lg p-4"
          :class="review.reviewer_id === viewerId
            ? 'border-accent/40 border-l-2 border-l-accent'
            : 'border-divider'"
        >
          <!-- Header -->
          <div class="flex items-center justify-between mb-3">
            <span class="text-sm font-semibold text-ink">
              {{ review.is_self_review ? 'Author' : review.reviewer_name || review.reviewer_id?.substring(0, 8) }}
              <span v-if="review.is_self_review" class="text-xs text-ink-muted/60 font-normal ml-1">(self-review)</span>
              <span v-if="review.reviewer_id === viewerId && !review.is_self_review" class="text-xs text-accent/80 font-normal ml-1">(you)</span>
            </span>
            <span class="text-xs text-ink-muted">{{ new Date(review.created_at).toLocaleString() }}</span>
          </div>

          <!-- Scores: editable for own review, read-only for others -->
          <ScoreBadges
            :score="review.scores"
            :editable="review.reviewer_id === viewerId"
            class="mb-3"
            @update-score="(dimKey: string, value: number) => emit('update-score', review.id, dimKey, value)"
          />

          <!-- Thread drawer (has messages) -->
          <div v-if="review.thread && review.thread.length">
            <button
              class="flex items-center gap-1.5 text-xs text-ink-muted hover:text-ink transition-colors"
              @click="emit('toggle-thread', review.id)"
            >
              <ChevronDown v-if="expandedThreads.has(review.id)" class="w-3.5 h-3.5" />
              <ChevronRight v-else class="w-3.5 h-3.5" />
              {{ t('article.thread') }} ({{ review.thread.length }})
            </button>

            <div v-if="expandedThreads.has(review.id)" class="mt-3 space-y-3">
              <div
                v-for="(msg, msgIdx) in review.thread"
                :key="msg.author_id + ':' + msg.created_at + ':' + msgIdx"
                class="flex"
                :class="articleAuthorIds.includes(msg.author_id) ? 'justify-start' : 'justify-end'"
              >
                <div
                  class="max-w-[75%] rounded-xl px-3 py-2 text-sm"
                  :class="articleAuthorIds.includes(msg.author_id)
                    ? 'bg-[#21262d] text-ink rounded-bl-md'
                    : 'bg-accent/15 border border-accent/30 text-ink rounded-br-md'"
                >
                  <span class="text-[10px] text-ink-muted/50 block mb-0.5">
                    {{ new Date(msg.created_at).toLocaleString() }}
                  </span>
                  <p class="leading-relaxed">{{ msg.content }}</p>
                </div>
              </div>

              <div v-if="isOwnArticle || review.reviewer_id === viewerId">
                <ThreadReplyInput
                  :model-value="replyTexts[review.id] || ''"
                  :disabled="sendingReplies[review.id]"
                  @send="emit('send-reply', review.id)"
                />
                <p v-if="replyErrors[review.id]" class="text-[10px] text-[#d73a49] mt-1">{{ replyErrors[review.id] }}</p>
              </div>

              <p v-else-if="viewerId" class="text-[10px] text-ink-muted/40 italic">
                {{ t('article.threadRestricted') }}
              </p>
            </div>
          </div>

          <!-- Empty thread: start conversation (own review only) -->
          <div v-if="review.reviewer_id === viewerId && (!review.thread || !review.thread.length)" class="mt-2">
            <ThreadReplyInput
              :model-value="replyTexts[review.id] || ''"
              placeholder="Start a conversation..."
              :disabled="sendingReplies[review.id]"
              @send="emit('send-reply', review.id)"
            />
            <p v-if="replyErrors[review.id]" class="text-[10px] text-[#d73a49] mt-1">{{ replyErrors[review.id] }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
