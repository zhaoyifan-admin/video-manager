import type { Directive, DirectiveBinding } from 'vue'
import { useAuthStore } from '../stores/auth'

// v-permission="'system:user:create'"：无权限时移除按钮，避免后端 403 后才提示。
const apply = (el: HTMLElement, binding: DirectiveBinding<string | string[]>): void => {
  const codes = Array.isArray(binding.value) ? binding.value : [binding.value]
  const permissions = useAuthStore().user?.permissions || []
  const allowed = codes.some((code) => !code || permissions.includes('*') || permissions.includes(code))
  if (allowed) return
  el.dataset.permissionDenied = '1'
  el.style.display = 'none'
}

export const permissionDirective: Directive<HTMLElement, string | string[]> = {
  mounted: apply,
  updated: apply,
}
