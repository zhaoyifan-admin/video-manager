<template>
  <el-menu
    :mode="mode"
    :default-active="activeIndex || activePath"
    :collapse="collapse"
    :unique-opened="accordion"
    :ellipsis="mode === 'horizontal'"
    :class="['app-menu', `app-menu--${mode}`, { 'app-menu--primary': primaryOnly }]"
    @select="(value: unknown) => emit('select', String(value))"
  >
    <MenuItems
      :items="menus"
      :mode="mode"
      :primary-only="primaryOnly"
      @select="value => emit('select', value)"
    />
  </el-menu>
</template>

<script setup lang="ts">
import type { MenuNode } from '@video-manager/shared'
import MenuItems from './MenuItems.vue'

withDefaults(defineProps<{
  menus: MenuNode[]
  mode?: 'vertical' | 'horizontal'
  activePath?: string
  activeIndex?: string
  primaryOnly?: boolean
  collapse?: boolean
  accordion?: boolean
}>(), {
  mode: 'vertical',
  activePath: '',
  activeIndex: '',
  primaryOnly: false,
  collapse: false,
  accordion: true,
})

const emit = defineEmits<{ select: [index: string] }>()
</script>
