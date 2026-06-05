import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getArticles, getArticle, createArticle, updateArticle } from '../api/articles'
import type { ArticleListParams } from '../api/articles'

export const useArticleStore = defineStore('article', () => {
  const articles = ref<any[]>([])
  const total = ref(0)
  const currentArticle = ref<any>(null)

  async function fetchArticles(params?: ArticleListParams) {
    try {
      const data = await getArticles(params)
      articles.value = data.articles ?? data
      total.value = data.total ?? 0
    } catch {
      // errors surface to caller via useAsyncState
    }
  }

  async function fetchArticle(id: string) {
    currentArticle.value = await getArticle(id)
  }

  async function createArticleAction(body: Record<string, unknown>) {
    const newArticle = await createArticle(body)
    articles.value.push(newArticle)
    return newArticle
  }

  async function updateArticleAction(id: string, body: Record<string, unknown>) {
    const updated = await updateArticle(id, body)
    // Update in list if present
    const idx = articles.value.findIndex((a: any) => a.id === id)
    if (idx !== -1) articles.value[idx] = updated
    // Update current article if it's the same
    if (currentArticle.value?.id === id) currentArticle.value = updated
    return updated
  }

  return {
    articles,
    total,
    currentArticle,
    fetchArticles,
    fetchArticle,
    createArticle: createArticleAction,
    updateArticle: updateArticleAction,
  }
})
