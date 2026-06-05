import apiClient from './client'
import type { Bookmark } from './types'

export async function fetchBookmarks(userId: string): Promise<Bookmark[]> {
  const res = await apiClient.get('/bookmarks', { params: { user_id: userId } })
  const data = res.data
  // Backend returns { bookmarks: [...] }
  if (data && Array.isArray(data.bookmarks)) {
    return data.bookmarks.map((b: any) => ({
      id: b.article_id,
      user_id: userId,
      article_id: b.article_id,
      created_at: b.created_at || '',
    }))
  }
  return []
}

export async function addBookmark(userId: string, articleId: string): Promise<Bookmark> {
  const res = await apiClient.post('/bookmarks', null, { params: { user_id: userId, article_id: articleId } })
  return res.data
}

export async function removeBookmark(articleId: string, userId: string): Promise<void> {
  await apiClient.delete(`/bookmarks/${articleId}`, { params: { user_id: userId } })
}
