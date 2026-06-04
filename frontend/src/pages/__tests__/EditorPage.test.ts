import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: {} }),
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
}))

describe('EditorPage', () => {
  it('renders editor page title', async () => {
    setActivePinia(createPinia())
    const EditorPage = (await import('../EditorPage.vue')).default
    const wrapper = mount(EditorPage, {
      global: {
        stubs: { 'router-link': true, 'router-view': true },
      },
    })
    expect(wrapper.text()).toContain('Create Article')
  })
})
