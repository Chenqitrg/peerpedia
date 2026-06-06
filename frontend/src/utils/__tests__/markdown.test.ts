import { describe, it, expect } from 'vitest'
import { parseMarkdown } from '../markdown'

describe('parseMarkdown', () => {
  it('converts basic markdown to HTML', () => {
    const result = parseMarkdown('# Hello')
    expect(result).toContain('<h1')
    expect(result).toContain('Hello')
  })

  it('converts bold and italic', () => {
    const result = parseMarkdown('**bold** and *italic*')
    expect(result).toContain('<strong>bold</strong>')
    expect(result).toContain('<em>italic</em>')
  })

  it('renders inline math with KaTeX', () => {
    const result = parseMarkdown('The formula $x^2 + y^2 = z^2$ is known')
    // KaTeX renders to spans with class "katex"
    expect(result).toContain('katex')
    expect(result).not.toContain('$x^2')
  })

  it('renders display math with KaTeX', () => {
    const result = parseMarkdown('$$\n\\int_0^\\infty e^{-x} dx = 1\n$$')
    // Display math gets katex-display class
    expect(result).toContain('katex-display')
    expect(result).toContain('katex')
  })

  it('does not mangle underscores inside math', () => {
    // Underscores inside $...$ should survive as math, not become <em> tags
    const result = parseMarkdown('The set $S_n = \\{x_1, x_2, \\dots, x_n\\}$ is finite')
    expect(result).not.toContain('<em>')
    expect(result).toContain('katex')
  })

  it('handles fenced code blocks', () => {
    const result = parseMarkdown('```js\nconst x = 1;\n```')
    expect(result).toContain('<code')
    expect(result).toContain('const x = 1')
  })

  it('handles tables', () => {
    const result = parseMarkdown('| A | B |\n| - | - |\n| 1 | 2 |')
    expect(result).toContain('<table')
    expect(result).toContain('<td>1</td>')
  })

  it('handles mixed content: text + math + code', () => {
    const result = parseMarkdown(
      '# Section\n\nSome text with $\\alpha$ math.\n\n```python\nprint("hello")\n```\n\nMore text.',
    )
    expect(result).toContain('<h1')
    expect(result).toContain('katex')
    expect(result).toContain('<code')
  })

  it('returns empty string for empty input', () => {
    const result = parseMarkdown('')
    expect(result).toBe('')
  })

  it('does not treat dollar amounts as math', () => {
    // Single $ followed by digits and no closing $ should stay as text.
    // The regex requires a matching pair: $...$
    const result = parseMarkdown('It costs $50 dollars.')
    expect(result).not.toContain('katex')
    expect(result).toContain('$50')
  })
})
