import axios, { type AxiosError, type AxiosRequestConfig } from 'axios'
import { VIDEO_API_BASE } from '@video-manager/shared'
import type {
  AuditLogItem, AuthConfig, CollectionItem, DirEntry, DriveItem, EngagementInfo, MediaInfo,
  NotificationItem, PageResult, PlaylistItem, ProgressInfo, TaxonomyRow, TypeItem, UserAccount,
  VideoItem, VideoListResult,
} from './types'

export { VIDEO_API_BASE }

const http = axios.create({
  baseURL: VIDEO_API_BASE,
  timeout: 10000,
})

// 后端契约：{code, msg, data}，code === 0 表示成功。
// 401（未登录/登录过期）时触发全局回调（main.ts 注册，跳转登录页）；
// 带 _skipAuthRedirect 标记的认证接口自身处理 401，不触发跳转
type VideoRequestConfig = AxiosRequestConfig & { _skipAuthRedirect?: boolean }

let onUnauthorized: (() => void) | null = null
export const setUnauthorizedHandler = (fn: (() => void) | null): void => {
  onUnauthorized = fn
}

http.interceptors.response.use(
  (resp) => {
    const body = resp.data as { code?: number; msg?: string; data?: unknown } | null
    if (body && body.code === 0) return body.data as never
    return Promise.reject(new Error(body?.msg || '请求失败'))
  },
  (err: AxiosError<{ msg?: string }>) => {
    const config = err.config as VideoRequestConfig | undefined
    if (err.response?.status === 401 && !config?._skipAuthRedirect) {
      onUnauthorized?.()
    }
    return Promise.reject(new Error(err.response?.data?.msg || '网络错误，请确认后端服务已启动'))
  },
)

const request = <T>(config: VideoRequestConfig): Promise<T> =>
  http.request<T>(config) as unknown as Promise<T>

// ---------- 认证 ----------
export const register = (username: string, password: string): Promise<UserAccount> =>
  request<UserAccount>({ url: '/auth/register', method: 'POST', data: { username, password }, _skipAuthRedirect: true })
export const login = (username: string, password: string): Promise<UserAccount> =>
  request<UserAccount>({ url: '/auth/login', method: 'POST', data: { username, password }, _skipAuthRedirect: true })
export const logout = (): Promise<void> =>
  request<void>({ url: '/auth/logout', method: 'POST', _skipAuthRedirect: true })
export const getMe = (): Promise<UserAccount> =>
  request<UserAccount>({ url: '/auth/me', method: 'GET', _skipAuthRedirect: true })
// 公开运行配置（注册开关 / 单用户配额）
export const getAuthConfig = (): Promise<AuthConfig> =>
  request<AuthConfig>({ url: '/auth/config', method: 'GET', _skipAuthRedirect: true })

// 注册用户名实时防重检测：返回 {available, message}
export const checkUsername = (username: string): Promise<{ available: boolean; message: string }> =>
  request<{ available: boolean; message: string }>({
    url: '/auth/check-username', method: 'GET', params: { username }, _skipAuthRedirect: true,
  })

// 修改本人密码：传入当前密码与新密码，后端校验后更新
export const changePassword = (oldPassword: string, newPassword: string): Promise<void> =>
  request<void>({ url: '/auth/change-password', method: 'POST', data: { oldPassword, newPassword } })

// 上传头像图片（不设超时）；返回 {avatar: 相对路径}
export const uploadAvatar = (file: File): Promise<{ avatar: string }> => {
  const formData = new FormData()
  formData.append('file', file)
  return request<{ avatar: string }>({
    url: '/auth/avatar',
    method: 'POST',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 0,
  })
}

// 当前登录用户头像图片地址（GET 端点按登录态返回本人头像）；t 用于上传后破除浏览器缓存
export const avatarUrl = (t: number = Date.now()): string => `${VIDEO_API_BASE}/auth/avatar?t=${t}`

// ---------- 标签（只读；发布 / 审核 / 管理已移至主系统控制台） ----------
// 标签栏 / 筛选专用：后端按会话角色返回可见集合（超管含未发布 + badge，其他角色仅已发布）
export const listVisibleTags = (): Promise<TaxonomyRow[]> =>
  request<TaxonomyRow[]>({ url: '/tags/visible', method: 'GET' })
// 视频表单用：审核角色全量，普通用户为已发布 + 自己提交的
export const listTags = (): Promise<TaxonomyRow[]> =>
  request<TaxonomyRow[]>({ url: '/tags', method: 'GET' })

// ---------- 影视类型（提交新类型保留，审核 / 管理已移至主系统控制台） ----------
export const listTypes = (): Promise<TypeItem[]> =>
  request<TypeItem[]>({ url: '/types', method: 'GET' })
export const createType = (name: string, isPublished = false): Promise<TypeItem> =>
  request<TypeItem>({ url: '/types', method: 'POST', data: { name, isPublished } })

// ---------- 视频 ----------
export const listVideos = (params: Record<string, unknown> = {}): Promise<VideoListResult> =>
  request<VideoListResult>({ url: '/videos', method: 'GET', params })
export const getVideo = (id: number | string): Promise<VideoItem> =>
  request<VideoItem>({ url: `/videos/${id}`, method: 'GET' })
export const createVideo = (data: Record<string, unknown>): Promise<VideoItem> =>
  request<VideoItem>({ url: '/videos', method: 'POST', data })
export const updateVideo = (id: number, data: Record<string, unknown>): Promise<VideoItem> =>
  request<VideoItem>({ url: `/videos/${id}`, method: 'PUT', data })
export interface DeleteVideoResult { fileDeleted: boolean; fileMissing: boolean }
export const deleteVideo = (id: number): Promise<DeleteVideoResult> =>
  request<DeleteVideoResult>({ url: `/videos/${id}`, method: 'DELETE' })

// 大图轮播：按热度（播放次数 + 收藏人数×5）取最多 9 条已过审可见视频
export const getFeaturedVideos = (): Promise<{ items: VideoItem[] }> =>
  request<{ items: VideoItem[] }>({ url: '/videos/featured', method: 'GET' })
// 打开播放页上报一次点击/播放（用于热度统计）
export const recordView = (id: number): Promise<void> =>
  request<void>({ url: `/videos/${id}/view`, method: 'POST' })

// 切换收藏状态（按当前用户记录，返回 {isFavorite, favoriteCount}）
export const toggleFavorite = (id: number): Promise<{ isFavorite: boolean; favoriteCount: number }> =>
  request<{ isFavorite: boolean; favoriteCount: number }>({ url: `/videos/${id}/favorite`, method: 'POST' })

// ===== 影片互动：评分 / 想看清单 / 相关推荐（与收藏相互独立） =====
export const getEngagement = (id: number): Promise<EngagementInfo> =>
  request<EngagementInfo>({ url: `/videos/${id}/engagement`, method: 'GET' })
export const rateVideo = (id: number, score: number): Promise<EngagementInfo> =>
  request<EngagementInfo>({ url: `/videos/${id}/rating`, method: 'PUT', data: { score } })
export const toggleWantToWatch = (id: number): Promise<EngagementInfo> =>
  request<EngagementInfo>({ url: `/videos/${id}/watchlist`, method: 'POST' })
export const getRecommendations = (id: number, limit = 8): Promise<{ items: VideoItem[] }> =>
  request<{ items: VideoItem[] }>({ url: `/videos/${id}/recommendations`, method: 'GET', params: { limit } })

// 切换公开状态（设为公开后所有用户可观看，需先通过审核）
export const togglePublic = (id: number): Promise<VideoItem> =>
  request<VideoItem>({ url: `/videos/${id}/public`, method: 'POST' })

// 审核留痕：单条视频的完整时间线（本人或超管可查）
export const getAuditLogs = (id: number): Promise<PageResult<AuditLogItem>> =>
  request<PageResult<AuditLogItem>>({ url: `/videos/${id}/audit-logs`, method: 'GET' })

// ---------- 保存路径（外接硬盘 / 目录浏览 / 新建文件夹） ----------
export const listDrives = (): Promise<DriveItem[]> =>
  request<DriveItem[]>({ url: '/paths/drives', method: 'GET' })
export interface DirListResult { path: string; parent: string | null; folders: string[] }
export const listDir = (dir: string): Promise<DirListResult> =>
  request<DirListResult>({ url: '/paths/list', method: 'GET', params: { dir } })
export const makeDir = (parent: string, name: string): Promise<DirEntry> =>
  request<DirEntry>({ url: '/paths/mkdir', method: 'POST', data: { parent, name } })

// 上传视频文件（大文件，不设超时）；saveDir 为自定义保存目录（绝对路径），fileName 可自定义保存文件名
export const uploadVideoFile = (file: File, saveDir?: string, fileName?: string): Promise<VideoItem> => {
  const formData = new FormData()
  formData.append('file', file)
  if (saveDir) formData.append('saveDir', saveDir)
  if (fileName) formData.append('fileName', fileName)
  return request<VideoItem>({
    url: '/videos/upload',
    method: 'POST',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 0,
  })
}

// 批量导入视频
export interface BatchImportResult { success: number; failed: Array<{ index: number; msg: string }> }
export const batchImportVideos = (items: Array<Record<string, unknown>>): Promise<BatchImportResult> =>
  request<BatchImportResult>({ url: '/videos/batch', method: 'POST', data: { items }, timeout: 30000 })

// ---------- 观看进度 / 续播 ----------
export const getProgress = (id: number): Promise<ProgressInfo> =>
  request<ProgressInfo>({ url: `/videos/${id}/progress`, method: 'GET' })
export const saveProgress = (id: number, position: number, duration: number): Promise<void> =>
  request<void>({ url: `/videos/${id}/progress`, method: 'POST', data: { position, duration } })
export const getWatchHistory = (): Promise<PageResult<VideoItem>> =>
  request<PageResult<VideoItem>>({ url: '/watch-history', method: 'GET' })

// ---------- 审核结果通知 ----------
export const getUnreadCount = (): Promise<{ count: number }> =>
  request<{ count: number }>({ url: '/notifications/unread-count', method: 'GET' })
export const getNotifications = (): Promise<NotificationItem[]> =>
  request<NotificationItem[]>({ url: '/notifications', method: 'GET' })
export const markNotificationsRead = (ids: number[]): Promise<void> =>
  request<void>({ url: '/notifications/read', method: 'POST', data: { ids } })
// 播放页编码兼容探测（MKV / HEVC 等浏览器不支持时给出明确原因）
export const getMediaInfo = (id: number): Promise<MediaInfo> =>
  request<MediaInfo>({ url: `/videos/${id}/media-info`, method: 'GET' })

// ---------- 合集（只读，供视频筛选下拉；管理已移至主系统控制台） ----------
export const listCollections = (): Promise<{ items: CollectionItem[] }> =>
  request<{ items: CollectionItem[] }>({ url: '/collections', method: 'GET' })

// ---------- 用户自建片单（与系统合集隔离） ----------
export const listPlaylists = (): Promise<{ items: PlaylistItem[] }> =>
  request<{ items: PlaylistItem[] }>({ url: '/playlists', method: 'GET' })
export const createPlaylist = (name: string, description = ''): Promise<PlaylistItem> =>
  request<PlaylistItem>({ url: '/playlists', method: 'POST', data: { name, description } })
export const updatePlaylist = (id: number, name: string, description = ''): Promise<PlaylistItem> =>
  request<PlaylistItem>({ url: `/playlists/${id}`, method: 'PUT', data: { name, description } })
export const deletePlaylist = (id: number): Promise<void> =>
  request<void>({ url: `/playlists/${id}`, method: 'DELETE' })
export const addVideoToPlaylist = (playlistId: number, videoId: number): Promise<void> =>
  request<void>({ url: `/playlists/${playlistId}/videos`, method: 'POST', data: { videoId } })
export const removeVideoFromPlaylist = (playlistId: number, videoId: number): Promise<void> =>
  request<void>({ url: `/playlists/${playlistId}/videos/${videoId}`, method: 'DELETE' })
// 返回当前用户片单列表，并标注每个片单是否已含该视频（用于勾选态）
export const getPlaylistsForVideo = (videoId: number): Promise<{ items: Array<PlaylistItem & { added: boolean }> }> =>
  request<{ items: Array<PlaylistItem & { added: boolean }> }>({ url: `/playlists/for-video/${videoId}`, method: 'GET' })
