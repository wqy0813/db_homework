<template>
  <el-button link @click="$router.push(backPath)">← 返回{{ route.query.group_name || route.query.series_id || data.show?.series_id ? '巡演详情' : '演出管理' }}</el-button>
  <div v-loading="loading">
    <h2>{{ route.query.group_name || route.query.series_id || data.show?.series_id ? '巡演站点维护' : '演出维护' }}：{{ data.show && data.show.show_name }}（ID {{ data.show && data.show.show_id }}）</h2>

    <el-card v-if="!route.query.group_name" shadow="never" style="margin-bottom:16px">
      <h3 style="margin-bottom:12px">演出基本信息</h3>
      <el-form inline @submit.prevent>
        <el-form-item label="名称"><el-input v-model="showForm.show_name" style="width:240px" /></el-form-item>
        <el-form-item label="类型">
          <el-select v-model="showForm.category_id" style="width:150px">
            <el-option v-for="c in categories" :key="c.category_id" :value="c.category_id" :label="c.category_name" />
          </el-select>
        </el-form-item>
        <el-form-item label="城市">
          <el-select v-model="showForm.city_id" style="width:140px">
            <el-option v-for="c in cities" :key="c.city_id" :value="c.city_id" :label="c.city_name" />
          </el-select>
        </el-form-item>
        <el-form-item label="海报">
          <div class="poster-editor">
            <el-upload
              :show-file-list="false"
              accept="image/jpeg,image/png,image/gif,image/webp"
              :http-request="uploadPoster"
            >
              <el-button>选择并上传</el-button>
            </el-upload>
            <el-input v-model="showForm.poster_url" placeholder="也可直接填写图片 URL" />
            <el-image v-if="showForm.poster_url" :src="showForm.poster_url" fit="cover" class="poster-preview" />
          </div>
        </el-form-item>
        <el-form-item label="介绍"><el-input v-model="showForm.description" type="textarea" style="width:420px" /></el-form-item>
        <el-button type="primary" @click="saveShow">保存基本信息</el-button>
      </el-form>
    </el-card>

    <el-card shadow="never" style="margin-bottom:16px">
      <h3 style="margin-bottom:12px">添加演出场次（演出日期）</h3>
      <el-form inline @submit.prevent>
        <el-form-item>
          <el-select v-model="seForm.venue_id" placeholder="选择场馆（本城市）" style="width:230px">
            <el-option v-for="v in data.venues" :key="v.venue_id" :value="v.venue_id"
                       :label="`${v.venue_name}（容量 ${v.capacity} 张）`" />
          </el-select>
        </el-form-item>
        <el-form-item label="开演日期">
          <el-date-picker v-model="seForm.show_date" type="date" value-format="YYYY-MM-DD"
                          :disabled-date="disablePastDate" />
        </el-form-item>
        <el-form-item label="开演时间">
          <el-time-picker v-model="seForm.show_clock" format="HH:mm" value-format="HH:mm"
                          placeholder="选择时间（24小时制）" />
        </el-form-item>
        <el-form-item label="开售时间">
          <span>{{ saleStartPreview || '选择开演时间后自动计算（开演前30天）' }}</span>
        </el-form-item>
        <el-button type="danger" @click="addSession">添加场次</el-button>
      </el-form>
      <el-alert v-if="selectedAddVenue" type="info" :closable="false" style="margin-top:8px"
                :title="`场馆总容量 ${selectedAddVenue.capacity} 张；新场次当前已分配 0 张`" />
    </el-card>

    <h3 class="section-title">已有场次与票档</h3>
    <el-card v-for="se in data.sessions" :key="se.session_id" shadow="never" style="margin-bottom:14px">
      <div class="sess-head">
        <div>
          <b>🗓 {{ fmt(se.show_time) }}</b>
          <span class="muted">　📍 {{ se.venue_name }}　开售 {{ fmt(se.sale_start) }}</span>
          <span class="muted">　场馆容量 {{ se.capacity }} 张；已分配 {{ se.assigned_seats }} 张</span>
        </div>
        <div>
          <el-tag :type="tagType(se.sale_status)">{{ STATUS_NAMES[se.sale_status] }}</el-tag>
          <el-button size="small" type="primary" plain style="margin-left:8px" @click="openEditSession(se)">修改场次</el-button>
          <el-popconfirm title="删除该场次将一并删除其票档，确认？" @confirm="delSession(se.session_id)">
            <template #reference><el-button size="small" type="danger" plain style="margin-left:8px">删除场次</el-button></template>
          </el-popconfirm>
        </div>
      </div>
      <el-table :data="data.tiers[se.session_id]||[]" size="small" style="margin:10px 0">
        <el-table-column prop="tier_name" label="票档" />
        <el-table-column label="金额"><template #default="{row}">¥{{ Number(row.price).toFixed(2) }}</template></el-table-column>
        <el-table-column prop="total_seats" label="总票数" width="80" />
        <el-table-column prop="sold_seats" label="已售" width="70" />
        <el-table-column prop="remain" label="余票" width="70" />
      </el-table>
    </el-card>

    <el-dialog v-model="editDialogVisible" title="修改场次" width="850px" :close-on-click-modal="false">
      <el-form label-width="100px" @submit.prevent>
        <el-form-item label="场馆">
          <el-select v-model="editForm.venue_id" style="width:100%">
            <el-option v-for="v in data.venues" :key="v.venue_id" :value="v.venue_id"
                       :label="`${v.venue_name}（容量 ${v.capacity} 张）`" />
          </el-select>
        </el-form-item>
        <el-form-item label="开演时间">
          <el-date-picker v-model="editForm.show_time" type="datetime" value-format="YYYY-MM-DD HH:mm:ss"
                          :disabled-date="disablePastDate" style="width:100%" />
        </el-form-item>
        <el-form-item label="开售时间">
          <span>{{ editSaleStartPreview || '选择开演时间后自动计算' }}</span>
        </el-form-item>
      </el-form>

      <el-alert :type="editOverCapacity ? 'error' : 'info'" :closable="false" style="margin-bottom:12px"
                :title="`场馆总容量 ${editVenueCapacity} 张；票档已分配 ${editAllocatedSeats} 张`" />
      <el-table :data="editForm.tiers" size="small" border>
        <el-table-column label="票档名称" min-width="170">
          <template #default="{row}">
            <el-input v-model="row.tier_name" :disabled="Number(row.sold_seats) > 0" />
          </template>
        </el-table-column>
        <el-table-column label="票价（元）" width="175">
          <template #default="{row}">
            <el-input-number v-model="row.price" :min="0.01" :precision="2"
                             :disabled="Number(row.sold_seats) > 0" style="width:150px" />
          </template>
        </el-table-column>
        <el-table-column label="总票数（张）" width="185">
          <template #default="{row}">
            <el-input-number v-model="row.total_seats" :min="Math.max(1, Number(row.sold_seats))"
                             :disabled="Number(row.sold_seats) > 0" style="width:155px" />
          </template>
        </el-table-column>
        <el-table-column prop="sold_seats" label="已售数量" width="100" />
        <el-table-column label="提示" min-width="150">
          <template #default="{row}">
            <el-tooltip v-if="Number(row.sold_seats) > 0" content="该票档已售不为 0" placement="top">
              <el-tag type="info">该票档已售不为 0</el-tag>
            </el-tooltip>
            <span v-else class="muted">可编辑</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="85">
          <template #default="{row, $index}">
            <el-tooltip v-if="Number(row.sold_seats) > 0" content="已售票档不能删除" placement="top">
              <el-button size="small" type="danger" link disabled>删除</el-button>
            </el-tooltip>
            <el-button v-else size="small" type="danger" link @click="removeExistingTier($index)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="edit-tier-header">
        <b>新增票档</b>
        <el-button size="small" @click="addEditTier">添加一行</el-button>
      </div>
      <el-table v-if="editForm.new_tiers.length" :data="editForm.new_tiers" size="small" border>
        <el-table-column label="票档名称" min-width="170">
          <template #default="{row}"><el-input v-model="row.tier_name" placeholder="如 VIP" /></template>
        </el-table-column>
        <el-table-column label="票价（元）" width="175">
          <template #default="{row}"><el-input-number v-model="row.price" :min="0.01" :precision="2" style="width:150px" /></template>
        </el-table-column>
        <el-table-column label="总票数（张）" width="185">
          <template #default="{row}"><el-input-number v-model="row.total_seats" :min="1" style="width:155px" /></template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ $index }"><el-button type="danger" link @click="removeEditTier($index)">移除</el-button></template>
        </el-table-column>
      </el-table>
      <el-alert v-if="editOverCapacity" type="error" :closable="false" style="margin-top:10px"
                title="票档总票数超过场馆容量" />

      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSaving" @click="saveSessionEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../../api'
import { STATUS_NAMES } from '../../store'

const route = useRoute()
const loading = ref(false)
const data = ref({ show: {}, sessions: [], venues: [], tiers: {} })
const backPath = computed(() => route.query.group_name
  ? { path: '/admin/series/group', query: { name: route.query.group_name } }
  : route.query.series_id ? `/admin/series/${route.query.series_id}`
    : data.value.show?.series_id ? `/admin/series/${data.value.show.series_id}` : '/admin/shows')
const cities = ref([])
const categories = ref([])
const showForm = reactive({ show_name: '', category_id: null, city_id: null, poster_url: '', description: '' })
const seForm = reactive({ venue_id: null, show_date: null, show_clock: null })
const editDialogVisible = ref(false)
const editSaving = ref(false)
const editForm = reactive({ session_id: null, venue_id: null, show_time: null, tiers: [], new_tiers: [], delete_tier_ids: [] })
const tagType = (s) => ({ 1: 'warning', 2: 'success', 3: 'info', 4: 'info' }[s])
const selectedAddVenue = computed(() => data.value.venues.find(v => Number(v.venue_id) === Number(seForm.venue_id)))
const editVenue = computed(() => data.value.venues.find(v => Number(v.venue_id) === Number(editForm.venue_id)))
const editVenueCapacity = computed(() => Number(editVenue.value?.capacity || 0))
const editAllocatedSeats = computed(() => [...editForm.tiers, ...editForm.new_tiers]
  .reduce((sum, tier) => sum + (Number(tier.total_seats) || 0), 0))
const editOverCapacity = computed(() => editVenueCapacity.value > 0 && editAllocatedSeats.value > editVenueCapacity.value)
const newSessionShowTime = computed(() => seForm.show_date && seForm.show_clock
  ? `${seForm.show_date} ${seForm.show_clock}:00` : '')
const saleStartPreview = computed(() => saleStartDisplay(newSessionShowTime.value))
const editSaleStartPreview = computed(() => saleStartDisplay(editForm.show_time))
// 兼容 Date 与字符串（v-model 已配 value-format 为字符串，此处兜底）
function pad(n) { return String(n).padStart(2, '0') }
function asLocalDate(value) {
  if (!value) return null
  const raw = String(value).replace('T', ' ')
  const date = new Date(raw.replace(' ', 'T')).getTime()
  if (Number.isNaN(date)) return null
  return new Date(date)
}
function fmt(s) {
  if (!s) return ''
  if (s instanceof Date && !isNaN(s)) {
    return `${s.getFullYear()}-${pad(s.getMonth() + 1)}-${pad(s.getDate())} ${pad(s.getHours())}:${pad(s.getMinutes())}`
  }
  return String(s).replace('T', ' ').slice(0, 16)
}
function saleStartDisplay(value) {
  const showTime = asLocalDate(value)
  if (!showTime) return ''
  const saleStart = new Date(showTime)
  saleStart.setDate(saleStart.getDate() - 30)
  if (saleStart < new Date()) saleStart.setHours(0, 0, 0, 0)
  return fmt(saleStart)
}
function disablePastDate(date) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return date < today
}
function requestErrorMessage(err, fallback) {
  return err?.msg || err?.response?.data?.msg || err?.message || fallback
}

async function load() {
  loading.value = true
  try {
    const r = await api.get('/admin/shows/' + route.params.id)
    data.value = r.data
    Object.assign(showForm, {
      show_name: r.data.show.show_name || '', category_id: r.data.show.category_id,
      city_id: r.data.show.city_id, poster_url: r.data.show.poster_url || '',
      description: r.data.show.description || ''
    })
    const dict = await api.get('/dicts')
    cities.value = dict.data.cities
    categories.value = dict.data.categories
  } finally { loading.value = false }
}
async function saveShow() {
  if (!showForm.show_name || !showForm.category_id || !showForm.city_id) return ElMessage.warning('请填写名称、类型和城市')
  const r = await api.post('/admin/shows/' + route.params.id + '/update', { ...showForm })
  ElMessage.success(r.msg); await load()
}
async function uploadPoster({ file, onSuccess, onError }) {
  const body = new FormData()
  body.append('poster', file)
  try {
    const r = await api.post('/admin/uploads/poster', body)
    showForm.poster_url = r.data.url
    ElMessage.success(r.msg)
    onSuccess(r)
  } catch (err) {
    onError(err)
  }
}
async function addSession() {
  if (!seForm.venue_id || !seForm.show_date || !seForm.show_clock) return ElMessage.warning('请选择场馆、开演日期和时间')
  const showTimeValue = `${seForm.show_date} ${seForm.show_clock}:00`
  const showTime = asLocalDate(showTimeValue)
  if (!showTime || showTime <= new Date()) return ElMessage.warning('开演时间必须晚于当前时间')
  try {
    const r = await api.post('/admin/session/create', {
      show_id: Number(route.params.id), venue_id: seForm.venue_id,
      show_time: showTimeValue
    })
    ElMessage.success(r.msg)
    Object.assign(seForm, { venue_id: null, show_date: null, show_clock: null })
    await load()
  } catch (err) {
    ElMessage.error(requestErrorMessage(err, '添加场次失败'))
  }
}
function openEditSession(session) {
  editForm.session_id = session.session_id
  editForm.venue_id = session.venue_id
  editForm.show_time = fmt(session.show_time) + ':00'
  editForm.tiers = (data.value.tiers[session.session_id] || []).map(tier => ({
    tier_id: tier.tier_id, tier_name: tier.tier_name, price: Number(tier.price),
    total_seats: Number(tier.total_seats), sold_seats: Number(tier.sold_seats)
  }))
  editForm.new_tiers = []
  editForm.delete_tier_ids = []
  editDialogVisible.value = true
}
function addEditTier() {
  const available = Math.max(1, editVenueCapacity.value - editAllocatedSeats.value)
  editForm.new_tiers.push({ tier_name: '', price: 100, total_seats: available, sold_seats: 0 })
}
function removeEditTier(index) { editForm.new_tiers.splice(index, 1) }
function removeExistingTier(index) {
  const [tier] = editForm.tiers.splice(index, 1)
  if (tier) editForm.delete_tier_ids.push(tier.tier_id)
}
async function saveSessionEdit() {
  if (!editForm.venue_id || !editForm.show_time) return ElMessage.warning('请选择场馆和开演时间')
  const showTime = asLocalDate(editForm.show_time)
  if (!showTime || showTime <= new Date()) return ElMessage.warning('开演时间必须晚于当前时间')
  if (editOverCapacity.value) return ElMessage.warning('票档总票数超过场馆容量')
  const allTiers = [...editForm.tiers, ...editForm.new_tiers]
  for (const tier of allTiers) {
    if (!tier.tier_name?.trim() || !Number.isFinite(Number(tier.price)) || Number(tier.price) <= 0 ||
        !Number.isInteger(Number(tier.total_seats)) || Number(tier.total_seats) <= 0) {
      return ElMessage.warning('请填写完整票档，并确保票价和总票数大于 0')
    }
    if (Number(tier.total_seats) < Number(tier.sold_seats || 0)) {
      return ElMessage.warning('总票数不能小于已售数量')
    }
  }
  editSaving.value = true
  try {
    const r = await api.post(`/admin/session/${editForm.session_id}/update`, {
      show_id: Number(route.params.id), venue_id: Number(editForm.venue_id),
      show_time: fmt(editForm.show_time) + ':00',
      tiers: editForm.tiers.map(({ tier_id, tier_name, price, total_seats }) => ({
        tier_id, tier_name, price, total_seats
      })),
      delete_tier_ids: editForm.delete_tier_ids,
      new_tiers: editForm.new_tiers.map(({ tier_name, price, total_seats }) => ({
        tier_name, price, total_seats
      }))
    })
    ElMessage.success(r.msg)
    editDialogVisible.value = false
    await load()
  } catch (err) {
    ElMessage.error(requestErrorMessage(err, '保存场次失败'))
  } finally {
    editSaving.value = false
  }
}
async function delSession(id) { await api.post(`/admin/session/${id}/delete`, { show_id: Number(route.params.id) }); ElMessage.success('已删除'); load() }

onMounted(load)
</script>

<style scoped>
.sess-head { display: flex; justify-content: space-between; align-items: center; }
.edit-tier-header { display: flex; align-items: center; justify-content: space-between; margin: 18px 0 8px; }
.poster-editor { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.poster-editor .el-input { width: 300px; }
.poster-preview { width: 42px; height: 42px; border-radius: 4px; }
</style>
