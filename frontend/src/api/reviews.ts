import apiClient from './client'

export async function getReviews(articleId: string) {
  const res = await apiClient.get(`/articles/${articleId}/reviews`)
  return res.data
}

export async function createReview(articleId: string, body: Record<string, unknown>) {
  const res = await apiClient.post(`/articles/${articleId}/reviews`, body)
  return res.data
}

export async function postReviewMessage(articleId: string, reviewId: string, authorId: string, body: { content: string }) {
  const res = await apiClient.post(`/articles/${articleId}/reviews/${reviewId}/messages`, body, {
    params: { author_id: authorId },
  })
  return res.data
}
