<template>
  <div v-if="visible" class="header-breadcrumb">
    <template v-for="(crumb, index) in crumbs" :key="`${crumb.code}-${index}`">
      <span v-if="index > 0" class="crumb-sep">/</span>
      <AppIcon v-if="showIcon && crumb.icon" :name="crumb.icon" :size="13" class="crumb-icon" />
      <span :class="index === crumbs.length - 1 ? 'crumb-current' : 'crumb-prev'">{{ crumb.title }}</span>
    </template>
    <span v-if="!crumbs.length" class="crumb-prev">{{ fallback }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AppIcon from '../../components/AppIcon.vue'

const props = withDefaults(defineProps<{
  crumbs: Array<{ code: string; title: string; icon?: string }>
  fallback?: string
  showIcon?: boolean
  hideOnlyOne?: boolean
}>(), { fallback: '管理控制台', showIcon: false, hideOnlyOne: false })

const visible = computed(() => !(props.hideOnlyOne && props.crumbs.length <= 1))
</script>

<style scoped>
.header-breadcrumb { display: flex; align-items: center; gap: 8px; font-size: var(--nf-font-base); min-width: 0; }
.crumb-sep { color: var(--nf-border-strong); }
.crumb-prev { color: var(--nf-text-secondary); }
.crumb-current { color: var(--nf-text-primary); }
.crumb-icon { display: inline-flex; }
</style>
