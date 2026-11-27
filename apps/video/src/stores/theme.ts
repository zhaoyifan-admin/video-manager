import { defineStore } from 'pinia'

export type ThemeMode = 'dark' | 'light'

const STORAGE_KEY = 'nf-theme'

/** 明暗主题：只改 <html data-theme>，色板由 theme.css 的变量层接管。
 * 默认维持影院深色观感，只有用户主动切换后才记住偏好（localStorage）。
 * 不自动跟随系统，避免同一台机器上的既有截稿/截图被系统主题意外改变。
 */
export const useThemeStore = defineStore('videoTheme', {
  state: () => ({
    theme: 'dark' as ThemeMode,
  }),

  getters: {
    isLight: (state): boolean => state.theme === 'light',
  },

  actions: {
    apply(mode: ThemeMode): void {
      this.theme = mode
      document.documentElement.dataset.theme = mode
      document.documentElement.style.colorScheme = mode
      try {
        localStorage.setItem(STORAGE_KEY, mode)
      } catch {
        // 隐私模式下 localStorage 不可用：本次会话内仍可切换
      }
    },

    initTheme(): void {
      let saved: string | null = null
      try {
        saved = localStorage.getItem(STORAGE_KEY)
      } catch {
        saved = null
      }
      this.apply(saved === 'light' ? 'light' : 'dark')
    },

    toggleTheme(): void {
      this.apply(this.isLight ? 'dark' : 'light')
    },
  },
})
