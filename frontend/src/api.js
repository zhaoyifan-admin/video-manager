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

// 修改本人密码：传入当前密码与新密码，后端校验后更新
export const changePassword = (oldPassword, newPassword) =>
  http.post('/auth/change-password', { oldPassword, newPassword })

// 上传头像图片（不设超时）；返回 {avatar: 相对路径}
export const uploadAvatar = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  return http.post('/auth/avatar', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 0,
  })
}

// 当前登录用户头像图片地址（GET 端点按登录态返回本人头像）；t 用于上传后破除浏览器缓存
export const avatarUrl = (t = Date.now()) => `/api/auth/avatar?t=${t}`

// ---------- 标签（普通用户可提交新标签，经管理员审核通过后发布） ----------
export const listTags = () => http.get('/tags')
// 新建标签：管理员传 isPublished=true 直接发布（免审通过），普通用户留空进入待审核
export const createTag = (name, isPublished = false) =>
  http.post('/tags', { name, isPublished })
// 管理员修改标签：{ name?, isPublished? }；isPublished 用于发布 / 取消发布（发布未通过条目会同步免审通过）
export const updateTag = (id, data) => http.put(`/tags/${id}`, data)
export const deleteTag = (id) => http.delete(`/tags/${id}`)
// 审核标签：action = 'approve' 通过 / 'reject' 驳回（驳回必带 reason）；复用视频审核权限
export const reviewTag = (id, action, reason = '') =>
  http.post(`/tags/${id}/review`, { action, reason })
// 创建者或管理员重新提交被驳回的标签
export const resubmitTag = (id) => http.post(`/tags/${id}/resubmit`)
// 单条标签的审核留痕（创建者或审核角色可查）
export const getTagLogs = (id) => http.get(`/tags/${id}/logs`)

// ---------- 影视类型（普通用户可提交新类型，经管理员审核通过后发布） ----------
export const listTypes = () => http.get('/types')
// 新建类型：管理员传 isPublished=true 直接发布（免审通过），普通用户留空进入待审核
export const createType = (name, isPublished = false) =>
  http.post('/types', { name, isPublished })
// 管理员修改影视类型：{ name?, isPublished? }；发布 / 取消发布同上
export const updateType = (id, data) => http.put(`/types/${id}`, data)
export const deleteType = (id) => http.delete(`/types/${id}`)
// 审核类型：action = 'approve' 通过 / 'reject' 驳回（驳回必带 reason）；复用视频审核权限
export const reviewType = (id, action, reason = '') =>
  http.post(`/types/${id}/review`, { action, reason })
// 创建者或管理员重新提交被驳回的类型
export const resubmitType = (id) => http.post(`/types/${id}/resubmit`)
// 单条类型的审核留痕（创建者或审核角色可查）
export const getTypeLogs = (id) => http.get(`/types/${id}/logs`)

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

// ===== 影片互动：评分 / 想看清单 / 相关推荐（与收藏相互独立） =====
export const getEngagement = (id) => http.get(`/videos/${id}/engagement`)
export const rateVideo = (id, score) => http.put(`/videos/${id}/rating`, { score })
export const toggleWantToWatch = (id) => http.post(`/videos/${id}/watchlist`)
export const getRecommendations = (id, limit = 8) =>
  http.get(`/videos/${id}/recommendations`, { params: { limit } })

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

// ---------- 合集（已接入审核模型，与标签 / 类型一致） ----------
// 列表保持 {items} 契约（供视频筛选下拉）；工作台需要纯数组，另给一个适配
export const listCollections = () => http.get('/collections')
export const listCollectionsForWorkbench = async () => (await listCollections()).items
export const createCollection = (name, description = '', isPublished = false) =>
  http.post('/collections', { name, description, isPublished })
// 工作台提交：管理员可传 isPublished 直接发布（免审通过），普通用户进入待审核
export const submitCollection = (name, isPublished = false) =>
  http.post('/collections', { name, isPublished })
export const updateCollection = (id, data) => http.put(`/collections/${id}`, data)
export const deleteCollection = (id) => http.delete(`/collections/${id}`)
export const reviewCollection = (id, action, reason = '') =>
  http.post(`/collections/${id}/review`, { action, reason })
export const resubmitCollection = (id) => http.post(`/collections/${id}/resubmit`)
export const getCollectionLogs = (id) => http.get(`/collections/${id}/logs`)

// ---------- 用户自建片单（与系统合集隔离） ----------
// 列表/创建/重命名/删除 + 加入/移除视频 + 查询某视频已在哪些片单
export const listPlaylists = () => http.get('/playlists')
export const createPlaylist = (name, description = '') =>
  http.post('/playlists', { name, description })
export const updatePlaylist = (id, name, description = '') =>
  http.put(`/playlists/${id}`, { name, description })
export const deletePlaylist = (id) => http.delete(`/playlists/${id}`)
export const addVideoToPlaylist = (playlistId, videoId) =>
  http.post(`/playlists/${playlistId}/videos`, { videoId })
export const removeVideoFromPlaylist = (playlistId, videoId) =>
  http.delete(`/playlists/${playlistId}/videos/${videoId}`)
// 返回当前用户片单列表，并标注每个片单是否已含该视频（用于勾选态）
export const getPlaylistsForVideo = (videoId) => http.get(`/playlists/for-video/${videoId}`)

// ---------- 管理员看板 / 操作审计 ----------
// overview 额外返回 viewTrend(近 14 天) / hotTags(Top8) / storageGrowth(近 30 天)
export const getAdminOverview = () => http.get('/admin/overview')
// 敏感管理动作流水（仅超管）：支持 keyword / action / targetType / days / page / pageSize
export const listAdminLogs = (params) => http.get('/admin-logs', { params })
