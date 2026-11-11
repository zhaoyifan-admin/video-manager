import { reactive, ref } from 'vue'

// ================= 封面截帧 / 时长缓存（Hero 与卡片共用） =================
// 后端 ffmpeg 缩略图优先，前端 Canvas 截帧兜底
// LRU 缓存上限 + Blob URL + 缩略分辨率，防止万级视频内存膨胀
const COVER_CACHE_MAX = 300
const COVER_THUMB_WIDTH = 640
const coverCache = ref({}) // { [videoId]: url }
const coverOrder = [] // 缓存插入顺序，用于淘汰最旧条目

const durationCache = reactive({}) // { [videoId]: 'mm:ss' }

export const formatDuration = (seconds) => {
  if (!Number.isFinite(seconds) || seconds <= 0) return ''
  const t = Math.round(seconds)
  const h = Math.floor(t / 3600)
  const m = Math.floor((t % 3600) / 60)
  const s = t % 60
  const mm = h > 0 ? String(m).padStart(2, '0') : String(m)
  const ss = String(s).padStart(2, '0')
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`
}

export const onMetaLoaded = (row, e) => {
  const text = formatDuration(e.target.duration)
  if (text) durationCache[row.id] = text
}

const captureByCanvas = (row) => {
  const video = document.createElement('video')
  video.muted = true
  video.preload = 'auto'
  video.playsInline = true
  video.src = /^https?:\/\//.test(row.filePath)
    ? row.filePath
    : `/api/videos/${row.id}/file`

  const cleanup = () => {
    video.removeAttribute('src')
    video.load()
  }
  const draw = () => {
    if (!video.videoWidth) {
      cleanup()
      return
    }
    try {
      // 缩放到缩略图尺寸，不存原始分辨率帧
      const scale = Math.min(1, COVER_THUMB_WIDTH / video.videoWidth)
      const canvas = document.createElement('canvas')
      canvas.width = Math.max(1, Math.round(video.videoWidth * scale))
      canvas.height = Math.max(1, Math.round(video.videoHeight * scale))
      canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height)
      canvas.toBlob((blob) => {
        if (!blob) return
        // LRU：超过上限时淘汰最早缓存的帧并释放其内存
        while (coverOrder.length >= COVER_CACHE_MAX) {
          const oldest = coverOrder.shift()
          if (oldest === row.id) continue
          const oldUrl = coverCache.value[oldest]
          if (oldUrl) URL.revokeObjectURL(oldUrl)
          delete coverCache.value[oldest]
        }
        coverCache.value[row.id] = URL.createObjectURL(blob)
        coverOrder.push(row.id)
      }, 'image/jpeg', 0.72)
    } catch {
      // 外链跨域等场景截帧失败，保留占位封面
    }
    cleanup()
  }

  video.addEventListener('error', cleanup, { once: true })
  video.addEventListener('loadedmetadata', () => {
    // 取约 10% 进度处的画面（跳过片头黑屏），上限 5 秒
    if (!isFinite(video.duration)) return
    video.currentTime = Math.min(Math.max(video.duration * 0.1, 0.1), 5)
  })
  video.addEventListener('seeked', draw, { once: true })
  video.addEventListener('loadeddata', () => {
    // 无时长信息（部分流媒体）时直接取首帧
    if (!isFinite(video.duration) && coverCache.value[row.id] === undefined) draw()
  })
}

const pendingRetry = {} // { [videoId]: 已重试次数 }

export const captureCover = async (row) => {
  if (coverCache.value[row.id] !== undefined || !row.filePath) return
  // 外链视频无法由后端抽帧，直接走前端截帧
  if (/^https?:\/\//.test(row.filePath)) return captureByCanvas(row)

  // 后端改为「占位图 + 后台异步生成」：先读响应头判断是否仍在生成中
  const url = `/api/videos/${row.id}/thumb`
  try {
    const res = await fetch(url, { cache: 'no-store' })
    if (!res.ok) return captureByCanvas(row)
    if (res.headers.get('X-Thumb-Pending') === '1') {
      const n = (pendingRetry[row.id] || 0) + 1
      pendingRetry[row.id] = n
      if (n <= 4) setTimeout(() => captureCover(row), n * 1500)
      else captureByCanvas(row) // 生成失败则退回前端截帧
      return
    }
    delete pendingRetry[row.id]
    coverCache.value[row.id] = url
  } catch {
    captureByCanvas(row)
  }
}

// 卡片进入可视区域（提前 200px）才开始截帧，避免一次性加载全部视频
export const vLazyCover = {
  mounted(el, binding) {
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          io.disconnect()
          captureCover(binding.value)
        }
      },
      { rootMargin: '200px' },
    )
    io.observe(el)
    el._coverIO = io
  },
  unmounted(el) {
    el._coverIO?.disconnect()
  },
}

// 卡片背景视频源：#t=1 让浏览器在 1s 处显示静帧（不播放）
export const mediaSrc = (row) => {
  const base = /^https?:\/\//.test(row.filePath)
    ? row.filePath
    : `/api/videos/${row.id}/file`
  return `${base}#t=1`
}

export function useCover() {
  return { coverCache, durationCache, captureCover, onMetaLoaded, mediaSrc }
}
