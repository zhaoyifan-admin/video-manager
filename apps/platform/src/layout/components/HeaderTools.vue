<template>
  <div class="header-tools">
    <el-badge v-if="theme.widgetNotification" :value="notices.unread" :hidden="!notices.unread" :max="99">
      <el-button text @click="openNotices">通知</el-button>
    </el-badge>
    <el-button text @click="openVideo">视频子系统</el-button>
    <el-button v-if="theme.widgetRefresh" text title="刷新页面" @click="refresh">
      <el-icon><Refresh /></el-icon>
    </el-button>
    <el-button
      v-if="theme.widgetThemeToggle"
      text
      :title="theme.isLight ? '深色模式' : '浅色模式'"
      @click="theme.toggle()"
    >
      <el-icon><Moon v-if="theme.isLight" /><Sunny v-else /></el-icon>
    </el-button>
    <el-button v-if="theme.widgetSettings" text title="偏好设置" @click="emit('openSettings')">
      <el-icon><Setting /></el-icon>
    </el-button>
    <el-dropdown @command="handleCommand">
      <span class="user-trigger">
        <el-avatar v-if="user?.avatar" :src="user.avatar" :size="26" />
        <el-avatar v-else :size="26">{{ user?.username?.slice(0, 1) || 'U' }}</el-avatar>
        <span class="user-name">{{ user?.username || '未登录' }}</span>
      </span>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item command="video">打开视频子系统</el-dropdown-item>
          <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Moon, Refresh, Setting, Sunny } from '@element-plus/icons-vue'
import { logout } from '../../api'
import { useAuthStore } from '../../stores/auth'
import { useNoticeStore } from '../../stores/notices'
import { useThemeStore } from '../../stores/theme'

const emit = defineEmits<{ openSettings: [] }>()
const router = useRouter()
const auth = useAuthStore()
const theme = useThemeStore()
const notices = useNoticeStore()
const user = computed(() => auth.user)

const openNotices = (): void => { void router.push('/console/notices') }
const openVideo = (): void => { window.location.assign('/video/') }
const refresh = (): void => { window.location.reload() }

const handleCommand = async (command: string): Promise<void> => {
  if (command === 'video') {
    openVideo()
    return
  }
  if (command === 'logout') {
    await logout().catch(() => {})
    auth.resetAuth()
    notices.reset()
    router.push({ name: 'login' })
  }
}
</script>

<style scoped>
.header-tools { display: flex; align-items: center; gap: 4px; }
.user-trigger { display: inline-flex; align-items: center; gap: 8px; cursor: pointer; }
.user-name { font-size: var(--nf-font-base); color: var(--nf-text-primary); }
</style>
