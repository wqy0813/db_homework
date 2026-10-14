<template>
  <h2>我的收货信息</h2>
  <el-card shadow="never" style="margin-bottom:18px">
    <el-button type="danger" @click="openAdd">新增收货地址</el-button>
    <span class="muted" style="margin-left:12px">支持整段粘贴自动识别收货人 / 手机号 / 省市区</span>
  </el-card>
  <el-table :data="list" v-loading="loading" border>
    <el-table-column prop="receiver_name" label="收货人" />
    <el-table-column prop="phone" label="手机号" />
    <el-table-column prop="address_detail" label="收货地址" />
    <el-table-column label="默认" width="80">
      <template #default="{row}"><el-tag v-if="row.is_default" type="success">默认</el-tag></template>
    </el-table-column>
    <el-table-column label="操作" width="240" fixed="right">
      <template #default="{row}">
        <template v-if="row.used_by_order">
          <el-tooltip placement="top"
                      content="为保留历史订单信息，不能修改或删除，可以新增一条用于后续购票。">
            <span style="margin-right:8px"><el-button size="small" disabled>编辑</el-button></span>
          </el-tooltip>
          <el-button v-if="!row.is_default" size="small" @click="setDefault(row.address_id)">设为默认</el-button>
          <el-tooltip placement="top"
                      content="为保留历史订单信息，不能修改或删除，可以新增一条用于后续购票。">
            <span style="margin-left:8px"><el-button size="small" type="danger" plain disabled>删除</el-button></span>
          </el-tooltip>
        </template>
        <template v-else>
          <el-button size="small" @click="edit(row)">编辑</el-button>
          <el-button v-if="!row.is_default" size="small" @click="setDefault(row.address_id)">设为默认</el-button>
          <el-popconfirm title="确认删除该收货信息？" @confirm="del(row.address_id)">
            <template #reference><el-button size="small" type="danger" plain>删除</el-button></template>
          </el-popconfirm>
        </template>
      </template>
    </el-table-column>
  </el-table>

  <AddressDialog v-model="dialogVisible" :address="editing" @saved="onSaved" />
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'
import AddressDialog from '../components/AddressDialog.vue'

const list = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const editing = ref(null)

async function load() {
  loading.value = true
  try { list.value = (await api.get('/addresses')).data.list } finally { loading.value = false }
}
function openAdd() {
  editing.value = null
  dialogVisible.value = true
}
async function del(id) {
  await api.post('/addresses/delete', { address_id: id })
  ElMessage.success('已删除'); load()
}
async function setDefault(id) {
  await api.post('/addresses/default', { address_id: id })
  ElMessage.success('已设为默认'); load()
}
function edit(row) {
  editing.value = row
  dialogVisible.value = true
}
function onSaved() {
  load()
}
onMounted(load)
</script>
