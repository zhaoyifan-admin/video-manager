import { defineStore } from 'pinia'
import { getMe } from '../api'
import type { CurrentUser, MenuNode } from '@video-manager/shared'

// 仅首次调用时请求 /auth/me；后续路由守卫复用该 Promise。
let readyPromise: Promise<CurrentUser | null> | null = null

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as CurrentUser | null,
    menus: [] as MenuNode[],
    permissions: [] as string[],
  }),

  getters: {
    isAuthenticated: (state): boolean => Boolean(state.user),
  },

  actions: {
    async fetchMe(): Promise<CurrentUser | null> {
      try {
        this.user = await getMe()
      } catch {
        this.user = null
      }
      return this.user
    },

    ensureLoaded(): Promise<CurrentUser | null> {
      if (!readyPromise) readyPromise = this.fetchMe()
      return readyPromise
    },

    setUser(user: CurrentUser | null): void {
      this.user = user
      readyPromise = Promise.resolve(user)
    },

    resetAuth(): void {
      this.user = null
      this.menus = []
      this.permissions = []
      readyPromise = null
    },

    patchUser(patch: Partial<CurrentUser>): void {
      if (this.user) this.user = { ...this.user, ...patch }
    },

    setMenus(menus: MenuNode[]): void {
      this.menus = menus
    },

    setPermissions(items: string[]): void {
      this.permissions = items
    },
  },
})
