// SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
// SPDX-License-Identifier: CC-BY-NC-SA-4.0

import { createRouter, createWebHistory } from 'vue-router'
import { loadJSON, saveString } from '../composables/useLocalStorage'

const routes = [
  { path: '/', component: () => import('../pages/HomePage.vue') },
  { path: '/article/:id', component: () => import('../pages/ArticlePage.vue') },
  { path: '/articles/:id', component: () => import('../pages/ArticlePage.vue') },
  { path: '/articles/:id/history', component: () => import('../pages/HistoryPage.vue') },
  { path: '/edit', component: () => import('../pages/EditorPage.vue'), meta: { requiresAuth: true } },
  { path: '/edit/:id', component: () => import('../pages/EditorPage.vue'), meta: { requiresAuth: true } },
  { path: '/schools', component: () => import('../pages/SchoolsPage.vue'), meta: { requiresAuth: true } },
  { path: '/pool', component: () => import('../pages/PoolPage.vue'), meta: { requiresAuth: true } },
  { path: '/user/:id', component: () => import('../pages/UserPage.vue') },
  { path: '/user/:id/followers', component: () => import('../pages/UserListPage.vue') },
  { path: '/user/:id/following', component: () => import('../pages/UserListPage.vue') },
  { path: '/search', component: () => import('../pages/SearchPage.vue') },
  { path: '/bookmarks', component: () => import('../pages/BookmarksPage.vue'), meta: { requiresAuth: true } },
  { path: '/articles/:id/citations', component: () => import('../pages/CitationsPage.vue') },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to, _from, next) => {
  if (to.meta.requiresAuth) {
    // Check localStorage directly to avoid circular store dependency
    const viewer = loadJSON('viewer')
    if (!viewer) {
      saveString('intendedRoute', to.fullPath)
      saveString('showAuthModal', 'true')
      next('/')
      return
    }
  }
  next()
})

export { router }
export default routes
