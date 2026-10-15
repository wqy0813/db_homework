<template>
  <h2>演出巡演</h2>
  <el-card shadow="never" class="filter">
    <el-select v-model="cityId" placeholder="全部城市" clearable style="width:150px"
               @keydown.capture.enter.stop.prevent="load">
      <el-option v-for="c in cities" :key="c.city_id" :label="c.city_name" :value="c.city_id" />
    </el-select>
    <el-select v-model="catId" placeholder="全部类型" clearable style="width:150px"
               @keydown.capture.enter.stop.prevent="load">
      <el-option v-for="c in cats" :key="c.category_id" :label="c.category_name" :value="c.category_id" />
    </el-select>
    <el-select v-model="statusId" placeholder="全部状态" clearable style="width:130px"
               @keydown.capture.enter.stop.prevent="load">
      <el-option v-for="(n, v) in STATUS_NAMES" :key="v" :label="n" :value="Number(v)" />
    </el-select>
    <el-input v-model="keyword" placeholder="搜索巡演/艺人" clearable @keyup.enter="load" style="width:220px" />
    <el-button type="danger" @click="load">筛选</el-button>
    <el-button type="success" @click="resetFilters">清空</el-button>
  </el-card>

  <template v-if="!appliedCityId">
    <h2>巡演</h2>
    <div class="grid" v-loading="loading">
      <el-card v-for="s in series" :key="s.group_name || s.series_id" shadow="hover" class="series-card" body-style="padding:0"
               @click="goDetail(s)">
        <div class="poster-wrap">
          <img v-if="s.poster_url" :src="s.poster_url" class="poster-img" />
          <div v-else class="poster-ph">{{ (s.main_artist||s.series_name).slice(0,1) }}</div>
          <el-tag :type="tagType(s.category_id)" class="cat-tag">{{ s.category_name }}</el-tag>
          <el-tag v-if="s.status" :type="statusTagType(s.status)" class="st-tag">{{ STATUS_NAMES[s.status] }}</el-tag>
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
  </template>

  <h2 v-if="!appliedCityId" style="margin-top:30px">单场演出</h2>
  <h2 v-else style="margin-top:30px">筛选结果</h2>
  <div class="grid" v-loading="loadingShows">
    <el-card v-for="s in visibleShows" :key="s.show_id" shadow="hover" class="series-card" body-style="padding:0"
             @click="openShow(s)">
      <div class="poster-wrap">
        <img v-if="s.poster_url" :src="s.poster_url" class="poster-img" />
        <div v-else class="poster-ph">{{ s.show_name.slice(0,1) }}</div>
        <el-tag :type="tagType(s.category_id)" class="cat-tag">{{ s.category_name }}</el-tag>
        <el-tag v-if="s.show_status" :type="statusTagType(s.show_status)" class="st-tag">{{ STATUS_NAMES[s.show_status] }}</el-tag>
      </div>
      <div style="padding:12px 14px">
        <h3 class="title">{{ s.show_name }}</h3>
        <p class="muted">📍 {{ s.city_name }} · {{ s.venue_name || '场馆待定' }}</p>
        <p class="muted">🗓 {{ s.show_dates || '暂无场次' }}</p>
        <p class="price">¥{{ Math.round(s.min_price||0) }} - ¥{{ Math.round(s.max_price||0) }}</p>
      </div>
    </el-card>
    <el-empty v-if="!loadingShows && visibleShows.length===0"
              :description="appliedCityId ? '该城市暂无符合条件的演出' : '暂无其他单场演出'" style="grid-column:1/-1" />
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { useStore, STATUS_NAMES, saveFilter, loadFilter } from '../store'

const router = useRouter()
const store = useStore()
function openInNewTab(path, query) {
  const url = router.resolve({ path, query }).href
  window.open(url, '_blank')
}

const FILTER_KEY = 'series'
const init = loadFilter(FILTER_KEY, { cityId: '', catId: '', statusId: '', keyword: '' })
const series = ref([])
const visibleShows = ref([])
const cities = ref([])
const cats = ref([])
const cityId = ref(init.cityId || '')
const appliedCityId = ref('')
const catId = ref(init.catId || '')
const statusId = ref(init.statusId || '')
const keyword = ref(init.keyword || '')
const loading = ref(false)
const loadingShows = ref(false)
const tagType = (cat) => ({ 1: 'danger', 2: 'warning', 3: 'success', 5: 'info', 6: 'primary', 7: 'warning' }[cat] || 'info')
const statusTagType = (s) => ({ 1: 'warning', 2: 'success', 3: 'info', 4: 'info' }[s])

async function load() {
  const filters = {
    city_id: cityId.value,
    category_id: catId.value,
    status: statusId.value,
    keyword: keyword.value.trim()
  }
  saveFilter(FILTER_KEY, { cityId: filters.city_id, catId: filters.category_id, statusId: filters.status, keyword: filters.keyword })
  loading.value = true
  loadingShows.value = true
  try {
    const params = {}
    if (filters.city_id) params.city_id = filters.city_id
    if (filters.category_id) params.category_id = filters.category_id
    if (filters.status) params.status = filters.status
    if (filters.keyword) params.keyword = filters.keyword
    const showsRequest = api.get('/shows', { params })
    if (filters.city_id) {
      const s = await showsRequest
      series.value = []
      visibleShows.value = s.data.list || []
    } else {
      const [r, s] = await Promise.all([api.get('/series', { params }), showsRequest])
      series.value = r.data.list || []
      visibleShows.value = (s.data.list || []).filter(x => !x.is_tour_station)
    }
    appliedCityId.value = filters.city_id
  } finally {
    loading.value = false
    loadingShows.value = false
  }
}

function resetFilters() {
  cityId.value = ''
  catId.value = ''
  statusId.value = ''
  keyword.value = ''
  appliedCityId.value = ''
  load()
}

async function loadDicts() {
  const r = await api.get('/dicts')
  cities.value = r.data.cities
  cats.value = r.data.categories
}

function goDetail(s) {
  const path = s.inferred ? '/series/group' : '/series/' + s.series_id
  const query = s.inferred ? { name: s.group_name } : undefined
  openInNewTab(path, query)
}

function openShow(s) {
  const query = s.is_tour_station
    ? (s.group_name
        ? { from_group: s.group_name }
        : s.series_id
          ? { from_series: String(s.series_id) }
          : { from_group: (s.show_name || '').split('·')[0].trim() })
    : { from: 'series' }
  openInNewTab('/shows/' + s.show_id, query)
}

onMounted(() => { loadDicts(); load() })
watch(() => store.isLogin, (now, before) => {
  if (before && !now) {
    cityId.value = ''; catId.value = ''; statusId.value = ''; keyword.value = ''
    saveFilter(FILTER_KEY, { cityId: '', catId: '', statusId: '', keyword: '' })
    load()
  }
})
</script>

<style scoped>
.filter { margin-bottom: 18px; }
.filter :deep(.el-card__body) { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; }
.series-card { border: none; border-radius: 12px; overflow: hidden; cursor: pointer; }
.series-card :deep(.el-card__body) { padding: 0; }
.poster-wrap { position: relative; height: 150px; }
.cat-tag { position: absolute; top: 10px; right: 10px; }
.st-tag { position: absolute; top: 10px; left: 10px; }
.artist-badge { position: absolute; left: 10px; bottom: 10px; background: rgba(0,0,0,.55); color: #fff; padding: 4px 10px; border-radius: 16px; font-size: 13px; font-weight: 600; }
.title { font-size: 16px; margin-bottom: 6px; line-height: 1.4; min-height: 44px; }
.price { color: #e94b64; font-weight: bold; margin-top: 8px; font-size: 16px; }
</style>
