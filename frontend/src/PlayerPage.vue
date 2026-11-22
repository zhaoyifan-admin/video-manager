<template>
  <!-- Netflix 风格播放页 -->
  <div class="player-page">
    <!-- 顶栏：返回 + 标题 + 收藏 -->
    <header class="page-header">
      <button class="back-btn" @click="goBack">
        <FaIcon :icon="ICONS.back" :fixed="false" class="text-[16px]" />
        返回
      </button>
      <div class="page-title" :title="video?.title">{{ video?.title || '加载中…' }}</div>
      <button
        v-if="video"
        class="fav-btn"
        :class="{ active: castOpen }"
        title="一键投屏"
        @click="castOpen = !castOpen"
      >
        <FaIcon :icon="ICONS.cast" :fixed="false" class="text-[18px]" />
      </button>
      <button
        v-if="video"
        class="fav-btn"
        :class="{ active: video.isFavorite }"
        :title="video.isFavorite ? '取消收藏' : '收藏'"
        @click="toggleFav"
      >
        <FaIcon :icon="ICONS.fav" :variant="video.isFavorite ? 'solid' : 'regular'" :fixed="false" class="text-[18px]" />
      </button>
    </header>

    <!-- 加载失败 -->
    <div v-if="error" class="error-panel">
      <div class="error-icon">⚠</div>
      <div class="error-title">{{ error }}</div>
      <div class="error-sub">请确认后端服务已启动、视频记录存在</div>
      <button class="nf-btn red" @click="goBack"><FaIcon :icon="ICONS.back" :fixed="false" />返回列表</button>
    </div>

    <!-- 播放器与信息 -->
    <template v-else-if="video">
      <!-- 一键投屏：优先调用浏览器远程播放 API，无设备时降级为可复制的播放链接 -->
      <div v-if="castOpen" class="mb-4 rounded-xl border border-nf-line bg-nf-elevated px-5 py-4">
        <div class="mb-2 flex items-center gap-2 text-[15px] font-bold text-nf-text">
          <FaIcon :icon="ICONS.cast" :fixed="false" class="text-nf-red" />一键投屏
        </div>
        <p class="mb-3 text-[12.5px] leading-relaxed text-nf-sub">
          浏览器检测到同网投屏设备时可直接推送播放；也可复制下方链接，在电视或另一台设备的浏览器里打开。
        </p>
        <button class="nf-btn red mb-3" @click="promptCast">
          <FaIcon :icon="ICONS.cast" :fixed="false" />搜索投屏设备
        </button>
        <div class="flex flex-wrap items-center gap-2">
          <input
            id="cast-url"
            class="nf-input min-w-[220px] flex-1"
            :value="castUrl"
            readonly
            aria-label="投屏播放链接"
          />
          <button class="nf-btn ghost shrink-0" @click="copyCastUrl">
            <FaIcon :icon="ICONS.copy" :fixed="false" />复制链接
          </button>
          <button class="nf-btn ghost shrink-0" @click="openCastLink">
            <FaIcon icon="up-right-from-square" :fixed="false" />新窗口打开
          </button>
        </div>
        <p class="mt-3 text-[11.5px] leading-relaxed text-nf-muted">
          本地文件走本站流式接口，跨设备打开需先在本站登录；外链视频则直接跳转到原始地址。
        </p>
      </div>

      <!-- 外链且非直链视频文件：提供直跳按钮 -->
      <div v-if="!isDirectFile" class="link-panel">
        <div class="link-title">外部播放链接</div>
        <div class="link-text" :title="video.filePath">{{ video.filePath }}</div>
        <div class="link-desc">该链接为网页或外站地址，浏览器无法内嵌播放，点击下方按钮跳转播放。</div>
        <button class="nf-btn red lg" @click="openLink"><FaIcon icon="up-right-from-square" :fixed="false" />打开播放链接</button>
      </div>

      <div v-else class="player-wrap">
        <!-- 播放失败：优先解释编码不兼容（MKV / HEVC 等浏览器无法原生解码） -->
        <div v-if="playError" class="compat-panel">
          <div class="compat-icon">⚠</div>
          <div class="compat-title">浏览器无法直接播放该视频</div>
          <div v-if="mediaInfo?.available && !mediaInfo.compatible" class="compat-detail">
            容器 <b>{{ mediaInfo.container }}</b> · 视频编码 <b>{{ mediaInfo.videoCodecs.join(' / ') || '未知' }}</b>
            · 音频编码 <b>{{ mediaInfo.audioCodecs.join(' / ') || '未知' }}</b>。<br />
            浏览器原生仅支持 H.264 / VP8 / VP9 / AV1 视频与 AAC / MP3 / Opus 音频，
            建议先转码为 MP4（H.264 + AAC）后重新入库。
          </div>
          <div v-else class="compat-detail">
            请确认源文件存在、外接硬盘已挂载，且文件路径在允许的媒体目录内；也可在「站点管理 → 存储体检」中检查。
          </div>
          <button class="nf-btn red" @click="goBack"><FaIcon :icon="ICONS.back" :fixed="false" />返回列表</button>
        </div>
        <video
          v-else-if="videoSrc"
          ref="playerEl"
          :key="videoSrc"
          :src="videoSrc"
          :autoplay="autoPlay"
          controls
          class="page-player"
          @loadedmetadata="onMeta"
          @timeupdate="onTimeUpdate"
          @ended="onEnded"
          @error="onVideoError"
        >
          <track
            v-if="video.subtitlePath"
            :src="`/api/videos/${video.id}/subtitle`"
            kind="subtitles"
            srclang="zh"
            label="字幕"
            default
          />
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
import { ICONS } from './composables/icons'
import FaIcon from './ui/FaIcon.vue'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from './ui/toast'
import {
  getVideo, toggleFavorite, recordView, getProgress, saveProgress, getMediaInfo,
} from './api'

const route = useRoute()
const router = useRouter()

const video = ref(null)
const error = ref('')
const playError = ref(false)
const mediaInfo = ref(null)
const playerEl = ref(null)
let lastReport = 0

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

// ================= 一键投屏 =================
// 优先用标准 Remote Playback API（Chrome/Edge 可唤起 Chromecast 等本机可见设备）；
// 浏览器不支持或没有设备时，降级为「同源播放链接」供电视端浏览器直接打开。
const castOpen = ref(false)
const castUrl = computed(() => {
  const src = videoSrc.value
  if (!src) return ''
  return /^https?:\/\//.test(src) ? src : `${window.location.origin}${src}`
})

const promptCast = async () => {
  const el = playerEl.value
  if (!el?.remote?.prompt) {
    showToast.error('当前浏览器不支持系统投屏，请改用下方播放链接')
    return
  }
  try {
    await el.remote.prompt()
    showToast('已发起投屏，请在设备上确认')
  } catch {
    showToast.error('未找到可用投屏设备，可使用下方链接在电视端打开')
  }
}

const copyCastUrl = async () => {
  try {
    await navigator.clipboard.writeText(castUrl.value)
    showToast('投屏链接已复制')
  } catch {
    // 非安全上下文里 Clipboard API 不可用：退回选中输入框 + 传统复制
    const input = document.getElementById('cast-url')
    input?.select()
    document.execCommand?.('copy')
    showToast('投屏链接已复制')
  }
}

const openCastLink = () => window.open(castUrl.value, '_blank')

const load = async () => {
  error.value = ''
  playError.value = false
  mediaInfo.value = null
  video.value = null
  try {
    video.value = await getVideo(route.params.id)
    document.title = `${video.value.title} - 视频播放`
  } catch (e) {
    error.value = e.message
  }
}

// ================= 续播 / 进度上报 =================
const clock = (s) => {
  const t = Math.max(0, Math.floor(Number(s) || 0))
  return `${String(Math.floor(t / 60)).padStart(2, '0')}:${String(t % 60).padStart(2, '0')}`
}

const onMeta = async (e) => {
  const el = e.target
  if (!video.value || !el.duration) return
  try {
    const p = await getProgress(video.value.id)
    if (p.position > 0 && p.position < el.duration - 2) {
      el.currentTime = p.position
      showToast(`已从 ${clock(p.position)} 继续播放`)
    }
  } catch {
    // 进度读取失败不影响播放
  }
}

const report = (position, duration) => {
  if (!video.value) return
  saveProgress(video.value.id, position, duration).catch(() => {})
}

const onTimeUpdate = (e) => {
  const now = Date.now()
  if (now - lastReport < 10000) return // 每 10 秒上报一次，避免频繁写库
  lastReport = now
  report(e.target.currentTime, e.target.duration)
}

const onEnded = (e) => report(e.target.duration, e.target.duration)

const onVideoError = async () => {
  playError.value = true
  if (!video.value) return
  try {
    mediaInfo.value = await getMediaInfo(video.value.id)
  } catch {
    // 探测失败也能给出通用提示
  }
}

// 离开页面时用 keepalive 补报最后一次进度，避免最后 10 秒丢失
onBeforeUnmount(() => {
  const el = playerEl.value
  if (!el || !video.value || !el.duration) return
  fetch(`/api/videos/${video.value.id}/progress`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ position: el.currentTime, duration: el.duration }),
    keepalive: true,
  }).catch(() => {})
})

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

// 打开播放页即视为一次播放：上报点击量（统计失败不影响播放）
onMounted(async () => {
  await load()
  if (video.value) {
    try {
      await recordView(video.value.id)
    } catch {
      // 热度统计属于旁路，不打断视频加载
    }
  }
})
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
  background: var(--nf-overlay);
  color: var(--nf-text-primary);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.18s ease;
}

.back-btn:hover {
  background: var(--nf-overlay-strong);
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
  background: var(--nf-overlay);
  color: var(--nf-text-secondary);
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
  color: var(--nf-text-primary);
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

/* 编码不兼容说明 */
.compat-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  min-height: 320px;
  padding: 56px 32px;
  text-align: center;
}

.compat-icon {
  font-size: 36px;
}

.compat-title {
  font-size: 17px;
  font-weight: 700;
  color: var(--nf-text-primary);
}

.compat-detail {
  max-width: 720px;
  font-size: 13.5px;
  line-height: 1.9;
  color: var(--nf-text-secondary);
}

.compat-detail b {
  color: var(--nf-text-primary);
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
  background: var(--nf-bg-elevated);
  color: var(--nf-text-primary);
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
  color: var(--nf-text-secondary);
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
  color: var(--nf-text-primary);
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
  color: var(--nf-text-secondary);
  margin-bottom: 20px;
}

@media (max-width: 700px) {
  .player-page {
    padding: 16px 20px 36px;
  }
}
</style>
