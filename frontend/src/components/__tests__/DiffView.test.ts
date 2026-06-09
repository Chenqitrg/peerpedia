import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import DiffView from '../DiffView.vue'
import type { DiffResult } from '../DiffView.vue'

const sampleDiff: DiffResult = {
  files: ['article.md'],
  hunks: [{
    old_start: 1, old_lines: 3, new_start: 1, new_lines: 4,
    header: '',
    lines: [
      { line_type: 'ctx', content: '# Version 1', old_lineno: 1, new_lineno: 1 },
      { line_type: 'del', content: '', old_lineno: 2, new_lineno: null },
      { line_type: 'add', content: '# Version 2', old_lineno: null, new_lineno: 2 },
      { line_type: 'ctx', content: 'Hello', old_lineno: 3, new_lineno: 3 },
      { line_type: 'add', content: 'New line', old_lineno: null, new_lineno: 4 },
    ],
  }],
}

describe('DiffView', () => {
  it('shows placeholder when diff is null', () => {
    const wrapper = mount(DiffView, { props: { diff: null } })
    expect(wrapper.text()).toContain('Select two commits')
  })

  it('shows no differences message for empty diff', () => {
    const empty: DiffResult = { files: [], hunks: [] }
    const wrapper = mount(DiffView, { props: { diff: empty } })
    expect(wrapper.text()).toContain('No differences')
  })

  it('renders additions and deletions with correct counts', () => {
    const wrapper = mount(DiffView, { props: { diff: sampleDiff } })
    expect(wrapper.text()).toContain('# Version 1')
    expect(wrapper.text()).toContain('# Version 2')
    expect(wrapper.text()).toContain('New line')
    expect(wrapper.text()).toContain('+2')
    expect(wrapper.text()).toContain('-1')
  })

  it('shows file count and summary', () => {
    const wrapper = mount(DiffView, { props: { diff: sampleDiff } })
    expect(wrapper.text()).toContain('1 file(s) changed')
    expect(wrapper.text()).toContain('+2')
    expect(wrapper.text()).toContain('-1')
  })

  it('renders hunk header with line numbers', () => {
    const wrapper = mount(DiffView, { props: { diff: sampleDiff } })
    expect(wrapper.text()).toContain('@@ -1,3 +1,4 @@')
  })

  // Regression: deleted lines must have danger styling
  it('applies danger class to deleted lines', () => {
    const wrapper = mount(DiffView, { props: { diff: sampleDiff } })
    // The '-' prefix on deleted lines should have text-danger class
    const delPrefixes = wrapper.findAll('.text-danger')
    expect(delPrefixes.length).toBeGreaterThan(0)
  })

  // Regression: added lines must have success styling
  it('applies success class to added lines', () => {
    const wrapper = mount(DiffView, { props: { diff: sampleDiff } })
    const addPrefixes = wrapper.findAll('.text-success')
    expect(addPrefixes.length).toBeGreaterThan(0)
  })

  // Regression: word-level diff highlighting within changed lines
  it('highlights changed words in deletions and additions', () => {
    const wordDiff: DiffResult = {
      files: ['article.typ'],
      hunks: [{
        old_start: 1, old_lines: 1, new_start: 1, new_lines: 1,
        header: '',
        lines: [
          { line_type: 'del', content: 'old version text here', old_lineno: 1, new_lineno: null },
          { line_type: 'add', content: 'new version text here', old_lineno: null, new_lineno: 1 },
        ],
      }],
    }
    const wrapper = mount(DiffView, { props: { diff: wordDiff } })
    const html = wrapper.html()
    // Word-level diff should wrap changed words in spans
    expect(html).toContain('diff-word-del')
    expect(html).toContain('diff-word-add')
  })
})
