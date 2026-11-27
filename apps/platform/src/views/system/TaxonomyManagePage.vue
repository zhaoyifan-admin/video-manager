<template>
  <div class="console-page">
    <div class="flex items-center justify-between mb-3 gap-2 flex-wrap">
      <el-radio-group v-model="resource" @change="reload">
        <el-radio-button value="tag">标签</el-radio-button>
        <el-radio-button value="type">影视类型</el-radio-button>
        <el-radio-button value="collection">合集</el-radio-button>
      </el-radio-group>
      <span class="text-xs" style="color: var(--nf-text-muted)">
        新建条目默认进入待审核；通过审核后全站可见
      </span>
    </div>

    <tvue-crud
      :option="option"
      :data="data"
      @on-load="onLoad"
      @row-save="onSave"
      @row-update="onUpdate"
      @row-del="onDelete"
    >
      <template #menu="{ row }">
        <template v-if="row.auditStatus === 0">
          <el-button link type="success" v-permission="'video:taxonomy:review'" @click="doReview(row as TaxonomyRow, 'approve')">通过</el-button>
          <el-button link type="danger" v-permission="'video:taxonomy:review'" @click="openReject(row as TaxonomyRow)">驳回</el-button>
        </template>
        <el-button v-if="row.auditStatus === 2" link type="warning" v-permission="'video:taxonomy:manage'" @click="doResubmit(row as TaxonomyRow)">重新提交</el-button>
        <el-button link type="primary" v-permission="'video:taxonomy:manage'" @click="openEdit(row as TaxonomyRow)">编辑</el-button>
        <el-button link type="primary" @click="openLogs(row as TaxonomyRow)">留痕</el-button>
        <el-button link type="danger" v-permission="'video:taxonomy:manage'" @click="onDelete(row as TaxonomyRow)">删除</el-button>
      </template>
      <template #auditStatus="{ row }">
        <el-tag :type="statusTag(row.auditStatus)" size="small">{{ statusText(row.auditStatus) }}</el-tag>
      </template>
      <template #isPublished="{ row }">
        <el-tag :type="row.isPublished ? 'success' : 'info'" size="small">{{ row.isPublished ? '已发布' : '未发布' }}</el-tag>
      </template>
    </tvue-crud>

    <el-dialog v-model="editVisible" title="编辑分类" width="480px">
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="名称" required>
          <el-input v-model="editForm.name" :maxlength="resource === 'collection' ? 100 : 50" />
        </el-form-item>
        <el-form-item v-if="resource === 'collection'" label="简介">
          <el-input v-model="editForm.description" type="textarea" :rows="3" maxlength="500" />
        </el-form-item>
        <el-form-item label="发布">
          <el-switch v-model="editForm.isPublished" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="rejectVisible" title="驳回分类" width="440px">
      <p class="text-sm mb-2" style="color: var(--nf-text-secondary)">驳回「{{ rejectTarget?.name }}」，理由将展示给创建者。</p>
      <el-input v-model="rejectReason" type="textarea" :rows="3" maxlength="500" placeholder="请填写驳回理由" />
      <template #footer>
        <el-button @click="rejectVisible = false">取消</el-button>
        <el-button type="danger" @click="confirmReject">确认驳回</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="logsVisible" :title="`审核留痕 · ${logsTarget?.name || ''}`" width="640px">
      <el-timeline v-if="logs.length">
        <el-timeline-item v-for="log in logs" :key="log.id" :timestamp="log.createdAt" placement="top">
          <b class="text-sm">{{ log.actionText }}</b>
          <span class="ml-2 text-xs" style="color: var(--nf-text-muted)">{{ log.operatorName }}</span>
          <div v-if="log.reason" class="text-sm mt-1" style="color: #ff9ba1">{{ log.reason }}</div>
        </el-timeline-item>
      </el-timeline>
      <el-empty v-else description="暂无留痕" />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listTaxonomy, createTaxonomy, updateTaxonomy, deleteTaxonomy,
  reviewTaxonomy, resubmitTaxonomy, listTaxonomyLogs, type TaxonomyRow, type AuditLogItem,
} from '../../api'

const resource = ref('tag')
const data = ref<TaxonomyRow[]>([])
const saving = ref(false)
const search = reactive<Record<string, unknown>>({})

const statusMap: Record<number, string> = { 0: '待审核', 1: '已通过', 2: '已驳回' }
const statusText = (s: number): string => statusMap[s] || '未知'
const statusTag = (s: number): 'warning' | 'success' | 'danger' =>
  s === 0 ? 'warning' : s === 1 ? 'success' : 'danger'

const option = reactive<Record<string, unknown>>({
  card: true, border: false, stripe: true, menuWidth: 300,
  addBtn: true, editBtn: false, delBtn: false,
  column: [
    { label: '名称', prop: 'name', minWidth: 160, search: true },
    { label: '简介', prop: 'description', minWidth: 180 },
    { label: '影片数', prop: 'videoCount', width: 90 },
    { label: '状态', prop: 'auditStatus', width: 100 },
    { label: '发布', prop: 'isPublished', width: 90 },
    { label: '创建者', prop: 'createdByName', width: 120 },
    { label: '驳回理由', prop: 'auditReason', minWidth: 160 },
  ],
})

const load = async (done?: () => void): Promise<void> => {
  try { data.value = (await listTaxonomy(resource.value)).items }
  catch (error) { ElMessage.error((error as Error).message) }
  finally { done?.() }
}
const onLoad = async (_paged: unknown, _params: Record<string, unknown>, done?: () => void): Promise<void> => load(done)
const reload = (): void => { void load() }

const buildPayload = (form: Record<string, unknown>): Record<string, unknown> => {
  const payload: Record<string, unknown> = {
    name: String(form.name || '').trim(),
    isPublished: Boolean(form.isPublished),
  }
  if (resource.value === 'collection') payload.description = String(form.description || '').trim()
  return payload
}
const onSave = async (form: Record<string, unknown>, done: () => void): Promise<void> => {
  try {
    await createTaxonomy(resource.value, buildPayload(form))
    ElMessage.success('已创建，等待审核')
    done()
    await load()
  } catch (error) { ElMessage.error((error as Error).message) }
}
const onUpdate = async (form: Record<string, unknown> & { id: number }, done: () => void): Promise<void> => {
  try {
    await updateTaxonomy(resource.value, form.id, buildPayload(form))
    ElMessage.success('已更新')
    done()
    await load()
  } catch (error) { ElMessage.error((error as Error).message) }
}
const onDelete = async (row: TaxonomyRow, done?: () => void): Promise<void> => {
  try {
    await ElMessageBox.confirm(`确认删除「${row.name}」？`, '提示', { type: 'warning' })
    await deleteTaxonomy(resource.value, row.id)
    ElMessage.success('已删除')
    await load()
  } catch (error) {
    if ((error as Error).message !== 'cancel') ElMessage.error((error as Error).message)
  } finally { done?.() }
}

const editVisible = ref(false)
const editForm = reactive({ id: 0, name: '', description: '', isPublished: false })
const openEdit = (row: TaxonomyRow): void => {
  editForm.id = row.id
  editForm.name = row.name
  editForm.description = row.description || ''
  editForm.isPublished = row.isPublished
  editVisible.value = true
}
const submitEdit = async (): Promise<void> => {
  if (!editForm.name.trim()) { ElMessage.warning('请填写名称'); return }
  saving.value = true
  try {
    await updateTaxonomy(resource.value, editForm.id, buildPayload({ ...editForm }))
    ElMessage.success('已更新')
    editVisible.value = false
    await load()
  } catch (error) { ElMessage.error((error as Error).message) }
  finally { saving.value = false }
}

const doReview = async (row: TaxonomyRow, action: string, reason = ''): Promise<void> => {
  try {
    const result = await reviewTaxonomy(resource.value, row.id, { action, reason })
    ElMessage.success(result.msg || '审核完成')
    await load()
  } catch (error) { ElMessage.error((error as Error).message) }
}
const rejectVisible = ref(false)
const rejectTarget = ref<TaxonomyRow | null>(null)
const rejectReason = ref('')
const openReject = (row: TaxonomyRow): void => {
  rejectTarget.value = row; rejectReason.value = ''; rejectVisible.value = true
}
const confirmReject = async (): Promise<void> => {
  if (!rejectReason.value.trim() || !rejectTarget.value) return
  await doReview(rejectTarget.value, 'reject', rejectReason.value.trim())
  rejectVisible.value = false
}
const doResubmit = async (row: TaxonomyRow): Promise<void> => {
  try { await resubmitTaxonomy(resource.value, row.id); ElMessage.success('已重新提交'); await load() }
  catch (error) { ElMessage.error((error as Error).message) }
}

const logsVisible = ref(false)
const logsTarget = ref<TaxonomyRow | null>(null)
const logs = ref<AuditLogItem[]>([])
const openLogs = async (row: TaxonomyRow): Promise<void> => {
  logsTarget.value = row
  try { logs.value = (await listTaxonomyLogs(resource.value, row.id)).items }
  catch (error) { ElMessage.error((error as Error).message); logs.value = [] }
  logsVisible.value = true
}
</script>
