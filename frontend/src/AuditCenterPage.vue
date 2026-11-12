<script setup>
import { ICONS } from './composables/icons'
import FaIcon from './ui/FaIcon.vue'
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { listVideos, auditVideo, listAuditLogs } from './api'
import PaginationBar from './components/PaginationBar.vue'
import AuditTimeline from './components/AuditTimeline.vue'
import { showToast } from './ui/toast'

const router = useRouter()

// 返回影库列表页
const goBack = () => router.push({ name: 'list' })

// ================= 状态页签 =================
const activeTab = ref(0) // 0 待审核 / 1 已通过 / 2 已驳回 / -1 全部 / 'logs' 审核记录流水
const TABS = [
  { value: 0, label: '待审核' },
  { value: 1, label: '已通过' },
  { value: 2, label: '已驳回' },
  { value: -1, label: '全部' },
  { value: 'logs', label: '审核记录' },
]

const LOG_ACTIONS = [
  { value: '', label: '全部动作' },
  { value: 'submit', label: '提交审核' },
  { value: 'resubmit', label: '重新提交' },
  { value: 'approve', label: '审核通过' },
  { value: 'reject', label: '审核驳回' },
  { value: 'auto_approve', label: '免审通过' },
]

// ================= 查询 =================
const keyword = ref('')
const logAction = ref('')
const page = ref(1)
const pageSize = ref(12)
const total = ref(0)
const items = ref([]) // 视频列表
const logItems = ref([]) // 审核流水
const loading = ref(false)

// 视频列表（scope=audit：所有用户、所有状态）
const loadVideos = async () => {
  loading.value = true
  try {
    const params = {
      scope: 'audit', // 审核中心查看所有用户、所有状态
      page: page.value,
      pageSize: pageSize.value,
      keyword: keyword.value.trim() || undefined,
    }
    if (activeTab.value !== -1) params.auditStatus = activeTab.value
    const data = await listVideos(params)
    items.value = data.items
    total.value = data.total
    // 删页后页码越界时回退一页重查
    if (page.value > 1 && !data.items.length && data.total > 0) {
      page.value = Math.max(1, Math.ceil(data.total / pageSize.value))
      return loadVideos()
    }
  } catch (e) {
    showToast.error(e.message)
  } finally {
    loading.value = false
  }
}

// 审核流水（全局留痕，仅超管）
const loadLogs = async () => {
  loading.value = true
  try {
    const data = await listAuditLogs({
      page: page.value,
      pageSize: pageSize.value,
      keyword: keyword.value.trim() || undefined,
      action: logAction.value || undefined,
    })
    logItems.value = data.items
    total.value = data.total
    if (page.value > 1 && !data.items.length && data.total > 0) {
      page.value = Math.max(1, Math.ceil(data.total / pageSize.value))
      return loadLogs()
    }
  } catch (e) {
    showToast.error(e.message)
  } finally {
    loading.value = false
  }
}

const load = () => (activeTab.value === 'logs' ? loadLogs() : loadVideos())

const switchTab = (value) => {
  activeTab.value = value
  page.value = 1
  keyword.value = ''
  logAction.value = ''
  timelineId.value = null
  cancelReject()
  load()
}

const onSearch = () => {
  page.value = 1
  load()
}

const goPage = (p) => {
  page.value = p
  load()
}

const changeSize = (s) => {
  pageSize.value = s
  page.value = 1
  load()
}

// ================= 审核操作 =================
// 通过：清空理由，视频进入主影库，公开与否由上传用户自行设置
const approve = async (row) => {
  try {
    await auditVideo(row.id, 1)
    showToast(`「${row.title}」已通过审核，已允许展示`)
    timelineVersion.value++
    load()
  } catch (e) {
    showToast.error(e.message)
  }
}

// 驳回：在表格该行下方展开理由输入框（无需弹框），理由会展示给上传用户
const rejectingId = ref(null)
const rejectReason = ref('')
const rejectError = ref('')
const QUICK_REASONS = ['画面/音质不清晰', '内容不符合要求', '文件无法播放或路径失效', '标题与资料不完整']

const openReject = (row) => {
  rejectingId.value = row.id
  rejectReason.value = ''
  rejectError.value = ''
  timelineId.value = null
}

const cancelReject = () => {
  rejectingId.value = null
  rejectReason.value = ''
  rejectError.value = ''
}

const confirmReject = async (row) => {
  const reason = rejectReason.value.trim()
  if (!reason) {
    rejectError.value = '请填写驳回理由，上传用户需要知道未通过的原因'
    return
  }
  try {
    await auditVideo(row.id, 2, reason)
    showToast(`「${row.title}」已驳回，理由已通知上传用户`)
    cancelReject()
    timelineVersion.value++
    load()
  } catch (e) {
    showToast.error(e.message)
  }
}

// ================= 单视频审核记录（表格行内展开，不用弹框） =================
const timelineId = ref(null)
const timelineVersion = ref(0) // 审核动作后自增，强制已展开的时间线重新加载
const toggleTimeline = (id) => {
  timelineId.value = timelineId.value === id ? null : id
  if (timelineId.value) cancelReject()
}

// 全局流水里点「只看该片」：按标题过滤出这条视频的完整轨迹
const filterByVideo = (title) => {
  keyword.value = title
  logAction.value = '' // 清掉动作筛选，才能看到该片从上传到审核的完整轨迹
  page.value = 1
  loadLogs()
}

// ================= 缩略图（后端 ffmpeg 缩略图优先，失败退占位图） =================
const thumbUrl = (row) =>
  row.filePath && !/^https?:\/\//.test(row.filePath) ? `/api/videos/${row.id}/thumb` : ''
const thumbFailed = ref({}) // { [videoId]: true }

const STATUS_TEXT = { 0: '待审核', 1: '已通过', 2: '已驳回' }

onMounted(load)
</script>

<template>
  <div class="audit-page">
    <!-- 页头 -->
    <div class="audit-head">
      <button class="back-btn" title="返回影库" @click="goBack">
        <FaIcon :icon="ICONS.back" :fixed="false" class="text-[15px]" />
        返回
      </button>
      <h1 class="audit-title">审核中心</h1>
      <span class="audit-sub">通过 → 允许展示；驳回 → 需填写理由，上传用户可按理由修改后重新提交</span>
    </div>

    <!-- 工具条：状态页签 + 搜索 -->
    <div class="audit-toolbar">
      <div class="audit-tabs">
        <button
          v-for="tab in TABS"
          :key="tab.value"
          class="audit-tab"
          :class="{ on: activeTab === tab.value }"
          @click="switchTab(tab.value)"
        >
          {{ tab.label }}
        </button>
      </div>
      <div class="audit-tools">
        <select v-if="activeTab === 'logs'" v-model="logAction" class="log-select" @change="onSearch">
          <option v-for="a in LOG_ACTIONS" :key="a.value" :value="a.value">{{ a.label }}</option>
        </select>
        <div class="audit-search">
          <FaIcon :icon="ICONS.search" :fixed="false" class="text-[13px]" />
          <input
            v-model="keyword"
            class="search-input"
            :placeholder="activeTab === 'logs' ? '搜索影片 / 用户 / 理由' : '搜索标题 / 路径 / 备注'"
            @keyup.enter="onSearch"
          />
        </div>
      </div>
    </div>

    <!-- 加载态 -->
    <div v-if="loading" class="audit-loading"><div class="nf-loading"></div></div>

    <!-- 审核记录：全局留痕流水（只追加、按时间倒序） -->
    <template v-else-if="activeTab === 'logs'">
      <div v-if="!logItems.length" class="audit-empty">暂无审核记录</div>
      <table v-else class="audit-table log-table">
        <thead>
          <tr>
            <th class="col-time">时间</th>
            <th class="col-film">影片 / 上传者</th>
            <th class="col-action">动作</th>
            <th class="col-owner">操作人</th>
            <th class="col-status-change">状态变化</th>
            <th class="col-reason">说明 / 驳回理由</th>
            <th class="col-ops">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="log in logItems" :key="log.id">
            <td class="col-time">{{ log.createdAt }}</td>
            <td class="col-film">
              <div class="film-title" :title="log.videoTitle">{{ log.videoTitle || '（视频已删除）' }}</div>
              <div class="film-path">上传者：{{ log.ownerName || '—' }}</div>
            </td>
            <td class="col-action">
              <span class="log-badge" :class="`a-${log.action}`">{{ log.actionText }}</span>
            </td>
            <td class="col-owner">{{ log.operatorName }}</td>
            <td class="col-status-change">
              {{ log.fromStatusText ? `${log.fromStatusText} → ${log.toStatusText}` : `初始 → ${log.toStatusText}` }}
            </td>
            <td class="col-reason">
              <span v-if="log.reason" class="reason-text" :class="{ reject: log.action === 'reject' }" :title="log.reason">
                {{ log.reason }}
              </span>
              <span v-else class="bar-muted">—</span>
            </td>
            <td class="col-ops">
              <button class="nf-btn sm ghost" @click="filterByVideo(log.videoTitle)"><FaIcon :icon="ICONS.filter" :fixed="false" />只看该片</button>
            </td>
          </tr>
        </tbody>
      </table>
    </template>

    <!-- 视频审核表格 -->
    <template v-else>
      <div v-if="!items.length" class="audit-empty">暂无相关视频</div>
      <table v-if="items.length" class="audit-table">
        <thead>
        <tr>
          <th class="col-film">影片</th>
          <th class="col-owner">归属用户</th>
          <th class="col-type">类型</th>
          <th class="col-public">公开</th>
          <th class="col-status">审核状态</th>
          <th class="col-reason">驳回理由</th>
          <th class="col-time">提交时间</th>
          <th class="col-ops">操作</th>
        </tr>
      </thead>
      <tbody>
        <template v-for="row in items" :key="row.id">
          <tr>
          <!-- 影片：缩略图 + 标题 + 路径 -->
          <td class="col-film">
            <div class="film-cell">
              <div class="thumb-box">
                <img
                  v-if="thumbUrl(row) && !thumbFailed[row.id]"
                  class="thumb"
                  :src="thumbUrl(row)"
                  loading="lazy"
                  @error="thumbFailed[row.id] = true"
                />
                <div v-else class="thumb-fallback"><FaIcon icon="film" :fixed="false" /></div>
              </div>
              <div class="film-info">
                <div class="film-title" :title="row.title">{{ row.title }}</div>
                <div class="film-path" :title="row.filePath">{{ row.filePath }}</div>
              </div>
            </div>
          </td>
          <td class="col-owner">{{ row.ownerName }}</td>
          <td class="col-type">{{ row.typeName || '—' }}</td>
          <td class="col-public">
            <span class="pub-flag" :class="{ on: row.isPublic }">
              {{ row.isPublic ? '公开' : '私有' }}
            </span>
          </td>
          <td class="col-status">
            <span
              class="state-badge"
              :class="[`s${row.auditStatus}`, { exempt: row.auditStatus === 1 && row.lastAction === 'auto_approve' }]"
            >
              {{ row.auditStatus === 1 && row.lastAction === 'auto_approve' ? '免审通过' : STATUS_TEXT[row.auditStatus] }}
            </span>
          </td>
          <td class="col-reason">
            <span v-if="row.auditStatus === 2 && row.auditReason" class="reason-text" :title="row.auditReason">
              {{ row.auditReason }}
            </span>
            <span v-else class="bar-muted">—</span>
          </td>
          <td class="col-time">{{ row.createdAt }}</td>
          <td class="col-ops">
            <button class="nf-btn sm ghost" @click="toggleTimeline(row.id)">
              {{ timelineId === row.id ? '收起' : '记录' }}
            </button>
            <template v-if="row.auditStatus === 0">
              <button class="nf-btn sm pass" @click="approve(row)"><FaIcon :icon="ICONS.check" :fixed="false" />通过</button>
              <button class="nf-btn sm ghost danger" @click="openReject(row)"><FaIcon :icon="ICONS.close" :fixed="false" />驳回</button>
            </template>
            <template v-else-if="row.auditStatus === 2">
              <button class="nf-btn sm ghost pass" @click="approve(row)"><FaIcon :icon="ICONS.check" :fixed="false" />恢复通过</button>
            </template>
          </td>
        </tr>

        <!-- 行内驳回：填写理由（替代弹框） -->
        <tr v-if="rejectingId === row.id" class="reject-row">
          <td colspan="8">
            <div class="reject-box">
              <div class="reject-head">
                <span class="reject-title">驳回「{{ row.title }}」</span>
                <span class="reject-tip">理由会展示给上传用户 {{ row.ownerName }}，请写明未通过原因</span>
              </div>
              <div class="reject-quick">
                <button v-for="r in QUICK_REASONS" :key="r" class="quick-reason" @click="rejectReason = r; rejectError = ''">
                  {{ r }}
                </button>
              </div>
              <textarea
                v-model="rejectReason"
                class="nf-textarea"
                rows="2"
                maxlength="500"
                placeholder="例如：画面分辨率过低，请上传清晰度更高的版本后重新提交"
                @input="rejectError = ''"
              ></textarea>
              <div v-if="rejectError" class="reject-error">{{ rejectError }}</div>
              <div class="reject-actions">
                <span class="reject-count">{{ rejectReason.length }}/500</span>
                <button class="nf-btn sm ghost" @click="cancelReject"><FaIcon :icon="ICONS.close" :fixed="false" />取消</button>
                <button class="nf-btn sm red" @click="confirmReject(row)"><FaIcon :icon="ICONS.close" :fixed="false" />确认驳回</button>
              </div>
            </div>
          </td>
        </tr>

        <!-- 行内审核时间线：该视频从上传到每次审核的完整留痕 -->
        <tr v-if="timelineId === row.id" class="timeline-row">
          <td colspan="8"><AuditTimeline :key="`${row.id}-${timelineVersion}`" :video-id="row.id" /></td>
        </tr>
        </template>
      </tbody>
    </table>
    </template>

    <!-- 分页 -->
    <PaginationBar
      :total="total"
      :page="page"
      :page-size="pageSize"
      @go-page="goPage"
      @size-change="changeSize"
    />
  </div>
</template>

<style scoped>
.audit-page {
  max-width: 1400px;
  margin: 0 auto;
  padding: 26px 40px 40px;
}

/* 返回按钮 */
.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 32px;
  padding: 0 14px 0 11px;
  border: 1px solid #333338;
  border-radius: 5px;
  background: #1f1f23;
  color: var(--nf-text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s ease;
  flex-shrink: 0;
}

.back-btn:hover {
  color: #fff;
  border-color: #55555c;
  background: rgba(255, 255, 255, 0.07);
}

/* 页头 */
.audit-head {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 20px;
}

.audit-title {
  position: relative;
  margin: 0;
  padding-left: 14px;
  font-size: 21px;
  font-weight: 800;
  letter-spacing: 1px;
  color: #fff;
}

.audit-title::before {
  content: '';
  position: absolute;
  left: 0;
  top: 4px;
  bottom: 4px;
  width: 4px;
  border-radius: 2px;
  background: var(--nf-red);
}

.audit-sub {
  font-size: 12.5px;
  color: var(--nf-text-muted);
}

/* 工具条 */
.audit-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}

.audit-tabs {
  display: flex;
  gap: 8px;
}

.audit-tab {
  padding: 6px 16px;
  border: 1px solid #333338;
  border-radius: 16px;
  background: transparent;
  color: var(--nf-text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.audit-tab:hover {
  color: #fff;
  border-color: #55555c;
}

.audit-tab.on {
  background: var(--nf-red);
  border-color: var(--nf-red);
  color: #fff;
  font-weight: 600;
}

.audit-search {
  display: flex;
  align-items: center;
  gap: 7px;
  width: 230px;
  height: 34px;
  padding: 0 11px;
  border: 1px solid #333338;
  border-radius: 5px;
  background: #1f1f23;
  color: #8a8a92;
  transition: border-color 0.18s ease;
}

.audit-search:focus-within {
  border-color: rgba(229, 9, 20, 0.75);
}

.search-input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  color: #f5f5f5;
  font-size: 13px;
  font-family: inherit;
}

.search-input::placeholder {
  color: #5c5c63;
}

/* 加载 / 空态 */
.audit-loading {
  display: flex;
  justify-content: center;
  padding: 60px 0;
}

.audit-empty {
  padding: 60px 0;
  text-align: center;
  font-size: 13.5px;
  color: var(--nf-text-muted);
  border: 1px dashed #2e2e34;
  border-radius: 10px;
}

/* ===== 审核表格 ===== */
.audit-table {
  width: 100%;
  border-collapse: collapse;
  background: rgba(24, 24, 27, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: 10px;
  overflow: hidden;
}

.audit-table th {
  padding: 11px 14px;
  background: rgba(255, 255, 255, 0.04);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  font-size: 12.5px;
  font-weight: 600;
  color: var(--nf-text-muted);
  text-align: left;
  white-space: nowrap;
  user-select: none;
}

.audit-table td {
  padding: 10px 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  font-size: 13px;
  color: #d9d9de;
  vertical-align: middle;
}

.audit-table tbody tr:last-child td {
  border-bottom: none;
}

.audit-table tbody tr {
  transition: background 0.15s ease;
}

.audit-table tbody tr:hover {
  background: rgba(255, 255, 255, 0.045);
}

/* 影片列 */
.film-cell {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.thumb-box {
  width: 76px;
  height: 44px;
  flex-shrink: 0;
  border-radius: 5px;
  overflow: hidden;
  background: #101013;
  display: flex;
  align-items: center;
  justify-content: center;
}

.thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.thumb-fallback {
  font-size: 18px;
  opacity: 0.6;
}

.film-info {
  min-width: 0;
}

.film-title {
  font-size: 13.5px;
  font-weight: 600;
  color: #f5f5f5;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 260px;
}

.film-path {
  margin-top: 3px;
  font-size: 11.5px;
  color: var(--nf-text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 260px;
}

.col-owner {
  color: #e08a90;
  white-space: nowrap;
}

.col-type,
.col-time {
  white-space: nowrap;
  color: var(--nf-text-secondary);
}

/* 公开标记 */
.pub-flag {
  padding: 1px 8px;
  border-radius: 9px;
  font-size: 11.5px;
  line-height: 17px;
  background: rgba(255, 255, 255, 0.09);
  color: var(--nf-text-muted);
  white-space: nowrap;
}

.pub-flag.on {
  background: rgba(0, 128, 96, 0.28);
  color: #6fd8ab;
}

/* 审核状态徽章 */
.state-badge {
  padding: 1px 9px;
  border-radius: 9px;
  font-size: 11.5px;
  font-weight: 600;
  line-height: 17px;
  background: rgba(190, 138, 0, 0.9);
  color: #fff;
  white-space: nowrap;
}

.state-badge.s1 {
  background: rgba(0, 128, 96, 0.85);
}

.state-badge.s2 {
  background: rgba(120, 24, 28, 0.92);
}

/* 工具条右侧：动作筛选 + 搜索 */
.audit-tools {
  display: flex;
  align-items: center;
  gap: 10px;
}

.log-select {
  height: 34px;
  padding: 0 10px;
  border: 1px solid #333338;
  border-radius: 5px;
  background: #1f1f23;
  color: var(--nf-text-secondary);
  font-size: 12.5px;
  font-family: inherit;
  outline: none;
  cursor: pointer;
}

.log-select:focus {
  border-color: rgba(229, 9, 20, 0.75);
}

/* 管理员上传的免审通过：用蓝色区别于普通审核通过 */
.state-badge.exempt {
  background: rgba(88, 118, 190, 0.9);
}

/* 行内审核时间线 */
.timeline-row > td {
  background: rgba(255, 255, 255, 0.035);
  padding: 14px 24px 16px !important;
  border-bottom: 1px solid rgba(255, 255, 255, 0.09) !important;
}

/* 全局流水表格 */
.log-table .film-title {
  max-width: 260px;
}

.log-table .film-path {
  color: #e08a90;
}

.log-table .col-action,
.log-table .col-status-change {
  white-space: nowrap;
}

.log-table .col-status-change {
  font-size: 12px;
  color: var(--nf-text-secondary);
}

.log-badge {
  display: inline-block;
  padding: 2px 9px;
  border-radius: 9px;
  font-size: 11.5px;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.1);
  color: #d9d9de;
  white-space: nowrap;
}

.log-badge.a-approve { background: rgba(0, 128, 96, 0.85); color: #fff; }
.log-badge.a-reject { background: rgba(150, 26, 32, 0.92); color: #fff; }
.log-badge.a-submit { background: rgba(190, 138, 0, 0.9); color: #fff; }
.log-badge.a-resubmit { background: rgba(190, 138, 0, 0.65); color: #fff; }
.log-badge.a-auto_approve { background: rgba(88, 118, 190, 0.9); color: #fff; }

.log-table .reason-text {
  color: var(--nf-text-secondary);
  -webkit-line-clamp: 2;
}

.log-table .reason-text.reject {
  color: #ff9ba1;
}

/* 驳回理由列 */
.col-reason {
  max-width: 190px;
}

.reason-text {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-size: 12px;
  color: #ff9ba1;
  line-height: 1.5;
}

/* 行内驳回输入区 */
.reject-row > td {
  background: rgba(229, 9, 20, 0.06);
  padding: 12px 16px 14px !important;
  border-bottom: 1px solid rgba(229, 9, 20, 0.25) !important;
  white-space: normal;
}

.reject-box {
  display: flex;
  flex-direction: column;
  gap: 9px;
  max-width: 720px;
}

.reject-head {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 10px;
}

.reject-title {
  font-size: 13.5px;
  font-weight: 700;
  color: #ffb3b8;
}

.reject-tip {
  font-size: 12px;
  color: var(--nf-text-muted);
}

.reject-quick {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.quick-reason {
  padding: 3px 10px;
  border: 1px solid #3a3a42;
  border-radius: 12px;
  background: transparent;
  color: var(--nf-text-secondary);
  font-size: 11.5px;
  cursor: pointer;
}

.quick-reason:hover {
  color: #fff;
  border-color: #6a6a74;
  background: rgba(255, 255, 255, 0.05);
}

.reject-box .nf-textarea {
  font-size: 13px;
  resize: vertical;
}

.reject-error {
  font-size: 12px;
  color: #ff6b72;
}

.reject-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}

.reject-count {
  margin-right: auto;
  font-size: 11.5px;
  color: var(--nf-text-muted);
}

.reject-actions .nf-btn {
  height: 28px;
  padding: 0 13px;
}

/* 操作列 */
.col-ops {
  white-space: nowrap;
}

.col-ops .nf-btn {
  height: 28px;
  padding: 0 13px;
}

.col-ops .nf-btn + .nf-btn {
  margin-left: 6px;
}

.col-ops .pass {
  background: rgba(0, 128, 96, 0.85);
  color: #fff;
}

.col-ops .pass:hover {
  filter: brightness(1.12);
}

.col-ops .ghost.pass {
  background: transparent;
  border: 1px solid rgba(0, 128, 96, 0.7);
  color: #6fd8ab;
}

.col-ops .ghost.pass:hover {
  background: rgba(0, 128, 96, 0.85);
  color: #fff;
}

.col-ops .ghost.danger:hover {
  background: rgba(229, 9, 20, 0.8);
}

.bar-muted {
  font-size: 12px;
  color: var(--nf-text-muted);
}

/* 响应式：小屏让整页横向滚动，表格列不被压缩到无法阅读 */
@media (max-width: 1000px) {
  .audit-page {
    padding: 22px 20px 32px;
    overflow-x: auto;
  }

  .audit-table {
    min-width: 880px;
  }

  .audit-head,
  .audit-tabs,
  .audit-toolbar,
  .audit-search {
    min-width: 880px;
  }
}
</style>
