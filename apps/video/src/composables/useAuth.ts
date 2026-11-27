import { toRef, type Ref } from 'vue'
import { useAuthStore } from '../stores/auth'
import type { UserAccount } from '../types'

// 兼容层：组件仍以 useAuth() 解构 ref 的方式使用；真实全局状态由 Pinia store 接管。
// Pinia store 必须在函数调用时获取（模块顶层时尚未 install pinia）。

export const ensureLoaded = (): Promise<UserAccount | null> => useAuthStore().ensureLoaded()
export const fetchMe = (): Promise<UserAccount | null> => useAuthStore().fetchMe()
export const setUser = (user: UserAccount | null): void => useAuthStore().setUser(user)
export const resetAuth = (): void => useAuthStore().resetAuth()
export const patchUser = (patch: Partial<UserAccount>): void => useAuthStore().patchUser(patch)

export function useAuth(): {
  user: Ref<UserAccount | null>
  ensureLoaded: () => Promise<UserAccount | null>
  fetchMe: () => Promise<UserAccount | null>
  setUser: (user: UserAccount | null) => void
  resetAuth: () => void
  patchUser: (patch: Partial<UserAccount>) => void
} {
  const store = useAuthStore()
  return {
    user: toRef(store, 'user'),
    ensureLoaded: store.ensureLoaded,
    fetchMe: store.fetchMe,
    setUser: store.setUser,
    resetAuth: store.resetAuth,
    patchUser: store.patchUser,
  }
}
