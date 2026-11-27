import { defineStore } from 'pinia'
import { listVideos } from '../api'
import { showToast } from '../ui/toast'
import type { PageItem, QueryState, VideoItem } from '../types'

// 频道页筛选复位：切频道或点「重置筛选」时清空，避免上一频道的条件残留
const CHANNEL_DEFAULTS: Partial<QueryState> = {
  tagId: 0, collectionId: 0, playlistId: 0, region: '', language: '', year: 0, letter: '',
  favorite: 0, wantlist: 0, sort: 'updated', page: 1,
}

const initialQuery = (): QueryState => ({
  keyword: '', tagId: 0, typeId: 0, favorite: 0, wantlist: 0,
  sort: 'updated', collectionId: 0, ownerId: 0, playlistId: 0,
  // 频道页多维筛选（后端 list_videos 的可缺省参数）
  region: '', language: '', year: 0, letter: '',
  page: 1, pageSize: 12,
})

export const useVideosStore = defineStore('videoVideos', {
  state: () => ({
    // typeId / tagId 均用 0 表示「全部」（后端对 0 不做过滤）
    query: initialQuery(),
    total: 0,
    videos: [] as VideoItem[],
    loading: false,
  }),

  getters: {
    totalPages: (state): number => Math.max(1, Math.ceil(state.total / state.query.pageSize)),

    pageItems(): PageItem[] {
      const cur = this.query.page
      const last = this.totalPages
      const out: PageItem[] = []
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
    },
  },

  actions: {
    scrollToLibrary(): void {
      document.getElementById('library')?.scrollIntoView({ behavior: 'smooth' })
    },

    async fetchVideos(): Promise<void> {
      this.loading = true
      try {
        const data = await listVideos({ ...this.query })
        this.videos = data.items
        this.total = data.total
      } catch (e) {
        showToast.error(e instanceof Error ? e.message : String(e))
      } finally {
        this.loading = false
      }
    },

    onSearch(): void {
      this.query.page = 1
      void this.fetchVideos()
    },

    // 顶部导航：按类型切换（netflixgc 分类导航）
    // 切到类型导航时必须退出「我的收藏」模式，否则高亮与列表过滤都会停留在收藏态
    selectType(id: number): void {
      this.query.typeId = id
      Object.assign(this.query, CHANNEL_DEFAULTS) // 每个频道从「全部」开始，且排序回到默认
      void this.fetchVideos()
      // 频道页头图 + 筛选面板置顶，切换后回到页首才能看到；首页沿用原来的定位到影库区
      if (id !== 0) window.scrollTo({ top: 0, behavior: 'smooth' })
      else this.scrollToLibrary()
    },

    // 频道面板：任一筛选行或排序 Tab 变更后重新拉取列表
    applyFilter(patch: Partial<QueryState>): void {
      Object.assign(this.query, patch)
      void this.fetchVideos()
    },

    // 「重置筛选」：只清筛选条件，保留当前频道与搜索词
    resetChannelFilters(): void {
      Object.assign(this.query, CHANNEL_DEFAULTS)
      void this.fetchVideos()
    },

    // 「我的收藏」导航开关
    toggleFavFilter(): void {
      this.query.favorite = this.query.favorite ? 0 : 1
      this.query.wantlist = 0
      this.query.page = 1
      // 退出收藏模式回到频道面板时，排序值可能不在面板 Tab 中，回到默认「按最新」
      if (!this.query.favorite) this.query.sort = 'updated'
      void this.fetchVideos()
      this.scrollToLibrary()
    },

    // 「想看」清单：与收藏互斥的独立视图，后端按当前用户的 video_watchlist 过滤
    toggleWantlist(): void {
      this.query.wantlist = this.query.wantlist ? 0 : 1
      this.query.favorite = 0
      this.query.page = 1
      if (!this.query.wantlist) this.query.sort = 'updated'
      void this.fetchVideos()
      this.scrollToLibrary()
    },

    goPage(p: PageItem): void {
      if (p === '…' || p === this.query.page) return
      this.query.page = p
      void this.fetchVideos()
      this.scrollToLibrary()
    },

    changeSize(): void {
      this.query.page = 1
      void this.fetchVideos()
    },

    // 「我的收藏」模式下取消收藏后列表需要刷新
    refreshIfFavMode(): void {
      if (this.query.favorite || this.query.wantlist) void this.fetchVideos()
    },
  },
})
