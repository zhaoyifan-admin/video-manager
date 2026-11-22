import { reactive } from 'vue'

// 全局 Toast 队列（替代 ElMessage）
export const toasts = reactive([])
let seq = 0

export function showToast(message, type = 'success', duration = 2600, action = null) {
  const id = ++seq
  toasts.push({ id, message, type, action })
  setTimeout(() => dismissToast(id), duration)
}

export function dismissToast(id) {
  const i = toasts.findIndex((t) => t.id === id)
  if (i > -1) toasts.splice(i, 1)
}

showToast.error = (msg) => showToast(msg, 'error', 3600)
showToast.warning = (msg) => showToast(msg, 'warning', 3200)
// 带操作按钮的提示（例如上传后引导去「审核结果」）
showToast.withAction = (msg, label, onClick, duration = 7000) =>
  showToast(msg, 'success', duration, { label, onClick })
