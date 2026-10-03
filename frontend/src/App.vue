<template>
  <el-container>
    <el-header class="topbar">
      <div class="wrap nav">
        <router-link to="/series" class="brand">🎫 演出票务系统</router-link>
        <el-menu mode="horizontal" :ellipsis="false" router :default-active="$route.path" class="menu">
          <el-menu-item index="/series">演出巡演</el-menu-item>
          <template v-if="store.isAdmin">
            <el-menu-item index="/admin/shows">演出管理</el-menu-item>
            <el-menu-item index="/admin/stats">销售统计</el-menu-item>
          </template>
          <template v-else-if="store.isLogin">
            <el-menu-item index="/orders">我的订单</el-menu-item>
            <el-menu-item index="/addresses">收货信息</el-menu-item>
            <el-menu-item index="/attendees">常用购票人</el-menu-item>
          </template>
        </el-menu>
        <div class="right">
          <template v-if="store.user">
            <span class="who">{{ store.user.name }}（{{ store.isAdmin ? '管理员' : '用户' }}）</span>
            <el-button size="small" @click="doLogout">退出</el-button>
          </template>
          <el-button v-else size="small" type="primary" @click="goLogin">登录</el-button>
        </div>
      </div>
    </el-header>
    <el-main>
      <div class="page">
        <router-view />
      </div>
    </el-main>
  </el-container>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useStore } from './store'

const store = useStore()
const router = useRouter()

onMounted(() => store.fetchMe())

async function doLogout() {
  await store.logout()
  router.push('/shows')
}

function goLogin() {
  router.push('/login')
}
</script>

<style scoped>
.topbar { background: #fff; border-bottom: 1px solid #e5e7ef; padding: 0; height: 60px; }
.wrap { max-width: 1100px; margin: 0 auto; padding: 0 16px; display: flex; align-items: center; height: 100%; gap: 20px; }
.brand { font-size: 19px; font-weight: bold; color: #e94b64; white-space: nowrap; }
.menu { flex: 1; border-bottom: none; }
.right { display: flex; align-items: center; gap: 10px; }
.who { color: #888; font-size: 13px; white-space: nowrap; }
</style>
