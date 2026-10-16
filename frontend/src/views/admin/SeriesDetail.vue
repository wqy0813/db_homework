<template>
  <el-button link @click="router.push('/admin/series')">← 返回巡演管理</el-button>
  <div class="page-head">
    <div>
      <h2>{{ data.series?.series_name || '巡演详情' }}</h2>
      <div class="muted">{{ data.series?.category_name }} <span v-if="data.series?.main_artist">· {{ data.series.main_artist }}</span></div>
    </div>
    <div class="actions">
      <el-button @click="openEditSeries">修改巡演</el-button>
      <el-button type="danger" @click="confirmDeleteSeries">删除巡演</el-button>
    </div>
  </div>

  <el-card shadow="never" style="margin-bottom:18px">
    <div class="section-head">
      <div><h3>巡演站点</h3><span class="muted">共 {{ data.stations.length }} 个站点</span></div>
      <el-button type="danger" @click="openAddStation">新增站点</el-button>
    </div>
    <el-table :data="data.stations" v-loading="loading" border>
      <el-table-column prop="show_id" label="ID" width="70" />
      <el-table-column prop="show_name" label="站点名称" min-width="200" />
      <el-table-column prop="city_name" label="城市" width="110" />
      <el-table-column prop="session_count" label="场次数" width="90" />
      <el-table-column label="票价区间" width="140">
        <template #default="{row}">¥{{ Math.round(row.min_price || 0) }}-¥{{ Math.round(row.max_price || 0) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{row}"><el-tag :type="tagType(row.show_status)">{{ STATUS_NAMES[row.show_status] }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="210" fixed="right">
        <template #default="{row}">
          <el-button size="small" type="primary" @click="manageSessions(row)">管理场次</el-button>
          <el-popconfirm title="删除站点会一并删除其场次和票档，已有订单的站点不可删除。确认？" @confirm="removeStation(row.show_id)">
            <template #reference><el-button size="small" type="danger">删除站点</el-button></template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!loading && !data.stations.length" description="该巡演还没有站点" />
  </el-card>

  <el-dialog v-model="seriesDialogVisible" title="修改巡演" width="720px" :close-on-click-modal="false">
    <el-form label-width="100px" @submit.prevent>
      <el-form-item label="巡演名称" required><el-input v-model="seriesForm.series_name" maxlength="100" /></el-form-item>
      <el-form-item label="演出类型" required>
        <el-select v-model="seriesForm.category_id" style="width:100%">
          <el-option v-for="c in categories" :key="c.category_id" :value="c.category_id" :label="c.category_name" />
        </el-select>
      </el-form-item>
      <el-form-item label="主演/艺人"><el-input v-model="seriesForm.main_artist" maxlength="50" /></el-form-item>
      <el-form-item label="巡演海报">
        <div class="poster-editor">
          <el-upload :show-file-list="false" accept="image/jpeg,image/png,image/gif,image/webp" :http-request="uploadSeriesPoster">
            <el-button>选择并上传</el-button>
          </el-upload>
          <el-input v-model="seriesForm.poster_url" placeholder="也可直接填写图片 URL" />
          <el-image v-if="seriesForm.poster_url" :src="seriesForm.poster_url" fit="cover" class="poster-preview" />
          <div class="poster-tip muted">支持上传图片（jpg/png/webp等），或填写以 http://、https://、/static 开头的网络地址；不支持本地文件路径（如 C:\...）</div>
        </div>
      </el-form-item>
      <el-form-item label="巡演介绍"><el-input v-model="seriesForm.description" type="textarea" :rows="4" maxlength="2000" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="seriesDialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="savingSeries" @click="saveSeries">保存</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="stationDialogVisible" title="新增巡演站点" width="620px" :close-on-click-modal="false">
    <el-form label-width="100px" @submit.prevent>
      <el-form-item label="所属巡演"><el-input :model-value="data.series?.series_name" disabled /></el-form-item>
      <el-form-item label="所在城市" required>
        <el-select v-model="stationForm.city_id" placeholder="请选择城市" filterable style="width:100%" @change="setStationName">
          <el-option v-for="city in cities" :key="city.city_id" :value="city.city_id" :label="city.city_name" />
        </el-select>
      </el-form-item>
      <el-form-item label="站点名称" required><el-input v-model="stationForm.show_name" maxlength="100" /></el-form-item>
      <el-form-item label="站点介绍"><el-input v-model="stationForm.description" type="textarea" :rows="3" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="stationDialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="savingStation" @click="createStation">添加站点</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api'
import { STATUS_NAMES } from '../../store'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const savingSeries = ref(false)
const savingStation = ref(false)
const seriesDialogVisible = ref(false)
const stationDialogVisible = ref(false)
const data = ref({ series: null, stations: [] })
const cities = ref([])
const categories = ref([])
const seriesForm = reactive({ series_name: '', category_id: null, main_artist: '', poster_url: '', description: '' })
const stationForm = reactive({ city_id: null, show_name: '', description: '' })
const tagType = status => ({ 1: 'warning', 2: 'success', 3: 'info', 4: 'info' }[status])

async function load() {
  loading.value = true
  try {
    const detailRequest = route.query.name
      ? api.get('/admin/series/group', { params: { name: route.query.name } })
      : api.get(`/admin/series/${route.params.id}`)
    const [detail, dict] = await Promise.all([detailRequest, api.get('/dicts')])
    data.value = detail.data
    cities.value = dict.data.cities
    categories.value = dict.data.categories
  } finally { loading.value = false }
}
function openEditSeries() {
  Object.assign(seriesForm, {
    series_name: data.value.series.series_name,
    category_id: data.value.series.category_id,
    main_artist: data.value.series.main_artist || '',
    poster_url: data.value.series.poster_url || '',
    description: data.value.series.description || ''
  })
  seriesDialogVisible.value = true
}
async function uploadSeriesPoster({ file, onSuccess, onError }) {
  const body = new FormData(); body.append('poster', file)
  try {
    const r = await api.post('/admin/uploads/poster', body)
    seriesForm.poster_url = r.data.url; ElMessage.success(r.msg); onSuccess(r)
  } catch (err) { onError(err) }
}
async function saveSeries() {
  if (!seriesForm.series_name.trim() || !seriesForm.category_id) return ElMessage.warning('请填写巡演名称并选择类型')
  if (seriesForm.poster_url && (/^[a-zA-Z]:[\\/]/.test(seriesForm.poster_url) || seriesForm.poster_url.includes('\\'))) {
    return ElMessage.warning('图片地址格式不正确：不能填写本地文件路径，请先点击「选择并上传」或填写网络地址')
  }
  savingSeries.value = true
  try {
    const payload = { ...seriesForm, series_name: seriesForm.series_name.trim() }
    const r = data.value.series.inferred
      ? await api.post('/admin/series/group/update', { ...payload, group_name: route.query.name })
      : await api.post(`/admin/series/${route.params.id}/update`, payload)
    ElMessage.success(r.msg); seriesDialogVisible.value = false
    if (r.data?.series_id) { await router.replace(`/admin/series/${r.data.series_id}`); await load() }
    else await load()
  } finally { savingSeries.value = false }
}
function openAddStation() {
  Object.assign(stationForm, { city_id: null, show_name: '', description: '' })
  stationDialogVisible.value = true
}
function setStationName(cityId) {
  const city = cities.value.find(item => Number(item.city_id) === Number(cityId))
  if (city) stationForm.show_name = `${data.value.series.series_name}·${city.city_name}站`
}
async function createStation() {
  if (!stationForm.city_id || !stationForm.show_name.trim()) return ElMessage.warning('请选择城市并填写站点名称')
  savingStation.value = true
  try {
    const payload = { ...stationForm, show_name: stationForm.show_name.trim() }
    const r = data.value.series.inferred
      ? await api.post('/admin/series/group/stations/create', { ...payload, group_name: route.query.name })
      : await api.post(`/admin/series/${route.params.id}/stations/create`, payload)
    ElMessage.success(r.msg); stationDialogVisible.value = false
    if (r.data?.series_id) { await router.replace(`/admin/series/${r.data.series_id}`); await load() }
    else await load()
  } finally { savingStation.value = false }
}
async function removeStation(showId) {
  const r = data.value.series.inferred
    ? await api.post(`/admin/series/group/stations/${showId}/delete`, { group_name: route.query.name })
    : await api.post(`/admin/series/${route.params.id}/stations/${showId}/delete`)
  ElMessage.success(r.msg)
  if (r.data?.became_single) router.push('/admin/shows')
  else await load()
}
function manageSessions(station) {
  const target = { path: `/admin/shows/${station.show_id}` }
  if (data.value.series.inferred) {
    target.query = { group_name: route.query.name }
  } else {
    // 显式保留来源巡演，站点场次维护和保存后返回时不依赖接口推断归属。
    target.query = { series_id: String(data.value.series.series_id) }
  }
  router.push(target)
}
async function confirmDeleteSeries() {
  try {
    await ElMessageBox.confirm('删除巡演将一并删除其全部站点、场次和票档；如已有订单则不能删除。确定继续？', '删除巡演', { type: 'warning' })
    const r = data.value.series.inferred
      ? await api.post('/admin/series/group/delete', { group_name: route.query.name })
      : await api.post(`/admin/series/${route.params.id}/delete`)
    ElMessage.success(r.msg); router.push('/admin/series')
  } catch { /* 用户取消确认，保持页面状态 */ }
}
onMounted(load)
</script>

<style scoped>
.page-head,.section-head { display:flex; align-items:center; justify-content:space-between; gap:16px; }
.page-head { margin:12px 0 18px; }
.page-head h2,.section-head h3 { margin:0 0 5px; }
.actions { display:flex; gap:8px; }
.section-head { margin-bottom:14px; }
.poster-editor { display:flex; align-items:center; gap:10px; flex-wrap:wrap; width:100%; }
.poster-editor .el-input { flex:1; min-width:220px; }
.poster-preview { width:56px; height:56px; border-radius:4px; }
.poster-tip { font-size:12px; color:#888; margin-top:4px; width:100%; }
</style>
