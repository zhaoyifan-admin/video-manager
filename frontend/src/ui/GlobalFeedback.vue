<script setup>
import { toasts } from './toast'
import { confirmState, settleConfirm } from './confirm'
import NfModal from './NfModal.vue'
</script>

<template>
  <!-- 全局 Toast（顶部居中，替代 ElMessage） -->
  <div class="nf-toasts">
    <TransitionGroup name="nf-toast">
      <div v-for="t in toasts" :key="t.id" class="nf-toast" :class="t.type">
        <svg v-if="t.type === 'success'" viewBox="0 0 24 24" width="15" height="15">
          <path d="M9 16.2 4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4z" fill="currentColor" />
        </svg>
        <svg v-else-if="t.type === 'error'" viewBox="0 0 24 24" width="15" height="15">
          <path
            d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"
            fill="currentColor"
          />
        </svg>
        <svg v-else viewBox="0 0 24 24" width="15" height="15">
          <path
            d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"
            fill="currentColor"
          />
        </svg>
        <span class="nf-toast-text">{{ t.message }}</span>
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
    <p class="nf-confirm-msg">{{ confirmState.message }}</p>
    <template #footer>
      <button class="nf-btn ghost" @click="settleConfirm(false)">取消</button>
      <button class="nf-btn red" @click="settleConfirm(true)">确定</button>
    </template>
  </NfModal>
</template>

<style scoped>
.nf-toasts {
  position: fixed;
  top: 18px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 2000;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  pointer-events: none;
}

.nf-toast {
  display: flex;
  align-items: center;
  gap: 8px;
  max-width: 72vw;
  padding: 9px 16px;
  border-radius: 6px;
  background: #1f1f23;
  border: 1px solid #333338;
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.55);
  font-size: 13px;
  line-height: 1.5;
  color: #f5f5f5;
}

.nf-toast.success svg {
  color: #46d369;
}

.nf-toast.error {
  border-color: rgba(229, 9, 20, 0.6);
}

.nf-toast.error svg {
  color: #e50914;
}

.nf-toast.warning {
  border-color: rgba(230, 160, 30, 0.55);
}

.nf-toast.warning svg {
  color: #e6a01e;
}

.nf-toast-text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}

.nf-toast-enter-active,
.nf-toast-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.nf-toast-enter-from,
.nf-toast-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

.nf-confirm-msg {
  margin: 4px 0;
  font-size: 14px;
  line-height: 1.8;
  color: #d2d2d2;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
