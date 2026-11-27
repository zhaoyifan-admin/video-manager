import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getUnreadNoticeCount, markNoticeRead } from '../api'

// P2 通知中心的全局未读数：顶栏角标与通知中心共用，避免两处各拉一次。
export const useNoticeStore = defineStore('notices', () => {
  const unread = ref(0)

  const refresh = async (): Promise<void> => {
    try {
      unread.value = (await getUnreadNoticeCount()).count
    } catch {
      // 无权限（如未分配通知中心菜单）或未登录时静默归零，不打扰用户。
      unread.value = 0
    }
  }

  const markRead = async (id: number): Promise<void> => {
    await markNoticeRead(id)
    await refresh()
  }

  const reset = (): void => {
    unread.value = 0
  }

  return { unread, refresh, markRead, reset }
})
