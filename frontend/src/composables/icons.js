/**
 * 全局图标语义表（Font Awesome 6 免费版 / solid）。
 *
 * 原来系统里图标分散在 20 多个组件中：手写 SVG path、emoji、字符符号（＋ ✕ ⋯ ▶ ★）混用，
 * 同类操作在不同页面长得不一样。这里按「语义」统一收敛，组件只引用语义键，
 * 以后换图标或换图标库只改这一处。
 *
 * 用法：import { ICONS } from '../composables/icons'
 *      <FaIcon :icon="ICONS.play" />
 */
export const ICONS = {
  // ===== 顶部导航 / 全局入口 =====
  home: 'house',
  favorites: 'heart',
  search: 'magnifying-glass',
  audit: 'clipboard-check',
  submissions: 'bell',
  create: 'plus',
  more: 'ellipsis',
  menu: 'bars',
  caretDown: 'caret-down',
  themeLight: 'sun',
  themeDark: 'moon',
  admin: 'gear',
  taxonomy: 'tags',
  batch: 'file-import',
  logout: 'arrow-right-from-bracket',
  account: 'circle-user',
  back: 'arrow-left',

  // ===== 视频 / 卡片操作 =====
  play: 'play',
  pause: 'pause',
  detail: 'circle-info',
  fav: 'heart',
  edit: 'pen',
  publicOn: 'globe',
  publicOff: 'lock',
  remove: 'trash',
  star: 'star',
  views: 'eye',
  duration: 'clock',
  publish: 'eye',
  unpublish: 'eye-slash',
  video: 'file-video',
  cover: 'image',
  collection: 'layer-group',
  playlist: 'list-ul',
  playlistAdd: 'plus',
  wantlist: 'bookmark',
  recommend: 'wand-magic-sparkles',
  cast: 'display',
  copy: 'copy',
  auditLog: 'clock-rotate-left',

  // ===== 通用动作 / 状态 =====
  close: 'xmark',
  check: 'check',
  success: 'circle-check',
  warning: 'triangle-exclamation',
  info: 'circle-info',
  error: 'circle-xmark',
  spinner: 'spinner',
  reset: 'arrows-rotate',
  refresh: 'rotate',
  filter: 'filter',
  list: 'list-check',
  select: 'square-check',
  ban: 'ban',
  unlock: 'unlock',
  download: 'download',

  // ===== 表单 / 文件 / 路径 =====
  folder: 'folder',
  folderOpen: 'folder-open',
  upload: 'upload',
  key: 'key',
  camera: 'camera',
  user: 'user',
  userAdd: 'user-plus',
  users: 'users',
  login: 'right-to-bracket',
  passwordShow: 'eye',
  passwordHide: 'eye-slash',
  hardDrive: 'hard-drive',
  chart: 'chart-line',
  gauge: 'gauge',
  shield: 'shield-halved',

  // ===== 翻页 / 轮播 =====
  prev: 'angle-left',
  next: 'angle-right',
  chevronLeft: 'chevron-left',
  chevronRight: 'chevron-right',
  chevronUp: 'chevron-up',
  backward: 'backward',
  forward: 'forward',

  // ===== 筛选维度（频道页说明行） =====
  region: 'location-dot',
  language: 'language',
  year: 'calendar',
  letter: 'font',
}

/** 频道头图图标：key 与 channelPresets.js 的 preset.icon 对应，值为 FA 图标名 */
export const CHANNEL_ICONS = {
  home: 'house',
  movie: 'clapperboard',
  tv: 'tv',
  doc: 'newspaper',
  variety: 'star',
  anime: 'face-smile',
  live: 'tower-broadcast',
  grid: 'table-cells',
}
