import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import RadarChart from '../RadarChart.vue'

describe('RadarChart', () => {
  const scores = { originality: 5, rigor: 4, completeness: 3, pedagogy: 5, impact: 4 }

  it('renders SVG element', () => {
    const wrapper = mount(RadarChart, { props: { scores } })
    expect(wrapper.find('svg').exists()).toBe(true)
  })

  it('renders 5 axis labels', () => {
    const wrapper = mount(RadarChart, { props: { scores } })
    const labels = wrapper.findAll('.axis-label')
    expect(labels).toHaveLength(5)
    expect(labels[0].text()).toContain('Originality')
  })
})
