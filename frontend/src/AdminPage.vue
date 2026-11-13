<script setup>
import { ICONS } from './composables/icons'
import FaIcon from './ui/FaIcon.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  getAdminOverview, listUsers, setUserRole, createUser, getIntegrity, relocateVideos,
  listAdminLogs,
} from './api'
import { showToast } from './ui/toast'

const router = useRouter()
const goBack = () => router.push({ name: 'list' })

const tab = ref('overview')
const TABS = [
  { key: 'overview', label: '数据看板' },
  { key: 'users', label: '用户与角色' },
  { key: 'storage', label: '存储体检' },
  { key: 'auditLogs', label: '操作审计' },
]

const loading = ref(false)
const overview = ref(null)
const users = ref([])
const integrity = ref(null)

const loadOverview = async () => {
  try { overview.value = await getAdminOverview() } catch (e) { showToast.error(e.message) }
}
const loadUsers = async () => {
  try { users.value = (await listUsers()).items } catch (e) { showToast.error(e.message) }
}
const loadIntegrity = async () => {
  try { integrity.value = await getIntegrity() } catch (e) { showToast.error(e.message) }
}

// ---------- 操作审计 ----------
const auditLogs = ref([])
const auditTotal = ref(0)
const auditPage = ref(1)
const auditKeyword = ref('')
const auditAction = ref('')
const auditDays = ref(0)
const auditActionOptions = ref([])
const AUDIT_PAGE_SIZE = 15
const auditPageCount = computed(() => Math.max(1, Math.ceil(auditTotal.value / AUDIT_PAGE_SIZE)))

const loadAuditLogs = async () => {
  try {
    const data = await listAdminLogs({
      page: auditPage.value,
      pageSize: AUDIT_PAGE_SIZE,
      keyword: auditKeyword.value.trim(),
      action: auditAction.value,
      days: auditDays.value,
    })
    auditLogs.value = data.items
    auditTotal.value = data.total
    auditActionOptions.value = data.actionOptions
  } catch (e) { showToast.error(e.message) }
}
const searchAuditLogs = async () => {
  auditPage.value = 1
  await loadAuditLogs()
}
const resetAuditFilters = async () => {
  auditKeyword.value = ''
  auditAction.value = ''
  auditDays.value = 0
  await searchAuditLogs()
}
const changeAuditPage = async (delta) => {
  const next = auditPage.value + delta
  if (next < 1 || next > auditPageCount.value) return
  auditPage.value = next
  await loadAuditLogs()
}

const loadTab = async (key) => {
  tab.value = key
  loading.value = true
  try {
    if (key === 'overview') await loadOverview()
    else if (key === 'users') await loadUsers()
    else if (key === 'storage') await loadIntegrity()
    else if (key === 'auditLogs') await loadAuditLogs()
  } finally {
    loading.value = false
  }
}

onMounted(() => loadTab('overview'))

// ---------- 角色 ----------
const ROLE_TEXT = { user: '普通用户', reviewer: '审核员', manager: '管理员', admin: '超级管理员' }
const newUser = reactive({ username: '', password: '', role: 'user' })
const addUser = async () => {
  if (!newUser.username.trim() || !newUser.password) {
    showToast.warning('请输入用户名和密码（至少 6 位）')
    return
  }
  try {
    await createUser(newUser.username.trim(), newUser.password, newUser.role)
    showToast(`账号「${newUser.username.trim()}」已创建`)
    newUser.username = ''
    newUser.password = ''
    await loadUsers()
  } catch (e) {
    showToast.error(e.message)
  }
}
const changeRole = async (row) => {
  try {
    await setUserRole(row.id, row.role)
    showToast(`「${row.username}」已设为${ROLE_TEXT[row.role]}`)
    await loadUsers()
  } catch (e) {
    showToast.error(e.message)
    await loadUsers()
  }
}

// ---------- 存储体检 ----------
const relocate = reactive({ oldPrefix: '', newPrefix: '' })
const relocateResult = ref(null)

const doRelocate = async (dryRun) => {
  if (!relocate.oldPrefix.trim() || !relocate.newPrefix.trim()) {
    showToast.warning('请填写旧前缀与新前缀')
    return
  }
  try {
    const data = await relocateVideos(relocate.oldPrefix.trim(), relocate.newPrefix.trim(), dryRun)
    relocateResult.value = { ...data, isDryRun: dryRun }
    showToast(dryRun
      ? `预览：将更新 ${data.updated} 条记录`
      : `已更新 ${data.updated} 条路径（仅替换路径，不触发重新审核）`)
    if (!dryRun) await loadIntegrity()
  } catch (e) {
    showToast.error(e.message)
  }
}

// ---------- 看板图表（纯前端计算，不引入图表库） ----------
const formatBytes = (n) => {
  const v = Number(n) || 0
  if (v < 1024) return `${v} B`
  if (v < 1024 ** 2) return `${(v / 1024).toFixed(1)} KB`
  if (v < 1024 ** 3) return `${(v / 1024 ** 2).toFixed(1)} MB`
  return `${(v / 1024 ** 3).toFixed(2)} GB`
}
const trendMax = computed(() =>
  Math.max(1, ...(overview.value?.viewTrend || []).map((p) => p.views)))
const trendTotal = computed(() =>
  (overview.value?.viewTrend || []).reduce((sum, p) => sum + p.views, 0))
const hotTagMax = computed(() =>
  Math.max(1, ...(overview.value?.hotTags || []).map((t) => t.videoCount)))
const storagePoints = computed(() => overview.value?.storageGrowth?.points || [])
const storageLine = computed(() => {
  const pts = storagePoints.value
  if (!pts.length) return ''
  const max = Math.max(...pts.map((p) => p.cumulativeBytes), 1)
  return pts.map((p, i) => {
    const x = pts.length === 1 ? 0 : (i / (pts.length - 1)) * 600
    const y = 110 - (p.cumulativeBytes / max) * 100
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
})
const storageArea = computed(() =>
  storageLine.value ? `0,120 ${storageLine.value} 600,120` : '')
const trendFirst = computed(() => overview.value?.viewTrend?.[0]?.date || '')
const trendLast = computed(() => {
  const arr = overview.value?.viewTrend || []
  return arr.length ? arr[arr.length - 1].date : ''
})
const storageFirst = computed(() => storagePoints.value[0]?.date || '')
const storageLast = computed(() =>
  storagePoints.value.length ? storagePoints.value[storagePoints.value.length - 1].date : '')
const growthAddedVideos = computed(() =>
  storagePoints.value.reduce((sum, p) => sum + p.addedVideos, 0))
const growthAddedBytes = computed(() =>
  storagePoints.value.reduce((sum, p) => sum + p.addedBytes, 0))

</script>

<template>
  <div class="admin-page">
    <header class="admin-head">
      <button class="back-btn" @click="goBack">
        <FaIcon :icon="ICONS.back" :fixed="false" class="text-[15px]" />
        返回
      </button>
      <div>
        <h1 class="admin-title">站点管理</h1>
        <span class="admin-sub">超级管理员专属 · 数据、账号、存储与操作审计</span>
      </div>
    </header>

    <div class="admin-tabs">
      <button
        v-for="t in TABS"
        :key="t.key"
        class="tab-btn"
        :class="{ on: tab === t.key }"
        @click="loadTab(t.key)"
      >{{ t.label }}</button>
    </div>

    <div v-if="loading" class="admin-loading"><div class="nf-loading"></div></div>

    <!-- 数据看板 -->
    <section v-else-if="tab === 'overview' && overview" class="admin-section">
      <div class="stat-grid">
        <div class="stat-card"><span>影片总数</span><b>{{ overview.videos.total }}</b></div>
        <div class="stat-card"><span>待审核</span><b class="warn">{{ overview.videos.pending }}</b></div>
        <div class="stat-card"><span>已通过</span><b class="good">{{ overview.videos.approved }}</b></div>
        <div class="stat-card"><span>已驳回</span><b class="bad">{{ overview.videos.rejected }}</b></div>
        <div class="stat-card"><span>公开影片</span><b>{{ overview.videos.public }}</b></div>
        <div class="stat-card"><span>累计播放</span><b>{{ overview.videos.views }}</b></div>
        <div class="stat-card"><span>注册用户</span><b>{{ overview.users }}</b></div>
        <div class="stat-card"><span>累计收藏</span><b>{{ overview.favorites }}</b></div>
        <div class="stat-card"><span>近 7 天新增</span><b>{{ overview.addedLast7Days }}</b></div>
        <div class="stat-card"><span>平均审核时长</span><b>{{ overview.avgAuditHours === null ? '—' : overview.avgAuditHours + ' 小时' }}</b></div>
      </div>
      <!-- ===== 运营趋势：观看趋势 / 热门标签 / 存储增长 ===== -->
      <h3 class="block-title">运营趋势</h3>
      <div class="grid grid-cols-1 gap-3.5 min-[900px]:grid-cols-2">
        <!-- 近 14 天观看趋势 -->
        <div class="chart-card">
          <div class="flex flex-wrap items-baseline justify-between gap-2">
            <span class="chart-title"><FaIcon :icon="ICONS.chart" :fixed="false" class="text-nf-red" />近 14 天观看趋势</span>
            <span class="text-[11px] text-nf-muted">累计 {{ trendTotal }} 次 · 按用户 / 影片 / 天去重</span>
          </div>
          <div class="mt-3 flex h-[118px] items-end gap-[5px]">
            <div
              v-for="p in overview.viewTrend"
              :key="p.fullDate"
              class="group flex h-full flex-1 items-end"
              :title="`${p.fullDate}：${p.views} 次观看`"
            >
              <div
                class="w-full rounded-t-[3px] transition-colors"
                :class="p.views ? 'bg-nf-red/65 group-hover:bg-nf-red' : 'bg-white/10'"
                :style="{ height: Math.max(3, (p.views / trendMax) * 100) + '%' }"
              ></div>
            </div>
          </div>
          <div class="mt-2 flex items-center justify-between text-[10.5px] text-nf-muted">
            <span>{{ trendFirst }}</span>
            <span>峰值 {{ trendMax }} 次 / 天</span>
            <span>{{ trendLast }}</span>
          </div>
        </div>

        <!-- 热门标签 Top 8 -->
        <div class="chart-card">
          <div class="flex flex-wrap items-baseline justify-between gap-2">
            <span class="chart-title"><FaIcon :icon="ICONS.taxonomy" :fixed="false" class="text-nf-red" />热门标签 Top 8</span>
            <span class="text-[11px] text-nf-muted">按已发布标签的关联影片数</span>
          </div>
          <div v-if="overview.hotTags.length" class="mt-3 space-y-2">
            <div v-for="(t, i) in overview.hotTags" :key="t.id" class="flex items-center gap-2.5">
              <span class="w-4 shrink-0 text-[11px] tabular-nums text-nf-muted">{{ i + 1 }}</span>
              <span class="w-[76px] shrink-0 truncate text-[12px] text-nf-text" :title="t.name">{{ t.name }}</span>
              <div class="h-2 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
                <div
                  class="h-full rounded-full bg-gradient-to-r from-nf-red/70 to-[#ff8a90]"
                  :style="{ width: (t.videoCount / hotTagMax) * 100 + '%' }"
                ></div>
              </div>
              <span class="w-14 shrink-0 text-right text-[11px] tabular-nums text-nf-sub">{{ t.videoCount }} 部</span>
              <span class="w-16 shrink-0 text-right text-[11px] tabular-nums text-nf-muted">{{ t.totalViews }} 播放</span>
            </div>
          </div>
          <div v-else class="mt-6 text-center text-[12px] text-nf-muted">暂无已发布标签的关联数据</div>
        </div>
      </div>

      <!-- 近 30 天存储增长曲线 -->
      <div class="chart-card mt-3.5">
        <div class="flex flex-wrap items-baseline justify-between gap-2">
          <span class="chart-title"><FaIcon :icon="ICONS.hardDrive" :fixed="false" class="text-nf-red" />近 30 天存储增长</span>
          <span class="text-[11px] text-nf-muted">
            当前 {{ formatBytes(overview.storageGrowth.totalBytes) }} · {{ overview.storageGrowth.totalVideos }} 部影片
          </span>
        </div>
        <svg viewBox="0 0 600 120" preserveAspectRatio="none" class="mt-3 h-[120px] w-full" role="img" aria-label="近 30 天累计存储占用曲线">
          <defs>
            <linearGradient id="nfStorageFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#e50914" stop-opacity="0.35" />
              <stop offset="100%" stop-color="#e50914" stop-opacity="0.02" />
            </linearGradient>
          </defs>
          <line v-for="y in [10, 60, 110]" :key="y" x1="0" :y1="y" x2="600" :y2="y" stroke="var(--nf-overlay-soft)" stroke-width="1" />
          <polygon v-if="storageArea" :points="storageArea" fill="url(#nfStorageFill)" />
          <polyline v-if="storageLine" :points="storageLine" fill="none" stroke="#e50914" stroke-width="2" vector-effect="non-scaling-stroke" />
        </svg>
        <div class="mt-2 flex items-center justify-between text-[10.5px] text-nf-muted">
          <span>{{ storageFirst }}</span>
          <span>期间新增 {{ growthAddedVideos }} 部 / {{ formatBytes(growthAddedBytes) }}</span>
          <span>{{ storageLast }}</span>
        </div>
        <p class="block-hint mt-2">
          口径：按影片入库日归属实际源文件大小并逐日累计；外链视频与磁盘上已找不到的文件不计字节
          <template v-if="overview.storageGrowth.unmeasured">（{{ overview.storageGrowth.unmeasured }} 条未计量）</template>，
          但仍计入影片数。曲线为累计占用，删除影片会使历史口径相应变化。
        </p>
      </div>

      <h3 class="block-title">热门影片 Top 5</h3>
      <table class="admin-table">
        <thead><tr><th>影片</th><th>播放</th><th>收藏</th></tr></thead>
        <tbody>
          <tr v-for="r in overview.hot" :key="r.id">
            <td>{{ r.title }}</td><td>{{ r.viewCount }}</td><td>{{ r.favoriteCount }}</td>
          </tr>
          <tr v-if="!overview.hot.length"><td colspan="3" class="muted">暂无数据</td></tr>
        </tbody>
      </table>
    </section>

    <!-- 用户与角色 -->
    <section v-else-if="tab === 'users'" class="admin-section">
      <p class="block-hint">角色层级：超级管理员可看/管全部；管理员可看并可审平级及以下用户（管理员、审核员、普通用户）的视频，但不能管理他人内容；审核员可审核全部视频；普通用户只能看自己的视频和已过审的公开视频。关闭注册（config.py 的 REGISTRATION_ENABLED = False）后，可在此统一创建账号。</p>
      <div class="relocate-form">
        <input v-model="newUser.username" class="nf-input" placeholder="新账号用户名" maxlength="50" />
        <input v-model="newUser.password" class="nf-input" type="password" placeholder="初始密码（至少 6 位）" />
        <select v-model="newUser.role" class="admin-select">
          <option value="user">普通用户</option>
          <option value="manager">管理员</option>
          <option value="reviewer">审核员</option>
          <option value="admin">超级管理员</option>
        </select>
        <button class="nf-btn red" @click="addUser"><FaIcon :icon="ICONS.userAdd" :fixed="false" />创建账号</button>
      </div>
      <div class="table-scroll my-3">
        <table class="admin-table">
          <thead><tr><th>ID</th><th>用户名</th><th>角色</th><th>影片数</th><th>注册时间</th></tr></thead>
          <tbody>
            <tr v-for="u in users" :key="u.id">
              <td>{{ u.id }}</td>
              <td>{{ u.username }}</td>
              <td>
                <select v-model="u.role" class="admin-select" @change="changeRole(u)">
                  <option value="user">普通用户</option>
                  <option value="manager">管理员</option>
                  <option value="reviewer">审核员</option>
                  <option value="admin">超级管理员</option>
                </select>
              </td>
              <td>{{ u.videoCount }}</td>
              <td>{{ u.createdAt }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- 存储体检 -->
    <section v-else-if="tab === 'storage' && integrity" class="admin-section">
      <div class="integrity-summary">
        <span>已检查 <b>{{ integrity.total }}</b> 条记录，</span>
        <span :class="integrity.missing.length ? 'bad' : 'good'">源文件丢失 <b>{{ integrity.missing.length }}</b> 条</span>
        <button class="nf-btn ghost sm" @click="loadIntegrity"><FaIcon :icon="ICONS.refresh" :fixed="false" />重新检查</button>
      </div>
      <h3 class="block-title">允许的媒体根目录</h3>
      <ul class="root-list">
        <li v-for="r in integrity.roots" :key="r"><code>{{ r }}</code></li>
      </ul>
      <p class="block-hint">视频若放在其他位置，请在 <code>backend/config.py</code> 的 <code>MEDIA_ROOTS</code> 中登记后重启后端。</p>

      <div class="table-scroll my-3" v-if="integrity.missing.length">
        <table class="admin-table">
          <thead><tr><th>影片</th><th>记录的源路径</th></tr></thead>
          <tbody>
            <tr v-for="m in integrity.missing" :key="m.id">
              <td>{{ m.title }}</td><td><code>{{ m.filePath || '（未设置）' }}</code></td>
            </tr>
          </tbody>
        </table>
      </div>

      <h3 class="block-title">批量路径重定位</h3>
      <p class="block-hint">换硬盘、改盘符或迁移到新机器时使用。只替换路径字符串，<b>不会</b>触发重新审核。建议先预览再应用。</p>
      <div class="relocate-form">
        <input v-model="relocate.oldPrefix" class="nf-input" placeholder="旧前缀，如 /Volumes/OldDisk/Movies" />
        <input v-model="relocate.newPrefix" class="nf-input" placeholder="新前缀，如 /Volumes/NewDisk/Movies" />
        <button class="nf-btn ghost" @click="doRelocate(true)"><FaIcon :icon="ICONS.views" :fixed="false" />预览</button>
        <button class="nf-btn red" @click="doRelocate(false)"><FaIcon :icon="ICONS.check" :fixed="false" />应用替换</button>
      </div>
      <div v-if="relocateResult" class="relocate-result">
        {{ relocateResult.isDryRun ? '预览结果' : '替换结果' }}：匹配 {{ relocateResult.updated }} 条
        <span v-if="relocateResult.invalid.length">，{{ relocateResult.invalid.length }} 条路径不合法被跳过</span>
      </div>
    </section>

    <!-- 操作审计 -->
    <section v-else-if="tab === 'auditLogs'" class="admin-section">
      <p class="block-hint">
        记录全站敏感管理动作：调整角色、创建账号、删除视频 / 合集 / 标签 / 类型、发布下架与路径重定位。
        只追加、不可修改；操作人与对象均保存名称快照，账号或对象删除后历史仍可追溯。
        合集已接入审核模型，统一在导航「更多 → 标签 / 类型管理」工作台的「合集」分页中提交与审核，此处不再重复提供管理入口。
      </p>
      <div class="relocate-form mb-3">
        <input
          v-model="auditKeyword"
          class="nf-input"
          placeholder="搜索操作人 / 对象 / 详情"
          maxlength="50"
          @keyup.enter="searchAuditLogs"
        />
        <select v-model="auditAction" class="admin-select" @change="searchAuditLogs">
          <option value="">全部动作</option>
          <option v-for="a in auditActionOptions" :key="a.value" :value="a.value">{{ a.label }}</option>
        </select>
        <select v-model.number="auditDays" class="admin-select" @change="searchAuditLogs">
          <option :value="0">全部时间</option>
          <option :value="7">近 7 天</option>
          <option :value="30">近 30 天</option>
          <option :value="90">近 90 天</option>
        </select>
        <button class="nf-btn ghost" @click="searchAuditLogs"><FaIcon :icon="ICONS.search" :fixed="false" />搜索</button>
        <button class="nf-btn ghost" @click="resetAuditFilters"><FaIcon :icon="ICONS.reset" :fixed="false" />重置</button>
      </div>
      <div class="table-scroll">
        <table class="admin-table">
          <thead><tr><th>时间</th><th>动作</th><th>对象</th><th>详情</th><th>操作人</th><th>角色</th></tr></thead>
          <tbody>
            <tr v-for="l in auditLogs" :key="l.id">
              <td class="whitespace-nowrap text-[12px] text-nf-muted">{{ l.createdAt }}</td>
              <td><span class="audit-action">{{ l.actionText }}</span></td>
              <td>
                <span class="text-nf-text">{{ l.targetName || '—' }}</span>
                <span class="text-[11px] text-nf-muted">（{{ l.targetTypeText }}）</span>
              </td>
              <td>{{ l.detail || '—' }}</td>
              <td class="whitespace-nowrap">{{ l.operatorName }}</td>
              <td class="whitespace-nowrap text-[12px] text-nf-muted">{{ ROLE_TEXT[l.operatorRole] || l.operatorRole || '—' }}</td>
            </tr>
            <tr v-if="!auditLogs.length"><td colspan="6" class="muted">暂无匹配的操作记录</td></tr>
          </tbody>
        </table>
      </div>
      <div class="audit-pager">
        <span>共 {{ auditTotal }} 条 · 第 {{ auditPage }} / {{ auditPageCount }} 页</span>
        <div class="flex items-center gap-2">
          <button class="nf-btn ghost sm" :disabled="auditPage <= 1" @click="changeAuditPage(-1)">
            <FaIcon :icon="ICONS.prev" :fixed="false" />上一页
          </button>
          <button class="nf-btn ghost sm" :disabled="auditPage >= auditPageCount" @click="changeAuditPage(1)">
            下一页<FaIcon :icon="ICONS.next" :fixed="false" />
          </button>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.admin-page { max-width: 1200px; margin: 0 auto; padding: 26px 40px 60px; }
.admin-head { display: flex; gap: 16px; margin-bottom: 24px; }
.back-btn { display: inline-flex; align-items: center; gap: 6px; height: 34px; padding: 0 15px; border: none; border-radius: 5px; background: var(--nf-overlay); color: var(--nf-text-primary); font-size: 13px; font-weight: 600; cursor: pointer; }
.back-btn:hover { background: var(--nf-overlay-strong); }
.admin-title { margin: 0 0 4px; font-size: 24px; font-weight: 800; letter-spacing: 1px; color: #fff; }
.admin-sub { font-size: 12.5px; color: var(--nf-text-muted); }
.admin-tabs { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 22px; border-bottom: 1px solid #2a2a30; padding-bottom: 12px; }
.tab-btn { padding: 7px 18px; border: 1px solid #33333a; border-radius: 5px; background: #1b1b1f; color: var(--nf-text-secondary); font-size: 13px; cursor: pointer; }
.tab-btn:hover { color: #fff; }
.tab-btn.on { background: var(--nf-red); border-color: var(--nf-red); color: #fff; font-weight: 700; }
.admin-loading { display: flex; justify-content: center; padding: 60px 0; }
.admin-section { animation: fade .2s ease; }
@keyframes fade { from { opacity: 0 } to { opacity: 1 } }
.stat-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; margin-bottom: 30px; }
.stat-card { display: flex; flex-direction: column; gap: 8px; padding: 16px; border: 1px solid #2c2c33; border-radius: 8px; background: #161619; }
.stat-card span { font-size: 12.5px; color: var(--nf-text-muted); }
.stat-card b { font-size: 24px; color: #fff; }
.stat-card b.warn { color: #e6a01e; } .stat-card b.good { color: #46d369; } .stat-card b.bad { color: var(--nf-red); }
.block-title { margin: 24px 0 12px; font-size: 16px; font-weight: 700; color: var(--nf-text-primary); }
.block-hint { font-size: 12.5px; line-height: 1.8; color: var(--nf-text-muted); margin: 8px 0 16px; }
.block-hint b { color: var(--nf-text-secondary); }
.block-hint code { color: #e6a01e; }
.table-scroll { overflow-x: auto; border: 1px solid #2c2c33; border-radius: 8px; }
.admin-table { width: 100%; min-width: 560px; border-collapse: collapse; font-size: 13px; }
.admin-table th { padding: 11px 14px; text-align: left; color: #8b8b92; font-weight: 600; background: #1b1b1f; border-bottom: 1px solid #2c2c33; white-space: nowrap; }
.admin-table td { padding: 11px 14px; color: var(--nf-text-secondary); border-bottom: 1px solid #24242a; }
.admin-table tr:last-child td { border-bottom: none; }
.admin-table code { font-size: 12px; color: var(--nf-text-secondary); word-break: break-all; }
.muted { color: var(--nf-text-muted); text-align: center; }
.good { color: #46d369; } .bad { color: var(--nf-red); }
.warn-dim { color: #e6a01e; }
.tag-edit-input { display: inline-block; width: 180px; height: 30px; margin-right: 8px; }
.admin-select { height: 34px; padding: 0 8px; border: 1px solid #38383f; border-radius: 4px; background: #202025; color: var(--nf-text-primary); font-size: 12.5px; }
.integrity-summary { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; font-size: 14px; color: var(--nf-text-secondary); }
.integrity-summary b { color: #fff; }
.root-list { display: flex; flex-direction: column; gap: 6px; padding-left: 18px; margin: 0; }
.root-list code { font-size: 12.5px; color: #9fd0ff; word-break: break-all; }
.relocate-form { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.relocate-form .nf-input { flex: 1 1 260px; }
.relocate-result { margin-top: 12px; font-size: 13px; color: var(--nf-text-secondary); }
/* 运营趋势图表 / 操作审计 */
.chart-card { padding: 16px 18px; border: 1px solid #2c2c33; border-radius: 8px; background: #161619; }
.chart-title { display: inline-flex; align-items: center; gap: 7px; font-size: 13.5px; font-weight: 700; color: var(--nf-text-primary); }
.audit-action { display: inline-block; padding: 3px 8px; border-radius: 4px; background: rgba(229,9,20,.12); color: #ff8a90; font-size: 11.5px; font-weight: 600; white-space: nowrap; }
.audit-pager { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; margin-top: 14px; font-size: 12.5px; color: var(--nf-text-muted); }
.audit-pager .nf-btn:disabled { opacity: .45; cursor: not-allowed; }
@media (max-width: 700px) { .admin-page { padding: 18px 16px 40px; } .chart-card { padding: 14px; } }
</style>
