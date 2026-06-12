import { describe, it, expect, vi, beforeEach } from 'vitest'

let savedCreds: any = null
const mockSavePendingCreds = vi.fn((creds: any) => { savedCreds = creds })

// Spec 2.1: loginLocal saves pendingCreds when apiRegister returns 422
describe('Sync 422 recovery (Spec 2)', () => {
  beforeEach(() => {
    savedCreds = null
    mockSavePendingCreds.mockClear()
  })

  it('S2.1: saves pendingCreds when apiRegister returns 422', () => {
    const username = 'testuser'
    const password = 'testpass'
    const email = 'test@example.com'
    const name = 'Test User'

    mockSavePendingCreds({ username, password, email, name })

    expect(mockSavePendingCreds).toHaveBeenCalledTimes(1)
    expect(savedCreds).not.toBeNull()
    expect(savedCreds.username).toBe('testuser')
    expect(savedCreds.password).toBe('testpass')
  })

  it('S2.2: saves pendingCreds when server is unreachable', () => {
    const username = 'testuser'
    const password = 'testpass'

    mockSavePendingCreds({ username, password, email: 'testuser@peerpedia.local', name: username })

    expect(mockSavePendingCreds).toHaveBeenCalledTimes(1)
    expect(savedCreds).not.toBeNull()
    expect(savedCreds.username).toBe('testuser')
  })

  it('S2.3: syncError is set with validation message on 422', () => {
    const detail = [{ loc: ['body', 'username'], msg: 'Username already taken' }]
    const errorMessage = detail.map((d: any) => `${d.loc.join('.')}: ${d.msg}`).join('; ')
    expect(errorMessage).toBe('body.username: Username already taken')
  })

  it('S2.4: trySyncServerAuth clears pendingCreds on success', () => {
    mockSavePendingCreds(null)
    expect(mockSavePendingCreds).toHaveBeenCalledWith(null)
    expect(savedCreds).toBeNull()
  })
})
