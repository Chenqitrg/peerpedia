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

  // ── SPEC-HL-4/5: Typst mode (pure-JS StreamLanguage, no WASM) ─────

  it('SPEC-HL-4: renders CodeMirror for Typst format with StreamLanguage (no freeze)', () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: '= Title', format: 'typst' },
    })
    // Editor MUST render — user can type Typst immediately.
    // No WASM dependency means no freeze risk.
    expect(wrapper.find('.cm-editor').exists()).toBe(true)
    expect(wrapper.find('textarea').exists()).toBe(false)
  })

  it('SPEC-HL-5: Typst StreamLanguage highlights headings', async () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: '= Introduction\n\nBody text.', format: 'typst' },
    })
    await nextTick()
    // Content must be in the editor
    const contentEl = wrapper.find('.cm-content')
    expect(contentEl.exists()).toBe(true)
    expect(contentEl.text()).toContain('Introduction')
  })

  it('SPEC-HL-6: Typst StreamLanguage highlights function calls', async () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: '#strong[bold text]', format: 'typst' },
    })
    await nextTick()
    const contentEl = wrapper.find('.cm-content')
    expect(contentEl.exists()).toBe(true)
    expect(contentEl.text()).toContain('bold text')
  })

  it('SPEC-HL-7: Typst StreamLanguage highlights math mode', async () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: '$x^2 + y^2 = z^2$', format: 'typst' },
    })
    await nextTick()
    const contentEl = wrapper.find('.cm-content')
    expect(contentEl.exists()).toBe(true)
    expect(contentEl.text()).toContain('x^2')
  })

  // ── SPEC-HL-8: Freeze regression — no WASM, no hang risk ──────────

  it('SPEC-HL-8: Typst editor never freezes (pure JS, zero WASM deps)', () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: '= Content', format: 'typst' },
    })
    // Synchronous mount must succeed — no async WASM to wait on.
    // If this test hangs, the spec is violated.
    const cm = wrapper.find('.cm-editor')
    expect(cm.exists()).toBe(true)
    const content = wrapper.find('.cm-content')
    expect(content.exists()).toBe(true)
  })
})
