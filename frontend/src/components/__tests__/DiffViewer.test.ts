import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import DiffViewer from '../DiffViewer.vue'
import * as articlesApi from '../../api/articles'

// Mock the API module
vi.mock('../../api/articles', () => ({
  getHistory: vi.fn(),
  getDiff: vi.fn(),
}))

// Mock diff2html so we don't actually render HTML
vi.mock('diff2html', () => ({
  html: (_diff: string, _config: unknown) => {
    if (!_diff) return ''
    return '<div class="d2h-wrapper"><table class="d2h-diff-table"><tr><td>diff content</td></tr></table></div>'
  },
}))

const mockedApi = vi.mocked(articlesApi)

describe('DiffViewer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders with articleId prop', () => {
    mockedApi.getHistory.mockResolvedValue({ commits: [] })
    const wrapper = mount(DiffViewer, { props: { articleId: '42' } })
    expect(wrapper.exists()).toBe(true)
    expect(wrapper.text()).toContain('History / Diff')
  })

  it('shows loading state initially', () => {
    // Return a promise that never resolves so loading stays true
    mockedApi.getHistory.mockReturnValue(new Promise(() => {}))
    const wrapper = mount(DiffViewer, { props: { articleId: '42' } })
    expect(wrapper.find('.animate-pulse').exists()).toBe(true)
  })

  it('shows empty state when no commits', async () => {
    mockedApi.getHistory.mockResolvedValue({ commits: [] })
    const wrapper = mount(DiffViewer, { props: { articleId: '42' } })
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('No commits yet')
  })

  it('renders diff content when data loads with commits', async () => {
    const commits = [
      { hash: 'abc123', author: 'Alice', message: 'Initial commit', timestamp: '2024-01-01' },
      { hash: 'def456', author: 'Bob', message: 'Second commit', timestamp: '2024-01-02' },
    ]
    mockedApi.getHistory.mockResolvedValue({ commits })
    mockedApi.getDiff.mockResolvedValue({
      diff_text: '--- a/file.md\n+++ b/file.md\n@@ -1 +1 @@\n-old content\n+new content\n',
      files: ['file.md'],
    })
    const wrapper = mount(DiffViewer, { props: { articleId: '42' } })
    // Wait for history fetch
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    // Should have loaded commits into selects
    expect(wrapper.find('select').exists()).toBe(true)

    // getDiff should have been called automatically with two commits
    expect(mockedApi.getDiff).toHaveBeenCalledWith('42', 'abc123', 'def456')

    // Wait for diff fetch to resolve
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    // The diff2html content should be rendered
    expect(wrapper.find('.diff2html-wrapper').exists()).toBe(true)
    expect(wrapper.html()).toContain('d2h-wrapper')
  })

  it('shows error state when API fails', async () => {
    mockedApi.getHistory.mockRejectedValue(new Error('Network error'))
    const wrapper = mount(DiffViewer, { props: { articleId: '42' } })
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Network error')
    expect(wrapper.text()).toContain('Retry')
  })

  it('shows error state when getDiff fails', async () => {
    const commits = [
      { hash: 'abc123', author: 'Alice', message: 'Initial commit', timestamp: '2024-01-01' },
      { hash: 'def456', author: 'Bob', message: 'Second commit', timestamp: '2024-01-02' },
    ]
    mockedApi.getHistory.mockResolvedValue({ commits })
    mockedApi.getDiff.mockRejectedValue(new Error('Diff fetch error'))
    const wrapper = mount(DiffViewer, { props: { articleId: '42' } })
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    // Wait for diff fetch
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Diff fetch error')
  })

  it('shows waiting message when only one commit exists', async () => {
    const commits = [
      { hash: 'abc123', author: 'Alice', message: 'Only commit', timestamp: '2024-01-01' },
    ]
    mockedApi.getHistory.mockResolvedValue({ commits })
    const wrapper = mount(DiffViewer, { props: { articleId: '42' } })
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Select two different commits to compare')
  })

  it('shows score in commit label when score is present', async () => {
    const commits = [
      {
        hash: 'abc1234def',
        author: 'Alice',
        message: 'Initial commit',
        timestamp: '2024-01-01',
        score: { originality: 4, rigor: 3, completeness: 4, pedagogy: 3, impact: 4 },
      },
      {
        hash: 'def5678abc',
        author: 'Bob',
        message: 'Second commit',
        timestamp: '2024-01-02',
        // No score
      },
    ]
    mockedApi.getHistory.mockResolvedValue({ commits })
    mockedApi.getDiff.mockResolvedValue({
      diff_text: '--- a/file.md\n+++ b/file.md\n@@ -1 +1 @@\n-old\n+new\n',
      files: ['file.md'],
    })
    const wrapper = mount(DiffViewer, { props: { articleId: '42' } })
    // Wait for history fetch
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()
    // Wait for diff fetch
    await new Promise(process.nextTick)
    await wrapper.vm.$nextTick()

    // First commit has score: avg of (4+3+4+3+4)/5 = 3.6
    expect(wrapper.text()).toContain('[3.6]')
    // Commit with no score should appear without brackets
    const allOptions = wrapper.findAll('option')
    const labels = allOptions.map(o => o.text())
    const withScore = labels.filter(l => l.includes('[3.6]'))
    // Appears in both selectors (base + head)
    expect(withScore.length).toBe(2)
  })
})
