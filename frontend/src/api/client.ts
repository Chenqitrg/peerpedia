import axios from 'axios'
import { loadString } from '../composables/useLocalStorage'
import { useNetworkStatus } from '../composables/useNetworkStatus'

// Lazy singleton — resolved on first request so useNetworkStatus is ready.
let _ns: ReturnType<typeof useNetworkStatus> | null = null
function _getNS() {
  if (!_ns) _ns = useNetworkStatus()
  return _ns
}

export const apiClient = axios.create({
  baseURL: 'http://localhost:8080/api/v1',
})

// ── Request interceptor: attach Bearer token ───────────────────────────
// ── Request interceptor: skip when offline ─────────────────────────────

apiClient.interceptors.request.use(config => {
  // Cooldown guard: after a network failure, block new requests for a
  // cooldown period to avoid spamming the console. The first request
  // after cooldown expires acts as a probe — if it succeeds, isOnline
  // flips to true; if it fails, cooldown resets.
  if (!_getNS().shouldTry()) {
    return Promise.reject(
      new axios.Cancel('Server unreachable — cooling down')
    )
  }
  const token = loadString('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ── Response error interceptor: extract user-friendly message ───────────

apiClient.interceptors.response.use(
  response => {
    _getNS().notifySuccess()
    return response
  },
  error => {
    // Offline guard — suppressed request, not a real error.
    if (axios.isCancel(error)) {
      return Promise.reject(error)
    }
    if (!error.response) {
      if (error.code === 'ERR_NETWORK' || error.message?.includes('Network Error')) {
        _getNS().notifyFailure()
        error.userMessage = 'Cannot reach server. Is the backend running on port 8080?'
      } else {
        error.userMessage = error.message || 'Network error'
      }
    } else {
      const status = error.response.status
      const detail = error.response.data?.detail
      if (status === 422 && Array.isArray(detail)) {
        error.userMessage = detail.map((d: any) => {
          const field = d.loc?.slice(1).join('.') || 'unknown'
          return `${field}: ${d.msg}`
        }).join('; ')
      } else if (typeof detail === 'string') {
        error.userMessage = detail
      } else {
        error.userMessage = `Request failed (HTTP ${status})`
      }
    }
    return Promise.reject(error)
  },
)

export default apiClient
