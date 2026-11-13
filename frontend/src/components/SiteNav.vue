<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import FaIcon from '../ui/FaIcon.vue'
import { ICONS } from '../composables/icons'
import { useTheme } from '../composables/useTheme'
import brandLogo from '../assets/logo.png'

const router = useRouter()
const { isLight, toggleTheme } = useTheme()

const props = defineProps({
  types: { type: Array, default: () => [] },
  activeTypeId: { type: Number, default: 0 },
  favActive: { type: Boolean, default: false },
  wantActive: { type: Boolean, default: false },
  username: { type: String, default: '' },
  // 当前登录用户头像相对路径（空串表示未设置，回退首字母）
  avatar: { type: String, default: '' },
  // 审核中心入口：role=admin 或 reviewer
  isAdmin: { type: Boolean, default: false },
  canAudit: { type: Boolean, default: false },
  pendingCount: { type: Number, default: 0 },
  // 本人被驳回的视频数量（「审核结果」角标）
  noticeCount: { type: Number, default: 0 },
})

const emit = defineEmits(['select-type', 'toggle-fav', 'toggle-want', 'search', 'manage', 'batch', 'create', 'logout', 'open-personal'])

// 头像图片地址（上传后 avatar 变化，时间戳破除浏览器缓存；加载失败回退首字母）
const ts = ref(Date.now())
const avatarErr = ref(false)
const avatarSrc = computed(() => (props.avatar ? `/api/auth/avatar?t=${ts.value}` : ''))
watch(
  () => props.avatar,
  () => { ts.value = Date.now(); avatarErr.value = false },
)

const keyword = ref('')

const onSearch = () => emit('search', keyword.value.trim())

// ===== 移动端汉堡抽屉：解决导航拥挤（窄屏收起内联导航与操作簇） =====
const menuOpen = ref(false)
const drawerRef = ref(null)
const toggleMenu = () => { menuOpen.value = !menuOpen.value }
const closeMenu = () => { menuOpen.value = false }
// 抽屉内任一操作：先执行 emit，再关抽屉
const pick = (fn) => { fn(); closeMenu() }

// 审核中心 / 站点管理：独立页面路由跳转
const goAudit = () => router.push({ name: 'audit' })
const goAdmin = () => router.push({ name: 'admin' })

// 我的提交 / 审核结果：查看自己待审与被驳回的视频及理由
const goSubmissions = () => router.push({ name: 'mySubmissions' })

// 审核下拉：合并「审核中心」与「审核结果」两个入口，缓解导航拥挤
const auditOpen = ref(false)
const auditRef = ref(null)
const toggleAudit = () => { auditOpen.value = !auditOpen.value }
const closeAudit = () => { auditOpen.value = false }
// 父按钮角标：审核员优先显示待审积压，普通用户显示被驳回提醒
const auditBadge = computed(() => {
  if (props.canAudit && props.pendingCount > 0) return props.pendingCount > 99 ? '99+' : props.pendingCount
  if (props.noticeCount > 0) return props.noticeCount > 99 ? '99+' : props.noticeCount
  return 0
})

// ===== 分类项工具类（完整类名写在源码里保证 Tailwind 扫描到） =====
const catBase =
  'shrink-0 relative px-3.5 py-[7px] rounded text-[13.5px] font-medium cursor-pointer select-none ' +
  'transition-colors hover:text-nf-text hover:bg-white/5'
// 选中态：白色加粗 + 底部红色指示条（after 变体）
const underline =
  'after:absolute after:left-3.5 after:right-3.5 after:bottom-0.5 after:h-[2px] after:rounded ' +
  'after:bg-nf-red after:content-[\'\']'
const catClass = (active, fav) => {
  let cls = catBase + (fav ? ' text-[#e08a90]' : ' text-nf-sub')
  // 选中态用主题文字色而非固定白色，浅色主题下依旧可读
  if (active) cls += ' font-bold ' + underline + (fav ? ' text-nf-red' : ' text-nf-text')
  return cls
}

// 角标共用工具类
const badge = (color) =>
  `min-w-[17px] h-[17px] px-[5px] rounded-full text-white text-[11px] font-bold leading-[17px] text-center tabular-nums ${color}`

// ===== 更多功能下拉：收起低频操作，缓解导航拥挤 =====
// 默认展开在栏上的：搜索 / 审核(合并审核中心+审核结果，带角标) / 新增视频 / 用户
// 收进「更多」的：站点管理(超管) / 标签·类型管理 / 批量导入
const dropdownOpen = ref(false)
const moreRef = ref(null)
const toggleMore = () => {
  dropdownOpen.value = !dropdownOpen.value
}
const closeMore = () => {
  dropdownOpen.value = false
}
const onDocClick = (e) => {
  if (dropdownOpen.value && moreRef.value && !moreRef.value.contains(e.target)) {
    dropdownOpen.value = false
  }
  if (auditOpen.value && auditRef.value && !auditRef.value.contains(e.target)) {
    auditOpen.value = false
  }
}
onMounted(() => document.addEventListener('click', onDocClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))
</script>

<template>
  <!-- ===== 顶部导航：品牌 + 分类导航 + 搜索 + 操作（netflixgc 风格） ===== -->
  <header
    class="nf-site-header sticky top-0 z-[100] flex items-center gap-5 px-10 py-3 bg-gradient-to-b from-black/95 to-nf-page/85 backdrop-blur-[10px] border-b border-white/10 max-[900px]:flex-wrap max-[900px]:gap-2.5 max-[900px]:px-5 max-[900px]:py-2.5"
  >
    <div class="flex items-center gap-2.5 shrink-0">
      <img
        class="w-[30px] h-[30px] rounded-lg shrink-0 shadow-[0_0_0_1px_var(--nf-overlay-soft)]"
        :src="brandLogo"
        alt="影库"
      />
      <span
        class="text-[26px] font-extrabold tracking-[4px] text-nf-red select-none [text-shadow:0_0_18px_rgba(229,9,20,0.45)]"
      >
        影库
      </span>
      <span class="hidden text-[10px] font-semibold tracking-[4px] text-nf-muted select-none max-[900px]:inline">
        VIDEO&nbsp;FACTORY
      </span>
    </div>

    <!-- 移动端汉堡：窄屏才显示，点击展开抽屉（桌面端隐藏） -->
    <button
      class="nf-btn ghost px-3 min-[901px]:hidden"
      title="菜单"
      @click.stop="toggleMenu"
    >
      <FaIcon :icon="ICONS.menu" :fixed="false" />
    </button>

    <nav
      class="flex-1 min-w-0 flex items-center gap-0.5 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden] max-[900px]:hidden"
    >
      <a :class="catClass(activeTypeId === 0 && !favActive && !wantActive, false)" @click="emit('select-type', 0)">首页</a>
      <!-- 「我的收藏」紧跟首页：频道较多时分类区横向滚动，个人入口始终在可视起点 -->
      <a :class="catClass(favActive, true)" @click="emit('toggle-fav')">
        <FaIcon :icon="ICONS.favorites" :fixed="false" class="mr-1 text-[12px]" />我的收藏
      </a>
      <a :class="catClass(wantActive, false)" @click="emit('toggle-want')">
        <FaIcon :icon="ICONS.wantlist" :fixed="false" class="mr-1 text-[12px]" />想看清单
      </a>
      <!-- 频道项刻意不加图标，避免本就拥挤的频道导航被撑宽 -->
      <a
        v-for="t in types"
        :key="t.id"
        :class="catClass(activeTypeId === t.id && !favActive && !wantActive, false)"
        @click="emit('select-type', t.id)"
      >
        {{ t.name }}
      </a>
    </nav>

    <div class="flex items-center gap-2 shrink-0 max-[900px]:hidden">
      <div
        class="flex items-center gap-[7px] w-[218px] h-[34px] px-[11px] border border-nf-line rounded bg-nf-elevated text-[#8a8a92] transition-colors focus-within:border-[rgba(229,9,20,0.75)]"
      >
        <FaIcon :icon="ICONS.search" :fixed="false" class="text-[13px]" />
        <input
          v-model="keyword"
          class="flex-1 min-w-0 border-none outline-none bg-transparent text-nf-text text-[13px] font-[inherit] placeholder:text-nf-line-hover"
          placeholder="搜索标题 / 备注"
          @keyup.enter="onSearch"
        />
      </div>
      <!-- 审核：合并「审核中心」与「审核结果」入口，缓解导航拥挤 -->
      <div class="relative" ref="auditRef">
        <button
          class="nf-btn text text-[#ffb3b8] hover:text-nf-text"
          @click.stop="toggleAudit"
        >
          <FaIcon :icon="ICONS.audit" :fixed="false" class="text-[12px]" />
          审核
          <FaIcon :icon="ICONS.caretDown" :fixed="false" class="text-[10px] ml-[2px]" />
          <span v-if="auditBadge > 0" :class="badge('bg-nf-red')">{{ auditBadge }}</span>
        </button>
        <div
          v-if="auditOpen"
          class="absolute right-0 top-[calc(100%+8px)] z-[110] min-w-[172px] py-1.5 rounded-xl border border-white/10 bg-nf-elevated shadow-[0_12px_32px_rgba(0,0,0,0.55)] backdrop-blur-[10px]"
        >
          <button v-if="canAudit" class="nf-btn-menu" @click="closeAudit(); goAudit()">
            <FaIcon :icon="ICONS.audit" />审核中心
            <span v-if="pendingCount > 0" :class="badge('bg-nf-red')">
              {{ pendingCount > 99 ? '99+' : pendingCount }}
            </span>
          </button>
          <button class="nf-btn-menu" @click="closeAudit(); goSubmissions()">
            <FaIcon :icon="ICONS.submissions" />审核结果
            <span v-if="noticeCount > 0" :class="badge('bg-[#b8141c]')">
              {{ noticeCount > 99 ? '99+' : noticeCount }}
            </span>
          </button>
        </div>
      </div>

      <!-- 更多功能：收起低频操作，缓解导航拥挤 -->
      <div class="relative" ref="moreRef">
        <button
          class="nf-btn ghost px-3"
          title="更多功能"
          @click.stop="toggleMore"
        >
          <FaIcon :icon="ICONS.more" :fixed="false" />
        </button>
        <div
          v-if="dropdownOpen"
          class="absolute right-0 top-[calc(100%+8px)] z-[110] min-w-[160px] py-1.5 rounded-xl border border-white/10 bg-nf-elevated shadow-[0_12px_32px_rgba(0,0,0,0.55)] backdrop-blur-[10px]"
        >
          <button v-if="isAdmin" class="nf-btn-menu" @click="closeMore(); goAdmin()">
            <FaIcon :icon="ICONS.admin" />站点管理
          </button>
          <button class="nf-btn-menu" @click="closeMore(); emit('manage')">
            <FaIcon :icon="ICONS.taxonomy" />标签 / 类型管理
          </button>
          <button class="nf-btn-menu" @click="closeMore(); emit('batch')">
            <FaIcon :icon="ICONS.batch" />批量导入
          </button>
          <div class="my-1 border-t border-white/10"></div>
          <button class="nf-btn-menu" @click="closeMore(); toggleTheme()">
            <FaIcon :icon="isLight ? ICONS.themeDark : ICONS.themeLight" />
            {{ isLight ? '切换深色主题' : '切换浅色主题' }}
          </button>
        </div>
      </div>

      <button class="nf-btn red" @click="emit('create')">
        <FaIcon :icon="ICONS.create" :fixed="false" />新增视频
      </button>
      <div class="flex items-center gap-2 py-1 pr-1.5 pl-1 rounded-[20px] bg-white/5">
        <button
          class="flex items-center gap-2 border-none bg-transparent p-0 cursor-pointer select-none"
          title="个人中心"
          @click="emit('open-personal')"
        >
          <img
            v-if="avatar && !avatarErr"
            :src="avatarSrc"
            class="w-[26px] h-[26px] rounded-full object-cover"
            alt="头像"
            @error="avatarErr = true"
          />
          <span
            v-else
            class="w-[26px] h-[26px] rounded-full bg-nf-red text-white text-xs font-bold flex items-center justify-center select-none"
          >
            {{ username.slice(0, 1).toUpperCase() }}
          </span>
          <span
            class="max-w-[90px] overflow-hidden text-ellipsis whitespace-nowrap text-[13px] font-semibold text-[var(--nf-text-primary)]"
            :title="username"
          >
            {{ username }}
          </span>
        </button>
        <button
          class="flex items-center gap-1 border-none bg-transparent text-nf-muted text-xs cursor-pointer px-1 py-0.5 rounded transition-colors hover:bg-[rgba(229,9,20,0.75)] hover:text-white"
          title="退出登录"
          @click="emit('logout')"
        >
          <FaIcon :icon="ICONS.logout" :fixed="false" />
          退出
        </button>
      </div>
    </div>
  </header>

  <!-- ===== 移动端抽屉：窄屏收纳全部导航与操作，缓解导航拥挤 ===== -->
  <Teleport to="body">
    <Transition name="nav-drawer">
      <div
        v-if="menuOpen"
        class="nav-overlay"
        @click.self="closeMenu"
      >
        <aside ref="drawerRef" class="nav-drawer">
          <div class="nav-drawer-head">
            <span class="nav-drawer-title">菜单</span>
            <button class="nav-close" title="关闭" @click="closeMenu">
              <FaIcon :icon="ICONS.close" :fixed="false" />
            </button>
          </div>

          <!-- 搜索 -->
          <div class="nav-search">
            <FaIcon :icon="ICONS.search" :fixed="false" class="text-[13px]" />
            <input
              v-model="keyword"
              class="flex-1 min-w-0 border-none outline-none bg-transparent text-nf-text text-[13px] font-[inherit] placeholder:text-nf-line-hover"
              placeholder="搜索标题 / 备注"
              @keyup.enter="pick(onSearch)"
            />
          </div>

          <!-- 导航：首页 / 收藏 / 频道 -->
          <nav class="nav-links">
            <a
              :class="catClass(activeTypeId === 0 && !favActive && !wantActive, false)"
              @click="pick(() => emit('select-type', 0))"
            >首页</a>
            <a
              :class="catClass(favActive, true)"
              @click="pick(() => emit('toggle-fav'))"
            >
              <FaIcon :icon="ICONS.favorites" :fixed="false" class="mr-1 text-[12px]" />我的收藏
            </a>
            <a
              :class="catClass(wantActive, false)"
              @click="pick(() => emit('toggle-want'))"
            >
              <FaIcon :icon="ICONS.wantlist" :fixed="false" class="mr-1 text-[12px]" />想看清单
            </a>
            <a
              v-for="t in types"
              :key="t.id"
              :class="catClass(activeTypeId === t.id && !favActive && !wantActive, false)"
              @click="pick(() => emit('select-type', t.id))"
            >{{ t.name }}</a>
          </nav>

          <!-- 操作：低频与高频统一收纳 -->
          <div class="nav-actions">
            <!-- 审核：合并入口 -->
            <div class="nav-group">
              <span class="nav-group-label">审核</span>
              <button v-if="canAudit" class="nf-btn text w-full justify-start" @click="pick(goAudit)">
                <FaIcon :icon="ICONS.audit" :fixed="false" class="text-[13px]" />审核中心
                <span v-if="pendingCount > 0" :class="badge('bg-nf-red')">{{ pendingCount > 99 ? '99+' : pendingCount }}</span>
              </button>
              <button class="nf-btn text w-full justify-start" @click="pick(goSubmissions)">
                <FaIcon :icon="ICONS.submissions" :fixed="false" class="text-[13px]" />审核结果
                <span v-if="noticeCount > 0" :class="badge('bg-[#b8141c]')">{{ noticeCount > 99 ? '99+' : noticeCount }}</span>
              </button>
            </div>
            <button v-if="isAdmin" class="nf-btn text w-full justify-start" @click="pick(goAdmin)">
              <FaIcon :icon="ICONS.admin" :fixed="false" class="text-[13px]" />站点管理
            </button>
            <button class="nf-btn text w-full justify-start" @click="pick(() => emit('manage'))">
              <FaIcon :icon="ICONS.taxonomy" :fixed="false" class="text-[13px]" />标签 / 类型管理
            </button>
            <button class="nf-btn text w-full justify-start" @click="pick(() => emit('batch'))">
              <FaIcon :icon="ICONS.batch" :fixed="false" class="text-[13px]" />批量导入
            </button>
            <button class="nf-btn red w-full justify-start" @click="pick(() => emit('create'))">
              <FaIcon :icon="ICONS.create" :fixed="false" class="text-[13px]" />新增视频
            </button>
            <button class="nf-btn text w-full justify-start" @click="pick(toggleTheme)">
              <FaIcon
                :icon="isLight ? ICONS.themeDark : ICONS.themeLight"
                :fixed="false"
                class="text-[13px]"
              />{{ isLight ? '切换深色主题' : '切换浅色主题' }}
            </button>
            <button class="nf-btn ghost w-full justify-start" @click="pick(() => emit('open-personal'))">
              <FaIcon :icon="ICONS.account" :fixed="false" class="text-[13px]" />个人中心
            </button>
            <button class="nf-btn ghost w-full justify-start" @click="pick(() => emit('logout'))">
              <FaIcon :icon="ICONS.logout" :fixed="false" class="text-[13px]" />退出登录
            </button>
          </div>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* ===== 移动端抽屉 ===== */
.nav-overlay {
  position: fixed;
  inset: 0;
  z-index: 120;
  display: flex;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
}

.nav-drawer {
  width: min(84vw, 340px);
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 18px 16px;
  overflow-y: auto;
  background: var(--nf-bg-page);
  border-right: 1px solid var(--nf-overlay);
  box-shadow: 12px 0 40px rgba(0, 0, 0, 0.6);
}

.nav-drawer-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.nav-drawer-title {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 2px;
  color: var(--nf-text, var(--nf-text-primary));
}

.nav-close {
  width: 30px;
  height: 30px;
  border: none;
  border-radius: 50%;
  background: var(--nf-overlay);
  color: var(--nf-sub, var(--nf-text-secondary));
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.nav-close:hover {
  background: rgba(229, 9, 20, 0.75);
  color: #fff;
}

.nav-search {
  display: flex;
  align-items: center;
  gap: 7px;
  height: 36px;
  padding: 0 11px;
  border: 1px solid var(--nf-line, var(--nf-overlay));
  border-radius: 7px;
  background: var(--nf-elevated, var(--nf-bg-card));
  color: #8a8a92;
}

.nav-links {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 0;
  border-top: 1px solid var(--nf-overlay-soft);
  border-bottom: 1px solid var(--nf-overlay-soft);
}

.nav-links a {
  padding: 10px 6px;
  font-size: 14px;
  color: var(--nf-sub, var(--nf-text-secondary));
  cursor: pointer;
  border-radius: 6px;
  transition: background 0.15s ease, color 0.15s ease;
}

.nav-links a:hover {
  background: var(--nf-overlay-soft);
  color: #fff;
}

.nav-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* 审核分组：将审核中心 / 审核结果归到「审核」标签下，与桌面端下拉一致 */
.nav-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 10px;
  margin-top: 4px;
  border-top: 1px solid var(--nf-overlay-soft);
}

.nav-group-label {
  font-size: 11px;
  letter-spacing: 2px;
  color: var(--nf-muted, #6b6b73);
  padding-left: 4px;
}

.nav-actions .nf-btn.w-full {
  width: 100%;
}

/* 抽屉滑入 / 淡入过渡 */
.nav-drawer-enter-active,
.nav-drawer-leave-active {
  transition: opacity 0.25s ease;
}
.nav-drawer-enter-active .nav-drawer,
.nav-drawer-leave-active .nav-drawer {
  transition: transform 0.25s ease;
}
.nav-drawer-enter-from,
.nav-drawer-leave-to {
  opacity: 0;
}
.nav-drawer-enter-from .nav-drawer,
.nav-drawer-leave-to .nav-drawer {
  transform: translateX(-100%);
}
</style>
