<template>
  <el-card class="console-placeholder">
    <template #header>
      <div class="flex items-center justify-between">
        <span class="text-sm font-medium">{{ title }}</span>
        <el-tag size="small" type="warning" effect="dark">骨架页</el-tag>
      </div>
    </template>
    <div class="py-10 text-center text-sm" style="color: var(--nf-text-sub)">
      <p>本模块已在菜单与权限体系中登记，业务功能将在后续批次交付。</p>
      <p class="mt-2 text-xs" style="color: var(--nf-text-muted)">
        路由标识：{{ route.name }} · 权限码：{{ route.meta.permission || '无' }}
      </p>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const title = computed(() => route.meta.title || '管理模块')
</script>
