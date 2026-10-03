<template>
  <el-button link @click="$router.push('/series')">← 返回巡演列表</el-button>
  <div v-if="data.series" v-loading="loading">
    <el-card shadow="never" class="head">
      <div class="head-inner">
        <div class="poster-big">
          <img v-if="data.series.poster_url" :src="data.series.poster_url" class="poster-img" />
          <div v-else class="poster-ph" style="font-size:60px">{{ (data.series.main_artist||data.series.series_name).slice(0,1) }}</div>
        </div>
        <div class="info">
          <h2>{{ data.series.series_name }}</h2>
          <p class="muted">🎤 主演/歌手：<b>{{ data.series.main_artist || '—' }}</b>
            ｜ {{ data.series.category_name }} ｜ {{ data.stations.length }} 个城市站</p>
          <p class="desc">{{ data.series.description }}</p>
        </div>
      </div>
    </el-card>

    <h3 class="section-title">城市站（点击进入该站选座购票）</h3>
    <el-card v-for="st in data.stations" :key="st.show_id" shadow="hover" class="station"
             @click="$router.push('/shows/'+st.show_id)" style="cursor:pointer">
      <div class="station-row">
        <div class="station-city">
          <b>📍 {{ st.city_name }}</b>
          <el-tag v-if="st.show_status" :type="statusTagType(st.show_status)" size="small" class="st-tag">{{ STATUS_SHORT[st.show_status] }}</el-tag>
          <span class="muted">　{{ st.session_count }} 场次</span>
        </div>
        <div class="station-info">
          <span class="muted" v-if="st.show_dates">🗓 {{ st.show_dates }}</span>
          <span class="price-small" v-if="st.min_price">¥{{ Math.round(st.min_price) }}-{{ Math.round(st.max_price) }}</span>
        </div>
        <el-button size="small" type="danger" plain @click.stop="$router.push('/shows/'+st.show_id)">查看场次/购票 →</el-button>
      </div>
    </el-card>
    <el-empty v-if="!loading && data.stations.length===0" description="该巡演暂无城市站" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'

// 大麦风格短标签：预售 / 在售 / 已售罄（映射系统 show_status 1/2/3）
const STATUS_SHORT = { 1: '预售', 2: '在售', 3: '已售罄' }
const statusTagType = (s) => ({ 1: 'warning', 2: 'success', 3: 'info' }[s])

const route = useRoute()
const loading = ref(false)
const data = ref({ series: null, stations: [] })

async function load() {
  loading.value = true
  try {
    const r = await api.get('/series/' + route.params.id)
    data.value = r.data
  } finally { loading.value = false }
}
onMounted(load)
</script>

<style scoped>
.head { margin-top: 10px; }
.head-inner { display: flex; gap: 22px; }
.poster-big { width: 160px; height: 210px; border-radius: 10px; overflow: hidden; flex: 0 0 auto; background: #eee; }
.info h2 { margin-bottom: 10px; }
.desc { color: #555; line-height: 1.7; margin-top: 12px; }
.station { margin-bottom: 12px; }
.station-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.station-city { min-width: 140px; }
.station-info { display: flex; flex-direction: column; gap: 4px; }
.price-small { color: #e94b64; font-weight: bold; }
</style>
