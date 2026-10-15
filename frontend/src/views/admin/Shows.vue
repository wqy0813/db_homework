<template>
  <div class="page-head">
    <h2>演出管理</h2>
    <el-button type="danger" @click="router.push('/admin/shows/create')">创建演出</el-button>
  </div>

  <el-card shadow="never" style="margin-bottom:18px">
    <el-form inline @submit.prevent="load">
      <el-form-item label="演出名称">
        <el-input v-model="filters.keyword" placeholder="输入演出名称" clearable style="width:210px"
                  @keyup.enter="load" />
      </el-form-item>
      <el-form-item label="类型">
        <el-select v-model="filters.category_id" placeholder="全部类型" clearable style="width:145px">
          <el-option v-for="c in cats" :key="c.category_id" :value="c.category_id" :label="c.category_name" />
        </el-select>
      </el-form-item>
      <el-form-item label="城市">
        <el-select v-model="filters.city_id" placeholder="全部城市" clearable filterable style="width:155px">
          <el-option v-for="c in cities" :key="c.city_id" :value="c.city_id" :label="c.city_name" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="filters.show_status" placeholder="全部状态" clearable style="width:135px">
          <el-option v-for="(name, value) in STATUS_NAMES" :key="value" :value="Number(value)" :label="name" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="load">筛选</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </el-form-item>
    </el-form>
  </el-card>

  <el-table :data="shows" v-loading="loading" border>
    <el-table-column prop="show_id" label="ID" width="70" />
    <el-table-column prop="show_name" label="名称" min-width="200" />
    <el-table-column prop="city_name" label="城市" width="110" />
    <el-table-column prop="category_name" label="类型" width="100" />
    <el-table-column label="票价区间" width="130">
      <template #default="{row}">¥{{ Math.round(row.min_price || 0) }}-{{ Math.round(row.max_price || 0) }}</template>
    </el-table-column>
    <el-table-column label="状态" width="100">
      <template #default="{row}">
        <el-tag :type="tagType(row.show_status)">{{ STATUS_NAMES[row.show_status] }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column label="操作" width="200">
      <template #default="{row}">
        <el-button size="small" type="primary" @click="router.push('/admin/shows/' + row.show_id)">编辑场次/票档</el-button>
        <el-popconfirm title="删除将级联删除其场次、票档、图片，确认？" @confirm="del(row.show_id)">
          <template #reference><el-button size="small" type="danger">删除</el-button></template>
        </el-popconfirm>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../../api'
import { STATUS_NAMES } from '../../store'

const router = useRouter()
const shows = ref([])
const cities = ref([])
const cats = ref([])
const loading = ref(false)
const filters = reactive({ keyword: '', category_id: null, city_id: null, show_status: null })
const tagType = (s) => ({ 1: 'warning', 2: 'success', 3: 'info', 4: 'info' }[s])

async function load() {
  loading.value = true
  try {
    const params = Object.fromEntries(Object.entries(filters).filter(([, value]) => value !== null && value !== ''))
    const r = await api.get('/admin/shows', { params })
    shows.value = r.data.list
    cities.value = r.data.cities
    cats.value = r.data.categories
  } finally { loading.value = false }
}
function resetFilters() {
  Object.assign(filters, { keyword: '', category_id: null, city_id: null, show_status: null })
  load()
}
async function del(id) {
  const r = await api.post(`/admin/shows/${id}/delete`)
  ElMessage.success(r.msg)
  await load()
}
onMounted(load)
</script>

<style scoped>
.page-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.page-head h2 { margin: 0; }
</style>
