import apiClient from './client'
import type { UserProfile, UserSummary } from './types'

export async function getUsers(): Promise<UserSummary[]> {
  const res = await apiClient.get('/users')
  return res.data
}

export async function createUser(body: Record<string, unknown>): Promise<UserProfile> {
  const res = await apiClient.post('/users', body)
  return res.data
}

export async function getUser(id: string): Promise<UserProfile> {
  const res = await apiClient.get(`/users/${id}`)
  return res.data
}

export async function getFollowers(id: string): Promise<UserSummary[]> {
  const res = await apiClient.get(`/users/${id}/followers`)
  return res.data
}

export async function getFollowing(id: string): Promise<UserSummary[]> {
  const res = await apiClient.get(`/users/${id}/following`)
  return res.data
}

export async function followUser(id: string): Promise<{ ok: boolean }> {
  const res = await apiClient.post(`/users/${id}/follow`)
  return res.data
}

export async function unfollowUser(id: string): Promise<{ ok: boolean }> {
  const res = await apiClient.delete(`/users/${id}/follow`)
  return res.data
}

export async function updateProfile(
  userId: string,
  data: {
    affiliation?: string
    expertise?: string[]
    anonymous_name?: string
    avatar_url?: string | null
    contact?: string | null
  }
): Promise<any> {
  const res = await apiClient.put(`/users/${userId}`, data)
  return res.data
}
