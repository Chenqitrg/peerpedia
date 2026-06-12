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

  it('startPing fires immediate ping and goes offline on first failure', async () => {
    // With FAILURE_THRESHOLD=1, a single failure flips to offline.
    globalThis.fetch = vi.fn()
      .mockRejectedValueOnce(new Error('Network error'))   // immediate (0ms)

    const { isOnline, startPing } = useNetworkStatus()
    expect(isOnline.value).toBe(false) // defaults to offline
    startPing(100)

    await vi.advanceTimersByTimeAsync(0)
    expect(isOnline.value).toBe(false) // 1 failure — offline
  })

  it('recovers to online on first successful ping after failure', async () => {
    // With FAILURE_THRESHOLD=1: 1 failure → offline, 1 success → online.
    globalThis.fetch = vi.fn()
      .mockRejectedValueOnce(new Error('fail'))   // immediate ping (0ms) → offline
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ ok: true }) }) // interval (100ms) → online

    const { isOnline, startPing } = useNetworkStatus()
    startPing(100)

    await vi.advanceTimersByTimeAsync(0)
    expect(isOnline.value).toBe(false) // 1 failure → offline

    await vi.advanceTimersByTimeAsync(100)
    expect(isOnline.value).toBe(true) // 1 success → back online
  })

  it('flips offline on first failure and recovers on first success', async () => {
    globalThis.fetch = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ ok: true }) })
      .mockRejectedValueOnce(new Error('fail'))
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ ok: true }) })

    const { isOnline, startPing } = useNetworkStatus()
    startPing(100)

    await vi.advanceTimersByTimeAsync(0)
    expect(isOnline.value).toBe(true) // success — online

    await vi.advanceTimersByTimeAsync(100)
    expect(isOnline.value).toBe(false) // 1 failure — flips offline (threshold=1)

    await vi.advanceTimersByTimeAsync(100)
    expect(isOnline.value).toBe(true) // 1 success — back online
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
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ ok: true }) })

    const a = useNetworkStatus() // caller A — e.g., useOffline
    const b = useNetworkStatus() // caller B — e.g., NetworkStatusBadge
    const c = useNetworkStatus() // caller C — e.g., App.vue (starts ping)

    expect(a.isOnline.value).toBe(false)
    expect(b.isOnline.value).toBe(false)
    expect(c.isOnline.value).toBe(false)

    c.startPing(100)

    // After 100ms: immediate (fail, 0ms) + 100ms interval (success)
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
