// SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
// SPDX-License-Identifier: CC-BY-NC-SA-4.0

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getArticles, getArticle, createArticle, updateArticle } from '../api/articles'
import type { ArticleListParams } from '../api/articles'
import type { ArticleDetail, ArticleSummary, ArticleCreatePayload, ArticleUpdatePayload } from '../api/types'

export const useArticleStore = defineStore('article', () => {
  const articles = ref<ArticleSummary[]>([])
  const total = ref(0)
  const currentArticle = ref<ArticleDetail | null>(null)

  async function fetchArticles(params?: ArticleListParams) {
    try {
      const data = await getArticles(params)
      articles.value = data.articles ?? data
      total.value = data.total ?? 0
    } catch(e) {
      console.warn('fetchArticles failed:', e)
      throw e
    }
  }

  async function fetchArticle(id: string) {
    currentArticle.value = await getArticle(id)
  }

  async function createArticleAction(body: ArticleCreatePayload) {
    const newArticle = await createArticle(body)
    articles.value.push(newArticle as unknown as ArticleSummary)
    return newArticle
  }

  async function updateArticleAction(id: string, body: ArticleUpdatePayload) {
    const updated = await updateArticle(id, body)
    // Update in list if present
    const idx = articles.value.findIndex(a => a.id === id)
    if (idx !== -1) articles.value[idx] = updated as unknown as ArticleSummary
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
