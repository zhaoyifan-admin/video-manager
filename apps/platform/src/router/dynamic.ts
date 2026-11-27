import { markRaw, type Component } from 'vue'
import type { RouteRecordRaw, Router } from 'vue-router'
import SystemPlaceholder from '../views/system/SystemPlaceholder.vue'
import UserManagePage from '../views/system/UserManagePage.vue'
import RoleManagePage from '../views/system/RoleManagePage.vue'
import MenuManagePage from '../views/system/MenuManagePage.vue'
import DeptManagePage from '../views/system/DeptManagePage.vue'
import PostManagePage from '../views/system/PostManagePage.vue'
import DictManagePage from '../views/system/DictManagePage.vue'
import ConfigManagePage from '../views/system/ConfigManagePage.vue'
import NoticeManagePage from '../views/system/NoticeManagePage.vue'
import NoticeCenterPage from '../views/system/NoticeCenterPage.vue'
import OperationLogPage from '../views/system/OperationLogPage.vue'
import LoginLogPage from '../views/system/LoginLogPage.vue'
import ExceptionLogPage from '../views/system/ExceptionLogPage.vue'
import VideoAuditPage from '../views/system/VideoAuditPage.vue'
import TaxonomyManagePage from '../views/system/TaxonomyManagePage.vue'
import VideoSiteManagePage from '../views/system/VideoSiteManagePage.vue'
import NotFound from '../views/error/NotFound.vue'
import { getSystemMenus } from '../api'
import { useAuthStore } from '../stores/auth'
import type { CurrentUser, MenuNode } from '@video-manager/shared'
import { setDefaultConsolePath, resetDefaultConsolePath } from './static'

// 动态路由：由后端 /api/system/menus 返回的菜单树生成，挂载在 console 下。
const DYNAMIC_PREFIX = 'console-dynamic-'
const componentMap: Record<string, Component> = {
  SystemPlaceholder: markRaw(SystemPlaceholder),
  UserManagePage: markRaw(UserManagePage),
  RoleManagePage: markRaw(RoleManagePage),
  MenuManagePage: markRaw(MenuManagePage),
  DeptManagePage: markRaw(DeptManagePage),
  PostManagePage: markRaw(PostManagePage),
  DictManagePage: markRaw(DictManagePage),
  ConfigManagePage: markRaw(ConfigManagePage),
  NoticeManagePage: markRaw(NoticeManagePage),
  NoticeCenterPage: markRaw(NoticeCenterPage),
  OperationLogPage: markRaw(OperationLogPage),
  LoginLogPage: markRaw(LoginLogPage),
  ExceptionLogPage: markRaw(ExceptionLogPage),
  VideoAuditPage: markRaw(VideoAuditPage),
  TaxonomyManagePage: markRaw(TaxonomyManagePage),
  VideoSiteManagePage: markRaw(VideoSiteManagePage),
}

interface DynamicEntry {
  node: MenuNode
  path: string
  absolutePath: string
  name: string
  component: Component
  meta: {
    title: string
    permission?: string
    cache: boolean
    icon?: string
  }
}

let dynamicRouteNames: string[] = []
let routesSignature = ''

// 权限码判断：无权限码放行；管理员的 '*' 通配；否则精确匹配。
export const hasPermission = (user: CurrentUser | null, code?: string): boolean => {
  if (!code) return true
  const permissions = user?.permissions || []
  return permissions.includes('*') || permissions.includes(code)
}

// 收集所有带路径的菜单节点：DIR（目录）也要生成路由，否则目录路径会落进 404。
const collectMenuRoutes = (nodes: MenuNode[] | undefined, output: DynamicEntry[] = []): DynamicEntry[] => {
  for (const node of nodes || []) {
    if (node.path) {
      output.push({
        node,
        path: node.path.replace(/^\/console\/?/, '') || 'index',
        absolutePath: node.path,
        name: `${DYNAMIC_PREFIX}${node.code}`,
        component: componentMap[node.componentKey || ''] || SystemPlaceholder,
        meta: {
          title: node.title,
          permission: node.permission,
          cache: Boolean(node.cache),
          icon: node.icon,
        },
      })
    }
    if (node.children?.length) collectMenuRoutes(node.children, output)
  }
  return output
}

// 目录 redirect：取其下第一个有权限的菜单；visibleByCode 已过滤过权限。
const firstVisibleMenu = (
  entry: DynamicEntry,
  visibleByCode: Map<string, DynamicEntry>,
  visited = new Set<string>(),
): DynamicEntry | null => {
  if (visited.has(entry.node.code)) return null
  visited.add(entry.node.code)
  if (entry.node.type === 'MENU') return entry
  for (const child of entry.node.children || []) {
    const childEntry = visibleByCode.get(child.code)
    if (!childEntry) continue
    const hit = firstVisibleMenu(childEntry, visibleByCode, visited)
    if (hit) return hit
  }
  return null
}

// 按当前用户与后端菜单同步动态路由；签名未变时跳过，避免重复 addRoute。
export const syncConsoleRoutes = async (router: Router, user: CurrentUser | null): Promise<boolean> => {
  let menus: MenuNode[] = []
  try {
    menus = (await getSystemMenus())?.items || []
  } catch {
    menus = []
  }
  useAuthStore().setMenus(menus)

  const targetRoutes = collectMenuRoutes(menus)
  const visibleRoutes = targetRoutes.filter((item) => hasPermission(user, item.meta.permission))
  const signature = JSON.stringify({
    id: user?.id,
    routes: visibleRoutes.map((item) => item.name),
    permissions: user?.permissions || [],
  })
  if (signature === routesSignature) return false

  for (const name of dynamicRouteNames) router.removeRoute(name)
  dynamicRouteNames = []

  const visibleByCode = new Map(visibleRoutes.map((item) => [item.node.code, item]))
  for (const item of visibleRoutes) {
    const route: RouteRecordRaw = item.node.type === 'DIR'
      ? {
          path: item.path,
          name: item.name,
          meta: item.meta,
          redirect: firstVisibleMenu(item, visibleByCode)?.absolutePath || '/403',
        }
      : {
          path: item.path,
          name: item.name,
          meta: item.meta,
          component: item.component,
        }
    router.addRoute('console', route)
    dynamicRouteNames.push(item.name)
  }

  const firstTop = visibleRoutes.find((item) => !item.node.parentId && item.node.type === 'DIR')
    || visibleRoutes.find((item) => !item.node.parentId)
  const landing = firstTop ? firstVisibleMenu(firstTop, visibleByCode) : null
  setDefaultConsolePath(landing?.absolutePath)

  // console 内兜底必须在动态路由之后注册，否则通配路由会抢占具体菜单路径。
  router.addRoute('console', {
    path: ':pathMatch(.*)*',
    name: `${DYNAMIC_PREFIX}fallback`,
    component: NotFound,
    meta: { title: '页面不存在' },
  })
  dynamicRouteNames.push(`${DYNAMIC_PREFIX}fallback`)
  routesSignature = signature
  return true
}

// 退出登录或登录过期时清空动态路由，防止下个账号看到上个账号的菜单。
export const resetDynamicRoutes = (router: Router): void => {
  for (const name of dynamicRouteNames) router.removeRoute(name)
  dynamicRouteNames = []
  routesSignature = ''
  resetDefaultConsolePath()
}
