import { ref, type Ref } from 'vue'

// Module-level singleton — all callers share the same isOnline state.
const isOnline: Ref<boolean> = ref(false)

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
  }

  /**
   * Let axios (or any server-action caller) update isOnline based on real
   * request outcomes. Call on success / non-network-error to mark online;
   * call on ERR_NETWORK / connection-refused to mark offline.
   */
  function notifySuccess() { isOnline.value = true }
  function notifyFailure() { isOnline.value = false }

  return { isOnline, ping, notifySuccess, notifyFailure, _resetForTest }
}
