<template>
  <el-icon v-if="icon.kind === 'el'" :size="size" :color="color">
    <component :is="icon.value" />
  </el-icon>
  <svg
    v-else-if="icon.kind === 'svg'"
    class="app-icon-svg"
    :style="{ width: sizeValue, height: sizeValue, color }"
    aria-hidden="true"
  >
    <use :href="icon.value" />
  </svg>
  <i
    v-else-if="icon.kind === 'font'"
    class="app-icon-font"
    :class="icon.value"
    :style="{ fontSize: sizeValue, color }"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { resolveIcon } from '../utils/icons'

const props = withDefaults(defineProps<{
  name?: string | number | null
  size?: number | string
  color?: string
}>(), {
  name: '',
  size: 16,
})

const icon = computed(() => resolveIcon(props.name))
const sizeValue = computed(() => typeof props.size === 'number' ? `${props.size}px` : props.size)
</script>

<style scoped>
.app-icon-font,
.app-icon-svg {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  vertical-align: middle;
}
</style>
