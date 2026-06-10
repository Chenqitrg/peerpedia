import { describe, it, expect } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import CodeEditor from '../CodeEditor.vue'

describe('CodeEditor', () => {
  it('renders a CodeMirror editor element', () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: '# Hello', format: 'markdown' },
    })
    const cm = wrapper.find('.cm-editor')
    expect(cm.exists()).toBe(true)
  })

  it('displays initial modelValue content', () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: '# Test Content', format: 'markdown' },
    })
    const editorEl = wrapper.find('.cm-content')
    expect(editorEl.exists()).toBe(true)
    expect(editorEl.text()).toContain('Test Content')
  })

  it('updates displayed content when modelValue changes', async () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: 'initial', format: 'markdown' },
    })
    await flushPromises()
    await nextTick()
    await wrapper.setProps({ modelValue: 'updated content' })
    await flushPromises()
    await nextTick()
    const editorEl = wrapper.find('.cm-content')
    expect(editorEl.text()).toContain('updated content')
  })

  it('exposes codemirrorView via defineExpose', async () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: '', format: 'markdown' },
    })
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.codemirrorView).toBeDefined()
    expect(vm.codemirrorView.state).toBeDefined()
  })

  // ── Typst format (post codemirror-lang-typst) ─────────────────────

  it('renders CodeMirror for Typst format, NOT textarea', () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: '= Title', format: 'typst' },
    })
    expect(wrapper.find('.cm-editor').exists()).toBe(true)
    expect(wrapper.find('textarea').exists()).toBe(false)
  })

  it('renders CodeMirror for Markdown format (regression check)', () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: '# Title', format: 'markdown' },
    })
    expect(wrapper.find('.cm-editor').exists()).toBe(true)
    expect(wrapper.find('textarea').exists()).toBe(false)
  })

  it('displays Typst content in CodeMirror editor', async () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: '= Introduction', format: 'typst' },
    })
    await nextTick()
    const editorEl = wrapper.find('.cm-content')
    expect(editorEl.exists()).toBe(true)
    expect(editorEl.text()).toContain('= Introduction')
  })

  it('exposes codemirrorView for Typst format', async () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: '', format: 'typst' },
    })
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.codemirrorView).toBeDefined()
    expect(vm.codemirrorView.state).toBeDefined()
    // Confirm the doc content is accessible
    expect(vm.codemirrorView.state.doc.toString()).toBe('')
  })

  it('updates CodeMirror when switching format from Markdown to Typst', async () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: 'some content', format: 'markdown' },
    })
    await flushPromises()
    await wrapper.setProps({ format: 'typst' as const, modelValue: '= New Typst' })
    await flushPromises()
    await nextTick()
    const editorEl = wrapper.find('.cm-content')
    expect(editorEl.exists()).toBe(true)
    expect(editorEl.text()).toContain('= New Typst')
  })
})
