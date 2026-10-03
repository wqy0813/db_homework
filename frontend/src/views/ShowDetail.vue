<template>
  <el-button link @click="$router.push('/series')">← 返回巡演列表</el-button>
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
          <p class="desc">{{ data.show.description }}</p>
        </div>
      </div>
    </el-card>

    <h3 class="section-title">演出介绍（图片）</h3>
    <div class="img-row">
      <el-image v-for="(im, i) in data.images" :key="i" :src="im.image_url"
                style="width:200px;height:130px;border-radius:10px" fit="cover"
                :preview-src-list="data.images.map(x=>x.image_url)" :initial-index="i" />
      <span v-if="data.images.length===0" class="muted">暂无介绍图片</span>
    </div>

    <h3 class="section-title">演出日期与票档（{{ data.sessions.length }} 个场次）</h3>
    <el-card v-for="se in data.sessions" :key="se.session_id" shadow="never" class="session">
      <div class="session-head">
        <div>
          <b>🗓 {{ fmt(se.show_time) }}</b>
          <span class="muted">　📍 {{ se.venue_name }}（{{ se.address }}）</span>
          <span class="muted" v-if="se.min_p">　💰 ¥{{ Math.round(se.min_p) }}-{{ Math.round(se.max_p) }}</span>
        </div>
        <el-tag :type="tagType(se.sale_status)">{{ statusName(se.sale_status) }}</el-tag>
      </div>
      <el-table :data="tiers[se.session_id]||[]" size="small" style="margin:10px 0">
        <el-table-column prop="tier_name" label="票档" />
        <el-table-column label="单价"><template #default="{row}">¥{{ row.price.toFixed(2) }}</template></el-table-column>
        <el-table-column prop="total_seats" label="总票数" width="80" />
        <el-table-column prop="sold_seats" label="已售" width="70" />
        <el-table-column prop="remain" label="余票" width="70" />
        <el-table-column label="状态" width="120">
          <template #default="{row}">
            <el-tag v-if="se.sale_status===1" type="warning">未开售</el-tag>
            <el-tag v-else-if="se.sale_status===3 || row.remain===0" type="info">该票档售罄</el-tag>
            <el-tag v-else type="success">在售</el-tag>
          </template>
        </el-table-column>
      </el-table>

      <!-- 购票区 -->
      <template v-if="store.isUser">
        <template v-if="se.sale_status===2">
          <el-divider />
          <el-form label-width="70px" @submit.prevent>
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
                  <el-select v-model="form[se.session_id].count">
                    <el-option v-for="i in 6" :key="i" :value="i" :label="i+' 张'" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="10">
                <el-form-item label="地址">
                  <el-select v-model="form[se.session_id].address_id" placeholder="选择收货地址">
                    <el-option v-for="a in addresses" :key="a.address_id" :value="a.address_id"
                      :label="`${a.receiver_name} ${a.phone} ${a.address_detail}`" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="购票人">
              <el-checkbox-group v-model="form[se.session_id].attendee_ids">
                <el-checkbox v-for="a in attendees" :key="a.attendee_id" :value="a.attendee_id" border>
                  {{ a.attendee_name }}（{{ idTypeName(a.id_type) }} {{ a.id_no }}）
                </el-checkbox>
              </el-checkbox-group>
            </el-form-item>
            <el-button type="danger" :loading="buying"
                       @click="buy(se)">提交购票请求</el-button>
            <span class="muted" style="margin-left:10px">每人限购 1 张，勾选人数须 = 票数</span>
          </el-form>
        </template>
        <el-alert v-else-if="se.sale_status===1" type="warning" :closable="false"
                  :title="`该场次预售中，开售时间：${fmt(se.sale_start)}，开售后方可购票`" style="margin-top:10px" />
        <el-alert v-else type="info" :closable="false" title="该场次已售罄" style="margin-top:10px" />
      </template>
      <el-alert v-else type="info" :closable="false" style="margin-top:10px">
        <router-link to="/login">登录</router-link> 后即可购票
      </el-alert>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'
import { useStore, STATUS_NAMES, ID_TYPE } from '../store'

const route = useRoute()
const store = useStore()
const data = ref({ show: null, sessions: [], images: [], tiers: {}, summary: {} })
const loading = ref(false)
const buying = ref(false)
const addresses = ref([])
const attendees = ref([])
const form = reactive({})
const tiers = ref({})

const statusName = (s) => STATUS_NAMES[s]
const idTypeName = (t) => ID_TYPE[t]
const tagType = (s) => ({ 1: 'warning', 2: 'success', 3: 'info' }[s])
const fmt = (s) => s ? s.replace('T', ' ').slice(0, 16) : ''

async function load() {
  loading.value = true
  try {
    const r = await api.get('/shows/' + route.params.id)
    data.value = r.data
    tiers.value = r.data.tiers
    r.data.sessions.forEach(se => { form[se.session_id] = { tier_id: null, count: 1, address_id: null, attendee_ids: [] } })
    if (store.isUser) await loadProfile()
  } finally { loading.value = false }
}

async function loadProfile() {
  const [a, t] = await Promise.all([api.get('/addresses'), api.get('/attendees')])
  addresses.value = a.data.list
  attendees.value = t.data.list
}

async function buy(se) {
  const f = form[se.session_id]
  if (!f.tier_id || !f.address_id) return ElMessage.warning('请选择票档和收货地址')
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
    f.attendee_ids = []
    await load()
  } catch (e) { /* 拦截器已提示 */ } finally { buying.value = false }
}

onMounted(load)
</script>

<style scoped>
.head { margin-top: 10px; }
.head-inner { display: flex; gap: 22px; }
.poster-big { width: 160px; height: 210px; border-radius: 10px; overflow: hidden; flex: 0 0 auto; background:#eee; }
.info h2 { margin-bottom: 10px; }
.desc { color: #555; line-height: 1.7; margin-top: 12px; }
.price-big { color: #e94b64; font-weight: bold; font-size: 18px; margin: 10px 0; }
.img-row { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 10px; }
.session { margin-bottom: 14px; }
.session-head { display: flex; justify-content: space-between; align-items: center; }
</style>
