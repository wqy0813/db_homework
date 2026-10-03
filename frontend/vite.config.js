import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 开发模式：/api 代理到 Flask 5000，避免跨域；生产构建后由 Flask 托管静态文件
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/static': { target: 'http://127.0.0.1:5000', changeOrigin: true }
    }
  },
  base: '/app/',
  build: {
    outDir: 'dist'
  }
})
