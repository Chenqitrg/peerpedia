// SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
// SPDX-License-Identifier: CC-BY-NC-SA-4.0

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useNetworkStatus } from '../useNetworkStatus'

describe('useNetworkStatus', () => {
  beforeEach(() => {
    useNetworkStatus()._resetForTest()
    vi.useFakeTimers()
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ ok: true }),
    })
    Object.defineProperty(navigator, 'onLine', {
      value: true, writable: true, configurable: true,
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  // ── S1: Initial state ──────────────────────────────────────────────

  it('S1: starts in idle state, isSynced false', () => {
    const { connectionState, isSynced } = useNetworkStatus()
    expect(connectionState.value).toBe('idle')
    expect(isSynced.value).toBe(false)
  })

  // ── S2: Connect success ────────────────────────────────────────────

  it('S2: connect() transitions idle → connecting → synced on success', async () => {
    const { connectionState, isSynced, connect } = useNetworkStatus()
    connect()
    expect(connectionState.value).toBe('connecting')
    expect(isSynced.value).toBe(false)

    await vi.runAllTimersAsync()
    expect(connectionState.value).toBe('synced')
    expect(isSynced.value).toBe(true)
  })

  it('S2: after synced, performing another server action stays synced', async () => {
    const { connectionState, connect, notifySuccess } = useNetworkStatus()
    connect()
    await vi.runAllTimersAsync()
    expect(connectionState.value).toBe('synced')
    // Simulate a successful API response after connect
    notifySuccess()
    expect(connectionState.value).toBe('synced')
  })

  // ── S3: Connect failure (timeout) ──────────────────────────────────

  it('S3: unreachable server → timeout → idle', async () => {
    // Use a promise that never resolves to simulate unreachable server.
    globalThis.fetch = vi.fn().mockImplementation(() => new Promise(() => {}))
    const { connectionState, connect } = useNetworkStatus()

    connect()
    expect(connectionState.value).toBe('connecting')

    // Advance past the 10s timeout.
    await vi.advanceTimersByTimeAsync(10_000)
    expect(connectionState.value).toBe('idle')
  })

  it('S3: timeout triggers red flash for 500ms', async () => {
    globalThis.fetch = vi.fn().mockImplementation(() => new Promise(() => {}))
    const { connectionState, flash, connect } = useNetworkStatus()

    connect()
    // Advance just to the timeout.
    vi.advanceTimersByTime(10_000)
    expect(connectionState.value).toBe('idle')
    expect(flash.value).toBe(true)

    // Flash clears after 500ms.
    vi.advanceTimersByTime(500)
    expect(flash.value).toBe(false)
  })

  it('S3: after timeout, isSynced stays false', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('fail'))
    const { isSynced, connect } = useNetworkStatus()

    connect()
    await vi.advanceTimersByTimeAsync(10_000)
    expect(isSynced.value).toBe(false)
  })

  // ── S4: Manual disconnect ──────────────────────────────────────────

  it('S4: disconnect() from synced → idle', async () => {
    const { connectionState, connect, disconnect } = useNetworkStatus()
    connect()
    await vi.runAllTimersAsync()
    expect(connectionState.value).toBe('synced')

    disconnect()
    expect(connectionState.value).toBe('idle')
  })

  it('S4: after disconnect, isSynced returns false', async () => {
    const { isSynced, connect, disconnect } = useNetworkStatus()
    connect()
    await vi.runAllTimersAsync()

    disconnect()
    expect(isSynced.value).toBe(false)
  })

  // ── S5: Cancel connecting ──────────────────────────────────────────

  it('S5: tap during connecting → disconnect() → idle, timeout does NOT fire', async () => {
    globalThis.fetch = vi.fn().mockImplementation(
      () => new Promise(resolve => setTimeout(() => resolve({ ok: true } as any), 5000))
    )
    const { connectionState, connect, disconnect } = useNetworkStatus()
    connect()
    expect(connectionState.value).toBe('connecting')

    disconnect()
    expect(connectionState.value).toBe('idle')

    // Advance past the fetch resolution — should NOT promote to synced (guard restored).
    await vi.advanceTimersByTimeAsync(5000)
    expect(connectionState.value).toBe('idle')

    // Advance past the 10s timeout — should NOT fire (timer was cleared on disconnect).
    await vi.advanceTimersByTimeAsync(10000)
    expect(connectionState.value).toBe('idle')
  })

  // ── S6: Auto-disconnect ───────────────────────────────────────────

  it('S6: disconnect() called on offline event returns to idle', () => {
    // The offline event handler simply calls disconnect(). Verify disconnect() behavior.
    const { connectionState, disconnect } = useNetworkStatus()
    // Simulate API-driven promotion to synced
    connectionState.value = 'synced'

    disconnect()
    expect(connectionState.value).toBe('idle')
  })

  it('S6: notifyFailure during synced auto-disconnects to idle (no flash)', async () => {
    const { connectionState, connect, notifyFailure, flash } = useNetworkStatus()
    connect()
    await vi.advanceTimersByTimeAsync(10_000)
    expect(connectionState.value).toBe('synced')

    // Simulate network error on a server action while synced (S6.1)
    notifyFailure()
    expect(connectionState.value).toBe('idle')
    expect(flash.value).toBe(false) // no flash — was already synced, not an active attempt
  })

  // ── S7: Auto-detect on browser online event ───────────────────────

  it('S7: browser online event triggers auto-ping and promotes to synced', async () => {
    const { connectionState, isSynced } = useNetworkStatus()
    expect(connectionState.value).toBe('idle')

    window.dispatchEvent(new Event('online'))
    expect(connectionState.value).toBe('connecting')

    // Resolve the fetch promise (microtask) without firing the 10s timer.
    await vi.advanceTimersByTimeAsync(1)
    expect(connectionState.value).toBe('synced')
    expect(isSynced.value).toBe(true)
  })

  it('S7: browser online event with unreachable server → timeout → idle + flash', async () => {
    globalThis.fetch = vi.fn().mockImplementation(() => new Promise(() => {}))
    const { connectionState, flash } = useNetworkStatus()

    window.dispatchEvent(new Event('online'))
    expect(connectionState.value).toBe('connecting')

    // Advance past the 10s timeout to trigger notifyFailure.
    await vi.advanceTimersByTimeAsync(10_000)
    expect(connectionState.value).toBe('idle')
    expect(flash.value).toBe(true)

    await vi.advanceTimersByTimeAsync(500)
    expect(flash.value).toBe(false)
  })

  // ── Guards ─────────────────────────────────────────────────────────

  it('notifySuccess from idle does NOT promote (only connecting→synced)', () => {
    const { connectionState, notifySuccess } = useNetworkStatus()
    expect(connectionState.value).toBe('idle')

    notifySuccess()
    expect(connectionState.value).toBe('idle') // guard: not connecting
  })

  it('connect() when navigator.onLine is false does not arm timer', () => {
    ;(navigator as any).onLine = false
    const { connectionState, connect } = useNetworkStatus()
    connect()
    expect(connectionState.value).toBe('idle') // ping() synchronously reverts

    // Timer was NOT armed — advancing should not trigger notifyFailure side effects
    vi.advanceTimersByTime(10000)
    expect(connectionState.value).toBe('idle')
    ;(navigator as any).onLine = true
  })

  // ── Module-level singleton ─────────────────────────────────────────

  it('connectionState is a singleton — shared across multiple useNetworkStatus() calls', async () => {
    const a = useNetworkStatus()
    const b = useNetworkStatus()
    const c = useNetworkStatus()

    expect(a.connectionState.value).toBe('idle')
    expect(b.connectionState.value).toBe('idle')
    expect(c.connectionState.value).toBe('idle')

    c.connect()
    expect(a.connectionState.value).toBe('connecting')
    expect(b.connectionState.value).toBe('connecting')

    await vi.runAllTimersAsync()
    expect(a.connectionState.value).toBe('synced')
    expect(b.connectionState.value).toBe('synced')
    expect(c.connectionState.value).toBe('synced')
  })

  // ── Legacy: ping() still works for direct probing ──────────────────

  it('ping sends request to /health', async () => {
    const { ping } = useNetworkStatus()
    await ping()
    expect(globalThis.fetch).toHaveBeenCalledWith(expect.stringMatching(/\/health$/))
  })

  it('ping from idle does not change state', async () => {
    const { connectionState, ping } = useNetworkStatus()
    await ping()
    // ping calls notifySuccess() but guard blocks promotion from idle
    expect(connectionState.value).toBe('idle')
  })
})
