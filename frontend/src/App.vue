<script setup>
import { ICONS } from './composables/icons'
import FaIcon from './ui/FaIcon.vue'
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'
import SiteNav from './components/SiteNav.vue'
import HeroCarousel from './components/HeroCarousel.vue'
import VideoCard from './components/VideoCard.vue'
import ChannelFilter from './components/ChannelFilter.vue'
import ChannelPosterCard from './components/ChannelPosterCard.vue'
import PaginationBar from './components/PaginationBar.vue'
import VideoFormModal from './components/VideoFormModal.vue'
import BatchImportModal from './components/BatchImportModal.vue'
import ManageModal from './components/ManageModal.vue'
import PersonalCenterModal from './components/PersonalCenterModal.vue'
import AddToPlaylistModal from './components/AddToPlaylistModal.vue'
import { useVideos } from './composables/useVideos'
import { useAuth } from './composables/useAuth'
import { getPreset, DENSITY_CLASS } from './composables/channelPresets'
import {
  listTags,
  listTypes,
  listVideos,
  getFeaturedVideos,
  getUnreadCount,
  getWatchHistory,
  listCollections,
  listPlaylists,
  toggleFavorite,
  togglePublic,
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
// 有审核权：超管、管理员（限平级及以下）或独立审核员（可进审核中心）
const canAudit = computed(() => ['admin', 'reviewer', 'manager'].includes(user.value?.role))

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
  // 普通用户接口已只返回已发布标签；管理员会拿到 isPublished 字段，筛选项里过滤掉未发布的
  tags.value = (await listTags()).filter((t) => t.isPublished !== false)
}

const loadTypes = async () => {
  // 待审核 / 未发布的类型不进频道导航（接口现已对普通用户返回 isPublished）
  types.value = (await listTypes()).filter((t) => t.isPublished !== false)
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
  toggleWantlist,
  applyFilter,
  resetChannelFilters,
  goPage,
  changeSize,
  refreshIfFavMode,
} = useVideos()

// ================= 频道视图：不同频道 → 不同筛选行 / 排序 / 配色 / 海报密度 =================
const isHome = computed(() => !query.favorite && !query.wantlist && query.typeId === 0 && !query.playlistId)
const isFavMode = computed(() => !!query.favorite)
const isWantMode = computed(() => !!query.wantlist)
const isChannelMode = computed(() => !query.favorite && !query.wantlist && query.typeId !== 0 && !query.playlistId)
// 个人片单查看模式：仅本人片单可进入（后端按归属校验）
const isPlaylistMode = computed(() => !query.favorite && !query.wantlist && query.playlistId !== 0)
const activeChannel = computed(() => types.value.find((t) => t.id === query.typeId))
const channelName = computed(() => activeChannel.value?.name || '全部影片')
const preset = computed(() => getPreset(isHome.value ? '' : channelName.value))
const gridClass = computed(() => DENSITY_CLASS[preset.value.density] || DENSITY_CLASS.mid)
// 首页 / 收藏：断点式列数（替代固定 320px auto-fill，窄屏不再挤压或溢出）
const homeGridClass =
  'grid grid-cols-1 gap-[18px] min-h-[160px] min-[520px]:grid-cols-2 min-[820px]:grid-cols-3 min-[1180px]:grid-cols-4'
// 骨架屏数量跟随当前每页条数，最多 12 个，避免长列表生成过多占位
const skeletonCount = computed(() => Math.min(query.pageSize || 12, 12))
// 卡片错峰入场：序号上限 10，单级 45ms，总时长控制在 0.45s 内
const enterDelay = (i) => `${Math.min(i, 10) * 45}ms`
// 进入片单模式时拉取片单名（用于标题与横幅）
const playlistName = ref('')
const openPlaylist = async (id) => {
  query.favorite = 0
  query.wantlist = 0
  query.typeId = 0
  query.tagId = 0
  query.keyword = ''
  query.playlistId = id
  query.page = 1
  try {
    const data = await listPlaylists()
    const found = (data.items || []).find((p) => p.id === id)
    playlistName.value = found ? found.name : ''
  } catch {
    playlistName.value = ''
  }
  fetchVideos()
  scrollToLibrary()
}
const exitPlaylist = () => {
  query.playlistId = 0
  query.page = 1
  fetchVideos()
  scrollToLibrary()
}
// 片单模式下，加入/移出视频后刷新列表
const onPlaylistChanged = () => {
  if (query.playlistId) fetchVideos()
}
// 面板已提供「合集」行的频道，不再重复显示旧版合集下拉
const showCollectionSelect = computed(
  () => isFavMode.value || !preset.value.rows.includes('collection'),
)
const hasChannelFilters = computed(
  () => !!(query.tagId || query.collectionId || query.region || query.language || query.year || query.letter),
)

// ================= 大图轮播：按热度取最多 9 条（独立于当前分页列表） =================
const featuredVideos = ref([])

const loadFeatured = async () => {
  try {
    const data = await getFeaturedVideos()
    featuredVideos.value = data.items
  } catch {
    // 轮播加载失败不阻塞影库主体
  }
}

// 顶部导航搜索框回车
const onNavSearch = (keyword) => {
  query.keyword = keyword
  onSearch()
}

const currentTypeName = computed(() => {
  if (query.favorite) return '我的收藏'
  if (query.wantlist) return '想看清单'
  if (query.playlistId) return `片单：${playlistName.value || '我的片单'}`
  const t = types.value.find((t) => t.id === query.typeId)
  return t ? t.name : '全部影片'
})

// 列表卡片「加入片单」入口：打开弹窗并传入视频 ID
const playlistModalOpen = ref(false)
const playlistVideoId = ref(0)
const openAddPlaylist = (row) => {
  playlistVideoId.value = row.id
  playlistModalOpen.value = true
}

// ================= 播放 / 详情：两个独立动作 =================
const playVideo = (row) => router.push({ name: 'play', params: { id: row.id } })
const openDetail = (row) => router.push({ name: 'detail', params: { id: row.id } })

// ================= 收藏 =================
const toggleFavoriteState = async (row) => {
  try {
    const data = await toggleFavorite(row.id)
    row.isFavorite = data.isFavorite
    if (typeof data.favoriteCount === 'number') row.favoriteCount = data.favoriteCount
    refreshIfFavMode()
    loadFeatured()
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
    if (data?.fileDeleted) {
      showToast('已删除（源文件已一并清理）')
    } else if (data?.fileMissing) {
      showToast('已删除（源文件本就不存在，仅清理记录）')
    } else {
      showToast.warning('记录已删除，但源文件未能删除（可能正被播放占用或不在媒体白名单内），请到所在文件夹手动删除')
    }
    await Promise.all([fetchVideos(), loadFeatured()])
  } catch (e) {
    showToast.error(e.message)
  }
}

// ================= 弹窗调度 =================
const formModal = ref(null)
const batchModal = ref(null)
const manageModal = ref(null)
const personalOpen = ref(false)

const openForm = (row = null) => formModal.value?.open(row)

const onFormSaved = async () => {
  await Promise.all([fetchVideos(), loadFeatured(), loadTags(), loadTypes(), loadPendingCount(), loadNoticeCount()])
}

const onManageChanged = async () => {
  // 工作台里合集通过 / 发布后，前台筛选下拉需要同步刷新
  await Promise.all([loadTags(), loadTypes(), loadCollections()])
}

// ================= 管理员审核 =================
const pendingCount = ref(0)
const noticeCount = ref(0)

const loadPendingCount = async () => {
  if (!canAudit.value) return
  try {
    const data = await listVideos({ scope: 'audit', auditStatus: 0, page: 1, pageSize: 1 })
    pendingCount.value = data.total
  } catch {
    // 角标加载失败不阻塞主流程
  }
}

const loadNoticeCount = async () => {
  try {
    const data = await getUnreadCount()
    noticeCount.value = data.count
  } catch {
    // 角标加载失败不阻塞主流程
  }
}

// ================= 排序 / 合集 / 继续观看 =================
const collections = ref([])
const watchHistory = ref([])

const loadCollections = async () => {
  try {
    // 合集已接入审核模型：只有「已通过 + 已发布」的合集才进入筛选下拉，
    // 与标签 / 类型一致，避免待审或未发布条目泄漏到前台
    collections.value = (await listCollections()).items
      .filter((c) => c.isPublished !== false && c.auditStatus === 1)
  } catch {
    // 合集加载失败不影响主列表
  }
}

const loadWatchHistory = async () => {
  try {
    watchHistory.value = (await getWatchHistory()).items.slice(0, 6)
  } catch {
    // 观看历史属于增强体验，失败静默
  }
}

const changeSort = () => {
  query.page = 1
  fetchVideos()
}

const changeCollection = () => {
  query.page = 1
  fetchVideos()
}

// ================= 批量管理（公开 / 删除） =================
const batchMode = ref(false)
const selectedIds = ref([])

const isSelected = (row) => selectedIds.value.includes(row.id)

const toggleSelect = (row) => {
  const i = selectedIds.value.indexOf(row.id)
  if (i > -1) selectedIds.value.splice(i, 1)
  else selectedIds.value.push(row.id)
}

const toggleBatchMode = () => {
  batchMode.value = !batchMode.value
  selectedIds.value = []
}

const batchSetPublic = async (target) => {
  const rows = videos.value.filter(
    (v) => isSelected(v) && canManage(v) && v.isPublic !== target && (target ? v.auditStatus === 1 : true),
  )
  let n = 0
  for (const row of rows) {
    try {
      const data = await togglePublic(row.id)
      row.isPublic = data.isPublic
      n += 1
    } catch (e) {
      showToast.error(e.message)
      break
    }
  }
  showToast(`已处理 ${n} 部影片（未过审或他人影片已跳过）`)
  selectedIds.value = []
}

const batchDelete = async () => {
  if (!selectedIds.value.length) return
  const ok = await confirmAction({
    title: '批量删除确认',
    message: `确认删除选中的 ${selectedIds.value.length} 部影片？\n将同时删除数据库记录与磁盘源文件，此操作不可恢复！`,
  })
  if (!ok) return
  let n = 0
  let sourceLeft = 0
  for (const id of selectedIds.value) {
    try {
      const data = await deleteVideo(id)
      n += 1
      if (data && !data.fileDeleted && !data.fileMissing) sourceLeft += 1
    } catch {
      // 单条失败不影响其余
    }
  }
  if (sourceLeft > 0) {
    showToast.warning(`已删除 ${n} 部影片，其中 ${sourceLeft} 部的源文件未能删除（被占用或不在媒体白名单内），请手动处理`)
  } else {
    showToast(`已删除 ${n} 部影片`)
  }
  selectedIds.value = []
  batchMode.value = false
  await Promise.all([fetchVideos(), loadFeatured(), loadNoticeCount()])
}

// 秒 → mm:ss（继续观看角标）
const formatClock = (seconds) => {
  const t = Math.max(0, Math.floor(Number(seconds) || 0))
  return `${String(Math.floor(t / 60)).padStart(2, '0')}:${String(t % 60).padStart(2, '0')}`
}

// ================= 回到顶部：长列表滚动超过一屏后浮出 =================
const showToTop = ref(false)
// 阈值取 300px：短列表（如仅几部影片）也能触发，不做固定大屏假设
const onScroll = () => { showToTop.value = window.scrollY > 300 }
const scrollToTop = () => {
  window.scrollTo({ top: 0, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' })
}

onMounted(() => {
  window.addEventListener('scroll', onScroll, { passive: true })
  onScroll()
  loadTags().catch((e) => showToast.error(e.message))
  loadTypes().catch((e) => showToast.error(e.message))
  fetchVideos()
  loadFeatured()
  loadPendingCount()
  loadNoticeCount()
  loadCollections()
  loadWatchHistory()
})
onBeforeUnmount(() => window.removeEventListener('scroll', onScroll))
</script>

<template>
  <!-- 顶部导航 -->
  <SiteNav
    :types="types"
    :active-type-id="query.typeId"
    :fav-active="!!query.favorite"
    :want-active="!!query.wantlist"
    :username="user?.username || ''"
    :avatar="user?.avatar || ''"
    :is-admin="isSuperAdmin"
    :can-audit="canAudit"
    :pending-count="pendingCount"
    :notice-count="noticeCount"
    @select-type="selectType"
    @toggle-fav="toggleFavFilter"
    @toggle-want="toggleWantlist"
    @search="onNavSearch"
    @manage="manageModal?.open()"
    @batch="batchModal?.open()"
    @create="openForm()"
    @open-personal="personalOpen = true"
    @logout="handleLogout"
  />

  <!-- Hero 大图轮播：仅首页保留；频道页让筛选面板置顶（对齐 VOD 频道页） -->
  <HeroCarousel v-if="isHome && featuredVideos.length" :videos="featuredVideos" @play="playVideo" @detail="openDetail" />

  <!-- ===== 影库主体：全部样式使用 Tailwind 工具类 ===== -->
  <main
    class="mx-auto max-w-[1400px] px-10 pb-10 max-[900px]:px-5 max-[900px]:pb-8"
    :class="isHome && featuredVideos.length ? 'pt-[26px]' : 'pt-9'"
  >
    <!-- 频道筛选面板：首页为简版（仅频道切换 + 排序），具体频道为专属完整版 -->
    <ChannelFilter
      v-if="!isFavMode && !isWantMode && !isPlaylistMode"
      :preset="preset"
      :channel-name="channelName"
      :channels="types"
      :active-id="query.typeId"
      :tags="tags"
      :collections="collections"
      :query="query"
      :total="total"
      @select-channel="selectType"
      @apply="applyFilter"
      @reset="resetChannelFilters"
    />

    <!-- 继续观看：仅首页展示 -->
    <div
      v-if="isHome && watchHistory.length"
      class="nf-scroll-x mb-[22px] flex items-center gap-2.5 overflow-x-auto rounded-lg border border-[#2a2a30] bg-[var(--nf-bg-card)] px-3.5 py-3"
    >
      <span class="shrink-0 text-[13px] font-bold tracking-[1px] text-nf-red">继续观看</span>
      <button
        v-for="w in watchHistory"
        :key="w.id"
        class="inline-flex max-w-[240px] shrink-0 items-center gap-2 rounded-[20px] border border-nf-line bg-[#202025] px-3 py-1.5 text-[12.5px] text-[var(--nf-text-secondary)] transition-colors hover:border-nf-red hover:text-nf-text"
        :title="`从 ${formatClock(w.position)} 继续播放「${w.title}」`"
        @click="playVideo({ id: w.id })"
      >
        <span class="truncate">{{ w.title }}</span>
        <span class="shrink-0 tabular-nums text-nf-muted">{{ formatClock(w.position) }}</span>
      </button>
    </div>

    <!-- 分区标题 + 工具条 -->
    <div id="library" class="mb-5 flex flex-wrap items-center gap-x-[18px] gap-y-3">
      <h2 class="relative m-0 pl-3.5 text-[21px] font-extrabold tracking-[1px] text-nf-text">
        <span class="absolute bottom-1 left-0 top-1 w-1 rounded-sm bg-nf-red"></span>
        {{ currentTypeName }}
      </h2>
      <span class="text-[13px] text-nf-muted">共 {{ total }} 部</span>

      <div class="ml-auto flex gap-2">
        <button
          class="h-7 rounded-[5px] border border-nf-line bg-nf-elevated px-2.5 text-[12.5px] text-nf-sub transition-colors hover:border-nf-red"
          :class="{ 'border-nf-red bg-[rgba(229,9,20,0.2)] text-nf-red': batchMode }"
          @click="toggleBatchMode"
        >
          {{ batchMode ? '退出批量' : '批量管理' }}
        </button>
        <!-- 收藏 / 想看模式没有频道面板，保留原有下拉 -->
        <select
          v-if="isFavMode || isWantMode"
          v-model="query.sort"
          class="h-7 cursor-pointer rounded-[5px] border border-nf-line bg-nf-elevated px-2.5 text-[12.5px] text-nf-sub"
          title="排序方式"
          @change="changeSort"
        >
          <option value="updated">最近更新</option>
          <option value="created">最近上架</option>
          <option value="hot">热度优先</option>
          <option value="views">播放最多</option>
          <option value="rating">评分最高</option>
          <option value="title">标题 A-Z</option>
        </select>
        <select
          v-if="showCollectionSelect"
          v-model.number="query.collectionId"
          class="h-7 cursor-pointer rounded-[5px] border border-nf-line bg-nf-elevated px-2.5 text-[12.5px] text-nf-sub"
          title="按合集筛选"
          @change="changeCollection"
        >
          <option :value="0">全部合集</option>
          <option v-for="c in collections" :key="c.id" :value="c.id">{{ c.name }}（{{ c.videoCount }}）</option>
        </select>
      </div>

      <!-- 标签胶囊：仅个人视图保留，频道模式由面板的「标签」行承担 -->
      <div v-if="isFavMode || isWantMode" class="flex flex-wrap gap-2">
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

    <!-- 批量操作条 -->
    <div
      v-if="batchMode"
      class="mb-[18px] flex flex-wrap items-center gap-2.5 rounded-lg border border-[rgba(229,9,20,0.35)] bg-[rgba(229,9,20,0.08)] px-3.5 py-3 text-[13px] text-nf-sub"
    >
      <span>已选 <b class="text-nf-text">{{ selectedIds.length }}</b> 部</span>
      <button class="nf-btn sm ghost" @click="batchSetPublic(true)"><FaIcon :icon="ICONS.publicOn" :fixed="false" />设为公开</button>
      <button class="nf-btn sm ghost" @click="batchSetPublic(false)"><FaIcon :icon="ICONS.publicOff" :fixed="false" />取消公开</button>
      <button class="nf-btn sm ghost danger" @click="batchDelete"><FaIcon :icon="ICONS.remove" :fixed="false" />删除所选</button>
      <button class="nf-btn sm ghost" @click="selectedIds = []"><FaIcon :icon="ICONS.reset" :fixed="false" />清空选择</button>
      <span class="ml-auto text-[12px] text-nf-muted">仅对自己有权管理、且已通过审核的影片生效</span>
    </div>

    <!-- 加载态：按当前视图形状渲染骨架屏，避免白屏 + 单调转圈 -->
    <div
      v-if="loading"
      :class="isChannelMode ? gridClass : homeGridClass"
      aria-busy="true"
      aria-label="正在加载影片"
    >
      <div
        v-for="n in skeletonCount"
        :key="n"
        class="nf-skeleton flex flex-col justify-end gap-2.5 p-3.5"
        :class="isChannelMode ? 'aspect-[2/3]' : 'h-[420px] max-[600px]:h-[300px]'"
      >
        <div class="nf-skeleton-bar h-[13px] w-3/5"></div>
        <div class="nf-skeleton-bar h-[10px] w-2/5"></div>
      </div>
    </div>

    <!-- 空态 -->
    <div
      v-else-if="videos.length === 0"
      class="flex min-h-[380px] flex-col items-center justify-center gap-3 rounded-[10px] border border-dashed border-[#2e2e34] px-6 py-10 text-center"
    >
      <FaIcon icon="film" :fixed="false" class="text-[48px] opacity-75" />
      <div class="text-[17px] font-bold text-nf-sub">
        {{ isWantMode ? '想看清单还是空的' : hasChannelFilters && !isFavMode ? '当前筛选条件下没有匹配的影片' : '暂无已通过审核的影片' }}
      </div>
      <div class="mb-2.5 max-w-[620px] text-[13px] leading-relaxed text-nf-muted">
        {{ isWantMode
          ? '在影片详情页点击「想看」即可加入清单，之后可在这里集中查看与播放。'
          : hasChannelFilters && !isFavMode
          ? '可点击面板右下角「重置筛选」清空条件，或切换到其它频道。地区 / 语言按标题与备注关键词匹配。'
          : '新上传的视频需管理员审核通过后才会出现在这里；可在右上角「审核结果」查看进度，或使用「批量导入」快速添加' }}
      </div>
      <button v-if="isWantMode" class="nf-btn ghost" @click="toggleWantlist()"><FaIcon :icon="ICONS.back" :fixed="false" />返回影库</button>
      <button v-else-if="hasChannelFilters && !isFavMode" class="nf-btn ghost" @click="resetChannelFilters"><FaIcon :icon="ICONS.reset" :fixed="false" />重置筛选</button>
      <button v-else class="nf-btn red" @click="openForm()"><FaIcon :icon="ICONS.create" :fixed="false" />新增视频</button>
    </div>

    <!-- 频道页：竖版海报墙（密度随频道变化） -->
    <div v-else-if="isChannelMode" :class="gridClass">
      <ChannelPosterCard
        v-for="(row, i) in videos"
        :key="row.id"
        class="nf-enter"
        :style="{ '--nf-delay': enterDelay(i) }"
        :video="row"
        :manageable="canManage(row)"
        :selectable="batchMode"
        :selected="isSelected(row)"
        @select="toggleSelect"
        @play="playVideo"
        @detail="openDetail"
        @edit="openForm"
        @remove="removeVideo"
        @toggle-fav="toggleFavoriteState"
        @toggle-public="togglePublicState"
        @add-playlist="openAddPlaylist"
      />
    </div>

    <!-- 首页 / 收藏：原有横向视频卡片 -->
    <div v-else :class="homeGridClass">
      <VideoCard
        v-for="(row, i) in videos"
        :key="row.id"
        class="nf-enter"
        :style="{ '--nf-delay': enterDelay(i) }"
        :video="row"
        :manageable="canManage(row)"
        :show-owner="row.ownerId !== user?.id"
        :selectable="batchMode"
        :selected="isSelected(row)"
        @select="toggleSelect"
        @play="playVideo"
        @edit="openForm"
        @remove="removeVideo"
        @toggle-fav="toggleFavoriteState"
        @toggle-public="togglePublicState"
        @add-playlist="openAddPlaylist"
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

    <!-- 个人片单模式横幅：提示当前正在查看某个片单，可一键退出 -->
    <div
      v-if="isPlaylistMode"
      class="mx-auto max-w-[1400px] px-10 pb-3 pt-4 max-[900px]:px-5"
    >
      <div class="flex flex-wrap items-center gap-3 rounded-lg border border-[rgba(229,9,20,0.35)] bg-[rgba(229,9,20,0.08)] px-4 py-3">
        <FaIcon :icon="ICONS.playlist" :fixed="false" class="text-[18px] text-nf-red" />
        <span class="text-[14px] font-bold text-nf-text">{{ playlistName || '我的片单' }}</span>
        <span class="text-[12.5px] text-nf-muted">片单内的影片</span>
        <button
          class="ml-auto nf-btn ghost"
          @click="exitPlaylist"
        >
          <FaIcon :icon="ICONS.close" :fixed="false" />退出片单
        </button>
      </div>
    </div>

  <!-- 页脚 -->
  <footer class="flex items-center gap-4 border-t border-white/[0.07] px-10 pb-[34px] pt-[26px] max-[900px]:flex-wrap max-[900px]:px-5">
    <div class="text-[16px] font-extrabold tracking-[2px] text-nf-red">
      影库 <span class="ml-1.5 text-[10px] tracking-[3px] text-nf-muted">VIDEO FACTORY</span>
    </div>
    <div class="text-[12.5px] text-nf-muted">本地私人影片管理 · 数据仅存储于本机</div>
    <div class="ml-auto text-[12px] text-[#4d4d55]">© {{ new Date().getFullYear() }} Video Manager</div>
  </footer>

  <!-- 弹窗组：新增/编辑 / 批量导入 / 标签类型管理 / 个人中心 -->
  <VideoFormModal ref="formModal" @saved="onFormSaved" />
  <BatchImportModal
    ref="batchModal"
    @imported="() => Promise.all([fetchVideos(), loadFeatured(), loadTags(), loadTypes(), loadPendingCount(), loadNoticeCount()])"
  />
  <ManageModal ref="manageModal" @changed="onManageChanged" />
  <PersonalCenterModal v-model="personalOpen" @logout="handleLogout" @view-playlist="openPlaylist" />
  <AddToPlaylistModal ref="playlistModal" v-model="playlistModalOpen" :video-id="playlistVideoId" @changed="onPlaylistChanged" />

  <!-- 回到顶部：长列表滚动超过一屏后浮出 -->
  <Transition name="nf-pop">
    <button
      v-if="showToTop"
      class="nf-to-top"
      title="回到顶部"
      aria-label="回到顶部"
      @click="scrollToTop"
    >
      <FaIcon :icon="ICONS.chevronUp" :fixed="false" class="text-[15px]" />
    </button>
  </Transition>
</template>
