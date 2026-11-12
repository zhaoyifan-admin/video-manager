<script setup>
import { computed } from 'vue'
import FaIcon from '../ui/FaIcon.vue'
import { ICONS } from '../composables/icons'
import { ROW_LABEL, CHANNEL_ICON } from '../composables/channelPresets'

// 频道筛选面板：频道头图 + 多维筛选行 + 排序 Tab
// 样式铁律：本组件全部使用 Tailwind 工具类，不写任何 scoped CSS。
const props = defineProps({
  preset: { type: Object, required: true },
  channelName: { type: String, default: '' },
  channels: { type: Array, default: () => [] },
  activeId: { type: Number, default: 0 },
  tags: { type: Array, default: () => [] },
  collections: { type: Array, default: () => [] },
  query: { type: Object, required: true },
  total: { type: Number, default: 0 },
})
const emit = defineEmits(['select-channel', 'apply', 'reset'])

// 排序 Tab 图标：与排序语义一一对应（键为 sort 值）
const SORT_ICON = {
  updated: 'clock',
  created: 'calendar',
  hot: 'chart-line',
  views: 'eye',
  title: 'font',
}

// 状态互斥的完整类名字符串：避免同组工具类因 CSS 生成顺序互相覆盖
// 注意：本项目 Tailwind 跳过 preflight，裸 <button> 会保留浏览器默认浅灰底/边框，
//       因此每个按钮都必须显式 bg-transparent + border-0。
const IDLE_CHIP =
  'shrink-0 border-0 bg-transparent px-2.5 py-[3px] rounded-[3px] text-[12.5px] leading-[22px] ' +
  'cursor-pointer select-none text-nf-sub transition-colors hover:bg-white/5 hover:text-white'
const ON_CHIP =
  'shrink-0 border-0 px-2.5 py-[3px] rounded-[3px] text-[12.5px] leading-[22px] font-semibold ' +
  'cursor-pointer select-none bg-nf-red text-white'
const IDLE_SORT =
  'relative flex-1 border-0 bg-transparent py-3 text-center text-[14px] cursor-pointer select-none ' +
  'text-nf-sub transition-colors hover:text-white'
const ON_SORT =
  'relative flex-1 border-0 bg-transparent py-3 text-center text-[14px] font-bold ' +
  'cursor-pointer select-none text-nf-red'

const FIELD = {
  genre: 'tagId', collection: 'collectionId', region: 'region',
  year: 'year', language: 'language', letter: 'letter',
}

const publishedChannels = computed(() => props.channels.filter((c) => c.isPublished !== false))

const optionsFor = (key) => {
  const p = props.preset
  switch (key) {
    case 'channel':
      return [
        { label: '首页', value: 0 },
        ...publishedChannels.value.map((c) => ({ label: c.name, value: c.id })),
      ]
    case 'genre':
      return [
        { label: '全部', value: 0 },
        ...props.tags.map((t) => ({ label: t.name, value: t.id })),
      ]
    case 'collection':
      return [
        { label: '全部', value: 0 },
        ...props.collections.map((c) => ({ label: c.name, value: c.id })),
      ]
    case 'region':
      return [{ label: '全部', value: '' }, ...p.regions.map((x) => ({ label: x, value: x }))]
    case 'language':
      return [{ label: '全部', value: '' }, ...p.languages.map((x) => ({ label: x, value: x }))]
    case 'year':
      return [{ label: '全部', value: 0 }, ...p.years.map((y) => ({ label: String(y), value: y }))]
    case 'letter':
      return [{ label: '全部', value: '' }, ...p.letters.map((l) => ({ label: l, value: l }))]
    default:
      return [{ label: '全部', value: 0 }]
  }
}

const valueFor = (key) => {
  if (key === 'channel') return props.activeId
  const field = FIELD[key]
  return field ? props.query[field] : 0
}

const rows = computed(() =>
  props.preset.rows.map((key) => ({
    key,
    label: ROW_LABEL[key] || key,
    options: optionsFor(key),
    value: valueFor(key),
  })),
)

const isOn = (row, opt) => row.value === opt.value

const choose = (row, opt) => {
  if (row.key === 'channel') {
    emit('select-channel', opt.value)
    return
  }
  const field = FIELD[row.key]
  if (!field) return
  emit('apply', { page: 1, [field]: opt.value })
}

const chooseSort = (s) => emit('apply', { page: 1, sort: s.value })

const hasFilters = computed(() => {
  const q = props.query
  return !!(q.tagId || q.collectionId || q.region || q.language || q.year || q.letter)
})
</script>

<template>
  <section
    class="mb-6 overflow-hidden rounded-xl border border-white/[0.07] bg-[#101013]"
  >
    <!-- ===== 频道头图：每个频道配色 / 图标 / 文案不同（首页已有 Hero，跳过） ===== -->
    <div
      v-if="!preset.minimal"
      class="relative flex items-center gap-4 bg-gradient-to-r px-7 py-6 max-[900px]:px-5 max-[900px]:py-5"
      :class="preset.gradient"
    >
      <div
        class="pointer-events-none absolute -right-10 -top-16 h-44 w-44 rounded-full opacity-[0.12] blur-[70px]"
        :class="preset.accentGlow"
      ></div>
      <div
        class="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/[0.06] text-[22px] text-white"
      >
        <FaIcon
          :icon="CHANNEL_ICON[preset.icon] || CHANNEL_ICON.grid"
          :fixed="false"
        />
      </div>
      <div class="min-w-0 flex-1">
        <div class="flex items-center gap-2 text-[10px] font-bold tracking-[3px] text-white/45">
          <span
            v-if="preset.live"
            class="inline-block h-[7px] w-[7px] animate-pulse rounded-full bg-nf-red"
          ></span>
          {{ preset.eyebrow }}
        </div>
        <h1 class="mt-1 truncate text-[23px] font-extrabold tracking-[1px] text-white">
          {{ channelName || '全部影片' }}
        </h1>
        <p class="mt-0.5 truncate text-[12.5px] text-white/55">{{ preset.desc }}</p>
      </div>
      <div class="hidden shrink-0 text-right sm:block">
        <div class="text-[26px] font-extrabold leading-none text-white tabular-nums">{{ total }}</div>
        <div class="mt-1 text-[11px] tracking-[2px] text-white/45">部影片</div>
      </div>
    </div>

    <!-- ===== 多维筛选行：行数与选项随频道变化 ===== -->
    <div
      class="px-7 max-[900px]:px-5"
      :class="preset.minimal ? 'pb-3 pt-3' : 'pb-4 pt-5'"
    >
      <div
        v-for="row in rows"
        :key="row.key"
        class="flex items-start gap-3 border-b border-white/[0.04] py-[7px] last:border-b-0 max-[900px]:flex-col max-[900px]:gap-1"
      >
        <span
          class="w-11 shrink-0 pt-[3px] text-[12.5px] font-semibold tracking-[1px] text-nf-muted"
        >
          {{ row.label }}
        </span>
        <div class="flex min-w-0 flex-1 flex-wrap items-center gap-x-1 gap-y-1">
          <button
            v-for="opt in row.options"
            :key="`${row.key}-${opt.value}`"
            :class="isOn(row, opt) ? ON_CHIP : IDLE_CHIP"
            @click="choose(row, opt)"
          >
            {{ opt.label }}
          </button>
          <span
            v-if="row.key === 'genre' && row.options.length === 1"
            class="ml-1 text-[12px] text-nf-muted"
          >
            暂无已发布标签，可在「更多 → 标签 / 类型管理」中新增
          </span>
        </div>
      </div>

      <!-- 筛选口径说明：让「模糊匹配」维度可预期 -->
      <p v-if="!preset.minimal" class="mt-3 flex items-start gap-1.5 text-[11.5px] leading-relaxed text-nf-muted">
        <FaIcon :icon="ICONS.info" :fixed="false" class="mt-[3px] text-[11px]" />
        <span>筛选口径：类型 / 合集按库内标签与合集精确匹配；地区、语言按标题或备注关键词匹配；年份按入库年份；字母按标题首字母。</span>
      </p>
    </div>

    <!-- ===== 排序 Tab：不同频道可配置不同排序项 ===== -->
    <div class="flex items-center border-t border-white/[0.06] bg-black/20 px-7 max-[900px]:px-5">
      <button
        v-for="s in preset.sorts"
        :key="s.value"
        :class="query.sort === s.value ? ON_SORT : IDLE_SORT"
        @click="chooseSort(s)"
      >
        <FaIcon
          :icon="SORT_ICON[s.value] || 'chart-line'"
          :fixed="false"
          class="mr-1.5 text-[12px]"
        />{{ s.label }}
        <span
          v-if="query.sort === s.value"
          class="absolute bottom-1.5 left-1/2 h-[3px] w-6 -translate-x-1/2 rounded-full bg-nf-red"
        ></span>
      </button>
      <button
        v-if="hasFilters"
        class="ml-4 inline-flex shrink-0 items-center rounded border border-white/15 bg-transparent px-3 py-1 text-[12px] text-nf-sub transition-colors hover:border-nf-red hover:text-white"
        @click="emit('reset')"
      >
        <FaIcon :icon="ICONS.reset" :fixed="false" class="mr-1.5" />重置筛选
      </button>
    </div>
  </section>
</template>
