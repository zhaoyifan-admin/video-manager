<script setup>
import { computed, onUnmounted, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '' },
  width: { type: [String, Number], default: '560px' },
  // 遮罩层级：业务弹窗默认 1000；全局确认框传更高值保证盖在业务弹窗之上
  overlayZ: { type: [String, Number], default: 1000 },
})
const emit = defineEmits(['update:modelValue'])

const close = () => emit('update:modelValue', false)

const overlayStyle = computed(() => ({
  zIndex: props.overlayZ,
}))

const widthStyle = computed(() => ({
  width: typeof props.width === 'number' ? `${props.width}px` : props.width,
}))

// 弹窗打开时锁定背景滚动；多层弹窗叠开时按计数释放（确认框关闭不影响底层弹窗）
let openCount = 0
watch(
  () => props.modelValue,
  (open) => {
    openCount += open ? 1 : -1
    document.body.style.overflow = openCount > 0 ? 'hidden' : ''
  },
)

onUnmounted(() => {
  if (!props.modelValue) return
  openCount = Math.max(0, openCount - 1)
  if (openCount === 0) document.body.style.overflow = ''
})

const onKeydown = (e) => {
  if (e.key === 'Escape' && props.modelValue) close()
}
window.addEventListener('keydown', onKeydown)
</script>

<template>
  <Teleport to="body">
    <Transition name="nf-modal">
      <div v-if="modelValue" class="nf-modal-overlay" :style="overlayStyle" @click.self="close">
        <div class="nf-modal" :style="widthStyle" role="dialog">
          <header class="nf-modal-head">
            <h3 class="nf-modal-title">{{ title }}</h3>
            <button class="nf-modal-close" title="关闭" @click="close">
              <svg viewBox="0 0 24 24" width="18" height="18">
                <path
                  d="M18.3 5.71 12 12.01l-6.3-6.3-1.4 1.41 6.29 6.3-6.3 6.3 1.42 1.4 6.29-6.29 6.3 6.3 1.4-1.42-6.29-6.29 6.3-6.3z"
                  fill="currentColor"
                />
              </svg>
            </button>
          </header>
          <div class="nf-modal-body">
            <slot />
          </div>
          <footer v-if="$slots.footer" class="nf-modal-foot">
            <slot name="footer" />
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.nf-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(0, 0, 0, 0.72);
  backdrop-filter: blur(4px);
}

.nf-modal {
  max-width: calc(100vw - 48px);
  max-height: calc(100vh - 48px);
  display: flex;
  flex-direction: column;
  background: #181818;
  border: 1px solid #2e2e34;
  border-radius: 10px;
  box-shadow: 0 24px 72px rgba(0, 0, 0, 0.8);
  overflow: hidden;
}

.nf-modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 22px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
}

.nf-modal-title {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  color: #f5f5f5;
}

.nf-modal-close {
  width: 30px;
  height: 30px;
  border: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.08);
  color: #b3b3b3;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.nf-modal-close:hover {
  background: rgba(229, 9, 20, 0.75);
  color: #fff;
}

.nf-modal-body {
  padding: 18px 22px;
  overflow-y: auto;
}

.nf-modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 22px 18px;
  border-top: 1px solid rgba(255, 255, 255, 0.07);
}

/* 过渡动画 */
.nf-modal-enter-active,
.nf-modal-leave-active {
  transition: opacity 0.22s ease;
}

.nf-modal-enter-active .nf-modal,
.nf-modal-leave-active .nf-modal {
  transition: transform 0.22s ease, opacity 0.22s ease;
}

.nf-modal-enter-from,
.nf-modal-leave-to {
  opacity: 0;
}

.nf-modal-enter-from .nf-modal,
.nf-modal-leave-to .nf-modal {
  transform: translateY(18px) scale(0.98);
  opacity: 0;
}
</style>
