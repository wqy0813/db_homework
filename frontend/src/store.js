import { defineStore } from 'pinia'
import api from './api'

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
      return r
    },
    async logout() {
      await api.post('/logout')
      this.user = null
      sessionStorage.removeItem('user')
    }
  }
})

export const STATUS_NAMES = { 1: '预售中', 2: '售票中', 3: '售罄' }
export const ORDER_STATUS = { 1: '待支付', 2: '已支付', 3: '已取消', 4: '已退款' }
export const ID_TYPE = { 1: '身份证', 2: '护照', 3: '港澳通行证', 4: '台胞证', 5: '军官证' }
