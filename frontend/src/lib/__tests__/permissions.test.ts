// SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
// SPDX-License-Identifier: CC-BY-NC-SA-4.0

import { describe, it, expect } from 'vitest'
import { articlePermissions, disabledReason } from '../permissions'
import type { ArticlePermissions } from '../permissions'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Shorthand: perms for (status, is_own_article, is_authenticated). */
function p(status: string, own: boolean, auth: boolean): ArticlePermissions {
  return articlePermissions({ status, is_own_article: own }, auth)
}

/** All permissions false. */
const ALL_FALSE: ArticlePermissions = {
  canEdit: false, canDelete: false, canRollback: false,
  canPublish: false, canExtendSink: false, canSync: false,
  canSelfReview: false, canFork: false, canBookmark: false,
  canDownload: false,
}

// ---------------------------------------------------------------------------
// Own article — 3 statuses
// ---------------------------------------------------------------------------

describe('own article', () => {
  it('draft: can edit/delete/rollback/publish/sync/self-review/download', () => {
    expect(p('draft', true, true)).toEqual({
      ...ALL_FALSE,
      canEdit: true, canDelete: true, canRollback: true,
      canPublish: true, canSync: true,
      canSelfReview: true,
      canDownload: true,
    })
  })

  it('sedimentation: can self-review/extend-sink/download, immutable otherwise', () => {
    expect(p('sedimentation', true, true)).toEqual({
      ...ALL_FALSE,
      canSelfReview: true,
      canExtendSink: true,
      canDownload: true,
    })
  })

  it('published: can edit/delete/rollback/publish/sync/fork/download', () => {
    expect(p('published', true, true)).toEqual({
      ...ALL_FALSE,
      canEdit: true, canDelete: true, canRollback: true,
      canPublish: true, canSync: true,
      canFork: true,
      canDownload: true,
    })
  })
})

// ---------------------------------------------------------------------------
// Not own — authenticated
// ---------------------------------------------------------------------------

describe('not own, authenticated', () => {
  it('draft: can bookmark (status not gated), nothing else', () => {
    expect(p('draft', false, true)).toEqual({
      ...ALL_FALSE,
      canBookmark: true, // bookmark doesn't gate on status
    })
  })

  it('sedimentation: can bookmark only', () => {
    expect(p('sedimentation', false, true)).toEqual({
      ...ALL_FALSE,
      canBookmark: true,
    })
  })

  it('published: can fork/bookmark/download', () => {
    expect(p('published', false, true)).toEqual({
      ...ALL_FALSE,
      canFork: true,
      canBookmark: true,
      canDownload: true,
    })
  })
})

// ---------------------------------------------------------------------------
// Not own — anonymous
// ---------------------------------------------------------------------------

describe('not own, anonymous', () => {
  it('draft: nothing', () => {
    expect(p('draft', false, false)).toEqual(ALL_FALSE)
  })

  it('sedimentation: nothing (no bookmark without auth)', () => {
    expect(p('sedimentation', false, false)).toEqual(ALL_FALSE)
  })

  it('published: can download only (fork/bookmark require auth)', () => {
    expect(p('published', false, false)).toEqual({
      ...ALL_FALSE,
      canDownload: true,
    })
  })
})

// ---------------------------------------------------------------------------
// Edge cases
// ---------------------------------------------------------------------------

describe('edge cases', () => {
  it('unknown status + own + auth: only download (author can always download)', () => {
    expect(p('retracted', true, true)).toEqual({
      ...ALL_FALSE,
      canDownload: true,
    })
  })

  it('unknown status + not own + auth: can bookmark, nothing else', () => {
    expect(p('retracted', false, true)).toEqual({
      ...ALL_FALSE,
      canBookmark: true, // bookmark doesn't gate on status
    })
  })

  it('unknown status + not own + anon: all false', () => {
    expect(p('retracted', false, false)).toEqual(ALL_FALSE)
  })
})

// ---------------------------------------------------------------------------
// disabledReason
// ---------------------------------------------------------------------------

describe('disabledReason', () => {
  const perms = p('draft', true, true)

  it('returns empty string for enabled actions', () => {
    expect(disabledReason(perms, 'canEdit')).toBe('')
    expect(disabledReason(perms, 'canPublish')).toBe('')
  })

  it('returns i18n key for disabled actions', () => {
    expect(disabledReason(perms, 'canFork')).toBe('perms.disabled.canFork')
    expect(disabledReason(perms, 'canBookmark')).toBe('perms.disabled.canBookmark')
  })
})
