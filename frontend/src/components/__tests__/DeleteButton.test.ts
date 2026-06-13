import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import DeleteButton from '../DeleteButton.vue'
import { useTauri } from '../../composables/useTauri'
import { useUserStore } from '../../stores/useUserStore'
import { deleteArticle } from '../../api/articles'

// Mock dependencies
vi.mock('../../composables/useTauri', () => ({
  useTauri: vi.fn(() => ({
    isTauri: { value: false },
    isBrowserLocal: { value: false },
    deleteArticle: vi.fn(),
  })),
}))

vi.mock('../../api/articles', () => ({
  deleteArticle: vi.fn(),
}))

describe('DeleteButton', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
    // Default: online (token present)
    const userStore = useUserStore()
    userStore.token = 'test-token'
    userStore.viewer = { id: 'u1', username: 'test', name: 'Test', anonymous_name: 'anon', expertise: [], reputation: 0, followers_count: 0, following_count: 0, created_at: '' } as any
  })

  it('shows trash icon by default, no confirm UI', () => {
    const wrapper = mount(DeleteButton, {
      props: { articleId: 'test-1' },
    })
    expect(wrapper.find('[aria-label="Delete article"]').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('Confirm?')
    expect(wrapper.text()).not.toContain('Cancel')
  })

  it('shows confirm UI after clicking trash', async () => {
    const wrapper = mount(DeleteButton, {
      props: { articleId: 'test-1' },
    })
    await wrapper.find('[aria-label="Delete article"]').trigger('click')
    expect(wrapper.text()).toContain('Confirm?')
    expect(wrapper.text()).toContain('Delete')
    expect(wrapper.text()).toContain('Cancel')
  })

  it('Cancel hides confirm UI, trash returns', async () => {
    const wrapper = mount(DeleteButton, {
      props: { articleId: 'test-1' },
    })
    await wrapper.find('[aria-label="Delete article"]').trigger('click')
    const cancelBtn = wrapper.findAll('button').find(b => b.text().trim() === 'Cancel')
    await cancelBtn!.trigger('click')
    expect(wrapper.find('[aria-label="Delete article"]').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('Confirm?')
  })

  it('emits deleted on successful server delete', async () => {
    ;(deleteArticle as any).mockResolvedValueOnce({})
    const wrapper = mount(DeleteButton, {
      props: { articleId: 'test-1' },
    })
    await wrapper.find('[aria-label="Delete article"]').trigger('click')
    const deleteBtn = wrapper.findAll('button').find(b => b.text().includes('Delete'))
    await deleteBtn!.trigger('click')
    await wrapper.vm.$nextTick()
    // Small wait for async delete to complete
    await new Promise(r => setTimeout(r, 10))
    expect(deleteArticle).toHaveBeenCalledWith('test-1')
    expect(wrapper.emitted('deleted')).toBeTruthy()
    expect(wrapper.emitted('deleted')![0]).toEqual(['test-1'])
  })

  it('emits error on API failure, confirm still visible', async () => {
    ;(deleteArticle as any).mockRejectedValueOnce(new Error('fail'))
    const wrapper = mount(DeleteButton, {
      props: { articleId: 'test-1' },
    })
    await wrapper.find('[aria-label="Delete article"]').trigger('click')
    const deleteBtn = wrapper.findAll('button').find(b => b.text().includes('Delete'))
    await deleteBtn!.trigger('click')
    await wrapper.vm.$nextTick()
    await new Promise(r => setTimeout(r, 10))
    expect(wrapper.emitted('deleted')).toBeFalsy()
    expect(wrapper.emitted('error')).toBeTruthy()
  })
})
