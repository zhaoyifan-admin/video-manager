<template>
  <div class="login-page flex min-h-screen items-center justify-center">
    <div
      class="w-full max-w-sm rounded-xl border p-8"
      style="background: var(--nf-bg-card); border-color: var(--nf-border)"
    >
      <div class="mb-8">
        <PlatformLogo :size="40" class="mb-4" />
        <h1 class="text-xl font-medium" style="color: var(--nf-text-primary)">中型管理系统</h1>
        <p class="mt-2 text-xs" style="color: var(--nf-text-muted)">
          统一登录入口 · 子系统按权限访问
        </p>
      </div>

      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="用户名">
          <el-input
            v-model="form.username"
            autocomplete="username"
            placeholder="请输入用户名"
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            type="password"
            autocomplete="current-password"
            placeholder="请输入密码"
            show-password
            @keyup.enter="submit"
          />
        </el-form-item>
        <p v-if="error" class="mb-3 text-xs" style="color: #e24b4a">{{ error }}</p>
        <el-button type="primary" class="w-full" :loading="submitting" @click="submit">
          登录
        </el-button>
      </el-form>

      <p class="mt-6 text-center text-xs" style="color: var(--nf-text-muted)">
        视频子系统入口：/video/
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { login } from './api'
import { useAuthStore } from './stores/auth'
import PlatformLogo from './components/PlatformLogo.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const form = reactive({ username: '', password: '' })
const submitting = ref(false)
const error = ref('')

const submit = async () => {
  if (!form.username || !form.password) {
    error.value = '请输入用户名与密码'
    return
  }
  submitting.value = true
  error.value = ''
  try {
    const user = await login(form.username, form.password)
    auth.setUser(user)
    router.push(String(route.query.redirect || '/console'))
  } catch (err) {
    error.value = err.message || '登录失败'
  } finally {
    submitting.value = false
  }
}
</script>
