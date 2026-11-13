/** 明暗主题：全局单例，切换时只改 <html data-theme>，色板由 theme.css 的变量层接管。
 *
 * 默认维持原有的影院深色观感，只有用户主动切换后才记住偏好（localStorage）。
 * 不自动跟随系统，避免同一台机器上的既有截稿/截图被系统主题意外改变。
 */
import { computed, ref } from 'vue'

const STORAGE_KEY = 'nf-theme'
const theme = ref('dark')
const isLight = computed(() => theme.value === 'light')

const apply = (mode) => {
  theme.value = mode
  document.documentElement.dataset.theme = mode
  document.documentElement.style.colorScheme = mode
  try {
    localStorage.setItem(STORAGE_KEY, mode)
  } catch {
    // 隐私模式下 localStorage 不可用：本次会话内仍可切换
  }
}

export const initTheme = () => {
  let saved = null
  try {
    saved = localStorage.getItem(STORAGE_KEY)
  } catch {
    saved = null
  }
  apply(saved === 'light' ? 'light' : 'dark')
}

export const toggleTheme = () => apply(isLight.value ? 'dark' : 'light')

export function useTheme() {
  return { theme, isLight, toggleTheme, initTheme }
}
