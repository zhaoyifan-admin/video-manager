<template>
  <!-- Netflix 风格详情页：只看信息，不承担播放 -->
  <div class="detail-page">
    <header class="page-header">
      <button class="back-btn" @click="goBack">
        <FaIcon :icon="ICONS.back" :fixed="false" class="text-[16px]" />
        返回
      </button>
      <div class="page-title">影片详情</div>
    </header>

    <!-- 加载失败 -->
    <div v-if="error" class="error-panel">
      <div class="error-icon">⚠</div>
      <div class="error-title">{{ error }}</div>
      <div class="error-sub">请确认后端服务已启动、视频记录存在</div>
      <button class="nf-btn red" @click="goBack"><FaIcon :icon="ICONS.back" :fixed="false" />返回列表</button>
    </div>

    <template v-else-if="video">
      <!-- 大图背景 + 标题信息 -->
      <div class="backdrop" :class="`cover-tone-${video.id % 6}`">
        <img v-if="coverUrl" class="backdrop-img" :src="coverUrl" alt="" />
        <div class="backdrop-scrim"></div>
        <div class="backdrop-content">
          <span v-if="video.typeName" class="backdrop-badge">{{ video.typeName }}</span>
          <h1 class="backdrop-title">{{ video.title }}</h1>
          <div v-if="video.tags.length" class="backdrop-tags">
            <span v-for="name in video.tags" :key="name" class="hero-chip">{{ name }}</span>
          </div>
          <p v-if="video.description" class="backdrop-desc">{{ video.description }}</p>
          <div class="backdrop-actions">
            <button class="nf-btn red lg" @click="goPlay">
              <FaIcon :icon="ICONS.play" :fixed="false" class="text-[18px]" />
              立即播放
            </button>
            <button
              class="nf-btn ghost lg"
              :class="{ faved: video.isFavorite }"
              @click="toggleFav"
            >
              <FaIcon :icon="ICONS.fav" :variant="video.isFavorite ? 'solid' : 'regular'" :fixed="false" />
              {{ video.isFavorite ? '已收藏' : '收藏' }}
            </button>
          </div>
        </div>
      </div>

      <!-- 元信息面板 -->
      <div class="info-panel">
        <div class="info-row">
          <span class="info-label">影视类型</span>
          <span class="info-value">{{ video.typeName || '未分类' }}</span>
        </div>
        <div class="info-row">
          <span class="info-label">标签</span>
          <span class="info-value">
            <template v-if="video.tags.length">
              <span v-for="name in video.tags" :key="name" class="chip">{{ name }}</span>
            </template>
            <template v-else>无标签</template>
          </span>
        </div>
        <div class="info-row">
          <span class="info-label">文件路径</span>
          <span class="info-value path" :title="video.filePath">{{ video.filePath || '—' }}</span>
        </div>
        <div class="info-row">
          <span class="info-label">备注</span>
          <span class="info-value">{{ video.description || '—' }}</span>
        </div>
        <div class="info-row">
          <span class="info-label">更新时间</span>
          <span class="info-value">{{ video.updatedAt }}</span>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ICONS } from './composables/icons'
import FaIcon from './ui/FaIcon.vue'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from './ui/toast'
import { getVideo, toggleFavorite } from './api'

const route = useRoute()
const router = useRouter()

const video = ref(null)
const error = ref('')

// 详情页封面：优先后端 ffmpeg 缩略图，失败（外链等）则用占位渐变
const coverUrl = ref('')
const loadCover = () => {
  const v = video.value
  if (!v || !v.filePath || /^https?:\/\//.test(v.filePath)) return
  const img = new Image()
  img.onload = () => {
    coverUrl.value = `/api/videos/${v.id}/thumb`
  }
  img.src = `/api/videos/${v.id}/thumb`
}

// 播放是独立动作：跳播放页自动播放
const goPlay = () => {
  router.push({ name: 'play', params: { id: video.value.id } })
}

const load = async () => {
  error.value = ''
  video.value = null
  try {
    video.value = await getVideo(route.params.id)
    document.title = `${video.value.title} - 影片详情`
    loadCover()
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
/* ===== Netflix 风格详情页 ===== */

.detail-page {
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
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 2px;
  color: var(--nf-text-secondary);
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

/* ===== 大图背景区 ===== */
.backdrop {
  position: relative;
  height: 400px;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--nf-border);
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.55);
}

.backdrop-img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.backdrop-scrim {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(90deg, rgba(0, 0, 0, 0.8) 0%, rgba(0, 0, 0, 0.4) 45%, rgba(0, 0, 0, 0.05) 80%),
    linear-gradient(180deg, rgba(0, 0, 0, 0.1) 0%, rgba(0, 0, 0, 0) 35%, rgba(11, 11, 13, 0.92) 100%);
}

.backdrop-content {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 0 36px 34px;
}

.backdrop-badge {
  display: inline-block;
  padding: 3px 12px;
  border-radius: 3px;
  background: var(--nf-red);
  color: #fff;
  font-size: 12.5px;
  font-weight: 700;
  letter-spacing: 2px;
  margin-bottom: 12px;
  box-shadow: 0 3px 12px rgba(229, 9, 20, 0.5);
}

.backdrop-title {
  margin: 0 0 10px;
  font-size: 32px;
  font-weight: 800;
  line-height: 1.25;
  letter-spacing: 1px;
  color: #fff;
  text-shadow: 0 2px 18px rgba(0, 0, 0, 0.6);
}

.backdrop-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.hero-chip {
  padding: 2px 12px;
  border: 1px solid rgba(255, 255, 255, 0.35);
  border-radius: 14px;
  font-size: 12px;
  line-height: 18px;
  color: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(2px);
}

.backdrop-desc {
  margin: 0 0 18px;
  max-width: 640px;
  font-size: 14px;
  line-height: 1.75;
  color: rgba(255, 255, 255, 0.82);
  text-shadow: 0 1px 8px rgba(0, 0, 0, 0.5);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.backdrop-actions {
  display: flex;
  gap: 12px;
}

.backdrop-actions .faved {
  border: 1px solid rgba(229, 9, 20, 0.6);
  color: #ff6b74;
}

/* ===== 元信息面板 ===== */
.info-panel {
  margin-top: 20px;
  background: var(--nf-bg-card);
  border: 1px solid var(--nf-border);
  border-radius: 8px;
  padding: 18px 24px;
}

.info-row {
  display: flex;
  gap: 16px;
  padding: 9px 0;
  font-size: 13.5px;
  line-height: 1.6;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.info-row:last-child {
  border-bottom: none;
}

.info-label {
  flex-shrink: 0;
  width: 72px;
  color: var(--nf-text-muted);
}

.info-value {
  flex: 1;
  min-width: 0;
  color: #e5e5e5;
  white-space: pre-wrap;
  word-break: break-all;
}

.info-value.path {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  font-size: 12.5px;
  color: var(--nf-text-secondary);
}

.info-value .chip {
  display: inline-block;
  margin-right: 6px;
  margin-bottom: 4px;
  padding: 1px 10px;
  border-radius: 10px;
  background: #26262b;
  border: 1px solid rgba(255, 255, 255, 0.1);
  font-size: 12px;
  line-height: 18px;
  color: rgba(255, 255, 255, 0.85);
}

@media (max-width: 700px) {
  .detail-page {
    padding: 16px 20px 36px;
  }

  .backdrop {
    height: 320px;
  }

  .backdrop-content {
    padding: 0 20px 24px;
  }

  .backdrop-title {
    font-size: 24px;
  }
}
</style>
