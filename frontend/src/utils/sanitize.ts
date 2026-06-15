import DOMPurify from 'dompurify'

/**
 * Sanitize user-generated HTML before rendering via v-html.
 *
 * Strips script tags, event handlers (onerror, onload, …),
 * javascript: URLs, and other XSS vectors while preserving
 * safe formatting elements and KaTeX markup.
 */
export function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html, {
    USE_PROFILES: { html: true },
    ALLOWED_URI_REGEXP:
      /^(?:(?:https?|mailto|ftp|data):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i,
  })
}
