import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockClient = {
  get: vi.fn(),
  post: vi.fn(),
  delete: vi.fn(),
}

vi.mock('../client', () => ({
  default: mockClient,
}))

describe('users API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('getUsers calls GET /users', async () => {
    const { getUsers } = await import('../users')
    const mockData = [{ id: 'u1', name: 'Alice' }]
    mockClient.get.mockResolvedValue({ data: mockData })
    const result = await getUsers()
    expect(mockClient.get).toHaveBeenCalledWith('/users')
    expect(result).toEqual(mockData)
  })

  it('createUser calls POST /users with body', async () => {
    const { createUser } = await import('../users')
    const body = { name: 'Alice', affiliation: 'MIT', expertise: ['physics'] }
    mockClient.post.mockResolvedValue({ data: { id: 'u1', ...body } })
    const result = await createUser(body)
    expect(mockClient.post).toHaveBeenCalledWith('/users', body)
    expect(result.id).toBe('u1')
  })

  it('getUser calls GET /users/{id}', async () => {
    const { getUser } = await import('../users')
    mockClient.get.mockResolvedValue({ data: { id: 'u1', name: 'Alice' } })
    const result = await getUser('u1')
    expect(mockClient.get).toHaveBeenCalledWith('/users/u1')
    expect(result.name).toBe('Alice')
  })

  it('getFollowers calls GET /users/{id}/followers', async () => {
    const { getFollowers } = await import('../users')
    mockClient.get.mockResolvedValue({ data: [{ id: 'u2', name: 'Bob' }] })
    const result = await getFollowers('u1')
    expect(mockClient.get).toHaveBeenCalledWith('/users/u1/followers')
    expect(result).toHaveLength(1)
  })

  it('getFollowing calls GET /users/{id}/following', async () => {
    const { getFollowing } = await import('../users')
    mockClient.get.mockResolvedValue({ data: [{ id: 'u3', name: 'Charlie' }] })
    const result = await getFollowing('u1')
    expect(mockClient.get).toHaveBeenCalledWith('/users/u1/following')
    expect(result).toHaveLength(1)
  })

  it('followUser calls POST /users/{id}/follow with follower_id param', async () => {
    const { followUser } = await import('../users')
    mockClient.post.mockResolvedValue({ data: {} })
    await followUser('u1', 'u2')
    expect(mockClient.post).toHaveBeenCalledWith('/users/u1/follow', null, {
      params: { follower_id: 'u2' },
    })
  })

  it('unfollowUser calls DELETE /users/{id}/follow with follower_id param', async () => {
    const { unfollowUser } = await import('../users')
    mockClient.delete.mockResolvedValue({ data: {} })
    await unfollowUser('u1', 'u2')
    expect(mockClient.delete).toHaveBeenCalledWith('/users/u1/follow', {
      params: { follower_id: 'u2' },
    })
  })
})
