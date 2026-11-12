<script setup>
import { computed } from 'vue'
import FaIcon from '../ui/FaIcon.vue'
import { ICONS } from '../composables/icons'
import { useCover } from '../composables/useCover'

// 频道页海报卡片：竖版 2:3 封面 + 右上角徽章 + 标题/简介 + 悬停操作条
// 样式铁律：全部 Tailwind 工具类，无 scoped CSS。
const props = defineProps({
  video: { type: Object, required: true },
  manageable: { type: Boolean, default: false },
  selectable: { type: Boolean, default: false },
  selected: { type: Boolean, default: false },
})
defineEmits(['play', 'detail', 'toggle-fav', 'edit', 'remove', 'toggle-public', 'select'])

const { coverCache, durationCache } = useCover()

// 完整类名字符串，保证 Tailwind v4 静态扫描可收集
const TONES = [
  'bg-gradient-to-br from-[#1d2a44] to-[#101826]',
  'bg-gradient-to-br from-[#17301f] to-[#0f2015]',
  'bg-gradient-to-br from-[#33210f] to-[#1f1409]',
  'bg-gradient-to-br from-[#2a1f3d] to-[#181126]',
  'bg-gradient-to-br from-[#33141d] to-[#1f0c11]',
  'bg-gradient-to-br from-[#123333] to-[#0c1f20]',
]
const tone = computed(() => TONES[props.video.id % TONES.length])
const badge = computed(() => props.video.tags?.[0] || props.video.typeName || '未分类')
const subline = computed(() => props.video.description || props.video.tags?.join(' · ') || '暂无简介')

// 操作条图标改用 Font Awesome 语义表（原先是手写 SVG path，各图标粗细不一致）
// 收藏用 solid 实心 / regular 空心区分，公开状态用 globe / lock 区分。
const actions = computed(() => {
  const v = props.video
  const list = [
    { key: 'detail', icon: ICONS.detail, title: '查看详情', show: true },
    {
      key: 'toggle-fav', icon: ICONS.fav, variant: v.isFavorite ? 'solid' : 'regular',
      title: v.isFavorite ? '取消收藏' : '收藏', show: true, active: v.isFavorite,
    },
    { key: 'edit', icon: ICONS.edit, title: '编辑', show: props.manageable },
    {
      key: 'toggle-public', icon: v.isPublic ? ICONS.publicOn : ICONS.publicOff,
      title: v.isPublic ? '设为私有' : '设为公开', show: props.manageable, active: v.isPublic,
    },
    { key: 'remove', icon: ICONS.remove, title: '删除', show: props.manageable, danger: true },
  ]
  return list.filter((a) => a.show)
})

</script>

<template>
  <article
    class="group cursor-pointer select-none"
    @click="selectable ? $emit('select', video) : $emit('play', video)"
  >
    <!-- 竖版海报 -->
    <div
      v-lazy-cover="video"
      class="relative aspect-[2/3] overflow-hidden rounded-lg border border-white/10 transition-all duration-200 group-hover:-translate-y-0.5 group-hover:border-nf-red/60 group-hover:shadow-[0_14px_30px_rgba(0,0,0,0.6)]"
      :class="[tone, { 'outline outline-2 -outline-offset-2 outline-nf-red': selectable && selected }]"
    >
      <img
        v-if="coverCache[video.id]"
        :src="coverCache[video.id]"
        class="absolute inset-0 h-full w-full object-cover"
        alt=""
      />
      <div class="absolute inset-0 bg-gradient-to-t from-black/75 via-transparent to-black/30"></div>

      <!-- 右上角徽章：首个标签或影视类型 -->
      <span
        class="absolute right-1.5 top-1.5 max-w-[70%] truncate rounded bg-black/60 px-1.5 py-[2px] text-[10px] font-medium text-white/90 backdrop-blur-sm"
        :title="badge"
      >
        {{ badge }}
      </span>

      <!-- 批量选择复选框 -->
      <label
        v-if="selectable"
        class="absolute left-1.5 top-1.5 flex h-5 w-5 cursor-pointer items-center justify-center rounded border border-white/60 bg-black/50"
        @click.stop
      >
        <input
          type="checkbox"
          class="h-3 w-3 cursor-pointer accent-nf-red"
          :checked="selected"
          @change="$emit('select', video)"
        />
      </label>

      <!-- 左下角时长 -->
      <span
        v-if="durationCache[video.id]"
        class="absolute bottom-2 left-2 rounded bg-black/65 px-1.5 py-[1px] text-[10px] tabular-nums text-white/85"
      >
        {{ durationCache[video.id] }}
      </span>

      <!-- 悬停：播放按钮 + 底部操作条 -->
      <div
        class="absolute inset-0 flex flex-col items-center justify-center bg-black/45 opacity-0 transition-opacity duration-200 group-hover:opacity-100"
      >
        <span
          class="mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-nf-red text-white shadow-lg"
        >
          <FaIcon :icon="ICONS.play" :fixed="false" class="ml-0.5 text-[20px]" />
        </span>
      </div>
      <div
        class="absolute inset-x-0 bottom-0 flex items-center justify-center gap-1 border-t border-white/10 bg-black/75 px-1 py-1.5 opacity-0 transition-opacity duration-200 group-hover:opacity-100"
        @click.stop
      >
        <button
          v-for="a in actions"
          :key="a.key"
          class="flex h-6 w-6 shrink-0 items-center justify-center rounded border-0 bg-transparent text-white/70 transition-colors hover:bg-white/15 hover:text-white"
          :class="[
            a.active ? 'text-nf-red' : '',
            a.danger ? 'hover:bg-nf-red hover:text-white' : '',
          ]"
          :title="a.title"
          @click="$emit(a.key, video)"
        >
          <FaIcon
            :icon="a.icon"
            :variant="a.variant || 'solid'"
            :fixed="false"
            class="text-[13px]"
          />
        </button>
      </div>
    </div>

    <!-- 海报下方信息：标题 + 简介 -->
    <h3
      class="mt-2 truncate text-[13px] font-semibold text-nf-text transition-colors group-hover:text-white"
      :title="video.title"
    >
      {{ video.title }}
    </h3>
    <p class="mt-0.5 truncate text-[11.5px] text-nf-muted" :title="subline">{{ subline }}</p>
  </article>
</template>
