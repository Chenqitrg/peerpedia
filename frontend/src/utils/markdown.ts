// Client-side Markdown → HTML compilation with KaTeX math support.
//
// Ports the _protect_math → _render_markdown → _restore_math pattern
// from core/peerpedia_core/storage/compiler.py to TypeScript.
//
// KaTeX was always client-side (utils/math.ts + katex npm package).
// This module replaces the server's Python `markdown` library step.
//
// Flow:
//   markdown → protect math → marked.parse() → restore math →
//   renderMathInHtml() → final HTML

import { marked } from 'marked'
import { renderMathInHtml } from './math'

const PLACEHOLDER_PREFIX = 'PEERPEDIA_MATH_'

/**
 * Compile a markdown string to HTML, with KaTeX math rendering.
 *
 * Math expressions ($...$ inline, $$...$$ display) are protected from
 * Markdown parsing (so underscores etc. inside math aren't interpreted
 * as Markdown emphasis), then rendered via KaTeX.
 */
export function parseMarkdown(source: string): string {
  // Step 1: Protect math expressions with placeholders.
  const { protectedText, placeholders } = protectMath(source)

  // Step 2: Render Markdown → HTML (math placeholders pass through untouched).
  const html = marked.parse(protectedText, {
    breaks: false,
    gfm: true,
  }) as string

  // Step 3: Restore math placeholders as KaTeX-compatible spans.
  const withMath = restoreMath(html, placeholders)

  // Step 4: Render KaTeX math from span-wrapped expressions.
  return renderMathInHtml(withMath)
}

interface PlaceholderMap {
  [placeholder: string]: string
}

/**
 * Protect math expressions from Markdown parsing by replacing them
 * with unique placeholders. Handles $$ display math and $ inline math.
 */
function protectMath(text: string): { protectedText: string; placeholders: PlaceholderMap } {
  const placeholders: PlaceholderMap = {}
  let counter = 0

  function replaceBlock(_match: string, inner: string): string {
    const key = `${PLACEHOLDER_PREFIX}D${counter}`
    placeholders[key] = `$$${inner}$$`
    counter++
    return key
  }

  function replaceInline(_match: string, inner: string): string {
    const key = `${PLACEHOLDER_PREFIX}I${counter}`
    placeholders[key] = `$${inner}$`
    counter++
    return key
  }

  // Display math first ($$ must be handled before $ to avoid conflict).
  let result = text.replace(/\$\$([\s\S]+?)\$\$/g, replaceBlock)
  // Inline math: $...$ (single $ not adjacent to another $).
  result = result.replace(/(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)/g, replaceInline)

  return { protectedText: result, placeholders }
}

/**
 * Restore math placeholders, wrapping them in KaTeX-compatible <span> tags.
 * The span format matches what renderMathInHtml() in math.ts expects.
 */
function restoreMath(html: string, placeholders: PlaceholderMap): string {
  // Sort by key length descending so longer keys match first (D10 before D1).
  const keys = Object.keys(placeholders).sort((a, b) => b.length - a.length)
  let result = html
  for (const key of keys) {
    const math = placeholders[key]
    if (key.includes(`${PLACEHOLDER_PREFIX}D`)) {
      result = result.replace(key, `<span class="katex-display">${math}</span>`)
    } else {
      result = result.replace(key, `<span class="katex-inline">${math}</span>`)
    }
  }
  return result
}
