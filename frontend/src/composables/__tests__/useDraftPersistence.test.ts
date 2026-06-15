// SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
// SPDX-License-Identifier: CC-BY-NC-SA-4.0

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useDraftPersistence } from '../useDraftPersistence'

// Mock useTauri to control platform mode
const mockTauriMethods = {
  isTauri: { value: false },
  isBrowserLocal: { value: false },
  saveDraft: vi.fn(),
  getDraft: vi.fn(),
  listDrafts: vi.fn(),
  deleteDraft: vi.fn(),
  getCachedArticle: vi.fn(),
}

vi.mock('../useTauri', () => ({
  useTauri: () => mockTauriMethods,
}))

// Mock axios for REST fallback — must include create() for apiClient.
const { mockPost, mockGet, mockPut } = vi.hoisted(() => {
  const mockPost = vi.fn()
  const mockGet = vi.fn()
  const mockPut = vi.fn()
  return { mockPost, mockGet, mockPut }
})

vi.mock('axios', () => {
  const noopInterceptor = { use: vi.fn(), eject: vi.fn(), clear: vi.fn() }
  return {
    default: {
      create: () => ({
        post: (...args: unknown[]) => mockPost(...args),
        get: (...args: unknown[]) => mockGet(...args),
        put: (...args: unknown[]) => mockPut(...args),
        interceptors: { request: noopInterceptor, response: noopInterceptor },
      }),
      post: (...args: unknown[]) => mockPost(...args),
      get: (...args: unknown[]) => mockGet(...args),
      put: (...args: unknown[]) => mockPut(...args),
    },
  }
})

describe('useDraftPersistence', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockTauriMethods.isTauri.value = false
    // Reset localStorage mock
    localStorage.clear()
  })

  describe('save', () => {
    it('calls Tauri saveDraft when isTauri is true', async () => {
      mockTauriMethods.isTauri.value = true
      mockTauriMethods.saveDraft.mockResolvedValue({
        id: 'draft-1',
        account_id: 'a1',
        title: 'My Draft',
        content: '# Hello',
        format: 'markdown',
        updated_at: '2026-06-06T00:00:00Z',
      })

      const { save } = useDraftPersistence()
      const result = await save('a1', 'My Draft', '# Hello', 'markdown')

      expect(mockTauriMethods.saveDraft).toHaveBeenCalledWith({
        account_id: 'a1',
        title: 'My Draft',
        content: '# Hello',
        format: 'markdown',
      })
      expect(result).toHaveProperty('id', 'draft-1')
      expect(result).not.toHaveProperty('error')
    })

    it('returns error when Tauri saveDraft fails', async () => {
      mockTauriMethods.isTauri.value = true
      mockTauriMethods.saveDraft.mockResolvedValue({ error: 'Disk full' })

      const { save } = useDraftPersistence()
      const result = await save('a1', 'Title', 'Content', 'markdown')

      expect(result).toHaveProperty('error', 'Disk full')
    })

    it('falls back to REST when isTauri is false', async () => {
      mockPost.mockResolvedValue({
        data: {
          id: 'web-draft-1',
          title: 'Web Draft',
          status: 'draft',
        },
      })

      const { save } = useDraftPersistence()
      const result = await save('a1', 'Web Draft', '# Web', 'markdown')

      // Should call the existing REST endpoint.
      expect(mockPost).toHaveBeenCalled()
      const callArgs = mockPost.mock.calls[0]
      expect(callArgs[0]).toContain('/articles')
      expect(result).toHaveProperty('id', 'web-draft-1')
    })

    it('throws on REST failure instead of returning fake ID', async () => {
      mockPost.mockRejectedValue(new Error('Network error'))

      const { save } = useDraftPersistence()
      await expect(save('a1', 'Web Draft', '# Web', 'markdown')).rejects.toThrow('Network error')

      // Verify no localStorage entry with fake ID was created
      const stored = localStorage.getItem('peerpedia_draft_a1')
      expect(stored).toBeNull()
    })

    it('fallback persists to localStorage in Web mode', async () => {
      mockPost.mockResolvedValue({
        data: { id: 'web-1', title: 'Draft', status: 'draft' },
      })

      const { save } = useDraftPersistence()
      await save('a1', 'Draft', '# Content', 'markdown')

      const stored = JSON.parse(localStorage.getItem('peerpedia_draft_a1') || '{}')
      expect(stored).toHaveProperty('title', 'Draft')
    })
  })

  describe('load', () => {
    it('calls Tauri getDraft when isTauri is true', async () => {
      mockTauriMethods.isTauri.value = true
      mockTauriMethods.getDraft.mockResolvedValue({
        id: 'draft-1',
        account_id: 'a1',
        title: 'Loaded',
        content: '# Hi',
        format: 'markdown',
        updated_at: '2026-06-06',
      })

      const { load } = useDraftPersistence()
      const result = await load('draft-1')

      expect(mockTauriMethods.getDraft).toHaveBeenCalledWith({ id: 'draft-1' })
      expect(result).toHaveProperty('title', 'Loaded')
    })

    it('falls back to REST when isTauri is false', async () => {
      mockGet.mockResolvedValue({
        data: { content: '# Web', format: 'markdown' },
      })

      const { load } = useDraftPersistence()
      const result = await load('web-1')

      expect(mockGet).toHaveBeenCalled()
      const callUrl = mockGet.mock.calls[0][0]
      expect(callUrl).toContain('/source')
      expect(result).toHaveProperty('content', '# Web')
      expect(result).toHaveProperty('format', 'markdown')
    })

    it('falls back to localStorage when REST fails', async () => {
      mockGet.mockRejectedValue(new Error('Network error'))
      localStorage.setItem('peerpedia_draft', JSON.stringify({
        id: 'local-1',
        title: 'Local Draft',
        content: '# Local',
        format: 'markdown',
      }))

      const { load } = useDraftPersistence()
      const result = await load('local-1')

      expect(result).toHaveProperty('title', 'Local Draft')
    })

    it('returns empty draft when all sources fail', async () => {
      mockGet.mockRejectedValue(new Error('Network error'))
      localStorage.clear()

      const { load } = useDraftPersistence()
      const result = await load('nonexistent')

      expect(result).toHaveProperty('content', '')
      expect(result).toHaveProperty('format', 'markdown')
    })
  })

  describe('listDrafts', () => {
    it('calls Tauri listDrafts when isTauri is true', async () => {
      mockTauriMethods.isTauri.value = true
      mockTauriMethods.listDrafts.mockResolvedValue([
        { id: 'd1', title: 'First', updated_at: '2026-01-01' },
      ])

      const { listDrafts } = useDraftPersistence()
      const result = await listDrafts('a1')

      expect(mockTauriMethods.listDrafts).toHaveBeenCalledWith({ account_id: 'a1' })
      expect(result).toHaveLength(1)
    })
  })

  describe('deleteDraft', () => {
    it('calls Tauri deleteDraft when isTauri is true', async () => {
      mockTauriMethods.isTauri.value = true
      mockTauriMethods.deleteDraft.mockResolvedValue({ ok: true })

      const { deleteDraft } = useDraftPersistence()
      const result = await deleteDraft('draft-1')

      expect(mockTauriMethods.deleteDraft).toHaveBeenCalledWith({ id: 'draft-1' })
      expect(result).toEqual({ ok: true })
    })
  })
})
