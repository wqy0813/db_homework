<template>
  <el-card class="login-card">
    <h2 style="text-align:center;margin-bottom:20px">{{ mode === 'login' ? '用户登录' : '注册新账号' }}</h2>

    <!-- 登录 -->
    <template v-if="mode === 'login'">
      <el-radio-group v-model="role" class="role-group">
        <el-radio-button value="user">用户</el-radio-button>
        <el-radio-button value="admin">管理员</el-radio-button>
      </el-radio-group>
      <el-input v-model="username" placeholder="用户名（如 zhang_san / admin）" size="large" style="margin:16px 0" />
      <el-input v-model="password" type="password" placeholder="密码 123456" size="large" @keyup.enter="doLogin" />
      <el-button type="danger" size="large" style="width:100%;margin-top:20px" :loading="loading" @click="doLogin">登 录</el-button>
      <p class="muted" style="margin-top:16px;line-height:1.8">
        演示账号：用户 zhang_san / li_si / wang_wu / zhao_liu / chen_qi，管理员 admin；密码均 <b>123456</b>。
        游客可直接 <router-link to="/series">浏览演出巡演</router-link>。
      </p>
      <p style="text-align:center;margin-top:8px" v-if="role === 'user'">
        还没有账号？<el-link type="danger" :underline="false" @click="goRegister">立即注册</el-link>
      </p>
    </template>

    <!-- 注册（仅普通用户） -->
    <template v-else>
      <el-form ref="regFormRef" label-position="top" :model="reg" :rules="regRules" @submit.prevent>
        <el-form-item label="用户名" prop="username">
          <el-input v-model="reg.username" maxlength="50" placeholder="2-50 个字符，中文/字母/数字/下划线" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="reg.password" type="password" maxlength="64" placeholder="6-64 位" show-password />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm">
          <el-input v-model="reg.confirm" type="password" maxlength="64" placeholder="再次输入密码"
                    @keyup.enter="doRegister" />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="reg.phone" maxlength="11" placeholder="11 位手机号，用于联系与找回" />
        </el-form-item>
        <el-form-item label="邮箱（选填）" prop="email">
          <el-input v-model="reg.email" maxlength="100" placeholder="选填" @keyup.enter="doRegister" />
        </el-form-item>
      </el-form>
      <el-button type="danger" size="large" style="width:100%;margin-top:4px" :loading="loading" @click="doRegister">注 册</el-button>
      <p class="muted" style="margin-top:12px">注册仅创建普通用户账号；管理员账号由系统维护，不能通过注册创建。</p>
      <p style="text-align:center;margin-top:8px">
        已有账号？<el-link type="danger" :underline="false" @click="mode = 'login'">返回登录</el-link>
      </p>
    </template>
  </el-card>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api'
import { useStore } from '../store'

const store = useStore()
const router = useRouter()
const mode = ref('login') // login | register
const role = ref('user')
const username = ref('')
const password = ref('')
const loading = ref(false)
const reg = reactive({ username: '', password: '', confirm: '', phone: '', email: '' })
const regFormRef = ref()

// 注册表单内联校验：错误红字显示在对应输入框下方
const regRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 50, message: '用户名应为 2-50 个字符', trigger: 'blur' },
    { pattern: /^[A-Za-z0-9_\u4e00-\u9fa5]+$/, message: '仅限中文、字母、数字或下划线', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 64, message: '密码长度应为 6-64 位', trigger: 'blur' }
  ],
  confirm: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    { validator: (rule, value, cb) => (value === reg.password ? cb() : cb(new Error('两次输入的密码不一致'))), trigger: 'blur' }
  ],
  phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { pattern: /^1\d{10}$/, message: '手机号应为 11 位数字（1 开头）', trigger: 'blur' }
  ],
  email: [
    { pattern: /^[^@\s]+@[^@\s]+\.[^@\s]+$/, message: '邮箱格式不正确', trigger: 'blur' }
  ]
}

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

function goRegister() {
  reg.username = username.value.trim()
  mode.value = 'register'
}

async function doRegister() {
  // 先过内联校验，不通过时错误已标红在各输入框下
  try { await regFormRef.value.validate() } catch (e) { return }
  const u = reg.username.trim()
  const email = reg.email.trim()

  loading.value = true
  try {
    const r = await api.post('/register', {
      username: u, password: reg.password, confirm_password: reg.confirm,
      phone: reg.phone.trim(), email: email || undefined
    })
    ElMessage.success(r.msg || '注册成功，请登录')
    username.value = u
    password.value = ''
    mode.value = 'login'
    role.value = 'user'
  } catch (e) {
    // 拦截器已提示（重复用户名、手机号已注册等后端校验）
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
