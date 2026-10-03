<template>
  <h2>销售情况统计</h2>
  <el-card shadow="never" style="margin-bottom:16px">
    <el-form inline @submit.prevent="load">
      <el-form-item label="开始"><el-date-picker v-model="start" type="date" value-format="YYYY-MM-DD" /></el-form-item>
      <el-form-item label="结束"><el-date-picker v-model="end" type="date" value-format="YYYY-MM-DD" /></el-form-item>
      <el-button type="danger" @click="load">统计</el-button>
    </el-form>
  </el-card>

  <el-row :gutter="16" style="margin-bottom:16px">
    <el-col :span="8"><el-card shadow="never"><el-statistic title="成交订单数" :value="total.orders" /></el-card></el-col>
    <el-col :span="8"><el-card shadow="never"><el-statistic title="售票张数" :value="total.tickets" /></el-card></el-col>
    <el-col :span="8"><el-card shadow="never"><el-statistic title="销售金额（元）" :value="Math.round(total.amount)" /></el-card></el-col>
  </el-row>

  <el-card shadow="never" style="margin-bottom:16px">
    <h3>每日销售趋势（折线图）</h3>
    <div v-if="!isEmpty" ref="dailyRef" class="chart-box" style="width:100%;height:340px"></div>
    <el-empty v-else description="暂无销售数据" :image-size="80" style="height:340px" />
  </el-card>
  <el-row :gutter="16">
    <el-col :span="12" style="min-width:0">
      <el-card shadow="never"><h3>各类型销售额（饼图）</h3>
        <div v-if="!isEmpty" ref="catRef" class="chart-box" style="width:100%;height:320px"></div>
        <el-empty v-else description="暂无销售数据" :image-size="70" style="height:320px" /></el-card>
    </el-col>
    <el-col :span="12" style="min-width:0">
      <el-card shadow="never"><h3>各城市售票数（柱状图）</h3>
        <div v-if="!isEmpty" ref="cityRef" class="chart-box" style="width:100%;height:320px"></div>
        <el-empty v-else description="暂无销售数据" :image-size="70" style="height:320px" /></el-card>
    </el-col>
  </el-row>
  <el-card shadow="never" style="margin-top:16px">
    <h3>热销演出 TOP10</h3>
    <el-table :data="top" border size="small" empty-text="暂无销售数据">
      <el-table-column type="index" label="排名" width="70" />
      <el-table-column prop="name" label="演出" min-width="200" />
      <el-table-column prop="city" label="城市" width="100" />
      <el-table-column prop="tickets" label="售票数" width="100" />
      <el-table-column label="销售额"><template #default="{row}">¥{{ Number(row.amount).toLocaleString() }}</template></el-table-column>
    </el-table>
  </el-card>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import api from '../../api'

// echarts 由 index.html 通过 <script src="./assets/echarts.min.js"> 全局提供
const echarts = window.echarts

function iso(d){ return new Date(d).toISOString().slice(0,10) }
const start = ref(iso(Date.now() - 29 * 86400000))
const end = ref(iso(Date.now()))
const total = reactive({ orders: 0, tickets: 0, amount: 0 })
const top = ref([])
// 空区间：无成交订单时显示“暂无销售数据”，不渲染图表
const isEmpty = computed(() => total.orders === 0)
const dailyRef = ref(null), catRef = ref(null), cityRef = ref(null)
const charts = {}
let disposed = false

function getChart(key, el) {
  if (!el) return null
  try {
    if (!charts[key]) charts[key] = echarts.init(el)
  } catch (e) {
    console.error('echarts init failed:', key, e)
    return null
  }
  return charts[key]
}

async function load() {
  let r
  try {
    r = await api.get('/admin/stats', { params: { start: start.value, end: end.value } })
  } catch (e) { return }
  const d = r.data
  Object.assign(total, d.total)
  top.value = d.top
  await nextTick()
  if (isEmpty.value) return   // 空区间：仅显示“暂无销售数据”
  // 等两帧确保布局完成再渲染，避免容器宽度为 0
  requestAnimationFrame(() => requestAnimationFrame(() => {
    if (disposed) return
    renderDaily(d.daily); renderCat(d.cats); renderCity(d.cities)
    // 渲染后再 resize 一次，确保拿到真实尺寸
    setTimeout(() => {
      if (disposed) return
      Object.values(charts).forEach(c => c && c.resize())
    }, 100)
  }))
}

function renderDaily(daily) {
  const c = getChart('daily', dailyRef.value); if (!c) return
  c.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['售票张数', '销售金额'] },
    xAxis: { type: 'category', data: daily.map(x => x.d) },
    yAxis: [{ type: 'value', name: '张数' }, { type: 'value', name: '金额' }],
    series: [
      { name: '售票张数', type: 'line', smooth: false, data: daily.map(x => x.tickets), itemStyle: { color: '#e94b64' } },
      { name: '销售金额', type: 'line', yAxisIndex: 1, smooth: false, data: daily.map(x => x.amount), itemStyle: { color: '#3b7fff' } }
    ]
  })
}
function renderCat(cats) {
  const c = getChart('cat', catRef.value); if (!c) return
  c.setOption({
    tooltip: { trigger: 'item', formatter: p => `${p.name}：¥${Number(p.value).toLocaleString()}（${p.percent}%）` },
    legend: { type: 'scroll', bottom: 0 },
    series: [{ name: '销售额', type: 'pie', radius: ['38%', '65%'], center: ['50%', '45%'],
      label: { formatter: p => p.name + ' ' + Number(p.percent).toFixed(1) + '%' },
      data: cats.map(x => ({ name: x.name, value: Number(x.value) })) }]
  })
}
function renderCity(cities) {
  const c = getChart('city', cityRef.value); if (!c) return
  c.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: cities.map(x => x.name), axisLabel: { rotate: 30 } },
    yAxis: { type: 'value', name: '张数' },
    series: [{ name: '售票数', type: 'bar', data: cities.map(x => x.tickets), itemStyle: { color: '#3b7fff' } }]
  })
}

function onResize(){ Object.values(charts).forEach(c => c && c.resize()) }
window.addEventListener('resize', onResize)
onBeforeUnmount(() => {
  disposed = true
  window.removeEventListener('resize', onResize)
  Object.values(charts).forEach(c => c && c.dispose())
})

onMounted(load)
</script>
