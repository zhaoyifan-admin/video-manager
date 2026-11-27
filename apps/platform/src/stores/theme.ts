import { defineStore } from 'pinia'

/** 主题偏好：dark / light / auto（跟随系统） */
export type ThemeMode = 'light' | 'dark' | 'auto'
export type LayoutMode = 'vertical' | 'horizontal' | 'vertical-mix' | 'horizontal-mix'
export type BuiltinTheme = 'default' | 'blue' | 'violet' | 'green' | 'amber' | 'rose' | 'custom'
export type TabbarStyle = 'chrome' | 'card' | 'plain'
export type TransitionName = 'fade' | 'fade-slide' | 'slide-left' | 'none'

const PREF_KEY = 'nf-preferences'
const LEGACY_THEME_KEY = 'nf-theme'
const LEGACY_LAYOUT_KEY = 'nf-layout'

export const presetColors = [
  { name: 'Netflix 红', value: '#e50914' },
  { name: '科技蓝', value: '#1677ff' },
  { name: '青绿', value: '#10b981' },
  { name: '紫罗兰', value: '#8b5cf6' },
  { name: '琥珀', value: '#f59e0b' },
  { name: '玫瑰', value: '#f43f5e' },
]

/** 内置主题：一键切换整套主色，之后手动改主色会变为 custom */
export const builtinThemes: Array<{ name: string; value: BuiltinTheme; color: string }> = [
  { name: '默认', value: 'default', color: '#e50914' },
  { name: '科技蓝', value: 'blue', color: '#1677ff' },
  { name: '紫罗兰', value: 'violet', color: '#8b5cf6' },
  { name: '青绿', value: 'green', color: '#10b981' },
  { name: '琥珀', value: 'amber', color: '#f59e0b' },
  { name: '玫瑰', value: 'rose', color: '#f43f5e' },
]

export const radiusOptions: Array<{ name: string; value: number }> = [
  { name: '直角', value: 0 },
  { name: '轻微', value: 0.25 },
  { name: '默认', value: 0.5 },
  { name: '圆润', value: 0.75 },
]

export const tabbarStyleOptions: Array<{ name: string; value: TabbarStyle }> = [
  { name: '浏览器', value: 'chrome' },
  { name: '卡片', value: 'card' },
  { name: '简洁', value: 'plain' },
]

export const transitionOptions: Array<{ name: string; value: TransitionName }> = [
  { name: '淡入滑动', value: 'fade-slide' },
  { name: '淡入', value: 'fade' },
  { name: '左侧滑入', value: 'slide-left' },
  { name: '无动画', value: 'none' },
]

export interface Preferences {
  /** 主题 */
  theme: ThemeMode
  builtinType: BuiltinTheme
  primaryColor: string
  radius: number
  compact: boolean
  /** 布局 */
  layoutMode: LayoutMode
  sidebarWidth: number
  sidebarCollapsed: boolean
  sidebarCollapsedButton: boolean
  mixedWidth: number
  secondaryWidth: number
  menuAccordion: boolean
  /** 顶栏与面包屑 */
  showHeader: boolean
  showBreadcrumb: boolean
  breadcrumbIcon: boolean
  hideBreadcrumbOne: boolean
  /** 标签页 */
  showTabs: boolean
  tabbarStyle: TabbarStyle
  showTabIcon: boolean
  tabMiddleClickClose: boolean
  tabWheelable: boolean
  tabPersist: boolean
  tabMaxCount: number
  /** 底栏 */
  showFooter: boolean
  /** 动画 */
  transitionEnable: boolean
  transitionName: TransitionName
  transitionProgress: boolean
  /** 通用 */
  watermark: boolean
  dynamicTitle: boolean
  /** 顶栏部件 */
  widgetNotification: boolean
  widgetThemeToggle: boolean
  widgetRefresh: boolean
  widgetSettings: boolean
}

const defaultPreferences: Preferences = {
  theme: 'dark',
  builtinType: 'default',
  primaryColor: '#e50914',
  radius: 0.5,
  compact: false,

  layoutMode: 'vertical',
  sidebarWidth: 232,
  sidebarCollapsed: false,
  sidebarCollapsedButton: true,
  mixedWidth: 68,
  secondaryWidth: 180,
  menuAccordion: true,

  showHeader: true,
  showBreadcrumb: true,
  breadcrumbIcon: false,
  hideBreadcrumbOne: false,

  showTabs: true,
  tabbarStyle: 'chrome',
  showTabIcon: true,
  tabMiddleClickClose: false,
  tabWheelable: true,
  tabPersist: true,
  tabMaxCount: 0,

  showFooter: false,

  transitionEnable: true,
  transitionName: 'fade-slide',
  transitionProgress: true,

  watermark: false,
  dynamicTitle: true,

  widgetNotification: true,
  widgetThemeToggle: true,
  widgetRefresh: true,
  widgetSettings: true,
}

const themeModes: ThemeMode[] = ['light', 'dark', 'auto']
const layoutModes: LayoutMode[] = ['vertical', 'horizontal', 'vertical-mix', 'horizontal-mix']
const tabbarStyles: TabbarStyle[] = ['chrome', 'card', 'plain']
const transitions: TransitionName[] = ['fade', 'fade-slide', 'slide-left', 'none']
const builtinValues: BuiltinTheme[] = builtinThemes.map(item => item.value)

const asBool = (value: unknown, fallback: boolean): boolean =>
  typeof value === 'boolean' ? value : fallback
const asNumber = (value: unknown, fallback: number, min: number, max: number): number =>
  typeof value === 'number' && Number.isFinite(value) ? Math.min(max, Math.max(min, value)) : fallback
const asEnum = <T extends string>(value: unknown, values: readonly T[], fallback: T): T =>
  typeof value === 'string' && (values as readonly string[]).includes(value) ? value as T : fallback

/** 读取偏好设置，同时兼容旧版 nf-theme / nf-layout 两个 key */
const readPreferences = (): Preferences => {
  let raw: Record<string, unknown> = {}
  try {
    const current = localStorage.getItem(PREF_KEY)
    if (current) {
      raw = JSON.parse(current) as Record<string, unknown>
    } else {
      const legacyTheme = localStorage.getItem(LEGACY_THEME_KEY)
      const legacyLayout = localStorage.getItem(LEGACY_LAYOUT_KEY)
      raw = {
        ...(legacyLayout ? JSON.parse(legacyLayout) as Record<string, unknown> : {}),
        ...(legacyTheme ? { theme: legacyTheme } : {}),
      }
    }
  } catch {
    raw = {}
  }
  const d = defaultPreferences
  return {
    theme: asEnum(raw.theme, themeModes, d.theme),
    builtinType: asEnum(raw.builtinType, builtinValues, d.builtinType),
    primaryColor: typeof raw.primaryColor === 'string' && /^#[0-9a-fA-F]{6}$/.test(raw.primaryColor)
      ? raw.primaryColor : d.primaryColor,
    radius: typeof raw.radius === 'number' && Number.isFinite(raw.radius) ? raw.radius : d.radius,
    compact: asBool(raw.compact, d.compact),

    layoutMode: asEnum(raw.layoutMode, layoutModes, d.layoutMode),
    sidebarWidth: asNumber(raw.sidebarWidth, d.sidebarWidth, 180, 300),
    sidebarCollapsed: asBool(raw.sidebarCollapsed, d.sidebarCollapsed),
    sidebarCollapsedButton: asBool(raw.sidebarCollapsedButton, d.sidebarCollapsedButton),
    mixedWidth: asNumber(raw.mixedWidth, d.mixedWidth, 56, 120),
    secondaryWidth: asNumber(raw.secondaryWidth, d.secondaryWidth, 140, 260),
    menuAccordion: asBool(raw.menuAccordion, d.menuAccordion),

    showHeader: asBool(raw.showHeader, d.showHeader),
    showBreadcrumb: asBool(raw.showBreadcrumb, d.showBreadcrumb),
    breadcrumbIcon: asBool(raw.breadcrumbIcon, d.breadcrumbIcon),
    hideBreadcrumbOne: asBool(raw.hideBreadcrumbOne, d.hideBreadcrumbOne),

    showTabs: asBool(raw.showTabs, d.showTabs),
    tabbarStyle: asEnum(raw.tabbarStyle, tabbarStyles, d.tabbarStyle),
    showTabIcon: asBool(raw.showTabIcon, d.showTabIcon),
    tabMiddleClickClose: asBool(raw.tabMiddleClickClose, d.tabMiddleClickClose),
    tabWheelable: asBool(raw.tabWheelable, d.tabWheelable),
    tabPersist: asBool(raw.tabPersist, d.tabPersist),
    tabMaxCount: asNumber(raw.tabMaxCount, d.tabMaxCount, 0, 30),

    showFooter: asBool(raw.showFooter, d.showFooter),

    transitionEnable: asBool(raw.transitionEnable, d.transitionEnable),
    transitionName: asEnum(raw.transitionName, transitions, d.transitionName),
    transitionProgress: asBool(raw.transitionProgress, d.transitionProgress),

    watermark: asBool(raw.watermark, d.watermark),
    dynamicTitle: asBool(raw.dynamicTitle, d.dynamicTitle),

    widgetNotification: asBool(raw.widgetNotification, d.widgetNotification),
    widgetThemeToggle: asBool(raw.widgetThemeToggle, d.widgetThemeToggle),
    widgetRefresh: asBool(raw.widgetRefresh, d.widgetRefresh),
    widgetSettings: asBool(raw.widgetSettings, d.widgetSettings),
  }
}

const applyPrimaryColor = (color: string): void => {
  const root = document.documentElement
  const hex = color.replace('#', '')
  if (!/^[0-9a-fA-F]{6}$/.test(hex)) return
  const channel = (start: number): number => parseInt(hex.slice(start, start + 2), 16)
  const [r, g, b] = [channel(0), channel(2), channel(4)]
  root.style.setProperty('--el-color-primary', color)
  ;[3, 5, 7, 8, 9].forEach(weight => {
    const mix = (value: number): string =>
      Math.round(value + (255 - value) * (weight / 10)).toString(16).padStart(2, '0')
    root.style.setProperty(`--el-color-primary-light-${weight}`, `#${mix(r)}${mix(g)}${mix(b)}`)
  })
  const dark = (value: number): string => Math.round(value * 0.8).toString(16).padStart(2, '0')
  root.style.setProperty('--el-color-primary-dark-2', `#${dark(r)}${dark(g)}${dark(b)}`)
  // 手写组件里的品牌色变量跟随主色，避免设置面板改色后 Logo / 选中态仍是旧红。
  root.style.setProperty('--nf-red', color)
  root.style.setProperty('--nf-red-hover', `#${mix255(r)}${mix255(g)}${mix255(b)}`)
}

const mix255 = (value: number): string =>
  Math.round(value + (255 - value) * 0.12).toString(16).padStart(2, '0')

let mediaListener: ((event: MediaQueryListEvent) => void) | null = null

export const useThemeStore = defineStore('theme', {
  state: (): Preferences => ({ ...defaultPreferences }),

  getters: {
    /** 跟随系统时解析成实际模式，供界面判断深浅 */
    isLight: (state): boolean => state.theme === 'auto'
      ? (typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: light)').matches)
      : state.theme === 'light',
    isHorizontalLayout: (state): boolean => state.layoutMode.startsWith('horizontal'),
    isMixLayout: (state): boolean => state.layoutMode.endsWith('-mix'),
    /** 当前生效的主题模式（auto 已解析） */
    effectiveTheme(): 'light' | 'dark' {
      return this.isLight ? 'light' : 'dark'
    },
  },

  actions: {
    /** 把偏好设置映射到 document / CSS 变量 */
    syncDom(): void {
      const root = document.documentElement
      const resolved: 'light' | 'dark' = this.isLight ? 'light' : 'dark'
      root.dataset.theme = resolved
      root.classList.toggle('dark', resolved === 'dark')
      root.style.colorScheme = resolved
      applyPrimaryColor(this.primaryColor)
      root.style.setProperty('--el-border-radius-base', `${this.radius}rem`)
      root.style.setProperty('--el-border-radius-small', `${Math.max(0, this.radius - 0.25)}rem`)
      root.classList.toggle('compact', this.compact)
    },

    save(): void {
      try {
        const payload: Preferences = { ...this.$state }
        localStorage.setItem(PREF_KEY, JSON.stringify(payload))
      } catch {
        // 隐私模式下 localStorage 不可用：本次会话内配置仍然有效。
      }
    },

    restore(): void {
      Object.assign(this, readPreferences())
      this.syncDom()
    },

    /** 设置任意偏好项并立即生效、持久化 */
    setPreference<K extends keyof Preferences>(key: K, value: Preferences[K]): void {
      ;(this as unknown as Record<string, unknown>)[key] = value
      this.syncDom()
      this.save()
    },

    apply(mode: ThemeMode): void {
      this.setPreference('theme', mode)
    },

    toggle(): void {
      const next: ThemeMode = this.isLight ? 'dark' : 'light'
      this.apply(next)
    },

    setLayoutMode(mode: LayoutMode): void {
      this.setPreference('layoutMode', mode)
    },

    setShowTabs(value: boolean): void {
      this.setPreference('showTabs', value)
    },

    setShowFooter(value: boolean): void {
      this.setPreference('showFooter', value)
    },

    setPrimaryColor(color: string): void {
      if (!/^#[0-9a-fA-F]{6}$/.test(color)) return
      const hit = builtinThemes.find(item => item.color.toLowerCase() === color.toLowerCase())
      this.primaryColor = color
      this.builtinType = hit?.value || 'custom'
      this.syncDom()
      this.save()
    },

    applyBuiltinTheme(value: BuiltinTheme): void {
      const hit = builtinThemes.find(item => item.value === value)
      if (!hit) return
      this.builtinType = value
      this.primaryColor = hit.color
      this.syncDom()
      this.save()
    },

    exportPreferences(): string {
      return JSON.stringify({ ...this.$state }, null, 2)
    },

    resetPreferences(): void {
      Object.assign(this, defaultPreferences)
      this.syncDom()
      this.save()
    },

    init(): void {
      this.restore()
      if (!mediaListener && typeof window !== 'undefined' && window.matchMedia) {
        const query = window.matchMedia('(prefers-color-scheme: dark)')
        mediaListener = () => {
          if (this.theme === 'auto') this.syncDom()
        }
        query.addEventListener('change', mediaListener)
      }
    },

    // 旧 API 兼容：既有调用点无需改动。
    saveLayout(): void { this.save() },
    restoreLayout(): void { this.restore() },
    resetLayout(): void { this.resetPreferences() },
  },
})
