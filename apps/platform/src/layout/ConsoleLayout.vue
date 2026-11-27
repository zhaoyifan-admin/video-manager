<template>
  <!-- 左侧导航 / 左侧混合 -->
  <el-container v-if="!theme.isHorizontalLayout" class="console-shell" style="height: 100vh">
    <el-aside :width="asideWidth" class="console-aside flex flex-col">
      <div class="aside-logo" :class="{ 'aside-logo--compact': compactAside }">
        <AppLogo :compact="compactAside" @click="goHome" />
      </div>
      <AppMenu
        class="aside-menu"
        :menus="primaryMenus"
        :mode="'vertical'"
        :collapse="compactAside"
        :primary-only="theme.isMixLayout"
        :active-path="route.path"
        :active-index="activePrimaryCode"
        :accordion="theme.menuAccordion"
        @select="onPrimarySelect"
      />
      <button
        v-if="!theme.isMixLayout && theme.sidebarCollapsedButton"
        class="aside-collapse"
        :title="theme.sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'"
        @click="theme.setPreference('sidebarCollapsed', !theme.sidebarCollapsed)"
      >
        <el-icon><component :is="theme.sidebarCollapsed ? Expand : Fold" /></el-icon>
      </button>
      <div v-if="!theme.isMixLayout && !theme.sidebarCollapsed" class="aside-note">视频系统 · 子系统模式</div>
    </el-aside>

    <el-aside
      v-if="theme.isMixLayout"
      :width="`${theme.secondaryWidth}px`"
      class="console-aside console-aside--secondary flex flex-col"
    >
      <div class="sub-menu-title">{{ activePrimaryTitle }}</div>
      <AppMenu
        class="aside-menu"
        :menus="secondaryMenus"
        :active-path="route.path"
        :accordion="theme.menuAccordion"
        @select="onMenuSelect"
      />
    </el-aside>

    <el-container class="flex-1">
      <el-header v-if="theme.showHeader" class="console-header flex items-center justify-between">
        <div class="flex items-center gap-2">
          <el-button v-if="theme.widgetSettings" text title="偏好设置" @click="settingsVisible = true">
            <el-icon><Setting /></el-icon>
          </el-button>
          <HeaderBreadcrumb
            v-if="showBreadcrumb"
            :crumbs="breadcrumbs"
            :show-icon="theme.breadcrumbIcon"
            :fallback="String(route.meta.title || '管理控制台')"
          />
        </div>
        <HeaderTools @open-settings="settingsVisible = true" />
      </el-header>
      <div v-else class="console-noheader-tools flex items-center justify-end">
        <HeaderTools @open-settings="settingsVisible = true" />
      </div>
      <GlobalTab v-if="theme.showTabs" @navigate="navigate" />
      <el-main class="console-main">
        <router-view v-slot="{ Component, route: current }">
          <transition :name="transitionName" mode="out-in">
            <keep-alive v-if="current.meta.cache">
              <component :is="Component" :key="current.path" />
            </keep-alive>
            <component v-else :is="Component" :key="current.path" />
          </transition>
        </router-view>
      </el-main>
      <el-footer v-if="theme.showFooter" class="console-footer">视频管理系统 · Vben 风格偏好设置</el-footer>
    </el-container>

    <div v-if="theme.transitionProgress && progressVisible" class="route-progress" />
    <div v-if="theme.watermark" class="console-watermark">{{ watermarkText }}</div>
  </el-container>

  <!-- 顶部导航 / 顶部混合 -->
  <el-container v-else class="console-shell" direction="vertical" style="height: 100vh; overflow: hidden">
    <el-header class="console-header console-header--horizontal flex items-center">
      <div
        class="horizontal-logo"
        :class="{ 'horizontal-logo--mix': theme.isMixLayout }"
        :style="theme.isMixLayout ? { width: `${theme.secondaryWidth}px` } : undefined"
      >
        <AppLogo @click="goHome" />
      </div>
      <AppMenu
        class="horizontal-menu"
        :menus="primaryMenus"
        :mode="'horizontal'"
        :primary-only="theme.isMixLayout"
        :active-path="route.path"
        :active-index="activePrimaryCode"
        :accordion="theme.menuAccordion"
        @select="onPrimarySelect"
      />
      <HeaderTools @open-settings="settingsVisible = true" />
    </el-header>

    <el-container class="flex-1" style="min-height: 0">
      <el-aside
        v-if="theme.isMixLayout"
        :width="`${theme.secondaryWidth}px`"
        class="console-aside console-aside--secondary flex flex-col"
      >
        <AppMenu
          class="aside-menu"
          :menus="secondaryMenus"
          :active-path="route.path"
          :accordion="theme.menuAccordion"
          @select="onMenuSelect"
        />
      </el-aside>
      <el-container class="flex-1" direction="vertical" style="min-height: 0">
        <div class="console-subheader flex items-center justify-between">
          <HeaderBreadcrumb
            v-if="showBreadcrumb"
            :crumbs="breadcrumbs"
            :show-icon="theme.breadcrumbIcon"
            :fallback="String(route.meta.title || '管理控制台')"
          />
          <el-button
            v-if="theme.widgetSettings"
            text
            title="偏好设置"
            @click="settingsVisible = true"
          ><el-icon><Setting /></el-icon></el-button>
        </div>
        <GlobalTab v-if="theme.showTabs" @navigate="navigate" />
        <el-main class="console-main">
          <router-view v-slot="{ Component, route: current }">
            <transition :name="transitionName" mode="out-in">
              <keep-alive v-if="current.meta.cache">
                <component :is="Component" :key="current.path" />
              </keep-alive>
              <component v-else :is="Component" :key="current.path" />
            </transition>
          </router-view>
        </el-main>
        <el-footer v-if="theme.showFooter" class="console-footer">视频管理系统 · Vben 风格偏好设置</el-footer>
      </el-container>
    </el-container>

    <div v-if="theme.transitionProgress && progressVisible" class="route-progress" />
    <div v-if="theme.watermark" class="console-watermark">{{ watermarkText }}</div>
  </el-container>

  <ThemeDrawer v-model="settingsVisible" />
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Expand, Fold, Setting } from '@element-plus/icons-vue'
import { getSystemMenus } from '../api'
import { useAuthStore } from '../stores/auth'
import { useNoticeStore } from '../stores/notices'
import { useTabsStore } from '../stores/tabs'
import { useThemeStore } from '../stores/theme'
import type { MenuNode } from '@video-manager/shared'
import AppLogo from './components/AppLogo.vue'
import AppMenu from './components/AppMenu.vue'
import GlobalTab from './components/GlobalTab.vue'
import HeaderBreadcrumb from './components/HeaderBreadcrumb.vue'
import HeaderTools from './components/HeaderTools.vue'
import ThemeDrawer from './components/ThemeDrawer.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const theme = useThemeStore()
const notices = useNoticeStore()
const tabs = useTabsStore()
const settingsVisible = ref(false)
const activePrimaryCode = ref('')
const progressVisible = ref(false)
let progressTimer = 0

const menus = computed(() => auth.menus)
const compactAside = computed(() => theme.isMixLayout || theme.sidebarCollapsed)
const asideWidth = computed(() => theme.isMixLayout
  ? `${theme.mixedWidth}px`
  : `${theme.sidebarCollapsed ? 64 : theme.sidebarWidth}px`)
const transitionName = computed(() => theme.transitionEnable ? theme.transitionName : 'none')
const watermarkText = computed(() => {
  const name = auth.user?.username || 'admin'
  return `${name} · ${new Date().toLocaleDateString('zh-CN')}`
})
const primaryMenus = computed(() => menus.value)
const activePrimary = computed(() => findByCode(menus.value, activePrimaryCode.value))
const activePrimaryTitle = computed(() => activePrimary.value?.title || '菜单')
const secondaryMenus = computed(() => activePrimary.value?.children || [])

const loadMenus = async (): Promise<void> => {
  try {
    const data = await getSystemMenus()
    auth.setMenus(data?.items || [])
  } catch {
    auth.setMenus([])
  }
}

const findByPath = (nodes: MenuNode[] | undefined, path: string): MenuNode | null => {
  for (const node of nodes || []) {
    if (node.path === path) return node
    const hit = findByPath(node.children, path)
    if (hit) return hit
  }
  return null
}
const findByCode = (nodes: MenuNode[] | undefined, code: string): MenuNode | null => {
  for (const node of nodes || []) {
    if (node.code === code) return node
    const hit = findByCode(node.children, code)
    if (hit) return hit
  }
  return null
}
const primaryOf = (nodes: MenuNode[] | undefined, path: string, parent: MenuNode | null = null): MenuNode | null => {
  for (const node of nodes || []) {
    if (node.path === path) return parent || node
    const hit = primaryOf(node.children, path, parent || node)
    if (hit) return hit
  }
  return null
}
const firstMenuPath = (nodes: MenuNode[] | undefined): string => {
  for (const node of nodes || []) {
    if (node.type === 'MENU' && node.path) return node.path
    const hit = firstMenuPath(node.children)
    if (hit) return hit
  }
  return ''
}

const findCrumbs = (nodes: MenuNode[] | undefined, path: string, trail: MenuNode[] = []): MenuNode[] | null => {
  for (const node of nodes || []) {
    const chain = [...trail, node]
    if (node.path === path) return chain
    const hit = findCrumbs(node.children, path, chain)
    if (hit) return hit
  }
  return null
}
const breadcrumbs = computed(() => {
  const hit = findCrumbs(menus.value, route.path)
  const source = hit?.length
    ? hit
    : (route.meta.title ? [{ code: 'current', title: String(route.meta.title), icon: '' }] : [])
  return source.map(item => ({ code: item.code, title: item.title, icon: item.icon }))
})
const showBreadcrumb = computed(() =>
  theme.showBreadcrumb && !(theme.hideBreadcrumbOne && breadcrumbs.value.length <= 1),
)

const navigate = (path: string): void => { void router.push(path) }
const goHome = (): void => navigate(tabs.homePath || firstMenuPath(menus.value) || '/console')

const openExternal = (node: MenuNode | null): boolean => {
  if (!node?.linkUrl) return false
  window.open(node.linkUrl, '_blank', 'noopener')
  return true
}

const syncPrimaryFromRoute = (): void => {
  if (!theme.isMixLayout) return
  const primary = primaryOf(menus.value, route.path)
  if (primary && primary.code !== activePrimaryCode.value) activePrimaryCode.value = primary.code
}

const onMenuSelect = (index: string): void => {
  const node = findByPath(menus.value, index) || findByCode(menus.value, index)
  if (!node || openExternal(node)) return
  if (node.type === 'DIR') {
    const child = firstMenuPath(node.children)
    if (child) navigate(child)
    return
  }
  if (node.path) navigate(node.path)
}

const onPrimarySelect = (index: string): void => {
  const node = findByCode(menus.value, index) || findByPath(menus.value, index)
  if (!node || openExternal(node)) return
  if (theme.isMixLayout && node.children?.length) {
    activePrimaryCode.value = node.code
    const child = firstMenuPath(node.children)
    if (child) navigate(child)
    return
  }
  onMenuSelect(index)
}

// 路由变化同步标签页、面包屑与混合模式辅栏；menus 变化后补首页固定标签。
watch(
  () => [route.path, menus.value] as const,
  () => {
    const node = findByPath(menus.value, route.path)
    const homePath = firstMenuPath(menus.value)
    if (homePath && !tabs.homePath) {
      const homeNode = findByPath(menus.value, homePath)
      tabs.syncHome({
        path: homePath,
        title: homeNode?.title || '首页',
        icon: homeNode?.icon,
      })
    }
    if (route.path && route.name !== 'login') {
      tabs.addTab({
        path: route.path,
        title: node?.title || String(route.meta.title || '页面'),
        icon: node?.icon || String(route.meta.icon || ''),
      })
      tabs.setActive(route.path)
    }
    syncPrimaryFromRoute()
  },
  { immediate: true, deep: true },
)

// 运行时切换布局模式时路由不变，需要主动同步混合模式的辅栏归属
watch(() => theme.layoutMode, () => {
  if (theme.isMixLayout) syncPrimaryFromRoute()
})

watch(() => route.path, () => { void notices.refresh() })
watch(() => route.path, () => {
  if (!theme.transitionProgress) return
  window.clearTimeout(progressTimer)
  progressVisible.value = false
  requestAnimationFrame(() => { progressVisible.value = true })
  progressTimer = window.setTimeout(() => { progressVisible.value = false }, 700)
})
watch(
  () => [route.meta.title, theme.dynamicTitle] as const,
  () => {
    const title = String(route.meta.title || '管理控制台')
    document.title = theme.dynamicTitle ? `${title} - 管理平台` : '管理平台'
  },
  { immediate: true },
)
watch(() => theme.tabPersist, enabled => { if (!enabled) tabs.clearPersisted() })

onMounted(() => {
  tabs.loadPersisted()
  loadMenus()
  void notices.refresh()
})
</script>

<style scoped>
.aside-logo {
  height: var(--nf-header-height);
  display: flex;
  align-items: center;
  border-bottom: 1px solid var(--nf-border);
  flex: 0 0 auto;
}
.aside-logo--compact { justify-content: center; }
.aside-menu { flex: 1; min-height: 0; overflow-y: auto; border-right: none; }
.aside-note { padding: 12px 16px; font-size: var(--nf-font-xs); color: var(--nf-text-muted); }
.aside-collapse {
  flex: 0 0 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-top: 1px solid var(--nf-border);
  background: transparent;
  color: var(--nf-text-muted);
  cursor: pointer;
}
.aside-collapse:hover { color: var(--el-color-primary); }
.console-aside--secondary { border-right: 1px solid var(--nf-border); }
.sub-menu-title {
  height: var(--nf-header-height);
  display: flex;
  align-items: center;
  padding: 0 16px;
  border-bottom: 1px solid var(--nf-border);
  font-size: var(--nf-font-base);
  font-weight: 600;
  color: var(--nf-text-primary);
}
.console-header--horizontal { gap: 12px; }
.horizontal-logo { flex: 0 0 auto; height: 100%; display: flex; align-items: center; border-right: 1px solid var(--nf-border); margin-left: -20px; padding-left: 20px; }
.horizontal-menu { flex: 1; min-width: 0; height: 100%; border-bottom: none; }
.console-subheader { height: var(--nf-subheader-height); padding: 0 16px; border-bottom: 1px solid var(--nf-border); background: var(--nf-bg-card); }
.console-footer { height: 36px; display: flex; align-items: center; justify-content: center; border-top: 1px solid var(--nf-border); color: var(--nf-text-muted); font-size: var(--nf-font-xs); }
.console-noheader-tools { height: 44px; padding: 0 16px; border-bottom: 1px solid var(--nf-border); background: var(--nf-bg-elevated); }
.route-progress {
  position: fixed;
  top: 0;
  left: 0;
  z-index: 4000;
  height: 2px;
  background: var(--el-color-primary);
  animation: pref-progress 0.7s ease-out forwards;
}
@keyframes pref-progress {
  from { width: 0; opacity: 1; }
  to { width: 100%; opacity: 0; }
}
.console-watermark {
  position: fixed;
  inset: 0;
  z-index: 900;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  font-size: var(--nf-font-xl);
  color: var(--nf-text-muted);
  opacity: 0.14;
  transform: rotate(-24deg);
  user-select: none;
}
</style>
