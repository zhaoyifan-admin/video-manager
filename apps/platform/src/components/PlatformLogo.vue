<template>
  <svg
    class="platform-logo"
    :width="size"
    :height="size"
    viewBox="0 0 64 64"
    fill="none"
    aria-hidden="true"
  >
    <!-- 中台标识：方框代表统一底座，贯穿的竖轴代表中台枢纽 -->
    <rect
      x="12"
      y="20"
      width="40"
      height="24"
      rx="6"
      stroke="currentColor"
      stroke-width="6"
    />
    <rect x="29" y="8" width="6" height="48" rx="3" fill="currentColor" />
  </svg>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ size?: number | string }>(), { size: 24 })
</script>

<style scoped>
.platform-logo {
  display: block;
  flex: 0 0 auto;
  color: var(--el-color-primary);
}
</style>
