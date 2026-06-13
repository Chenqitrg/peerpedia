// SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
// SPDX-License-Identifier: CC-BY-NC-SA-4.0

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getReviews, createReview, postReviewMessage } from '../api/reviews'
import type { ReviewOut, ReviewCreatePayload, FiveDimScores } from '../api/types'

export const useReviewStore = defineStore('review', () => {
  const reviews = ref<ReviewOut[]>([])
  const loading = ref(false)
  const error = ref('')

  /** Fetch all reviews for an article. */
  async function fetchReviews(articleId: string) {
    loading.value = true
    error.value = ''
    try {
      reviews.value = await getReviews(articleId)
    } catch(e) {
      console.warn('fetchReviews failed:', e)
      reviews.value = []
    } finally {
      loading.value = false
    }
  }

  /** Submit a new review with optional comment. */
  async function submitReview(
    articleId: string,
    commitHash: string,
    scope: 'pool' | 'published',
    scores: FiveDimScores,
    comment?: string,
  ): Promise<ReviewOut> {
    const review = await createReview(articleId, {
      article_id: articleId,
      commit_hash: commitHash,
      scope,
      scores: { ...scores },
    })
    if (comment) {
      try {
        await postReviewMessage(articleId, review.id, { content: comment })
      } catch {
        // comment failed but review succeeded
      }
    }
    // Refresh the list
    await fetchReviews(articleId)
    return review
  }

  /** Update an existing review's scores (upsert via createReview). */
  async function updateScore(
    articleId: string,
    reviewId: string,
    commitHash: string,
    scope: 'pool' | 'published',
    scores: FiveDimScores,
  ) {
    await createReview(articleId, {
      article_id: articleId,
      commit_hash: commitHash,
      scope,
      scores: { ...scores },
    })
  }

  /** Send a reply in a review thread. */
  async function sendReply(articleId: string, reviewId: string, content: string) {
    await postReviewMessage(articleId, reviewId, { content })
    await fetchReviews(articleId)
  }

  /** Optimistically update a single score dimension, revert on failure. */
  function optimisticUpdateScore(reviewId: string, dim: string, newValue: number) {
    const review = reviews.value.find(r => r.id === reviewId)
    if (!review) return
    const oldValue = review.scores[dim as keyof typeof review.scores]
    review.scores = { ...review.scores, [dim]: newValue }
    return oldValue
  }

  /** Revert an optimistic score update. */
  function revertScore(reviewId: string, dim: string, oldValue: number) {
    const review = reviews.value.find(r => r.id === reviewId)
    if (review) {
      review.scores = { ...review.scores, [dim]: oldValue }
    }
  }

  return {
    reviews,
    loading,
    error,
    fetchReviews,
    submitReview,
    updateScore,
    sendReply,
    optimisticUpdateScore,
    revertScore,
  }
})
