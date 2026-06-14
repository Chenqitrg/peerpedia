// SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
// SPDX-License-Identifier: CC-BY-NC-SA-4.0

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import SyncButton from '../SyncButton.vue'

const mockConnect = vi.fn()
const mockDisconnect = vi.fn()
const mockConnectionState = ref<'idle' | 'connecting' | 'synced'>('idle')
const mockFlash = ref(false)

vi.mock('@/composables/useNetworkStatus', () => ({
  useNetworkStatus: () => ({
    connectionState: mockConnectionState,
    flash: mockFlash,
    connect: mockConnect,
    disconnect: mockDisconnect,
  }),
}))

const mockPendingCount = ref(0)
vi.mock('@/composables/useAutoSync', () => ({
  useAutoSync: () => ({
    pendingCount: mockPendingCount,
  }),
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}))

describe('SyncButton', () => {
  beforeEach(() => {
    mockConnectionState.value = 'idle'
    mockFlash.value = false
    mockPendingCount.value = 0
    mockConnect.mockClear()
    mockDisconnect.mockClear()
  })

  // ── Render: 32x32 icon button with corner dot ──────────────────

  it('renders idle state: WifiOff icon, gray dot, no text', () => {
    const wrapper = mount(SyncButton)
    expect(wrapper.find('.sync-dot--idle').exists()).toBe(true)
    expect(wrapper.find('svg').exists()).toBe(true)
    expect(wrapper.attributes('title')).toBe('nav.syncConnectAria')
  })

  it('renders connecting state: Wifi icon, white pulsing dot', () => {
    mockConnectionState.value = 'connecting'
    const wrapper = mount(SyncButton)
    expect(wrapper.find('.sync-dot--connecting').exists()).toBe(true)
    expect(wrapper.find('.sync-icon--connecting').exists()).toBe(true)
    expect(wrapper.attributes('title')).toBe('nav.syncConnecting')
  })

  it('renders synced state: Wifi icon, blue dot with glow', () => {
    mockConnectionState.value = 'synced'
    const wrapper = mount(SyncButton)
    expect(wrapper.find('.sync-btn--synced').exists()).toBe(true)
    expect(wrapper.find('.sync-dot--synced').exists()).toBe(true)
    expect(wrapper.find('.sync-icon--synced').exists()).toBe(true)
    expect(wrapper.attributes('title')).toBe('nav.syncDisconnectAria')
  })

  it('shows red flash dot', () => {
    mockConnectionState.value = 'idle'
    mockFlash.value = true
    const wrapper = mount(SyncButton)
    expect(wrapper.find('.sync-dot--flash').exists()).toBe(true)
    expect(wrapper.find('.sync-icon--flash').exists()).toBe(true)
  })

  // ── Pending count badge ────────────────────────────────────────

  it('shows pending count badge when offline with pending', () => {
    mockConnectionState.value = 'idle'
    mockPendingCount.value = 3
    const wrapper = mount(SyncButton)
    const badge = wrapper.find('.sync-badge')
    expect(badge.exists()).toBe(true)
    expect(badge.text()).toBe('3')
  })

  it('hides pending badge when online even with pending', () => {
    mockConnectionState.value = 'synced'
    mockPendingCount.value = 3
    const wrapper = mount(SyncButton)
    expect(wrapper.find('.sync-badge').exists()).toBe(false)
  })

  it('hides pending count badge when pendingCount is 0', () => {
    mockConnectionState.value = 'idle'
    mockPendingCount.value = 0
    const wrapper = mount(SyncButton)
    expect(wrapper.find('.sync-badge').exists()).toBe(false)
  })

  it('shows pending count in tooltip when offline with pending', () => {
    mockConnectionState.value = 'idle'
    mockPendingCount.value = 2
    const wrapper = mount(SyncButton)
    expect(wrapper.attributes('title')).toBe('2 pending sync(s)')
  })

  it('shows normal tooltip when synced (no pending mention)', () => {
    mockConnectionState.value = 'synced'
    mockPendingCount.value = 1
    const wrapper = mount(SyncButton)
    expect(wrapper.attributes('title')).toBe('nav.syncDisconnectAria')
  })

  // ── Click behavior ─────────────────────────────────────────────

  it('is a button element', () => {
    const wrapper = mount(SyncButton)
    expect(wrapper.find('button').exists()).toBe(true)
  })

  it('calls connect() on click when idle', async () => {
    const wrapper = mount(SyncButton)
    await wrapper.trigger('click')
    expect(mockConnect).toHaveBeenCalledOnce()
  })

  it('calls disconnect() on click when synced', async () => {
    mockConnectionState.value = 'synced'
    const wrapper = mount(SyncButton)
    await wrapper.trigger('click')
    expect(mockDisconnect).toHaveBeenCalledOnce()
  })

  it('calls disconnect() on click when connecting (cancel)', async () => {
    mockConnectionState.value = 'connecting'
    const wrapper = mount(SyncButton)
    await wrapper.trigger('click')
    expect(mockDisconnect).toHaveBeenCalledOnce()
  })
})
