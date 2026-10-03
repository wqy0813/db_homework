<template>
  <h2>我的订单</h2>
  <el-table :data="orders" v-loading="loading" border stripe>
    <el-table-column prop="order_no" label="订单号" width="190" />
    <el-table-column prop="show_name" label="演出名称" min-width="160" />
    <el-table-column label="地点" width="160">
      <template #default="{row}">{{ row.city_name }}·{{ row.venue_name }}</template>
    </el-table-column>
    <el-table-column label="演出日期" width="150">
      <template #default="{row}">{{ fmt(row.show_time) }}</template>
    </el-table-column>
    <el-table-column prop="ticket_count" label="票数" width="60" />
    <el-table-column label="金额" width="100">
      <template #default="{row}">¥{{ Number(row.total_amount).toFixed(2) }}</template>
    </el-table-column>
    <el-table-column label="状态" width="90">
      <template #default="{row}">
        <el-tag :type="orderTagType(row.order_status)">{{ ORDER_STATUS[row.order_status] }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column label="收货信息" min-width="150">
      <template #default="{row}">{{ row.receiver_name }} {{ row.phone }}<br>{{ row.address_detail }}</template>
    </el-table-column>
    <el-table-column label="持票人" min-width="140">
      <template #default="{row}">
        <span v-for="(it,i) in row.items" :key="i">{{ it.attendee_name }}（{{ idTypeName(it.id_type) }}）<br></span>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'
import { ORDER_STATUS, ID_TYPE } from '../store'

const orders = ref([])
const loading = ref(false)
const idTypeName = (t) => ID_TYPE[t]
const orderTagType = (s) => ({ 1: 'warning', 2: 'success', 3: 'info', 4: 'info' }[s])
const fmt = (s) => s ? s.replace('T', ' ').slice(0, 16) : ''

async function load() {
  loading.value = true
  try {
    const r = await api.get('/orders')
    orders.value = r.data.list
  } finally { loading.value = false }
}
onMounted(load)
</script>
