// Typed localStorage utility — the single abstraction that owns all
// localStorage access. Callers wrap in ref()/Pinia stores where reactive
// state matters; this module only provides safe serialized I/O.
//
// All functions catch and return fallback on any error (quota exceeded,
// disabled in private browsing, corrupt JSON, etc.) — never throws.

function getLS(): Storage | null {
  if (typeof window === 'undefined') return null
  // In test environments (jsdom), globalThis.localStorage may be a mock
  // installed by test-setup. Prefer globalThis for test compatibility.
  try {
    const ls = (globalThis as { localStorage?: Storage }).localStorage
    if (ls) return ls
  } catch { /* globalThis access denied */ }
  try {
    return window.localStorage
  } catch { /* private browsing blocks access */ }
  return null
}

// ── String ───────────────────────────────────────────────────────────────

export function loadString(key: string, fallback?: string): string | null {
  const LS = getLS()
  if (!LS) return fallback ?? null
  try {
    const v = LS.getItem(key)
    return v !== null ? v : (fallback ?? null)
  } catch {
    return fallback ?? null
  }
}

export function saveString(key: string, value: string): void {
  const LS = getLS()
  if (!LS) return
  try { LS.setItem(key, value) } catch { /* quota or private browsing */ }
}

// ── JSON ─────────────────────────────────────────────────────────────────

export function loadJSON<T>(key: string, fallback?: T): T | null {
  const LS = getLS()
  if (!LS) return fallback ?? null
  try {
    const raw = LS.getItem(key)
    if (raw === null) return fallback ?? null
    return JSON.parse(raw) as T
  } catch {
    return fallback ?? null
  }
}

export function saveJSON(key: string, value: unknown): void {
  const LS = getLS()
  if (!LS) return
  try { LS.setItem(key, JSON.stringify(value)) } catch { /* quota */ }
}

// ── Remove ───────────────────────────────────────────────────────────────

export function remove(key: string): void {
  const LS = getLS()
  if (!LS) return
  try { LS.removeItem(key) } catch { /* disabled */ }
}
