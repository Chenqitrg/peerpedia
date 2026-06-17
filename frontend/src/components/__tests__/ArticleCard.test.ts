// SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
// SPDX-License-Identifier: CC-BY-NC-SA-4.0

import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ArticleCard from '../ArticleCard.vue'
import { useUserStore } from '../../stores/useUserStore'

const RouterLinkStub = {
  props: ['to'],
  template: '<a :href="to"><slot /></a>',
}

function makeArticle(overrides = {}) {
  return {
    id: 'art-1',
    title: 'Quantum Computing Foundations',
    status: 'sedimentation' as const,
    authors: [
      { id: 'u1', name: 'Alice Chen', anonymous_name: 'anonymous1' },
      { id: 'u2', name: 'Bob Lee', anonymous_name: 'anonymous2' },
    ],
    abstract: null as string | null,
    content_preview: 'This paper explores the fundamental principles of quantum computing, including superposition, entanglement, and quantum gates. We present a novel approach to error correction...',
    commit_hash: 'a1b2c3d',
    fork_count: 3,
    forked_from: null,
    commit_count: 4,
    score: { originality: 4, rigor: 3, completeness: 5, pedagogy: 4, impact: 3 },
    sink_eta: '2026-06-20T00:00:00Z',
    days_remaining: 12,
    sink_duration_days: 30,
    is_bookmarked: false,
    is_own_article: true,
    created_at: '2026-05-01T00:00:00Z',
    updated_at: '2026-06-05T00:00:00Z',
    ...overrides,
  }
}

describe('ArticleCard (Article Bar)', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders article title', () => {
    const wrapper = mount(ArticleCard, {
      props: { article: makeArticle() },
      global: { stubs: { 'router-link': RouterLinkStub } },
    })
    expect(wrapper.text()).toContain('Quantum Computing Foundations')
  })

  it('renders authors with clickable links', () => {
    const wrapper = mount(ArticleCard, {
      props: { article: makeArticle() },
      global: { stubs: { 'router-link': RouterLinkStub } },
    })
    expect(wrapper.text()).toContain('Alice Chen')
    expect(wrapper.text()).toContain('Bob Lee')
    const authorLinks = wrapper.findAll('a[href^="/user/"]')
    expect(authorLinks.length).toBeGreaterThanOrEqual(2)
  })

  it('renders content preview', () => {
    const wrapper = mount(ArticleCard, {
      props: { article: makeArticle() },
      global: { stubs: { 'router-link': RouterLinkStub } },
    })
    expect(wrapper.text()).toContain('fundamental principles')
  })

  it('renders 5-dim scores', () => {
    const wrapper = mount(ArticleCard, {
      props: { article: makeArticle() },
      global: { stubs: { 'router-link': RouterLinkStub } },
    })
    // ScoreBadges now shows icon + value (e.g. <Lightbulb/> 4)
    expect(wrapper.text()).toContain('4')
    expect(wrapper.text()).toContain('3')
    expect(wrapper.text()).toContain('5')
  })

  it('renders commit hash', () => {
    const wrapper = mount(ArticleCard, {
      props: { article: makeArticle() },
      global: { stubs: { 'router-link': RouterLinkStub } },
    })
    expect(wrapper.text()).toContain('a1b2c3d')
  })

  it('renders status badge (In Pool for sedimentation)', () => {
    const wrapper = mount(ArticleCard, {
      props: { article: makeArticle() },
      global: { stubs: { 'router-link': RouterLinkStub } },
    })
    expect(wrapper.text()).toMatch(/In Pool|sedimentation/)
  })

  it('renders sink progress bar for sedimentation status', () => {
    const wrapper = mount(ArticleCard, {
      props: { article: makeArticle() },
      global: { stubs: { 'router-link': RouterLinkStub } },
    })
    expect(wrapper.text()).toContain('12')
    expect(wrapper.text()).toContain('remaining')
    const progressBar = wrapper.find('progress, [role="progressbar"], .progress-bar, div[style*="width"]')
    expect(progressBar.exists()).toBe(true)
  })

  it('does not render progress bar for published status', () => {
    const wrapper = mount(ArticleCard, {
      props: { article: makeArticle({ status: 'published', days_remaining: null, sink_duration_days: null }) },
      global: { stubs: { 'router-link': RouterLinkStub } },
    })
    expect(wrapper.text()).not.toContain('remaining')
  })

  it('hides bookmark button on own article', () => {
    const wrapper = mount(ArticleCard, {
      props: { article: makeArticle({ is_own_article: true }) },
      global: { stubs: { 'router-link': RouterLinkStub } },
    })
    const bookmarkBtn = wrapper.find('button[aria-label*="bookmark" i]')
    expect(bookmarkBtn.exists()).toBe(false)
  })

  it('renders bookmark toggle button on other articles (authenticated)', () => {
    const userStore = useUserStore()
    userStore.viewer = { id: 'u-viewer', name: 'Viewer' } as any
    const wrapper = mount(ArticleCard, {
      props: { article: makeArticle({ is_own_article: false }) },
      global: { stubs: { 'router-link': RouterLinkStub } },
    })
    const bookmarkBtn = wrapper.find('button[aria-label*="bookmark" i]')
    expect(bookmarkBtn.exists()).toBe(true)
  })

  it('renders edit button when is_own_article is true', () => {
    const wrapper = mount(ArticleCard, {
      props: { article: makeArticle({ is_own_article: true }) },
      global: { stubs: { 'router-link': RouterLinkStub } },
    })
    const editBtn = wrapper.find('button[aria-label="Edit"]')
    expect(editBtn.exists()).toBe(true)
  })

  it('disables edit button when is_own_article is false', () => {
    const wrapper = mount(ArticleCard, {
      props: { article: makeArticle({ is_own_article: false }) },
      global: { stubs: { 'router-link': RouterLinkStub } },
    })
    const editBtn = wrapper.find('button[aria-label="Edit"]')
    expect(editBtn.exists()).toBe(true)
    expect(editBtn.attributes('disabled')).toBeDefined()
  })

  it('renders commit count badge when edited multiple times', () => {
    const wrapper = mount(ArticleCard, {
      props: { article: makeArticle({ commit_count: 4 }) },
      global: { stubs: { 'router-link': RouterLinkStub } },
    })
    expect(wrapper.text()).toMatch(/v4|v\s*4/)
  })

  it('renders forked badge when article is a fork', () => {
    const wrapper = mount(ArticleCard, {
      props: { article: makeArticle({ forked_from: 'art-0' }) },
      global: { stubs: { 'router-link': RouterLinkStub } },
    })
    expect(wrapper.text().toLowerCase()).toMatch(/fork/)
  })

  it('renders history link', () => {
    const wrapper = mount(ArticleCard, {
      props: { article: makeArticle() },
      global: { stubs: { 'router-link': RouterLinkStub } },
    })
    const historyLinks = wrapper.findAll('a[href*="history"]')
    expect(historyLinks.length).toBeGreaterThanOrEqual(1)
  })

  it('renders commit hash badge when hash is present', () => {
    const wrapper = mount(ArticleCard, {
      props: { article: makeArticle({ commit_hash: 'a1b2c3d4e5f6' }) },
      global: { stubs: { 'router-link': RouterLinkStub } },
    })
    expect(wrapper.text()).toContain('a1b2c3d')
  })

  it('hides commit hash badge when hash is empty', () => {
    const wrapper = mount(ArticleCard, {
      props: { article: makeArticle({ commit_hash: '' }) },
      global: { stubs: { 'router-link': RouterLinkStub } },
    })
    expect(wrapper.text()).not.toContain('a1b2c3d')
  })
})
