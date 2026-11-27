import { defineStore } from 'pinia'
import { useThemeStore } from './theme'

export interface RouteTab {
  path: string
  title: string
  icon?: string
  fixed?: boolean
}

const TABS_KEY = 'nf-tabs'

type PersistedTabs = {
  tabs: RouteTab[]
  activePath: string
  homePath: string
}

export const useTabsStore = defineStore('tabs', {
  state: () => ({
    tabs: [] as RouteTab[],
    activePath: '',
    homePath: '',
    suppressed: [] as string[],
  }),

  getters: {
    count: (state): number => state.tabs.length,
  },

  actions: {
    /** 偏好设置开启「刷新后保留」时写入本地存储 */
    persist(): void {
      if (!useThemeStore().tabPersist) return
      try {
        const payload: PersistedTabs = {
          tabs: this.tabs,
          activePath: this.activePath,
          homePath: this.homePath,
        }
        localStorage.setItem(TABS_KEY, JSON.stringify(payload))
      } catch {
        // 忽略存储失败，标签仍在当前会话内有效。
      }
    },

    clearPersisted(): void {
      try { localStorage.removeItem(TABS_KEY) } catch { /* 忽略 */ }
    },

    loadPersisted(): void {
      const theme = useThemeStore()
      if (!theme.tabPersist) return
      try {
        const raw = localStorage.getItem(TABS_KEY)
        if (!raw) return
        const saved = JSON.parse(raw) as PersistedTabs
        if (!Array.isArray(saved.tabs)) return
        this.tabs = saved.tabs.filter(item => item && typeof item.path === 'string' && item.path)
        this.activePath = typeof saved.activePath === 'string' ? saved.activePath : ''
        this.homePath = typeof saved.homePath === 'string' ? saved.homePath : ''
      } catch {
        this.tabs = []
      }
    },

    /** 设置首页路径并保证其作为固定标签存在 */
    syncHome(tab: RouteTab): void {
      this.homePath = tab.path
      const existing = this.tabs.find(item => item.path === tab.path)
      if (existing) {
        existing.fixed = true
        existing.title = tab.title
        existing.icon = tab.icon
        this.persist()
        return
      }
      this.tabs.unshift({ ...tab, fixed: true })
      this.persist()
    },

    /** 关闭标签后屏蔽旧路径，直到导航到新路由后再释放，避免 watcher 补回 */
    suppress(path: string): void {
      if (path && !this.suppressed.includes(path)) this.suppressed.push(path)
    },

    release(path: string): void {
      this.suppressed = this.suppressed.filter(item => item !== path)
    },

    addTab(tab: RouteTab): void {
      if (!tab.path || this.suppressed.includes(tab.path)) return
      const existing = this.tabs.find(item => item.path === tab.path)
      if (existing) {
        existing.title = tab.title
        if (tab.icon) existing.icon = tab.icon
        this.persist()
        return
      }
      this.tabs.push({ ...tab })

      // 数量上限：优先淘汰最早打开且非固定的标签，当前页永不淘汰。
      const limit = useThemeStore().tabMaxCount
      while (limit > 0 && this.tabs.length > limit) {
        const index = this.tabs.findIndex(item => !item.fixed && item.path !== this.activePath)
        if (index < 0) break
        this.tabs.splice(index, 1)
      }
      this.persist()
    },

    setActive(path: string): void {
      if (this.activePath === path) return
      this.activePath = path
      this.persist()
    },

    /** 关闭指定标签，返回需要重新导航的路径；固定标签不可关闭 */
    removeTab(path: string): string | null {
      const index = this.tabs.findIndex(item => item.path === path)
      if (index < 0 || this.tabs[index].fixed) return null
      this.suppress(path)
      this.tabs.splice(index, 1)
      this.persist()
      if (this.activePath !== path) {
        window.setTimeout(() => this.release(path), 1000)
        return null
      }
      const next = this.tabs[index] || this.tabs[index - 1]
      this.activePath = next?.path || this.homePath
      window.setTimeout(() => this.release(path), 1000)
      return this.activePath
    },

    closeOthers(path: string): void {
      this.tabs = this.tabs.filter(item => item.fixed || item.path === path)
      if (!this.tabs.some(item => item.path === this.activePath)) this.activePath = path
      this.persist()
    },

    closeLeft(path: string): void {
      const index = this.tabs.findIndex(item => item.path === path)
      if (index < 0) return
      this.tabs = this.tabs.filter((item, i) => item.fixed || i >= index)
      if (!this.tabs.some(item => item.path === this.activePath)) this.activePath = path
      this.persist()
    },

    closeRight(path: string): void {
      const index = this.tabs.findIndex(item => item.path === path)
      if (index < 0) return
      this.tabs = this.tabs.filter((item, i) => item.fixed || i <= index)
      if (!this.tabs.some(item => item.path === this.activePath)) this.activePath = path
      this.persist()
    },

    closeAll(): void {
      this.tabs = this.tabs.filter(item => item.fixed)
      this.activePath = this.tabs[0]?.path || this.homePath
      this.persist()
    },

    reset(): void {
      this.tabs = []
      this.activePath = ''
      this.homePath = ''
      this.clearPersisted()
    },
  },
})
