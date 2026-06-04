import apiClient from './client'

export async function getUsers() {
  const res = await apiClient.get('/users')
  return res.data
}

export async function createUser(body: Record<string, unknown>) {
  const res = await apiClient.post('/users', body)
  return res.data
}

export async function getUser(id: string) {
  const res = await apiClient.get(`/users/${id}`)
  return res.data
}

export async function getFollowers(id: string) {
  const res = await apiClient.get(`/users/${id}/followers`)
  return res.data
}

export async function getFollowing(id: string) {
  const res = await apiClient.get(`/users/${id}/following`)
  return res.data
}

export async function followUser(id: string, followerId: string) {
  const res = await apiClient.post(`/users/${id}/follow`, null, { params: { follower_id: followerId } })
  return res.data
}

export async function unfollowUser(id: string, followerId: string) {
  const res = await apiClient.delete(`/users/${id}/follow`, { params: { follower_id: followerId } })
  return res.data
}
