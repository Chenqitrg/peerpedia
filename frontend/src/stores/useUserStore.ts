import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as apiLogin, register as apiRegister, getMe } from '../api/auth'
import { useTauri } from '../composables/useTauri'
import { useFollowCache } from '../composables/useFollowCache'
import { loadString, loadJSON, saveString, saveJSON, remove } from '../composables/useLocalStorage'
import type { UserProfile } from '../api/types'
import type { Account, AccountSummary } from '../composables/useTauri'

export const useUserStore = defineStore('user', () => {
  const storedToken = loadString('token')
  const storedViewer = loadJSON<UserProfile>('viewer')

  const viewer = ref<UserProfile | null>(storedViewer)
  const token = ref<string | null>(storedToken)
  const showAuthModal = ref(false)
  const intendedRoute = ref<string | null>(null)
  const syncError = ref<string | null>(null)

  // ── Local account layer (Tauri or dev mock) ──────────────────────────

  const localAccount = ref<Account | null>(null)
  const localAccounts = ref<AccountSummary[]>([])
  const localToken = ref<string | null>(null)  // Session token from Tauri login
  const isTauriMode = ref(false)
  const isBrowserLocal = ref(false)

  const tauri = useTauri()

  // Credentials held for server sync retry. Stored when local login/register
  // succeeds but the server is unreachable, cleared on successful sync.
  // Persisted to localStorage to survive HMR and page refreshes.
  const PENDING_CREDS_KEY = 'peerpedia_pending_server_creds'
  let _pendingServerCreds: {
    username: string
    password: string
    email: string
    name: string
  } | null = loadJSON(PENDING_CREDS_KEY) || null

  function _savePendingCreds(creds: typeof _pendingServerCreds) {
    _pendingServerCreds = creds
    if (creds) saveJSON(PENDING_CREDS_KEY, creds)
    else remove(PENDING_CREDS_KEY)
  }

  // Detect Tauri / dev mock mode on store initialization.
  isTauriMode.value = tauri.isTauri.value
  isBrowserLocal.value = tauri.isBrowserLocal.value

  // Restore session token immediately (sync) from localStorage, before any
  // async operation or component mount. Without this, page components that
  // load data during setup will call Tauri commands with a null token.
  if (isLocalMode()) {
    const savedToken = loadString('peerpedia_local_token')
    if (savedToken) {
      localToken.value = savedToken
      tauri.setSessionToken(savedToken)
    }
  }

  // Local mode: real Tauri desktop app OR browser dev mock.
  function isLocalMode() {
    return isTauriMode.value || isBrowserLocal.value
  }

  async function loadLocalAccounts() {
    if (!isLocalMode()) return
    const result = await tauri.listAccounts()
    if (result && Array.isArray(result)) {
      localAccounts.value = result
    }
  }

  async function loginLocal(username: string, password: string) {
    const result = await tauri.login({ username, password })
    if (!result) throw new Error('Tauri unavailable')
    if ('error' in result) throw new Error(result.error)
    const acctWithToken = result as { id: string; username: string; token: string; email: string; name: string }
    localAccount.value = { id: acctWithToken.id, username: acctWithToken.username }
    localToken.value = acctWithToken.token
    tauri.setSessionToken(acctWithToken.token)
    saveString('peerpedia_local_token', acctWithToken.token)
    // Create a minimal viewer profile and persist to localStorage
    // so the router guard recognizes the user as authenticated.
    const profile = {
      id: (result as Account).id,
      username: (result as Account).username,
      name: acctWithToken.name || acctWithToken.username,
      anonymous_name: '',
      affiliation: '',
      expertise: [],
      reputation: { professionalism: 0, objectivity: 0, collaboration: 0, pedagogy: 0 },
      followers_count: 0,
      following_count: 0,
      article_count: 0,
      created_at: new Date().toISOString(),
    }
    viewer.value = profile
    saveJSON('viewer', profile)

    // Try to get a backend JWT and sync identity with server.
    try {
      console.log('[loginLocal] Trying apiLogin with:', username)
      const { user: serverUser, token: t } = await apiLogin({ username, password })
      console.log('[loginLocal] apiLogin SUCCESS, token:', !!t, 'serverId:', serverUser.id)
      token.value = t
      saveString('token', t)
      // Switch to server identity when online — follow/bookmark/article APIs use server UUIDs.
      viewer.value = serverUser
      saveJSON('viewer', serverUser)
      _savePendingCreds(null)
      syncError.value = null
      // Refresh offline follow cache.
      useFollowCache().refreshCache(serverUser.id).catch(() => {})
    } catch (e: any) {
      console.log('[loginLocal] apiLogin failed, trying apiRegister:', e?.response?.status)
      // User doesn't exist on server yet — try apiRegister immediately.
      try {
        const { user: serverUser, token: t } = await apiRegister({
          username,
          password,
          email: acctWithToken.email || `${username}@peerpedia.local`,
          name: acctWithToken.name || username,
        })
        token.value = t
        saveString('token', t)
        viewer.value = serverUser
        saveJSON('viewer', serverUser)
        _savePendingCreds(null)
        syncError.value = null
        useFollowCache().refreshCache(serverUser.id).catch(() => {})
      } catch (regErr: any) {
        const detail = regErr?.response?.data?.detail
        console.error('[loginLocal] apiRegister error:', regErr?.response?.status, JSON.stringify(detail))
        // Save credentials for retry regardless of error type.
        // 422 (validation error): user can fix the issue and trySyncServerAuth will retry.
        // Network error: server will be reachable later.
        _savePendingCreds({
          username,
          password,
          email: acctWithToken.email || `${username}@peerpedia.local`,
          name: acctWithToken.name || username,
        })
        if (regErr?.response?.status === 422) {
          syncError.value = Array.isArray(detail)
            ? detail.map((d: any) => `${d.loc?.join('.')}: ${d.msg}`).join('; ')
            : detail || '注册数据不合规'
          throw new Error(syncError.value)
        }
      }
    }
  }

  async function registerLocal(username: string, password: string, email: string, name: string) {
    // Clear any stale draft data from previous sessions to prevent cross-user leaks.
    remove('peerpedia_draft')
    remove('editor-draft-anonymous-new')
    remove('editor-draft-id-anonymous-new')
    const result = await tauri.createAccount({ username, password, email, name })
    if (!result) throw new Error('Tauri unavailable')
    if ('error' in result) throw new Error(result.error)
    localAccount.value = result as Account
    const profile = {
      id: (result as Account).id,
      username: (result as Account).username,
      name: (result as Account).username,
      anonymous_name: '',
      affiliation: '',
      expertise: [],
      reputation: { professionalism: 0, objectivity: 0, collaboration: 0, pedagogy: 0 },
      followers_count: 0,
      following_count: 0,
      article_count: 0,
      created_at: new Date().toISOString(),
    }
    viewer.value = profile
    saveJSON('viewer', profile)

    // Login to get a session token for subsequent Tauri commands.
    try {
      const loginResult = await tauri.login({ username, password })
      if (loginResult && !('error' in loginResult)) {
        const acct = loginResult as { id: string; username: string; token: string }
        localToken.value = acct.token
        tauri.setSessionToken(acct.token)
        saveString('peerpedia_local_token', acct.token)
      }
    } catch {
      // OK to continue without local token
    }

    // Try to register on backend — sync identity with server.
    try {
      const { user: serverUser, token: t } = await apiRegister({
        username,
        password,
        email: email || `${username}@peerpedia.local`,
        name: name || username,
      })
      token.value = t
      saveString('token', t)
      viewer.value = serverUser
      saveJSON('viewer', serverUser)
      _savePendingCreds(null)
      syncError.value = null
    } catch (e: any) {
      // Save credentials for retry regardless of error type.
      _savePendingCreds({ username, password, email, name })
      // Show validation errors to user, re-throw for AuthModal.
      const detail = e?.response?.data?.detail
      if (Array.isArray(detail) && detail.length > 0) {
        syncError.value = detail.map((d: any) => `${d.loc?.join('.')}: ${d.msg}`).join('; ')
        throw new Error(syncError.value)
      }
    }
  }

  // ── Actions (original web auth — unchanged) ─────────────────────────

  function _persist(user: UserProfile, t: string) {
    viewer.value = user
    token.value = t
    saveJSON('viewer', user)
    saveString('token', t)
  }

  function clear() {
    // Capture user ID before nulling for draft key cleanup.
    const uid = viewer.value?.id
    viewer.value = null
    token.value = null
    localAccount.value = null
    localToken.value = null
    tauri.setSessionToken(null)
    _savePendingCreds(null)
    syncError.value = null
    remove('viewer')
    remove('token')
    remove('peerpedia_local_token')
    // Clear stale draft data to prevent cross-user leaks.
    remove('peerpedia_draft')
    if (uid) {
      remove(`editor-draft-${uid}-new`)
      remove(`editor-draft-id-${uid}-new`)
      remove(`peerpedia_draft_${uid}`)
    }
  }

  /**
   * Try to obtain a server JWT using stored local credentials.
   * Strategy: apiLogin first (user may already exist on server, e.g. seed data
   * or multi-device), then apiRegister as fallback (create server account).
   * On success: clears credentials, syncs profile. On failure: keeps credentials for retry.
   * Returns true if a valid server token was obtained.
   */
  async function trySyncServerAuth(): Promise<boolean> {
    console.log('[sync] trySyncServerAuth called, pendingCreds:', !!_pendingServerCreds)
    if (!_pendingServerCreds) return false
    const creds = _pendingServerCreds
    console.log('[sync] creds:', creds.username)

    // Step 1: Try apiLogin (user may already exist on server)
    try {
      const { user: serverUser, token: t } = await apiLogin({
        username: creds.username,
        password: creds.password,
      })
      console.log('[sync] apiLogin SUCCESS')
      token.value = t
      saveString('token', t)
      viewer.value = serverUser
      saveJSON('viewer', serverUser)
      _savePendingCreds(null)
      syncError.value = null
      useFollowCache().refreshCache(serverUser.id).catch(() => {})
      return true
    } catch (e: any) {
      console.log('[sync] apiLogin failed:', e?.response?.status, e?.response?.data?.detail || e?.message || e)
    }

    // Step 2: Try apiRegister (create server account for local user)
    try {
      console.log('[sync] Trying apiRegister:', creds.username)
      const { user: serverUser, token: t } = await apiRegister({
        username: creds.username,
        password: creds.password,
        email: creds.email || `${creds.username}@peerpedia.local`,
        name: creds.name || creds.username,
      })
      console.log('[sync] apiRegister SUCCESS')
      token.value = t
      saveString('token', t)
      viewer.value = serverUser
      saveJSON('viewer', serverUser)
      _savePendingCreds(null)
      syncError.value = null
      useFollowCache().refreshCache(serverUser.id).catch(() => {})
      return true
    } catch (regErr: any) {
      const detail = regErr?.response?.data?.detail
      console.error('[sync] apiRegister failed:', regErr?.response?.status, JSON.stringify(detail))
      // Show validation / conflict errors to the user.
      if (Array.isArray(detail) && detail.length > 0) {
        syncError.value = detail.map((d: any) => `${d.loc?.join('.')}: ${d.msg}`).join('; ')
      } else if (typeof detail === 'string') {
        const isConflict = detail.includes('already exists') || detail.includes('taken') || detail.includes('unique')
        syncError.value = isConflict
          ? `服务器上已有用户 ${creds.username}。请输入该账号的服务器密码进行关联。`
          : detail
      } else {
        syncError.value = `无法同步到服务器（HTTP ${regErr?.response?.status}）`
      }
      return false
    }
  }

  /**
   * Sync local profile data to server (L3). Best-effort — silent on failure.
   */
  async function syncProfileToServer() {
    if (!token.value || !viewer.value) return
    try {
      const { updateProfile } = await import('../api/users')
      await updateProfile(viewer.value.id, {
        affiliation: viewer.value.affiliation,
        expertise: viewer.value.expertise,
      })
    } catch {
      // Silent — profile sync is best-effort
    }
  }

  async function login(username: string, password: string) {
    if (isLocalMode()) {
      return loginLocal(username, password)
    }
    const { user, token: t } = await apiLogin({ username, password })
    _persist(user, t)
  }

  async function register(username: string, password: string, email: string, name: string) {
    if (isLocalMode()) {
      return registerLocal(username, password, email, name)
    }
    const { user, token: t } = await apiRegister({ username, password, email, name })
    _persist(user, t)
  }

  function logout() {
    clear()
    showAuthModal.value = false
  }

  async function restoreSession() {
    if (isLocalMode()) {
      await loadLocalAccounts()
      // Restore session token from localStorage (survives page refresh).
      const savedToken = loadString('peerpedia_local_token')
      if (savedToken) {
        localToken.value = savedToken
        tauri.setSessionToken(savedToken)
      }
      return
    }
    const t = token.value
    if (!t) return
    try {
      const { user } = await getMe(t)
      viewer.value = user
      saveJSON('viewer', user)
    } catch {
      clear()
    }
  }

  // ── Return ───────────────────────────────────────────────────────────

  return {
    viewer,
    token,
    showAuthModal,
    intendedRoute,
    syncError,
    localAccount,
    localAccounts,
    localToken,
    isTauriMode,
    isBrowserLocal,
    login,
    register,
    loginLocal,
    registerLocal,
    loadLocalAccounts,
    logout,
    restoreSession,
    clear,
    hasPendingCreds: computed(() => !!_pendingServerCreds),
    trySyncServerAuth,
    syncProfileToServer,
  }
})
