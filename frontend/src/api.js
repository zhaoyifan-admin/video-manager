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

// ---------- 标签 ----------
export const listTags = () => http.get('/tags')
export const createTag = (name) => http.post('/tags', { name })
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

// 切换收藏状态
export const toggleFavorite = (id) => http.post(`/videos/${id}/favorite`)

// 切换公开状态（设为公开后所有用户可观看）
export const togglePublic = (id) => http.post(`/videos/${id}/public`)

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
