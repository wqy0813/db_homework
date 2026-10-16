<template>
  <el-button link @click="goBack">← {{ backText }}</el-button>
  <div v-if="data.show" v-loading="loading">
    <el-card shadow="never" class="head">
      <div class="head-inner">
        <div class="poster-big">
          <img v-if="data.show.poster_url" :src="data.show.poster_url" class="poster-img" />
          <div v-else class="poster-ph" style="font-size:60px">{{ data.show.show_name.slice(0,1) }}</div>
        </div>
        <div class="info">
          <h2>{{ data.show.show_name }}</h2>
          <p class="muted">📍 {{ data.show.city_name }} · {{ data.show.category_name }}
            <el-tag :type="tagType(data.summary.show_status)" style="margin-left:8px">{{ statusName(data.summary.show_status) }}</el-tag>
          </p>
          <p class="price-big">票价：¥{{ Math.round(data.summary.min_price||0) }} - ¥{{ Math.round(data.summary.max_price||0) }}</p>
          <p class="desc" v-if="(data.show.description||'').trim()">{{ data.show.description }}</p>
          <p class="muted" v-else>暂无演出介绍</p>
        </div>
      </div>
    </el-card>

    <h3 class="section-title">演出日期与票档（{{ data.sessions.length }} 个场次）</h3>
    <el-card v-for="se in data.sessions" :key="se.session_id" shadow="never" class="session">
      <div class="session-head">
        <div>
          <b>🗓 {{ fmt(se.show_time) }}</b>
          <span class="muted">　📍 {{ se.venue_name }}（{{ se.address }}）</span>
          <span class="muted" v-if="se.min_p">　💰 ¥{{ Math.round(se.min_p) }}-{{ Math.round(se.max_p) }}</span>
        </div>
        <el-tag :type="tagType(se.sale_status)">{{ se.sale_status === 1 && sessionHasSold(se.session_id) ? '预售（往期已售）' : statusName(se.sale_status) }}</el-tag>
      </div>
      <el-table :data="tiers[se.session_id]||[]" size="small" style="margin:10px 0">
        <el-table-column prop="tier_name" label="票档" />
        <el-table-column label="单价"><template #default="{row}">¥{{ row.price.toFixed(2) }}</template></el-table-column>
        <el-table-column prop="total_seats" label="总票数" width="80" />
        <el-table-column prop="sold_seats" label="已售" width="70" />
        <el-table-column prop="remain" label="余票" width="70" />
        <el-table-column label="状态" width="140">
          <template #default="{row}">
            <el-tag v-if="se.sale_status===1" type="warning">{{ row.sold_seats > 0 ? '预售（往期已售）' : '未开售' }}</el-tag>
            <el-tag v-else-if="se.sale_status===4" type="info">演出已结束</el-tag>
            <el-tag v-else-if="se.sale_status===3 || row.remain===0" type="info">该票档售罄</el-tag>
            <el-tag v-else type="success">在售</el-tag>
          </template>
        </el-table-column>
      </el-table>

      <!-- 已登录用户：根据场次销售状态显示购票 / 预售 / 售罄 / 结束 -->
      <template v-if="store.isUser">
        <template v-if="se.sale_status===2">
          <el-divider />
          <el-form label-width="80px" @submit.prevent>
            <el-row :gutter="16">
              <el-col :span="8">
                <el-form-item label="票档">
                  <el-select v-model="form[se.session_id].tier_id" placeholder="选择票档">
                    <el-option v-for="t in (tiers[se.session_id]||[])" :key="t.tier_id"
                      :value="t.tier_id" :disabled="t.remain===0"
                      :label="`${t.tier_name} ¥${Math.round(t.price)}${t.remain===0?'（售罄）':''}`" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item label="票数">
                  <!-- 手动 − / 输入框 / ＋ 三件套：步进按钮保留，键盘输入照常，
                       非法输入（0/7/12/-1/1.5/+-等）在失焦/回车时弹居中确认框 -->
                  <div class="count-ctrl">
                    <el-button size="small" @click="stepCount(se.session_id, -1)">−</el-button>
                    <el-input v-model="form[se.session_id].count_input" maxlength="3"
                              placeholder="1-6" style="width:70px"
                              @blur="onCountBlur(se.session_id)" @keyup.enter="onCountBlur(se.session_id)" />
                    <el-button size="small" @click="stepCount(se.session_id, 1)">＋</el-button>
                  </div>
                </el-form-item>
              </el-col>
              <el-col :span="10">
                <el-form-item label="地址">
                  <el-select v-model="form[se.session_id].address_id" placeholder="选择收货地址" style="width:200px">
                    <el-option v-for="a in addresses" :key="a.address_id" :value="a.address_id"
                      :label="`${a.receiver_name} ${a.phone} ${a.address_detail}`" />
                  </el-select>
                  <el-button size="small" plain style="margin-left:6px" @click="openAddAddress(se.session_id)">+ 新增地址</el-button>
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="购票人">
              <el-checkbox-group v-model="form[se.session_id].attendee_ids">
                <el-checkbox v-for="a in attendees" :key="a.attendee_id" :value="a.attendee_id" border>
                  {{ a.attendee_name }}（{{ idTypeName(a.id_type) }} {{ a.id_no }}）
                </el-checkbox>
              </el-checkbox-group>
              <el-button size="small" plain style="margin-left:10px" @click="openAddAttendee(se.session_id)">+ 新增购票人</el-button>
            </el-form-item>
            <el-button type="danger" :loading="buying"
                       @click="buy(se)">提交购票请求</el-button>
            <span class="muted" style="margin-left:10px">单笔最多 6 张，每位观演人同一场次限购 1 张（勾选人数须等于票数）</span>
          </el-form>
        </template>

        <template v-else-if="se.sale_status===1">
          <el-alert type="warning" :closable="false" style="margin-top:10px" show-icon>
            <template #title>
              <span v-if="sessionHasSold(se.session_id)">
                本场次已完成首轮售票，下一轮开售时间：{{ fmt(se.sale_start) }}，开售后方可购票
              </span>
              <span v-else>
                该场次预售中，开售时间：{{ fmt(se.sale_start) }}，开售后方可购票
              </span>
            </template>
            <div style="margin-top:6px;display:flex;gap:8px;flex-wrap:wrap;align-items:center">
              <el-button size="small" @click="openAddAddress(se.session_id)">提前完善收货地址</el-button>
              <el-button size="small" @click="openAddAttendee(se.session_id)">提前完善购票人</el-button>
              <span class="muted" v-if="sessionHasSold(se.session_id)">本场次已有历史销售记录（已售 {{ sessionSoldSeats(se.session_id) }} 张），提前填写资料不代表购票成功，开售前不能提交订单，也不会占用库存</span>
              <span class="muted" v-else>提前填写资料不代表购票成功，开售前不能提交订单，也不会占用库存</span>
            </div>
          </el-alert>
        </template>

        <el-alert v-else-if="se.sale_status===3" type="info" :closable="false" title="该场次已售罄" style="margin-top:10px" />
        <el-alert v-else type="info" :closable="false" title="该场次已结束" style="margin-top:10px" />
      </template>

      <el-alert v-else type="info" :closable="false" style="margin-top:10px">
        <router-link :to="{ path: '/login', query: { intent: 'login' } }">登录</router-link> 后即可购票
      </el-alert>
    </el-card>
  </div>

  <AddressDialog v-model="addrDialog" @saved="onAddressSaved" />
  <AttendeeDialog v-model="attDialog" @saved="onAttendeeSaved" />
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'
import { useStore, STATUS_NAMES, ID_TYPE, buyFormBySession } from '../store'
import AddressDialog from '../components/AddressDialog.vue'
import AttendeeDialog from '../components/AttendeeDialog.vue'

const route = useRoute()
const router = useRouter()
const fromSeries = computed(() => Boolean(route.query.from_series || route.query.from_group || data.value.show?.series_id))
const backPath = computed(() => {
  if (route.query.from_group) return { path: '/series/group', query: { name: route.query.from_group } }
  if (route.query.from_series) return `/series/${route.query.from_series}`
  if (data.value.show?.series_id) return `/series/${data.value.show.series_id}`
  return '/series'
})
const store = useStore()
const data = ref({ show: null, sessions: [], images: [], tiers: {}, summary: {} })
const loading = ref(false)
const buying = ref(false)
const addresses = ref([])
const attendees = ref([])
// form 提到 store 里（按 session_id 隔离），导航到别的演出再回来时不会清空
const form = buyFormBySession
const tiers = ref({})
const addrDialog = ref(false)
const attDialog = ref(false)
const pendingSessionId = ref(null)
let profileRequest = 0
let disposed = false

const statusName = (s) => STATUS_NAMES[s]
const idTypeName = (t) => ID_TYPE[t]
const tagType = (s) => ({ 1: 'warning', 2: 'success', 3: 'info', 4: 'info' }[s])
const fmt = (s) => s ? s.replace('T', ' ').slice(0, 16) : ''
const sessionSoldSeats = (sessionId) => (tiers.value[sessionId] || []).reduce((acc, t) => acc + (t.sold_seats || 0), 0)
const sessionHasSold = (sessionId) => sessionSoldSeats(sessionId) > 0

// 返回目标按来路决定：从巡演页/站点进来的回巡演，独立单场演出回巡演列表；直接输入网址时按 series_id 兜底。
const backText = computed(() => fromSeries.value ? '返回巡演详情' : '返回演出巡演')
// 来源标签已经是目标巡演或列表时关闭当前标签，否则在当前标签返回所属页面。
function goBack() {
  const target = new URL(router.resolve(backPath.value).href, window.location.href)
  try {
    const opener = window.opener
    if (opener && !opener.closed && opener.location.origin === target.origin && opener.location.hash === target.hash) {
      window.close()
      setTimeout(() => { if (!window.closed) router.replace(backPath.value) }, 200)
      return
    }
  } catch (e) { /* 来源页跨域或已关闭时直接返回所属页面 */ }
  router.replace(backPath.value)
}

async function load() {
  loading.value = true
  try {
    const r = await api.get('/shows/' + route.params.id)
    if (disposed) return
    data.value = r.data
    tiers.value = r.data.tiers
    // 把演出名写进浏览器标签标题，多标签浏览时分得清
    if (r.data.show) document.title = `${r.data.show.show_name} - 演出票务系统`
    // 保留已有选择：仅对尚未建立过表单的场次初始化，避免刷新/重新加载时清空票档/票数/地址/购票人
    r.data.sessions.forEach(se => {
      if (!form[se.session_id]) {
        form[se.session_id] = { tier_id: null, count: 1, count_input: '1', address_id: null, attendee_ids: [] }
      } else if (form[se.session_id].count_input === undefined) {
        // 兼容旧草稿结构
        form[se.session_id].count_input = String(form[se.session_id].count)
      }
    })
    if (store.isUser) await loadProfile()
    applyDefaultAddressForNewSessions()
  } finally { loading.value = false }
}

async function loadProfile() {
  const requestId = ++profileRequest
  const userId = store.user?.id
  const [a, t] = await Promise.all([api.get('/addresses'), api.get('/attendees')])
  if (disposed || requestId !== profileRequest || !store.isUser || store.user.id !== userId) return
  addresses.value = a.data.list
  attendees.value = t.data.list
}

// 第一次加载时为每个场次自动选默认地址；用户手动改过的不再覆盖
function applyDefaultAddressForNewSessions() {
  if (disposed || !addresses.value.length) return
  const def = addresses.value.find(x => x.is_default) || addresses.value[0]
  Object.keys(form).forEach(sid => {
    if (form[sid].address_id == null) form[sid].address_id = def.address_id
  })
}

function openAddAddress(sessionId) {
  pendingSessionId.value = sessionId
  addrDialog.value = true
}
function openAddAttendee(sessionId) {
  pendingSessionId.value = sessionId
  attDialog.value = true
}
async function onAddressSaved({ address_id }) {
  await loadProfile()
  if (pendingSessionId.value != null && form[pendingSessionId.value]) {
    form[pendingSessionId.value].address_id = address_id
  }
}
async function onAttendeeSaved({ attendee_id }) {
  await loadProfile()
  if (pendingSessionId.value != null && form[pendingSessionId.value]) {
    const f = form[pendingSessionId.value]
    if (!f.attendee_ids.includes(attendee_id)) f.attendee_ids.push(attendee_id)
  }
}

function validateCount(n) {
  if (n === null || n === undefined || n === '') return '请填写票数'
  const v = Number(n)
  if (!Number.isInteger(v) || v < 1 || v > 6) return '单笔最多 6 张，请输入 1-6 之间的整数'
  return null
}

// 把输入框内容同步进 count；非法时返回错误文案（不弹窗，由调用方决定提示方式）
function applyCount(sid) {
  const f = form[sid]
  if (!f) return null
  const err = validateCount(String(f.count_input ?? '').trim())
  if (err) return err
  f.count = parseInt(f.count_input, 10)
  f.count_input = String(f.count)
  return null
}

// 票数错误统一用居中模态框，用户点"确定"关闭；
// 防重入锁：blur 和随后的点击（提交/步进）都可能触发校验，避免连弹两个框
let countDialogOpen = false
function showCountError(msg) {
  if (countDialogOpen) return
  countDialogOpen = true
  ElMessageBox.alert(msg, '票数有误', {
    confirmButtonText: '确定',
    type: 'warning',
    center: true
  }).catch(() => {}).finally(() => { countDialogOpen = false })
}

// 校验失败时的统一处理：清空输入框里的错误内容，再弹确认框
function rejectCount(sid, err) {
  const f = form[sid]
  if (f) f.count_input = ''
  showCountError(err)
}

// 失焦/回车校验：非法输入弹居中确认框
function onCountBlur(sid) {
  const err = applyCount(sid)
  if (err) rejectCount(sid, err)
}

// −/＋ 步进：先把输入框当前值校验同步，再在 1-6 范围内步进
function stepCount(sid, delta) {
  const f = form[sid]
  if (!f) return
  const err = applyCount(sid)
  if (err) return rejectCount(sid, err)
  const next = Math.min(6, Math.max(1, f.count + delta))
  f.count = next
  f.count_input = String(next)
}

async function buy(se) {
  const f = form[se.session_id]
  if (!f.tier_id) return ElMessage.warning('请选择票档')
  // 提交前再校验一次输入框（覆盖"输了非法值直接点提交"的情况）
  const cntErr = applyCount(se.session_id) || validateCount(f.count)
  if (cntErr) return rejectCount(se.session_id, cntErr)
  if (!f.address_id) return ElMessage.warning('请选择收货地址；如尚未维护，可点击“新增地址”')
  if (f.attendee_ids.length !== f.count) {
    return ElMessageBox.alert(`票数为 ${f.count} 张，但勾选了 ${f.attendee_ids.length} 位购票人。规则：每人限购 1 张，购票人数必须等于票数。`)
  }
  buying.value = true
  try {
    const r = await api.post('/buy', {
      show_id: Number(route.params.id),
      session_id: se.session_id,
      tier_id: f.tier_id,
      count: f.count,
      address_id: f.address_id,
      attendee_ids: f.attendee_ids
    })
    ElMessage.success(r.msg)
    f.attendee_ids = [] // 本次已下单的购票人清空，票档/票数/地址保留以便继续操作
    await load()
  } catch (e) { /* 拦截器已提示 */ } finally { buying.value = false }
}

watch(() => [store.user?.role, store.user?.id], async ([role]) => {
  if (role === 'user' && data.value.show) {
    try {
      await loadProfile()
      applyDefaultAddressForNewSessions()
    } catch (e) { /* 请求拦截器已提示 */ }
  } else if (role !== 'user') {
    profileRequest++
    addresses.value = []
    attendees.value = []
  }
})
onBeforeUnmount(() => { disposed = true; profileRequest++ })
onMounted(load)
</script>

<style scoped>
.count-ctrl { display: inline-flex; align-items: center; gap: 4px; }
.head { margin-top: 10px; }
.head-inner { display: flex; gap: 22px; }
.poster-big { width: 160px; height: 210px; border-radius: 10px; overflow: hidden; flex: 0 0 auto; background:#eee; }
.info h2 { margin-bottom: 10px; }
.desc { color: #555; line-height: 1.7; margin-top: 12px; white-space: pre-line; }
.price-big { color: #e94b64; font-weight: bold; font-size: 18px; margin: 10px 0; }
.session { margin-bottom: 14px; }
.session-head { display: flex; justify-content: space-between; align-items: center; }
</style>
