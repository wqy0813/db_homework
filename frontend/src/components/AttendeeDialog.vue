<template>
  <el-dialog :model-value="modelValue" :title="isEdit ? '编辑购票人' : '新增购票人'"
             width="480px" @update:model-value="v => emit('update:modelValue', v)" @open="fill">
    <el-form label-width="80px" @submit.prevent>
      <el-form-item label="姓名">
        <el-input v-model="form.attendee_name" maxlength="50" placeholder="购票人真实姓名" />
      </el-form-item>
      <el-form-item label="证件类型">
        <el-select v-model="form.id_type" style="width:160px">
          <el-option v-for="(n, i) in ID_TYPE" :key="i" :value="Number(i)" :label="n" />
        </el-select>
      </el-form-item>
      <el-form-item label="证件号">
        <el-input v-model="form.id_no" maxlength="30" placeholder="与证件类型一致的证件号" />
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
import api from '../api'
import { ID_TYPE } from '../store'

const props = defineProps({
  modelValue: Boolean,
  // 编辑时传原购票人对象，新增时传 null
  attendee: { type: Object, default: null }
})
const emit = defineEmits(['update:modelValue', 'saved'])

const isEdit = computed(() => !!props.attendee)
const saving = ref(false)
const form = reactive({ attendee_name: '', id_type: 1, id_no: '' })

function fill() {
  form.attendee_name = props.attendee ? props.attendee.attendee_name : ''
  form.id_type = props.attendee ? Number(props.attendee.id_type) : 1
  form.id_no = props.attendee ? props.attendee.id_no : ''
}

function close() { emit('update:modelValue', false) }

async function save() {
  const name = form.attendee_name.trim()
  const idNo = form.id_no.trim()
  const idType = Number(form.id_type)
  if (!name) return ElMessage.warning('请填写购票人姓名')
  if (idType === 1 && !/^\d{17}[\dXx]$/.test(idNo)) return ElMessage.warning('身份证号应为 18 位（末位可为 X）')
  if (idType !== 1 && !(idNo.length >= 5 && idNo.length <= 30)) return ElMessage.warning('证件号长度应为 5-30 个字符')
  saving.value = true
  try {
    const payload = { attendee_name: name, id_type: idType, id_no: idNo }
    let attendeeId
    if (isEdit.value) {
      await api.post('/attendees/update', { ...payload, attendee_id: props.attendee.attendee_id })
      attendeeId = props.attendee.attendee_id
    } else {
      const r = await api.post('/attendees/add', payload)
      attendeeId = r.data.attendee_id
    }
    ElMessage.success(isEdit.value ? '购票人已更新' : '购票人已添加')
    emit('saved', { attendee_id: attendeeId })
    close()
  } catch (e) {
    // 拦截器已提示（含“已用于订单不能修改”的保护说明）
  } finally { saving.value = false }
}
</script>
