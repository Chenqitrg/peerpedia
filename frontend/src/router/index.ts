import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', component: () => import('../pages/HomePage.vue') },
  { path: '/article/:id', component: () => import('../pages/ArticlePage.vue') },
  { path: '/edit', component: () => import('../pages/EditorPage.vue') },
  { path: '/edit/:id', component: () => import('../pages/EditorPage.vue') },
  { path: '/pool', component: () => import('../pages/PoolPage.vue') },
  { path: '/user/:id', component: () => import('../pages/UserPage.vue') },
  { path: '/search', component: () => import('../pages/SearchPage.vue') },
]

const router = createRouter({ history: createWebHistory(), routes })

export { router }
export default routes
