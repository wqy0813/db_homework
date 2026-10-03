import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/series' },
  { path: '/login', component: () => import('./views/Login.vue') },
  { path: '/series', component: () => import('./views/SeriesList.vue') },
  { path: '/series/:id', component: () => import('./views/SeriesDetail.vue') },
  { path: '/shows', component: () => import('./views/ShowList.vue') },
  { path: '/shows/:id', component: () => import('./views/ShowDetail.vue') },
  { path: '/orders', component: () => import('./views/Orders.vue'), meta: { role: 'user' } },
  { path: '/addresses', component: () => import('./views/Addresses.vue'), meta: { role: 'user' } },
  { path: '/attendees', component: () => import('./views/Attendees.vue'), meta: { role: 'user' } },
  { path: '/admin/shows', component: () => import('./views/admin/Shows.vue'), meta: { role: 'admin' } },
  { path: '/admin/shows/:id', component: () => import('./views/admin/ShowEdit.vue'), meta: { role: 'admin' } },
  { path: '/admin/stats', component: () => import('./views/admin/Stats.vue'), meta: { role: 'admin' } }
]

const router = createRouter({ history: createWebHashHistory(), routes })

router.beforeEach((to) => {
  // 简单角色守卫（store 在组件内 fetchMe 后会再次拦截 API）
  if (to.meta.role) {
    const raw = sessionStorage.getItem('user')
    if (raw) {
      try {
        const u = JSON.parse(raw)
        if (u.role !== to.meta.role) return '/shows'
      } catch (e) {
        sessionStorage.removeItem('user')
        return '/login'
      }
    }
  }
  return true
})

export default router
