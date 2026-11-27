<template>
  <el-drawer
    :model-value="modelValue"
    size="480px"
    append-to-body
    class="pref-drawer"
    @update:model-value="(value: boolean) => emit('update:modelValue', value)"
  >
    <template #header>
      <div class="pref-header">
        <span class="pref-header-title">偏好设置</span>
        <span class="pref-header-desc">自定义主题、布局与交互行为</span>
      </div>
    </template>

    <div class="pref-body">
      <nav class="pref-nav">
        <button
          v-for="group in groups"
          :key="group.key"
          class="pref-nav-item"
          :class="{ active: activeGroup === group.key }"
          @click="activeGroup = group.key"
        >
          <el-icon><component :is="group.icon" /></el-icon>
          <span>{{ group.label }}</span>
        </button>
      </nav>

      <div class="pref-content">
        <!-- 通用 -->
        <template v-if="activeGroup === 'general'">
          <section class="pref-section">
            <h4>主题模式</h4>
            <div class="segmented">
              <button
                v-for="item in themeModeOptions"
                :key="item.value"
                :class="{ active: theme.theme === item.value }"
                @click="theme.apply(item.value)"
              >
                <el-icon><component :is="item.icon" /></el-icon>
                <span>{{ item.label }}</span>
              </button>
            </div>
            <p class="pref-hint">跟随系统会依据操作系统外观自动切换</p>
          </section>

          <section class="pref-section">
            <h4>内置主题</h4>
            <div class="theme-options">
              <button
                v-for="item in builtinThemes"
                :key="item.value"
                class="theme-option"
                :class="{ active: theme.builtinType === item.value }"
                @click="theme.applyBuiltinTheme(item.value)"
              >
                <span class="theme-option-dot" :style="{ background: item.color }" />
                <span>{{ item.name }}</span>
              </button>
            </div>
          </section>

          <section class="pref-section">
            <h4>主题色</h4>
            <div class="color-row">
              <button
                v-for="color in presetColors"
                :key="color.value"
                class="color-dot"
                :class="{ active: theme.primaryColor.toLowerCase() === color.value.toLowerCase() }"
                :style="{ background: color.value }"
                :title="color.name"
                @click="theme.setPrimaryColor(color.value)"
              />
              <el-color-picker
                :model-value="theme.primaryColor"
                size="small"
                @change="(value: string | null) => value && theme.setPrimaryColor(value)"
              />
            </div>
          </section>

          <section class="pref-section">
            <h4>圆角</h4>
            <div class="segmented segmented--compact">
              <button
                v-for="item in radiusOptions"
                :key="item.value"
                :class="{ active: theme.radius === item.value }"
                @click="theme.setPreference('radius', item.value)"
              >{{ item.name }}</button>
            </div>
          </section>

          <section class="pref-section pref-list">
            <SettingRow label="紧凑模式" desc="缩小内容区间距">
              <el-switch
                :model-value="theme.compact"
                @update:model-value="(v: boolean | string | number) => theme.setPreference('compact', Boolean(v))"
              />
            </SettingRow>
            <SettingRow label="页面水印" desc="显示当前账号标识">
              <el-switch
                :model-value="theme.watermark"
                @update:model-value="(v: boolean | string | number) => theme.setPreference('watermark', Boolean(v))"
              />
            </SettingRow>
            <SettingRow label="动态页面标题" desc="标题跟随菜单变化">
              <el-switch
                :model-value="theme.dynamicTitle"
                @update:model-value="(v: boolean | string | number) => theme.setPreference('dynamicTitle', Boolean(v))"
              />
            </SettingRow>
          </section>
        </template>

        <!-- 布局 -->
        <template v-else-if="activeGroup === 'layout'">
          <section class="pref-section">
            <h4>布局模式</h4>
            <div class="layout-grid">
              <button
                v-for="item in layoutModeOptions"
                :key="item.value"
                class="layout-card"
                :class="{ active: theme.layoutMode === item.value }"
                @click="theme.setLayoutMode(item.value)"
              >
                <svg viewBox="0 0 48 36" class="layout-thumb">
                  <template v-if="item.value === 'vertical'">
                    <rect x="1" y="1" width="12" height="34" rx="2" :fill="thumbFill(item.value)" />
                    <rect x="15" y="1" width="32" height="6" rx="2" :fill="thumbFill(item.value, 0.45)" />
                    <rect x="15" y="9" width="32" height="26" rx="2" :fill="thumbFill(item.value, 0.25)" />
                  </template>
                  <template v-else-if="item.value === 'horizontal'">
                    <rect x="1" y="1" width="46" height="8" rx="2" :fill="thumbFill(item.value)" />
                    <rect x="1" y="11" width="46" height="24" rx="2" :fill="thumbFill(item.value, 0.25)" />
                  </template>
                  <template v-else-if="item.value === 'vertical-mix'">
                    <rect x="1" y="1" width="8" height="34" rx="2" :fill="thumbFill(item.value)" />
                    <rect x="11" y="1" width="10" height="34" rx="2" :fill="thumbFill(item.value, 0.6)" />
                    <rect x="23" y="1" width="24" height="6" rx="2" :fill="thumbFill(item.value, 0.35)" />
                    <rect x="23" y="9" width="24" height="26" rx="2" :fill="thumbFill(item.value, 0.25)" />
                  </template>
                  <template v-else>
                    <rect x="1" y="1" width="46" height="8" rx="2" :fill="thumbFill(item.value)" />
                    <rect x="1" y="11" width="10" height="24" rx="2" :fill="thumbFill(item.value, 0.6)" />
                    <rect x="13" y="11" width="34" height="24" rx="2" :fill="thumbFill(item.value, 0.25)" />
                  </template>
                </svg>
                <span>{{ item.label }}</span>
              </button>
            </div>
          </section>

          <section v-if="theme.layoutMode === 'vertical'" class="pref-section">
            <h4>侧边栏宽度 <em>{{ theme.sidebarWidth }}px</em></h4>
            <el-slider
              :model-value="theme.sidebarWidth"
              :min="180"
              :max="300"
              :step="4"
              @update:model-value="(v: number | number[]) => theme.setPreference('sidebarWidth', Number(v))"
            />
          </section>

          <section v-if="theme.layoutMode === 'vertical-mix'" class="pref-section">
            <h4>混合主栏宽度 <em>{{ theme.mixedWidth }}px</em></h4>
            <el-slider
              :model-value="theme.mixedWidth"
              :min="56"
              :max="120"
              :step="4"
              @update:model-value="(v: number | number[]) => theme.setPreference('mixedWidth', Number(v))"
            />
          </section>

          <section v-if="theme.isMixLayout" class="pref-section">
            <h4>二级菜单宽度 <em>{{ theme.secondaryWidth }}px</em></h4>
            <el-slider
              :model-value="theme.secondaryWidth"
              :min="140"
              :max="260"
              :step="4"
              @update:model-value="(v: number | number[]) => theme.setPreference('secondaryWidth', Number(v))"
            />
          </section>

          <section class="pref-section pref-list">
            <SettingRow v-if="theme.layoutMode === 'vertical'" label="折叠侧边栏" desc="仅保留图标">
              <el-switch
                :model-value="theme.sidebarCollapsed"
                @update:model-value="(v: boolean | string | number) => theme.setPreference('sidebarCollapsed', Boolean(v))"
              />
            </SettingRow>
            <SettingRow v-if="theme.layoutMode === 'vertical'" label="折叠按钮" desc="侧栏底部显示展开按钮">
              <el-switch
                :model-value="theme.sidebarCollapsedButton"
                @update:model-value="(v: boolean | string | number) => theme.setPreference('sidebarCollapsedButton', Boolean(v))"
              />
            </SettingRow>
            <SettingRow label="菜单手风琴" desc="只展开一个子菜单">
              <el-switch
                :model-value="theme.menuAccordion"
                @update:model-value="(v: boolean | string | number) => theme.setPreference('menuAccordion', Boolean(v))"
              />
            </SettingRow>
          </section>
        </template>

        <!-- 顶栏 -->
        <template v-else-if="activeGroup === 'header'">
          <section class="pref-section pref-list">
            <SettingRow label="显示顶栏" :desc="theme.isHorizontalLayout ? '顶部布局下必显' : '隐藏后仅保留内容区'">
              <el-switch
                :model-value="theme.showHeader || theme.isHorizontalLayout"
                :disabled="theme.isHorizontalLayout"
                @update:model-value="(v: boolean | string | number) => theme.setPreference('showHeader', Boolean(v))"
              />
            </SettingRow>
            <SettingRow label="显示面包屑" desc="展示当前菜单层级">
              <el-switch
                :model-value="theme.showBreadcrumb"
                @update:model-value="(v: boolean | string | number) => theme.setPreference('showBreadcrumb', Boolean(v))"
              />
            </SettingRow>
            <SettingRow label="面包屑图标" desc="层级前显示菜单图标">
              <el-switch
                :model-value="theme.breadcrumbIcon"
                @update:model-value="(v: boolean | string | number) => theme.setPreference('breadcrumbIcon', Boolean(v))"
              />
            </SettingRow>
            <SettingRow label="单一层级隐藏" desc="只有一级时隐藏面包屑">
              <el-switch
                :model-value="theme.hideBreadcrumbOne"
                @update:model-value="(v: boolean | string | number) => theme.setPreference('hideBreadcrumbOne', Boolean(v))"
              />
            </SettingRow>
          </section>
        </template>

        <!-- 标签页 -->
        <template v-else-if="activeGroup === 'tabbar'">
          <section class="pref-section pref-list">
            <SettingRow label="显示标签页" desc="多页面快速切换">
              <el-switch
                :model-value="theme.showTabs"
                @update:model-value="(v: boolean | string | number) => theme.setPreference('showTabs', Boolean(v))"
              />
            </SettingRow>
          </section>

          <section class="pref-section">
            <h4>标签风格</h4>
            <div class="segmented segmented--compact">
              <button
                v-for="item in tabbarStyleOptions"
                :key="item.value"
                :class="{ active: theme.tabbarStyle === item.value }"
                @click="theme.setPreference('tabbarStyle', item.value)"
              >{{ item.name }}</button>
            </div>
          </section>

          <section class="pref-section pref-list">
            <SettingRow label="显示图标">
              <el-switch
                :model-value="theme.showTabIcon"
                @update:model-value="(v: boolean | string | number) => theme.setPreference('showTabIcon', Boolean(v))"
              />
            </SettingRow>
            <SettingRow label="中键关闭" desc="鼠标中键点击标签关闭">
              <el-switch
                :model-value="theme.tabMiddleClickClose"
                @update:model-value="(v: boolean | string | number) => theme.setPreference('tabMiddleClickClose', Boolean(v))"
              />
            </SettingRow>
            <SettingRow label="滚轮切换" desc="滚轮横向浏览标签">
              <el-switch
                :model-value="theme.tabWheelable"
                @update:model-value="(v: boolean | string | number) => theme.setPreference('tabWheelable', Boolean(v))"
              />
            </SettingRow>
            <SettingRow label="刷新后保留" desc="记住已打开的标签">
              <el-switch
                :model-value="theme.tabPersist"
                @update:model-value="(v: boolean | string | number) => theme.setPreference('tabPersist', Boolean(v))"
              />
            </SettingRow>
            <SettingRow label="数量上限" desc="0 表示不限制">
              <el-input-number
                :model-value="theme.tabMaxCount"
                :min="0"
                :max="30"
                size="small"
                controls-position="right"
                @update:model-value="(v: number | undefined) => theme.setPreference('tabMaxCount', Number(v || 0))"
              />
            </SettingRow>
          </section>
        </template>

        <!-- 动画 -->
        <template v-else-if="activeGroup === 'transition'">
          <section class="pref-section pref-list">
            <SettingRow label="页面切换动画">
              <el-switch
                :model-value="theme.transitionEnable"
                @update:model-value="(v: boolean | string | number) => theme.setPreference('transitionEnable', Boolean(v))"
              />
            </SettingRow>
            <SettingRow label="顶部进度条" desc="路由切换时显示加载进度">
              <el-switch
                :model-value="theme.transitionProgress"
                @update:model-value="(v: boolean | string | number) => theme.setPreference('transitionProgress', Boolean(v))"
              />
            </SettingRow>
          </section>

          <section class="pref-section">
            <h4>动画效果</h4>
            <div class="option-list">
              <button
                v-for="item in transitionOptions"
                :key="item.value"
                class="option-row"
                :class="{ active: theme.transitionName === item.value }"
                :disabled="!theme.transitionEnable"
                @click="theme.setPreference('transitionName', item.value)"
              >
                <span>{{ item.name }}</span>
                <el-icon v-if="theme.transitionName === item.value"><Check /></el-icon>
              </button>
            </div>
          </section>
        </template>

        <!-- 部件 -->
        <template v-else>
          <section class="pref-section pref-list">
            <SettingRow v-for="item in widgetRows" :key="item.key" :label="item.label" :desc="item.desc">
              <el-switch
                :model-value="theme[item.key]"
                @update:model-value="(v: boolean | string | number) => theme.setPreference(item.key, Boolean(v))"
              />
            </SettingRow>
          </section>
          <p class="pref-hint">部件开关仅影响控制台顶栏入口，不影响功能权限</p>
        </template>
      </div>
    </div>

    <template #footer>
      <div class="pref-footer">
        <el-button size="small" @click="copyPreferences">复制配置</el-button>
        <el-button size="small" type="primary" plain @click="theme.resetPreferences()">恢复默认</el-button>
      </div>
    </template>
  </el-drawer>
</template>

<script setup lang="ts">
import { defineComponent, h, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Check, Menu, Monitor, Moon, Operation, Setting, Sunny, Tickets, Top, VideoCamera,
} from '@element-plus/icons-vue'
import {
  builtinThemes, presetColors, radiusOptions, tabbarStyleOptions, transitionOptions,
  useThemeStore,
  type LayoutMode, type Preferences, type ThemeMode,
} from '../../stores/theme'

defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()
const theme = useThemeStore()

const SettingRow = defineComponent({
  props: { label: { type: String, required: true }, desc: { type: String, default: '' } },
  setup(props, { slots }) {
    return () => h('div', { class: 'pref-row' }, [
      h('div', { class: 'pref-row-text' }, [
        h('span', { class: 'pref-row-label' }, props.label),
        props.desc ? h('span', { class: 'pref-row-desc' }, props.desc) : null,
      ]),
      h('div', { class: 'pref-row-control' }, slots.default?.()),
    ])
  },
})

const groups = [
  { key: 'general', label: '通用', icon: Setting },
  { key: 'layout', label: '布局', icon: Menu },
  { key: 'header', label: '顶栏', icon: Top },
  { key: 'tabbar', label: '标签页', icon: Tickets },
  { key: 'transition', label: '动画', icon: VideoCamera },
  { key: 'widget', label: '部件', icon: Operation },
]
const activeGroup = ref('general')

const themeModeOptions: Array<{ label: string; value: ThemeMode; icon: typeof Sunny }> = [
  { label: '浅色', value: 'light', icon: Sunny },
  { label: '深色', value: 'dark', icon: Moon },
  { label: '系统', value: 'auto', icon: Monitor },
]
const layoutModeOptions: Array<{ label: string; value: LayoutMode }> = [
  { label: '左侧导航', value: 'vertical' },
  { label: '顶部导航', value: 'horizontal' },
  { label: '左侧混合', value: 'vertical-mix' },
  { label: '顶部混合', value: 'horizontal-mix' },
]
const widgetRows: Array<{ key: keyof Preferences; label: string; desc: string }> = [
  { key: 'widgetNotification', label: '通知入口', desc: '顶栏消息通知按钮' },
  { key: 'widgetThemeToggle', label: '主题切换', desc: '顶栏深浅色切换按钮' },
  { key: 'widgetRefresh', label: '页面刷新', desc: '顶栏刷新当前路由' },
  { key: 'widgetSettings', label: '设置入口', desc: '顶栏偏好设置按钮' },
]

const thumbFill = (mode: LayoutMode, opacity = 1): string => {
  const primary = 'var(--el-color-primary)'
  const muted = 'var(--nf-text-muted)'
  const mix = (base: string): string =>
    `color-mix(in srgb, ${base} ${Math.round(opacity * 100)}%, transparent)`
  return theme.layoutMode === mode
    ? opacity === 1 ? primary : mix(primary)
    : mix(muted)
}

const copyPreferences = async (): Promise<void> => {
  try {
    await navigator.clipboard.writeText(theme.exportPreferences())
    ElMessage.success('偏好设置已复制到剪贴板')
  } catch {
    ElMessage.warning('当前环境不支持剪贴板，请在控制台复制')
    console.info(theme.exportPreferences())
  }
}
</script>

<style scoped>
.pref-header { display: flex; flex-direction: column; gap: 4px; }
.pref-header-title { font-size: var(--nf-font-lg); font-weight: 600; color: var(--nf-text-primary); }
.pref-header-desc { font-size: var(--nf-font-xs); color: var(--nf-text-muted); }
.pref-body { display: flex; height: 100%; min-height: 0; margin: -12px 0; }
.pref-nav {
  width: 92px;
  flex: 0 0 92px;
  padding: 8px 6px;
  border-right: 1px solid var(--nf-border);
  background: var(--nf-bg-subtle);
}
.pref-nav-item {
  display: flex;
  align-items: center;
  gap: 7px;
  width: 100%;
  padding: 9px 8px;
  margin-bottom: 4px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--nf-text-secondary);
  font-size: var(--nf-font-xs);
  cursor: pointer;
}
.pref-nav-item:hover { background: var(--nf-overlay); color: var(--nf-text-primary); }
.pref-nav-item.active { background: var(--el-color-primary-light-9); color: var(--el-color-primary); font-weight: 600; }
.pref-content { flex: 1; min-width: 0; padding: 4px 18px 18px; overflow-y: auto; }
.pref-section { padding: 12px 0; border-bottom: 1px solid var(--nf-border); }
.pref-section:last-child { border-bottom: none; }
.pref-section h4 {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 0 0 10px;
  font-size: var(--nf-font-base);
  font-weight: 600;
  color: var(--nf-text-primary);
}
.pref-section h4 em { font-style: normal; font-weight: 400; font-size: var(--nf-font-xs); color: var(--nf-text-muted); }
.pref-second-title { margin-top: 18px !important; }
.pref-hint { margin: 8px 0 0; font-size: var(--nf-font-xs); color: var(--nf-text-muted); }
.pref-list { padding: 4px 0; }
.pref-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 48px; }
.pref-row-text { display: flex; flex-direction: column; gap: 2px; }
.pref-row-label { font-size: var(--nf-font-base); color: var(--nf-text-primary); }
.pref-row-desc { font-size: var(--nf-font-xs); color: var(--nf-text-muted); }
.pref-row-control { flex: 0 0 auto; }

.segmented { display: flex; gap: 8px; }
.segmented button {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 9px 6px;
  border: 1px solid var(--nf-border);
  border-radius: 6px;
  background: var(--nf-bg-card);
  color: var(--nf-text-secondary);
  font-size: var(--nf-font-xs);
  cursor: pointer;
}
.segmented button:hover { border-color: var(--el-color-primary); }
.segmented button.active {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-weight: 600;
}
.segmented--compact button { padding: 7px 4px; }

.theme-options { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.theme-option {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 6px;
  border: 1px solid var(--nf-border);
  border-radius: 6px;
  background: var(--nf-bg-card);
  color: var(--nf-text-secondary);
  font-size: var(--nf-font-xs);
  cursor: pointer;
}
.theme-option:hover { border-color: var(--el-color-primary); }
.theme-option.active { border-color: var(--el-color-primary); color: var(--el-color-primary); }
.theme-option-dot { width: 12px; height: 12px; border-radius: 50%; flex: 0 0 auto; }

.color-row { display: flex; align-items: center; gap: 12px; }
.color-dot { width: 24px; height: 24px; border: 2px solid transparent; border-radius: 50%; cursor: pointer; }
.color-dot.active { border-color: var(--nf-text-primary); box-shadow: 0 0 0 2px var(--nf-bg-card) inset; }

.layout-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
.layout-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 9px 4px;
  border: 1px solid var(--nf-border);
  border-radius: 6px;
  background: var(--nf-bg-card);
  color: var(--nf-text-secondary);
  font-size: var(--nf-font-xs);
  cursor: pointer;
}
.layout-card:hover { border-color: var(--el-color-primary); }
.layout-card.active { border-color: var(--el-color-primary); color: var(--el-color-primary); }
.layout-thumb { width: 48px; height: 36px; }

.option-list { display: flex; flex-direction: column; gap: 6px; }
.option-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 9px 12px;
  border: 1px solid var(--nf-border);
  border-radius: 6px;
  background: var(--nf-bg-card);
  color: var(--nf-text-secondary);
  font-size: var(--nf-font-xs);
  cursor: pointer;
}
.option-row:hover:not(:disabled) { border-color: var(--el-color-primary); }
.option-row.active { border-color: var(--el-color-primary); color: var(--el-color-primary); }
.option-row:disabled { opacity: 0.45; cursor: not-allowed; }

.pref-footer { display: flex; justify-content: flex-end; gap: 8px; }
</style>

<style>
.pref-drawer .el-drawer__body { padding: 12px 20px; min-height: 0; overflow: hidden; }
.pref-drawer .el-drawer__footer { border-top: 1px solid var(--nf-border); padding: 12px 20px; }
</style>
