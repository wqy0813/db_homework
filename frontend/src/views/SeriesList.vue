<template>
  <h2>演出巡演</h2>
  <el-card shadow="never" class="filter">
    <el-select v-model="cityId" placeholder="全部城市" clearable style="width:150px">
      <el-option v-for="c in cities" :key="c.city_id" :label="c.city_name" :value="c.city_id" />
    </el-select>
    <el-select v-model="catId" placeholder="全部类型" clearable style="width:150px">
      <el-option v-for="c in cats" :key="c.category_id" :label="c.category_name" :value="c.category_id" />
    </el-select>
    <el-select v-model="statusId" placeholder="全部状态" clearable style="width:130px">
      <el-option v-for="(n, v) in STATUS_SHORT" :key="v" :label="n" :value="Number(v)" />
    </el-select>
    <el-input v-model="keyword" placeholder="搜索巡演/艺人" clearable @keyup.enter="load" style="width:220px" />
    <el-button type="danger" @click="load">筛选</el-button>
  </el-card>

  <div class="grid" v-loading="loading">
    <el-card v-for="s in series" :key="s.series_id" shadow="hover" class="series-card" body-style="padding:0"
             @click="goDetail(s.series_id)">
      <div class="poster-wrap">
        <img v-if="s.poster_url" :src="s.poster_url" class="poster-img" />
        <div v-else class="poster-ph">{{ (s.main_artist||s.series_name).slice(0,1) }}</div>
        <el-tag :type="tagType(s.category_id)" class="cat-tag">{{ s.category_name }}</el-tag>
        <el-tag v-if="s.status" :type="statusTagType(s.status)" class="st-tag">{{ STATUS_SHORT[s.status] }}</el-tag>
        <div v-if="s.main_artist" class="artist-badge">🎤 {{ s.main_artist }}</div>
      </div>
      <div style="padding:12px 14px">
        <h3 class="title">{{ s.series_name }}</h3>
        <p class="muted">📍 {{ s.city_count }} 城 · {{ s.station_count }} 站
          <template v-if="s.show_dates">　🗓 {{ s.show_dates }}</template>
        </p>
        <p class="price">¥{{ Math.round(s.min_price||0) }} - ¥{{ Math.round(s.max_price||0) }}</p>
      </div>
    </el-card>
    <el-empty v-if="!loading && series.length===0" description="没有符合条件的巡演" style="grid-column:1/-1" />
  </div>

  <h2 style="margin-top:30px">其他单场演出</h2>
  <div class="grid" v-loading="loadingShows">
    <el-card v-for="s in others" :key="s.show_id" shadow="hover" class="series-card" body-style="padding:0"
             @click="$router.push('/shows/'+s.show_id)">
      <div class="poster-wrap">
        <img v-if="s.poster_url" :src="s.poster_url" class="poster-img" />
        <div v-else class="poster-ph">{{ s.show_name.slice(0,1) }}</div>
        <el-tag :type="tagType(s.category_id)" class="cat-tag">{{ s.category_name }}</el-tag>
        <el-tag v-if="s.show_status" :type="statusTagType(s.show_status)" class="st-tag">{{ STATUS_SHORT[s.show_status] }}</el-tag>
      </div>
      <div style="padding:12px 14px">
        <h3 class="title">{{ s.show_name }}</h3>
        <p class="muted">📍 {{ s.city_name }} · {{ s.venue_name || '场馆待定' }}</p>
        <p class="muted">🗓 {{ s.show_dates || '暂无场次' }}</p>
        <p class="price">¥{{ Math.round(s.min_price||0) }} - ¥{{ Math.round(s.max_price||0) }}</p>
      </div>
    </el-card>
    <el-empty v-if="!loadingShows && others.length===0" description="暂无其他单场演出" style="grid-column:1/-1" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'

// 大麦风格短标签：预售 / 在售 / 已售罄（映射系统 show_status 1/2/3）
const STATUS_SHORT = { 1: '预售', 2: '在售', 3: '已售罄' }

const router = useRouter()
const series = ref([])
const others = ref([])
const cities = ref([])
const cats = ref([])
const cityId = ref('')
const catId = ref('')
const statusId = ref('')
const keyword = ref('')
const loading = ref(false)
const loadingShows = ref(false)

const tagType = (cat) => ({ 1: 'danger', 2: 'warning', 3: 'success', 5: 'info', 6: 'primary', 7: 'warning' }[cat] || 'info')
const statusTagType = (s) => ({ 1: 'warning', 2: 'success', 3: 'info' }[s])

async function load() {
  loading.value = true
  try {
    const params = {}
    if (cityId.value) params.city_id = cityId.value
    if (catId.value) params.category_id = catId.value
    if (statusId.value) params.status = statusId.value
    if (keyword.value) params.keyword = keyword.value
    const r = await api.get('/series', { params })
    series.value = r.data.list
    // 单场演出：筛选条件下未归入巡演的（关键词为空时用 /shows 全量里 series 未归的）
    const s = await api.get('/shows', { params })
    others.value = (s.data.list || []).filter(x => !x.series_id)
  } finally { loading.value = false; loadingShows.value = false }
}

async function loadDicts() {
  const r = await api.get('/dicts')
  cities.value = r.data.cities
  cats.value = r.data.categories
}

function goDetail(id) { router.push('/series/' + id) }

onMounted(() => { loadDicts(); load() })
</script>

<style scoped>
.filter { margin-bottom: 18px; }
.filter :deep(.el-card__body) { display: flex; gap: 10px; flex-wrap: wrap; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }
.series-card { cursor: pointer; border: none; border-radius: 12px; overflow: hidden; }
.poster-wrap { position: relative; height: 150px; }
.cat-tag { position: absolute; top: 10px; right: 10px; }
.st-tag { position: absolute; top: 10px; left: 10px; }
.artist-badge { position: absolute; left: 10px; bottom: 10px; background: rgba(0,0,0,.55);
  color: #fff; padding: 4px 10px; border-radius: 16px; font-size: 13px; font-weight: 600; }
.title { font-size: 16px; margin-bottom: 6px; line-height: 1.4; min-height: 44px; }
.price { color: #e94b64; font-weight: bold; margin-top: 8px; font-size: 16px; }
</style>
