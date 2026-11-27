<template>
  <div class="console-page">
    <div class="flex justify-end gap-2 mb-2">
      <el-button v-permission="'system:notice:create'" type="primary" size="small" @click="openForm()">新增公告</el-button>
    </div>
    <tvue-crud
      :option="option"
      :data="data"
      :page="page"
      v-model:search="search"
      @on-load="onLoad"
      @row-del="onDelete"
    >
      <template #status="{ row }">
        <el-tag :type="statusTag(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
      </template>
      <template #menu="{ row }">
        <el-button link type="primary" @click="openContent(row as NoticeItem)">正文</el-button>
        <el-button v-if="(row as NoticeItem).status === 'DRAFT' || (row as NoticeItem).status === 'SCHEDULED'" v-permission="'system:notice:publish'" link type="primary" @click="doPublish(row as NoticeItem)">发布</el-button>
        <el-button v-if="(row as NoticeItem).status !== 'WITHDRAWN'" v-permission="'system:notice:withdraw'" link type="warning" @click="doWithdraw(row as NoticeItem)">撤回</el-button>
        <el-button v-if="(row as NoticeItem).status !== 'WITHDRAWN'" v-permission="'system:notice:update'" link type="primary" @click="openForm(row as NoticeItem)">编辑</el-button>
      </template>
    </tvue-crud>

    <el-dialog v-model="formVisible" :title="editing ? '编辑公告' : '新增公告'" width="640px">
      <el-form :model="form" label-width="88px">
        <el-form-item label="标题" required>
          <el-input v-model="form.title" maxlength="150" placeholder="请输入公告标题" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.noticeType" style="width: 100%">
            <el-option label="通知" value="NOTICE" />
            <el-option label="公告" value="ANNOUNCEMENT" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="!editing" label="发布方式">
          <el-select v-model="form.status" style="width: 100%">
            <el-option label="保存草稿" value="DRAFT" />
            <el-option label="立即发布" value="PUBLISHED" />
            <el-option label="定时发布" value="SCHEDULED" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.status === 'SCHEDULED' || editing" label="发布时间">
          <el-date-picker
            v-model="form.publishAt" type="datetime" placeholder="选择发布时间"
            value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%"
          />
        </el-form-item>
        <el-form-item v-if="editing" label="撤回时间">
          <el-date-picker
            v-model="form.withdrawAt" type="datetime" placeholder="可选：到期自动撤回"
            value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="正文" required>
          <el-input v-model="form.contentMd" type="textarea" :rows="8" placeholder="支持 Markdown 文本" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="contentVisible" :title="contentTarget?.title || '公告正文'" width="640px">
      <div class="whitespace-pre-wrap text-sm leading-6" style="color: var(--nf-text-primary)">{{ contentTarget?.contentMd }}</div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createNotice, deleteNotice, listNotices, publishNotice, updateNotice, withdrawNotice,
  type NoticeItem,
} from '../../api'
import { useAuthStore } from '../../stores/auth'

const auth = useAuthStore()
const can = (code: string): boolean =>
  Boolean(auth.user?.permissions?.includes('*') || auth.user?.permissions?.includes(code))

const data = ref<NoticeItem[]>([])
const search = reactive<Record<string, unknown>>({})
const page = reactive({ currentPage: 1, pageSize: 10, total: 0 })
const noticeTypes = [
  { label: '通知', value: 'NOTICE' },
  { label: '公告', value: 'ANNOUNCEMENT' },
]
const statuses = [
  { label: '草稿', value: 'DRAFT' },
  { label: '定时发布', value: 'SCHEDULED' },
  { label: '已发布', value: 'PUBLISHED' },
  { label: '已撤回', value: 'WITHDRAWN' },
]

const option = reactive<Record<string, unknown>>({
  card: true, border: false, stripe: true, menuWidth: 230, index: true,
  addBtn: false, editBtn: false,
  delBtn: can('system:notice:delete'),
  column: [
    { label: '标题', prop: 'title', search: true, width: 220 },
    {
      label: '类型', prop: 'noticeType', type: 'select', dicData: noticeTypes,
      props: { label: 'label', value: 'value' }, width: 90,
    },
    { label: '状态', prop: 'status', width: 100 },
    { label: '发布时间', prop: 'publishAt', add: false, edit: false, width: 160 },
    { label: '已读', prop: 'readCount', add: false, edit: false, width: 80 },
    { label: '发布人', prop: 'publisherName', add: false, edit: false, width: 110 },
  ],
})

const statusText = (status: string): string =>
  statuses.find((item) => item.value === status)?.label || status
const statusTag = (status: string): 'success' | 'warning' | 'info' | 'danger' => {
  if (status === 'PUBLISHED') return 'success'
  if (status === 'SCHEDULED') return 'warning'
  if (status === 'WITHDRAWN') return 'danger'
  return 'info'
}

const onLoad = async (paged: { currentPage: number; pageSize: number }, params: Record<string, unknown>, done?: () => void): Promise<void> => {
  if (paged) { page.currentPage = paged.currentPage; page.pageSize = paged.pageSize }
  try {
    const result = await listNotices({
      page: page.currentPage, pageSize: page.pageSize,
      keyword: params?.keyword, noticeType: params?.noticeType, status: params?.status,
    })
    data.value = result.items
    page.total = result.total
  } finally { done?.() }
}

const onDelete = async (row: NoticeItem, done: () => void): Promise<void> => {
  try {
    await ElMessageBox.confirm(`确认删除公告「${row.title}」？已读记录也会一并删除。`, '提示', { type: 'warning' })
    await deleteNotice(row.id)
    ElMessage.success('公告已删除')
    done?.()
    await onLoad(page, search)
  } catch (error) {
    if ((error as Error).message !== 'cancel') ElMessage.error((error as Error).message)
  }
}

const doPublish = async (row: NoticeItem): Promise<void> => {
  try {
    await publishNotice(row.id)
    ElMessage.success('公告已发布')
    await onLoad(page, search)
  } catch (error) { ElMessage.error((error as Error).message) }
}

const doWithdraw = async (row: NoticeItem): Promise<void> => {
  try {
    await ElMessageBox.confirm(`确认撤回公告「${row.title}」？`, '提示', { type: 'warning' })
    await withdrawNotice(row.id)
    ElMessage.success('公告已撤回')
    await onLoad(page, search)
  } catch (error) {
    if ((error as Error).message !== 'cancel') ElMessage.error((error as Error).message)
  }
}

const contentVisible = ref(false)
const contentTarget = ref<NoticeItem | null>(null)
const openContent = (row: NoticeItem): void => {
  contentTarget.value = row
  contentVisible.value = true
}

const formVisible = ref(false)
const editing = ref(false)
const saving = ref(false)
const form = reactive({
  id: 0, title: '', noticeType: 'NOTICE', status: 'DRAFT',
  publishAt: '', withdrawAt: '', contentMd: '',
})

const openForm = (row?: NoticeItem): void => {
  editing.value = Boolean(row)
  form.id = row?.id || 0
  form.title = row?.title || ''
  form.noticeType = row?.noticeType || 'NOTICE'
  form.status = row?.status || 'DRAFT'
  form.publishAt = row?.publishAt || ''
  form.withdrawAt = row?.withdrawAt || ''
  form.contentMd = row?.contentMd || ''
  formVisible.value = true
}

const submitForm = async (): Promise<void> => {
  if (!form.title.trim() || !form.contentMd.trim()) {
    ElMessage.warning('标题与正文不能为空')
    return
  }
  saving.value = true
  try {
    const payload = {
      title: form.title, noticeType: form.noticeType, contentMd: form.contentMd,
      publishAt: form.publishAt || null, withdrawAt: form.withdrawAt || null,
      status: form.status,
    }
    if (editing.value) {
      await updateNotice(form.id, payload)
      ElMessage.success('公告已更新')
    } else {
      await createNotice(payload)
      ElMessage.success('公告已保存')
    }
    formVisible.value = false
    await onLoad(page, search)
  } catch (error) { ElMessage.error((error as Error).message) }
  finally { saving.value = false }
}
</script>
