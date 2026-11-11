<script setup>
import { computed } from 'vue'

const props = defineProps({
  total: { type: Number, default: 0 },
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 12 },
})

const emit = defineEmits(['go-page', 'size-change'])

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))

const pageItems = computed(() => {
  const cur = props.page
  const last = totalPages.value
  const out = []
  if (last <= 7) {
    for (let i = 1; i <= last; i++) out.push(i)
    return out
  }
  out.push(1)
  if (cur > 3) out.push('…')
  for (let i = Math.max(2, cur - 1); i <= Math.min(last - 1, cur + 1); i++) out.push(i)
  if (cur < last - 2) out.push('…')
  out.push(last)
  return out
})

const onSizeChange = (e) => {
  emit('size-change', Number(e.target.value))
}

// 页码按钮的工具类：基础态 + 当前页高亮态（Netflix 红实底）
const btnBase =
  'min-w-8 h-8 px-2 border rounded-[5px] text-[13px] cursor-pointer transition-colors ' +
  'enabled:hover:border-nf-line-hover enabled:hover:text-white disabled:opacity-35 disabled:cursor-not-allowed ' +
  'border-nf-line bg-nf-elevated text-nf-sub'
const btnOn = 'bg-nf-red border-nf-red text-white font-bold'
const btnClass = (p) => (p === props.page ? btnOn : btnBase)
</script>

<template>
  <!-- 分页（Tailwind 工具类） -->
  <div v-if="total > 0" class="flex items-center justify-end gap-3.5 mt-[26px]">
    <span class="text-[13px] text-nf-muted">共 {{ total }} 条</span>
    <select
      class="nf-select w-[104px] h-8 py-0 pl-2.5 pr-[26px] text-[12.5px]"
      :value="pageSize"
      @change="onSizeChange"
    >
      <option :value="12">12 条/页</option>
      <option :value="24">24 条/页</option>
      <option :value="48">48 条/页</option>
    </select>
    <div class="flex items-center gap-[5px]">
      <button :class="btnBase" :disabled="page <= 1" @click="emit('go-page', page - 1)">
        ‹
      </button>
      <template v-for="(p, i) in pageItems" :key="`${p}-${i}`">
        <span v-if="p === '…'" class="text-nf-line-hover px-0.5 select-none">…</span>
        <button v-else :class="btnClass(p)" @click="emit('go-page', p)">
          {{ p }}
        </button>
      </template>
      <button :class="btnBase" :disabled="page >= totalPages" @click="emit('go-page', page + 1)">
        ›
      </button>
    </div>
  </div>
</template>
