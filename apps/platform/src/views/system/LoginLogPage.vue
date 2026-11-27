<template>
  <div class="console-page">
    <tvue-crud
      :option="option"
      :data="data"
      :page="page"
      v-model:search="search"
      @on-load="onLoad"
    >
      <template #success="{ row }">
        <el-tag :type="row.success ? 'success' : 'danger'" size="small">{{ row.success ? '成功' : '失败' }}</el-tag>
      </template>
    </tvue-crud>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { listLoginLogs, type LoginLogItem } from '../../api'

const data = ref<LoginLogItem[]>([])
const search = reactive<Record<string, unknown>>({})
const page = reactive({ currentPage: 1, pageSize: 10, total: 0 })

const option = reactive<Record<string, unknown>>({
  card: true, border: false, stripe: true, menuWidth: 60, index: true,
  addBtn: false, editBtn: false, delBtn: false, menu: false,
  column: [
    { label: '账号', prop: 'account', search: true, width: 160 },
    { label: '登录 IP', prop: 'loginIp', width: 150 },
    { label: '结果', prop: 'success', width: 90 },
    { label: '失败原因', prop: 'failReason', minWidth: 160 },
    { label: '登录时间', prop: 'createdAt', width: 170 },
  ],
})

const onLoad = async (
  paged: { currentPage: number; pageSize: number },
  params: Record<string, unknown>,
  done?: () => void,
): Promise<void> => {
  if (paged) { page.currentPage = paged.currentPage; page.pageSize = paged.pageSize }
  try {
    const result = await listLoginLogs({
      page: page.currentPage, pageSize: page.pageSize,
      account: params?.account,
    })
    data.value = result.items
    page.total = result.total
  } finally { done?.() }
}
</script>
