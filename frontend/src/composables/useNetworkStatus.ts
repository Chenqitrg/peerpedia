import { ref, type Ref } from 'vue'

const FAILURE_THRESHOLD = 2

// Module-level singleton — all callers share the same isOnline state.
// If each useNetworkStatus() call created its own ref, App.vue's
// startPing() would update one instance while useOffline reads another
// that stays false forever.
const isOnline: Ref<boolean> = ref(false)
let intervalId: ReturnType<typeof setInterval> | null = null
let consecutiveFailures = 0

export function useNetworkStatus() {

  async function ping(): Promise<void> {
    try {
      // Must use absolute URL — relative /health resolves to tauri://localhost
      // in Tauri webview, not the Python backend on localhost:8080.
      const resp = await fetch('http://localhost:8080/health')
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

  // Exposed for tests — reset singleton state between test cases.
  function _resetForTest() {
    isOnline.value = false
    stopPing()
    consecutiveFailures = 0
  }

  function startPing(intervalMs = 30000): void {
    // No fetch in test environment (jsdom) — skip silently.
    if (typeof fetch === 'undefined') return
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

  return { isOnline, startPing, stopPing, _resetForTest }
}
