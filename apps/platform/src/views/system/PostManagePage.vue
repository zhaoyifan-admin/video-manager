<template>
  <div class="console-page">
    <tvue-crud
      :option="option"
      :data="data"
      :page="page"
      v-model:search="search"
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
import { createPost, deletePost, listPosts, updatePost, type PostItem } from '../../api'

const data = ref<PostItem[]>([])
const search = reactive<Record<string, unknown>>({})
const page = reactive({ currentPage: 1, pageSize: 10, total: 0 })
const option = reactive<Record<string, unknown>>({
  card: true, border: false, stripe: true, menuWidth: 150, index: true,
  column: [
    { label: '岗位编码', prop: 'code', search: true, width: 140 },
    { label: '岗位名称', prop: 'name', search: true, span: 12 },
    { label: '排序', prop: 'sortNo', type: 'number', span: 12, hide: true },
    { label: '用户数', prop: 'userCount', add: false, edit: false, width: 90 },
    { label: '状态', prop: 'enabled', type: 'switch', span: 12, value: true },
    { label: '备注', prop: 'remark', span: 24 },
  ],
})

const onLoad = async (paged: { currentPage: number; pageSize: number }, params: Record<string, unknown>, done?: () => void): Promise<void> => {
  if (paged) { page.currentPage = paged.currentPage; page.pageSize = paged.pageSize }
  try {
    const result = await listPosts({ page: page.currentPage, pageSize: page.pageSize, keyword: params?.keyword })
    data.value = result.items
    page.total = result.total
  } finally { done?.() }
}
const onSave = async (form: Record<string, unknown>, done: () => void): Promise<void> => {
  try {
    await createPost(form)
    ElMessage.success('岗位已创建')
    done()
    await onLoad(page, search)
  } catch (error) { ElMessage.error((error as Error).message) }
}
const onUpdate = async (form: Record<string, unknown> & { id: number }, done: () => void): Promise<void> => {
  try {
    const { id, ...payload } = form
    await updatePost(id, payload)
    ElMessage.success('岗位已更新')
    done()
    await onLoad(page, search)
  } catch (error) { ElMessage.error((error as Error).message) }
}
const onDelete = async (row: PostItem, done: () => void): Promise<void> => {
  try {
    await ElMessageBox.confirm(`确认删除岗位「${row.name}」？`, '提示', { type: 'warning' })
    await deletePost(row.id)
    ElMessage.success('岗位已删除')
    done?.()
    await onLoad(page, search)
  } catch (error) {
    if ((error as Error).message !== 'cancel') ElMessage.error((error as Error).message)
  }
}
</script>
