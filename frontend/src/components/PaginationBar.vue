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
</script>

<template>
  <!-- 分页（手写） -->
  <div v-if="total > 0" class="pagination">
    <span class="page-total">共 {{ total }} 条</span>
    <select class="nf-select page-size" :value="pageSize" @change="onSizeChange">
      <option :value="12">12 条/页</option>
      <option :value="24">24 条/页</option>
      <option :value="48">48 条/页</option>
    </select>
    <div class="page-nums">
      <button class="page-btn" :disabled="page <= 1" @click="emit('go-page', page - 1)">
        ‹
      </button>
      <template v-for="(p, i) in pageItems" :key="`${p}-${i}`">
        <span v-if="p === '…'" class="page-ellipsis">…</span>
        <button
          v-else
          class="page-btn"
          :class="{ active: p === page }"
          @click="emit('go-page', p)"
        >
          {{ p }}
        </button>
      </template>
      <button class="page-btn" :disabled="page >= totalPages" @click="emit('go-page', page + 1)">
        ›
      </button>
    </div>
  </div>
</template>

<style scoped>
/* ===== 分页 ===== */
.pagination {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 14px;
  margin-top: 26px;
}

.page-total {
  font-size: 13px;
  color: var(--nf-text-muted);
}

.page-size {
  width: 104px;
  height: 32px;
  padding: 0 26px 0 10px;
  font-size: 12.5px;
}

.page-nums {
  display: flex;
  align-items: center;
  gap: 5px;
}

.page-btn {
  min-width: 32px;
  height: 32px;
  padding: 0 8px;
  border: 1px solid #333338;
  border-radius: 5px;
  background: #1f1f23;
  color: #b3b3b3;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.page-btn:hover:not(:disabled) {
  border-color: #5c5c63;
  color: #fff;
}

.page-btn.active {
  background: var(--nf-red);
  border-color: var(--nf-red);
  color: #fff;
  font-weight: 700;
}

.page-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.page-ellipsis {
  color: #5c5c63;
  padding: 0 2px;
  user-select: none;
}
</style>
