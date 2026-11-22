<script setup>
import { computed } from 'vue'

/**
 * 全局统一图标组件（Font Awesome 6 免费版）。
 *
 * - icon 直接传 FA 图标名，如 <FaIcon icon="house" />；
 *   也可传 composables/icons.js 里的语义键对应值，如 :icon="ICONS.play"。
 * - 这些 fa-* 类由全局 all.min.css 提供（不是 Tailwind 工具类），
 *   所以动态拼接同样生效；颜色、字号继续用 Tailwind 的 text-* / text-[..] 控制。
 * - 默认 fa-fw 固定宽度，让菜单 / 按钮里的图标与文字整齐对齐；
 *   纯图标且需要紧凑时可传 :fixed="false"。
 */
const props = defineProps({
  icon: { type: String, required: true },
  variant: { type: String, default: 'solid' }, // solid | regular | brands
  fixed: { type: Boolean, default: true },
  size: { type: String, default: '' }, // 2xs / xs / sm / lg / xl / 2xl
  spin: { type: Boolean, default: false },
})

const classes = computed(() => [
  `fa-${props.variant}`,
  `fa-${props.icon}`,
  props.fixed ? 'fa-fw' : '',
  props.size ? `fa-${props.size}` : '',
  props.spin ? 'fa-spin' : '',
].filter(Boolean))
</script>

<template>
  <i :class="classes" aria-hidden="true"></i>
</template>
