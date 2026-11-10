import { reactive } from 'vue'

// 全局 Toast 队列（替代 ElMessage）
export const toasts = reactive([])
let seq = 0

export function showToast(message, type = 'success', duration = 2600) {
  const id = ++seq
  toasts.push({ id, message, type })
  setTimeout(() => {
    const i = toasts.findIndex((t) => t.id === id)
    if (i > -1) toasts.splice(i, 1)
  }, duration)
}

showToast.error = (msg) => showToast(msg, 'error', 3600)
showToast.warning = (msg) => showToast(msg, 'warning', 3200)
