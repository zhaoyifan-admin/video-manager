<template>
  <template v-for="item in items" :key="item.code">
    <el-sub-menu
      v-if="!primaryOnly && item.type === 'DIR' && item.children?.length"
      :index="item.code"
    >
      <template #title>
        <AppIcon v-if="item.icon" :name="item.icon" :size="16" class="app-menu-icon" />
        <span>{{ item.title }}</span>
      </template>
      <MenuItems
        :items="item.children"
        :mode="mode"
        @select="value => emit('select', value)"
      />
    </el-sub-menu>
    <el-menu-item
      v-else
      :index="primaryOnly && item.type === 'DIR' ? item.code : (item.path || item.code)"
    >
      <AppIcon v-if="item.icon" :name="item.icon" :size="16" class="app-menu-icon" />
      <span>{{ item.title }}</span>
    </el-menu-item>
  </template>
</template>

<script setup lang="ts">
import type { MenuNode } from '@video-manager/shared'
import AppIcon from '../../components/AppIcon.vue'

withDefaults(defineProps<{
  items: MenuNode[]
  mode?: 'vertical' | 'horizontal'
  primaryOnly?: boolean
}>(), {
  mode: 'vertical',
  primaryOnly: false,
})

const emit = defineEmits<{ select: [index: string] }>()
</script>
