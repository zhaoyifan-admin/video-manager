import { reactive } from 'vue'

// 全局确认框状态（替代 ElMessageBox.confirm），confirmAction 返回 Promise<boolean>
interface ConfirmState {
  visible: boolean
  title: string
  message: string
  resolve: ((result: boolean) => void) | null
}

export const confirmState = reactive<ConfirmState>({
  visible: false,
  title: '',
  message: '',
  resolve: null,
})

export interface ConfirmOptions {
  title?: string
  message?: string
}

export function confirmAction({ title = '提示', message = '' }: ConfirmOptions = {}): Promise<boolean> {
  return new Promise((resolve) => {
    confirmState.title = title
    confirmState.message = message
    confirmState.resolve = resolve
    confirmState.visible = true
  })
}

export function settleConfirm(result: boolean): void {
  confirmState.visible = false
  const resolve = confirmState.resolve
  confirmState.resolve = null
  resolve?.(result)
}
