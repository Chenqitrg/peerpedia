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

  // T7: Typst slot fallback
  it('renders Typst fallback slot when format is typst', () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: '= Title', format: 'typst' },
      slots: { 'typst-fallback': '<textarea class="typst-fallback">= Title</textarea>' },
    })
    expect(wrapper.find('.cm-editor').exists()).toBe(false)
    expect(wrapper.find('.typst-fallback').exists()).toBe(true)
  })
})
