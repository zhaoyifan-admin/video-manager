import { createApp, h } from 'vue'
import { createRouter, createWebHistory, RouterView } from 'vue-router'
import './theme.css'
import App from './App.vue'
import PlayerPage from './PlayerPage.vue'
import DetailPage from './DetailPage.vue'
import LoginPage from './LoginPage.vue'
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
  ],
})

// 全局路由守卫：除登录页外都要先确认登录态
router.beforeEach(async (to) => {
  if (to.name === 'login') return true
  const user = await ensureLoaded()
  if (!user) {
    return { name: 'login', query: { redirect: to.fullPath } } // 登录后跳回原目标页
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
