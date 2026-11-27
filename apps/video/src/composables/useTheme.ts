import { computed, toRef, type ComputedRef, type Ref } from 'vue'
import { useThemeStore, type ThemeMode } from '../stores/theme'

// 兼容层：组件仍以 useTheme() 解构 ref / computed 的方式使用；真实全局状态由 Pinia store 接管。

export const initTheme = (): void => useThemeStore().initTheme()
export const toggleTheme = (): void => useThemeStore().toggleTheme()

export function useTheme(): {
  theme: Ref<ThemeMode>
  isLight: ComputedRef<boolean>
  toggleTheme: () => void
  initTheme: () => void
} {
  const store = useThemeStore()
  return {
    theme: toRef(store, 'theme'),
    isLight: computed(() => store.isLight),
    toggleTheme: store.toggleTheme,
    initTheme: store.initTheme,
  }
}
