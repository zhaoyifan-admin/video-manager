import { computed, reactive, ref } from 'vue'
import { listVideos } from '../api'
import { showToast } from '../ui/toast'

// ================= 视频查询 / 分页（全局单例状态） =================
// typeId / tagId 均用 0 表示「全部」（后端对 0 不做过滤）
const query = reactive({ keyword: '', tagId: 0, typeId: 0, favorite: 0, page: 1, pageSize: 12 })
const total = ref(0)
const videos = ref([])
const loading = ref(false)

const scrollToLibrary = () => {
  document.getElementById('library')?.scrollIntoView({ behavior: 'smooth' })
}

const fetchVideos = async () => {
  loading.value = true
  try {
    const data = await listVideos({ ...query })
    videos.value = data.items
    total.value = data.total
  } catch (e) {
    showToast.error(e.message)
  } finally {
    loading.value = false
  }
}

const onSearch = () => {
  query.page = 1
  fetchVideos()
}

// 顶部导航：按类型切换（netflixgc 分类导航）
// 切到类型导航时必须退出「我的收藏」模式，否则高亮与列表过滤都会停留在收藏态
const selectType = (id) => {
  query.typeId = id
  query.favorite = 0
  query.tagId = 0
  query.keyword = ''
  query.page = 1
  fetchVideos()
  scrollToLibrary()
}

// 「我的收藏」导航开关
const toggleFavFilter = () => {
  query.favorite = query.favorite ? 0 : 1
  query.page = 1
  fetchVideos()
  scrollToLibrary()
}

// ================= 分页（手写） =================
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / query.pageSize)))

const pageItems = computed(() => {
  const cur = query.page
  const last = totalPages.value
  const out = []
  if (last <= 7) {
    for (let i = 1; i <= last; i++) out.push(i)
    return out
  }
  out.push(1)
  if (cur > 3) out.push('…')
  for (let i = Math.max(2, cur - 1); i <= Math.min(last - 1, cur + 1); i++) out.push(i)
  if (cur < last - 2) out.push('…')
  out.push(last)
  return out
})

const goPage = (p) => {
  if (p === '…' || p === query.page) return
  query.page = p
  fetchVideos()
  scrollToLibrary()
}

const changeSize = () => {
  query.page = 1
  fetchVideos()
}

// 「我的收藏」模式下取消收藏后列表需要刷新
const refreshIfFavMode = () => {
  if (query.favorite) fetchVideos()
}

export function useVideos() {
  return {
    query,
    total,
    videos,
    loading,
    fetchVideos,
    onSearch,
    selectType,
    toggleFavFilter,
    totalPages,
    pageItems,
    goPage,
    changeSize,
    refreshIfFavMode,
  }
}
