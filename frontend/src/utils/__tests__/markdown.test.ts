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

  // ── Regression: specific math patterns the user reported ──────────────

  it('renders simple display math $$xy$$ correctly', () => {
    const result = parseMarkdown('$$xy$$')
    expect(result).toContain('katex-display')
    // No raw $$ delimiters should leak into output
    expect(result).not.toMatch(/<span[^>]*katex-display[^>]*>\$\$/)
  })

  it('renders display math with spaces $$ x + y $$ correctly', () => {
    const result = parseMarkdown('$$ x + y $$')
    expect(result).toContain('katex-display')
    expect(result).not.toContain('$$')
  })

  it('renders multiline inline math $\\nx\\n$ correctly', () => {
    // Inline math spanning newlines — the dot in .+? doesn't cross lines
    const result = parseMarkdown('$\nx\n$')
    // Should contain katex (rendered math), not raw dollar signs
    expect(result).toContain('katex')
  })

  it('renders display math with surrounding text', () => {
    const result = parseMarkdown('Here is an equation\n\n$$\nx^2 + y^2 = z^2\n$$\n\nNice!')
    expect(result).toContain('katex-display')
    expect(result).not.toContain('$$')
  })

  it('renders $$x^2$$ as display math', () => {
    const result = parseMarkdown('$$x^2$$')
    // Use real parseMarkdown (not inline test) — returned HTML must be
    // fully KaTeX-rendered, no raw $ leaking anywhere.
    expect(result).toContain('katex-display')
    expect(result).toContain('katex')
    // No raw $ inside katex-display span (= renderMathInHtml failed)
    expect(result).not.toMatch(/<span[^>]*katex-display[^>]*>\$/)
    // No raw $ anywhere in output (= $$ became $ via String.replace)
    expect(result).not.toMatch(/(?<!\\)\$(?!\$)/)
  })

  it('$$x^2$$ restoreMath preserves $$', async () => {
    // Regression: String.replace() interprets $$ as literal $ in the
    // replacement string. Verify restoreMath uses split/join instead.
    const result = parseMarkdown('$$x^2$$')
    expect(result).toContain('katex-display')
    expect(result).toContain('katex')
    // No raw $ in the output
    expect(result).not.toMatch(/(?<!\\)\$(?!\$)/)
  })

  it('renders $$x^2 + y^2 = z^2$$ as display math', () => {
    const result = parseMarkdown('$$\nx^2 + y^2 = z^2\n$$')
    expect(result).toContain('katex-display')
    expect(result).toContain('katex')
  })

  it('placeholder survives marked parsing (no underscore emphasis)', () => {
    // Regression: marked's GFM interpreted _MATH_ in PEERPEDIA_MATH_D0 as
    // emphasis, breaking the placeholder. Now uses PEERPEDIA-MATH-D0 (hyphens).
    const result = parseMarkdown('$$x$$')
    expect(result).toContain('katex-display')
    expect(result).toContain('katex')
  })

  it('parseMarkdown renders markdown headings (# → <h1>)', () => {
    const result = parseMarkdown('# Hello World')
    expect(result).toContain('<h1')
    expect(result).toContain('Hello World')
  })

  it('renderMathInHtml does NOT render markdown (must use parseMarkdown)', async () => {
    // Regression: ArticlePage line 169 was calling renderMathInHtml on raw
    // markdown. renderMathInHtml only processes katex spans — it won't
    // convert # to <h1> or $$ to display math. parseMarkdown must be used.
    const { renderMathInHtml } = await import('../math')
    const raw = renderMathInHtml('# Hello\n\n$$x^2$$')
    // renderMathInHtml leaves raw markdown untouched — no <h1>, no katex
    expect(raw).not.toContain('<h1')
    expect(raw).not.toContain('katex')
    // parseMarkdown handles everything
    const cooked = parseMarkdown('# Hello\n\n$$x^2$$')
    expect(cooked).toContain('<h1')
    expect(cooked).toContain('katex-display')
  })

  it('renders multiple display math blocks independently', () => {
    const result = parseMarkdown('$$\na = 1\n$$\n\n$$\nb = 2\n$$')
    const displayCount = (result.match(/katex-display/g) || []).length
    expect(displayCount).toBe(2)
  })
})
