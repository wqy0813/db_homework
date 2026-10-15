<template>
  <el-button link @click="router.push('/admin/shows')">← 返回演出管理</el-button>
  <h2>创建新演出</h2>

  <el-card shadow="never" v-loading="loading" class="create-card">
    <el-form label-width="100px" @submit.prevent>
      <el-form-item label="演出名称" required>
        <el-input v-model="form.show_name" maxlength="120" show-word-limit placeholder="请输入演出名称" />
      </el-form-item>
      <el-form-item label="演出类型" required>
        <el-select v-model="form.category_id" placeholder="请选择类型" style="width:240px">
          <el-option v-for="c in categories" :key="c.category_id" :value="c.category_id" :label="c.category_name" />
        </el-select>
      </el-form-item>
      <el-form-item label="所在城市" required>
        <el-select v-model="form.city_id" placeholder="请选择城市" filterable style="width:240px">
          <el-option v-for="c in cities" :key="c.city_id" :value="c.city_id" :label="c.city_name" />
        </el-select>
      </el-form-item>
      <el-form-item label="演出海报">
        <div class="poster-editor">
          <el-upload :show-file-list="false" accept="image/jpeg,image/png,image/gif,image/webp"
                     :http-request="uploadPoster">
            <el-button>选择并上传</el-button>
          </el-upload>
          <el-input v-model="form.poster_url" placeholder="也可直接填写图片 URL" />
          <el-image v-if="form.poster_url" :src="form.poster_url" fit="cover" class="poster-preview" />
        </div>
      </el-form-item>
      <el-form-item label="演出介绍">
        <el-input v-model="form.description" type="textarea" :rows="6" maxlength="2000"
                  show-word-limit placeholder="请输入演出介绍" />
      </el-form-item>
      <el-form-item>
        <el-button @click="router.push('/admin/shows')">取消</el-button>
        <el-button type="primary" :loading="saving" @click="create">创建演出</el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../../api'

const router = useRouter()
const cities = ref([])
const categories = ref([])
const loading = ref(false)
const saving = ref(false)
const form = reactive({ show_name: '', category_id: null, city_id: null, poster_url: '', description: '' })

async function loadDicts() {
  loading.value = true
  try {
    const r = await api.get('/admin/shows')
    cities.value = r.data.cities
    categories.value = r.data.categories
  } finally { loading.value = false }
}
async function uploadPoster({ file, onSuccess, onError }) {
  const body = new FormData()
  body.append('poster', file)
  try {
    const r = await api.post('/admin/uploads/poster', body)
    form.poster_url = r.data.url
    ElMessage.success(r.msg)
    onSuccess(r)
  } catch (err) { onError(err) }
}
async function create() {
  if (!form.show_name.trim() || !form.category_id || !form.city_id) {
    return ElMessage.warning('请填写演出名称、类型和城市')
  }
  saving.value = true
  try {
    const r = await api.post('/admin/shows/create', { ...form, show_name: form.show_name.trim() })
    ElMessage.success(r.msg)
    router.push('/admin/shows/' + r.data.show_id)
  } finally { saving.value = false }
}
onMounted(loadDicts)
</script>

<style scoped>
.create-card { max-width: 850px; }
.poster-editor { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.poster-editor .el-input { width: 350px; }
.poster-preview { width: 56px; height: 56px; border-radius: 4px; }
</style>
