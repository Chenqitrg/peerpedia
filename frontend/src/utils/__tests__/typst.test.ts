import { describe, it, expect } from 'vitest'
import { sanitizeTypstSvg } from '../typst'

describe('sanitizeTypstSvg', () => {
  it('strips white background rect with width="100%"', () => {
    const input = '<svg><rect width="100%" height="100%" fill="white"/><text>Hello</text></svg>'
    const output = sanitizeTypstSvg(input)
    expect(output).not.toContain('<rect')
    expect(output).toContain('<text>Hello</text>')
  })

  it('strips rect with fill="#ffffff"', () => {
    const input = '<svg><rect fill="#ffffff" width="100%"/><path d="M0,0"/></svg>'
    const output = sanitizeTypstSvg(input)
    expect(output).not.toContain('fill="#ffffff"')
    expect(output).toContain('<path')
  })

  it('preserves non-background SVG elements', () => {
    const input = '<svg><g><text>Title</text><path d="M0,0 L10,10"/><circle cx="5" cy="5" r="2"/></g></svg>'
    const output = sanitizeTypstSvg(input)
    expect(output).toContain('<text>Title</text>')
    expect(output).toContain('<path')
    expect(output).toContain('<circle')
  })

  it('returns unchanged SVG when no white rect exists', () => {
    const input = '<svg><text>Hello</text></svg>'
    expect(sanitizeTypstSvg(input)).toBe(input)
  })

  it('handles empty string', () => {
    expect(sanitizeTypstSvg('')).toBe('')
  })
})
