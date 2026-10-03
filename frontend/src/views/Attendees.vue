<template>
  <h2>常用购票人</h2>
  <el-card shadow="never" style="margin-bottom:18px">
    <el-form inline @submit.prevent>
      <el-form-item label="姓名"><el-input v-model="form.attendee_name" placeholder="姓名" /></el-form-item>
      <el-form-item label="证件类型">
        <el-select v-model="form.id_type" style="width:130px">
          <el-option v-for="(n,i) in ID_TYPE" :key="i" :value="i" :label="n" />
        </el-select>
      </el-form-item>
      <el-form-item label="证件号"><el-input v-model="form.id_no" placeholder="证件号" /></el-form-item>
      <el-button type="danger" @click="add">添加</el-button>
    </el-form>
  </el-card>
  <el-table :data="list" v-loading="loading" border>
    <el-table-column prop="attendee_name" label="姓名" />
    <el-table-column label="证件类型" width="120">
      <template #default="{row}">{{ ID_TYPE[row.id_type] }}</template>
    </el-table-column>
    <el-table-column prop="id_no" label="证件号" />
    <el-table-column label="操作" width="100">
      <template #default="{row}">
        <el-popconfirm title="确认删除该购票人？" @confirm="del(row.attendee_id)">
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
import { ID_TYPE } from '../store'

const list = ref([])
const loading = ref(false)
const form = reactive({ attendee_name: '', id_type: 1, id_no: '' })

async function load() {
  loading.value = true
  try { list.value = (await api.get('/attendees')).data.list } finally { loading.value = false }
}
async function add() {
  if (!form.attendee_name || !form.id_no) return ElMessage.warning('请填写完整')
  // 证件号格式校验（避免乱码/测试数据）
  const idNo = form.id_no.trim()
  const idType = Number(form.id_type)
  if (idType === 1 && !/^\d{17}[\dXx]$/.test(idNo)) {
    return ElMessage.warning('身份证号应为 18 位（末位可为 X）')
  }
  if (idType !== 1 && idNo.length < 5) {
    return ElMessage.warning('证件号格式不正确')
  }
  await api.post('/attendees/add', { ...form, id_no: idNo })
  ElMessage.success('已添加')
  Object.assign(form, { attendee_name: '', id_no: '' })
  load()
}
async function del(id) {
  await api.post('/attendees/delete', { attendee_id: id })
  ElMessage.success('已删除'); load()
}
onMounted(load)
</script>
