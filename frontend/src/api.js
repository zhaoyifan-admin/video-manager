import axios from 'axios'

// 统一走 vite 代理（开发态）或同源部署（生产态）
const http = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

// 后端契约：{code, msg, data}，code === 0 表示成功
// 401（未登录/登录过期）时触发全局回调（main.js 注册，跳转登录页）；
// 带 _skipAuthRedirect 标记的认证接口自身处理 401，不触发跳转
let onUnauthorized = null
export const setUnauthorizedHandler = (fn) => {
  onUnauthorized = fn
}

http.interceptors.response.use(
  (resp) => {
    const body = resp.data
    if (body && body.code === 0) return body.data
    return Promise.reject(new Error(body?.msg || '请求失败'))
  },
  (err) => {
    if (err.response?.status === 401 && !err.config?._skipAuthRedirect) {
      onUnauthorized?.()
    }
    return Promise.reject(new Error(err.response?.data?.msg || '网络错误，请确认后端服务已启动'))
  },
)

// ---------- 认证 ----------
export const register = (username, password) =>
  http.post('/auth/register', { username, password }, { _skipAuthRedirect: true })
export const login = (username, password) =>
  http.post('/auth/login', { username, password }, { _skipAuthRedirect: true })
export const logout = () => http.post('/auth/logout', null, { _skipAuthRedirect: true })
export const getMe = () => http.get('/auth/me', { _skipAuthRedirect: true })
// 公开运行配置（注册开关 / 单用户配额）
export const getAuthConfig = () => http.get('/auth/config', { _skipAuthRedirect: true })
// 超管：账号列表与角色分配（user / manager / reviewer / admin）
export const listUsers = () => http.get('/auth/users')
export const setUserRole = (id, role) => http.post(`/auth/users/${id}/role`, { role })
export const createUser = (username, password, role) =>
  http.post('/auth/users', { username, password, role })

// 注册用户名实时防重检测：返回 {available, message}
export const checkUsername = (username) =>
  http.get('/auth/check-username', { params: { username }, _skipAuthRedirect: true })

// ---------- 标签（增删改仅超管，普通用户只读已发布标签） ----------
export const listTags = () => http.get('/tags')
export const createTag = (name) => http.post('/tags', { name })
export const updateTag = (id, data) => http.put(`/tags/${id}`, data)
export const deleteTag = (id) => http.delete(`/tags/${id}`)

// ---------- 影视类型 ----------
export const listTypes = () => http.get('/types')
export const createType = (name) => http.post('/types', { name })
export const deleteType = (id) => http.delete(`/types/${id}`)

// ---------- 视频 ----------
export const listVideos = (params) => http.get('/videos', { params })
export const getVideo = (id) => http.get(`/videos/${id}`)
export const createVideo = (data) => http.post('/videos', data)
export const updateVideo = (id, data) => http.put(`/videos/${id}`, data)
export const deleteVideo = (id) => http.delete(`/videos/${id}`)

// 大图轮播：按热度（播放次数 + 收藏人数×5）取最多 9 条已过审可见视频
export const getFeaturedVideos = () => http.get('/videos/featured')
// 打开播放页上报一次点击/播放（用于热度统计）
export const recordView = (id) => http.post(`/videos/${id}/view`)

// 切换收藏状态（按当前用户记录，返回 {isFavorite, favoriteCount}）
export const toggleFavorite = (id) => http.post(`/videos/${id}/favorite`)

// 切换公开状态（设为公开后所有用户可观看，需先通过审核）
export const togglePublic = (id) => http.post(`/videos/${id}/public`)

// 管理员审核：status 1 通过 / 2 驳回（驳回必须带 reason，会展示给上传用户）
export const auditVideo = (id, status, reason = '') =>
  http.post(`/videos/${id}/audit`, { status, reason })

// 审核留痕：单条视频的完整时间线（本人或超管可查）
export const getAuditLogs = (id) => http.get(`/videos/${id}/audit-logs`)
// 审核留痕：全局流水（仅超管，支持 keyword / action / page / pageSize）
export const listAuditLogs = (params) => http.get('/audit-logs', { params })

// ---------- 保存路径（外接硬盘 / 目录浏览 / 新建文件夹） ----------
export const listDrives = () => http.get('/paths/drives')
export const listDir = (dir) => http.get('/paths/list', { params: { dir } })
export const makeDir = (parent, name) => http.post('/paths/mkdir', { parent, name })

// 上传视频文件（大文件，不设超时）；saveDir 为自定义保存目录（绝对路径），fileName 可自定义保存文件名
export const uploadVideoFile = (file, saveDir, fileName) => {
  const formData = new FormData()
  formData.append('file', file)
  if (saveDir) formData.append('saveDir', saveDir)
  if (fileName) formData.append('fileName', fileName)
  return http.post('/videos/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 0,
  })
}

// 批量导入视频
export const batchImportVideos = (items) => http.post('/videos/batch', { items }, { timeout: 30000 })

// ---------- 观看进度 / 续播 ----------
export const getProgress = (id) => http.get(`/videos/${id}/progress`)
export const saveProgress = (id, position, duration) =>
  http.post(`/videos/${id}/progress`, { position, duration })
export const getWatchHistory = () => http.get('/watch-history')

// ---------- 审核结果通知 ----------
export const getUnreadCount = () => http.get('/notifications/unread-count')
export const getNotifications = () => http.get('/notifications')
export const markNotificationsRead = (ids) => http.post('/notifications/read', { ids })
// 播放页编码兼容探测（MKV / HEVC 等浏览器不支持时给出明确原因）
export const getMediaInfo = (id) => http.get(`/videos/${id}/media-info`)

// ---------- 存储体检 / 路径重定位 ----------
export const getIntegrity = () => http.get('/videos/integrity')
export const relocateVideos = (oldPrefix, newPrefix, dryRun = true) =>
  http.post('/videos/relocate', { oldPrefix, newPrefix, dryRun })

// ---------- 合集 ----------
export const listCollections = () => http.get('/collections')
export const createCollection = (name, description = '') =>
  http.post('/collections', { name, description })
export const deleteCollection = (id) => http.delete(`/collections/${id}`)

// ---------- 管理员看板 ----------
export const getAdminOverview = () => http.get('/admin/overview')
