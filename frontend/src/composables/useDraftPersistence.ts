// Backend-agnostic draft persistence.
//
// In Tauri mode: uses IPC to save/load drafts from local SQLite.
// In Web mode: uses REST API + localStorage fallback.
//
// EditorPage calls this single interface — no platform branching in component code.

import { useTauri } from './useTauri'
import type { Draft, DraftSummary } from './useTauri'
import axios from 'axios'

const LOCAL_STORAGE_KEY = 'peerpedia_draft'
const API_BASE = '/api/v1'

interface PersistenceResult {
  id?: string
  account_id?: string
  title?: string
  content?: string
  format?: string
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
    if (tauri.isTauri.value) {
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
    try {
      if (draftId) {
        // Update existing draft via PUT.
        const { data } = await axios.put(`${API_BASE}/articles/${draftId}`, {
          title,
          content,
          commit_message: 'Save draft',
          publish: false,
        })
        localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify({
          id: data.id, title: data.title, content, format,
        }))
        return { id: data.id, title: data.title, content, format }
      }

      // New draft: create via POST.
      const payload: Record<string, unknown> = {
        title,
        content,
        format,
        commit_message: 'Save draft',
        publish: false,
        authors: [accountId],
        self_review: { originality: 0, rigor: 0, completeness: 0, pedagogy: 0, impact: 0 },
      }
      const { data } = await axios.post(`${API_BASE}/articles`, payload)
      // Persist to localStorage as offline backup.
      localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify({
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
      }
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e)
      // Fallback: save to localStorage only.
      const localDraft = {
        id: draftId || `local-${Date.now()}`,
        title,
        content,
        format,
        updated_at: new Date().toISOString(),
      }
      localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(localDraft))
      return { ...localDraft, error: message }
    }
  }

  async function load(draftId: string): Promise<PersistenceResult> {
    if (tauri.isTauri.value) {
      const result = await tauri.getDraft({ id: draftId })
      if (!result) return { error: 'Tauri unavailable', content: '', format: 'markdown' }
      if ('error' in result) return { ...result as PersistenceResult, content: '', format: 'markdown' }
      return result as Draft
    }

    // Web mode: try REST source endpoint (returns content), fall back to localStorage.
    try {
      const { data: source } = await axios.get(`${API_BASE}/articles/${draftId}/source`)
      return {
        id: draftId,
        title: '',
        content: source.content || '',
        format: source.format || 'markdown',
      }
    } catch {
      // Try localStorage fallback.
      const stored = localStorage.getItem(LOCAL_STORAGE_KEY)
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
    if (tauri.isTauri.value) {
      const result = await tauri.listDrafts({ account_id: accountId })
      if (!result) return []
      if (Array.isArray(result)) return result as DraftSummary[]
      return []
    }

    // Web mode: REST fallback (returns flat array).
    try {
      const { data } = await axios.get(`${API_BASE}/articles`, {
        params: { status: 'draft', author_id: accountId },
      })
      const list = Array.isArray(data) ? data : (data.items || [])
      return list.map((item: Record<string, unknown>) => ({
        id: item.id as string,
        title: item.title as string,
        updated_at: item.updated_at as string,
      }))
    } catch {
      return []
    }
  }

  async function deleteDraft(draftId: string): Promise<PersistenceResult> {
    if (tauri.isTauri.value) {
      const result = await tauri.deleteDraft({ id: draftId })
      if (!result) return { error: 'Tauri unavailable' }
      if ('error' in result) return result as PersistenceResult
      return result as PersistenceResult
    }

    // Web mode: delete via REST.
    try {
      await axios.put(`${API_BASE}/articles/${draftId}`, { publish: false })
      localStorage.removeItem(LOCAL_STORAGE_KEY)
      return { ok: true }
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e)
      return { error: message }
    }
  }

  return { save, load, listDrafts, deleteDraft }
}
