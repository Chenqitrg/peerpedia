// SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
// SPDX-License-Identifier: CC-BY-NC-SA-4.0

/**
 * Frontend permission module — 1:1 mirror of ``core/peerpedia_core/policies/articles.py``.
 *
 * Every ``assert_can_*`` in the backend policy maps to a ``can*`` boolean here.
 * Components call ``articlePermissions()`` instead of inline ``is_own_article &&
 * status === '...'`` checks.
 */

export interface ArticlePermissions {
  canEdit: boolean
  canDelete: boolean
  canRollback: boolean
  canPublish: boolean
  canExtendSink: boolean
  canSync: boolean
  canSelfReview: boolean
  canFork: boolean
  canBookmark: boolean
  canDownload: boolean
}

/**
 * Compute article-level permissions from status, ownership, and auth state.
 */
export function articlePermissions(
  article: { status: string; is_own_article: boolean },
  is_authenticated: boolean,
): ArticlePermissions {
  const own = article.is_own_article
  const auth = is_authenticated
  const s = article.status

  return {
    // Write — author-only, status-gated (matches _WRITABLE_STATUSES)
    canEdit:        own && (s === "draft" || s === "published"),
    canDelete:      own && (s === "draft" || s === "published"),
    canRollback:    own && (s === "draft" || s === "published"),
    canPublish:     own && (s === "draft" || s === "published"),
    canSync:        own && (s === "draft" || s === "published"),

    // Extend sink — author-only, sedimentation only
    canExtendSink:  own && s === "sedimentation",

    // Self-review — author-only, draft + sedimentation
    canSelfReview:  own && (s === "draft" || s === "sedimentation"),

    // Fork — authenticated + published only (duplicate check server-side)
    canFork:        auth && s === "published",

    // Bookmark — authenticated + not own article
    canBookmark:    auth && !own,

    // Download — published (anyone) OR author (any status)
    canDownload:    s === "published" || own,
  }
}

/** Action names used as keys into ``ArticlePermissions``. */
export type ArticleAction = keyof ArticlePermissions

/**
 * Return an i18n key describing why *action* is disabled, or ``''`` if allowed.
 *
 * The caller wraps with ``t()``: ``:data-tooltip="t(disabledReason(perms, 'canEdit'))"``
 */
export function disabledReason(perms: ArticlePermissions, action: ArticleAction): string {
  if (perms[action]) return ""
  // i18n keys — add translations in the locale files.
  return `perms.disabled.${action}`
}
