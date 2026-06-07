import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import NetworkStatusBadge from '../NetworkStatusBadge.vue'

// Mock useNetworkStatus to control isOnline.
vi.mock('@/composables/useNetworkStatus', () => ({
  useNetworkStatus: vi.fn(),
}))

import { useNetworkStatus } from '@/composables/useNetworkStatus'

const mockedUseNetworkStatus = useNetworkStatus as ReturnType<typeof vi.fn>

function setOnline(online: boolean) {
  mockedUseNetworkStatus.mockReturnValue({
    isOnline: { value: online },
    startPing: vi.fn(),
    stopPing: vi.fn(),
  })
}

describe('NetworkStatusBadge', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders online state with green dot when isOnline is true', () => {
    setOnline(true)
    const wrapper = mount(NetworkStatusBadge)
    expect(wrapper.find('.network-status-badge').exists()).toBe(true)
    const dot = wrapper.find('.status-dot')
    expect(dot.exists()).toBe(true)
    expect(dot.classes()).toContain('online')
  })

  it('renders offline state by default (isOnline starts false)', () => {
    setOnline(false)
    const wrapper = mount(NetworkStatusBadge)
    const dot = wrapper.find('.status-dot')
    expect(dot.exists()).toBe(true)
    expect(dot.classes()).toContain('offline')
    expect(dot.classes()).not.toContain('online')
  })

  it('renders offline state with gray dot when forceOffline', () => {
    setOnline(true) // Even when isOnline says true, forceOffline overrides
    const wrapper = mount(NetworkStatusBadge, {
      props: { forceOffline: true },
    })
    const dot = wrapper.find('.status-dot')
    expect(dot.exists()).toBe(true)
    expect(dot.classes()).toContain('offline')
    expect(dot.classes()).not.toContain('online')
  })
})
