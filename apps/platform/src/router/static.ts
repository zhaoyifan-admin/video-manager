import type { RouteRecordRaw } from 'vue-router'
import LoginPage from '../LoginPage.vue'
import ConsoleLayout from '../layout/ConsoleLayout.vue'
import Forbidden from '../views/error/Forbidden.vue'
import NotFound from '../views/error/NotFound.vue'
import ConsoleUnavailable from '../views/error/ConsoleUnavailable.vue'

// 静态路由：与应用一起注册，不依赖后端返回；public 表示未登录也可访问。
export const CONSOLE_EMPTY_PATH = '/console/unavailable'

let defaultConsolePath = CONSOLE_EMPTY_PATH
export const setDefaultConsolePath = (path?: string): void => {
  defaultConsolePath = path || CONSOLE_EMPTY_PATH
}
export const resetDefaultConsolePath = (): void => {
  defaultConsolePath = CONSOLE_EMPTY_PATH
}
export const getDefaultConsolePath = (): string => defaultConsolePath

export const staticRoutes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/console',
  },
  {
    path: '/login',
    name: 'login',
    component: LoginPage,
    meta: { title: '登录', public: true },
  },
  {
    path: '/console',
    name: 'console',
    component: ConsoleLayout,
    // 落点不在解析期硬编码：redirect 先于守卫执行，此时动态菜单尚未同步。
    meta: { title: '管理控制台' },
    children: [
      {
        path: 'unavailable',
        name: 'console-unavailable',
        component: ConsoleUnavailable,
        meta: { title: '暂无可用模块' },
      },
    ],
  },
  {
    path: '/403',
    name: 'forbidden',
    component: Forbidden,
    meta: { title: '无权限', public: true },
  },
  {
    path: '/404',
    name: 'not-found',
    component: NotFound,
    meta: { title: '页面不存在', public: true },
  },
]

// 全局兜底：所有未定义路径统一落到 404。
export const globalFallbackRoute: RouteRecordRaw = {
  path: '/:pathMatch(.*)*',
  name: 'not-found-catch-all',
  component: NotFound,
  meta: { title: '页面不存在', public: true },
}
