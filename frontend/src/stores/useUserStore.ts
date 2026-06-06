import { defineStore } from 'pinia'
import { ref } from 'vue'
import { login as apiLogin, register as apiRegister, getMe } from '../api/auth'
import { useTauri } from '../composables/useTauri'
import type { UserProfile } from '../api/types'
import type { Account, AccountSummary } from '../composables/useTauri'

export const useUserStore = defineStore('user', () => {
  const storedToken = localStorage.getItem('token')
  const storedViewer = localStorage.getItem('viewer')

  const viewer = ref<UserProfile | null>(storedViewer ? JSON.parse(storedViewer) : null)
  const token = ref<string | null>(storedToken)
  const showAuthModal = ref(false)
  const intendedRoute = ref<string | null>(null)

  // ── Local account layer (Tauri or dev mock) ──────────────────────────

  const localAccount = ref<Account | null>(null)
  const localAccounts = ref<AccountSummary[]>([])
  const isTauriMode = ref(false)
  const isDevMock = ref(false)

  const tauri = useTauri()

  // Detect Tauri / dev mock mode on store initialization.
  isTauriMode.value = tauri.isTauri.value
  isDevMock.value = tauri.isDevMock.value

  // Local mode: real Tauri desktop app OR browser dev mock.
  function isLocalMode() {
    return isTauriMode.value || isDevMock.value
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
    localAccount.value = result as Account
    // Create a minimal viewer profile and persist to localStorage
    // so the router guard recognizes the user as authenticated.
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
    localStorage.setItem('viewer', JSON.stringify(profile))
  }

  async function registerLocal(username: string, password: string, email: string, name: string) {
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
    localStorage.setItem('viewer', JSON.stringify(profile))
  }

  // ── Actions (original web auth — unchanged) ─────────────────────────

  function _persist(user: UserProfile, t: string) {
    viewer.value = user
    token.value = t
    localStorage.setItem('viewer', JSON.stringify(user))
    localStorage.setItem('token', t)
  }

  function clear() {
    viewer.value = null
    token.value = null
    localAccount.value = null
    localStorage.removeItem('viewer')
    localStorage.removeItem('token')
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
      return
    }
    const t = token.value
    if (!t) return
    try {
      const { user } = await getMe(t)
      viewer.value = user
      localStorage.setItem('viewer', JSON.stringify(user))
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
    localAccount,
    localAccounts,
    isTauriMode,
    isDevMock,
    login,
    register,
    loginLocal,
    registerLocal,
    loadLocalAccounts,
    logout,
    restoreSession,
    clear,
  }
})
