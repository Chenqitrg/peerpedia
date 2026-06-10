/**
 * Sanitize Typst-compiled SVG for dark-theme display.
 * - Strips root width/height attrs so CSS can drive responsive sizing
 * - Strips white/opaque background <rect> elements that clash with dark theme
 */
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
    // Remove white-background rect elements.
    // Handles self-closing (<rect …/>) and explicit close (<rect …></rect>).
    .replace(
      /<rect\b[^>]*\bfill\s*=\s*["']\s*(?:white|#fff(?:fff)?|rgb\(\s*255\s*,\s*255\s*,\s*255\s*\))\s*["'][^>]*\/?>\s*(?:<\/rect>)?/gi,
      '',
    )
}
