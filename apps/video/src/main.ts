import { createApp, h } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory, RouterView, type RouteRecordRaw } from 'vue-router'
// Font Awesome 6 免费版：基础样式 + solid / regular 两套字形，本地依赖离线可用。
// 项目没有用到 brands 品牌图标，刻意不引 all.min.css，避免多打包 300KB+ 无用字体。
import '@fortawesome/fontawesome-free/css/fontawesome.min.css'
import '@fortawesome/fontawesome-free/css/solid.min.css'
import '@fortawesome/fontawesome-free/css/regular.min.css'
import './theme.css'
import App from './App.vue'
import PlayerPage from './PlayerPage.vue'
import DetailPage from './DetailPage.vue'
import LoginPage from './LoginPage.vue'
import MySubmissionsPage from './MySubmissionsPage.vue'
import GlobalFeedback from './ui/GlobalFeedback.vue'
import { vLazyCover } from './composables/useCover'
import { useAuthStore } from './stores/auth'
import { useThemeStore } from './stores/theme'
import { setUnauthorizedHandler } from './api'

// 视频子系统挂载在管理平台的 /video/ 下；独立开发时 vite 也按该 base 提供资源。
const routes: RouteRecordRaw[] = [
  { path: '/', name: 'list', component: App }, // 视频列表页
  { path: '/login', name: 'login', component: LoginPage }, // 登录 / 注册页（子系统直连兜底）
  { path: '/detail/:id', name: 'detail', component: DetailPage }, // 影片详情页
  { path: '/play/:id', name: 'play', component: PlayerPage }, // 独立播放页
  { path: '/my-submissions', name: 'mySubmissions', component: MySubmissionsPage }, // 审核结果页（日常必需）
  // 审核中心 / 站点管理 / 分类管理已搬移至主系统控制台（/console/video-mgmt/*）。
]

const router = createRouter({
  history: createWebHistory('/video/'),
  routes,
})

// 全局路由守卫：先确认登录态，再按页面权限放行
router.beforeEach(async (to) => {
  const user = await useAuthStore().ensureLoaded()
  if (to.name === 'login') {
    return user ? { name: 'list' } : true
  }
  if (!user) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  return true
})

// 任意接口返回 401（登录过期）：清空登录态并回到登录页
setUnauthorizedHandler(() => {
  useAuthStore().resetAuth()
  if (router.currentRoute.value.name !== 'login') {
    void router.push({ name: 'login' })
  }
})

// 根组件：路由视图 + 全局 Toast / 确认框（全部手写，无 UI 框架）
const app = createApp({
  render: () => [h(RouterView), h(GlobalFeedback)],
})

const pinia = createPinia()
app.use(pinia)
app.use(router)
app.directive('lazy-cover', vLazyCover) // 卡片懒截帧指令（VideoCard 使用）

// 首屏渲染前落定主题，避免深色 → 浅色的闪屏
useThemeStore().initTheme()

app.mount('#app')
