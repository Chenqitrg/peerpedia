import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import DeleteButton from '../DeleteButton.vue'
import { useTauri } from '../../composables/useTauri'
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

  it('emits deleted on successful delete', async () => {
    ;(deleteArticle as any).mockResolvedValueOnce({})
    const wrapper = mount(DeleteButton, {
      props: { articleId: 'test-1' },
    })
    await wrapper.find('[aria-label="Delete article"]').trigger('click')
    const deleteBtn = wrapper.findAll('button').find(b => b.text().includes('Delete'))
    await deleteBtn!.trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('deleted')).toBeTruthy()
    expect(wrapper.emitted('deleted')![0]).toEqual(['test-1'])
  })

  it('does not emit deleted on API failure, confirm still visible', async () => {
    ;(deleteArticle as any).mockRejectedValueOnce(new Error('fail'))
    const wrapper = mount(DeleteButton, {
      props: { articleId: 'test-1' },
    })
    await wrapper.find('[aria-label="Delete article"]').trigger('click')
    const deleteBtn = wrapper.findAll('button').find(b => b.text().includes('Delete'))
    await deleteBtn!.trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('deleted')).toBeFalsy()
  })
})
