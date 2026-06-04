import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import StarRating from '../StarRating.vue'

describe('StarRating', () => {
  it('renders 5 stars', () => {
    const wrapper = mount(StarRating, { props: { modelValue: 0 } })
    const stars = wrapper.findAll('.star-btn')
    expect(stars).toHaveLength(5)
  })

  it('clicking a star sets the value', async () => {
    const wrapper = mount(StarRating, { props: { modelValue: 0 } })
    const stars = wrapper.findAll('.star-btn')
    await stars[2].trigger('click')
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')![0]).toEqual([3])
  })

  it('highlights stars up to the selected value', () => {
    const wrapper = mount(StarRating, { props: { modelValue: 3 } })
    const stars = wrapper.findAll('.star-btn')
    expect(stars[0].classes()).toContain('star-filled')
    expect(stars[1].classes()).toContain('star-filled')
    expect(stars[2].classes()).toContain('star-filled')
    expect(stars[3].classes()).not.toContain('star-filled')
    expect(stars[4].classes()).not.toContain('star-filled')
  })
})
