import { computed, ref } from 'vue'
import {
  listTags, createTag, updateTag, deleteTag, reviewTag, resubmitTag, getTagLogs,
  listTypes, createType, updateType, deleteType, reviewType, resubmitType, getTypeLogs,
} from '../api'
import { useAuth } from './useAuth'
import { showToast } from '../ui/toast'
import { confirmAction } from '../ui/confirm'

// 标签与影视类型的审核流程完全一致，统一在此维护一份逻辑；
// 两个资源仅通过 API 集合与少量文案区分，界面只负责渲染。
export const TAXONOMY_TABS = [
  { key: 'tag', label: '标签', desc: '多选题材标记，用于视频筛选', icon: 'tag' },
  { key: 'type', label: '影视类型', desc: '单选分类，决定首页频道', icon: 'film' },
]

export const QUICK_REASONS = [
  '名称不规范',
  '与现有条目重复或含义不清',
  '内容不符合要求',
]

const RESOURCES = {
  tag: {
    label: '标签',
    deleteHint: '已挂接该标签的视频会同步解除关联。',
    api: {
      list: listTags, create: createTag, update: updateTag, remove: deleteTag,
      review: reviewTag, resubmit: resubmitTag, logs: getTagLogs,
    },
  },
  type: {
    label: '影视类型',
    deleteHint: '使用该类型的视频会变为未分类。',
    api: {
      list: listTypes, create: createType, update: updateType, remove: deleteType,
      review: reviewType, resubmit: resubmitType, logs: getTypeLogs,
    },
  },
}

// 状态视觉：用完整类名字符串，避免动态拼接导致 Tailwind 扫描不到
export const STATE_STYLE = {
  pending: {
    text: '待审核',
    bar: 'bg-amber-400',
    badge: 'bg-amber-500/15 text-amber-300 ring-1 ring-inset ring-amber-500/30',
    dot: 'bg-amber-400',
  },
  published: {
    text: '已发布',
    bar: 'bg-emerald-500',
    badge: 'bg-emerald-500/15 text-emerald-300 ring-1 ring-inset ring-emerald-500/30',
    dot: 'bg-emerald-500',
  },
  rejected: {
    text: '已驳回',
    bar: 'bg-rose-500',
    badge: 'bg-rose-500/15 text-rose-300 ring-1 ring-inset ring-rose-500/30',
    dot: 'bg-rose-500',
  },
  unpublished: {
    text: '未发布',
    bar: 'bg-white/25',
    badge: 'bg-white/10 text-nf-sub ring-1 ring-inset ring-white/15',
    dot: 'bg-white/30',
  },
}

export const stateOf = (row) => {
  if (row.auditStatus === 0) return STATE_STYLE.pending
  if (row.auditStatus === 2) return STATE_STYLE.rejected
  return row.isPublished === false ? STATE_STYLE.unpublished : STATE_STYLE.published
}

export const ACTION_STYLE = {
  submit: 'bg-amber-500/20 text-amber-300',
  resubmit: 'bg-amber-500/20 text-amber-300',
  approve: 'bg-emerald-500/20 text-emerald-300',
  auto_approve: 'bg-sky-500/20 text-sky-300',
  reject: 'bg-rose-500/20 text-rose-300',
}

export const ACTION_DOT = {
  submit: 'bg-amber-400',
  resubmit: 'bg-amber-400',
  approve: 'bg-emerald-500',
  auto_approve: 'bg-sky-400',
  reject: 'bg-rose-500',
}

export function useTaxonomy(onChanged) {
  const { user } = useAuth()
  const isSuperAdmin = computed(() => user.value?.role === 'admin')
  const canAudit = computed(() => ['admin', 'manager', 'reviewer'].includes(user.value?.role))
  const roleText = computed(() => (canAudit.value ? '审核权限' : '普通用户'))

  const active = ref('tag')
  const buckets = ref({ tag: [], type: [] })
  const loading = ref(false)
  const switching = ref(false)

  const keyword = ref('')
  const filter = ref('all')
  const draft = ref('')
  const holdPublish = ref(false)
  const submitting = ref(false)

  // 行内展开：驳回理由 / 审核留痕，二者互斥且归属到具体某一行
  const expanded = ref(null) // { id, kind: 'reject' | 'logs' }
  const rejectRow = ref(null)
  const rejectReason = ref('')
  const rejectError = ref('')
  const logs = ref([])
  const logsLoading = ref(false)

  const current = computed(() => RESOURCES[active.value])
  const rows = computed(() => buckets.value[active.value] || [])

  const counts = computed(() => {
    const all = rows.value
    return {
      all: all.length,
      published: all.filter((r) => r.auditStatus === 1 && r.isPublished !== false).length,
      unpublished: all.filter((r) => r.auditStatus === 1 && r.isPublished === false).length,
      pending: all.filter((r) => r.auditStatus === 0).length,
      rejected: all.filter((r) => r.auditStatus === 2).length,
      mine: all.filter((r) => r.isMine === true).length,
    }
  })

  // 待审核优先、驳回次之、已发布最后；同状态内按名称排序
  const WEIGHT = { 0: 0, 2: 1, 1: 2 }
  const filtered = computed(() => {
    const kw = keyword.value.trim().toLowerCase()
    return rows.value
      .filter((r) => {
        if (filter.value === 'published' && !(r.auditStatus === 1 && r.isPublished !== false)) return false
        if (filter.value === 'unpublished' && !(r.auditStatus === 1 && r.isPublished === false)) return false
        if (filter.value === 'pending' && r.auditStatus !== 0) return false
        if (filter.value === 'rejected' && r.auditStatus !== 2) return false
        if (filter.value === 'mine' && r.isMine !== true) return false
        return !kw || r.name.toLowerCase().includes(kw)
      })
      .sort((a, b) =>
        (WEIGHT[a.auditStatus] ?? 3) - (WEIGHT[b.auditStatus] ?? 3)
        || a.name.localeCompare(b.name, 'zh-Hans-CN'),
      )
  })

  const hasFilter = computed(() => filter.value !== 'all' || keyword.value.trim() !== '')
  const pendingCount = computed(() => counts.value.pending)

  const collapse = () => {
    expanded.value = null
    rejectRow.value = null
    rejectReason.value = ''
    rejectError.value = ''
    logs.value = []
  }

  const load = async (key = active.value) => {
    try {
      return await RESOURCES[key].api.list()
    } catch (e) {
      showToast.error(e.message)
      return buckets.value[key] || []
    }
  }

  const loadAll = async () => {
    loading.value = true
    try {
      const [t, tp] = await Promise.all([load('tag'), load('type')])
      buckets.value = { tag: t, type: tp }
    } finally {
      loading.value = false
    }
  }

  const refresh = async (msg) => {
    buckets.value = { ...buckets.value, [active.value]: await load(active.value) }
    if (msg) showToast(msg)
    onChanged?.()
  }

  const open = async () => {
    collapse()
    keyword.value = ''
    filter.value = 'all'
    draft.value = ''
    holdPublish.value = false
    await loadAll()
  }

  const switchTab = async (key) => {
    if (key === active.value) return
    switching.value = true
    active.value = key
    collapse()
    keyword.value = ''
    filter.value = 'all'
    try {
      buckets.value = { ...buckets.value, [key]: await load(key) }
    } finally {
      switching.value = false
    }
  }

  const setFilter = (key) => {
    filter.value = filter.value === key ? 'all' : key
    collapse()
  }

  const resetFilters = () => {
    filter.value = 'all'
    keyword.value = ''
    collapse()
  }

  const create = async () => {
    const name = draft.value.trim()
    if (!name || submitting.value) return
    submitting.value = true
    try {
      const publish = isSuperAdmin.value && !holdPublish.value
      await current.value.api.create(name, publish)
      draft.value = ''
      holdPublish.value = false
      await refresh(
        publish
          ? `${current.value.label}已创建并发布`
          : isSuperAdmin.value
            ? `${current.value.label}已创建（未发布）`
            : `${current.value.label}已提交，等待审核`,
      )
    } catch (e) {
      showToast.error(e.message)
    } finally {
      submitting.value = false
    }
  }

  const approve = async (row) => {
    try {
      const data = await current.value.api.review(row.id, 'approve')
      collapse()
      await refresh(data?.msg || '已通过审核并发布')
    } catch (e) {
      showToast.error(e.message)
    }
  }

  const openReject = (row) => {
    expanded.value = { id: row.id, kind: 'reject' }
    rejectRow.value = row
    rejectReason.value = ''
    rejectError.value = ''
    logs.value = []
  }

  const pickReason = (text) => {
    rejectReason.value = text
    rejectError.value = ''
  }

  const confirmReject = async () => {
    const reason = rejectReason.value.trim()
    if (!reason) {
      rejectError.value = '请填写驳回理由，创建者需要知道未通过的原因'
      return
    }
    const row = rejectRow.value
    if (!row) return
    try {
      const data = await current.value.api.review(row.id, 'reject', reason)
      collapse()
      await refresh(data?.msg || '已驳回，理由已通知创建者')
    } catch (e) {
      showToast.error(e.message)
    }
  }

  const resubmit = async (row) => {
    try {
      await current.value.api.resubmit(row.id)
      collapse()
      await refresh('已重新提交，等待审核')
    } catch (e) {
      showToast.error(e.message)
    }
  }

  const remove = async (row) => {
    const ok = await confirmAction({
      title: `删除${current.value.label}`,
      message: `确认删除「${row.name}」？${current.value.deleteHint}`,
    })
    if (!ok) return
    try {
      await current.value.api.remove(row.id)
      collapse()
      await refresh(`${current.value.label}已删除`)
    } catch (e) {
      showToast.error(e.message)
    }
  }

  // 发布 / 取消发布：走 PUT /:id 的 isPublished 字段，后端仅超级管理员可执行。
  // 取消发布会影响全站可见性，先二次确认；发布时若条目尚未通过，后端会同步免审通过。
  const togglePublish = async (row) => {
    const publish = row.isPublished !== true
    if (!publish) {
      const ok = await confirmAction({
        title: `取消发布${current.value.label}`,
        message: `确认取消发布「${row.name}」？普通用户的${current.value.label}列表与筛选将不再显示它；已关联的视频不会被删除，可随时重新发布。`,
      })
      if (!ok) return
    }
    try {
      await current.value.api.update(row.id, { isPublished: publish })
      collapse()
      let msg = `${current.value.label}已取消发布`
      if (publish) {
        msg = row.auditStatus === 1
          ? `${current.value.label}已发布，全站可见`
          : `${current.value.label}已免审通过并发布`
      }
      await refresh(msg)
    } catch (e) {
      showToast.error(e.message)
    }
  }

  const toggleLogs = async (row) => {
    if (expanded.value?.kind === 'logs' && expanded.value.id === row.id) {
      collapse()
      return
    }
    expanded.value = { id: row.id, kind: 'logs' }
    rejectRow.value = null
    logs.value = []
    logsLoading.value = true
    try {
      logs.value = await current.value.api.logs(row.id)
    } catch (e) {
      showToast.error(e.message)
    } finally {
      logsLoading.value = false
    }
  }

  // 权限判定（与后端一致）：管理员可删任意；创建者仅可删自己未通过的条目
  const canDelete = (row) => isSuperAdmin.value || (row.isMine === true && row.auditStatus !== 1)
  const canResubmit = (row) => row.auditStatus === 2 && (isSuperAdmin.value || row.isMine === true)
  const canViewLogs = (row) => canAudit.value || row.isMine === true
  const canReview = (row) => canAudit.value && row.auditStatus === 0

  return {
    active, buckets, rows, current, loading, switching,
    keyword, filter, draft, holdPublish, submitting, hasFilter, counts, pendingCount, filtered,
    expanded, rejectRow, rejectReason, rejectError, logs, logsLoading,
    isSuperAdmin, canAudit, roleText,
    open, switchTab, setFilter, resetFilters, create,
    approve, openReject, pickReason, confirmReject, collapse, resubmit, remove, togglePublish, toggleLogs,
    canDelete, canResubmit, canViewLogs, canReview,
  }
}
