import { defineStore } from 'pinia'
import { ref } from 'vue'
import { login as apiLogin, register as apiRegister, getMe } from '../api/auth'
import type { UserProfile } from '../api/types'

export const useUserStore = defineStore('user', () => {
  const storedToken = localStorage.getItem('token')
  const storedViewer = localStorage.getItem('viewer')

  const viewer = ref<UserProfile | null>(storedViewer ? JSON.parse(storedViewer) : null)
  const token = ref<string | null>(storedToken)
  const showAuthModal = ref(false)
  const intendedRoute = ref<string | null>(null)

  // ── Actions ──────────────────────────────────────────────────────────

  function _persist(user: UserProfile, t: string) {
    viewer.value = user
    token.value = t
    localStorage.setItem('viewer', JSON.stringify(user))
    localStorage.setItem('token', t)
  }

  function clear() {
    viewer.value = null
    token.value = null
    localStorage.removeItem('viewer')
    localStorage.removeItem('token')
  }

  async function login(username: string, password: string) {
    const { user, token: t } = await apiLogin({ username, password })
    _persist(user, t)
  }

  async function register(username: string, password: string, email: string, name: string) {
    const { user, token: t } = await apiRegister({ username, password, email, name })
    _persist(user, t)
  }

  function logout() {
    clear()
    showAuthModal.value = false
  }

  async function restoreSession() {
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
    login,
    register,
    logout,
    restoreSession,
    clear,
  }
})
