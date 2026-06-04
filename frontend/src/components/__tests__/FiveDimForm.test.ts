import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import FiveDimForm from '../FiveDimForm.vue'

describe('FiveDimForm', () => {
  it('renders 5 dimension labels', () => {
    const wrapper = mount(FiveDimForm, { props: { modelValue: { originality: 0, rigor: 0, completeness: 0, pedagogy: 0, impact: 0 } } })
    const labels = wrapper.findAll('.dimension-label')
    expect(labels).toHaveLength(5)
    expect(labels[0].text()).toContain('Originality')
    expect(labels[1].text()).toContain('Rigor')
    expect(labels[2].text()).toContain('Completeness')
    expect(labels[3].text()).toContain('Pedagogy')
    expect(labels[4].text()).toContain('Impact')
  })

  it('emits update:modelValue when a star is clicked', async () => {
    const wrapper = mount(FiveDimForm, { props: { modelValue: { originality: 0, rigor: 0, completeness: 0, pedagogy: 0, impact: 0 } } })
    const stars = wrapper.findAll('.star-btn')
    await stars[2].trigger('click')
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')![0][0]).toHaveProperty('originality', 3)
  })
})
