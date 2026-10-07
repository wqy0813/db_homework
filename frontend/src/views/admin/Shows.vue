<template>
  <h2>演出管理</h2>
  <el-card shadow="never" style="margin-bottom:18px">
    <el-form inline @submit.prevent>
      <el-form-item><el-input v-model="form.show_name" placeholder="演出名称" style="width:200px" /></el-form-item>
      <el-form-item>
        <el-select v-model="form.category_id" placeholder="类型" style="width:130px">
          <el-option v-for="c in cats" :key="c.category_id" :value="c.category_id" :label="c.category_name" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-select v-model="form.city_id" placeholder="城市" style="width:130px">
          <el-option v-for="c in cities" :key="c.city_id" :value="c.city_id" :label="c.city_name" />
        </el-select>
      </el-form-item>
      <el-form-item label="海报">
        <div class="poster-editor">
          <el-upload
            :show-file-list="false"
            accept="image/jpeg,image/png,image/gif,image/webp"
            :http-request="uploadPoster"
          >
            <el-button>选择并上传</el-button>
          </el-upload>
          <el-input v-model="form.poster_url" placeholder="也可直接填写图片 URL" />
          <el-image v-if="form.poster_url" :src="form.poster_url" fit="cover" class="poster-preview" />
        </div>
      </el-form-item>
      <el-form-item><el-input v-model="form.description" placeholder="演出介绍" /></el-form-item>
      <el-button type="danger" @click="create">创建演出</el-button>
    </el-form>
  </el-card>

  <el-table :data="shows" v-loading="loading" border>
    <el-table-column prop="show_id" label="ID" width="70" />
    <el-table-column prop="show_name" label="名称" min-width="200" />
    <el-table-column prop="city_name" label="城市" width="90" />
    <el-table-column prop="category_name" label="类型" width="100" />
    <el-table-column label="票价区间" width="130">
      <template #default="{row}">¥{{ Math.round(row.min_price||0) }}-{{ Math.round(row.max_price||0) }}</template>
    </el-table-column>
    <el-table-column label="状态" width="100">
      <template #default="{row}">
        <el-tag :type="tagType(row.show_status)">{{ STATUS_NAMES[row.show_status] }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column label="操作" width="200">
      <template #default="{row}">
        <el-button size="small" type="primary" @click="$router.push('/admin/shows/'+row.show_id)">编辑场次/票档</el-button>
        <el-popconfirm title="删除将级联删除其场次、票档、图片，确认？" @confirm="del(row.show_id)">
          <template #reference><el-button size="small" type="danger">删除</el-button></template>
        </el-popconfirm>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../../api'
import { STATUS_NAMES } from '../../store'

const router = useRouter()
const shows = ref([])
const cities = ref([])
const cats = ref([])
const loading = ref(false)
const form = reactive({ show_name: '', category_id: null, city_id: null, poster_url: '', description: '' })
const tagType = (s) => ({ 1: 'warning', 2: 'success', 3: 'info', 4: 'info' }[s])

async function load() {
  loading.value = true
  try {
    const r = await api.get('/admin/shows')
    shows.value = r.data.list
    cities.value = r.data.cities
    cats.value = r.data.categories
  } finally { loading.value = false }
}
async function create() {
  if (!form.show_name || !form.category_id || !form.city_id) return ElMessage.warning('请填写名称、类型、城市')
  const r = await api.post('/admin/shows/create', { ...form })
  ElMessage.success(r.msg)
  Object.assign(form, { show_name: '', category_id: null, city_id: null, poster_url: '', description: '' })
  router.push('/admin/shows/' + r.data.show_id)
}
async function uploadPoster({ file, onSuccess, onError }) {
  const body = new FormData()
  body.append('poster', file)
  try {
    const r = await api.post('/admin/uploads/poster', body)
    form.poster_url = r.data.url
    ElMessage.success(r.msg)
    onSuccess(r)
  } catch (err) {
    onError(err)
  }
}
async function del(id) {
  const r = await api.post(`/admin/shows/${id}/delete`)
  ElMessage.success(r.msg); load()
}
onMounted(load)
</script>

<style scoped>
.poster-editor { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.poster-editor .el-input { width: 280px; }
.poster-preview { width: 42px; height: 42px; border-radius: 4px; }
</style>
