import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useNetworkStatus } from '../useNetworkStatus'

describe('useNetworkStatus', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    // Singleton refs persist across tests — reset them.
    useNetworkStatus()._resetForTest()
    // Default: fetch succeeds
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ ok: true }),
    })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('isOnline defaults to false', () => {
    const { isOnline } = useNetworkStatus()
    expect(isOnline.value).toBe(false)
  })

  it('startPing fires immediate ping and stays offline on failures', async () => {
    // startPing fires an immediate ping, so we need 2 rejection slots:
    // 1 for the immediate ping, 2 for the interval pings.
    globalThis.fetch = vi.fn()
      .mockRejectedValueOnce(new Error('Network error'))   // immediate (0ms)
      .mockRejectedValueOnce(new Error('Network error'))   // interval (100ms)

    const { isOnline, startPing } = useNetworkStatus()
    expect(isOnline.value).toBe(false) // defaults to offline
    startPing(100)

    // After 100ms: immediate ping (0ms) failed + interval ping (100ms) failed
    // That's 2 ≥ FAILURE_THRESHOLD → stays offline.
    await vi.advanceTimersByTimeAsync(100)
    expect(isOnline.value).toBe(false)
  })

  it('recovers to online after a successful ping', async () => {
    // startPing fires an immediate ping, so the sequence is:
    // immediate (0ms) → interval (100ms) → interval (200ms) → interval (300ms)
    globalThis.fetch = vi.fn()
      .mockRejectedValueOnce(new Error('fail'))   // immediate ping (0ms)
      .mockRejectedValueOnce(new Error('fail'))   // interval (100ms)
      .mockRejectedValueOnce(new Error('fail'))   // interval (200ms)
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ ok: true }) }) // interval (300ms)

    const { isOnline, startPing } = useNetworkStatus()
    startPing(100)

    // immediate + 100ms + 200ms → 3 failures, still offline
    await vi.advanceTimersByTimeAsync(100)
    await vi.advanceTimersByTimeAsync(100)
    expect(isOnline.value).toBe(false)

    // 300ms → one success → back online
    await vi.advanceTimersByTimeAsync(100)
    expect(isOnline.value).toBe(true)
  })

  it('isOnline stays true on single intermittent failure', async () => {
    globalThis.fetch = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ ok: true }) })
      .mockRejectedValueOnce(new Error('fail'))
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ ok: true }) })

    const { isOnline, startPing } = useNetworkStatus()
    startPing(100)

    await vi.advanceTimersByTimeAsync(100)
    expect(isOnline.value).toBe(true) // success

    await vi.advanceTimersByTimeAsync(100)
    expect(isOnline.value).toBe(true) // 1 failure — not enough to flip

    await vi.advanceTimersByTimeAsync(100)
    expect(isOnline.value).toBe(true) // success
  })

  it('stopPing stops the interval', async () => {
    // startPing fires an immediate ping + interval pings.
    globalThis.fetch = vi.fn()
      .mockRejectedValue(new Error('fail'))

    const { isOnline, startPing, stopPing } = useNetworkStatus()
    expect(isOnline.value).toBe(false)
    startPing(100)

    // Immediate ping already fired, 100ms interval fires → 2 failures so far.
    await vi.advanceTimersByTimeAsync(100)
    expect(isOnline.value).toBe(false) // still offline

    stopPing()

    // Advance more — should not change because interval stopped.
    await vi.advanceTimersByTimeAsync(500)
    expect(isOnline.value).toBe(false) // still unchanged
  })

  it('isOnline is a singleton — shared across multiple useNetworkStatus() calls', async () => {
    // Bug: if each useNetworkStatus() call creates its own ref, App.vue's
    // startPing() updates one instance while useOffline + NetworkStatusBadge
    // read their own copies that stay false forever.
    globalThis.fetch = vi.fn()
      .mockRejectedValueOnce(new Error('fail'))
      .mockRejectedValueOnce(new Error('fail'))
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ ok: true }) })

    const a = useNetworkStatus() // caller A — e.g., useOffline
    const b = useNetworkStatus() // caller B — e.g., NetworkStatusBadge
    const c = useNetworkStatus() // caller C — e.g., App.vue (starts ping)

    expect(a.isOnline.value).toBe(false)
    expect(b.isOnline.value).toBe(false)
    expect(c.isOnline.value).toBe(false)

    c.startPing(100)

    // After 200ms: immediate (fail, 0ms) + 100ms interval (fail) + 200ms interval (success)
    await vi.advanceTimersByTimeAsync(100)
    await vi.advanceTimersByTimeAsync(100)
    expect(c.isOnline.value).toBe(true)

    // All callers share the same ref
    expect(a.isOnline.value).toBe(true)
    expect(b.isOnline.value).toBe(true)
  })

  it('ping sends request to http://localhost:8080/health (absolute URL)', async () => {
    // Bug: relative /health resolves to tauri://localhost/health in Tauri webview.
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ ok: true }),
    })

    const { startPing, stopPing } = useNetworkStatus()
    startPing(100)

    // Immediate ping fires at 0ms.
    await vi.advanceTimersByTimeAsync(0)
    stopPing()

    expect(globalThis.fetch).toHaveBeenCalledWith('http://localhost:8080/health')
  })
})
