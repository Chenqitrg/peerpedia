import apiClient from './client'
import type { Bookmark } from './types'

export async function fetchBookmarks(userId: number): Promise<Bookmark[]> {
  const res = await apiClient.get('/bookmarks', { params: { user_id: userId } })
  return res.data
}

export async function addBookmark(userId: number, articleId: number): Promise<Bookmark> {
  const res = await apiClient.post('/bookmarks', null, { params: { user_id: userId, article_id: articleId } })
  return res.data
}

export async function removeBookmark(articleId: number, userId: number): Promise<void> {
  await apiClient.delete(`/bookmarks/${articleId}`, { params: { user_id: userId } })
}
