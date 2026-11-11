<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { listVideos, auditVideo } from './api'
import PaginationBar from './components/PaginationBar.vue'
import { showToast } from './ui/toast'
import { confirmAction } from './ui/confirm'

const router = useRouter()

// 返回影库列表页
const goBack = () => router.push({ name: 'list' })

// ================= 状态页签 =================
const activeTab = ref(0) // 0 待审核 / 1 已通过 / 2 已驳回 / -1 全部
const TABS = [
  { value: 0, label: '待审核' },
  { value: 1, label: '已通过' },
  { value: 2, label: '已驳回' },
  { value: -1, label: '全部' },
]

// ================= 查询 =================
const keyword = ref('')
const page = ref(1)
const pageSize = ref(12)
const total = ref(0)
const items = ref([])
const loading = ref(false)

const load = async () => {
  loading.value = true
  try {
    const params = {
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
      return load()
    }
  } catch (e) {
    showToast.error(e.message)
  } finally {
    loading.value = false
  }
}

const switchTab = (value) => {
  activeTab.value = value
  page.value = 1
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
const setStatus = async (row, status) => {
  if (status === 2) {
    const ok = await confirmAction({
      title: '驳回确认',
      message: `确认驳回视频「${row.title}」？驳回后该视频将自动转为私有，仅归属者本人可见。`,
    })
    if (!ok) return
  }
  try {
    await auditVideo(row.id, status)
    row.auditStatus = status
    if (status === 2) row.isPublic = false
    showToast(status === 1 ? `「${row.title}」已通过审核` : `「${row.title}」已驳回`)
    load()
  } catch (e) {
    showToast.error(e.message)
  }
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
        <svg viewBox="0 0 24 24" width="15" height="15">
          <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z" fill="currentColor" />
        </svg>
        返回
      </button>
      <h1 class="audit-title">审核中心</h1>
      <span class="audit-sub">超级管理员专属 · 审核通过的视频才允许公开给所有用户观看</span>
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
      <div class="audit-search">
        <svg viewBox="0 0 24 24" width="13" height="13">
          <path
            d="M15.5 14h-.79l-.28-.27a6.5 6.5 0 1 0-.7.7l.27.28v.79l5 4.99L20.49 19zm-6 0A4.5 4.5 0 1 1 14 9.5 4.5 4.5 0 0 1 9.5 14z"
            fill="currentColor"
          />
        </svg>
        <input
          v-model="keyword"
          class="search-input"
          placeholder="搜索标题 / 路径 / 备注"
          @keyup.enter="onSearch"
        />
      </div>
    </div>

    <!-- 加载态 -->
    <div v-if="loading" class="audit-loading"><div class="nf-loading"></div></div>

    <!-- 空态 -->
    <div v-else-if="!items.length" class="audit-empty">暂无相关视频</div>

    <!-- 审核表格 -->
    <table v-else class="audit-table">
      <thead>
        <tr>
          <th class="col-film">影片</th>
          <th class="col-owner">归属用户</th>
          <th class="col-type">类型</th>
          <th class="col-public">公开</th>
          <th class="col-status">审核状态</th>
          <th class="col-time">提交时间</th>
          <th class="col-ops">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in items" :key="row.id">
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
                <div v-else class="thumb-fallback">🎬</div>
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
            <span class="state-badge" :class="`s${row.auditStatus}`">
              {{ STATUS_TEXT[row.auditStatus] }}
            </span>
          </td>
          <td class="col-time">{{ row.createdAt }}</td>
          <td class="col-ops">
            <template v-if="row.auditStatus === 0">
              <button class="nf-btn sm pass" @click="setStatus(row, 1)">通过</button>
              <button class="nf-btn sm ghost danger" @click="setStatus(row, 2)">驳回</button>
            </template>
            <template v-else-if="row.auditStatus === 2">
              <button class="nf-btn sm ghost pass" @click="setStatus(row, 1)">恢复通过</button>
            </template>
            <span v-else class="bar-muted">—</span>
          </td>
        </tr>
      </tbody>
    </table>

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

/* 响应式：小屏横向滚动 */
@media (max-width: 1000px) {
  .audit-page {
    padding: 22px 20px 32px;
  }

  .audit-table {
    display: block;
    overflow-x: auto;
  }
}
</style>
