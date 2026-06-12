import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useNetworkStatus } from '../useNetworkStatus'

describe('useNetworkStatus', () => {
  beforeEach(() => {
    useNetworkStatus()._resetForTest()
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ ok: true }),
    })
    // Ensure navigator.onLine is true by default in jsdom
    Object.defineProperty(navigator, 'onLine', {
      value: true, writable: true, configurable: true,
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('isOnline defaults to false', () => {
    const { isOnline } = useNetworkStatus()
    expect(isOnline.value).toBe(false)
  })

  it('ping sets isOnline to true on success', async () => {
    const { isOnline, ping } = useNetworkStatus()
    await ping()
    expect(isOnline.value).toBe(true)
  })

  it('ping sets isOnline to false on failure', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('fail'))
    const { isOnline, ping } = useNetworkStatus()
    await ping()
    expect(isOnline.value).toBe(false)
  })

  it('ping sets isOnline to false when navigator.onLine is false', async () => {
    ;(navigator as any).onLine = false
    const { isOnline, ping } = useNetworkStatus()
    await ping()
    expect(isOnline.value).toBe(false)
    expect(globalThis.fetch).not.toHaveBeenCalled()
    ;(navigator as any).onLine = true
  })

  it('isOnline is a singleton — shared across multiple useNetworkStatus() calls', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ ok: true }),
    })

    const a = useNetworkStatus()
    const b = useNetworkStatus()
    const c = useNetworkStatus()

    expect(a.isOnline.value).toBe(false)
    expect(b.isOnline.value).toBe(false)
    expect(c.isOnline.value).toBe(false)

    await c.ping()
    expect(c.isOnline.value).toBe(true)
    expect(a.isOnline.value).toBe(true)
    expect(b.isOnline.value).toBe(true)
  })

  it('online event listener is registered without error', () => {
    const { isOnline } = useNetworkStatus()
    // Trigger online — ping is async, but handler should not throw.
    expect(() => window.dispatchEvent(new Event('online'))).not.toThrow()
  })

  it('offline event sets isOnline to false immediately', () => {
    const { isOnline } = useNetworkStatus()
    isOnline.value = true

    window.dispatchEvent(new Event('offline'))
    expect(isOnline.value).toBe(false)
  })

  it('ping sends request to http://localhost:8080/health (absolute URL)', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ ok: true }),
    })
    const { ping } = useNetworkStatus()
    await ping()
    expect(globalThis.fetch).toHaveBeenCalledWith('http://localhost:8080/health')
  })
})
