import { computed } from 'vue'
import { useAsyncState } from '@vueuse/core'
import type { UseAsyncStateOptions } from '@vueuse/core'

/**
 * Wraps VueUse's useAsyncState with a unified error extraction pattern.
 * Eliminates the boilerplate error computed duplicated across 8 pages.
 *
 * Each page is responsible for checking canRead(canWrite) via useOffline()
 * before triggering a network fetch. This composable no longer blanket-suppresses
 * errors — if a page fires a request without checking offline capability first,
 * the error is surfaced to the user.
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
    const e = rawError.value as Record<string, unknown> | null
    if (!e) return ''
    // Try known error message fields
    const msg = (e.userMessage as string) || (e.message as string) || ''
    if (msg) return msg
    const resp = e.response as Record<string, unknown> | undefined
    if (resp) {
      const data = resp.data as Record<string, unknown> | undefined
      if (data) return (data.detail as string) || ''
    }
    return ''
  })

  return { data: state, loading: isLoading, error, execute }
}
