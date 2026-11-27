import { computed, toRef, type ComputedRef, type Ref } from 'vue'
import { useVideosStore } from '../stores/videos'
import type { PageItem, QueryState, VideoItem } from '../types'

// 兼容层：组件仍以 useVideos() 解构 query / ref / 方法的方式使用；真实全局状态由 Pinia store 接管。

export function useVideos(): {
  query: QueryState
  total: Ref<number>
  videos: Ref<VideoItem[]>
  loading: Ref<boolean>
  fetchVideos: () => Promise<void>
  onSearch: () => void
  selectType: (id: number) => void
  toggleFavFilter: () => void
  toggleWantlist: () => void
  applyFilter: (patch: Partial<QueryState>) => void
  resetChannelFilters: () => void
  totalPages: ComputedRef<number>
  pageItems: ComputedRef<PageItem[]>
  goPage: (p: PageItem) => void
  changeSize: () => void
  refreshIfFavMode: () => void
  scrollToLibrary: () => void
} {
  const store = useVideosStore()
  return {
    query: store.query,
    total: toRef(store, 'total'),
    videos: toRef(store, 'videos'),
    loading: toRef(store, 'loading'),
    fetchVideos: store.fetchVideos,
    onSearch: store.onSearch,
    selectType: store.selectType,
    toggleFavFilter: store.toggleFavFilter,
    toggleWantlist: store.toggleWantlist,
    applyFilter: store.applyFilter,
    resetChannelFilters: store.resetChannelFilters,
    totalPages: computed(() => store.totalPages),
    pageItems: computed(() => store.pageItems),
    goPage: store.goPage,
    changeSize: store.changeSize,
    refreshIfFavMode: store.refreshIfFavMode,
    scrollToLibrary: store.scrollToLibrary,
  }
}
