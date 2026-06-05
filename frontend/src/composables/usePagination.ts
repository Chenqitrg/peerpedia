import { ref, computed } from 'vue'

/**
 * Shared pagination state and navigation helpers.
 * Used by HomePage and SearchPage.
 *
 * Usage:
 *   const pagination = usePagination(20)
 *   pagination.updateTotal(articles.length)  // after fetch
 *   pagination.goToPage(2)                    // navigate
 */
export function usePagination(pageSize = 20) {
  const currentPage = ref(1)
  const total = ref(0)

  const totalPages = computed(() =>
    Math.max(1, Math.ceil(total.value / pageSize)),
  )

  function updateTotal(newTotal: number) {
    total.value = newTotal
  }

  function goToPage(page: number) {
    if (page < 1 || page > totalPages.value) return
    currentPage.value = page
  }

  return { currentPage, totalPages, pageSize, updateTotal, goToPage }
}
