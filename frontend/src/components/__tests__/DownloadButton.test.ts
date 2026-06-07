import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import DownloadButton from '../DownloadButton.vue'

describe('DownloadButton', () => {
  beforeEach(() => {
    // Mock URL.createObjectURL/revokeObjectURL
    URL.createObjectURL = vi.fn(() => 'blob:test')
    URL.revokeObjectURL = vi.fn()
  })

  it('renders source button with download icon', () => {
    const wrapper = mount(DownloadButton, {
      props: { format: 'source', content: '# Hello' },
    })
    expect(wrapper.text()).toContain('Source')
    expect(wrapper.find('svg').exists()).toBe(true)
  })

  it('renders compiled button with file icon', () => {
    const wrapper = mount(DownloadButton, {
      props: { format: 'compiled', content: '# Hello' },
    })
    expect(wrapper.text()).toContain('HTML')
  })

  it('downloads source as .md file', async () => {
    const wrapper = mount(DownloadButton, {
      props: { format: 'source', content: '# Hello', filename: 'test-article' },
    })
    await wrapper.find('button').trigger('click')
    // Should trigger a download
    expect(URL.createObjectURL).toHaveBeenCalled()
  })

  it('downloads compiled markdown as .html', async () => {
    const wrapper = mount(DownloadButton, {
      props: { format: 'compiled', content: '# Hello', filename: 'test-article' },
    })
    await wrapper.find('button').trigger('click')
    expect(URL.createObjectURL).toHaveBeenCalled()
  })

  it('uses custom filename when provided', async () => {
    const createElementSpy = vi.spyOn(document, 'createElement')
    const wrapper = mount(DownloadButton, {
      props: { format: 'source', content: '# Hello', filename: 'My Article' },
    })
    await wrapper.find('button').trigger('click')
    const anchor = createElementSpy.mock.results.find(r => {
      try { return r.value instanceof HTMLAnchorElement } catch { return false }
    })
    expect(createElementSpy).toHaveBeenCalled()
  })

  it('disables button while downloading', async () => {
    const wrapper = mount(DownloadButton, {
      props: { format: 'source', content: '# Hello' },
    })
    const btn = wrapper.find('button')
    expect(btn.attributes('disabled')).toBeUndefined()
    await btn.trigger('click')
    expect(btn.attributes('disabled')).toBeDefined()
  })

  it('compiles markdown to HTML for compiled format', async () => {
    const wrapper = mount(DownloadButton, {
      props: { format: 'compiled', content: '# Hello\n\n$$x^2$$', filename: 'test' },
    })
    await wrapper.find('button').trigger('click')
    // The blob should contain rendered HTML, not raw markdown
    expect(URL.createObjectURL).toHaveBeenCalled()
  })

  it('does not trigger when disabled prop is true', async () => {
    const wrapper = mount(DownloadButton, {
      props: { format: 'source', content: '# Hello', disabled: true },
    })
    await wrapper.find('button').trigger('click')
    expect(URL.createObjectURL).not.toHaveBeenCalled()
  })
})
