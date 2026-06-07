import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import ScoreBadges from '../ScoreBadges.vue'
import StarRating from '../StarRating.vue'

const i18n = createI18n({
  legacy: false,
  locale: 'en-US',
  messages: { 'en-US': { article: { scores: 'Scores' } } },
})

const SAMPLE_SCORE = { originality: 4, rigor: 3, completeness: 3, pedagogy: 3, impact: 5 }

function mountComponent(props = {}) {
  return mount(ScoreBadges, {
    props: { score: SAMPLE_SCORE, ...props },
    global: { plugins: [i18n] },
  })
}

describe('ScoreBadges', () => {
  describe('read-only mode (default)', () => {
    it('renders all five dimensions with icon and value', () => {
      const wrapper = mountComponent()
      const text = wrapper.text()
      // Icons replace the old O:/R:/C: text — values should be present
      expect(text).toContain('4')
      expect(text).toContain('3')
      expect(text).toContain('5')
      // Should have 5 icon components (Lightbulb, FlaskConical, CheckCheck, BookOpen, TrendingUp)
      expect(wrapper.findAll('svg').length).toBeGreaterThanOrEqual(5)
    })

    it('shows "Scores" label when showLabel is true', () => {
      const wrapper = mountComponent({ showLabel: true })
      expect(wrapper.text()).toContain('Scores')
    })

    it('renders dash when score is null', () => {
      const wrapper = mountComponent({ score: null })
      expect(wrapper.text()).toBe('—')
    })

    it('highlights originality when highlightFirst is true', () => {
      const wrapper = mountComponent({ highlightFirst: true })
      // First dimension span should have text-accent class
      const spans = wrapper.findAll('span')
      const accentSpans = spans.filter(s => s.classes().includes('text-accent'))
      expect(accentSpans.length).toBeGreaterThan(0)
    })

    it('does not render StarRating in read-only mode', () => {
      const wrapper = mountComponent()
      expect(wrapper.findComponent(StarRating).exists()).toBe(false)
    })
  })

  describe('editable mode', () => {
    it('renders scores without StarRating initially', () => {
      const wrapper = mountComponent({ editable: true })
      expect(wrapper.findComponent(StarRating).exists()).toBe(false)
    })

    it('shows StarRating on mouseenter over a dimension', async () => {
      const wrapper = mountComponent({ editable: true })
      // Find all dimension containers by looking for spans with cursor-default
      const dims = wrapper.findAll('.cursor-default')
      expect(dims.length).toBeGreaterThan(0)
      await dims[0].trigger('mouseenter')
      expect(wrapper.findComponent(StarRating).exists()).toBe(true)
    })

    it('hides StarRating on mouseleave', async () => {
      const wrapper = mountComponent({ editable: true })
      const dims = wrapper.findAll('.cursor-default')
      await dims[0].trigger('mouseenter')
      expect(wrapper.findComponent(StarRating).exists()).toBe(true)
      await dims[0].trigger('mouseleave')
      // Wait for the 100ms debounce
      await new Promise(r => setTimeout(r, 150))
      expect(wrapper.findComponent(StarRating).exists()).toBe(false)
    })

    it('emits update-score when star is clicked', async () => {
      const wrapper = mountComponent({ editable: true })
      const dims = wrapper.findAll('.cursor-default')
      await dims[0].trigger('mouseenter')
      // Click the 5th star to change rating from 4 to 5
      const stars = wrapper.findComponent(StarRating).findAll('[role="radio"]')
      await stars[4].trigger('click')
      expect(wrapper.emitted('update-score')).toBeTruthy()
      expect(wrapper.emitted('update-score')![0]).toEqual(['originality', 5])
    })

    it('only shows StarRating for the hovered dimension', async () => {
      const wrapper = mountComponent({ editable: true })
      const dims = wrapper.findAll('.cursor-default')
      await dims[0].trigger('mouseenter')
      expect(wrapper.findAllComponents(StarRating).length).toBe(1)
      await dims[0].trigger('mouseleave')
      await new Promise(r => setTimeout(r, 150))
      await dims[2].trigger('mouseenter')
      expect(wrapper.findAllComponents(StarRating).length).toBe(1)
    })

    it('does nothing on mouseenter when score is null', async () => {
      const wrapper = mountComponent({ editable: true, score: null })
      // Null score means no dimensions rendered at all
      expect(wrapper.find('svg').exists()).toBe(false)
    })
  })
})
