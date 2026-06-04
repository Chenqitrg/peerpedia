import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ArticleCard from '../ArticleCard.vue'

describe('ArticleCard', () => {
  const article = {
    id: '1',
    title: 'Quantum Mechanics',
    status: 'published',
    authors: ['Alice', 'Bob'],
    score: { originality: 5, rigor: 4, completeness: 3, pedagogy: 5, impact: 4 },
    fork_count: 2,
    review_count: 3,
    created_at: '2026-01-01',
    updated_at: '2026-06-01',
  }

  it('renders article title', () => {
    const wrapper = mount(ArticleCard, { props: { article } })
    expect(wrapper.text()).toContain('Quantum Mechanics')
  })

  it('renders authors', () => {
    const wrapper = mount(ArticleCard, { props: { article } })
    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.text()).toContain('Bob')
  })

  it('renders score', () => {
    const wrapper = mount(ArticleCard, { props: { article } })
    expect(wrapper.text()).toContain('5')
    expect(wrapper.text()).toContain('4')
  })

  it('renders status', () => {
    const wrapper = mount(ArticleCard, { props: { article } })
    expect(wrapper.text()).toContain('published')
  })
})
