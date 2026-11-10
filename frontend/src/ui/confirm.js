import { reactive } from 'vue'

// 全局确认框状态（替代 ElMessageBox.confirm），confirmAction 返回 Promise<boolean>
export const confirmState = reactive({
  visible: false,
  title: '',
  message: '',
  resolve: null,
})

export function confirmAction({ title = '提示', message = '' } = {}) {
  return new Promise((resolve) => {
    confirmState.title = title
    confirmState.message = message
    confirmState.resolve = resolve
    confirmState.visible = true
  })
}

export function settleConfirm(result) {
  confirmState.visible = false
  const resolve = confirmState.resolve
  confirmState.resolve = null
  resolve?.(result)
}
