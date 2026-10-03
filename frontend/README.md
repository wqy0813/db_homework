# 前端（Vue 3 前后端分离）

第 3 期前端：Vue 3 + Vite + Element Plus + Pinia + Vue Router + ECharts，通过 `/api` 调用 Flask 后端。

## 开发模式（前后端分别启动，改代码热更新）

1. 先确保后端 Flask 在运行（5000 端口）：在 `backend/` 下 `python app.py`；
2. 在本目录（`frontend/`）：
   ```bash
   npm install          # 首次，安装依赖
   npm run dev          # 启动 Vite，访问 http://localhost:5173
   ```
   Vite 已配置代理：`/api` 请求自动转发到 `http://127.0.0.1:5000`，无跨域问题。

## 生产构建（单服务部署，答辩推荐）

```bash
npm run build          # 产物输出到 frontend/dist
```
构建后，把 `dist` 内容复制到 `backend/static_web/`（已按此约定配置 Flask 托管）。
之后只需启动 Flask 一个服务：

- 新版前端入口：**http://127.0.0.1:5000/app/**
- 根路径 `http://127.0.0.1:5000/` 会重定向到新版入口
- 接口：http://127.0.0.1:5000/api/...

> 一键脚本 `start_website.bat` 会启动 MySQL + Flask；新前端访问 `/app/`。

## 目录结构

```
frontend/
├─ src/
│  ├─ main.js            入口（注册 Element Plus / Pinia / Router）
│  ├─ App.vue            顶部导航布局
│  ├─ router.js          路由与角色守卫（hash 路由）
│  ├─ store.js           Pinia 登录态 + 常量字典
│  ├─ api.js             axios 封装（baseURL=/api，withCredentials，统一错误提示）
│  └─ views/
│     ├─ Login.vue / ShowList.vue / ShowDetail.vue（含购票）
│     ├─ Orders.vue / Addresses.vue / Attendees.vue
│     └─ admin/ Shows.vue / ShowEdit.vue / Stats.vue（ECharts）
└─ vite.config.js        dev 代理 /app/ base / build 配置
```

## 页面与接口对应

见后端文档 `docs/API接口说明.md`。购票、限购、不超卖、统计图表等逻辑全部在后端 `/api`，
前端只负责展示与交互；登录态用 Cookie Session（axios `withCredentials:true`）。
