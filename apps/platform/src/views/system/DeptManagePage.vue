<template>
  <div class="console-page">
    <tvue-crud
      :option="option"
      :data="data"
      @on-load="onLoad"
      @row-save="onSave"
      @row-update="onUpdate"
      @row-del="onDelete"
    />
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createDepartment, deleteDepartment, listDepartments, updateDepartment, type DeptItem } from '../../api'

const data = ref<DeptItem[]>([])
const option = reactive<Record<string, unknown>>({
  card: true, border: false, stripe: true, menuWidth: 150, index: true,
  column: [
    { label: '部门编码', prop: 'code', search: true, width: 140 },
    { label: '部门名称', prop: 'name', search: true, span: 12 },
    { label: '父级ID', prop: 'parentId', type: 'number', span: 12 },
    { label: '负责人ID', prop: 'leaderUserId', type: 'number', span: 12, hide: true },
    { label: '排序', prop: 'sortNo', type: 'number', span: 12, hide: true },
    { label: '用户数', prop: 'userCount', add: false, edit: false, width: 90 },
    { label: '祖先路径', prop: 'ancestorPath', add: false, edit: false, hide: true },
    { label: '状态', prop: 'enabled', type: 'switch', span: 12, value: true },
  ],
})

const onLoad = async (_paged: unknown, _params: Record<string, unknown>, done?: () => void): Promise<void> => {
  try { data.value = (await listDepartments()).items } finally { done?.() }
}
const onSave = async (form: Record<string, unknown>, done: () => void): Promise<void> => {
  try {
    await createDepartment(form)
    ElMessage.success('部门已创建')
    done()
    await onLoad(null, {})
  } catch (error) { ElMessage.error((error as Error).message) }
}
const onUpdate = async (form: Record<string, unknown> & { id: number }, done: () => void): Promise<void> => {
  try {
    const { id, ...payload } = form
    await updateDepartment(id, payload)
    ElMessage.success('部门已更新')
    done()
    await onLoad(null, {})
  } catch (error) { ElMessage.error((error as Error).message) }
}
const onDelete = async (row: DeptItem, done: () => void): Promise<void> => {
  try {
    await ElMessageBox.confirm(`确认删除部门「${row.name}」？`, '提示', { type: 'warning' })
    await deleteDepartment(row.id)
    ElMessage.success('部门已删除')
    done?.()
    await onLoad(null, {})
  } catch (error) {
    if ((error as Error).message !== 'cancel') ElMessage.error((error as Error).message)
  }
}
</script>
