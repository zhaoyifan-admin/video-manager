import { reactive } from 'vue'

// 全局 Toast 队列（替代 ElMessage）
export interface ToastAction {
  label: string
  onClick: () => void
}

export interface ToastItem {
  id: number
  message: string
  type: string
  action: ToastAction | null
}

export const toasts = reactive<ToastItem[]>([])
let seq = 0

interface ShowToast {
  (message: string, type?: string, duration?: number, action?: ToastAction | null): void
  error: (msg: string) => void
  warning: (msg: string) => void
  withAction: (msg: string, label: string, onClick: () => void, duration?: number) => void
}

export const showToast = ((message: string, type = 'success', duration = 2600, action: ToastAction | null = null) => {
  const id = ++seq
  toasts.push({ id, message, type, action })
  setTimeout(() => dismissToast(id), duration)
}) as ShowToast

export function dismissToast(id: number): void {
  const i = toasts.findIndex((t) => t.id === id)
  if (i > -1) toasts.splice(i, 1)
}

showToast.error = (msg: string) => showToast(msg, 'error', 3600)
showToast.warning = (msg: string) => showToast(msg, 'warning', 3200)
// 带操作按钮的提示（例如上传后引导去「审核结果」）
showToast.withAction = (msg: string, label: string, onClick: () => void, duration = 7000) =>
  showToast(msg, 'success', duration, { label, onClick })
