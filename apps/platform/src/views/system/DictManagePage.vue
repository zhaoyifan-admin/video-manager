<template>
  <div class="console-page">
    <div class="flex justify-end gap-2 mb-2">
      <el-button v-permission="'system:dict:update'" size="small" :loading="refreshing" @click="doRefreshCache">
        刷新字典缓存
      </el-button>
    </div>
    <tvue-crud
      :option="option"
      :data="data"
      :page="page"
      v-model:search="search"
      @on-load="onLoad"
      @row-save="onSave"
      @row-update="onUpdate"
      @row-del="onDelete"
    >
      <template #menu="{ row }">
        <el-button v-permission="'system:dict:item'" link type="primary" @click="openItems(row as DictType)">字典项</el-button>
      </template>
    </tvue-crud>

    <el-dialog v-model="itemVisible" :title="`字典项 · ${activeType?.name || ''}`" width="820px">
      <tvue-crud
        :option="itemOption"
        :data="items"
        :page="itemPage"
        v-model:search="itemSearch"
        @on-load="onItemLoad"
        @row-save="onItemSave"
        @row-update="onItemUpdate"
        @row-del="onItemDelete"
      />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createDictItem, createDictType, deleteDictItem, deleteDictType, listDictItems,
  listDictTypes, refreshDictCache, updateDictItem, updateDictType,
  type DictItem, type DictType,
} from '../../api'
import { useAuthStore } from '../../stores/auth'

const auth = useAuthStore()
const can = (code: string): boolean =>
  Boolean(auth.user?.permissions?.includes('*') || auth.user?.permissions?.includes(code))

const data = ref<DictType[]>([])
const search = reactive<Record<string, unknown>>({})
const page = reactive({ currentPage: 1, pageSize: 10, total: 0 })
const refreshing = ref(false)
const option = reactive<Record<string, unknown>>({
  card: true, border: true, stripe: true, index: true,
  addBtn: can('system:dict:create'),
  editBtn: can('system:dict:update'),
  delBtn: can('system:dict:delete'),
  column: [
    { label: '字典编码', prop: 'code', search: true, width: 160 },
    { label: '字典名称', prop: 'name', search: true, span: 12 },
    { label: '字典项数', prop: 'itemCount', add: false, edit: false, width: 100 },
    { label: '状态', prop: 'enabled', type: 'switch', span: 12, value: true },
    { label: '备注', prop: 'remark', span: 24 },
  ],
})

const onLoad = async (paged: { currentPage: number; pageSize: number }, params: Record<string, unknown>, done?: () => void): Promise<void> => {
  if (paged) { page.currentPage = paged.currentPage; page.pageSize = paged.pageSize }
  try {
    const result = await listDictTypes({ page: page.currentPage, pageSize: page.pageSize, keyword: params?.keyword })
    data.value = result.items
    page.total = result.total
  } finally { done?.() }
}

const onSave = async (form: Record<string, unknown>, done: () => void): Promise<void> => {
  try {
    await createDictType(form)
    ElMessage.success('字典类型已创建')
    done()
    await onLoad(page, search)
  } catch (error) { ElMessage.error((error as Error).message) }
}

const onUpdate = async (form: Record<string, unknown> & { id: number }, done: () => void): Promise<void> => {
  try {
    const { id, ...payload } = form
    await updateDictType(id, payload)
    ElMessage.success('字典类型已更新')
    done()
    await onLoad(page, search)
  } catch (error) { ElMessage.error((error as Error).message) }
}

const onDelete = async (row: DictType, done: () => void): Promise<void> => {
  try {
    await ElMessageBox.confirm(`确认删除字典「${row.name}」及其全部字典项？`, '提示', { type: 'warning' })
    await deleteDictType(row.id)
    ElMessage.success('字典类型已删除')
    done?.()
    await onLoad(page, search)
  } catch (error) {
    if ((error as Error).message !== 'cancel') ElMessage.error((error as Error).message)
  }
}

const doRefreshCache = async (): Promise<void> => {
  refreshing.value = true
  try {
    await refreshDictCache()
    ElMessage.success('字典缓存已刷新')
  } catch (error) { ElMessage.error((error as Error).message) }
  finally { refreshing.value = false }
}

// ---------------- 字典项 ----------------

const itemVisible = ref(false)
const activeType = ref<DictType | null>(null)
const items = ref<DictItem[]>([])
const itemSearch = reactive<Record<string, unknown>>({})
const itemPage = reactive({ currentPage: 1, pageSize: 10, total: 0 })
const itemOption = reactive<Record<string, unknown>>({
  border: true, stripe: true, menuWidth: 130, index: true,
  addBtn: can('system:dict:item'),
  editBtn: can('system:dict:item'),
  delBtn: can('system:dict:item'),
  column: [
    { label: '字典值', prop: 'value', search: true, span: 12 },
    { label: '显示文案', prop: 'label', search: true, span: 12 },
    { label: '排序', prop: 'sortNo', type: 'number', span: 12, hide: true },
    { label: '状态', prop: 'enabled', type: 'switch', span: 12, value: true },
    { label: '字典类型', prop: 'dictCode', add: false, edit: false, width: 140 },
  ],
})

const openItems = (row: DictType): void => {
  activeType.value = row
  itemVisible.value = true
}

const onItemLoad = async (paged: { currentPage: number; pageSize: number }, params: Record<string, unknown>, done?: () => void): Promise<void> => {
  if (!activeType.value) { done?.(); return }
  if (paged) { itemPage.currentPage = paged.currentPage; itemPage.pageSize = paged.pageSize }
  try {
    const result = await listDictItems({
      page: itemPage.currentPage, pageSize: itemPage.pageSize,
      dictTypeId: activeType.value.id, keyword: params?.keyword,
    })
    items.value = result.items
    itemPage.total = result.total
  } finally { done?.() }
}

const onItemSave = async (form: Record<string, unknown>, done: () => void): Promise<void> => {
  try {
    await createDictItem({ ...form, dictTypeId: activeType.value?.id })
    ElMessage.success('字典项已创建')
    done()
    await onItemLoad(itemPage, itemSearch)
  } catch (error) { ElMessage.error((error as Error).message) }
}

const onItemUpdate = async (form: Record<string, unknown> & { id: number }, done: () => void): Promise<void> => {
  try {
    const { id, ...payload } = form
    await updateDictItem(id, { ...payload, dictTypeId: activeType.value?.id })
    ElMessage.success('字典项已更新')
    done()
    await onItemLoad(itemPage, itemSearch)
  } catch (error) { ElMessage.error((error as Error).message) }
}

const onItemDelete = async (row: DictItem, done: () => void): Promise<void> => {
  try {
    await ElMessageBox.confirm(`确认删除字典项「${row.label}」？`, '提示', { type: 'warning' })
    await deleteDictItem(row.id)
    ElMessage.success('字典项已删除')
    done?.()
    await onItemLoad(itemPage, itemSearch)
  } catch (error) {
    if ((error as Error).message !== 'cancel') ElMessage.error((error as Error).message)
  }
}
</script>
