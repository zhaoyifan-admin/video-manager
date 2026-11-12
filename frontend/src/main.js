import { createApp, h } from 'vue'
import { createRouter, createWebHistory, RouterView } from 'vue-router'
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
import AuditCenterPage from './AuditCenterPage.vue'
import MySubmissionsPage from './MySubmissionsPage.vue'
import AdminPage from './AdminPage.vue'
import GlobalFeedback from './ui/GlobalFeedback.vue'
import { vLazyCover } from './composables/useCover'
import { ensureLoaded, resetAuth } from './composables/useAuth'
import { setUnauthorizedHandler } from './api'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'list', component: App }, // 视频列表页
    { path: '/login', name: 'login', component: LoginPage }, // 登录 / 注册页
    { path: '/detail/:id', name: 'detail', component: DetailPage }, // 影片详情页
    { path: '/play/:id', name: 'play', component: PlayerPage }, // 独立播放页
    { path: '/audit', name: 'audit', component: AuditCenterPage }, // 审核中心页（超管 / 审核员）
    { path: '/my-submissions', name: 'mySubmissions', component: MySubmissionsPage }, // 我的提交（审核结果）页
    { path: '/admin', name: 'admin', component: AdminPage }, // 站点管理（仅超管：看板 / 用户 / 存储 / 合集）
  ],
})

// 全局路由守卫：先确认登录态，再按页面权限放行
router.beforeEach(async (to) => {
  const user = await ensureLoaded()
  // 已登录访问登录页：拦截并送回列表页（防止后退/直达又看到登录表单）
  if (to.name === 'login') {
    return user ? { name: 'list' } : true
  }
  if (!user) {
    return { name: 'login', query: { redirect: to.fullPath } } // 登录后跳回原目标页
  }
  // 审核中心：超管、管理员或独立审核员可进；站点管理：仅超管
  if (to.name === 'audit' && !['admin', 'reviewer', 'manager'].includes(user.role)) {
    return { name: 'list' }
  }
  if (to.name === 'admin' && user.role !== 'admin') {
    return { name: 'list' }
  }
})

// 任意接口返回 401（登录过期）：清空登录态并回到登录页
setUnauthorizedHandler(() => {
  resetAuth()
  if (router.currentRoute.value.name !== 'login') {
    router.push({ name: 'login' })
  }
})

// 根组件：路由视图 + 全局 Toast / 确认框（全部手写，无 UI 框架）
createApp({
  render: () => [h(RouterView), h(GlobalFeedback)],
})
  .use(router)
  .directive('lazy-cover', vLazyCover) // 卡片懒截帧指令（VideoCard 使用）
  .mount('#app')
