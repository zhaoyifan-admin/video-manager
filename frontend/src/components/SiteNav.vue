<script setup>
import { ref } from 'vue'
import brandLogo from '../assets/logo.png'

defineProps({
  types: { type: Array, default: () => [] },
  activeTypeId: { type: Number, default: 0 },
  favActive: { type: Boolean, default: false },
  username: { type: String, default: '' },
})

const emit = defineEmits(['select-type', 'toggle-fav', 'search', 'manage', 'batch', 'create', 'logout'])

const keyword = ref('')

const onSearch = () => emit('search', keyword.value.trim())
</script>

<template>
  <!-- ===== 顶部导航：品牌 + 分类导航 + 搜索 + 操作（netflixgc 风格） ===== -->
  <header class="site-nav">
    <div class="nav-left">
      <img class="nav-logo" :src="brandLogo" alt="影库" />
      <span class="nav-brand">影库</span>
      <span class="nav-sub">VIDEO&nbsp;FACTORY</span>
    </div>

    <nav class="nav-cats">
      <a class="nav-cat" :class="{ active: activeTypeId === 0 && !favActive }" @click="emit('select-type', 0)">首页</a>
      <a
        v-for="t in types"
        :key="t.id"
        class="nav-cat"
        :class="{ active: activeTypeId === t.id && !favActive }"
        @click="emit('select-type', t.id)"
      >
        {{ t.name }}
      </a>
      <a class="nav-cat fav" :class="{ active: favActive }" @click="emit('toggle-fav')">
        ♥ 我的收藏
      </a>
    </nav>

    <div class="nav-right">
      <div class="nav-search">
        <svg viewBox="0 0 24 24" width="14" height="14">
          <path
            d="M15.5 14h-.79l-.28-.27a6.5 6.5 0 1 0-.7.7l.27.28v.79l5 4.99L20.49 19zm-6 0A4.5 4.5 0 1 1 14 9.5 4.5 4.5 0 0 1 9.5 14z"
            fill="currentColor"
          />
        </svg>
        <input
          v-model="keyword"
          class="search-input"
          placeholder="搜索标题 / 路径 / 备注"
          @keyup.enter="onSearch"
        />
      </div>
      <button class="nf-btn text" @click="emit('manage')">管理</button>
      <button class="nf-btn ghost" @click="emit('batch')">批量导入</button>
      <button class="nf-btn red" @click="emit('create')">＋ 新增视频</button>
      <div class="nav-user">
        <span class="user-avatar">{{ username.slice(0, 1).toUpperCase() }}</span>
        <span class="user-name" :title="username">{{ username }}</span>
        <button class="logout-btn" title="退出登录" @click="emit('logout')">退出</button>
      </div>
    </div>
  </header>
</template>

<style scoped>
/* ===== 顶部导航 ===== */
.site-nav {
  position: sticky;
  top: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 12px 40px;
  background: linear-gradient(180deg, rgba(0, 0, 0, 0.95), rgba(11, 11, 13, 0.85));
  backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.nav-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.nav-logo {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  flex-shrink: 0;
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.08);
}

.nav-brand {
  font-size: 26px;
  font-weight: 800;
  letter-spacing: 4px;
  color: var(--nf-red);
  text-shadow: 0 0 18px rgba(229, 9, 20, 0.45);
  user-select: none;
}

.nav-sub {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 4px;
  color: var(--nf-text-muted);
  user-select: none;
}

/* 分类导航 */
.nav-cats {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 2px;
  overflow-x: auto;
  scrollbar-width: none;
}

.nav-cats::-webkit-scrollbar {
  display: none;
}

.nav-cat {
  flex-shrink: 0;
  padding: 7px 14px;
  border-radius: 5px;
  font-size: 13.5px;
  font-weight: 500;
  color: var(--nf-text-secondary);
  cursor: pointer;
  transition: color 0.15s ease, background 0.15s ease;
  user-select: none;
}

.nav-cat:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.07);
}

.nav-cat.active {
  color: #fff;
  font-weight: 700;
  position: relative;
}

.nav-cat.active::after {
  content: '';
  position: absolute;
  left: 14px;
  right: 14px;
  bottom: 1px;
  height: 2px;
  border-radius: 1px;
  background: var(--nf-red);
}

.nav-cat.fav {
  color: #e08a90;
}

.nav-cat.fav.active {
  color: var(--nf-red);
}

.nav-cat.fav.active::after {
  background: var(--nf-red);
}

.nav-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

/* 搜索框 */
.nav-search {
  display: flex;
  align-items: center;
  gap: 7px;
  width: 218px;
  padding: 0 11px;
  height: 34px;
  border: 1px solid #333338;
  border-radius: 5px;
  background: #1f1f23;
  color: #8a8a92;
  transition: border-color 0.18s ease;
}

.nav-search:focus-within {
  border-color: rgba(229, 9, 20, 0.75);
}

.search-input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  color: #f5f5f5;
  font-size: 13px;
  font-family: inherit;
}

.search-input::placeholder {
  color: #5c5c63;
}

/* 用户区：头像 + 用户名 + 退出 */
.nav-user {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 6px 4px 4px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.06);
}

.user-avatar {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--nf-red);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  user-select: none;
}

.user-name {
  max-width: 90px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 600;
  color: #e5e5e5;
}

.logout-btn {
  border: none;
  background: transparent;
  color: var(--nf-text-muted);
  font-size: 12px;
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 4px;
}

.logout-btn:hover {
  color: #fff;
  background: rgba(229, 9, 20, 0.75);
}

/* 响应式：小屏收紧间距 */
@media (max-width: 900px) {
  .site-nav {
    flex-wrap: wrap;
    padding: 10px 20px;
    gap: 10px;
  }

  .nav-right {
    flex-wrap: wrap;
  }
}
</style>
