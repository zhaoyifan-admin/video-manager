// ================= 频道页配置表 =================
// 头图渐变终点统一固定为深色 #101013：头图是「深色强调区」，内部文字固定为白色，
// 若终点用 --color-nf-page 变量，浅色主题下会渐变到白底导致白字不可读。
// 各频道的 from / via 仍保留各自配色，深浅主题下都能区分频道。
// 一个频道 = 一个影视类型（types 表）。点击不同频道时，本表决定：
//   筛选行组合 / 每行选项 / 排序 Tab / 头图配色 / 海报墙密度
// 所有视觉值均为「完整 Tailwind 类名字符串」，保证 v4 扫描器能静态收集。
import { CHANNEL_ICONS } from './icons'

export const ROW_LABEL = {
  channel: '频道',
  genre: '标签',
  region: '地区',
  year: '年份',
  language: '语言',
  letter: '字母',
  collection: '合集',
}

// 频道头图图标：统一用 Font Awesome 图标名，映射集中维护在 icons.js
// （原先是手写 SVG path，各频道粗细/圆角不一致；现由 <FaIcon> 渲染）
export const CHANNEL_ICON = CHANNEL_ICONS

// 海报墙密度：完整类名，供 App.vue 直接绑定。
// 改为断点式列数：窄屏固定 2~3 列且不溢出，宽屏逐级增加，保持各频道原有疏密差异。
export const DENSITY_CLASS = {
  wide:
    'grid grid-cols-2 gap-[18px] min-h-[160px] max-[420px]:gap-2.5 ' +
    'min-[720px]:grid-cols-3 min-[1100px]:grid-cols-4 min-[1400px]:grid-cols-5',
  mid:
    'grid grid-cols-2 gap-4 min-h-[160px] max-[420px]:gap-2.5 ' +
    'min-[600px]:grid-cols-3 min-[900px]:grid-cols-4 min-[1200px]:grid-cols-5 min-[1500px]:grid-cols-6',
  compact:
    'grid grid-cols-3 gap-3.5 min-h-[160px] max-[420px]:grid-cols-2 max-[420px]:gap-2.5 ' +
    'min-[600px]:grid-cols-4 min-[900px]:grid-cols-5 min-[1200px]:grid-cols-6 min-[1500px]:grid-cols-8',
}

const YEARS = Array.from({ length: 20 }, (_, i) => 2026 - i)
const LETTERS = [...'ABCDEFGHIJKLMNOPQRSTUVWXYZ', '0-9']
const REGION_FULL = [
  '中国', '大陆', '香港', '台湾', '美国', '韩国', '日本', '泰国', '新加坡', '马来西亚',
  '印度', '英国', '法国', '瑞典', '瑞士', '乌克兰', '加拿大', '西班牙', '俄罗斯', '其它',
]
const REGION_ASIA = ['中国', '大陆', '香港', '台湾', '日本', '韩国', '泰国', '新加坡', '其它']
const LANG_FULL = [
  '中文', '国语', '粤语', '闽南语', '英语', '日语', '韩语', '法语', '俄语', '德语',
  '泰语', '瑞典语', '印度语', '其它',
]
const LANG_EAST = ['中文', '国语', '粤语', '日语', '韩语', '英语', '其它']
const SORT_FULL = [
  { label: '按最新', value: 'updated' },
  { label: '按最热', value: 'hot' },
  { label: '按播放', value: 'views' },
]
const SORT_SIMPLE = [
  { label: '按最新', value: 'updated' },
  { label: '按最热', value: 'hot' },
]

const BASE = {
  icon: 'grid',
  gradient: 'from-[#2a1013] via-[#160c0e] to-[#101013]',
  accentGlow: 'bg-nf-red',
  eyebrow: 'CHANNEL',
  desc: '按频道与多维条件快速定位影片',
  rows: ['channel', 'genre', 'year', 'letter'],
  regions: REGION_FULL,
  languages: LANG_FULL,
  years: YEARS,
  letters: LETTERS,
  sorts: SORT_FULL,
  density: 'mid',
}

// 首页：保留频道切换 + 标签筛选 + 排序，保留原有大卡片与 Hero
// genre 行即「标签」维度（ChannelFilter 把 genre 映射到 tagId），让搜索结果可二次按标签过滤
const HOME = {
  ...BASE,
  icon: 'home',
  gradient: 'from-[#241014] via-[#140b0d] to-[#101013]',
  eyebrow: 'ALL VIDEOS',
  desc: '全部影片 · 点击频道进入专属筛选视图',
  rows: ['channel', 'genre'],
  density: 'wide',
  minimal: true, // 首页有 Hero，不重复渲染一块大频道头图
}

export const CHANNEL_PRESETS = {
  '电影': {
    ...BASE, icon: 'movie',
    gradient: 'from-[#3a1116] via-[#1b0c0f] to-[#101013]',
    eyebrow: 'MOVIES CHANNEL',
    desc: '六维筛选 · 按标签 / 地区 / 年份 / 语言 / 字母定位',
    rows: ['channel', 'genre', 'region', 'year', 'language', 'letter'],
    density: 'compact',
  },
  '电视剧': {
    ...BASE, icon: 'tv',
    gradient: 'from-[#101f3a] via-[#0c1424] to-[#101013]',
    accentGlow: 'bg-[#3b82f6]',
    eyebrow: 'TV SERIES CHANNEL',
    desc: '剧集视图 · 额外支持按合集归类追剧',
    rows: ['channel', 'genre', 'region', 'year', 'collection', 'letter'],
    regions: REGION_ASIA,
    density: 'compact',
  },
  '连续剧': {
    ...BASE, icon: 'tv',
    gradient: 'from-[#101f3a] via-[#0c1424] to-[#101013]',
    accentGlow: 'bg-[#3b82f6]',
    eyebrow: 'TV SERIES CHANNEL',
    desc: '剧集视图 · 额外支持按合集归类追剧',
    rows: ['channel', 'genre', 'region', 'year', 'collection', 'letter'],
    regions: REGION_ASIA,
    density: 'compact',
  },
  '港剧': {
    ...BASE, icon: 'tv',
    gradient: 'from-[#2b1a3a] via-[#160f21] to-[#101013]',
    accentGlow: 'bg-[#a855f7]',
    eyebrow: 'HK DRAMA CHANNEL',
    desc: '精简筛选 · 地区与语言固定为粤语片单',
    rows: ['channel', 'genre', 'year', 'letter'],
    regions: ['香港', '中国', '大陆', '其它'],
    languages: LANG_EAST,
    density: 'mid',
  },
  '动漫': {
    ...BASE, icon: 'anime',
    gradient: 'from-[#2a1438] via-[#160d20] to-[#101013]',
    accentGlow: 'bg-[#c084fc]',
    eyebrow: 'ANIME CHANNEL',
    desc: '动漫视图 · 精简地区与字母索引',
    rows: ['channel', 'genre', 'region', 'year', 'letter'],
    regions: ['中国', '日本', '韩国', '美国', '其它'],
    years: YEARS.slice(0, 12),
    density: 'compact',
  },
  '纪录片': {
    ...BASE, icon: 'doc',
    gradient: 'from-[#0d2b26] via-[#0a1a18] to-[#101013]',
    accentGlow: 'bg-[#2dd4bf]',
    eyebrow: 'DOCUMENTARY CHANNEL',
    desc: '精简视图 · 只保留频道 / 标签 / 地区 / 年份',
    rows: ['channel', 'genre', 'region', 'year'],
    sorts: SORT_SIMPLE,
    density: 'mid',
  },
  '综艺': {
    ...BASE, icon: 'variety',
    gradient: 'from-[#3a2708] via-[#1d1508] to-[#101013]',
    accentGlow: 'bg-[#f59e0b]',
    eyebrow: 'VARIETY CHANNEL',
    desc: '综艺视图 · 按地区 / 年份 / 语言浏览',
    rows: ['channel', 'genre', 'region', 'year', 'language'],
    languages: LANG_EAST,
    density: 'mid',
  },
  '直播': {
    ...BASE, icon: 'live',
    gradient: 'from-[#3b0d0d] via-[#1c0909] to-[#101013]',
    eyebrow: 'LIVE CHANNEL',
    desc: '极简视图 · 频道 / 标签 / 地区',
    rows: ['channel', 'genre', 'region'],
    sorts: SORT_SIMPLE,
    live: true,
    density: 'mid',
  },
}

// 未配置的自定义类型（管理员新建的频道）走通用兜底
export function getPreset(name) {
  if (!name) return HOME
  return CHANNEL_PRESETS[name] || { ...BASE, eyebrow: `${name} CHANNEL`, desc: `${name} · 通用频道筛选视图` }
}
