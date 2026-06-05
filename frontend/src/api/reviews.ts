import apiClient from './client'
import type { ReviewOut, ReviewCreatePayload, ReviewMessagePayload } from './types'

export async function getReviews(articleId: string): Promise<ReviewOut[]> {
  const res = await apiClient.get(`/articles/${articleId}/reviews`)
  return res.data
}

export async function createReview(articleId: string, body: ReviewCreatePayload): Promise<ReviewOut> {
  const res = await apiClient.post(`/articles/${articleId}/reviews`, body)
  return res.data
}

export async function postReviewMessage(articleId: string, reviewId: string, body: ReviewMessagePayload) {
  const res = await apiClient.post(`/articles/${articleId}/reviews/${reviewId}/messages`, body)
  return res.data
}
