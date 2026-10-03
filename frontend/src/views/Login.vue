<template>
  <el-card class="login-card">
    <h2 style="text-align:center;margin-bottom:20px">用户登录</h2>
    <el-radio-group v-model="role" class="role-group">
      <el-radio-button value="user">用户</el-radio-button>
      <el-radio-button value="admin">管理员</el-radio-button>
    </el-radio-group>
    <el-input v-model="username" placeholder="用户名（如 zhang_san / admin）" size="large" style="margin:16px 0" />
    <el-input v-model="password" type="password" placeholder="密码 123456" size="large" @keyup.enter="doLogin" />
    <el-button type="danger" size="large" style="width:100%;margin-top:20px" :loading="loading" @click="doLogin">登 录</el-button>
    <p class="muted" style="margin-top:16px;line-height:1.8">
      演示账号：用户 zhang_san / li_si / wang_wu / zhao_liu / chen_qi，管理员 admin；密码均 <b>123456</b>。
      游客可直接 <router-link to="/series">浏览巡演</router-link>。
    </p>
  </el-card>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useStore } from '../store'

const store = useStore()
const router = useRouter()
const role = ref('user')
const username = ref('')
const password = ref('')
const loading = ref(false)

async function doLogin() {
  if (!username.value || !password.value) return ElMessage.warning('请输入用户名和密码')
  loading.value = true
  try {
    const r = await store.login(role.value, username.value.trim(), password.value)
    ElMessage.success(r.msg)
    router.push(role.value === 'admin' ? '/admin/shows' : '/series')
  } catch (e) {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-card { max-width: 440px; margin: 40px auto; }
.role-group { display: flex; justify-content: center; width: 100%; }
.role-group :deep(.el-radio-button) { width: 50%; }
</style>
