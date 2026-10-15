import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/series' },
  {
    path: '/login', component: () => import('./views/Login.vue'), meta: { title: '登录 / 注册' },
    beforeEnter: (to) => to.query.intent === 'login' || to.query.required === 'true' ? true : '/series'
  },
  { path: '/series', component: () => import('./views/SeriesList.vue'), meta: { title: '演出巡演' } },
  { path: '/series/group', component: () => import('./views/SeriesDetail.vue'), meta: { title: '巡演详情' } },
  { path: '/series/:id', component: () => import('./views/SeriesDetail.vue'), meta: { title: '巡演详情' } },
  { path: '/shows/:id', component: () => import('./views/ShowDetail.vue'), meta: { title: '演出详情' } },
  { path: '/orders', component: () => import('./views/Orders.vue'), meta: { role: 'user', title: '我的订单' } },
  { path: '/addresses', component: () => import('./views/Addresses.vue'), meta: { role: 'user', title: '收货信息' } },
  { path: '/attendees', component: () => import('./views/Attendees.vue'), meta: { role: 'user', title: '常用购票人' } },
  { path: '/admin/shows', component: () => import('./views/admin/Shows.vue'), meta: { role: 'admin', title: '演出管理' } },
  { path: '/admin/shows/create', component: () => import('./views/admin/ShowCreate.vue'), meta: { role: 'admin', title: '创建演出' } },
  { path: '/admin/shows/:id', component: () => import('./views/admin/ShowEdit.vue'), meta: { role: 'admin', title: '演出维护' } },
  { path: '/admin/series', component: () => import('./views/admin/SeriesManage.vue'), meta: { role: 'admin', title: '巡演管理' } },
  { path: '/admin/series/group', component: () => import('./views/admin/SeriesDetail.vue'), meta: { role: 'admin', title: '巡演站点' } },
  { path: '/admin/series/:id', component: () => import('./views/admin/SeriesDetail.vue'), meta: { role: 'admin', title: '巡演站点' } },
  { path: '/admin/stats', component: () => import('./views/admin/Stats.vue'), meta: { role: 'admin', title: '销售统计' } }
]

const router = createRouter({ history: createWebHashHistory(), routes })

router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} - 演出票务系统` : '演出票务系统'
})

router.beforeEach((to) => {
  if (to.meta.role) {
    const raw = sessionStorage.getItem('user')
    if (raw) {
      try {
        const u = JSON.parse(raw)
        if (u.role !== to.meta.role) return '/series'
      } catch (e) {
        sessionStorage.removeItem('user')
        return { path: '/login', query: { required: 'true' } }
      }
    }
  }
  return true
})

export default router
