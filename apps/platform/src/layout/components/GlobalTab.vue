<template>
  <div v-if="tabs.count" :class="['global-tab', `global-tab--${theme.tabbarStyle}`]">
    <el-icon class="tab-scroll-btn" @click="scrollPrev"><ArrowLeft /></el-icon>
    <div ref="listRef" class="tab-list" @wheel="onWheel">
      <template v-if="theme.tabbarStyle === 'chrome'">
        <div
          v-for="(tab, index) in tabs.tabs"
          :key="tab.path"
          class="tab-item tab-item--chrome"
          :class="{ active: tab.path === tabs.activePath }"
          @click="activate(tab.path)"
          @contextmenu.prevent="openContext($event, tab.path)"
          @auxclick="(event: MouseEvent) => onAuxClick(event, tab.path)"
        >
          <div class="tab-chrome">
            <span v-if="index > 0 && tab.path !== tabs.activePath" class="tab-chrome-divider" />
            <div class="tab-chrome-bg">
              <div class="tab-chrome-bg-content" />
              <svg class="tab-chrome-bg-before" width="7" height="7" viewBox="0 0 7 7">
                <path d="M 0 7 A 7 7 0 0 0 7 0 L 7 7 Z" />
              </svg>
              <svg class="tab-chrome-bg-after" width="7" height="7" viewBox="0 0 7 7">
                <path d="M 0 0 A 7 7 0 0 0 7 7 L 0 7 Z" />
              </svg>
            </div>
            <div class="tab-chrome-extra">
              <el-icon v-if="!tab.fixed" class="tab-close" @click.stop="close(tab.path)"><Close /></el-icon>
            </div>
            <div class="tab-chrome-main">
              <AppIcon v-if="theme.showTabIcon && tab.icon" :name="tab.icon" :size="14" class="tab-icon" />
              <span class="tab-title">{{ tab.title }}</span>
            </div>
          </div>
        </div>
      </template>
      <template v-else>
        <div
          v-for="tab in tabs.tabs"
          :key="tab.path"
          class="tab-item"
          :class="{ active: tab.path === tabs.activePath }"
          @click="activate(tab.path)"
          @contextmenu.prevent="openContext($event, tab.path)"
          @auxclick="(event: MouseEvent) => onAuxClick(event, tab.path)"
        >
          <AppIcon v-if="theme.showTabIcon && tab.icon" :name="tab.icon" :size="14" class="tab-icon" />
          <span class="tab-title">{{ tab.title }}</span>
          <el-icon v-if="!tab.fixed" class="tab-close" @click.stop="close(tab.path)"><Close /></el-icon>
        </div>
      </template>
    </div>
    <el-icon class="tab-scroll-btn" @click="scrollNext"><ArrowRight /></el-icon>
    <el-dropdown trigger="click" @command="handleCommand">
      <el-icon class="tab-more"><MoreFilled /></el-icon>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item command="closeAll">关闭全部</el-dropdown-item>
          <el-dropdown-item command="closeOthers">关闭其他</el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>

    <teleport to="body">
      <ul
        v-if="context.visible"
        class="tab-context"
        :style="{ left: `${context.left}px`, top: `${context.top}px` }"
        @mousedown.stop
      >
        <li @mousedown="handleContext('closeCurrent')">关闭当前</li>
        <li @mousedown="handleContext('closeOthers')">关闭其他</li>
        <li @mousedown="handleContext('closeLeft')">关闭左侧</li>
        <li @mousedown="handleContext('closeRight')">关闭右侧</li>
        <li @mousedown="handleContext('closeAll')">关闭全部</li>
      </ul>
    </teleport>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ArrowLeft, ArrowRight, Close, MoreFilled } from '@element-plus/icons-vue'
import { useTabsStore } from '../../stores/tabs'
import { useThemeStore } from '../../stores/theme'
import AppIcon from '../../components/AppIcon.vue'

const emit = defineEmits<{ navigate: [path: string] }>()
const tabs = useTabsStore()
const theme = useThemeStore()
const listRef = ref<HTMLElement | null>(null)
const context = reactive({ visible: false, left: 0, top: 0, path: '' })

const activate = (path: string): void => {
  tabs.setActive(path)
  emit('navigate', path)
}

const close = (path: string): void => {
  const wasActive = tabs.activePath === path
  tabs.removeTab(path)
  if (wasActive && tabs.activePath && tabs.activePath !== path) emit('navigate', tabs.activePath)
}

const openContext = (event: MouseEvent, path: string): void => {
  context.path = path
  context.left = Math.min(event.clientX, window.innerWidth - 160)
  context.top = Math.min(event.clientY, window.innerHeight - 180)
  context.visible = true
}

const handleContext = (command: string): void => {
  const path = context.path
  context.visible = false
  if (!path) return
  switch (command) {
    case 'closeCurrent': close(path); break
    case 'closeOthers': tabs.closeOthers(path); break
    case 'closeLeft': tabs.closeLeft(path); break
    case 'closeRight': tabs.closeRight(path); break
    case 'closeAll':
      tabs.closeAll()
      if (tabs.activePath) emit('navigate', tabs.activePath)
      break
  }
}

const handleCommand = (command: string): void => {
  if (command === 'closeAll') {
    tabs.closeAll()
    if (tabs.activePath) emit('navigate', tabs.activePath)
  } else if (command === 'closeOthers' && tabs.activePath) {
    tabs.closeOthers(tabs.activePath)
  }
}

const onAuxClick = (event: MouseEvent, path: string): void => {
  if (event.button !== 1 || !theme.tabMiddleClickClose) return
  event.preventDefault()
  close(path)
}

const onWheel = (event: WheelEvent): void => {
  if (!theme.tabWheelable) return
  event.preventDefault()
  listRef.value?.scrollBy({ left: event.deltaY || event.deltaX, behavior: 'smooth' })
}

const scrollPrev = (): void => { listRef.value?.scrollBy({ left: -240, behavior: 'smooth' }) }
const scrollNext = (): void => { listRef.value?.scrollBy({ left: 240, behavior: 'smooth' }) }

const hideContext = (event: MouseEvent): void => {
  if ((event.target as HTMLElement)?.closest('.tab-context')) return
  context.visible = false
}
onMounted(() => document.addEventListener('mousedown', hideContext))
onBeforeUnmount(() => document.removeEventListener('mousedown', hideContext))
</script>

<style scoped>
.global-tab {
  display: flex;
  flex: 0 0 38px;
  align-items: center;
  gap: 4px;
  height: 38px;
  padding: 0 10px;
  background: var(--nf-bg-card);
}
.tab-list {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1;
  overflow-x: auto;
  scrollbar-width: none;
}
.tab-list::-webkit-scrollbar { display: none; }
.tab-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex: 0 0 auto;
  height: 28px;
  padding: 0 10px;
  border: 1px solid var(--nf-border);
  border-radius: 4px;
  color: var(--nf-text-secondary);
  font-size: var(--nf-font-xs);
  cursor: pointer;
  white-space: nowrap;
}
.tab-item:hover { color: var(--nf-text-primary); }
.tab-item.active {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}
.tab-close { font-size: var(--nf-font-xs); }
.tab-close:hover { color: var(--nf-red); }
.tab-icon { display: inline-flex; }
.tab-scroll-btn, .tab-more {
  flex: 0 0 auto;
  padding: 4px;
  cursor: pointer;
  color: var(--nf-text-muted);
}

/* ===== 浏览器风格标签：对齐 Vben Admin tabs-chrome ===== */
.global-tab--chrome {
  --tab-gap: 7px;
  --tab-overlap: 12px;
  gap: 0;
  padding-left: 10px;
}
.global-tab--chrome .tab-list {
  gap: 0;
  height: 100%;
  padding-right: 24px;
}
.global-tab--chrome .tab-item {
  position: relative;
  z-index: 1;
  height: 100%;
  margin: 0;
  margin-right: calc(var(--tab-overlap) * -1);
  padding: 0;
  border: none;
  border-radius: 0;
  background: transparent;
  color: var(--nf-text-secondary);
}
.global-tab--chrome .tab-item.active {
  z-index: 2;
  border: none;
  background: transparent;
  color: var(--el-color-primary);
}
.global-tab--chrome .tab-item:hover:not(.active) { color: var(--nf-text-primary); }
.tab-chrome {
  position: relative;
  display: flex;
  align-items: center;
  width: 100%;
  height: 100%;
}
.tab-chrome-divider {
  position: absolute;
  top: 50%;
  left: calc(var(--tab-gap) * -1);
  z-index: 0;
  width: 1px;
  height: 16px;
  background: var(--nf-line-soft);
  transform: translateY(-50%);
  transition: opacity 0.15s ease;
}
.global-tab--chrome .tab-item:hover:not(.active) .tab-chrome-divider,
.global-tab--chrome .tab-item.active + .tab-item .tab-chrome-divider { opacity: 0; }
.tab-chrome-bg {
  position: absolute;
  inset: 0;
  z-index: -1;
  padding: 0 calc(var(--tab-gap) - 1px);
  pointer-events: none;
  transition: padding-bottom 0.15s ease;
}
.tab-chrome-bg-content {
  height: 100%;
  border-radius: 7px 7px 0 0;
  background: transparent;
  transition: background 0.15s ease, margin 0.15s ease, border-radius 0.15s ease;
}
.tab-chrome-bg-before,
.tab-chrome-bg-after {
  position: absolute;
  bottom: 0;
  width: 7px;
  height: 7px;
  fill: transparent;
  transition: fill 0.15s ease;
}
.tab-chrome-bg-before { left: -1px; }
.tab-chrome-bg-after { right: -1px; }
.global-tab--chrome .tab-item.active .tab-chrome-bg-content {
  background: var(--nf-tab-active-bg);
}
.global-tab--chrome .tab-item.active .tab-chrome-bg-before,
.global-tab--chrome .tab-item.active .tab-chrome-bg-after {
  fill: var(--nf-tab-active-bg);
}
.global-tab--chrome .tab-item:hover:not(.active) .tab-chrome-bg { padding-bottom: 2px; }
.global-tab--chrome .tab-item:hover:not(.active) .tab-chrome-bg-content {
  margin: 0 2px;
  border-radius: 6px;
  background: var(--nf-bg-elevated);
}
.tab-chrome-extra {
  position: absolute;
  top: 50%;
  right: var(--tab-gap);
  z-index: 3;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  transform: translateY(-50%);
}
.tab-chrome-main {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  height: 100%;
  margin: 0 calc(var(--tab-gap) * 2);
  padding: 0 16px 0 8px;
  border-radius: 5px 5px 0 0;
  overflow: hidden;
}
.tab-chrome-main .tab-icon { margin-right: 5px; }
.tab-chrome-main .tab-title {
  font-size: var(--nf-font-base);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>

<style>
.tab-context {
  position: fixed;
  z-index: 3000;
  min-width: 140px;
  margin: 0;
  padding: 4px;
  list-style: none;
  border: 1px solid var(--nf-border);
  border-radius: 6px;
  background: var(--nf-bg-elevated);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
}
.tab-context li {
  padding: 7px 12px;
  border-radius: 4px;
  color: var(--nf-text-primary);
  font-size: var(--nf-font-xs);
  cursor: pointer;
}
.tab-context li:hover { background: var(--nf-overlay); }
</style>
