<template>
  <el-button link @click="$router.push('/admin/shows')">← 返回演出管理</el-button>
  <div v-loading="loading">
    <h2>演出维护：{{ data.show && data.show.show_name }}（ID {{ data.show && data.show.show_id }}）</h2>

    <el-card shadow="never" style="margin-bottom:16px">
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
      <h3 style="margin-bottom:12px">演出介绍图片</h3>
      <el-form inline @submit.prevent>
        <el-input v-model="imageForm.image_url" placeholder="图片 URL" style="width:360px" />
        <el-input-number v-model="imageForm.sort_no" :min="0" :max="127" style="width:130px" />
        <el-button type="primary" @click="addImage">添加图片</el-button>
      </el-form>
      <el-table :data="data.images || []" size="small" style="margin-top:10px">
        <el-table-column prop="sort_no" label="顺序" width="70" />
        <el-table-column prop="image_url" label="图片地址" min-width="320" />
        <el-table-column label="预览" width="100">
          <template #default="{row}"><el-image :src="row.image_url" style="width:56px;height:56px" fit="cover" /></template>
        </el-table-column>
        <el-table-column label="操作" width="90">
          <template #default="{row}">
            <el-button size="small" type="danger" plain @click="delImage(row.image_id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never" style="margin-bottom:16px">
      <h3 style="margin-bottom:12px">添加演出场次（演出日期）</h3>
      <el-form inline @submit.prevent>
        <el-form-item>
          <el-select v-model="seForm.venue_id" placeholder="选择场馆（本城市）" style="width:230px">
            <el-option v-for="v in data.venues" :key="v.venue_id" :value="v.venue_id" :label="v.venue_name" />
          </el-select>
        </el-form-item>
        <el-form-item label="开演时间"><el-date-picker v-model="seForm.show_time" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" /></el-form-item>
        <el-form-item label="开售时间">
          <span>{{ saleStartPreview || '选择开演时间后自动计算（开演前30天）' }}</span>
        </el-form-item>
        <el-button type="danger" @click="addSession">添加场次</el-button>
      </el-form>
    </el-card>

    <h3 class="section-title">已有场次与票档</h3>
    <el-card v-for="se in data.sessions" :key="se.session_id" shadow="never" style="margin-bottom:14px">
      <div class="sess-head">
        <div>
          <b>🗓 {{ fmt(se.show_time) }}</b>
          <span class="muted">　📍 {{ se.venue_name }}　开售 {{ fmt(se.sale_start) }}</span>
        </div>
        <div>
          <el-tag :type="tagType(se.sale_status)">{{ STATUS_NAMES[se.sale_status] }}</el-tag>
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
        <el-table-column label="操作" width="90">
          <template #default="{row}">
            <el-popconfirm title="确认删除该票档？" @confirm="delTier(row.tier_id)">
              <template #reference><el-button size="small" type="danger" plain>删除</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
      <el-form inline @submit.prevent>
        <el-input :model-value="(tierForm[se.session_id]||{}).tier_name"
                  @update:model-value="setTier(se.session_id,'tier_name',$event)"
                  placeholder="票档名称（如 VIP 880）" style="width:200px" />
        <el-input-number :model-value="(tierForm[se.session_id]||{}).price"
                  @update:model-value="setTier(se.session_id,'price',$event)"
                  :min="1" style="width:130px" />
        <el-input-number :model-value="(tierForm[se.session_id]||{}).total_seats"
                  @update:model-value="setTier(se.session_id,'total_seats',$event)"
                  :min="1" style="width:130px" />
        <el-button type="danger" @click="addTier(se.session_id)">为该场次添加票档</el-button>
      </el-form>
    </el-card>
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
const data = ref({ show: {}, images: [], sessions: [], venues: [], tiers: {} })
const cities = ref([])
const categories = ref([])
const showForm = reactive({ show_name: '', category_id: null, city_id: null, poster_url: '', description: '' })
const imageForm = reactive({ image_url: '', sort_no: 0 })
const seForm = reactive({ venue_id: null, show_time: null })
const tierForm = reactive({})
const tagType = (s) => ({ 1: 'warning', 2: 'success', 3: 'info', 4: 'info' }[s])
const saleStartPreview = computed(() => {
  if (!seForm.show_time) return ''
  const [date, time = '00:00:00'] = String(seForm.show_time).replace('T', ' ').split(' ')
  const value = new Date(`${date}T${time}Z`)
  if (Number.isNaN(value.getTime())) return ''
  value.setUTCDate(value.getUTCDate() - 30)
  return value.toISOString().slice(0, 16).replace('T', ' ')
})
// 兼容 Date 与字符串（v-model 已配 value-format 为字符串，此处兜底）
function pad(n) { return String(n).padStart(2, '0') }
function fmt(s) {
  if (!s) return ''
  if (s instanceof Date && !isNaN(s)) {
    return `${s.getFullYear()}-${pad(s.getMonth() + 1)}-${pad(s.getDate())} ${pad(s.getHours())}:${pad(s.getMinutes())}`
  }
  return String(s).replace('T', ' ').slice(0, 16)
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
    r.data.sessions.forEach(se => { tierForm[se.session_id] = { tier_name: '', price: 100, total_seats: 500 } })
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
async function addImage() {
  if (!imageForm.image_url.trim()) return ElMessage.warning('请输入图片 URL')
  const r = await api.post(`/admin/shows/${route.params.id}/images/add`, { ...imageForm })
  ElMessage.success(r.msg); Object.assign(imageForm, { image_url: '', sort_no: 0 }); await load()
}
async function delImage(id) {
  const r = await api.post(`/admin/shows/${route.params.id}/images/${id}/delete`)
  ElMessage.success(r.msg); await load()
}
async function addSession() {
  if (!seForm.venue_id || !seForm.show_time) return ElMessage.warning('请选择场馆和开演时间')
  const r = await api.post('/admin/session/create', {
    show_id: Number(route.params.id),
    venue_id: seForm.venue_id,
    show_time: fmt(seForm.show_time) + ':00'
  })
  ElMessage.success(r.msg)
  Object.assign(seForm, { venue_id: null, show_time: null })
  load()
}
function setTier(session_id, key, val) {
  if (!tierForm[session_id]) tierForm[session_id] = {}
  tierForm[session_id][key] = val
}
async function addTier(session_id) {
  const f = tierForm[session_id] || {}
  if (!f.tier_name || !f.price || !f.total_seats) return ElMessage.warning('请填写票档名称、金额、票数')
  const r = await api.post('/admin/tier/create', { show_id: Number(route.params.id), session_id, ...f })
  ElMessage.success(r.msg)
  f.tier_name = ''
  load()
}
async function delSession(id) { await api.post(`/admin/session/${id}/delete`, { show_id: Number(route.params.id) }); ElMessage.success('已删除'); load() }
async function delTier(id) { await api.post(`/admin/tier/${id}/delete`, { show_id: Number(route.params.id) }); ElMessage.success('已删除'); load() }

onMounted(load)
</script>

<style scoped>
.sess-head { display: flex; justify-content: space-between; align-items: center; }
.sess-head .el-form { margin-top: 10px; }
.poster-editor { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.poster-editor .el-input { width: 300px; }
.poster-preview { width: 42px; height: 42px; border-radius: 4px; }
</style>
