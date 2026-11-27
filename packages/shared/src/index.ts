export interface ApiResult<T> {
  code: number
  msg: string
  data: T
}

export type UserRole = 'admin' | 'manager' | 'reviewer' | 'user'

export interface CurrentUser {
  id: number
  username: string
  role: UserRole | string
  avatar?: string
  roles: string[]
  permissions: string[]
}

export interface MenuNode {
  id: number
  code: string
  parentId: number
  type: 'DIR' | 'MENU'
  title: string
  path: string
  componentKey?: string
  icon?: string
  permission?: string
  linkUrl?: string
  cache?: boolean
  sort?: number
  children?: MenuNode[]
}

export const VIDEO_BASE_PATH = '/video/'
export const VIDEO_API_BASE = '/video/api'
