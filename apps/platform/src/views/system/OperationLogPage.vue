<template>
  <div class="console-page">
    <tvue-crud
      :option="option"
      :data="data"
      :page="page"
      v-model:search="search"
      @on-load="onLoad"
    >
      <template #operator="{ row }">
        <span>{{ operatorText(row) }}</span>
      </template>
      <template #success="{ row }">
        <el-tag :type="row.success ? 'success' : 'danger'" size="small">{{ row.success ? '成功' : '失败' }}</el-tag>
      </template>
      <template #target="{ row }">
        <el-popover placement="top-start" :width="420" trigger="click">
          <template #reference>
            <el-button link type="primary" size="small">查看快照</el-button>
          </template>
          <pre class="text-xs whitespace-pre-wrap break-all">{{ formatJson(row.target) }}</pre>
        </el-popover>
      </template>
    </tvue-crud>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { listOperationLogs, type OperationLogItem } from '../../api'

const data = ref<OperationLogItem[]>([])
const search = reactive<Record<string, unknown>>({})
const page = reactive({ currentPage: 1, pageSize: 10, total: 0 })

const option = reactive<Record<string, unknown>>({
  card: true, border: true, stripe: true, menuWidth: 60, index: true,
  addBtn: false, editBtn: false, delBtn: false, menu: false,
  column: [
    { label: '操作人', prop: 'operator', width: 140 },
    { label: '模块', prop: 'moduleCode', search: true, width: 170 },
    { label: '动作', prop: 'actionCode', width: 110 },
    { label: '请求路径', prop: 'requestPath', search: true, minWidth: 210 },
    { label: '结果', prop: 'success', width: 90 },
    { label: '耗时(ms)', prop: 'costMs', width: 100 },
    { label: '参数快照', prop: 'target', width: 100 },
    { label: '操作时间', prop: 'createdAt', width: 170 },
  ],
})

const onLoad = async (
  paged: { currentPage: number; pageSize: number },
  params: Record<string, unknown>,
  done?: () => void,
): Promise<void> => {
  if (paged) { page.currentPage = paged.currentPage; page.pageSize = paged.pageSize }
  try {
    const result = await listOperationLogs({
      page: page.currentPage, pageSize: page.pageSize,
      moduleCode: params?.moduleCode, requestPath: params?.requestPath,
    })
    data.value = result.items
    page.total = result.total
  } finally { done?.() }
}

const operatorText = (row: OperationLogItem): string => {
  const op = row.operator
  if (op && typeof op === 'object' && !Array.isArray(op)) {
    return String(op.username || op.id || '-')
  }
  return op ? String(op) : `#${row.operatorId}`
}

const formatJson = (value: unknown): string => {
  if (value == null) return '-'
  if (typeof value === 'string') return value
  try { return JSON.stringify(value, null, 2) } catch { return String(value) }
}
</script>
