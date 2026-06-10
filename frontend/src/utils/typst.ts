/**
 * Sanitize Typst-compiled SVG for dark-theme display.
 * - Strips white/opaque background <rect> elements that clash with dark theme
 * - The responsive sizing (width: 100%, height: auto) is handled by CSS
 */
export function sanitizeTypstSvg(svg: string): string {
  return svg
    // Remove full-width background rects (Typst's default page background)
    .replace(/<rect[^>]*width="100%"[^>]*\/>/gi, '')
    // Remove explicitly white-filled rects
    .replace(/<rect[^>]*fill=["'](?:white|#fff(?:fff)?)["'][^>]*\/>/gi, '')
}
