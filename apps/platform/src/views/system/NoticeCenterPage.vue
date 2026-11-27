<template>
  <div class="console-page">
    <tvue-crud
      :option="option"
      :data="data"
      :page="page"
      v-model:search="search"
      @on-load="onLoad"
    >
      <template #read="{ row }">
        <el-tag :type="(row as MyNoticeItem).read ? 'info' : 'danger'" size="small">
          {{ (row as MyNoticeItem).read ? '已读' : '未读' }}
        </el-tag>
      </template>
      <template #menu="{ row }">
        <el-button link type="primary" @click="openDetail(row as MyNoticeItem)">查看</el-button>
      </template>
    </tvue-crud>

    <el-dialog v-model="detailVisible" :title="detail?.title || '公告详情'" width="640px">
      <div class="flex items-center gap-3 mb-3 text-xs" style="color: var(--nf-text-sub)">
        <span>{{ detail?.noticeType === 'ANNOUNCEMENT' ? '公告' : '通知' }}</span>
        <span>{{ detail?.publisherName || '系统' }}</span>
        <span>{{ detail?.publishAt }}</span>
      </div>
      <div class="whitespace-pre-wrap text-sm leading-7" style="color: var(--nf-text-primary)">{{ detail?.contentMd }}</div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { listMyNotices, type MyNoticeItem } from '../../api'
import { useNoticeStore } from '../../stores/notices'

const notices = useNoticeStore()
const data = ref<MyNoticeItem[]>([])
const search = reactive<Record<string, unknown>>({})
const page = reactive({ currentPage: 1, pageSize: 10, total: 0 })

const option = reactive<Record<string, unknown>>({
  card: true, border: false, stripe: true, menuWidth: 80, index: true,
  addBtn: false, editBtn: false, delBtn: false,
  column: [
    { label: '标题', prop: 'title', search: true, width: 240 },
    { label: '类型', prop: 'noticeType', width: 90 },
    { label: '状态', prop: 'read', width: 90 },
    { label: '发布时间', prop: 'publishAt', width: 170 },
    { label: '发布人', prop: 'publisherName', width: 110 },
  ],
})

const onLoad = async (paged: { currentPage: number; pageSize: number }, params: Record<string, unknown>, done?: () => void): Promise<void> => {
  if (paged) { page.currentPage = paged.currentPage; page.pageSize = paged.pageSize }
  try {
    const result = await listMyNotices({
      page: page.currentPage, pageSize: page.pageSize, keyword: params?.keyword,
    })
    data.value = result.items
    page.total = result.total
  } catch (error) { ElMessage.error((error as Error).message) }
  finally { done?.() }
}

const detailVisible = ref(false)
const detail = ref<MyNoticeItem | null>(null)

const openDetail = async (row: MyNoticeItem): Promise<void> => {
  detail.value = row
  detailVisible.value = true
  if (!row.read) {
    try {
      await notices.markRead(row.id)
      row.read = true
    } catch (error) { ElMessage.error((error as Error).message) }
  }
}

onMounted(() => { void notices.refresh() })
</script>
