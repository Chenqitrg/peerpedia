import { ref, type Ref } from 'vue'

const FAILURE_THRESHOLD = 2

export function useNetworkStatus() {
  const isOnline: Ref<boolean> = ref(true)
  let intervalId: ReturnType<typeof setInterval> | null = null
  let consecutiveFailures = 0

  async function ping(): Promise<void> {
    try {
      const resp = await fetch('/health')
      if (resp.ok) {
        consecutiveFailures = 0
        isOnline.value = true
      } else {
        consecutiveFailures++
        if (consecutiveFailures >= FAILURE_THRESHOLD) {
          isOnline.value = false
        }
      }
    } catch {
      consecutiveFailures++
      if (consecutiveFailures >= FAILURE_THRESHOLD) {
        isOnline.value = false
      }
    }
  }

  function startPing(intervalMs = 30000): void {
    stopPing()
    consecutiveFailures = 0
    intervalId = setInterval(ping, intervalMs)
  }

  function stopPing(): void {
    if (intervalId !== null) {
      clearInterval(intervalId)
      intervalId = null
    }
  }

  return { isOnline, startPing, stopPing }
}
