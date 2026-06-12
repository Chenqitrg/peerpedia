import { ref, computed, type Ref, type ComputedRef } from 'vue'

type ConnectionState = 'idle' | 'connecting' | 'synced'
const CONNECT_TIMEOUT_MS = 10_000

// Module-level singleton — all callers share the same connection state.
const connectionState: Ref<ConnectionState> = ref('idle')
const flash: Ref<boolean> = ref(false)
let connectTimer: ReturnType<typeof setTimeout> | null = null
let flashTimer: ReturnType<typeof setTimeout> | null = null

async function ping(): Promise<void> {
  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    connectionState.value = 'idle'
    return
  }
  try {
    const resp = await fetch('http://localhost:8080/health')
    if (resp.ok) { notifySuccess() } else { notifyFailure() }
  } catch { notifyFailure() }
}

function connect() {
  if (connectionState.value === 'connecting') return
  connectionState.value = 'connecting'
  ping()
  // Only arm the timeout if ping() didn't immediately resolve (e.g. navigator.onLine = false
  // causes ping() to synchronously set state back to 'idle').
  if (connectionState.value === 'connecting') {
    connectTimer = setTimeout(() => { notifyFailure() }, CONNECT_TIMEOUT_MS)
  }
}

function disconnect() {
  connectionState.value = 'idle'
  if (connectTimer !== null) { clearTimeout(connectTimer); connectTimer = null }
}

function notifySuccess() {
  // Only promote to synced if user initiated connection (via connect() → ping()).
  // Prevents: (a) stale ping() promises after disconnect, (b) axios interceptor
  // auto-connecting the user without a tap.
  if (connectionState.value !== 'connecting') return
  connectionState.value = 'synced'
  if (connectTimer !== null) { clearTimeout(connectTimer); connectTimer = null }
}

function notifyFailure() {
  // Ignore failures when already idle — nothing to disconnect from.
  if (connectionState.value === 'idle') return
  const wasConnecting = connectionState.value === 'connecting'
  connectionState.value = 'idle'
  if (connectTimer !== null) { clearTimeout(connectTimer); connectTimer = null }
  if (wasConnecting) {
    // Connection attempt failed — show red flash.
    flash.value = true
    if (flashTimer !== null) clearTimeout(flashTimer)
    flashTimer = setTimeout(() => { flash.value = false }, 500)
  }
  // else: was synced → auto-disconnect on network error (S6), no flash.
}

const isSynced: ComputedRef<boolean> = computed(() => connectionState.value === 'synced')
// Backward compat: existing consumers that destructure isOnline.
const isOnline: ComputedRef<boolean> = isSynced

// Browser network events — registered once at module level
let _listening = false
function _setupListeners() {
  if (_listening || typeof window === 'undefined') return
  _listening = true
  window.addEventListener('offline', () => disconnect())
  // 'online' event intentionally does nothing — user controls connection
}

// Exposed for tests.
function _resetForTest() {
  connectionState.value = 'idle'
  flash.value = false
  _listening = false
  if (connectTimer !== null) { clearTimeout(connectTimer); connectTimer = null }
  if (flashTimer !== null) { clearTimeout(flashTimer); flashTimer = null }
}

export function useNetworkStatus() {
  _setupListeners()
  return { connectionState, flash, isSynced, isOnline, connect, disconnect, ping, notifySuccess, notifyFailure, _resetForTest }
}
