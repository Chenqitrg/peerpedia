import { describe, it, expect } from 'vitest'
import { createRouter, createWebHistory } from 'vue-router'

describe('router', () => {
  it('has all routes', async () => {
    const { default: routes } = await import('../index')
    const router = createRouter({ history: createWebHistory(), routes })
    const paths = routes.map(r => r.path)
    expect(paths).toContain('/')
    expect(paths).toContain('/article/:id')
    expect(paths).toContain('/edit')
    expect(paths).toContain('/edit/:id')
    expect(paths).toContain('/pool')
    expect(paths).toContain('/user/:id')
    expect(paths).toContain('/search')
  })
})
