<template>
  <div class="app-logo" :class="{ 'app-logo--compact': compact }" @click="emit('click')">
    <PlatformLogo :size="compact ? 22 : 24" />
    <span v-if="!compact" class="logo-text">管理平台</span>
  </div>
</template>

<script setup lang="ts">
import PlatformLogo from '../../components/PlatformLogo.vue'

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
.logo-text { font-size: var(--nf-font-md); font-weight: 500; letter-spacing: 0.5px; white-space: nowrap; }
</style>
