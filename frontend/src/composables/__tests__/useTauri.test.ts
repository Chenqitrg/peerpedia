import { describe, it, expect, beforeEach } from 'vitest'
import { useTauri } from '../useTauri'

describe('useTauri', () => {
  beforeEach(() => {
    delete (window as any).__TAURI__
  })

  it('detects Web mode (no __TAURI__)', () => {
    const tauri = useTauri()
    expect(tauri.isTauri.value).toBe(false)
  })

  it('detects Tauri mode when __TAURI__ is present', () => {
    ;(window as any).__TAURI__ = { core: { invoke: async () => ({}) } }
    const tauri = useTauri()
    expect(tauri.isTauri.value).toBe(true)
  })

  it('createAccount returns null in Web mode', async () => {
    const tauri = useTauri()
    const result = await tauri.createAccount({
      username: 'test', password: 'pass', email: '', name: '',
    })
    expect(result).toBeNull()
  })

  it('login returns null in Web mode', async () => {
    const tauri = useTauri()
    const result = await tauri.login({ username: 'test', password: 'pass' })
    expect(result).toBeNull()
  })

  it('listAccounts returns null in Web mode', async () => {
    const tauri = useTauri()
    const result = await tauri.listAccounts()
    expect(result).toBeNull()
  })

  it('calls invoke in Tauri mode for login', async () => {
    const mockInvoke = async (_cmd: string, _args?: any) => ({ id: 'u1', username: 'alice' })
    ;(window as any).__TAURI__ = { core: { invoke: mockInvoke } }

    const tauri = useTauri()
    const result = await tauri.login({ username: 'alice', password: 'pass' })
    expect(result).toEqual({ id: 'u1', username: 'alice' })
  })

  it('calls invoke in Tauri mode for saveDraft', async () => {
    let capturedCmd = ''
    let capturedArgs: any = {}
    const mockInvoke = async (cmd: string, args?: any) => {
      capturedCmd = cmd
      capturedArgs = args
      return { id: 'd1', title: 'Draft', content: '# H', format: 'md', updated_at: '2026-01-01', account_id: 'a1' }
    }
    ;(window as any).__TAURI__ = { core: { invoke: mockInvoke } }

    const tauri = useTauri()
    const result = await tauri.saveDraft({ account_id: 'a1', title: 'Draft', content: '# H', format: 'markdown' })
    expect(capturedCmd).toBe('save_draft')
    // Tauri 2.x wraps args under the named parameter key 'params'
    expect(capturedArgs.params).toMatchObject({ account_id: 'a1', title: 'Draft' })
    expect(result).toHaveProperty('id', 'd1')
  })

  it('returns error object when invoke throws', async () => {
    const mockInvoke = async () => { throw new Error('IPC failed') }
    ;(window as any).__TAURI__ = { core: { invoke: mockInvoke } }

    const tauri = useTauri()
    const result = await tauri.login({ username: 'alice', password: 'pass' })
    expect(result).toEqual({ error: 'IPC failed' })
  })

  it('returns error object when invoke returns AppError shape', async () => {
    const mockInvoke = async () => ({ code: 'AUTH_FAILED', message: 'Incorrect password' })
    ;(window as any).__TAURI__ = { core: { invoke: mockInvoke } }

    const tauri = useTauri()
    const result = await tauri.login({ username: 'alice', password: 'wrong' })
    expect(result).toEqual({ error: 'Incorrect password' })
  })

  it('returns error when core API is missing in Tauri mode', async () => {
    ;(window as any).__TAURI__ = {} // no .core
    const tauri = useTauri()
    expect(tauri.isTauri.value).toBe(true)
    const result = await tauri.login({ username: 'alice', password: 'pass' })
    expect(result).toEqual({ error: 'Tauri core API not available' })
  })
})
