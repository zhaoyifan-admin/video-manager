// 视频子系统业务类型。
// 说明：后端返回字段较多且各版本会追加字段，核心字段显式声明，其余用索引签名兜底，
// 既保留类型提示又避免旧数据/新增字段造成大面积类型回归。

export interface VideoItem {
  id: number
  title: string
  filePath: string
  subtitlePath?: string
  description?: string
  cover?: string
  typeId?: number
  tagIds?: number[]
  tags?: string[]
  collectionId?: number
  auditStatus?: number
  isPublished?: boolean
  isMine?: boolean
  views?: number
  favoriteCount?: number
  rating?: number
  duration?: number
  region?: string
  language?: string
  year?: number
  letter?: string
  ownerId?: number
  createdAt?: string
  updatedAt?: string
  [key: string]: any
}

export interface TaxonomyRow {
  id: number
  name: string
  auditStatus?: number
  isPublished?: boolean
  isMine?: boolean
  description?: string
  createdAt?: string
  [key: string]: any
}

export type TagItem = TaxonomyRow
export type TypeItem = TaxonomyRow
export type CollectionItem = TaxonomyRow

export interface PlaylistItem {
  id: number
  name: string
  description?: string
  hasVideo?: boolean
  videoCount?: number
  [key: string]: any
}

export interface PageResult<T> {
  items: T[]
  total: number
  [key: string]: any
}

export interface VideoListResult extends PageResult<VideoItem> {}

export interface UserAccount {
  id: number
  username: string
  role: string
  avatar?: string
  createdAt?: string
  [key: string]: any
}

export interface AuthConfig {
  registrationEnabled: boolean
  maxVideosPerUser: number
  [key: string]: any
}

export interface ProgressInfo {
  position: number
  duration: number
  [key: string]: any
}

export interface EngagementInfo {
  rating?: number
  /** 详情页：平均分 */
  avgScore?: number
  ratingCount?: number
  /** 详情页：我的评分 */
  myScore?: number
  favoriteCount?: number
  wantCount?: number
  isFavorite?: boolean
  isWant?: boolean
  /** 详情页：是否加入想看清单 */
  isWantToWatch?: boolean
  [key: string]: any
}

export interface MediaInfo {
  codec?: string
  format?: string
  duration?: number
  browserSupported?: boolean
  reason?: string
  [key: string]: any
}

export interface AuditLogItem {
  id: number
  videoId?: number
  targetId?: number
  targetName?: string
  action?: string
  reason?: string
  operator?: string
  createdAt?: string
  [key: string]: any
}

export interface AdminLogItem extends AuditLogItem {
  targetType?: string
  days?: number
}

export interface NotificationItem {
  id: number
  title?: string
  content?: string
  isRead?: boolean
  createdAt?: string
  [key: string]: any
}

export interface DriveItem {
  name: string
  path: string
  [key: string]: any
}

export interface DirEntry {
  name: string
  path: string
  isDir: boolean
  [key: string]: any
}

export interface IntegrityResult {
  total?: number
  missing: Array<{ id: number; title: string; filePath: string; [key: string]: any }>
  roots: string[]
  [key: string]: any
}

export interface AdminOverview {
  stats?: Record<string, number>
  viewTrend?: Array<{ date: string; views: number; [key: string]: any }>
  hotTags?: Array<TaxonomyRow>
  storageGrowth?: {
    points: Array<{ date: string; cumulativeBytes: number; totalBytes: number; totalVideos: number; [key: string]: any }>
    unmeasured: number
    [key: string]: any
  }
  [key: string]: any
}

export interface QueryState {
  keyword: string
  tagId: number
  typeId: number
  favorite: number
  wantlist: number
  sort: string
  collectionId: number
  ownerId: number
  playlistId: number
  region: string
  language: string
  year: number
  letter: string
  page: number
  pageSize: number
  [key: string]: any
}

export type PageItem = number | '…'
