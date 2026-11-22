import { ref } from 'vue'
import { getMe } from '../api'

// ================= 登录态（全局单例） =================
// user 为 null 表示未登录；ensureLoaded 在应用启动后首次路由时才真正请求
const user = ref(null)
let readyPromise = null

const fetchMe = async () => {
  try {
    user.value = await getMe()
  } catch {
    user.value = null
  }
  return user.value
}

// 仅首次调用时请求一次 /auth/me，后续路由守卫直接复用结果
export const ensureLoaded = () => {
  if (!readyPromise) readyPromise = fetchMe()
  return readyPromise
}

// 登录/注册成功后写入用户并标记已就绪
export const setUser = (u) => {
  user.value = u
  readyPromise = Promise.resolve(u)
}

// 退出登录 / 登录过期：清空状态，下次路由守卫会重新探测
export const resetAuth = () => {
  user.value = null
  readyPromise = null
}

// 合并更新本地用户态（如上传头像后仅刷新 avatar 字段），避免重新请求 /auth/me
export const patchUser = (patch) => {
  user.value = { ...(user.value || {}), ...patch }
}

export function useAuth() {
  return { user, ensureLoaded, setUser, resetAuth, fetchMe, patchUser }
}
