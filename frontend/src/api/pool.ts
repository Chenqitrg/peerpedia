import apiClient from './client'

export async function getPool(): Promise<import('./types').PoolResponse> {
  const res = await apiClient.get('/pool')
  return res.data
}
