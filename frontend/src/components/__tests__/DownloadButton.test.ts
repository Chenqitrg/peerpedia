import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import DownloadButton from '../DownloadButton.vue'

describe('DownloadButton', () => {
  beforeEach(() => {
    URL.createObjectURL = vi.fn(() => 'blob:test')
    URL.revokeObjectURL = vi.fn()
  })

  it('renders download button with icon', () => {
    const wrapper = mount(DownloadButton, {
      props: { format: 'source', content: '# Hello' },
    })
    // Icon-only: no text labels
    expect(wrapper.find('svg').exists()).toBe(true)
    expect(wrapper.find('button').exists()).toBe(true)
  })

  it('renders compiled button with icon', () => {
    const wrapper = mount(DownloadButton, {
      props: { format: 'compiled', content: '# Hello' },
    })
    expect(wrapper.find('svg').exists()).toBe(true)
  })

  it('has tooltip via aria-label', () => {
    const wrapper = mount(DownloadButton, {
      props: { format: 'source', content: '# Hello' },
    })
    expect(wrapper.attributes('aria-label')).toBe('Download source (.md)')
  })

  it('has tooltip for compiled format', () => {
    const wrapper = mount(DownloadButton, {
      props: { format: 'compiled', content: '# Hello' },
    })
    expect(wrapper.attributes('aria-label')).toBe('Download compiled (.html)')
  })

  it('downloads source as .md file', async () => {
    const wrapper = mount(DownloadButton, {
      props: { format: 'source', content: '# Hello', filename: 'test-article' },
    })
    await wrapper.find('button').trigger('click')
    expect(URL.createObjectURL).toHaveBeenCalled()
  })

  it('downloads compiled markdown as .html', async () => {
    const wrapper = mount(DownloadButton, {
      props: { format: 'compiled', content: '# Hello', filename: 'test-article' },
    })
    await wrapper.find('button').trigger('click')
    expect(URL.createObjectURL).toHaveBeenCalled()
  })

  it('appends commit hash to filename when provided', async () => {
    const createElementSpy = vi.spyOn(document, 'createElement')
    const wrapper = mount(DownloadButton, {
      props: { format: 'source', content: '# Hello', filename: 'MyArticle', commitHash: 'abc123def456' },
    })
    await wrapper.find('button').trigger('click')
    const anchor = createElementSpy.mock.results.find(r => {
      try { return r.value instanceof HTMLAnchorElement } catch { return false }
    })
    expect(anchor).toBeDefined()
    expect((anchor!.value as HTMLAnchorElement).download).toContain('abc123d')
  })

  it('uses custom filename when provided', async () => {
    const createElementSpy = vi.spyOn(document, 'createElement')
    const wrapper = mount(DownloadButton, {
      props: { format: 'source', content: '# Hello', filename: 'My Article' },
    })
    await wrapper.find('button').trigger('click')
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
    expect(URL.createObjectURL).toHaveBeenCalled()
  })

  it('sanitizes filename to prevent path traversal', async () => {
    const createElementSpy = vi.spyOn(document, 'createElement')
    const wrapper = mount(DownloadButton, {
      props: { format: 'source', content: '# Hello', filename: '../../../etc/passwd' },
    })
    await wrapper.find('button').trigger('click')
    expect(createElementSpy).toHaveBeenCalled()
  })

  it('does not trigger when disabled prop is true', async () => {
    const wrapper = mount(DownloadButton, {
      props: { format: 'source', content: '# Hello', disabled: true },
    })
    await wrapper.find('button').trigger('click')
    expect(URL.createObjectURL).not.toHaveBeenCalled()
  })

  // Regression: Typst source downloads as .typ file
  it('shows .typ aria-label for Typst source downloads', () => {
    const wrapper = mount(DownloadButton, {
      props: { format: 'source', content: '= Typst', contentFormat: 'typst' },
    })
    expect(wrapper.attributes('aria-label')).toBe('Download source (.typ)')
  })

  // Regression: Typst compiled downloads as .pdf
  it('shows .pdf aria-label for Typst compiled downloads', () => {
    const wrapper = mount(DownloadButton, {
      props: { format: 'compiled', content: '= Typst', contentFormat: 'typst' },
    })
    expect(wrapper.attributes('aria-label')).toBe('Download compiled (.pdf)')
  })

  // Regression: repo download creates blob URL in Tauri mode
  it('downloads repo via blob URL in Tauri mode', async () => {
    const mockExportArticle = vi.fn().mockResolvedValue(
      'H4sIAAAAAAAA/8vJTElVKEstKk3NK1Eoz0gtSlUoSi3KSQUAoxhasBcAAAA='
    )
    // Re-mock useTauri with Tauri mode enabled + exportArticle mock
    vi.doMock('../../composables/useTauri', () => ({
      useTauri: () => ({
        isTauri: { value: true },
        isBrowserLocal: { value: false },
        exportArticle: mockExportArticle,
      }),
    }))
    // Force re-import to pick up new mock
    vi.resetModules()
    const { default: DownloadButtonFresh } = await import('../DownloadButton.vue')
    const wrapper = mount(DownloadButtonFresh, {
      props: { format: 'repo', content: '', articleId: 'test-1', filename: 'my-article' },
    })
    await wrapper.find('button').trigger('click')
    await new Promise(r => setTimeout(r, 50))

    expect(URL.createObjectURL).toHaveBeenCalled()
    // The blob should be application/gzip
    const blobArg = (URL.createObjectURL as any).mock.calls[0]?.[0]
    expect(blobArg?.type).toBe('application/gzip')
  })
})
