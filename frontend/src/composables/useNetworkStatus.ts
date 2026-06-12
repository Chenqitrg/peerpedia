import { ref, type Ref } from 'vue'

// Module-level singleton — all callers share the same isOnline state.
const isOnline: Ref<boolean> = ref(false)

// Cooldown: after a network failure, block new requests for COOLDOWN_MS.
// The first request after cooldown acts as a probe — succeeds → online,
// fails → reset cooldown. Limits console noise to max 1 per cooldown.
const COOLDOWN_MS = 30_000
let lastFailedAt = 0

// Whether we've registered the navigator.onLine event listeners.
let _listening = false

function _setupListeners(ping: () => Promise<void>) {
  if (_listening || typeof window === 'undefined') return
  _listening = true

  // When the browser's network interface comes back, ping to see if the
  // Python server is reachable too.
  window.addEventListener('online', () => {
    ping()
  })

  // When the browser goes offline, the server is definitely unreachable.
  window.addEventListener('offline', () => {
    isOnline.value = false
  })
}

export function useNetworkStatus() {

  async function ping(): Promise<void> {
    if (typeof navigator !== 'undefined' && !navigator.onLine) {
      isOnline.value = false
      return
    }
    try {
      const resp = await fetch('http://localhost:8080/health')
      isOnline.value = resp.ok
    } catch {
      isOnline.value = false
    }
  }

  _setupListeners(ping)

  // Exposed for tests.
  function _resetForTest() {
    isOnline.value = false
    _listening = false
    lastFailedAt = 0
  }

  /**
   * Should axios attempt a real network request?
   * - Always yes when isOnline (server is known reachable).
   * - When offline: only after cooldown expires (probe to detect recovery).
   */
  function shouldTry(): boolean {
    if (isOnline.value) return true
    return Date.now() - lastFailedAt >= COOLDOWN_MS
  }

  /** Call on any successful server response. */
  function notifySuccess() { isOnline.value = true }

  /** Call on ERR_NETWORK / connection-refused — start cooldown. */
  function notifyFailure() {
    isOnline.value = false
    lastFailedAt = Date.now()
  }

  return { isOnline, ping, shouldTry, notifySuccess, notifyFailure, _resetForTest }
}
