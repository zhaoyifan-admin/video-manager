<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import SiteNav from './components/SiteNav.vue'
import HeroCarousel from './components/HeroCarousel.vue'
import VideoCard from './components/VideoCard.vue'
import PaginationBar from './components/PaginationBar.vue'
import VideoFormModal from './components/VideoFormModal.vue'
import BatchImportModal from './components/BatchImportModal.vue'
import ManageModal from './components/ManageModal.vue'
import { useVideos } from './composables/useVideos'
import { useAuth } from './composables/useAuth'
import {
  listTags,
  listTypes,
  listVideos,
  toggleFavorite,
  togglePublic,
  auditVideo,
  deleteVideo,
  logout as apiLogout,
} from './api'
import { showToast } from './ui/toast'
import { confirmAction } from './ui/confirm'

const router = useRouter()

// ================= 登录态（路由守卫已确保已登录才进入本页） =================
const { user, resetAuth } = useAuth()

// 超级管理员：可查看并管理所有用户的视频
const isSuperAdmin = computed(() => user.value?.role === 'admin')

// 编辑/删除/公开设置权限：本人视频或超级管理员
const canManage = (row) => isSuperAdmin.value || row.ownerId === user.value?.id

const handleLogout = async () => {
  try {
    await apiLogout()
  } catch {
    // 退出接口失败也照样清理本地登录态
  }
  resetAuth()
  showToast('已退出登录')
  router.push({ name: 'login' })
}

// ================= 标签 / 类型（导航与筛选用） =================
const tags = ref([])
const types = ref([])

const loadTags = async () => {
  tags.value = await listTags()
}

const loadTypes = async () => {
  types.value = await listTypes()
}

// ================= 查询 / 分页（来自 useVideos 组合式函数） =================
const {
  query,
  total,
  videos,
  loading,
  fetchVideos,
  onSearch,
  selectType,
  toggleFavFilter,
  goPage,
  changeSize,
  refreshIfFavMode,
} = useVideos()

// 顶部导航搜索框回车
const onNavSearch = (keyword) => {
  query.keyword = keyword
  onSearch()
}

const currentTypeName = computed(() => {
  if (query.favorite) return '我的收藏'
  const t = types.value.find((t) => t.id === query.typeId)
  return t ? t.name : '全部影片'
})

// ================= 播放 / 详情：两个独立动作 =================
// 播放：跳独立播放页（自动播放）
const playVideo = (row) => {
  router.push({ name: 'play', params: { id: row.id } })
}

// 详情：跳独立详情页（只看信息，不承担播放）
const openDetail = (row) => {
  router.push({ name: 'detail', params: { id: row.id } })
}

// ================= 收藏 =================
const toggleFavoriteState = async (row) => {
  try {
    const data = await toggleFavorite(row.id)
    row.isFavorite = data.isFavorite
    refreshIfFavMode() // 「我的收藏」模式下取消收藏后列表需要刷新
    showToast(data.isFavorite ? '已收藏' : '已取消收藏')
  } catch (e) {
    showToast.error(e.message)
  }
}

// ================= 公开 / 私有切换（所有用户可观看） =================
const togglePublicState = async (row) => {
  try {
    const data = await togglePublic(row.id)
    row.isPublic = data.isPublic
    showToast(data.isPublic ? '已设为公开，所有用户可观看' : '已设为私有，仅自己可见')
  } catch (e) {
    showToast.error(e.message)
  }
}

// ================= 删除（数据库 + 磁盘源文件） =================
const removeVideo = async (row) => {
  const ok = await confirmAction({
    title: '删除确认',
    message:
      `确认删除视频「${row.title}」？\n` +
      `将同时删除数据库记录与磁盘上的视频源文件（含缩略图缓存），此操作不可恢复！`,
  })
  if (!ok) return
  try {
    const data = await deleteVideo(row.id)
    showToast(data?.fileDeleted ? '已删除（源文件已一并清理）' : '已删除（源文件不存在，仅清理记录）')
    await fetchVideos()
  } catch (e) {
    showToast.error(e.message)
  }
}

// ================= 弹窗调度 =================
const formModal = ref(null)
const batchModal = ref(null)
const manageModal = ref(null)

const openForm = (row = null) => formModal.value?.open(row)

// 新增/编辑保存后：刷新列表 + 标签 + 类型（新类型/标签可能已创建）+ 待审角标
const onFormSaved = async () => {
  await Promise.all([fetchVideos(), loadTags(), loadTypes(), loadPendingCount()])
}

// 管理弹窗变更后：刷新导航与筛选用的标签/类型
const onManageChanged = async () => {
  await Promise.all([loadTags(), loadTypes()])
}

// ================= 管理员审核 =================
const pendingCount = ref(0) // 待审核数量（导航角标）

const loadPendingCount = async () => {
  if (!isSuperAdmin.value) return
  try {
    const data = await listVideos({ auditStatus: 0, page: 1, pageSize: 1 })
    pendingCount.value = data.total
  } catch {
    // 角标加载失败不阻塞主流程
  }
}

// 卡片快捷审核（通过 / 驳回）
const handleAudit = async (row, status) => {
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
    loadPendingCount()
  } catch (e) {
    showToast.error(e.message)
  }
}

// 审核中心页内完成审核后，回到列表页时组件重新挂载，会自动刷新列表与角标

onMounted(() => {
  loadTags().catch((e) => showToast.error(e.message))
  loadTypes().catch((e) => showToast.error(e.message))
  fetchVideos()
  loadPendingCount()
})
</script>

<template>
  <!-- 顶部导航 -->
  <SiteNav
    :types="types"
    :active-type-id="query.typeId"
    :fav-active="!!query.favorite"
    :username="user?.username || ''"
    :is-admin="isSuperAdmin"
    :pending-count="pendingCount"
    @select-type="selectType"
    @toggle-fav="toggleFavFilter"
    @search="onNavSearch"
    @manage="manageModal?.open()"
    @batch="batchModal?.open()"
    @create="openForm()"
    @logout="handleLogout"
  />

  <!-- Hero 大图轮播 -->
  <HeroCarousel :videos="videos" @play="playVideo" @detail="openDetail" />

  <!-- ===== 影库主体 ===== -->
  <main class="page" :class="{ 'no-hero': !videos.length }">
    <!-- 分区标题 -->
    <div id="library" class="section-head">
      <h2 class="section-title">{{ currentTypeName }}</h2>
      <span class="section-count">共 {{ total }} 部</span>

      <!-- 标签筛选：胶囊单选 -->
      <div class="tag-filter">
        <button class="chip-opt" :class="{ on: query.tagId === 0 }" @click="query.tagId = 0; onSearch()">全部</button>
        <button
          v-for="t in tags"
          :key="t.id"
          class="chip-opt"
          :class="{ on: query.tagId === t.id }"
          @click="query.tagId = t.id; onSearch()"
        >
          {{ t.name }}
        </button>
      </div>
    </div>

    <!-- 加载态 -->
    <div v-if="loading" class="grid-loading">
      <div class="nf-loading"></div>
    </div>

    <!-- 空态：独立整块居中，不进网格 -->
    <div v-else-if="videos.length === 0" class="empty-state">
      <div class="empty-icon">🎬</div>
      <div class="empty-text">暂无影片</div>
      <div class="empty-sub">点击右上角「＋ 新增视频」上传，或使用「批量导入」快速添加</div>
      <button class="nf-btn red" @click="openForm()">＋ 新增视频</button>
    </div>

    <!-- 海报卡片墙 -->
    <div v-else class="video-grid">
      <VideoCard
        v-for="row in videos"
        :key="row.id"
        :video="row"
        :manageable="canManage(row)"
        :can-audit="isSuperAdmin"
        :show-owner="row.ownerId !== user?.id"
        @play="playVideo"
        @edit="openForm"
        @remove="removeVideo"
        @toggle-fav="toggleFavoriteState"
        @toggle-public="togglePublicState"
        @audit="handleAudit"
      />
    </div>

    <!-- 分页 -->
    <PaginationBar
      :total="total"
      :page="query.page"
      :page-size="query.pageSize"
      @go-page="goPage"
      @size-change="(s) => { query.pageSize = s; changeSize() }"
    />
  </main>

  <!-- 页脚 -->
  <footer class="site-footer">
    <div class="footer-brand">影库 <span>VIDEO FACTORY</span></div>
    <div class="footer-tip">本地私人影片管理 · 数据仅存储于本机</div>
    <div class="footer-copy">© {{ new Date().getFullYear() }} Video Manager</div>
  </footer>

  <!-- 弹窗组：新增/编辑 / 批量导入 / 标签类型管理（审核中心已独立为 /audit 页面） -->
  <VideoFormModal ref="formModal" @saved="onFormSaved" />
  <BatchImportModal
    ref="batchModal"
    @imported="() => Promise.all([fetchVideos(), loadTags(), loadTypes(), loadPendingCount()])"
  />
  <ManageModal ref="manageModal" @changed="onManageChanged" />
</template>

<style scoped>
/* ===== 影库主体 ===== */
.page {
  max-width: 1400px;
  margin: 0 auto;
  padding: 26px 40px 40px;
}

.page.no-hero {
  padding-top: 36px;
}

/* 分区标题：红色竖条 + 标题（netflixgc 分区语言） */
.section-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px 18px;
  margin-bottom: 20px;
}

.section-title {
  position: relative;
  margin: 0;
  padding-left: 14px;
  font-size: 21px;
  font-weight: 800;
  letter-spacing: 1px;
  color: #fff;
}

.section-title::before {
  content: '';
  position: absolute;
  left: 0;
  top: 4px;
  bottom: 4px;
  width: 4px;
  border-radius: 2px;
  background: var(--nf-red);
}

.section-count {
  font-size: 13px;
  color: var(--nf-text-muted);
}

.tag-filter {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-left: auto;
}

/* ===== 海报卡片墙 ===== */
.grid-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
}

.video-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, 320px);
  justify-content: start;
  gap: 18px;
  min-height: 160px;
}

/* ===== 空态：独立整块，水平 + 垂直双向居中 ===== */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  min-height: 380px;
  padding: 40px 24px;
  border: 1px dashed #2e2e34;
  border-radius: 10px;
  text-align: center;
}

.empty-icon {
  font-size: 48px;
  opacity: 0.75;
}

.empty-text {
  font-size: 17px;
  font-weight: 700;
  color: var(--nf-text-secondary);
}

.empty-sub {
  font-size: 13px;
  line-height: 1.6;
  color: var(--nf-text-muted);
  margin-bottom: 10px;
}

/* ===== 页脚 ===== */
.site-footer {
  border-top: 1px solid rgba(255, 255, 255, 0.07);
  padding: 26px 40px 34px;
  display: flex;
  align-items: center;
  gap: 16px;
}

.footer-brand {
  font-size: 16px;
  font-weight: 800;
  letter-spacing: 2px;
  color: var(--nf-red);
}

.footer-brand span {
  font-size: 10px;
  letter-spacing: 3px;
  color: var(--nf-text-muted);
  margin-left: 6px;
}

.footer-tip {
  font-size: 12.5px;
  color: var(--nf-text-muted);
}

.footer-copy {
  margin-left: auto;
  font-size: 12px;
  color: #4d4d55;
}

/* 响应式：小屏收紧间距 */
@media (max-width: 900px) {
  .page {
    padding: 22px 20px 32px;
  }

  .tag-filter {
    margin-left: 0;
  }
}
</style>
