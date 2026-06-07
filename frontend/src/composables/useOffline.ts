import { useNetworkStatus } from './useNetworkStatus'

type Capability = 'full' | 'readonly' | 'blocked'

interface FeatureCapability {
  read: Capability
  write: Capability
  fallback: string
}

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

  function canRead(feature: string): boolean {
    if (isOnline.value) return true
    const cap = offlineMatrix[feature]
    return cap ? cap.read !== 'blocked' : false
  }

  function canWrite(feature: string): boolean {
    if (isOnline.value) return true
    const cap = offlineMatrix[feature]
    return cap ? cap.write === 'full' : false
  }

  function getFallback(feature: string): string {
    const cap = offlineMatrix[feature]
    return cap ? cap.fallback : ''
  }

  return { canRead, canWrite, getFallback }
}
