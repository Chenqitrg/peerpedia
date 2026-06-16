// SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
// SPDX-License-Identifier: CC-BY-NC-SA-4.0

// Backend-agnostic draft persistence.
//
// In Tauri mode: uses IPC to save/load drafts from local SQLite.
// In Web mode: uses REST API + localStorage fallback.
//
// EditorPage calls this single interface — no platform branching in component code.

import { useTauri } from './useTauri'
import type { Draft, DraftSummary } from './useTauri'
import apiClient from '../api/client'
import { v4 as uuidv4 } from 'uuid'

function draftStorageKey(accountId?: string): string {
  return accountId ? `peerpedia_draft_${accountId}` : 'peerpedia_draft'
}

interface PersistenceResult {
  id?: string
  account_id?: string
  title?: string
  content?: string
  format?: string
  commit_hash?: string
  updated_at?: string
  error?: string
  ok?: boolean
}

export function useDraftPersistence() {
  const tauri = useTauri()

  async function save(
    accountId: string,
    title: string,
    content: string,
    format: string,
    draftId?: string,
  ): Promise<PersistenceResult> {
    // In Tauri/dev-mock mode, always save to local mock storage first.
    if (tauri.isTauri.value || tauri.isBrowserLocal.value) {
      const result = await tauri.saveDraft({
        id: draftId || undefined,
        account_id: accountId,
        title,
        content,
        format,
      })

      if (!result) return { error: 'Tauri unavailable' }
      if ('error' in result) return result as PersistenceResult
      return result as Draft
    }

    // Web mode: REST API + localStorage backup.
    const storageKey = draftStorageKey(accountId)
    try {
      if (draftId) {
        // Update existing draft via PUT.
        const { data } = await apiClient.put(`/articles/${draftId}`, {
          title,
          content,
          commit_message: 'Save draft',
          publish: false,
        })
        localStorage.setItem(storageKey, JSON.stringify({
          id: data.id, title: data.title, content, format,
        }))
        return { id: data.id, title: data.title, content, format, commit_hash: data.commit_hash || '' }
      }

      // New draft: generate client UUID, create via POST.
      const clientId = uuidv4()
      const payload: Record<string, unknown> = {
        id: clientId,
        title,
        content,
        format,
        commit_message: 'Save draft',
        publish: false,
      }
      const { data } = await apiClient.post('/articles', payload)
      // Persist to localStorage as offline backup.
      localStorage.setItem(storageKey, JSON.stringify({
        id: data.id,
        title: data.title,
        content,
        format,
      }))
      return {
        id: data.id,
        title: data.title,
        content,
        format,
        commit_hash: (data as any).commit_hash || '',
      }
    } catch (e: unknown) {
      // Propagate the error to the caller — do NOT silently create a fake
      // local ID.  A fake ID causes downstream updateArticle calls to 404.
      throw e
    }
  }

  async function load(draftId: string, accountId?: string): Promise<PersistenceResult> {
    if (tauri.isTauri.value || tauri.isBrowserLocal.value) {
      const result = await tauri.getDraft({ id: draftId })
      if (!result) return { error: 'Tauri unavailable', content: '', format: 'markdown' }
      if ('error' in result) return { ...result as PersistenceResult, content: '', format: 'markdown' }
      return result as Draft
    }

    // Web mode: try REST source endpoint (returns content), fall back to localStorage.
    try {
      const { data: source } = await apiClient.get(`/articles/${draftId}/source`)
      return {
        id: draftId,
        title: '',
        content: source.content || '',
        format: source.format || 'markdown',
      }
    } catch {
      // Try localStorage fallback (scoped to user if accountId provided).
      const storageKey = draftStorageKey(accountId)
      const stored = localStorage.getItem(storageKey)
      if (stored) {
        try {
          return JSON.parse(stored) as PersistenceResult
        } catch {
          // Corrupt localStorage.
        }
      }
      return { id: draftId, title: '', content: '', format: 'markdown' }
    }
  }

  async function listDrafts(accountId: string): Promise<DraftSummary[]> {
    if (tauri.isTauri.value || tauri.isBrowserLocal.value) {
      const result = await tauri.listDrafts({ account_id: accountId })
      if (!result) return []
      if (Array.isArray(result)) return result as DraftSummary[]
      return []
    }

    // Web mode: REST fallback (returns flat array).
    try {
      const { data } = await apiClient.get('/articles', {
        params: { status: 'draft', author_id: accountId },
      })
      const list = Array.isArray(data)
        ? data
        : (data.articles || data.items || [])
      return list.map((item: Record<string, unknown>) => ({
        id: item.id as string,
        title: item.title as string,
        updated_at: item.updated_at as string,
      }))
    } catch {
      return []
    }
  }

  async function deleteDraft(draftId: string, accountId?: string): Promise<PersistenceResult> {
    if (tauri.isTauri.value || tauri.isBrowserLocal.value) {
      const result = await tauri.deleteDraft({ id: draftId })
      if (!result) return { error: 'Tauri unavailable' }
      if ('error' in result) return result as PersistenceResult
      return result as PersistenceResult
    }

    // Web mode: delete via REST.
    try {
      await apiClient.put(`/articles/${draftId}`, { publish: false })
      localStorage.removeItem(draftStorageKey(accountId))
      return { ok: true }
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e)
      return { error: message }
    }
  }

  return { save, load, listDrafts, deleteDraft }
}
