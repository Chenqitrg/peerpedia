// SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
// SPDX-License-Identifier: CC-BY-NC-SA-4.0

import { describe, it, expect } from 'vitest'

describe('API client', () => {
  it('has correct base URL', async () => {
    const { apiClient } = await import('../client')
    // base URL reads VITE_API_BASE_URL env var, defaulting to localhost:8080
    const expected = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080'
    expect(apiClient.defaults.baseURL).toBe(`${expected}/api/v1`)
  })
})
