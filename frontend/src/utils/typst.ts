/**
 * Sanitize Typst-compiled SVG for dark-theme display.
 * - Strips root width/height attrs so CSS can drive responsive sizing
 * - Strips Typst's full-page white background (typst-shape path or rect)
 * - Inverts default black text (#000000) to the project ink color
 *
 * NOTE: only affects inline SVG preview. PDF output is compiled
 * separately via `typst compile --format pdf` and never touched.
 */

/** Project text-primary per MASTER.md — 13:1 contrast on #0d1117. */
const INK = '#e6edf3'

export function sanitizeTypstSvg(svg: string): string {
  return svg
    // Remove root SVG width/height attributes for responsive sizing.
    // Keep viewBox so the SVG scales proportionally.
    .replace(/<svg([^>]*?)>/i, (_, attrs: string) => {
      const cleaned = attrs
        .replace(/\s+width\s*=\s*"[^"]*"/i, '')
        .replace(/\s+height\s*=\s*"[^"]*"/i, '')
      return `<svg${cleaned}>`
    })
    // Remove Typst's page background — a <path> with class="typst-shape"
    // and white fill. Always the first element after <svg>; draws the
    // full page rectangle via path commands.
    .replace(
      /<path\b[^>]*\bclass\s*=\s*["']typst-shape["'][^>]*\bfill\s*=\s*["']\s*#(?:fff(?:fff)?|FFF(?:FFF)?)\s*["'][^>]*\/>/g,
      '',
    )
    // Fallback: remove any <rect> with white fill (older Typst, or
    // alternative SVG generators).
    .replace(
      /<rect\b[^>]*\bfill\s*=\s*["']\s*(?:white|#fff(?:fff)?|rgb\(\s*255\s*,\s*255\s*,\s*255\s*\))\s*["'][^>]*\/?>\s*(?:<\/rect>)?/gi,
      '',
    )
    // Invert Typst's default black text to ink so text is readable
    // against the dark page background (#0d1117).
    .replace(
      /fill\s*=\s*["']\s*#000(?:000)?\s*["']/gi,
      `fill="${INK}"`,
    )
}
