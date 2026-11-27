<template>
  <div class="console-page">
    <tvue-crud
      :option="option"
      :data="data"
      :page="page"
      v-model:search="search"
      @on-load="onLoad"
    >
      <template #messageDigest="{ row }">
        <el-tooltip :content="row.messageDigest" placement="top" :show-after="300">
          <span class="block truncate">{{ row.messageDigest }}</span>
        </el-tooltip>
      </template>
    </tvue-crud>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { listExceptionLogs, type ExceptionLogItem } from '../../api'

const data = ref<ExceptionLogItem[]>([])
const search = reactive<Record<string, unknown>>({})
const page = reactive({ currentPage: 1, pageSize: 10, total: 0 })

const option = reactive<Record<string, unknown>>({
  card: true, border: false, stripe: true, menuWidth: 60, index: true,
  addBtn: false, editBtn: false, delBtn: false, menu: false,
  column: [
    { label: '异常类型', prop: 'exceptionType', search: true, width: 160 },
    { label: '请求路径', prop: 'requestPath', search: true, minWidth: 210 },
    { label: '摘要', prop: 'messageDigest', minWidth: 240 },
    { label: '用户ID', prop: 'userId', width: 100 },
    { label: '发生时间', prop: 'createdAt', width: 170 },
  ],
})

const onLoad = async (
  paged: { currentPage: number; pageSize: number },
  params: Record<string, unknown>,
  done?: () => void,
): Promise<void> => {
  if (paged) { page.currentPage = paged.currentPage; page.pageSize = paged.pageSize }
  try {
    const result = await listExceptionLogs({
      page: page.currentPage, pageSize: page.pageSize,
      exceptionType: params?.exceptionType, requestPath: params?.requestPath,
    })
    data.value = result.items
    page.total = result.total
  } finally { done?.() }
}
</script>
