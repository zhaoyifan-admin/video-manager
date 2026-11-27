<template>
  <div class="console-page">
    <tvue-crud
      :option="option"
      :data="data"
      :page="page"
      v-model:search="search"
      @on-load="onLoad"
    >
      <template #menu="{ row }">
        <el-button v-if="row.auditStatus === 0" link type="success" v-permission="'video:audit:review'" @click="doReview(row as AuditVideoItem, 1)">通过</el-button>
        <el-button v-if="row.auditStatus === 0" link type="danger" v-permission="'video:audit:review'" @click="openReject(row as AuditVideoItem)">驳回</el-button>
        <el-button v-if="row.auditStatus === 2" link type="success" v-permission="'video:audit:review'" @click="doReview(row as AuditVideoItem, 1)">恢复通过</el-button>
        <el-button link type="primary" @click="openTimeline(row as AuditVideoItem)">记录</el-button>
      </template>
      <template #auditStatus="{ row }">
        <el-tag :type="statusTag(row.auditStatus)" size="small">{{ statusText(row.auditStatus) }}</el-tag>
      </template>
      <template #isPublic="{ row }">
        <el-tag :type="row.isPublic ? 'success' : 'info'" size="small">{{ row.isPublic ? '公开' : '私有' }}</el-tag>
      </template>
    </tvue-crud>

    <el-dialog v-model="rejectVisible" title="驳回视频" width="520px">
      <p class="text-sm mb-2" style="color: var(--nf-text-secondary)">
        驳回「{{ rejectTarget?.title }}」后视频将退出影库，理由会展示给上传用户 {{ rejectTarget?.ownerName }}。
      </p>
      <div class="flex flex-wrap gap-2 mb-2">
        <el-button v-for="r in QUICK_REASONS" :key="r" size="small" @click="rejectReason = r">{{ r }}</el-button>
      </div>
      <el-input v-model="rejectReason" type="textarea" :rows="3" maxlength="500" placeholder="请填写驳回理由" />
      <template #footer>
        <el-button @click="rejectVisible = false">取消</el-button>
        <el-button type="danger" :loading="saving" @click="confirmReject">确认驳回</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="timelineVisible" :title="`审核记录 · ${timelineTarget?.title || ''}`" width="720px">
      <el-timeline v-if="timeline.length">
        <el-timeline-item v-for="log in timeline" :key="log.id" :timestamp="log.createdAt" placement="top">
          <div class="text-sm">
            <b>{{ log.actionText }}</b>
            <span class="ml-2" style="color: var(--nf-text-muted)">
              {{ log.fromStatusText ? `${log.fromStatusText} → ${log.toStatusText}` : `初始 → ${log.toStatusText}` }}
            </span>
            <span class="ml-2" style="color: var(--nf-text-muted)">操作人：{{ log.operatorName }}</span>
          </div>
          <div v-if="log.reason" class="text-sm mt-1" style="color: #ff9ba1">{{ log.reason }}</div>
        </el-timeline-item>
      </el-timeline>
      <el-empty v-else description="暂无审核记录" />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  listAuditVideos, reviewAuditVideo, listVideoTimeline,
  type AuditVideoItem, type AuditLogItem,
} from '../../api'

const data = ref<AuditVideoItem[]>([])
const search = reactive<Record<string, unknown>>({})
const page = reactive({ currentPage: 1, pageSize: 10, total: 0 })
const saving = ref(false)

const statusMap: Record<number, string> = { 0: '待审核', 1: '已通过', 2: '已驳回' }
const statusText = (s: number): string => statusMap[s] || '未知'
const statusTag = (s: number): 'warning' | 'success' | 'danger' =>
  s === 0 ? 'warning' : s === 1 ? 'success' : 'danger'

const option = reactive<Record<string, unknown>>({
  card: true, border: true, stripe: true, menuWidth: 260, index: true,
  addBtn: false, editBtn: false, delBtn: false,
  column: [
    { label: '影片', prop: 'title', search: true, minWidth: 180 },
    { label: '归属用户', prop: 'ownerName', width: 120 },
    { label: '类型', prop: 'typeName', width: 110 },
    { label: '公开', prop: 'isPublic', width: 80 },
    { label: '审核状态', prop: 'auditStatus', width: 100 },
    { label: '驳回理由', prop: 'auditReason', minWidth: 160 },
    { label: '提交时间', prop: 'createdAt', width: 160 },
  ],
})

const onLoad = async (
  paged: { currentPage: number; pageSize: number },
  params: Record<string, unknown>,
  done?: () => void,
): Promise<void> => {
  if (paged) { page.currentPage = paged.currentPage; page.pageSize = paged.pageSize }
  try {
    const result = await listAuditVideos({
      page: page.currentPage, pageSize: page.pageSize, keyword: params?.keyword,
    })
    data.value = result.items
    page.total = result.total
  } finally { done?.() }
}

const doReview = async (row: AuditVideoItem, status: number, reason = ''): Promise<void> => {
  saving.value = true
  try {
    await reviewAuditVideo(row.id, { status, reason })
    ElMessage.success(status === 1 ? '已通过审核' : '已驳回')
    await onLoad(page, search)
  } catch (error) { ElMessage.error((error as Error).message) }
  finally { saving.value = false }
}

const QUICK_REASONS = ['画面/音质不清晰', '内容不符合要求', '文件无法播放或路径失效', '标题与资料不完整']
const rejectVisible = ref(false)
const rejectTarget = ref<AuditVideoItem | null>(null)
const rejectReason = ref('')
const openReject = (row: AuditVideoItem): void => {
  rejectTarget.value = row
  rejectReason.value = ''
  rejectVisible.value = true
}
const confirmReject = async (): Promise<void> => {
  if (!rejectReason.value.trim()) { ElMessage.warning('请填写驳回理由'); return }
  if (!rejectTarget.value) return
  await doReview(rejectTarget.value, 2, rejectReason.value.trim())
  rejectVisible.value = false
}

const timelineVisible = ref(false)
const timelineTarget = ref<AuditVideoItem | null>(null)
const timeline = ref<AuditLogItem[]>([])
const openTimeline = async (row: AuditVideoItem): Promise<void> => {
  timelineTarget.value = row
  try { timeline.value = (await listVideoTimeline(row.id)).items }
  catch (error) { ElMessage.error((error as Error).message); timeline.value = [] }
  timelineVisible.value = true
}
</script>
