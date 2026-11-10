<template>
  <!-- Netflix 风格播放页 -->
  <div class="player-page">
    <!-- 顶栏：返回 + 标题 + 收藏 -->
    <header class="page-header">
      <button class="back-btn" @click="goBack">
        <svg viewBox="0 0 24 24" width="16" height="16">
          <path
            d="M19 11H7.83l4.88-4.88a1 1 0 1 0-1.42-1.41l-6.29 6.3a1 1 0 0 0 0 1.41l6.29 6.3a1 1 0 0 0 1.42-1.41L7.83 13H19a1 1 0 0 0 0-2z"
            fill="currentColor"
          />
        </svg>
        返回
      </button>
      <div class="page-title" :title="video?.title">{{ video?.title || '加载中…' }}</div>
      <button
        v-if="video"
        class="fav-btn"
        :class="{ active: video.isFavorite }"
        :title="video.isFavorite ? '取消收藏' : '收藏'"
        @click="toggleFav"
      >
        <svg viewBox="0 0 24 24" width="18" height="18">
          <path
            v-if="video.isFavorite"
            d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"
            fill="currentColor"
          />
          <path
            v-else
            d="M16.5 3c-1.74 0-3.41.81-4.5 2.09C10.91 3.81 9.24 3 7.5 3 4.42 3 2 5.42 2 8.5c0 3.78 3.4 6.86 8.55 11.54L12 21.35l1.45-1.32C18.6 15.36 22 12.28 22 8.5 22 5.42 19.58 3 16.5 3zm-4.4 15.55l-.1.1-.1-.1C7.14 14.24 4 11.39 4 8.5 4 6.5 5.5 5 7.5 5c1.54 0 3.04.99 3.57 2.36h1.87C13.46 5.99 14.96 5 16.5 5c2 0 3.5 1.5 3.5 3.5 0 2.89-3.14 5.74-7.9 10.05z"
            fill="currentColor"
          />
        </svg>
      </button>
    </header>

    <!-- 加载失败 -->
    <div v-if="error" class="error-panel">
      <div class="error-icon">⚠</div>
      <div class="error-title">{{ error }}</div>
      <div class="error-sub">请确认后端服务已启动、视频记录存在</div>
      <button class="nf-btn red" @click="goBack">返回列表</button>
    </div>

    <!-- 播放器与信息 -->
    <template v-else-if="video">
      <!-- 外链且非直链视频文件：提供直跳按钮 -->
      <div v-if="!isDirectFile" class="link-panel">
        <div class="link-title">外部播放链接</div>
        <div class="link-text" :title="video.filePath">{{ video.filePath }}</div>
        <div class="link-desc">该链接为网页或外站地址，浏览器无法内嵌播放，点击下方按钮跳转播放。</div>
        <button class="nf-btn red lg" @click="openLink">打开播放链接 ↗</button>
      </div>

      <div v-else class="player-wrap">
        <video
          v-if="videoSrc"
          :key="videoSrc"
          :src="videoSrc"
          :autoplay="autoPlay"
          controls
          class="page-player"
        >
          当前浏览器不支持该视频格式（推荐 MP4 / WebM），可尝试改用转换后的格式。
        </video>
        <div v-else class="empty-player">该视频未配置有效的文件路径</div>
      </div>

      <div class="meta-panel">
        <span v-if="video.typeName" class="meta-chip type">{{ video.typeName }}</span>
        <span v-for="name in video.tags" :key="name" class="meta-chip">{{ name }}</span>
        <span v-if="!video.tags.length && !video.typeName" class="meta-muted">无标签</span>
        <span class="meta-time">更新于 {{ video.updatedAt }}</span>
      </div>
      <p v-if="video.description" class="meta-desc">{{ video.description }}</p>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from './ui/toast'
import { getVideo, toggleFavorite } from './api'

const route = useRoute()
const router = useRouter()

const video = ref(null)
const error = ref('')

// 到达播放页即视为「立即播放」，进入后自动开始
const autoPlay = true

// 在线直链视频直接播放；本地路径走后端流式接口
const videoSrc = computed(() => {
  const v = video.value
  if (!v) return ''
  return /^https?:\/\//.test(v.filePath) ? v.filePath : `/api/videos/${v.id}/file`
})

// 直链视频文件扩展名（浏览器 <video> 可直接播放的类型）
const DIRECT_FILE_RE = /\.(mp4|webm|ogv|ogg|m4v|mov)(\?|#|$)/i

const isExternalLink = computed(() => /^https?:\/\//.test(video.value?.filePath || ''))

// 外链且不是直链视频文件（如网页地址）→ 提供直跳按钮而非内嵌播放
const isDirectFile = computed(() => !isExternalLink.value || DIRECT_FILE_RE.test(video.value.filePath))

const openLink = () => {
  if (video.value?.filePath) window.open(video.value.filePath, '_blank')
}

const load = async () => {
  error.value = ''
  video.value = null
  try {
    video.value = await getVideo(route.params.id)
    document.title = `${video.value.title} - 视频播放`
  } catch (e) {
    error.value = e.message
  }
}

const goBack = () => {
  if (window.history.length > 1) router.back()
  else router.push({ name: 'list' })
}

const toggleFav = async () => {
  try {
    const data = await toggleFavorite(video.value.id)
    video.value.isFavorite = data.isFavorite
    showToast(data.isFavorite ? '已收藏' : '已取消收藏')
  } catch (e) {
    showToast.error(e.message)
  }
}

onMounted(load)
</script>

<style scoped>
/* ===== Netflix 风格播放页 ===== */

.player-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px 40px 48px;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 18px;
}

.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 15px;
  border: none;
  border-radius: 5px;
  background: rgba(255, 255, 255, 0.12);
  color: #f5f5f5;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.18s ease;
}

.back-btn:hover {
  background: rgba(255, 255, 255, 0.22);
}

.page-title {
  flex: 1;
  min-width: 0;
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 0.5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fav-btn {
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.1);
  color: #b3b3b3;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  transition: transform 0.15s ease, color 0.15s ease, background 0.15s ease;
}

.fav-btn:hover {
  transform: scale(1.1);
  color: #fff;
  background: rgba(229, 9, 20, 0.75);
}

.fav-btn.active {
  color: var(--nf-red);
}

/* 加载失败 */
.error-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 70px 0;
  text-align: center;
}

.error-icon {
  font-size: 40px;
}

.error-title {
  font-size: 16px;
  font-weight: 700;
  color: #f5f5f5;
}

.error-sub {
  font-size: 13px;
  color: var(--nf-text-muted);
  margin-bottom: 14px;
}

/* 播放器 */
.player-wrap {
  background: #000;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.6);
}

.page-player {
  width: 100%;
  max-height: 72vh;
  display: block;
  outline: none;
}

.empty-player {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 320px;
  color: var(--nf-text-muted);
  font-size: 14px;
}

.meta-panel {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}

.meta-chip {
  padding: 2px 12px;
  border-radius: 3px;
  background: #26262b;
  color: #e5e5e5;
  font-size: 13px;
  line-height: 22px;
}

/* 类型徽章：Netflix 红 */
.meta-chip.type {
  background: var(--nf-red);
  color: #fff;
  font-weight: 600;
  letter-spacing: 1px;
}

.meta-time {
  margin-left: auto;
  font-size: 13px;
  color: var(--nf-text-muted);
}

.meta-muted {
  font-size: 13px;
  color: #57575e;
}

.meta-desc {
  margin: 14px 0 0;
  font-size: 14px;
  line-height: 1.8;
  color: #b3b3b3;
  white-space: pre-wrap;
}

/* 外部链接直跳面板 */
.link-panel {
  background: var(--nf-bg-card);
  border: 1px solid var(--nf-border);
  border-radius: 8px;
  padding: 48px 32px;
  text-align: center;
}

.link-title {
  font-size: 16px;
  font-weight: 700;
  color: #f5f5f5;
  margin-bottom: 12px;
}

.link-text {
  font-size: 13px;
  color: var(--nf-text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 640px;
  margin: 0 auto 16px;
}

.link-desc {
  font-size: 13px;
  color: #b3b3b3;
  margin-bottom: 20px;
}

@media (max-width: 700px) {
  .player-page {
    padding: 16px 20px 36px;
  }
}
</style>
