import axios, { type AxiosError, type AxiosRequestConfig } from 'axios'
import type { ApiResult, CurrentUser, MenuNode } from '@video-manager/shared'

// 平台接口统一挂在根 /api；视频子系统接口在 /video/api，不属于本前端。
const http = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

let onUnauthorized: (() => void) | null = null
export const setUnauthorizedHandler = (fn: (() => void) | null): void => {
  onUnauthorized = fn
}

// 契约：{ code, msg, data }，code === 0 表示成功。
http.interceptors.response.use(
  (resp) => {
    const body = resp.data as ApiResult<unknown>
    if (body && body.code === 0) return body.data as never
    return Promise.reject(new Error(body?.msg || '请求失败'))
  },
  (err: AxiosError<ApiResult<unknown>>) => {
    const config = err.config as (AxiosRequestConfig & { _skipAuthRedirect?: boolean }) | undefined
    if (err.response?.status === 401 && !config?._skipAuthRedirect) {
      onUnauthorized?.()
    }
    return Promise.reject(new Error(err.response?.data?.msg || '网络错误，请确认后端服务已启动'))
  },
)

const request = <T>(config: AxiosRequestConfig): Promise<T> =>
  http.request<T>(config) as unknown as Promise<T>

export interface AuthConfig {
  registrationEnabled: boolean
  maxVideosPerUser: number
}

export interface MenuResponse {
  items: MenuNode[]
}

export interface PermissionResponse {
  roles: string[]
  items: string[]
}

export const getAuthConfig = (): Promise<AuthConfig> =>
  request<AuthConfig>({ url: '/auth/config', method: 'GET', _skipAuthRedirect: true })

export const login = (username: string, password: string): Promise<CurrentUser> =>
  request<CurrentUser>({
    url: '/auth/login',
    method: 'POST',
    data: { username, password },
    _skipAuthRedirect: true,
  })

export const logout = (): Promise<void> =>
  request<void>({ url: '/auth/logout', method: 'POST', _skipAuthRedirect: true })

export const getMe = (): Promise<CurrentUser> =>
  request<CurrentUser>({ url: '/auth/me', method: 'GET', _skipAuthRedirect: true })

export const getSystemMenus = (): Promise<MenuResponse> =>
  request<MenuResponse>({ url: '/system/menus', method: 'GET' })

export const getSystemPermissions = (): Promise<PermissionResponse> =>
  request<PermissionResponse>({ url: '/system/permissions', method: 'GET' })

// ---------------- P1 组织与权限 ----------------
export interface PageResult<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
  pwdPolicy?: PasswordPolicy
}

export interface PasswordPolicy {
  minLength: number
  requireComplex: boolean
  historyLimit: number
  lockThreshold: number
  lockMinutes: number
  expireDays: number
}

export interface SystemUser {
  id: number
  username: string
  displayName: string
  phone: string
  email: string
  deptId: number
  deptName: string
  primaryRole: string
  roleCodes: string[]
  postNames: string
  enabled: boolean
  createdAt: string | null
  pwdUpdatedAt: string | null
  forcePwd: boolean
  locked: boolean
}

export interface UserPayload {
  username?: string
  password?: string
  displayName: string
  phone?: string
  email?: string
  deptId?: number
  enabled?: boolean
  forcePwd?: boolean
  roleCodes?: string[]
  postIds?: number[]
}

export interface SystemRole {
  id: number
  roleCode: string
  roleName: string
  dataScope: 'ALL' | 'DEPT' | 'DEPT_TREE' | 'SELF' | 'CUSTOM'
  sortNo: number
  enabled: boolean
  builtIn: boolean
  remark: string
  userCount: number
}

export interface MenuButton {
  id: number
  code: string
  desc: string
}

export interface MenuItem {
  id: number
  code: string
  parentId: number
  type: 'DIR' | 'MENU' | 'BUTTON'
  title: string
  path: string
  componentKey: string
  redirectPath: string
  icon: string
  permission: string
  linkUrl: string
  visible: boolean
  cache: boolean
  sortNo: number
  enabled: boolean
  buttons: MenuButton[]
  children: MenuItem[]
}

export interface DeptItem {
  id: number
  code: string
  parentId: number
  ancestorPath: string
  name: string
  leaderUserId: number
  sortNo: number
  enabled: boolean
  userCount: number
  children: DeptItem[]
}

export interface PostItem {
  id: number
  code: string
  name: string
  sortNo: number
  enabled: boolean
  remark: string
  userCount: number
}

export interface FormOptions {
  departments: Array<{ id: number; code: string; name: string }>
  posts: Array<{ id: number; code: string; name: string }>
  roles: Array<{ code: string; name: string; builtIn: boolean }>
}

export interface ImportResult {
  success: number
  failed: Array<{ row: number; reason: string }>
}

const query = (params: Record<string, unknown>): string => {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') search.append(key, String(value))
  })
  const text = search.toString()
  return text ? `?${text}` : ''
}

export const listUsers = (params: Record<string, unknown>): Promise<PageResult<SystemUser>> =>
  request<PageResult<SystemUser>>({ url: `/system/users${query(params)}`, method: 'GET' })

export const createUser = (data: UserPayload): Promise<{ id: number }> =>
  request<{ id: number }>({ url: '/system/users', method: 'POST', data })

export const updateUser = (id: number, data: UserPayload): Promise<{ id: number }> =>
  request<{ id: number }>({ url: `/system/users/${id}`, method: 'PUT', data })

export const deleteUser = (id: number): Promise<void> =>
  request<void>({ url: `/system/users/${id}`, method: 'DELETE' })

export const resetUserPassword = (id: number, password: string, forcePwd = false): Promise<void> =>
  request<void>({ url: `/system/users/${id}/reset-password`, method: 'POST', data: { password, forcePwd } })

export const importUsers = (file: File): Promise<ImportResult> => {
  const form = new FormData()
  form.append('file', file)
  return request<ImportResult>({
    url: '/system/users/import', method: 'POST', data: form,
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const exportUsersUrl = (params: Record<string, unknown>): string =>
  `/api/system/users/export${query(params)}`

export const userImportTemplateUrl = (): string => '/api/system/users/template'

export const listRoles = (params: Record<string, unknown>): Promise<PageResult<SystemRole>> =>
  request<PageResult<SystemRole>>({ url: `/system/roles${query(params)}`, method: 'GET' })

export const createRole = (data: Record<string, unknown>): Promise<{ id: number }> =>
  request<{ id: number }>({ url: '/system/roles', method: 'POST', data })

export const updateRole = (id: number, data: Record<string, unknown>): Promise<{ id: number }> =>
  request<{ id: number }>({ url: `/system/roles/${id}`, method: 'PUT', data })

export const deleteRole = (id: number): Promise<void> =>
  request<void>({ url: `/system/roles/${id}`, method: 'DELETE' })

export interface GrantedMenu {
  id: number
  code: string
  type: string
  title: string
  parentId: number
  permission: string
  granted: boolean
}

export const getRoleMenus = (id: number): Promise<{ items: GrantedMenu[] }> =>
  request<{ items: GrantedMenu[] }>({ url: `/system/roles/${id}/menus`, method: 'GET' })

export const assignRoleMenus = (id: number, menuIds: number[]): Promise<void> =>
  request<void>({ url: `/system/roles/${id}/menus`, method: 'PUT', data: { menuIds } })

export interface GrantedDept {
  id: number
  code: string
  name: string
  parentId: number
  granted: boolean
}

export const getRoleDepts = (id: number): Promise<{ items: GrantedDept[] }> =>
  request<{ items: GrantedDept[] }>({ url: `/system/roles/${id}/depts`, method: 'GET' })

export const assignRoleDepts = (id: number, deptIds: number[]): Promise<void> =>
  request<void>({ url: `/system/roles/${id}/depts`, method: 'PUT', data: { deptIds } })

export const listMenus = (): Promise<{ items: MenuItem[]; componentWhitelist: string[]; menuTypes: string[] }> =>
  request<{ items: MenuItem[]; componentWhitelist: string[]; menuTypes: string[] }>({ url: '/system/menus/tree', method: 'GET' })

export const createMenu = (data: Record<string, unknown>): Promise<{ id: number }> =>
  request<{ id: number }>({ url: '/system/menus', method: 'POST', data })

export const updateMenu = (id: number, data: Record<string, unknown>): Promise<{ id: number }> =>
  request<{ id: number }>({ url: `/system/menus/${id}`, method: 'PUT', data })

export const deleteMenu = (id: number): Promise<void> =>
  request<void>({ url: `/system/menus/${id}`, method: 'DELETE' })

export const listDepartments = (): Promise<{ items: DeptItem[] }> =>
  request<{ items: DeptItem[] }>({ url: '/system/departments', method: 'GET' })

export const createDepartment = (data: Record<string, unknown>): Promise<{ id: number }> =>
  request<{ id: number }>({ url: '/system/departments', method: 'POST', data })

export const updateDepartment = (id: number, data: Record<string, unknown>): Promise<{ id: number }> =>
  request<{ id: number }>({ url: `/system/departments/${id}`, method: 'PUT', data })

export const deleteDepartment = (id: number): Promise<void> =>
  request<void>({ url: `/system/departments/${id}`, method: 'DELETE' })

export const listPosts = (params: Record<string, unknown>): Promise<PageResult<PostItem>> =>
  request<PageResult<PostItem>>({ url: `/system/posts${query(params)}`, method: 'GET' })

export const createPost = (data: Record<string, unknown>): Promise<{ id: number }> =>
  request<{ id: number }>({ url: '/system/posts', method: 'POST', data })

export const updatePost = (id: number, data: Record<string, unknown>): Promise<{ id: number }> =>
  request<{ id: number }>({ url: `/system/posts/${id}`, method: 'PUT', data })

export const deletePost = (id: number): Promise<void> =>
  request<void>({ url: `/system/posts/${id}`, method: 'DELETE' })

export const getFormOptions = (): Promise<FormOptions> =>
  request<FormOptions>({ url: '/system/options', method: 'GET' })

export const getSecurityPolicy = (): Promise<PasswordPolicy> =>
  request<PasswordPolicy>({ url: '/system/security-policy', method: 'GET' })

// ---------------- P2 基础设施：字典 / 参数 / 通知公告 ----------------
export interface DictType {
  id: number
  code: string
  name: string
  enabled: boolean
  remark: string
  itemCount: number
}

export interface DictItem {
  id: number
  dictTypeId: number
  dictCode: string
  value: string
  label: string
  sortNo: number
  enabled: boolean
}

export interface DictOptionSet {
  code: string
  name: string
  items: Array<{ value: string; label: string }>
}

export interface ConfigItem {
  id: number
  key: string
  value: string
  group: string
  valueType: 'string' | 'number' | 'bool' | 'json'
  cache: boolean
  remark: string
  builtIn: boolean
}

export interface NoticeItem {
  id: number
  title: string
  contentMd: string
  noticeType: 'NOTICE' | 'ANNOUNCEMENT'
  publishAt: string | null
  withdrawAt: string | null
  status: 'DRAFT' | 'SCHEDULED' | 'PUBLISHED' | 'WITHDRAWN'
  publisherName: string
  readCount: number
}

export interface MyNoticeItem extends NoticeItem {
  read: boolean
}

export const listDictTypes = (params: Record<string, unknown>): Promise<PageResult<DictType>> =>
  request<PageResult<DictType>>({ url: `/system/dict-types${query(params)}`, method: 'GET' })

export const createDictType = (data: Record<string, unknown>): Promise<{ id: number }> =>
  request<{ id: number }>({ url: '/system/dict-types', method: 'POST', data })

export const updateDictType = (id: number, data: Record<string, unknown>): Promise<{ id: number }> =>
  request<{ id: number }>({ url: `/system/dict-types/${id}`, method: 'PUT', data })

export const deleteDictType = (id: number): Promise<void> =>
  request<void>({ url: `/system/dict-types/${id}`, method: 'DELETE' })

export const listDictItems = (params: Record<string, unknown>): Promise<PageResult<DictItem>> =>
  request<PageResult<DictItem>>({ url: `/system/dict-items${query(params)}`, method: 'GET' })

export const createDictItem = (data: Record<string, unknown>): Promise<{ id: number }> =>
  request<{ id: number }>({ url: '/system/dict-items', method: 'POST', data })

export const updateDictItem = (id: number, data: Record<string, unknown>): Promise<{ id: number }> =>
  request<{ id: number }>({ url: `/system/dict-items/${id}`, method: 'PUT', data })

export const deleteDictItem = (id: number): Promise<void> =>
  request<void>({ url: `/system/dict-items/${id}`, method: 'DELETE' })

export const getDictOptions = (dictCode?: string): Promise<{ items: DictOptionSet[] }> =>
  request<{ items: DictOptionSet[] }>({
    url: `/system/dict/options${query(dictCode ? { dictCode } : {})}`, method: 'GET',
  })

export const refreshDictCache = (): Promise<{ refreshed: boolean }> =>
  request<{ refreshed: boolean }>({ url: '/system/dict/refresh', method: 'POST' })

export const listConfigs = (params: Record<string, unknown>): Promise<PageResult<ConfigItem>> =>
  request<PageResult<ConfigItem>>({ url: `/system/configs${query(params)}`, method: 'GET' })

export const createConfig = (data: Record<string, unknown>): Promise<{ key: string }> =>
  request<{ key: string }>({ url: '/system/configs', method: 'POST', data })

export const updateConfig = (id: number, data: Record<string, unknown>): Promise<{ id: number }> =>
  request<{ id: number }>({ url: `/system/configs/${id}`, method: 'PUT', data })

export const deleteConfig = (id: number): Promise<void> =>
  request<void>({ url: `/system/configs/${id}`, method: 'DELETE' })

export const refreshConfigCache = (): Promise<{ refreshed: boolean }> =>
  request<{ refreshed: boolean }>({ url: '/system/configs/refresh', method: 'POST' })

export const listNotices = (params: Record<string, unknown>): Promise<PageResult<NoticeItem>> =>
  request<PageResult<NoticeItem>>({ url: `/system/notices${query(params)}`, method: 'GET' })

export const createNotice = (data: Record<string, unknown>): Promise<{ id: number }> =>
  request<{ id: number }>({ url: '/system/notices', method: 'POST', data })

export const updateNotice = (id: number, data: Record<string, unknown>): Promise<{ id: number }> =>
  request<{ id: number }>({ url: `/system/notices/${id}`, method: 'PUT', data })

export const deleteNotice = (id: number): Promise<void> =>
  request<void>({ url: `/system/notices/${id}`, method: 'DELETE' })

export const publishNotice = (id: number): Promise<{ id: number; status: string }> =>
  request<{ id: number; status: string }>({ url: `/system/notices/${id}/publish`, method: 'POST' })

export const withdrawNotice = (id: number): Promise<{ id: number; status: string }> =>
  request<{ id: number; status: string }>({ url: `/system/notices/${id}/withdraw`, method: 'POST' })

export const listMyNotices = (params: Record<string, unknown>): Promise<PageResult<MyNoticeItem>> =>
  request<PageResult<MyNoticeItem>>({ url: `/system/notices/mine${query(params)}`, method: 'GET' })

export const getUnreadNoticeCount = (): Promise<{ count: number }> =>
  request<{ count: number }>({ url: '/system/notices/unread-count', method: 'GET' })

export const markNoticeRead = (id: number): Promise<{ id: number; read: boolean }> =>
  request<{ id: number; read: boolean }>({ url: `/system/notices/${id}/read`, method: 'POST' })

// ---------------- P3 审计与数据范围 ----------------
export interface OperationLogItem {
  id: number
  operatorId: number
  operator: { id?: number; username?: string; role?: string } | string | null
  moduleCode: string
  actionCode: string
  target: Record<string, unknown> | string | null
  requestPath: string
  success: boolean
  costMs: number
  createdAt: string
}

export interface LoginLogItem {
  id: number
  userId: number
  account: string
  loginIp: string
  success: boolean
  failReason: string
  createdAt: string
}

export interface ExceptionLogItem {
  id: number
  userId: number
  requestPath: string
  exceptionType: string
  messageDigest: string
  createdAt: string
}

export const listOperationLogs = (params: Record<string, unknown>): Promise<PageResult<OperationLogItem>> =>
  request<PageResult<OperationLogItem>>({ url: `/logs/operations${query(params)}`, method: 'GET' })

export const listLoginLogs = (params: Record<string, unknown>): Promise<PageResult<LoginLogItem>> =>
  request<PageResult<LoginLogItem>>({ url: `/logs/logins${query(params)}`, method: 'GET' })

export const listExceptionLogs = (params: Record<string, unknown>): Promise<PageResult<ExceptionLogItem>> =>
  request<PageResult<ExceptionLogItem>>({ url: `/logs/exceptions${query(params)}`, method: 'GET' })

// ---------------- 视频运营管理（从子系统搬移） ----------------
export interface AuditVideoItem {
  id: number
  title: string
  filePath: string
  ownerId: number
  ownerName: string
  typeName: string
  isPublic: boolean
  auditStatus: number
  auditReason: string
  lastAction: string
  viewCount: number
  createdAt: string
}

export interface AuditLogItem {
  id: number
  videoId: number
  videoTitle?: string
  ownerName?: string
  action: string
  actionText: string
  fromStatus: number | null
  toStatus: number
  fromStatusText: string | null
  toStatusText: string
  operatorName: string
  reason: string
  createdAt: string
}

export interface TaxonomyRow {
  id: number
  name: string
  description?: string
  videoCount?: number
  auditStatus: number
  isPublished: boolean
  isMine: boolean
  auditReason?: string
  createdBy?: number
  createdByName?: string
}

export interface SiteOverview {
  videos: Record<string, number>
  users: number
  favorites: number
  addedLast7Days: number
  avgAuditHours: number | null
  hot: Array<{ id: number; title: string; viewCount: number; favoriteCount: number }>
  viewTrend: Array<{ date: string; fullDate: string; views: number }>
  hotTags: Array<{ id: number; name: string; videoCount: number; totalViews: number }>
  storageGrowth: {
    points: Array<{ date: string; fullDate: string; addedVideos: number; addedBytes: number; cumulativeVideos: number; cumulativeBytes: number }>
    totalVideos: number
    totalBytes: number
    unmeasured: number
  }
}

export interface AdminLogItem {
  id: number
  createdAt: string
  actionText: string
  targetName: string
  targetTypeText: string
  detail: string
  operatorName: string
  operatorRole: string
}

export const listAuditVideos = (params: Record<string, unknown>): Promise<PageResult<AuditVideoItem>> =>
  request<PageResult<AuditVideoItem>>({ url: `/video-admin/audit/videos${query(params)}`, method: 'GET' })

export const reviewAuditVideo = (id: number, data: { status: number; reason?: string }): Promise<{ auditStatus: number }> =>
  request<{ auditStatus: number }>({ url: `/video-admin/audit/videos/${id}/review`, method: 'POST', data })

export const listVideoAuditLogs = (params: Record<string, unknown>): Promise<PageResult<AuditLogItem> & { actionOptions: Array<{ value: string; label: string }> }> =>
  request<PageResult<AuditLogItem> & { actionOptions: Array<{ value: string; label: string }> }>({ url: `/video-admin/audit/logs${query(params)}`, method: 'GET' })

export const listVideoTimeline = (id: number): Promise<{ items: AuditLogItem[] }> =>
  request<{ items: AuditLogItem[] }>({ url: `/video-admin/audit/videos/${id}/logs`, method: 'GET' })

export const listTaxonomy = (resource: string): Promise<{ items: TaxonomyRow[] }> =>
  request<{ items: TaxonomyRow[] }>({ url: `/video-admin/taxonomy/${resource}`, method: 'GET' })

export const createTaxonomy = (resource: string, data: Record<string, unknown>): Promise<{ id: number }> =>
  request<{ id: number }>({ url: `/video-admin/taxonomy/${resource}`, method: 'POST', data })

export const updateTaxonomy = (resource: string, id: number, data: Record<string, unknown>): Promise<{ id: number }> =>
  request<{ id: number }>({ url: `/video-admin/taxonomy/${resource}/${id}`, method: 'PUT', data })

export const deleteTaxonomy = (resource: string, id: number): Promise<void> =>
  request<void>({ url: `/video-admin/taxonomy/${resource}/${id}`, method: 'DELETE' })

export const reviewTaxonomy = (resource: string, id: number, data: { action: string; reason?: string }): Promise<{ msg: string }> =>
  request<{ msg: string }>({ url: `/video-admin/taxonomy/${resource}/${id}/review`, method: 'POST', data })

export const resubmitTaxonomy = (resource: string, id: number): Promise<TaxonomyRow> =>
  request<TaxonomyRow>({ url: `/video-admin/taxonomy/${resource}/${id}/resubmit`, method: 'POST' })

export const listTaxonomyLogs = (resource: string, id: number): Promise<{ items: AuditLogItem[] }> =>
  request<{ items: AuditLogItem[] }>({ url: `/video-admin/taxonomy/${resource}/${id}/logs`, method: 'GET' })

export const getSiteOverview = (): Promise<SiteOverview> =>
  request<SiteOverview>({ url: '/video-admin/admin/overview', method: 'GET' })

export const getStorageIntegrity = (): Promise<{ total: number; missing: Array<{ id: number; title: string; filePath: string }>; roots: string[] }> =>
  request<{ total: number; missing: Array<{ id: number; title: string; filePath: string }>; roots: string[] }>({ url: '/video-admin/admin/integrity', method: 'GET' })

export const relocateVideoPaths = (data: { oldPrefix: string; newPrefix: string; dryRun: boolean }): Promise<{ updated: number; invalid: Array<{ title: string; msg: string }> }> =>
  request<{ updated: number; invalid: Array<{ title: string; msg: string }> }>({ url: '/video-admin/admin/relocate', method: 'POST', data })

export const listAdminLogs = (params: Record<string, unknown>): Promise<PageResult<AdminLogItem> & { actionOptions: Array<{ value: string; label: string }>; targetOptions: Array<{ value: string; label: string }> }> =>
  request<PageResult<AdminLogItem> & { actionOptions: Array<{ value: string; label: string }>; targetOptions: Array<{ value: string; label: string }> }>({ url: `/video-admin/admin/logs${query(params)}`, method: 'GET' })
