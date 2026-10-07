<template>
  <h2>演出列表</h2>
  <el-card shadow="never" class="filter">
    <el-select v-model="cityId" placeholder="全部城市" clearable @change="load" style="width:150px">
      <el-option v-for="c in cities" :key="c.city_id" :label="c.city_name" :value="c.city_id" />
    </el-select>
    <el-select v-model="catId" placeholder="全部类型" clearable @change="load" style="width:150px">
      <el-option v-for="c in cats" :key="c.category_id" :label="c.category_name" :value="c.category_id" />
    </el-select>
    <el-select v-model="statusId" placeholder="全部状态" clearable @change="load" style="width:130px">
      <el-option v-for="(n, v) in STATUS_NAMES" :key="v" :label="n" :value="Number(v)" />
    </el-select>
    <el-input v-model="keyword" placeholder="搜索演出名称" clearable @keyup.enter="load" style="width:220px" />
    <el-button type="danger" @click="load">筛选</el-button>
  </el-card>

  <div class="grid" v-loading="loading">
    <el-card v-for="s in shows" :key="s.show_id" shadow="hover" class="show-card" body-style="padding:0"
             @click="goDetail(s.show_id)">
      <div class="poster-wrap">
        <img v-if="s.poster_url" :src="s.poster_url" class="poster-img" />
        <div v-else class="poster-ph">{{ s.show_name.slice(0,1) }}</div>
        <el-tag :type="tagType(s.show_status)" class="st-tag">{{ statusName(s.show_status) }}</el-tag>
      </div>
      <div style="padding:12px 14px">
        <h3 class="title">{{ s.show_name }}</h3>
        <p class="muted">📍 {{ s.city_name }} · {{ s.venue_name || '场馆待定' }} · {{ s.category_name }}</p>
        <p class="muted">🗓 {{ s.show_dates || '暂无场次' }}</p>
        <p class="price">¥{{ Math.round(s.min_price||0) }} - ¥{{ Math.round(s.max_price||0) }}</p>
      </div>
    </el-card>
    <el-empty v-if="!loading && shows.length===0" description="没有符合条件的演出" style="grid-column:1/-1" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { STATUS_NAMES } from '../store'

const router = useRouter()
const shows = ref([])
const cities = ref([])
const cats = ref([])
const cityId = ref('')
const catId = ref('')
const statusId = ref('')
const keyword = ref('')
const loading = ref(false)

const statusName = (s) => STATUS_NAMES[s]
const tagType = (s) => ({ 1: 'warning', 2: 'success', 3: 'info', 4: 'info' }[s])

async function load() {
  loading.value = true
  try {
    const params = {}
    if (cityId.value) params.city_id = cityId.value
    if (catId.value) params.category_id = catId.value
    if (statusId.value) params.status = statusId.value
    if (keyword.value) params.keyword = keyword.value
    const r = await api.get('/shows', { params })
    shows.value = r.data.list
  } finally { loading.value = false }
}

async function loadDicts() {
  const r = await api.get('/dicts')
  cities.value = r.data.cities
  cats.value = r.data.categories
}

function goDetail(id) { router.push('/shows/' + id) }

onMounted(() => { loadDicts(); load() })
</script>

<style scoped>
.filter { margin-bottom: 18px; }
.filter :deep(.el-card__body) { display: flex; gap: 10px; flex-wrap: wrap; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }
.show-card { cursor: pointer; border: none; border-radius: 12px; overflow: hidden; }
.poster-wrap { position: relative; height: 150px; }
.st-tag { position: absolute; top: 10px; right: 10px; }
.title { font-size: 16px; margin-bottom: 6px; line-height: 1.4; min-height: 44px; }
.price { color: #e94b64; font-weight: bold; margin-top: 8px; font-size: 16px; }
</style>
