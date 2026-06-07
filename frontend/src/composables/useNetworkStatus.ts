import { ref, type Ref } from 'vue'

const FAILURE_THRESHOLD = 2

export function useNetworkStatus() {
  // Start as offline — only flip to online after a successful ping.
  // This prevents the ~60s window where offline features like pool/schools
  // would incorrectly render as accessible when the device is actually offline.
  const isOnline: Ref<boolean> = ref(false)
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
    // Fire an immediate first ping so we don't wait intervalMs before
    // discovering whether the server is reachable.
    ping()
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
