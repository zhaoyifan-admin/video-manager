<template>
  <div class="app-logo" :class="{ 'app-logo--compact': compact }" @click="emit('click')">
    <span class="logo-mark" />
    <span v-if="!compact" class="logo-text">管理平台</span>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ compact?: boolean }>(), { compact: false })
const emit = defineEmits<{ click: [] }>()
</script>

<style scoped>
.app-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 100%;
  padding: 0 16px;
  cursor: pointer;
}
.app-logo--compact { justify-content: center; padding: 0; }
.logo-mark { width: 8px; height: 20px; border-radius: 2px; background: var(--el-color-primary); flex: 0 0 auto; }
.logo-text { font-size: var(--nf-font-md); font-weight: 500; letter-spacing: 0.5px; white-space: nowrap; }
</style>
