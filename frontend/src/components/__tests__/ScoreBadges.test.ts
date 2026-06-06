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
    it('renders all five dimensions with label:value format', () => {
      const wrapper = mountComponent()
      const text = wrapper.text()
      // The .full span is in the DOM but hidden via CSS max-width: 0.
      // text() returns the full unfolded content.
      expect(text).toContain('Originality')
      expect(text).toContain('Rigor')
      expect(text).toContain(':4')
      expect(text).toContain(':3')
      expect(text).toContain(':5')
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
      const dims = wrapper.findAll('.score-dim')
      expect(dims[0].classes()).toContain('text-accent')
      expect(dims[0].classes()).toContain('font-semibold')
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
      const firstDim = wrapper.findAll('.score-dim')[0]
      await firstDim.trigger('mouseenter')
      expect(wrapper.findComponent(StarRating).exists()).toBe(true)
    })

    it('hides StarRating on mouseleave', async () => {
      const wrapper = mountComponent({ editable: true })
      const firstDim = wrapper.findAll('.score-dim')[0]
      await firstDim.trigger('mouseenter')
      expect(wrapper.findComponent(StarRating).exists()).toBe(true)
      await firstDim.trigger('mouseleave')
      // Wait for the 100ms debounce
      await new Promise(r => setTimeout(r, 150))
      expect(wrapper.findComponent(StarRating).exists()).toBe(false)
    })

    it('emits update-score when star is clicked', async () => {
      const wrapper = mountComponent({ editable: true })
      const firstDim = wrapper.findAll('.score-dim')[0]
      await firstDim.trigger('mouseenter')
      // Click the 5th star to change rating from 4 to 5
      const stars = wrapper.findComponent(StarRating).findAll('[role="radio"]')
      await stars[4].trigger('click')
      expect(wrapper.emitted('update-score')).toBeTruthy()
      expect(wrapper.emitted('update-score')![0]).toEqual(['originality', 5])
    })

    it('only shows StarRating for the hovered dimension', async () => {
      const wrapper = mountComponent({ editable: true })
      const dims = wrapper.findAll('.score-dim')
      await dims[0].trigger('mouseenter')
      // Only one StarRating should be visible
      expect(wrapper.findAllComponents(StarRating).length).toBe(1)
      await dims[0].trigger('mouseleave')
      await new Promise(r => setTimeout(r, 150))
      await dims[2].trigger('mouseenter')
      expect(wrapper.findAllComponents(StarRating).length).toBe(1)
    })

    it('does nothing on mouseenter when score is null', async () => {
      const wrapper = mountComponent({ editable: true, score: null })
      const el = wrapper.find('.score-dim')
      // Null score means the element isn't rendered at all
      expect(el.exists()).toBe(false)
    })
  })
})
