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

  it('strips width and height from root svg tag for responsive sizing', () => {
    const input = '<svg width="595.27pt" height="841.89pt" viewBox="0 0 595.27 841.89"><text>Hello</text></svg>'
    const output = sanitizeTypstSvg(input)
    expect(output).not.toContain('width=')
    expect(output).not.toContain('height=')
    expect(output).toContain('viewBox=')
    expect(output).toContain('<text>Hello</text>')
  })

  it('strips rect with closing tag (non-self-closing)', () => {
    const input = '<svg><rect width="100%" height="100%" fill="white"></rect><text>Hello</text></svg>'
    const output = sanitizeTypstSvg(input)
    expect(output).not.toContain('<rect')
    expect(output).toContain('<text>Hello</text>')
  })

  // ── Real Typst SVG output ──────────────────────────────────────────

  it('strips Typst page-background path (typst-shape + #ffffff) + inverts text', () => {
    // Exact output from `typst compile --format svg` for "= test"
    const input =
      '<svg class="typst-doc" viewBox="0 0 595.28 841.89" width="595.28pt" height="841.89pt" xmlns="http://www.w3.org/2000/svg">' +
      '<path class="typst-shape" fill="#ffffff" fill-rule="nonzero" d="M 0 0v 841.89 h 595.28 v -841.89 Z "/>' +
      '<g><g class="typst-text"><use xlink:href="#g1" x="0" y="0" fill="#000000"/></g></g>' +
      '</svg>'
    const output = sanitizeTypstSvg(input)
    // Page background must be gone
    expect(output).not.toContain('typst-shape')
    expect(output).not.toContain('#ffffff')
    // Content survives, black text inverted to ink
    expect(output).toContain('typst-text')
    expect(output).not.toContain('#000000')
    expect(output).toContain('#e6edf3')
    // viewBox preserved for proportional scaling
    expect(output).toContain('viewBox=')
  })

  it('e2e: real Typst SVG — no white fill, text readable on dark theme', () => {
    // Full real output from `typst compile --format svg` for "= test"
    const input =
      '<svg class="typst-doc" viewBox="0 0 595.2755905511812 841.8897637795276" width="595.2755905511812pt" height="841.8897637795276pt" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:h5="http://www.w3.org/1999/xhtml">\n' +
      '    <path class="typst-shape" fill="#ffffff" fill-rule="nonzero" d="M 0 0v 841.8898 h 595.2756 v -841.8898 Z "/>\n' +
      '    <g>\n' +
      '        <g class="typst-group" transform="matrix(1 0 0 1 70.86614173228347 70.86614173228347)">\n' +
      '            <g>\n' +
      '                <g class="typst-text" transform="matrix(1 0 0 -1 0 9.933)">\n' +
      '                    <use xlink:href="#g1" x="0" y="0" fill="#000000" fill-rule="nonzero"/>\n' +
      '                    <use xlink:href="#g2" x="5.51" y="0" fill="#000000" fill-rule="nonzero"/>\n' +
      '                    <use xlink:href="#g3" x="13.04" y="0" fill="#000000" fill-rule="nonzero"/>\n' +
      '                    <use xlink:href="#g1" x="19.62" y="0" fill="#000000" fill-rule="nonzero"/>\n' +
      '                </g>\n' +
      '            </g>\n' +
      '        </g>\n' +
      '    </g>\n' +
      '</svg>'
    const output = sanitizeTypstSvg(input)
    // No white fills anywhere
    expect(output).not.toMatch(/#ffffff|#FFFFFF|#fff|#FFF/)
    // No black text — all inverted to ink (#e6edf3 per MASTER.md, 13:1)
    expect(output).not.toContain('#000000')
    expect(output).toContain('#e6edf3')
    // Content intact
    expect(output).toContain('typst-text')
    // Width/height stripped for responsive
    expect(output).not.toMatch(/\bwidth\s*=/i)
    expect(output).not.toMatch(/\bheight\s*=/i)
    expect(output).toContain('viewBox=')
  })
})
