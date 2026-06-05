import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', component: () => import('../pages/HomePage.vue') },
  { path: '/article/:id', component: () => import('../pages/ArticlePage.vue') },
  { path: '/articles/:id', component: () => import('../pages/ArticlePage.vue') },
  { path: '/articles/:id/history', component: () => import('../pages/HistoryPage.vue') },
  { path: '/edit', component: () => import('../pages/EditorPage.vue'), meta: { requiresAuth: true } },
  { path: '/edit/:id', component: () => import('../pages/EditorPage.vue'), meta: { requiresAuth: true } },
  { path: '/schools', component: () => import('../pages/SchoolsPage.vue') },
  { path: '/pool', component: () => import('../pages/PoolPage.vue'), meta: { requiresAuth: true } },
  { path: '/user/:id', component: () => import('../pages/UserPage.vue') },
  { path: '/search', component: () => import('../pages/SearchPage.vue') },
  { path: '/bookmarks', component: () => import('../pages/BookmarksPage.vue'), meta: { requiresAuth: true } },
  { path: '/articles/:id/citations', component: () => import('../pages/CitationsPage.vue') },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to, _from, next) => {
  if (to.meta.requiresAuth) {
    // Check localStorage directly to avoid circular store dependency
    const viewer = localStorage.getItem('viewer')
    if (!viewer) {
      localStorage.setItem('intendedRoute', to.fullPath)
      localStorage.setItem('showAuthModal', 'true')
      next('/')
      return
    }
  }
  next()
})

export { router }
export default routes
