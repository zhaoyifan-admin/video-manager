<template>
  <div class="min-h-screen flex items-center justify-center">
    <div class="text-center">
      <div class="text-7xl font-light leading-none" style="color: var(--nf-red)">403</div>
      <p class="mt-5 text-sm" style="color: var(--nf-text-primary)">没有权限访问该页面</p>
      <p v-if="redirect" class="mt-2 text-xs" style="color: var(--nf-text-muted)">
        原路径：{{ redirect }}
      </p>
      <div class="mt-8 flex justify-center gap-3">
        <el-button @click="router.push('/console')">返回控制台</el-button>
        <el-button type="primary" @click="router.push('/login')">重新登录</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const redirect = route.query.redirect || ''
</script>
