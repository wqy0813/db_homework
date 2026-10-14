import { defineStore } from 'pinia'
import { reactive } from 'vue'
import api from './api'

// 登录/登出时清空所有列表筛选条件：换会话后筛选归零，
// 同一会话内的刷新、进详情再返回仍正常保留。
function clearAllFilters() {
  try {
    Object.keys(sessionStorage)
      .filter(k => k.startsWith('filter:'))
      .forEach(k => sessionStorage.removeItem(k))
  } catch (e) {}
}

export const useStore = defineStore('main', {
  state: () => ({ user: null }),
  getters: {
    isLogin: (s) => !!s.user,
    isAdmin: (s) => s.user && s.user.role === 'admin',
    isUser: (s) => s.user && s.user.role === 'user'
  },
  actions: {
    async fetchMe() {
      try {
        const r = await api.get('/me', { silent: true })
        this.user = r.data.user
        sessionStorage.setItem('user', JSON.stringify(this.user))
      } catch (e) {
        this.user = null
        sessionStorage.removeItem('user')
      }
    },
    async login(role, username, password) {
      const r = await api.post('/login', { role, username, password })
      this.user = r.data.user
      sessionStorage.setItem('user', JSON.stringify(this.user))
      clearAllFilters()
      clearBuyForms()
      return r
    },
    async logout() {
      await api.post('/logout')
      this.user = null
      sessionStorage.removeItem('user')
      clearAllFilters()
      clearBuyForms()
    }
  }
})

export const STATUS_NAMES = { 1: '预售中', 2: '售票中', 3: '售罄', 4: '已结束' }
export const ORDER_STATUS = { 1: '待支付', 2: '已支付', 3: '已取消', 4: '已退款' }
export const ID_TYPE = { 1: '身份证', 2: '护照', 3: '港澳通行证', 4: '台胞证', 5: '军官证' }

// 列表筛选条件本地持久化：进入详情再返回、刷新后仍能恢复。
// 使用 sessionStorage，关闭浏览器标签即清空，不在多用户机器上残留。
const FILTER_PREFIX = 'filter:'

export function saveFilter(key, value) {
  try { sessionStorage.setItem(FILTER_PREFIX + key, JSON.stringify(value)) } catch (e) {}
}

export function loadFilter(key, fallback = null) {
  try {
    const raw = sessionStorage.getItem(FILTER_PREFIX + key)
    return raw ? JSON.parse(raw) : fallback
  } catch (e) { return fallback }
}

export function clearFilter(key) {
  try { sessionStorage.removeItem(FILTER_PREFIX + key) } catch (e) {}
}

// 购票表单跨页面共享：导航到别的演出再返回时，
// 已选过的场次（按 session_id）的票档/票数/地址/购票人全部保留；
// 登出/换号时清空，避免新账号看到旧账号的草稿。
export const buyFormBySession = reactive({})

export function clearBuyForms() {
  try { Object.keys(buyFormBySession).forEach(k => delete buyFormBySession[k]) } catch (e) {}
}
