import { useNetworkStatus } from './useNetworkStatus'

type Capability = 'full' | 'readonly' | 'blocked'

interface FeatureCapability {
  read: Capability
  write: Capability
  fallback: string
}

// Features that require a server and are never available in local-only mode
// (Tauri desktop with no server, or browser-local mock mode).
const NETWORK_ONLY_FEATURES = new Set([
  'feed.online',
  'pool',
  'schools',
  'search.network',
  'article.fork',
  'article.publish',
  'editor.publish_pool',
])

const offlineMatrix: Record<string, FeatureCapability> = {
  'feed':               { read: 'full',     write: 'full',     fallback: '' },
  'feed.online':         { read: 'blocked',  write: 'blocked',  fallback: 'offline.feed_hint' },
  'article.content':    { read: 'full',     write: 'full',     fallback: '' },
  'article.comments':   { read: 'readonly', write: 'blocked',  fallback: 'offline.comment_hint' },
  'article.fork':       { read: 'blocked',  write: 'blocked',  fallback: 'offline.fork_hint' },
  'article.publish':    { read: 'blocked',  write: 'blocked',  fallback: 'offline.publish_hint' },
  'pool':               { read: 'blocked',  write: 'blocked',  fallback: 'offline.pool_hint' },
  'schools':            { read: 'blocked',  write: 'blocked',  fallback: 'offline.schools_hint' },
  'search.local':       { read: 'full',     write: 'full',     fallback: '' },
  'search.network':     { read: 'blocked',  write: 'blocked',  fallback: 'offline.search_hint' },
  'user.self':          { read: 'full',     write: 'full',     fallback: '' },
  'user.follow_graph':  { read: 'readonly', write: 'blocked',  fallback: 'offline.user_hint' },
  'editor':             { read: 'full',     write: 'full',     fallback: '' },
  'editor.publish_pool':{ read: 'blocked',  write: 'blocked',  fallback: 'offline.publish_hint' },
  'compile':            { read: 'full',     write: 'full',     fallback: '' },
  'bookmarks':          { read: 'full',     write: 'full',     fallback: '' },
}

export function useOffline() {
  const { isOnline } = useNetworkStatus()

  // In local-only mode (Tauri desktop / browser-local mock), network features
  // are never available — there is no server to reach. This check is independent
  // of ping-based isOnline which can lag for ~60s.
  function isLocalOnly(): boolean {
    if (typeof window === 'undefined') return false
    return '__TAURI__' in window || new URLSearchParams(window.location.search).has('tauri')
  }

  function canRead(feature: string): boolean {
    if (isLocalOnly() && NETWORK_ONLY_FEATURES.has(feature)) return false
    if (isOnline.value) return true
    const cap = offlineMatrix[feature]
    return cap ? cap.read !== 'blocked' : false
  }

  function canWrite(feature: string): boolean {
    if (isLocalOnly() && NETWORK_ONLY_FEATURES.has(feature)) return false
    if (isOnline.value) return true
    const cap = offlineMatrix[feature]
    return cap ? cap.write === 'full' : false
  }

  function getFallback(feature: string): string {
    if (isLocalOnly() && NETWORK_ONLY_FEATURES.has(feature)) return 'offline.local_mode_hint'
    const cap = offlineMatrix[feature]
    return cap ? cap.fallback : ''
  }

  return { canRead, canWrite, getFallback, isLocalOnly }
}
