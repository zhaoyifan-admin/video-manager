<script setup>
import { ref, watch } from 'vue'
import { getAuditLogs } from '../api'

const props = defineProps({
  videoId: { type: Number, required: true },
})

const logs = ref([])
const loading = ref(false)

const load = async () => {
  loading.value = true
  try {
    const data = await getAuditLogs(props.videoId)
    logs.value = data.items
  } catch {
    logs.value = []
  } finally {
    loading.value = false
  }
}

watch(() => props.videoId, load, { immediate: true })
defineExpose({ reload: load })
</script>

<template>
  <div class="timeline">
    <div class="timeline-head">审核记录</div>

    <div v-if="loading" class="timeline-loading">加载中…</div>
    <div v-else-if="!logs.length" class="timeline-empty">暂无审核记录</div>

    <ol v-else class="timeline-list">
      <li v-for="log in logs" :key="log.id" class="timeline-item" :class="`a-${log.action}`">
        <span class="timeline-dot"></span>
        <div class="timeline-body">
          <div class="timeline-row">
            <span class="action-badge" :class="`a-${log.action}`">{{ log.actionText }}</span>
            <span v-if="log.fromStatusText" class="status-change">
              {{ log.fromStatusText }} <span class="arrow">→</span> {{ log.toStatusText }}
            </span>
            <span v-else class="status-change">
              初始状态 <span class="arrow">→</span> {{ log.toStatusText }}
            </span>
            <span class="timeline-time">{{ log.createdAt }}</span>
          </div>
          <div class="timeline-meta">
            操作人：<span class="operator">{{ log.operatorName }}</span>
            <span v-if="log.action === 'auto_approve'" class="exempt-tip">管理员上传 · 无需审核流程</span>
          </div>
          <div v-if="log.reason" class="timeline-reason" :class="{ reject: log.action === 'reject' }">
            {{ log.reason }}
          </div>
        </div>
      </li>
    </ol>
  </div>
</template>

<style scoped>
.timeline {
  padding: 4px 0 2px;
}

.timeline-head {
  margin-bottom: 12px;
  font-size: 13px;
  font-weight: 700;
  color: var(--nf-text-primary);
}

.timeline-loading,
.timeline-empty {
  padding: 14px 0;
  font-size: 12.5px;
  color: var(--nf-text-muted);
}

.timeline-list {
  list-style: none;
  margin: 0;
  padding: 0 0 0 14px;
  border-left: 1px solid #3a3a42;
}

.timeline-item {
  position: relative;
  padding: 0 0 16px 16px;
}

.timeline-item:last-child {
  padding-bottom: 2px;
}

.timeline-dot {
  position: absolute;
  left: -19px;
  top: 4px;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #6a6a74;
  border: 2px solid #1b1b1f;
  box-sizing: content-box;
}

.timeline-item.a-approve .timeline-dot { background: #37b58a; }
.timeline-item.a-reject .timeline-dot { background: #e50914; }
.timeline-item.a-submit .timeline-dot { background: #be8a00; }
.timeline-item.a-resubmit .timeline-dot { background: #d99b2b; }
.timeline-item.a-auto_approve .timeline-dot { background: #6c8ed6; }

.timeline-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 9px;
}

.action-badge {
  padding: 2px 9px;
  border-radius: 9px;
  font-size: 11.5px;
  font-weight: 600;
  background: var(--nf-overlay);
  color: #d9d9de;
  white-space: nowrap;
}

.action-badge.a-approve { background: rgba(0, 128, 96, 0.85); color: #fff; }
.action-badge.a-reject { background: rgba(150, 26, 32, 0.92); color: #fff; }
.action-badge.a-submit { background: rgba(190, 138, 0, 0.9); color: #fff; }
.action-badge.a-resubmit { background: rgba(190, 138, 0, 0.65); color: #fff; }
.action-badge.a-auto_approve { background: rgba(88, 118, 190, 0.9); color: #fff; }

.status-change {
  font-size: 12px;
  color: var(--nf-text-secondary);
}

.arrow {
  color: var(--nf-red);
  margin: 0 3px;
}

.timeline-time {
  margin-left: auto;
  font-size: 11.5px;
  color: var(--nf-text-muted);
  white-space: nowrap;
}

.timeline-meta {
  margin-top: 5px;
  font-size: 12px;
  color: var(--nf-text-muted);
}

.operator {
  color: #e08a90;
}

.exempt-tip {
  margin-left: 10px;
  padding-left: 10px;
  border-left: 1px solid #3a3a42;
  color: #8fa8dd;
}

.timeline-reason {
  margin-top: 7px;
  padding: 7px 10px;
  border-radius: 5px;
  background: var(--nf-overlay-soft);
  font-size: 12.5px;
  line-height: 1.55;
  color: var(--nf-text-secondary);
}

.timeline-reason.reject {
  border-left: 3px solid #ff525b;
  background: rgba(229, 9, 20, 0.09);
  color: #ffb3b8;
}
</style>
