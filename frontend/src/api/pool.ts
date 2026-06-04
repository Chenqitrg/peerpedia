import apiClient from './client'

export async function getPool() {
  const res = await apiClient.get('/pool')
  return res.data
}
