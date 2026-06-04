import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getPool } from '../api/pool'

export const usePoolStore = defineStore('pool', () => {
  const poolArticles = ref<any[]>([])
  const loading = ref(false)

  async function fetchPool() {
    loading.value = true
    try {
      const data = await getPool()
      poolArticles.value = data.articles ?? []
    } finally {
      loading.value = false
    }
  }

  return {
    poolArticles,
    loading,
    fetchPool,
  }
})
