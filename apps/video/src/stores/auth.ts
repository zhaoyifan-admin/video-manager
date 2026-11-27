import { defineStore } from 'pinia'
import { getMe } from '../api'
import type { UserAccount } from '../types'

// 仅首次调用时请求 /auth/me；后续路由守卫复用该 Promise。
let readyPromise: Promise<UserAccount | null> | null = null

export const useAuthStore = defineStore('videoAuth', {
  state: () => ({
    user: null as UserAccount | null,
  }),

  getters: {
    isAuthenticated: (state): boolean => Boolean(state.user),
    role: (state): string => state.user?.role || '',
  },

  actions: {
    async fetchMe(): Promise<UserAccount | null> {
      try {
        this.user = await getMe()
      } catch {
        this.user = null
      }
      return this.user
    },

    ensureLoaded(): Promise<UserAccount | null> {
      if (!readyPromise) readyPromise = this.fetchMe()
      return readyPromise
    },

    setUser(user: UserAccount | null): void {
      this.user = user
      readyPromise = Promise.resolve(user)
    },

    resetAuth(): void {
      this.user = null
      readyPromise = null
    },

    patchUser(patch: Partial<UserAccount>): void {
      if (this.user) this.user = { ...this.user, ...patch }
    },
  },
})
