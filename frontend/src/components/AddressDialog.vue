<template>
  <el-dialog :model-value="modelValue" :title="isEdit ? '编辑收货地址' : '新增收货地址'"
             width="520px" @update:model-value="v => emit('update:modelValue', v)" @open="fill">
    <el-form label-width="80px" @submit.prevent>
      <!-- 整段粘贴 → 一键识别回填 -->
      <el-form-item label="智能识别">
        <div style="display:flex;flex-direction:column;gap:6px;width:100%">
          <el-input v-model="pasteText" type="textarea" :rows="2"
                    placeholder="粘贴整段收货信息，如：张三，13812345678，广东省深圳市南山区科技园路1号8栋501室" />
          <el-button size="small" type="primary" plain @click="smartParse">自动识别并填入</el-button>
        </div>
      </el-form-item>
      <el-form-item label="收货人">
        <el-input v-model="form.receiver_name" maxlength="50" placeholder="收货人姓名" />
      </el-form-item>
      <el-form-item label="手机号">
        <!-- 不设 maxlength=11：超长输入保留显示，交给保存时校验报错 -->
        <el-input v-model="form.phone" maxlength="20" placeholder="11 位手机号" />
      </el-form-item>
      <el-form-item label="所在地区">
        <el-cascader v-model="form.region" :options="regionData"
                     placeholder="省 / 市 / 区县" style="width:100%" />
      </el-form-item>
      <el-form-item label="详细地址">
        <el-input v-model="form.detail" maxlength="100" placeholder="街道、楼宇、门牌号（需自行填写）" />
      </el-form-item>
      <el-form-item>
        <el-checkbox v-model="form.is_default">设为默认收货地址</el-checkbox>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button type="danger" :loading="saving" @click="save">保 存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { reactive, ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { regionData, codeToText } from 'element-china-area-data'
import api from '../api'
import { parseSmartAddress } from '../utils/address'

const props = defineProps({
  modelValue: Boolean,
  // 编辑时传原地址对象，新增时传 null
  address: { type: Object, default: null }
})
const emit = defineEmits(['update:modelValue', 'saved'])

const isEdit = computed(() => !!props.address)
const saving = ref(false)
const pasteText = ref('')
const form = reactive({ receiver_name: '', phone: '', region: [], detail: '', is_default: false })

// 粘贴识别：结果回填表单，由用户核对后手动保存
function smartParse() {
  if (!pasteText.value.trim()) return ElMessage.warning('请先粘贴收货信息')
  const p = parseSmartAddress(pasteText.value)
  if (!p.name && !p.phone && !p.region.length && !p.detail) {
    return ElMessage.warning('未识别到有效内容，请检查粘贴的文本')
  }
  if (p.name) form.receiver_name = p.name
  if (p.phone) form.phone = p.phone
  if (p.region.length) form.region = p.region
  if (p.detail) form.detail = p.detail
  ElMessage.success('已识别填入，请核对后保存')
}

// 编辑时把旧的一条整串地址拆回省市区 + 详细地址；拆不出地区就整串放详细地址
function fill() {
  form.receiver_name = props.address ? props.address.receiver_name : ''
  form.phone = props.address ? props.address.phone : ''
  form.region = []
  form.detail = ''
  form.is_default = props.address ? !!props.address.is_default : false
  pasteText.value = ''
  if (props.address) {
    const p = parseSmartAddress(props.address.address_detail)
    if (p.region.length >= 2) {
      form.region = p.region
      form.detail = p.detail
    } else {
      form.detail = props.address.address_detail
    }
  }
}

function close() { emit('update:modelValue', false) }

// 省市区代码 → 文本（过滤直辖市的"市辖区"中间层）
function regionText() {
  return form.region
    .map(c => codeToText[c])
    .filter(l => l && l !== '市辖区' && l !== '县')
    .join(' ')
}

async function save() {
  const receiver = form.receiver_name.trim()
  const phone = form.phone.trim()
  const detail = form.detail.trim()
  if (!receiver) return ElMessage.warning('请填写收货人姓名')
  if (!/^1\d{10}$/.test(phone)) return ElMessage.warning('手机号应为 11 位数字（1 开头）')
  if (!form.region.length || form.region.length < 2) return ElMessage.warning('请选择所在地区（省 / 市 / 区县）')
  if (!detail) return ElMessage.warning('请填写详细地址（街道、楼宇、门牌号）')
  // 数据库 address_detail 仍是单列：省市区文本 + 详细地址拼接存储
  const full = `${regionText()} ${detail}`
  if (full.length > 200) return ElMessage.warning('地址过长，请精简详细地址')

  saving.value = true
  try {
    const payload = { receiver_name: receiver, phone, address_detail: full,
                      is_default: form.is_default ? 1 : 0 }
    let addressId
    if (isEdit.value) {
      await api.post('/addresses/update', { ...payload, address_id: props.address.address_id })
      addressId = props.address.address_id
    } else {
      const r = await api.post('/addresses/add', payload)
      addressId = r.data.address_id
    }
    ElMessage.success(isEdit.value ? '收货地址已更新' : '收货地址已添加')
    emit('saved', { address_id: addressId, is_default: form.is_default })
    close()
  } catch (e) {
    // 拦截器已提示（含"已用于订单不能修改"的保护说明）
  } finally { saving.value = false }
}
</script>
