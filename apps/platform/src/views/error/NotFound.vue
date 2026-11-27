<template>
  <div class="min-h-screen flex items-center justify-center">
    <div class="text-center">
      <div class="text-7xl font-light leading-none" style="color: var(--nf-red)">404</div>
      <p class="mt-5 text-sm" style="color: var(--nf-text-primary)">页面不存在</p>
      <p class="mt-2 text-xs" style="color: var(--nf-text-muted)">{{ route.fullPath }}</p>
      <div class="mt-8 flex justify-center gap-3">
        <el-button @click="router.back()">返回上一页</el-button>
        <el-button type="primary" @click="router.push('/console')">返回控制台</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
</script>
