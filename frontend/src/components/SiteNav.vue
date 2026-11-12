<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import FaIcon from '../ui/FaIcon.vue'
import { ICONS } from '../composables/icons'
import brandLogo from '../assets/logo.png'

const router = useRouter()

const props = defineProps({
  types: { type: Array, default: () => [] },
  activeTypeId: { type: Number, default: 0 },
  favActive: { type: Boolean, default: false },
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

const emit = defineEmits(['select-type', 'toggle-fav', 'search', 'manage', 'batch', 'create', 'logout', 'open-personal'])

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

// 审核中心 / 站点管理：独立页面路由跳转
const goAudit = () => router.push({ name: 'audit' })
const goAdmin = () => router.push({ name: 'admin' })

// 我的提交 / 审核结果：查看自己待审与被驳回的视频及理由
const goSubmissions = () => router.push({ name: 'mySubmissions' })

// ===== 分类项工具类（完整类名写在源码里保证 Tailwind 扫描到） =====
const catBase =
  'shrink-0 relative px-3.5 py-[7px] rounded text-[13.5px] font-medium cursor-pointer select-none ' +
  'transition-colors hover:text-white hover:bg-white/5'
// 选中态：白色加粗 + 底部红色指示条（after 变体）
const underline =
  'after:absolute after:left-3.5 after:right-3.5 after:bottom-0.5 after:h-[2px] after:rounded ' +
  'after:bg-nf-red after:content-[\'\']'
const catClass = (active, fav) => {
  let cls = catBase + (fav ? ' text-[#e08a90]' : ' text-nf-sub')
  if (active) cls += ' font-bold ' + underline + (fav ? ' text-nf-red' : ' text-white')
  return cls
}

// 角标共用工具类
const badge = (color) =>
  `min-w-[17px] h-[17px] px-[5px] rounded-full text-white text-[11px] font-bold leading-[17px] text-center tabular-nums ${color}`

// ===== 更多功能下拉：收起低频操作，缓解导航拥挤 =====
// 默认展开在栏上的：搜索 / 审核中心(角标) / 审核结果(角标) / 新增视频 / 用户
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
}
onMounted(() => document.addEventListener('click', onDocClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))
</script>

<template>
  <!-- ===== 顶部导航：品牌 + 分类导航 + 搜索 + 操作（netflixgc 风格） ===== -->
  <header
    class="sticky top-0 z-[100] flex items-center gap-5 px-10 py-3 bg-gradient-to-b from-black/95 to-nf-page/85 backdrop-blur-[10px] border-b border-white/10 max-[900px]:flex-wrap max-[900px]:gap-2.5 max-[900px]:px-5 max-[900px]:py-2.5"
  >
    <div class="flex items-center gap-2.5 shrink-0">
      <img
        class="w-[30px] h-[30px] rounded-lg shrink-0 shadow-[0_0_0_1px_rgba(255,255,255,0.08)]"
        :src="brandLogo"
        alt="影库"
      />
      <span
        class="text-[26px] font-extrabold tracking-[4px] text-nf-red select-none [text-shadow:0_0_18px_rgba(229,9,20,0.45)]"
      >
        影库
      </span>
      <span class="text-[10px] font-semibold tracking-[4px] text-nf-muted select-none">
        VIDEO&nbsp;FACTORY
      </span>
    </div>

    <nav
      class="flex-1 min-w-0 flex items-center gap-0.5 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
    >
      <a :class="catClass(activeTypeId === 0 && !favActive, false)" @click="emit('select-type', 0)">首页</a>
      <!-- 「我的收藏」紧跟首页：频道较多时分类区横向滚动，个人入口始终在可视起点 -->
      <a :class="catClass(favActive, true)" @click="emit('toggle-fav')">
        <FaIcon :icon="ICONS.favorites" :fixed="false" class="mr-1 text-[12px]" />我的收藏
      </a>
      <!-- 频道项刻意不加图标，避免本就拥挤的频道导航被撑宽 -->
      <a
        v-for="t in types"
        :key="t.id"
        :class="catClass(activeTypeId === t.id && !favActive, false)"
        @click="emit('select-type', t.id)"
      >
        {{ t.name }}
      </a>
    </nav>

    <div class="flex items-center gap-2 shrink-0 max-[900px]:flex-wrap">
      <div
        class="flex items-center gap-[7px] w-[218px] h-[34px] px-[11px] border border-nf-line rounded bg-nf-elevated text-[#8a8a92] transition-colors focus-within:border-[rgba(229,9,20,0.75)]"
      >
        <FaIcon :icon="ICONS.search" :fixed="false" class="text-[13px]" />
        <input
          v-model="keyword"
          class="flex-1 min-w-0 border-none outline-none bg-transparent text-nf-text text-[13px] font-[inherit] placeholder:text-nf-line-hover"
          placeholder="搜索标题 / 路径 / 备注"
          @keyup.enter="onSearch"
        />
      </div>
      <button
        v-if="canAudit"
        class="nf-btn text text-[#ffb3b8] hover:text-white"
        @click="goAudit"
      >
        <FaIcon :icon="ICONS.audit" :fixed="false" class="text-[12px]" />
        审核中心
        <span v-if="pendingCount > 0" :class="badge('bg-nf-red')">
          {{ pendingCount > 99 ? '99+' : pendingCount }}
        </span>
      </button>
      <button
        class="nf-btn text text-[#ffb3b8] hover:text-white"
        title="查看我上传视频的审核结果"
        @click="goSubmissions"
      >
        <FaIcon :icon="ICONS.submissions" :fixed="false" class="text-[12px]" />
        审核结果
        <span v-if="noticeCount > 0" :class="badge('bg-[#b8141c]')">
          {{ noticeCount > 99 ? '99+' : noticeCount }}
        </span>
      </button>

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
            class="max-w-[90px] overflow-hidden text-ellipsis whitespace-nowrap text-[13px] font-semibold text-[#e5e5e5]"
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
</template>
