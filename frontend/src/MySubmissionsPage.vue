<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import VideoCard from './components/VideoCard.vue'
import VideoFormModal from './components/VideoFormModal.vue'
import AuditTimeline from './components/AuditTimeline.vue'
import PaginationBar from './components/PaginationBar.vue'
import {
  listVideos, deleteVideo, toggleFavorite, togglePublic, markNotificationsRead,
} from './api'
import { showToast } from './ui/toast'
import { confirmAction } from './ui/confirm'

const router = useRouter()

// 返回影库 / 播放预览
const goBack = () => router.push({ name: 'list' })
const goPlay = (row) => router.push({ name: 'play', params: { id: row.id } })

// ================= 状态页签 =================
const activeTab = ref(-1) // -1 全部 / 0 待审核 / 2 未通过 / 1 已通过
const TABS = [
  { value: -1, label: '全部提交' },
  { value: 0, label: '待审核' },
  { value: 2, label: '未通过' },
  { value: 1, label: '已通过' },
]

// ================= 查询（scope=mine：本人所有状态） =================
const page = ref(1)
const pageSize = ref(12)
const total = ref(0)
const items = ref([])
const loading = ref(false)

const load = async () => {
  loading.value = true
  try {
    const params = { scope: 'mine', page: page.value, pageSize: pageSize.value }
    if (activeTab.value !== -1) params.auditStatus = activeTab.value
    const data = await listVideos(params)
    items.value = data.items
    total.value = data.total
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

const goPage = (p) => {
  page.value = p
  load()
}

const changeSize = (s) => {
  pageSize.value = s
  page.value = 1
  load()
}

// ================= 审核记录（行内展开，不用弹框） =================
const logVideo = ref(null)
const openLog = (row) => {
  logVideo.value = logVideo.value?.id === row.id ? null : row
}

// ================= 卡片操作 =================
const formModal = ref(null)
const openEdit = (row) => formModal.value?.open(row)

// 编辑保存后：被驳回的视频会自动重新进入待审核；切回「全部提交」避免卡片从当前页签消失
const onSaved = () => {
  activeTab.value = -1
  page.value = 1
  logVideo.value = null // 状态可能已变，收起记录面板，再点开即重新加载
  load()
}

const toggleFav = async (row) => {
  try {
    const data = await toggleFavorite(row.id)
    row.isFavorite = data.isFavorite
    showToast(data.isFavorite ? '已收藏' : '已取消收藏')
  } catch (e) {
    showToast.error(e.message)
  }
}

const togglePub = async (row) => {
  if (row.auditStatus !== 1) {
    showToast.warning('视频需先通过审核才能设为公开')
    return
  }
  try {
    const data = await togglePublic(row.id)
    row.isPublic = data.isPublic
    showToast(data.isPublic ? '已设为公开，所有用户可观看' : '已设为私有，仅自己可见')
  } catch (e) {
    showToast.error(e.message)
  }
}

const remove = async (row) => {
  const ok = await confirmAction({
    title: '删除确认',
    message:
      `确认删除视频「${row.title}」？\n` +
      `将同时删除数据库记录与磁盘上的视频源文件（含缩略图缓存），此操作不可恢复！`,
  })
  if (!ok) return
  try {
    await deleteVideo(row.id)
    showToast('已删除')
    logVideo.value = null
    load()
  } catch (e) {
    showToast.error(e.message)
  }
}

onMounted(() => {
  load()
  // 打开审核结果页即视为已读：清空导航上的未读角标（失败不影响页面）
  markNotificationsRead(null).catch(() => {})
})
</script>

<template>
  <div class="sub-page">
    <!-- 页头 -->
    <div class="sub-head">
      <button class="back-btn" title="返回影库" @click="goBack">
        <svg viewBox="0 0 24 24" width="15" height="15">
          <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z" fill="currentColor" />
        </svg>
        返回
      </button>
      <h1 class="sub-title">审核结果</h1>
      <span class="sub-desc">我上传的视频 · 通过审核后才会展示在影库中</span>
    </div>

    <!-- 流程说明 -->
    <div class="flow-note">
      <span class="flow-item"><i class="dot pending"></i> 上传 → 待管理员审核</span>
      <span class="flow-arrow">›</span>
      <span class="flow-item"><i class="dot pass"></i> 通过 → 进入影库，可设置是否公开</span>
      <span class="flow-arrow">›</span>
      <span class="flow-item"><i class="dot reject"></i> 驳回 → 查看理由，修改后保存即重新送审</span>
    </div>

    <!-- 状态页签 -->
    <div class="sub-toolbar">
      <div class="sub-tabs">
        <button
          v-for="tab in TABS"
          :key="tab.value"
          class="sub-tab"
          :class="{ on: activeTab === tab.value }"
          @click="switchTab(tab.value)"
        >
          {{ tab.label }}
        </button>
      </div>
      <span class="sub-count">共 {{ total }} 部</span>
    </div>

    <!-- 行内展开：本人视频的完整审核留痕（含每次驳回理由） -->
    <div v-if="logVideo" class="log-panel">
      <div class="log-panel-head">
        <span class="log-panel-title">「{{ logVideo.title }}」的审核记录</span>
        <button class="log-panel-close" @click="logVideo = null">收起 ✕</button>
      </div>
      <AuditTimeline :key="logVideo.id" :video-id="logVideo.id" />
    </div>

    <!-- 加载态 -->
    <div v-if="loading" class="sub-loading"><div class="nf-loading"></div></div>

    <!-- 空态 -->
    <div v-else-if="!items.length" class="sub-empty">
      <div class="empty-icon">📋</div>
      <div class="empty-text">暂无相关提交</div>
      <div class="empty-sub">上传新视频后，可在这里查看审核进度与未通过理由</div>
      <button class="nf-btn red" @click="goBack">返回影库上传视频</button>
    </div>

    <!-- 本人视频卡片墙（驳回视频带红色理由条） -->
    <div v-else class="video-grid">
      <VideoCard
        v-for="row in items"
        :key="row.id"
        :video="row"
        :manageable="true"
        :show-owner="false"
        :show-audit-log="true"
        @audit-log="openLog"
        @play="goPlay"
        @edit="openEdit"
        @remove="remove"
        @toggle-fav="toggleFav"
        @toggle-public="togglePub"
      />
    </div>

    <!-- 分页 -->
    <PaginationBar
      :total="total"
      :page="page"
      :page-size="pageSize"
      @go-page="goPage"
      @size-change="changeSize"
    />

    <!-- 编辑弹框：复用影库同一表单，保存后自动刷新 -->
    <VideoFormModal ref="formModal" @saved="onSaved" />
  </div>
</template>

<style scoped>
.sub-page {
  max-width: 1400px;
  margin: 0 auto;
  padding: 26px 40px 40px;
}

/* 页头 */
.sub-head {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 16px;
}

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

.sub-title {
  position: relative;
  margin: 0;
  padding-left: 14px;
  font-size: 21px;
  font-weight: 800;
  letter-spacing: 1px;
  color: #fff;
}

.sub-title::before {
  content: '';
  position: absolute;
  left: 0;
  top: 4px;
  bottom: 4px;
  width: 4px;
  border-radius: 2px;
  background: var(--nf-red);
}

.sub-desc {
  font-size: 12.5px;
  color: var(--nf-text-muted);
}

/* 流程说明 */
.flow-note {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 18px;
  padding: 10px 14px;
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: 8px;
  background: rgba(24, 24, 27, 0.6);
  font-size: 12px;
  color: var(--nf-text-secondary);
}

.flow-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  display: inline-block;
}

.dot.pending {
  background: #be8a00;
}

.dot.pass {
  background: #008060;
}

.dot.reject {
  background: #e50914;
}

.flow-arrow {
  color: var(--nf-text-muted);
}

/* 工具条 */
.sub-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 18px;
}

.sub-tabs {
  display: flex;
  gap: 8px;
}

.sub-tab {
  padding: 6px 16px;
  border: 1px solid #333338;
  border-radius: 16px;
  background: transparent;
  color: var(--nf-text-secondary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.sub-tab:hover {
  color: #fff;
  border-color: #55555c;
}

.sub-tab.on {
  background: var(--nf-red);
  border-color: var(--nf-red);
  color: #fff;
  font-weight: 600;
}

.sub-count {
  font-size: 12.5px;
  color: var(--nf-text-muted);
}

/* 行内审核记录面板 */
.log-panel {
  margin-bottom: 20px;
  padding: 16px 20px 18px;
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-left: 3px solid var(--nf-red);
  border-radius: 8px;
  background: rgba(24, 24, 27, 0.75);
}

.log-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
}

.log-panel-title {
  font-size: 13.5px;
  font-weight: 700;
  color: #fff;
}

.log-panel-close {
  padding: 4px 10px;
  border: 1px solid #3a3a42;
  border-radius: 4px;
  background: transparent;
  color: var(--nf-text-secondary);
  font-size: 12px;
  font-family: inherit;
  cursor: pointer;
}

.log-panel-close:hover {
  color: #fff;
  border-color: #6a6a74;
}

/* 加载 / 空态 */
.sub-loading {
  display: flex;
  justify-content: center;
  padding: 60px 0;
}

.sub-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  min-height: 320px;
  padding: 40px 24px;
  border: 1px dashed #2e2e34;
  border-radius: 10px;
  text-align: center;
}

.empty-icon {
  font-size: 44px;
  opacity: 0.75;
}

.empty-text {
  font-size: 17px;
  font-weight: 700;
  color: var(--nf-text-secondary);
}

.empty-sub {
  font-size: 13px;
  color: var(--nf-text-muted);
  margin-bottom: 10px;
}

/* 卡片墙：与影库主列表一致 */
.video-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, 320px);
  justify-content: start;
  gap: 18px;
  min-height: 160px;
}

@media (max-width: 900px) {
  .sub-page {
    padding: 22px 20px 32px;
  }
}
</style>
