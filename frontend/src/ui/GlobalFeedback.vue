<script setup>
import { toasts, dismissToast } from './toast'
import { confirmState, settleConfirm } from './confirm'
import NfModal from './NfModal.vue'

const runAction = (t) => {
  dismissToast(t.id)
  t.action?.onClick?.()
}

// 按类型返回的修饰类（完整类名写在源码里保证 Tailwind 扫描到）
const typeBorder = {
  success: 'border-nf-line',
  error: 'border-[rgba(229,9,20,0.6)]',
  warning: 'border-[rgba(230,160,30,0.55)]',
}
const typeIcon = {
  success: 'text-nf-green',
  error: 'text-nf-red',
  warning: 'text-nf-amber',
}
</script>

<template>
  <!-- 全局 Toast（顶部居中，替代 ElMessage） -->
  <div class="fixed top-[18px] left-1/2 -translate-x-1/2 z-[2000] flex flex-col items-center gap-2 pointer-events-none">
    <TransitionGroup name="nf-toast">
      <div
        v-for="t in toasts"
        :key="t.id"
        class="flex items-center gap-2 max-w-[72vw] px-4 py-[9px] rounded-md bg-nf-elevated shadow-[0_8px_28px_rgba(0,0,0,0.55)] text-[13px] leading-[1.5] text-nf-text"
        :class="typeBorder[t.type] || typeBorder.success"
      >
        <svg v-if="t.type === 'success'" viewBox="0 0 24 24" width="15" height="15" :class="typeIcon[t.type]">
          <path d="M9 16.2 4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4z" fill="currentColor" />
        </svg>
        <svg v-else-if="t.type === 'error'" viewBox="0 0 24 24" width="15" height="15" :class="typeIcon[t.type]">
          <path
            d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"
            fill="currentColor"
          />
        </svg>
        <svg v-else viewBox="0 0 24 24" width="15" height="15" :class="typeIcon[t.type] || typeIcon.warning">
          <path
            d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"
            fill="currentColor"
          />
        </svg>
        <span class="min-w-0 overflow-hidden text-ellipsis line-clamp-3">{{ t.message }}</span>
        <button
          v-if="t.action"
          class="shrink-0 px-2.5 py-[3px] border rounded text-xs font-semibold cursor-pointer pointer-events-auto border-[rgba(229,9,20,0.65)] bg-[rgba(229,9,20,0.16)] text-[#ff9ba0] transition-colors hover:bg-nf-red hover:text-white"
          @click="runAction(t)"
        >
          {{ t.action.label }}
        </button>
      </div>
    </TransitionGroup>
  </div>

  <!-- 全局确认框（替代 ElMessageBox.confirm）：层级高于业务弹窗，叠开时始终可见 -->
  <NfModal
    v-model="confirmState.visible"
    :title="confirmState.title"
    width="420px"
    :overlay-z="1200"
  >
    <p class="my-1 mx-0 text-sm leading-[1.8] text-[#d2d2d2] whitespace-pre-wrap break-all">
      {{ confirmState.message }}
    </p>
    <template #footer>
      <button class="nf-btn ghost" @click="settleConfirm(false)">取消</button>
      <button class="nf-btn red" @click="settleConfirm(true)">确定</button>
    </template>
  </NfModal>
</template>

<style scoped>
/* Toast 进出场动画（Vue TransitionGroup 配套类名，保留手写） */
.nf-toast-enter-active,
.nf-toast-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.nf-toast-enter-from,
.nf-toast-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
