<template>
  <div class="min-h-[70vh] flex items-center justify-center">
    <div class="max-w-md text-center">
      <div class="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-full"
        style="background: color-mix(in srgb, var(--nf-red) 14%, transparent)">
        <span class="text-2xl" style="color: var(--nf-red)">!</span>
      </div>
      <h2 class="text-lg font-medium" style="color: var(--nf-text-primary)">
        暂无可访问的管理模块
      </h2>
      <p class="mt-3 text-sm leading-relaxed" style="color: var(--nf-text-muted)">
        当前账号尚未被授予管理平台的菜单权限。你可以继续使用视频子系统，或联系管理员开通访问权限。
      </p>
      <div class="mt-8 flex justify-center gap-3">
        <el-button @click="handleLogout">重新登录</el-button>
        <el-button type="primary" @click="openVideo">打开视频子系统</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { logout } from '../../api'
import { useAuthStore } from '../../stores/auth'
import { resetDynamicRoutes } from '../../router/dynamic'

const router = useRouter()
const auth = useAuthStore()

const openVideo = () => {
  // 子系统为独立挂载的 SPA，必须整页跳转。
  window.location.assign('/video/')
}

const handleLogout = async () => {
  await logout().catch(() => {})
  auth.resetAuth()
  resetDynamicRoutes(router)
  router.push({ name: 'login' })
}
</script>
