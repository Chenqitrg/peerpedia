import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const RouterLinkStub = {
  props: ['to'],
  template: '<a :href="to"><slot /></a>',
}

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useRoute: () => ({ params: { id: 'art-1' } }),
  RouterLink: { template: '<a><slot /></a>' },
}))

vi.mock('../../api/articles', () => ({
  getCitations: vi.fn().mockResolvedValue({
    cites: [
      { article_id: 'cited-1', title: 'Referenced Paper', forward_prob: 0.8, backward_prob: 0.2 },
      { article_id: 'cited-2', title: 'Another Reference', forward_prob: 0.6, backward_prob: 0.4 },
    ],
    cited_by: [
      { article_id: 'citing-1', title: 'Citing Paper', forward_prob: 0.3, backward_prob: 0.7 },
    ],
  }),
}))

describe('CitationsPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders citations page with heading', async () => {
    const CitationsPage = (await import('../CitationsPage.vue')).default
    const wrapper = mount(CitationsPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('Citations')
  })

  it('renders references (cites)', async () => {
    const CitationsPage = (await import('../CitationsPage.vue')).default
    const wrapper = mount(CitationsPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('Referenced Paper')
    expect(wrapper.text()).toContain('Another Reference')
  })

  it('renders cited-by entries', async () => {
    const CitationsPage = (await import('../CitationsPage.vue')).default
    const wrapper = mount(CitationsPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('Citing Paper')
  })

  it('has back navigation', async () => {
    const CitationsPage = (await import('../CitationsPage.vue')).default
    const wrapper = mount(CitationsPage, {
      global: { stubs: { 'router-link': RouterLinkStub, 'router-view': true } },
    })
    await flushPromises()
    const backBtn = wrapper.find('button[aria-label="Back to article"]')
    expect(backBtn.exists()).toBe(true)
  })
})
