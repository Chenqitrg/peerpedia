import { computed } from 'vue'
import { useAsyncState } from '@vueuse/core'
import type { UseAsyncStateOptions } from '@vueuse/core'

/**
 * Wraps VueUse's useAsyncState with a unified error extraction pattern.
 * Eliminates the boilerplate error computed duplicated across 8 pages.
 *
 * In Tauri mode, network errors are suppressed — there is no server.
 * Pages show their empty state instead of "Cannot reach server".
 */
export function useAsyncResource<T>(
  fetcher: () => Promise<T>,
  initialValue: T | null = null,
  options: UseAsyncStateOptions<false, T | null> = {},
) {
  const { state, isLoading, error: rawError, execute } = useAsyncState(
    fetcher,
    initialValue,
    { shallow: false, ...options },
  )

  const error = computed(() => {
    // In Tauri mode, suppress network errors — no server expected.
    const isTauri = typeof window !== 'undefined' && '__TAURI__' in window
    if (isTauri) return ''

    const e = rawError.value as any
    return e?.userMessage || e?.response?.data?.detail || e?.message || ''
  })

  return { data: state, loading: isLoading, error, execute }
}
