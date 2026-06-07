import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useNetworkStatus } from '../useNetworkStatus'

describe('useNetworkStatus', () => {
  beforeEach(() => {
    vi.useFakeTimers()
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

  it('isOnline defaults to true', () => {
    const { isOnline } = useNetworkStatus()
    expect(isOnline.value).toBe(true)
  })

  it('startPing sets isOnline to false after 2 consecutive failures', async () => {
    globalThis.fetch = vi.fn()
      .mockRejectedValueOnce(new Error('Network error'))
      .mockRejectedValueOnce(new Error('Network error'))

    const { isOnline, startPing } = useNetworkStatus()
    startPing(100) // fast interval for tests

    // 1st ping fails
    await vi.advanceTimersByTimeAsync(100)
    expect(isOnline.value).toBe(true) // still true after 1 failure

    // 2nd ping fails → flips to offline
    await vi.advanceTimersByTimeAsync(100)
    expect(isOnline.value).toBe(false)
  })

  it('recovers to online after a successful ping', async () => {
    globalThis.fetch = vi.fn()
      .mockRejectedValueOnce(new Error('fail'))
      .mockRejectedValueOnce(new Error('fail'))
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ ok: true }) })

    const { isOnline, startPing } = useNetworkStatus()
    startPing(100)

    // Two failures → offline
    await vi.advanceTimersByTimeAsync(100)
    await vi.advanceTimersByTimeAsync(100)
    expect(isOnline.value).toBe(false)

    // One success → back online
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
    globalThis.fetch = vi.fn()
      .mockRejectedValue(new Error('fail'))

    const { isOnline, startPing, stopPing } = useNetworkStatus()
    startPing(100)

    await vi.advanceTimersByTimeAsync(100)
    expect(isOnline.value).toBe(true) // 1 failure

    stopPing()

    // Advance more — should not change because interval stopped
    await vi.advanceTimersByTimeAsync(500)
    expect(isOnline.value).toBe(true) // still unchanged
  })
})
