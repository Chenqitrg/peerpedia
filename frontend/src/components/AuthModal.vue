<script setup lang="ts">
import { ref } from 'vue'
import { useUserStore } from '../stores/useUserStore'
import { X } from 'lucide-vue-next'

const userStore = useUserStore()

const tab = ref<'login' | 'register'>('login')
const username = ref('')
const password = ref('')
const email = ref('')
const displayName = ref('')
const error = ref('')
const loading = ref(false)

function extractError(e: any, fallback: string): string {
  // No response at all — network error / server down
  if (!e.response) {
    if (e.code === 'ERR_NETWORK' || e.message?.includes('Network Error')) {
      return 'Cannot reach server. Is the backend running on port 8080?'
    }
    return e.message || fallback
  }

  const status = e.response.status
  const detail = e.response.data?.detail

  // FastAPI 422 validation error: detail is an array of {loc, msg}
  if (status === 422 && Array.isArray(detail)) {
    const msgs = detail.map((d: any) => {
      const field = d.loc?.slice(1).join('.') || 'unknown'
      return `${field}: ${d.msg}`
    })
    return msgs.join('; ')
  }

  // Standard error with string detail
  if (typeof detail === 'string') return detail

  // Fallback with status code
  return `${fallback} (HTTP ${status})`
}

function switchTab(t: 'login' | 'register') {
  tab.value = t
  error.value = ''
}

async function handleLogin() {
  error.value = ''
  if (!username.value.trim() || !password.value.trim()) {
    error.value = 'Please enter both username and password'
    return
  }
  loading.value = true
  try {
    await userStore.login(username.value, password.value)
    close()
  } catch (e: any) {
    error.value = extractError(e, 'Login failed')
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  error.value = ''
  if (!username.value.trim() || !password.value.trim()) {
    error.value = 'Username and password are required'
    return
  }
  if (password.value.length < 6) {
    error.value = 'Password must be at least 6 characters'
    return
  }
  if (!email.value.trim() || !email.value.includes('@')) {
    error.value = 'Please enter a valid email address'
    return
  }
  if (!displayName.value.trim()) {
    error.value = 'Display name is required'
    return
  }
  loading.value = true
  try {
    await userStore.register(username.value, password.value, email.value, displayName.value)
    close()
  } catch (e: any) {
    error.value = extractError(e, 'Registration failed')
  } finally {
    loading.value = false
  }
}

function close() {
  userStore.showAuthModal = false
  error.value = ''
}

function onOverlayClick(e: MouseEvent) {
  if ((e.target as HTMLElement).classList.contains('modal-overlay')) {
    close()
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="userStore.showAuthModal"
      class="modal-overlay fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm"
      @click="onOverlayClick"
    >
      <div class="w-full max-w-sm bg-card border border-divider rounded-xl shadow-2xl p-6 animate-fade-in">
        <!-- Tab switcher -->
        <div class="flex items-center justify-between mb-5">
          <div class="flex gap-4">
            <button
              class="text-sm font-semibold pb-1 border-b-2 transition-colors"
              :class="tab === 'login'
                ? 'text-ink border-accent'
                : 'text-ink-muted border-transparent hover:text-ink'"
              @click="switchTab('login')"
            >
              Log In
            </button>
            <button
              class="text-sm font-semibold pb-1 border-b-2 transition-colors"
              :class="tab === 'register'
                ? 'text-ink border-accent'
                : 'text-ink-muted border-transparent hover:text-ink'"
              @click="switchTab('register')"
            >
              Create Account
            </button>
          </div>
          <button
            class="flex items-center justify-center w-6 h-6 rounded text-ink-muted hover:text-ink hover:bg-[#21262d] transition-colors"
            @click="close"
          >
            <X class="w-4 h-4" stroke-width="2" />
          </button>
        </div>

        <!-- Login form -->
        <form v-if="tab === 'login'" @submit.prevent="handleLogin" class="space-y-3">
          <input
            v-model="username"
            type="text"
            placeholder="Username"
            required
            class="w-full bg-[#0d1117] border border-divider rounded-lg px-3 py-2 text-sm text-ink placeholder:text-ink-muted/50 focus:outline-none focus:ring-1 focus:ring-accent"
          />
          <input
            v-model="password"
            type="password"
            placeholder="Password"
            required
            class="w-full bg-[#0d1117] border border-divider rounded-lg px-3 py-2 text-sm text-ink placeholder:text-ink-muted/50 focus:outline-none focus:ring-1 focus:ring-accent"
          />
          <p v-if="error" class="text-xs text-[#d73a49]">{{ error }}</p>
          <button
            type="submit"
            :disabled="loading"
            class="w-full py-2 text-sm font-semibold bg-accent text-[#0d1117] rounded-lg hover:brightness-110 transition-all duration-200 disabled:opacity-50"
          >
            {{ loading ? '...' : 'Log In' }}
          </button>
        </form>

        <!-- Register form -->
        <form v-if="tab === 'register'" @submit.prevent="handleRegister" class="space-y-3">
          <input
            v-model="username"
            type="text"
            placeholder="Username"
            required
            class="w-full bg-[#0d1117] border border-divider rounded-lg px-3 py-2 text-sm text-ink placeholder:text-ink-muted/50 focus:outline-none focus:ring-1 focus:ring-accent"
          />
          <input
            v-model="email"
            type="email"
            placeholder="Email"
            required
            class="w-full bg-[#0d1117] border border-divider rounded-lg px-3 py-2 text-sm text-ink placeholder:text-ink-muted/50 focus:outline-none focus:ring-1 focus:ring-accent"
          />
          <input
            v-model="displayName"
            type="text"
            placeholder="Display Name"
            required
            class="w-full bg-[#0d1117] border border-divider rounded-lg px-3 py-2 text-sm text-ink placeholder:text-ink-muted/50 focus:outline-none focus:ring-1 focus:ring-accent"
          />
          <input
            v-model="password"
            type="password"
            placeholder="Password (min 6 characters)"
            required
            class="w-full bg-[#0d1117] border border-divider rounded-lg px-3 py-2 text-sm text-ink placeholder:text-ink-muted/50 focus:outline-none focus:ring-1 focus:ring-accent"
          />
          <p v-if="error" class="text-xs text-[#d73a49]">{{ error }}</p>
          <button
            type="submit"
            :disabled="loading"
            class="w-full py-2 text-sm font-semibold bg-accent text-[#0d1117] rounded-lg hover:brightness-110 transition-all duration-200 disabled:opacity-50"
          >
            {{ loading ? '...' : 'Create Account' }}
          </button>
        </form>
      </div>
    </div>
  </Teleport>
</template>
