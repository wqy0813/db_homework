<template>
  <el-button link @click="goBack">← 返回巡演列表</el-button>
  <div v-loading="loading" v-if="data.series">
    <!-- 巡演封面 + 标题 + 基本信息 -->
    <el-card shadow="never" class="intro">
      <div class="intro-wrap">
        <div class="poster-wrap">
          <img v-if="data.series.poster_url" :src="data.series.poster_url" class="poster-img" />
          <div v-else class="poster-ph">{{ (data.series.main_artist||data.series.series_name).slice(0,1) }}</div>
          <el-tag :type="tagType(data.series.category_id)" class="cat-tag">{{ data.series.category_name }}</el-tag>
          <el-tag v-if="data.series.show_status" :type="statusTagType(data.series.show_status)" class="st-tag">
            {{ STATUS_NAMES[data.series.show_status] }}
          </el-tag>
        </div>
        <div class="intro-main">
          <h2>{{ data.series.series_name }}</h2>
          <p v-if="data.series.main_artist" class="muted">🎤 {{ data.series.main_artist }}</p>
          <p class="muted">📍 巡演范围：{{ data.series.city_count || data.stations.length }} 城 · {{ data.stations.length }} 站</p>
          <p class="price">¥{{ Math.round(data.series.min_price||0) }} - ¥{{ Math.round(data.series.max_price||0) }}</p>
        </div>
      </div>
      <!-- 巡演介绍：保留换行；没介绍时显示提示 -->
      <div class="description">
        <h4>巡演介绍</h4>
        <p v-if="data.series.description" style="white-space:pre-line">{{ data.series.description }}</p>
        <p v-else class="muted">暂无巡演介绍</p>
      </div>
    </el-card>

    <!-- 各城市站 -->
    <h3 style="margin-top:24px">各城市站（点击进入该站选座购票）</h3>
    <div class="station-list" v-loading="loading">
      <el-card v-for="st in data.stations" :key="st.show_id" shadow="hover" class="station-item"
               @click="openStation(st.show_id)">
        <div class="station-head">
          <b>📍 {{ st.city_name }}</b>
          <el-tag v-if="st.show_status" :type="statusTagType(st.show_status)" size="small">
            {{ STATUS_NAMES[st.show_status] }}
          </el-tag>
        </div>
        <div class="muted station-meta">
          <span v-if="st.show_dates">🗓 {{ st.show_dates }}</span>
        </div>
        <div class="station-price">
          <span v-if="st.min_price">¥{{ Math.round(st.min_price) }}-{{ Math.round(st.max_price) }}</span>
          <span v-else class="muted">价格待定</span>
          <span class="go">购票 →</span>
        </div>
      </el-card>
      <el-empty v-if="!loading && data.stations.length===0" description="该巡演暂无城市站" style="width:100%" />
    </div>
  </div>
  <el-empty v-else-if="!loading" description="该巡演不存在或已下架" />
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { STATUS_NAMES } from '../store'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const data = ref({ series: null, stations: [] })

const tagType = (cat) => ({ 1: 'danger', 2: 'warning', 3: 'success', 5: 'info', 6: 'primary', 7: 'warning' }[cat] || 'info')
const statusTagType = (s) => ({ 1: 'warning', 2: 'success', 3: 'info', 4: 'info' }[s])

function openStation(showId) {
  const query = route.query.name
    ? { from_group: route.query.name }
    : { from_series: String(route.params.id || '') }
  const url = router.resolve({ path: `/shows/${showId}`, query }).href
  window.open(url, '_blank')
}

async function load() {
  loading.value = true
  try {
    const r = route.query.name
      ? await api.get('/series/group', { params: { name: route.query.name } })
      : await api.get('/series/' + route.params.id)
    data.value = r.data
    // 把巡演名写进浏览器标签标题，多标签浏览时分得清
    if (r.data.series) document.title = `${r.data.series.series_name} - 演出票务系统`
  } finally { loading.value = false }
}

// 智能返回：本标签是新开的（无内部历史）→ 直接关闭标签回到原列表；
// 本标签内部跳转过 → 浏览器后退。close 失败（如用户手动新开）时兜底回列表。
function goBack() {
  if (window.history.length > 1) return router.back()
  window.close()
  setTimeout(() => { if (!window.closed) router.push('/series') }, 200)
}

onMounted(load)
</script>

<style scoped>
.intro { margin: 12px 0 8px; }
.intro-wrap { display: flex; gap: 18px; }
.poster-wrap { position: relative; width: 220px; flex: none; }
.poster-img { width: 100%; height: 280px; object-fit: cover; border-radius: 8px; }
.poster-ph { width: 100%; height: 280px; border-radius: 8px; background: linear-gradient(135deg,#a18cd1,#fbc2eb);
  display: flex; align-items: center; justify-content: center; color: #fff; font-size: 80px; font-weight: 600; }
.cat-tag { position: absolute; top: 10px; right: 10px; }
.st-tag { position: absolute; top: 10px; left: 10px; }
.intro-main { flex: 1; }
.intro-main h2 { margin: 0 0 8px; }
.price { color: #e94b64; font-weight: bold; margin-top: 12px; font-size: 18px; }
.description { margin-top: 18px; border-top: 1px dashed #eee; padding-top: 14px; }
.description h4 { margin: 0 0 8px; }

.station-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 14px; margin-top: 10px; }
.station-item { border-radius: 8px; cursor: pointer; transition: box-shadow .15s, transform .15s; }
.station-item:hover { box-shadow: 0 2px 10px rgba(233,75,100,.15); transform: translateY(-1px); }
.station-head { display: flex; align-items: center; gap: 8px; }
.station-meta { font-size: 12px; margin-top: 4px; }
.station-price { display: flex; justify-content: space-between; align-items: center; margin-top: 6px; font-size: 14px; }
.station-price .go { color: #e94b64; font-weight: 600; }
</style>
