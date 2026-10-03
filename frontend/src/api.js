import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from './router'

const api = axios.create({ baseURL: '/api', withCredentials: true })

// 响应拦截：统一按 code 处理
api.interceptors.response.use(
  (resp) => {
    const body = resp.data
    if (body.code === 0) return body
    // 静默模式（如 /me 探测登录态）不弹窗、不跳转
    const silent = resp.config && resp.config.silent
    if (body.code === 401) {
      if (!silent) {
        ElMessage.warning('请先登录')
        router.push('/login')
      }
      return Promise.reject(body)
    }
    if (body.code === 403) {
      if (!silent) ElMessage.error('无权访问')
      return Promise.reject(body)
    }
    if (!silent) ElMessage.error(body.msg || '操作失败')
    return Promise.reject(body)
  },
  (err) => {
    const silent = err.config && err.config.silent
    if (!silent) ElMessage.error('网络错误：' + err.message)
    return Promise.reject(err)
  }
)

export default api
