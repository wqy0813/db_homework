<template>
  <div class="page-head">
    <h2>巡演管理</h2>
    <el-button type="danger" @click="openCreate">创建巡演</el-button>
  </div>

  <el-card shadow="never" style="margin-bottom:18px">
    <el-form inline @submit.prevent="load">
      <el-form-item label="巡演名称">
        <el-input v-model="filters.keyword" placeholder="输入巡演名称或艺人" clearable style="width:220px" @keyup.enter="load" />
      </el-form-item>
      <el-form-item label="类型">
        <el-select v-model="filters.category_id" placeholder="全部类型" clearable style="width:145px">
          <el-option v-for="c in categories" :key="c.category_id" :value="c.category_id" :label="c.category_name" />
        </el-select>
      </el-form-item>
      <el-form-item label="城市站">
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

  <el-table :data="series" v-loading="loading" border>
    <el-table-column prop="series_id" label="ID" width="70" />
    <el-table-column prop="series_name" label="巡演名称" min-width="190" />
    <el-table-column prop="main_artist" label="主演/艺人" min-width="130">
      <template #default="{row}">{{ row.main_artist || '—' }}</template>
    </el-table-column>
    <el-table-column prop="category_name" label="类型" width="100" />
    <el-table-column label="站点" width="120">
      <template #default="{row}">{{ row.station_count }} 站 / {{ row.city_count }} 城</template>
    </el-table-column>
    <el-table-column label="票价区间" width="130">
      <template #default="{row}">¥{{ Math.round(row.min_price || 0) }}-¥{{ Math.round(row.max_price || 0) }}</template>
    </el-table-column>
    <el-table-column label="状态" width="100">
      <template #default="{row}">
        <el-tag v-if="row.station_count" :type="tagType(row.show_status)">{{ STATUS_NAMES[row.show_status] }}</el-tag>
        <el-tag v-else type="info">待添加站点</el-tag>
      </template>
    </el-table-column>
    <el-table-column label="操作" width="250" fixed="right">
      <template #default="{row}">
        <el-button size="small" type="primary" @click="goDetail(row)">站点/场次</el-button>
        <el-button size="small" @click="openEdit(row)">修改</el-button>
        <el-popconfirm title="删除巡演会一并删除其站点、场次和票档，已有订单的巡演不可删除。确认？" @confirm="remove(row)">
          <template #reference><el-button size="small" type="danger">删除</el-button></template>
        </el-popconfirm>
      </template>
    </el-table-column>
  </el-table>
  <el-empty v-if="!loading && !series.length" description="暂无巡演" />

  <el-dialog v-model="dialogVisible" :title="editing ? '修改巡演' : '创建巡演'" width="720px" :close-on-click-modal="false">
    <el-form label-width="100px" @submit.prevent>
      <el-form-item label="巡演名称" required><el-input v-model="form.series_name" maxlength="100" show-word-limit /></el-form-item>
      <el-form-item label="演出类型" required>
        <el-select v-model="form.category_id" placeholder="请选择类型" style="width:100%">
          <el-option v-for="c in categories" :key="c.category_id" :value="c.category_id" :label="c.category_name" />
        </el-select>
      </el-form-item>
      <el-form-item label="主演/艺人"><el-input v-model="form.main_artist" maxlength="50" /></el-form-item>
      <el-form-item label="巡演海报">
        <div class="poster-editor">
          <el-upload :show-file-list="false" accept="image/jpeg,image/png,image/gif,image/webp" :http-request="uploadPoster">
            <el-button>选择并上传</el-button>
          </el-upload>
          <el-input v-model="form.poster_url" placeholder="也可直接填写图片 URL" />
          <el-image v-if="form.poster_url" :src="form.poster_url" fit="cover" class="poster-preview" />
          <div class="poster-tip muted">支持上传图片（jpg/png/webp等），或填写以 http://、https://、/static 开头的网络地址；不支持本地文件路径（如 C:\...）</div>
        </div>
      </el-form-item>
      <el-form-item label="巡演介绍"><el-input v-model="form.description" type="textarea" :rows="4" maxlength="2000" show-word-limit /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">{{ editing ? '保存' : '创建' }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../../api'
import { STATUS_NAMES } from '../../store'

const router = useRouter()
const series = ref([])
const cities = ref([])
const categories = ref([])
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editingId = ref(null)
const editingGroupName = ref('')
const filters = reactive({ keyword: '', category_id: null, city_id: null, show_status: null })
const form = reactive({ series_name: '', category_id: null, main_artist: '', poster_url: '', description: '' })
const editing = computed(() => editingId.value !== null || Boolean(editingGroupName.value))
const tagType = status => ({ 1: 'warning', 2: 'success', 3: 'info', 4: 'info' }[status])

async function load() {
  loading.value = true
  try {
    const params = Object.fromEntries(Object.entries(filters).filter(([, value]) => value !== null && value !== ''))
    const r = await api.get('/admin/series', { params })
    series.value = r.data.list
    cities.value = r.data.cities
    categories.value = r.data.categories
  } finally { loading.value = false }
}
function resetFilters() {
  Object.assign(filters, { keyword: '', category_id: null, city_id: null, show_status: null })
  load()
}
function clearForm() {
  editingId.value = null
  editingGroupName.value = ''
  Object.assign(form, { series_name: '', category_id: null, main_artist: '', poster_url: '', description: '' })
}
function openCreate() { clearForm(); dialogVisible.value = true }
function openEdit(row) {
  editingId.value = row.inferred ? null : row.series_id
  editingGroupName.value = row.inferred ? row.group_name : ''
  Object.assign(form, {
    series_name: row.series_name, category_id: row.category_id,
    main_artist: row.main_artist || '', poster_url: row.poster_url || '', description: row.description || ''
  })
  dialogVisible.value = true
}
async function uploadPoster({ file, onSuccess, onError }) {
  const body = new FormData(); body.append('poster', file)
  try {
    const r = await api.post('/admin/uploads/poster', body)
    form.poster_url = r.data.url; ElMessage.success(r.msg); onSuccess(r)
  } catch (err) { onError(err) }
}
async function save() {
  if (!form.series_name.trim() || !form.category_id) return ElMessage.warning('请填写巡演名称并选择类型')
  if (form.poster_url && (/^[a-zA-Z]:[\\/]/.test(form.poster_url) || form.poster_url.includes('\\'))) {
    return ElMessage.warning('图片地址格式不正确：不能填写本地文件路径，请先点击「选择并上传」或填写网络地址')
  }
  saving.value = true
  try {
    const payload = { ...form, series_name: form.series_name.trim() }
    const r = editingId.value
      ? await api.post(`/admin/series/${editingId.value}/update`, payload)
      : editingGroupName.value
        ? await api.post('/admin/series/group/update', { ...payload, group_name: editingGroupName.value })
        : await api.post('/admin/series/create', payload)
    ElMessage.success(r.msg); dialogVisible.value = false; await load()
  } finally { saving.value = false }
}
async function remove(row) {
  const r = row?.inferred
    ? await api.post('/admin/series/group/delete', { group_name: row.group_name })
    : await api.post(`/admin/series/${row.series_id}/delete`)
  ElMessage.success(r.msg); await load()
}
function goDetail(row) {
  if (row.inferred) router.push({ path: '/admin/series/group', query: { name: row.group_name } })
  else router.push(`/admin/series/${row.series_id}`)
}
onMounted(load)
</script>

<style scoped>
.page-head { display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }
.page-head h2 { margin:0; }
.poster-editor { display:flex; align-items:center; gap:10px; flex-wrap:wrap; width:100%; }
.poster-editor .el-input { flex:1; min-width:220px; }
.poster-preview { width:56px; height:56px; border-radius:4px; }
.poster-tip { font-size: 12px; color: #888; margin-top: 4px; width: 100%; }
</style>
