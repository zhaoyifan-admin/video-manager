import * as ElementPlusIconsVue from '@element-plus/icons-vue'

/**
 * 菜单图标统一走 tvue 原生的 tvue-input-icon。
 * tvue 的 icon-temp 支持三类值：
 * 1. `el-icon-xxx`：Element Plus 组件（tvue 安装时全局注册）
 * 2. `#icon-xxx`：SVG symbol（<use href="#icon-xxx">）
 * 3. 字体图标 class：如 `fa-solid fa-house`、`iconfont icon-home`
 *
 * 这里把 Element Plus / FontAwesome / 阿里 iconfont 聚合成同一个 iconList，
 * 并提供存量旧值的兼容转换与统一的渲染类型判断。
 */

export type IconListItem = {
  label: string
  value: string
  size: number
  color?: string
}

export type IconListTab = {
  label: string
  prop: string
  list: IconListItem[]
}

/**
 * 阿里 iconfont 项目样式表地址。
 * 填入自己的 at.alicdn.com/t/xxx.css 后，下面的 iconfont symbol 才会显示真实字形。
 * 留空也不影响 Element Plus / FontAwesome 的使用。
 */
export const ICONFONT_CSS_URLS: string[] = [
  // 'https://at.alicdn.com/t/font_xxxxxxxx.css',
]

const iconfontStyleKeys = new Set<string>()

/** 在入口调用，把用户配置的 iconfont 样式表注入页面，避免重复插入 */
export const loadIconfontStyles = (urls: string[] = ICONFONT_CSS_URLS): void => {
  if (typeof document === 'undefined') return
  urls.filter(Boolean).forEach(raw => {
    const href = raw.startsWith('//') ? `${window.location.protocol}${raw}` : raw
    if (iconfontStyleKeys.has(href)) return
    const exists = Array.from(document.querySelectorAll<HTMLLinkElement>('link[data-iconfont-href]'))
      .some(link => link.dataset.iconfontHref === href)
    if (exists) {
      iconfontStyleKeys.add(href)
      return
    }
    const link = document.createElement('link')
    link.rel = 'stylesheet'
    link.href = href
    link.dataset.iconfontHref = href
    document.head.appendChild(link)
    iconfontStyleKeys.add(href)
  })
}

/** 驼峰图标名 → tvue 注册的组件名，如 HomeFilled → el-icon-home-filled */
export const toTvueIconName = (name: string): string =>
  'el-icon' + name.replace(/[A-Z]/g, m => '-' + m.toLowerCase())

/** Element Plus 全部图标名（去掉 default 导出） */
const elementIconNames = Object.keys(ElementPlusIconsVue).filter(k => k !== 'default')

/** 常用图标的中文名，仅用于列表展示 */
const elementIconLabels: Record<string, string> = {
  HomeFilled: '首页', Setting: '设置', Tools: '工具', User: '用户', UserFilled: '用户',
  Lock: '锁', Key: '密钥', Avatar: '头像', Menu: '菜单', Grid: '网格',
  Operation: '操作', Management: '管理', Document: '文档', DocumentChecked: '已办文档',
  Tickets: '列表', Files: '文件', Folder: '文件夹', FolderOpened: '文件夹(开)',
  Bell: '通知', Warning: '警告', WarningFilled: '警告', InfoFilled: '信息',
  CircleCheck: '成功', CircleClose: '关闭', VideoCamera: '视频', Camera: '相机',
  PriceTag: '标签', Odometer: '仪表盘', DataAnalysis: '数据分析', Histogram: '柱状图',
  PieChart: '饼图', TrendCharts: '趋势', Calendar: '日历', Clock: '时钟',
  Search: '搜索', Plus: '新增', Delete: '删除', Edit: '编辑', Refresh: '刷新',
  Star: '星标', Collection: '收藏', Monitor: '监控', Box: '盒子', Wallet: '钱包',
}

/** FontAwesome Free 常用 solid 图标（7.x class 名） */
const fontAwesomeSolidNames = [
  'house', 'gear', 'user', 'users', 'user-gear', 'shield-halved', 'lock', 'key',
  'gauge-high', 'chart-bar', 'chart-simple', 'chart-pie', 'table', 'list',
  'folder', 'folder-open', 'file-lines', 'file', 'file-image', 'images',
  'video', 'play', 'film', 'camera', 'microphone', 'music',
  'book-open', 'book', 'clipboard-list', 'clipboard-check', 'note-sticky',
  'tags', 'tag', 'bell', 'calendar', 'calendar-check', 'clock', 'hourglass',
  'magnifying-glass', 'plus', 'minus', 'pen', 'trash', 'arrows-rotate',
  'circle-check', 'circle-xmark', 'triangle-exclamation', 'circle-info',
  'star', 'bookmark', 'eye', 'eye-slash', 'sitemap', 'grip', 'layer-group',
  'database', 'server', 'desktop', 'mobile-screen', 'cloud', 'download',
  'upload', 'link', 'paper-plane', 'envelope', 'comment-dots', 'headset',
  'lightbulb', 'flag', 'trophy', 'heart', 'print', 'share-nodes',
  'right-from-bracket', 'bars', 'bars-staggered', 'ellipsis',
  'chevron-down', 'chevron-right', 'arrow-right', 'arrow-left',
  'id-card', 'address-card', 'building', 'store', 'truck',
  'money-bill', 'wallet', 'credit-card', 'gift', 'ticket',
  'wrench', 'screwdriver-wrench', 'microchip', 'palette', 'compass',
]

/** FontAwesome Free 品牌图标 */
const fontAwesomeBrandNames = [
  'github', 'gitlab', 'google', 'microsoft', 'apple', 'android', 'linux',
  'windows', 'chrome', 'firefox', 'vuejs', 'node-js', 'python', 'java',
  'docker', 'react', 'npm', 'js', 'html5', 'css3', 'weixin', 'qq',
]

const fontAwesomeLabels: Record<string, string> = {
  house: '首页', gear: '设置', user: '用户', users: '用户组', 'user-gear': '用户管理',
  'shield-halved': '权限', lock: '锁', key: '密钥', 'gauge-high': '仪表盘',
  'chart-bar': '柱状图', 'chart-simple': '趋势', 'chart-pie': '饼图',
  table: '表格', list: '列表', folder: '文件夹', 'folder-open': '文件夹(开)',
  'file-lines': '文档', file: '文件', 'file-image': '图片文件', images: '图片',
  video: '视频', play: '播放', film: '影片', camera: '相机', microphone: '麦克风',
  music: '音乐', 'book-open': '书本', book: '书本', 'clipboard-list': '待办',
  'clipboard-check': '审核', tags: '标签', tag: '标签', bell: '通知',
  calendar: '日历', 'calendar-check': '日程', clock: '时钟', hourglass: '等待',
  'magnifying-glass': '搜索', plus: '新增', minus: '减少', pen: '编辑',
  trash: '删除', 'arrows-rotate': '刷新', 'circle-check': '成功',
  'circle-xmark': '关闭', 'triangle-exclamation': '警告', 'circle-info': '信息',
  star: '星标', bookmark: '收藏', eye: '查看', 'eye-slash': '隐藏',
  sitemap: '站点', grip: '拖拽', 'layer-group': '图层', database: '数据库',
  server: '服务器', desktop: '桌面', 'mobile-screen': '移动端', cloud: '云',
  download: '下载', upload: '上传', link: '链接', 'paper-plane': '发送',
  envelope: '邮件', 'comment-dots': '评论', headset: '客服', lightbulb: '灵感',
  flag: '标记', trophy: '奖杯', heart: '收藏', print: '打印', 'share-nodes': '分享',
  'right-from-bracket': '退出', bars: '菜单', 'bars-staggered': '菜单',
  ellipsis: '更多', 'chevron-down': '展开', 'chevron-right': '下一级',
  'arrow-right': '右移', 'arrow-left': '左移', 'id-card': '证件',
  'address-card': '名片', building: '建筑', store: '店铺', truck: '物流',
  'money-bill': '金额', wallet: '钱包', 'credit-card': '银行卡', gift: '礼物',
  ticket: '票券', wrench: '工具', 'screwdriver-wrench': '运维',
  microchip: '芯片', palette: '主题', compass: '导航',
  github: 'GitHub', gitlab: 'GitLab', google: 'Google', microsoft: 'Microsoft',
  apple: 'Apple', android: 'Android', linux: 'Linux', windows: 'Windows',
  chrome: 'Chrome', firefox: 'Firefox', vuejs: 'Vue', 'node-js': 'Node.js',
  python: 'Python', java: 'Java', docker: 'Docker', react: 'React',
  npm: 'npm', js: 'JavaScript', html5: 'HTML5', css3: 'CSS3',
  weixin: '微信', qq: 'QQ',
}

/**
 * 阿里 iconfont 常用 symbol 名。
 * 实际字形取决于 ICONFONT_CSS_URLS 指向的项目字体， symbol 名可在 iconfont.cn 项目中复制。
 */
const iconfontSymbolNames = [
  'home', 'user', 'users', 'setting', 'system', 'menu', 'search', 'video',
  'play', 'folder', 'file', 'picture', 'edit', 'delete', 'plus', 'minus',
  'close', 'check', 'warning', 'info', 'bell', 'calendar', 'clock', 'chart',
  'tag', 'lock', 'key', 'shield', 'cloud', 'download', 'upload', 'link',
  'message', 'phone', 'mail', 'location', 'star', 'heart', 'eye', 'refresh',
  'help', 'customer-service', 'shopping-cart', 'money', 'wallet', 'card',
  'trash', 'password', 'audit', 'dashboard', 'database', 'tools', 'list',
  'grid', 'more', 'back', 'forward', 'fullscreen', 'compass', 'flag',
  'trophy', 'gift', 'music', 'camera', 'mic', 'print', 'save', 'copy',
  'filter', 'sort', 'zoom-in', 'zoom-out', 'logout', 'login', 'user-add',
  'user-del', 'department', 'role', 'permission', 'notice', 'dict', 'config',
  'log', 'backup',
]

const iconfontLabels: Record<string, string> = {
  home: '首页', user: '用户', users: '用户组', setting: '设置', system: '系统',
  menu: '菜单', search: '搜索', video: '视频', play: '播放', folder: '文件夹',
  file: '文件', picture: '图片', edit: '编辑', delete: '删除', plus: '新增',
  minus: '减少', close: '关闭', check: '成功', warning: '警告', info: '信息',
  bell: '通知', calendar: '日历', clock: '时钟', chart: '图表', tag: '标签',
  lock: '锁', key: '密钥', shield: '权限', cloud: '云', download: '下载',
  upload: '上传', link: '链接', message: '消息', phone: '电话', mail: '邮件',
  location: '定位', star: '星标', heart: '收藏', eye: '查看', refresh: '刷新',
  help: '帮助', 'customer-service': '客服', 'shopping-cart': '购物车',
  money: '金额', wallet: '钱包', card: '银行卡', trash: '回收站',
  password: '密码', audit: '审核', dashboard: '仪表盘', database: '数据库',
  tools: '工具', list: '列表', grid: '网格', more: '更多', back: '返回',
  forward: '前进', fullscreen: '全屏', compass: '导航', flag: '标记',
  trophy: '奖杯', gift: '礼物', music: '音乐', camera: '相机', mic: '麦克风',
  print: '打印', save: '保存', copy: '复制', filter: '筛选', sort: '排序',
  'zoom-in': '放大', 'zoom-out': '缩小', logout: '退出', login: '登录',
  'user-add': '新增用户', 'user-del': '删除用户', department: '部门',
  role: '角色', permission: '权限', notice: '通知', dict: '字典',
  config: '参数', log: '日志', backup: '备份',
}

const makeItems = (
  names: string[],
  labels: Record<string, string> = {},
  toValue: (name: string) => string = name => name,
): IconListItem[] => names.map(name => ({
  label: labels[name] ? `${labels[name]} · ${name}` : name,
  value: toValue(name),
  size: 20,
}))

const elementItems = makeItems(elementIconNames, elementIconLabels, toTvueIconName)
const fontAwesomeItems = makeItems(fontAwesomeSolidNames, fontAwesomeLabels, name => `fa-solid fa-${name}`)
const fontAwesomeBrandItems = makeItems(fontAwesomeBrandNames, fontAwesomeLabels, name => `fa-brands fa-${name}`)
const iconfontItems = makeItems(iconfontSymbolNames, iconfontLabels, name => `iconfont icon-${name}`)

/** 供 tvue-input-icon 使用的分组图标列表 */
export const iconList: IconListTab[] = [
  {
    label: '常用',
    prop: 'common',
    list: [
      ...makeItems(['HomeFilled', 'Setting', 'User', 'Menu', 'Grid', 'Document', 'Tickets',
        'Bell', 'VideoCamera', 'PriceTag', 'Odometer', 'Search'], elementIconLabels, toTvueIconName),
      ...makeItems(['house', 'gear', 'user', 'users', 'sitemap', 'video', 'tags',
        'bell', 'gauge-high', 'magnifying-glass'], fontAwesomeLabels, name => `fa-solid fa-${name}`),
      ...makeItems(['home', 'user', 'setting', 'system', 'menu', 'video', 'audit',
        'dashboard', 'database', 'notice'], iconfontLabels, name => `iconfont icon-${name}`),
    ],
  },
  { label: 'Element Plus', prop: 'element', list: elementItems },
  { label: 'FontAwesome', prop: 'fontawesome', list: fontAwesomeItems },
  { label: 'FA 品牌', prop: 'fontawesome-brands', list: fontAwesomeBrandItems },
  { label: '阿里图标', prop: 'iconfont', list: iconfontItems },
]

/**
 * 存量菜单图标值多为 FontAwesome 风格短名（gear / user / video ...），
 * 未显式带 fa- / iconfont 前缀时仍映射到相近的 Element Plus 图标，保证旧数据可显示。
 */
const legacyIconMap: Record<string, string> = {
  gear: 'Setting', cog: 'Setting', user: 'User', users: 'UserFilled',
  shield: 'Lock', 'shield-halved': 'Lock', 'user-shield': 'Lock',
  bars: 'Menu', 'bars-staggered': 'Menu', sitemap: 'Grid',
  'id-card': 'Postcard', 'address-card': 'Postcard', book: 'Document',
  'book-open': 'Reading', sliders: 'Operation', bell: 'Bell',
  'file-lines': 'Document', file: 'Document', list: 'Tickets',
  'right-to-bracket': 'SwitchButton', 'triangle-exclamation': 'Warning',
  'folder-open': 'FolderOpened', folder: 'Folder', video: 'VideoCamera',
  'clipboard-check': 'DocumentChecked', tags: 'PriceTag', tag: 'PriceTag',
  gauge: 'Odometer', chart: 'DataAnalysis', 'chart-bar': 'Histogram',
}

/**
 * 把任意图标值归一成 tvue icon-temp 可识别的值：
 * - `#icon-xxx` / 含空格的 class 串：规整空白后原样保留
 * - `fa-xxx` 单类：补成 `fa-solid fa-xxx`
 * - `icon-xxx` 单类：补成 `iconfont icon-xxx`
 * - `el-icon-xxx`：原样返回
 * - 存量短名：命中映射后转 Element Plus 组件名
 */
export const normalizeIcon = (value: unknown): string => {
  const raw = String(value ?? '').trim().replace(/\s+/g, ' ')
  if (!raw) return ''
  if (raw.startsWith('#') || raw.startsWith('el-icon-')) return raw
  if (raw.includes(' ')) return raw
  if (raw.startsWith('fa-')) return `fa-solid ${raw}`
  if (raw.startsWith('icon-')) return `iconfont ${raw}`
  const mapped = legacyIconMap[raw] || legacyIconMap[raw.replace(/-/g, '')]
  if (mapped) return toTvueIconName(mapped)
  // 未知短横线小写值不再当成组件名，避免 <component :is> 解析失败
  if (/^[a-z][a-z0-9-]*$/.test(raw)) return ''
  return toTvueIconName(raw)
}

export type ResolvedIcon =
  | { kind: 'el'; value: string }
  | { kind: 'svg'; value: string }
  | { kind: 'font'; value: string }
  | { kind: 'none'; value: '' }

/** 判断图标值应采用哪种渲染方式，供侧边栏和表格预览共用 */
export const resolveIcon = (value: unknown): ResolvedIcon => {
  const normalized = normalizeIcon(value)
  if (!normalized) return { kind: 'none', value: '' }
  if (normalized.startsWith('#')) return { kind: 'svg', value: normalized }
  if (normalized.startsWith('el-icon-')) return { kind: 'el', value: normalized }
  return { kind: 'font', value: normalized }
}

/** 兼容旧调用：仅返回 Element Plus 组件名，非 Element Plus 图标返回空串 */
export const iconComponentName = (value: unknown): string => {
  const icon = resolveIcon(value)
  return icon.kind === 'el' ? icon.value : ''
}
