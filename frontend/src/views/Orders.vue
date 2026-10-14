<template>
  <h2>我的订单</h2>

  <el-card shadow="never" class="toolbar-card">
    <el-form inline @submit.prevent="applySearch">
      <el-form-item label="搜索订单">
        <el-input
          v-model="searchInput"
          placeholder="订单号或演出名称"
          clearable
          style="width: 280px"
          @keyup.enter="applySearch"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="loading" @click="applySearch">搜索</el-button>
        <el-button :disabled="loading && !searchInput && !searchKeyword" @click="clearSearch">
          清空搜索条件
        </el-button>
      </el-form-item>
    </el-form>
  </el-card>

  <el-table :data="orders" v-loading="loading" border stripe empty-text="暂无订单数据">
    <el-table-column prop="order_no" label="订单号" min-width="210" />
    <el-table-column prop="show_name" label="演出名称" min-width="180" show-overflow-tooltip />
    <el-table-column label="地点" min-width="160">
      <template #default="{ row }">{{ row.city_name }}·{{ row.venue_name }}</template>
    </el-table-column>
    <el-table-column label="演出日期" width="155">
      <template #default="{ row }">{{ formatDateTime(row.show_time) }}</template>
    </el-table-column>
    <el-table-column prop="ticket_count" label="票数" width="75" />
    <el-table-column label="金额" width="110">
      <template #default="{ row }">¥{{ formatMoney(row.total_amount) }}</template>
    </el-table-column>
    <el-table-column label="状态" width="100">
      <template #default="{ row }">
        <el-tag :type="orderTagType(row.order_status)">{{ ORDER_STATUS[row.order_status] || '未知' }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column label="操作" width="115" fixed="right">
      <template #default="{ row }">
        <el-button link type="primary" @click="openDetail(row)">查看详情</el-button>
      </template>
    </el-table-column>
  </el-table>

  <div class="pagination-row">
    <el-pagination
      :current-page="page"
      :page-size="pageSize"
      :page-sizes="[10, 20, 50]"
      :total="total"
      layout="total, sizes, prev, pager, next, jumper"
      @current-change="changePage"
      @size-change="changePageSize"
    />
  </div>

  <el-dialog v-model="detailVisible" title="订单详情" width="760px" destroy-on-close>
    <div v-loading="detailLoading" class="detail-content">
      <template v-if="orderDetail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="订单号">{{ orderDetail.order_no }}</el-descriptions-item>
          <el-descriptions-item label="订单状态">
            <el-tag :type="orderTagType(orderDetail.order_status)">
              {{ ORDER_STATUS[orderDetail.order_status] || '未知' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="演出场次">{{ orderDetail.show_name }}</el-descriptions-item>
          <el-descriptions-item label="演出时间">{{ formatDateTime(orderDetail.show_time) }}</el-descriptions-item>
          <el-descriptions-item label="场馆">{{ orderDetail.city_name }}·{{ orderDetail.venue_name }}</el-descriptions-item>
          <el-descriptions-item label="票档">{{ orderDetail.tier_name }}</el-descriptions-item>
          <el-descriptions-item label="票数">{{ orderDetail.ticket_count }} 张</el-descriptions-item>
          <el-descriptions-item label="票档单价">¥{{ formatMoney(orderDetail.tier_price) }}</el-descriptions-item>
          <el-descriptions-item label="订单金额">¥{{ formatMoney(orderDetail.total_amount) }}</el-descriptions-item>
          <el-descriptions-item label="下单时间">{{ formatDateTime(orderDetail.create_time) }}</el-descriptions-item>
          <el-descriptions-item label="付款时间">{{ formatDateTime(orderDetail.pay_time) }}</el-descriptions-item>
          <el-descriptions-item label="收货人">{{ orderDetail.receiver_name }}</el-descriptions-item>
          <el-descriptions-item label="联系电话">{{ orderDetail.phone }}</el-descriptions-item>
          <el-descriptions-item label="收货地址" :span="2">
            {{ orderDetail.address_detail }}
          </el-descriptions-item>
        </el-descriptions>

        <h3 class="attendee-title">持票人</h3>
        <el-table :data="orderDetail.items" border size="small" empty-text="暂无持票人信息">
          <el-table-column prop="attendee_name" label="姓名" min-width="120" />
          <el-table-column label="证件类型" min-width="120">
            <template #default="{ row }">{{ ID_TYPE[row.id_type] || '其他' }}</template>
          </el-table-column>
          <el-table-column prop="masked_id_no" label="证件号码" min-width="160" />
          <el-table-column label="票价" width="120">
            <template #default="{ row }">¥{{ formatMoney(row.unit_price) }}</template>
          </el-table-column>
        </el-table>
      </template>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'
import { ORDER_STATUS, ID_TYPE } from '../store'

const orders = ref([])
const loading = ref(false)
const searchInput = ref('')
const searchKeyword = ref('')
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const detailVisible = ref(false)
const detailLoading = ref(false)
const orderDetail = ref(null)

const orderTagType = (status) => ({ 1: 'warning', 2: 'success', 3: 'info', 4: 'info' }[status])
const formatDateTime = (value) => value ? String(value).replace('T', ' ').slice(0, 16) : '—'
const formatMoney = (value) => Number(value || 0).toFixed(2)

async function load() {
  loading.value = true
  try {
    const response = await api.get('/orders', {
      params: { page: page.value, page_size: pageSize.value, keyword: searchKeyword.value },
    })
    orders.value = response.data.list || []
    total.value = Number(response.data.total || 0)
  } finally {
    loading.value = false
  }
}

function applySearch() {
  searchKeyword.value = searchInput.value.trim()
  page.value = 1
  load()
}

function clearSearch() {
  searchInput.value = ''
  searchKeyword.value = ''
  page.value = 1
  load()
}

function changePage(value) {
  page.value = value
  load()
}

function changePageSize(value) {
  pageSize.value = value
  page.value = 1
  load()
}

async function openDetail(row) {
  detailVisible.value = true
  detailLoading.value = true
  orderDetail.value = null
  try {
    const response = await api.get(`/orders/${row.order_id}`)
    orderDetail.value = { ...response.data.order, items: response.data.items || [] }
  } finally {
    detailLoading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.toolbar-card { margin-bottom: 16px; }
.pagination-row { display: flex; justify-content: flex-end; margin-top: 18px; }
.detail-content { min-height: 80px; }
.attendee-title { margin: 22px 0 12px; font-size: 16px; }
</style>
