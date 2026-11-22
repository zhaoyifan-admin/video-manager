<script setup>
import { ICONS } from '../composables/icons'
import FaIcon from './FaIcon.vue'
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
      <div
        v-if="modelValue"
        class="fixed inset-0 flex items-center justify-center p-6 bg-black/70 backdrop-blur-[4px]"
        :style="overlayStyle"
        @click.self="close"
      >
        <div
          class="nf-modal-panel flex flex-col max-w-[calc(100vw-48px)] max-h-[calc(100vh-48px)] bg-nf-card border border-[#2e2e34] rounded-[10px] shadow-[0_24px_72px_rgba(0,0,0,0.8)] overflow-hidden"
          :style="widthStyle"
          role="dialog"
        >
          <header class="flex items-center justify-between px-[22px] pt-4 pb-3 border-b border-white/10">
            <h3 class="m-0 text-[17px] font-bold text-nf-text">{{ title }}</h3>
            <button
              class="w-[30px] h-[30px] rounded-full bg-white/10 text-nf-sub flex items-center justify-center cursor-pointer transition-colors hover:bg-[rgba(229,9,20,0.75)] hover:text-white"
              title="关闭"
              @click="close"
            >
              <FaIcon :icon="ICONS.close" :fixed="false" class="text-[18px]" />
            </button>
          </header>
          <div class="px-[22px] py-[18px] overflow-y-auto">
            <slot />
          </div>
          <footer v-if="$slots.footer" class="flex justify-end gap-2.5 px-[22px] pt-3.5 pb-[18px] border-t border-white/10">
            <slot name="footer" />
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* 过渡动画（Vue Transition 需要配套类名，保留手写） */
.nf-modal-enter-active,
.nf-modal-leave-active {
  transition: opacity 0.22s ease;
}

.nf-modal-enter-active .nf-modal-panel,
.nf-modal-leave-active .nf-modal-panel {
  transition: transform 0.22s ease, opacity 0.22s ease;
}

.nf-modal-enter-from,
.nf-modal-leave-to {
  opacity: 0;
}

.nf-modal-enter-from .nf-modal-panel,
.nf-modal-leave-to .nf-modal-panel {
  transform: translateY(18px) scale(0.98);
  opacity: 0;
}
</style>
