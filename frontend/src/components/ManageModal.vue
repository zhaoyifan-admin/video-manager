<script setup>
import { ref } from 'vue'
import FaIcon from '../ui/FaIcon.vue'
import { ICONS } from '../composables/icons'
import NfModal from '../ui/NfModal.vue'
import {
  useTaxonomy, TAXONOMY_TABS, QUICK_REASONS,
  stateOf, ACTION_STYLE, ACTION_DOT,
} from '../composables/useTaxonomy'

const emit = defineEmits(['changed'])

const visible = ref(false)
const {
  active, rows, current, loading, switching,
  keyword, filter, draft, holdPublish, submitting, hasFilter, counts, filtered,
  expanded, rejectReason, rejectError, logs, logsLoading,
  isSuperAdmin, canAudit, roleText,
  open, switchTab, setFilter, resetFilters, create,
  approve, openReject, pickReason, confirmReject, collapse, resubmit, remove, togglePublish, toggleLogs,
  canDelete, canResubmit, canViewLogs, canReview,
} = useTaxonomy(() => emit('changed'))

const openModal = async () => {
  visible.value = true
  await open()
}
defineExpose({ open: openModal })

// ===== 纯 Tailwind 类名常量（项目跳过 preflight，所有按钮显式去掉浏览器默认底色/边框）=====
const BTN = 'inline-flex items-center justify-center gap-1 border border-solid bg-transparent cursor-pointer transition-colors'
const TAB_ON = 'border-0 bg-nf-red text-white shadow-[0_2px_14px_rgba(229,9,20,0.3)]'
const TAB_OFF = 'border-0 bg-transparent text-nf-sub hover:bg-white/[0.06] hover:text-nf-text'
const CARD_ON = 'border-nf-red/50 bg-nf-red/[0.09]'
const CARD_OFF = 'border-white/[0.08] bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.05]'
const ACT_PLAIN = `${BTN} h-7 shrink-0 rounded border-white/15 px-2.5 text-[11.5px] font-medium leading-none text-nf-sub hover:border-white/35 hover:bg-white/[0.06] hover:text-nf-text`
const ACT_PASS = `${BTN} h-7 shrink-0 rounded border-emerald-500/40 px-2.5 text-[11.5px] font-semibold leading-none text-emerald-300 hover:border-emerald-400/70 hover:bg-emerald-500/20 hover:text-emerald-200`
const ACT_DANGER = `${BTN} h-7 shrink-0 rounded border-rose-500/40 px-2.5 text-[11.5px] font-semibold leading-none text-rose-300 hover:border-rose-400/70 hover:bg-rose-500/20 hover:text-rose-200`
const ACT_PUBLISH = `${BTN} h-7 shrink-0 rounded border-emerald-500/40 px-2.5 text-[11.5px] font-semibold leading-none text-emerald-300 hover:border-emerald-400/70 hover:bg-emerald-500/20 hover:text-emerald-200`
const ACT_UNPUBLISH = `${BTN} h-7 shrink-0 rounded border-amber-500/40 px-2.5 text-[11.5px] font-semibold leading-none text-amber-300 hover:border-amber-400/70 hover:bg-amber-500/20 hover:text-amber-200`
const INPUT = 'w-full rounded-md border border-solid border-white/10 bg-nf-elevated text-[13px] text-nf-text placeholder:text-nf-muted outline-none transition-colors focus:border-nf-red/60'
const QUICK_CHIP = `${BTN} rounded-full border-white/15 px-2.5 py-1 text-[11px] text-nf-sub hover:border-white/35 hover:bg-white/[0.06] hover:text-nf-text`

const STAT_CARDS = [
  { key: 'all', label: '全部条目', tone: 'text-nf-text' },
  { key: 'published', label: '已发布', tone: 'text-emerald-300' },
  { key: 'unpublished', label: '未发布', tone: 'text-nf-sub' },
  { key: 'pending', label: '待审核', tone: 'text-amber-300' },
  { key: 'rejected', label: '已驳回', tone: 'text-rose-300' },
  { key: 'mine', label: '我提交的', tone: 'text-sky-300' },
]

const subInfo = (row) => {
  let base
  if (row.createdByName) base = `由 ${row.createdByName} 提交`
  else if (row.isMine) base = '由我提交'
  else base = '系统预置'
  // 合集额外展示已关联影片数，便于判断删除影响面
  return row.videoCount !== undefined ? `${base} · ${row.videoCount} 部影片` : base
}
</script>

<template>
  <NfModal v-model="visible" title="分类管理 · 标签 / 影视类型 / 合集" width="880px">
    <!-- ============ 顶部：资源切换 + 权限说明 ============ -->
    <div class="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.08] pb-3.5">
      <div class="flex items-center gap-1 rounded-lg border border-solid border-white/[0.08] bg-black/25 p-1">
        <button
          v-for="tab in TAXONOMY_TABS"
          :key="tab.key"
          class="flex h-9 items-center gap-2 rounded-md px-4 text-[13px] font-semibold whitespace-nowrap cursor-pointer transition-colors"
          :class="active === tab.key ? TAB_ON : TAB_OFF"
          @click="switchTab(tab.key)"
        >
          <FaIcon :icon="tab.icon" :fixed="false" class="text-[15px]" />
          {{ tab.label }}
          <span
            v-if="tab.key === active && counts.pending"
            class="rounded-full bg-white/25 px-1.5 py-[1px] text-[10px] font-bold text-nf-text"
            :title="`当前分类有 ${counts.pending} 条待审核`"
          >{{ counts.pending }}</span>
        </button>
      </div>
      <div class="flex items-center gap-2 text-[11.5px] text-nf-muted">
        <span class="rounded border border-solid border-white/10 px-2 py-[3px] font-semibold text-nf-sub">{{ roleText }}</span>
        <span>{{ canAudit ? '可审核全部分类' : '可提交新分类，审核通过后全站可见' }}</span>
      </div>
    </div>

    <!-- ============ 概览统计：点击即为状态筛选 ============ -->
    <div class="mt-4 grid grid-cols-6 gap-2.5 max-[640px]:grid-cols-3">
      <button
        v-for="card in STAT_CARDS"
        :key="card.key"
        class="flex flex-col items-start gap-1 rounded-lg border border-solid px-3.5 py-2.5 text-left cursor-pointer transition-colors"
        :class="filter === card.key && card.key !== 'all' ? CARD_ON : CARD_OFF"
        @click="setFilter(card.key)"
      >
        <span class="flex items-center gap-1.5 text-[11px] text-nf-muted">
          {{ card.label }}
          <span v-if="card.key === 'pending' && counts.pending" class="h-1.5 w-1.5 rounded-full bg-amber-400 animate-pulse"></span>
        </span>
        <span class="text-[22px] font-bold leading-none tabular-nums" :class="card.tone">{{ counts[card.key] }}</span>
      </button>
    </div>

    <!-- ============ 新建提交 ============ -->
    <div class="mt-4 rounded-lg border border-solid border-white/[0.08] bg-white/[0.02] px-3.5 py-3">
      <div class="mb-2.5 flex flex-wrap items-baseline gap-2">
        <span class="text-[12.5px] font-semibold text-nf-text">新建{{ current.label }}</span>
        <span class="text-[11.5px] text-nf-muted">{{ TAXONOMY_TABS.find(t => t.key === active)?.desc }}</span>
      </div>
      <div class="flex flex-wrap items-center gap-2.5">
        <div class="relative min-w-[200px] flex-1">
          <FaIcon :icon="ICONS.create" :fixed="false" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[15px] text-nf-muted" />
          <input
            v-model="draft"
            :class="INPUT"
            class="h-9 pl-9 pr-3"
            :placeholder="`输入新${current.label}名称，最多 ${current.maxLength || 50} 字`"
            :maxlength="current.maxLength || 50"
            @keyup.enter="create"
          />
        </div>
        <button
          class="inline-flex items-center justify-center gap-1.5 h-9 shrink-0 rounded-md border-0 bg-nf-red px-4 text-[13px] font-semibold text-white cursor-pointer transition-colors hover:bg-nf-red-hover disabled:opacity-50"
          :disabled="submitting || !draft.trim()"
          @click="create"
        >
          <FaIcon :icon="ICONS.create" :fixed="false" />
          {{ isSuperAdmin ? (holdPublish ? '仅创建' : '创建并发布') : '提交审核' }}
        </button>
      </div>
      <label v-if="isSuperAdmin" class="mt-2.5 flex w-fit items-center gap-2 text-[11.5px] text-nf-muted cursor-pointer">
        <input v-model="holdPublish" type="checkbox" class="h-3.5 w-3.5 cursor-pointer accent-nf-red" />
        暂不发布（留作待审核，可在下方清单点「通过」发布）
      </label>
      <p v-else class="mt-2 text-[11.5px] leading-relaxed text-nf-muted">
        提交后进入「待审核」，审核通过后才会对全部用户可见；被驳回可查看理由并重新提交。
      </p>
    </div>

    <!-- ============ 列表工具条 ============ -->
    <div class="sticky top-0 z-10 mt-5 flex flex-wrap items-center gap-2.5 bg-nf-card pb-2.5">
      <span class="text-[12.5px] font-semibold text-nf-sub">{{ current.label }}清单</span>
      <span class="rounded-full bg-white/[0.07] px-2 py-[2px] text-[11px] text-nf-muted">{{ filtered.length }} 条</span>
      <div class="relative ml-auto w-[220px] max-w-full">
        <FaIcon :icon="ICONS.search" :fixed="false" class="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[14px] text-nf-muted" />
        <input v-model="keyword" :class="INPUT" class="h-8 pl-8 pr-3 text-[12px]" placeholder="搜索名称" />
      </div>
      <button
        v-if="hasFilter"
        class="inline-flex items-center justify-center gap-1.5 h-8 shrink-0 rounded-md border border-solid border-white/15 bg-transparent px-2.5 text-[11.5px] text-nf-sub cursor-pointer transition-colors hover:border-white/35 hover:text-nf-text"
        @click="resetFilters"
      >
        <FaIcon :icon="ICONS.close" :fixed="false" />清除筛选
      </button>
    </div>

    <!-- ============ 行式列表 ============ -->
    <div class="max-h-[54vh] min-h-[120px] space-y-2 overflow-y-auto pb-1 pr-1">
      <div v-if="loading || switching" class="flex items-center justify-center gap-2 py-12 text-[12.5px] text-nf-muted">
        <FaIcon :icon="ICONS.spinner" spin :fixed="false" class="text-nf-red" />
        加载中…
      </div>

      <div v-else-if="!filtered.length" class="flex flex-col items-center gap-2 py-10 text-center">
        <FaIcon :icon="ICONS.list" :fixed="false" class="text-[30px] text-nf-muted/40" />
        <div class="text-[13.5px] font-semibold text-nf-sub">
          {{ rows.length ? '没有匹配的条目' : `还没有${current.label}` }}
        </div>
        <p class="text-[11.5px] text-nf-muted">
          {{ rows.length ? '换个关键词，或清除状态筛选试试' : `在上方输入名称即可新建${current.label}` }}
        </p>
        <button
          v-if="hasFilter"
          class="inline-flex items-center justify-center gap-1.5 mt-1 h-7 rounded-md border border-solid border-white/15 bg-transparent px-3 text-[11.5px] text-nf-sub cursor-pointer hover:text-nf-text"
          @click="resetFilters"
        >
          <FaIcon :icon="ICONS.close" :fixed="false" />清除筛选
        </button>
      </div>

      <template v-else>
        <div
          v-for="row in filtered"
          :key="row.id"
          class="overflow-hidden rounded-lg border border-solid border-white/[0.08] bg-white/[0.02] transition-colors hover:border-white/[0.16]"
        >
          <div class="flex items-center gap-3 px-3 py-2.5 max-[640px]:flex-wrap">
            <!-- 状态色条 -->
            <span class="h-8 w-[3px] shrink-0 rounded-full" :class="stateOf(row).bar"></span>

            <!-- 名称与来源 -->
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span class="truncate text-[13.5px] font-semibold text-nf-text">{{ row.name }}</span>
                <span v-if="row.isMine" class="shrink-0 rounded bg-sky-500/15 px-1.5 py-[2px] text-[10px] font-medium text-sky-300">我提交的</span>
              </div>
              <div class="mt-[3px] truncate text-[11px] text-nf-muted">
                {{ subInfo(row) }}
                <template v-if="row.auditStatus === 2 && row.auditReason"> · 驳回理由：{{ row.auditReason }}</template>
              </div>
            </div>

            <!-- 状态徽章 -->
            <span class="shrink-0 rounded px-2 py-[3px] text-[11px] font-semibold" :class="stateOf(row).badge">
              {{ stateOf(row).text }}
            </span>

            <!-- 操作区 -->
            <div class="flex shrink-0 items-center gap-1.5 max-[640px]:w-full max-[640px]:justify-end">
              <!-- 发布 / 取消发布：仅超级管理员，且只对已通过审核的条目开放；待审 / 驳回走审核流程 -->
              <button
                v-if="isSuperAdmin && row.auditStatus === 1"
                :class="row.isPublished ? ACT_UNPUBLISH : ACT_PUBLISH"
                :title="row.isPublished ? '取消发布后普通用户将不再看到该条目' : '发布后全站可见'"
                @click="togglePublish(row)"
              >
                <FaIcon :icon="row.isPublished ? ICONS.unpublish : ICONS.publish" :fixed="false" />
                {{ row.isPublished ? '取消发布' : '发布' }}
              </button>
              <button v-if="canReview(row)" :class="ACT_PASS" @click="approve(row)"><FaIcon :icon="ICONS.check" :fixed="false" />通过</button>
              <button v-if="canReview(row)" :class="ACT_DANGER" @click="openReject(row)"><FaIcon :icon="ICONS.close" :fixed="false" />驳回</button>
              <button v-if="canResubmit(row)" :class="ACT_PLAIN" @click="resubmit(row)"><FaIcon :icon="ICONS.refresh" :fixed="false" />重新提交</button>
              <button v-if="canViewLogs(row)" :class="ACT_PLAIN" @click="toggleLogs(row)">
                <FaIcon :icon="ICONS.auditLog" :fixed="false" />
                {{ expanded?.kind === 'logs' && expanded.id === row.id ? '收起记录' : '审核记录' }}
              </button>
              <button
                v-if="canDelete(row)"
                :title="`删除${current.label}`"
                class="flex h-7 w-7 shrink-0 items-center justify-center rounded border border-solid border-white/15 bg-transparent text-[13px] text-nf-muted cursor-pointer transition-colors hover:border-rose-500/60 hover:bg-rose-500/15 hover:text-rose-300"
                @click="remove(row)"
              >
                <FaIcon :icon="ICONS.remove" :fixed="false" />
              </button>
            </div>
          </div>

          <!-- ===== 行内驳回理由（明确标注对象） ===== -->
          <div
            v-if="expanded?.kind === 'reject' && expanded.id === row.id"
            class="border-t border-solid border-white/[0.07] bg-rose-500/[0.04] px-3.5 py-3"
          >
            <div class="flex flex-wrap items-baseline gap-2">
              <span class="text-[12.5px] font-semibold text-rose-300">驳回「{{ row.name }}」</span>
              <span class="text-[11px] text-nf-muted">理由会展示给创建者，请写明未通过原因</span>
            </div>
            <div class="mt-2.5 flex flex-wrap gap-1.5">
              <button v-for="r in QUICK_REASONS" :key="r" :class="QUICK_CHIP" @click="pickReason(r)">{{ r }}</button>
            </div>
            <textarea
              v-model="rejectReason"
              rows="2"
              maxlength="500"
              :class="INPUT"
              class="mt-2.5 resize-y px-3 py-2 leading-relaxed"
              placeholder="例如：名称与现有条目重复，请改用更准确的命名后重新提交"
              @input="rejectError = ''"
            ></textarea>
            <div v-if="rejectError" class="mt-1.5 text-[11.5px] text-rose-300">{{ rejectError }}</div>
            <div class="mt-2 flex items-center justify-end gap-2">
              <span class="mr-auto text-[11px] text-nf-muted">{{ rejectReason.length }}/500</span>
              <button :class="ACT_PLAIN" @click="collapse"><FaIcon :icon="ICONS.close" :fixed="false" />取消</button>
              <button
                class="inline-flex items-center justify-center gap-1.5 h-7 shrink-0 rounded border-0 bg-rose-600 px-3 text-[11.5px] font-semibold text-white cursor-pointer transition-colors hover:bg-rose-500"
                @click="confirmReject"
              >
                <FaIcon :icon="ICONS.close" :fixed="false" />确认驳回
              </button>
            </div>
          </div>

          <!-- ===== 行内审核时间线 ===== -->
          <div
            v-if="expanded?.kind === 'logs' && expanded.id === row.id"
            class="border-t border-solid border-white/[0.07] bg-black/20 px-3.5 py-3"
          >
            <div class="mb-2.5 text-[11.5px] font-semibold text-nf-sub">「{{ row.name }}」审核轨迹</div>
            <div v-if="logsLoading" class="py-2 text-[11.5px] text-nf-muted">加载中…</div>
            <div v-else-if="!logs.length" class="py-2 text-[11.5px] text-nf-muted">暂无审核记录</div>
            <div v-else class="space-y-0">
              <div v-for="log in logs" :key="log.id" class="flex gap-2.5">
                <span class="mt-[7px] h-2 w-2 shrink-0 rounded-full" :class="ACTION_DOT[log.action] || 'bg-white/30'"></span>
                <div class="min-w-0 flex-1 pb-3">
                  <div class="flex flex-wrap items-center gap-2 text-[11.5px]">
                    <span class="rounded px-1.5 py-[2px] text-[10.5px] font-semibold" :class="ACTION_STYLE[log.action] || 'bg-white/10 text-nf-sub'">
                      {{ log.actionText }}
                    </span>
                    <span class="text-nf-sub">
                      {{ log.fromStatusText ? `${log.fromStatusText} → ${log.toStatusText}` : `初始 → ${log.toStatusText}` }}
                    </span>
                    <span class="text-[#e08a90]">{{ log.operatorName }}</span>
                    <span class="text-nf-muted">{{ log.createdAt }}</span>
                  </div>
                  <div v-if="log.reason" class="mt-1 text-[11px] leading-relaxed text-rose-300/80">理由：{{ log.reason }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- ============ 底部流程说明 ============ -->
    <div class="mt-3.5 flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-solid border-white/[0.08] pt-3 text-[11px] text-nf-muted">
      <span class="rounded bg-amber-500/15 px-1.5 py-[2px] font-semibold text-amber-300">提交</span>
      <span>→</span>
      <span class="rounded bg-nf-red/15 px-1.5 py-[2px] font-semibold text-[#ff8a90]">审核</span>
      <span>→</span>
      <span class="rounded bg-emerald-500/15 px-1.5 py-[2px] font-semibold text-emerald-300">全站可见</span>
      <span class="ml-1">已通过条目可由超级管理员随时「发布 / 取消发布」；名称全局唯一，被驳回请用「重新提交」；已发布条目仅管理员可删除。</span>
    </div>
  </NfModal>
</template>
