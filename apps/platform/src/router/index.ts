import { createRouter, createWebHistory, type RouteLocationNormalized } from 'vue-router'
import { staticRoutes, globalFallbackRoute, getDefaultConsolePath } from './static'
import { hasPermission, syncConsoleRoutes, resetDynamicRoutes } from './dynamic'
import { useAuthStore } from '../stores/auth'
import { setUnauthorizedHandler } from '../api'

const router = createRouter({
  history: createWebHistory(),
  routes: staticRoutes,
})

// 全局兜底；console 内的 404 在动态菜单同步后注册，避免通配路由抢占具体菜单。
router.addRoute(globalFallbackRoute)

router.beforeEach(async (to: RouteLocationNormalized) => {
  const auth = useAuthStore()
  const user = await auth.ensureLoaded()
  const isPublic = to.meta?.public === true

  if (to.name === 'login') {
    return user ? { name: 'console' } : true
  }
  if (!user && !isPublic) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (user && to.path.startsWith('/console')) {
    const firstPass = await syncConsoleRoutes(router, user)
    // /console 根路径：菜单同步完成后再决定落点，避免解析期 redirect 读到旧值。
    if (to.name === 'console') {
      return { path: getDefaultConsolePath(), replace: true }
    }
    // 动态路由在守卫内注入，必须用完整路径重新导航一次才能命中。
    if (firstPass && to.name === 'not-found-catch-all') {
      return { path: to.path, query: to.query, hash: to.hash, replace: true }
    }
    if (!hasPermission(user, to.meta.permission as string | undefined)) {
      return { name: 'forbidden', query: { redirect: to.fullPath } }
    }
  }
  return true
})

setUnauthorizedHandler(() => {
  const auth = useAuthStore()
  auth.resetAuth()
  resetDynamicRoutes(router)
  if (router.currentRoute.value.name !== 'login') {
    router.push({ name: 'login' })
  }
})

export default router
