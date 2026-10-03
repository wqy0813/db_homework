<template>
  <h2>我的收货信息</h2>
  <el-card shadow="never" style="margin-bottom:18px">
    <el-form inline @submit.prevent>
      <el-form-item label="收货人"><el-input v-model="form.receiver_name" placeholder="收货人" /></el-form-item>
      <el-form-item label="手机号"><el-input v-model="form.phone" placeholder="手机号" /></el-form-item>
      <el-form-item label="地址"><el-input v-model="form.address_detail" placeholder="收货地址" style="width:260px" /></el-form-item>
      <el-form-item><el-checkbox v-model="form.is_default">设为默认</el-checkbox></el-form-item>
      <el-button type="danger" @click="add">添加</el-button>
    </el-form>
  </el-card>
  <el-table :data="list" v-loading="loading" border>
    <el-table-column prop="receiver_name" label="收货人" />
    <el-table-column prop="phone" label="手机号" />
    <el-table-column prop="address_detail" label="收货地址" />
    <el-table-column label="默认" width="80">
      <template #default="{row}"><el-tag v-if="row.is_default" type="success">默认</el-tag></template>
    </el-table-column>
    <el-table-column label="操作" width="190">
      <template #default="{row}">
        <el-button v-if="!row.is_default" size="small" @click="setDefault(row.address_id)">设为默认</el-button>
        <el-popconfirm title="确认删除该收货信息？" @confirm="del(row.address_id)">
          <template #reference><el-button size="small" type="danger" plain>删除</el-button></template>
        </el-popconfirm>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const list = ref([])
const loading = ref(false)
const form = reactive({ receiver_name: '', phone: '', address_detail: '', is_default: false })

async function load() {
  loading.value = true
  try { list.value = (await api.get('/addresses')).data.list } finally { loading.value = false }
}
async function add() {
  if (!form.receiver_name || !form.phone || !form.address_detail) return ElMessage.warning('请填写完整')
  if (!/^1\d{10}$/.test(form.phone.trim())) return ElMessage.warning('手机号应为 11 位数字（1 开头）')
  await api.post('/addresses/add', { ...form, phone: form.phone.trim(), is_default: form.is_default ? 1 : 0 })
  ElMessage.success('已添加')
  Object.assign(form, { receiver_name: '', phone: '', address_detail: '', is_default: false })
  load()
}
async function del(id) {
  await api.post('/addresses/delete', { address_id: id })
  ElMessage.success('已删除'); load()
}
async function setDefault(id) {
  await api.post('/addresses/default', { address_id: id })
  ElMessage.success('已设为默认'); load()
}
onMounted(load)
</script>
