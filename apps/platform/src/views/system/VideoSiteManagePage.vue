<template>
  <div class="console-page">
    <el-tabs v-model="tab" @tab-change="loadTab">
      <el-tab-pane label="数据看板" name="overview" />
      <el-tab-pane label="存储体检" name="storage" />
      <el-tab-pane label="操作审计" name="logs" />
    </el-tabs>

    <div v-loading="loading">
      <!-- 数据看板 -->
      <template v-if="tab === 'overview' && overview">
        <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
          <el-card v-for="s in statCards" :key="s.label" shadow="never">
            <div class="text-xs" style="color: var(--nf-text-muted)">{{ s.label }}</div>
            <div class="text-2xl font-semibold mt-1">{{ s.value }}</div>
          </el-card>
        </div>

        <div class="text-sm font-semibold mb-2">运营趋势</div>
        <div class="grid grid-cols-1 gap-3 md:grid-cols-2 mb-3">
          <el-card shadow="never">
            <template #header>
              <div class="flex items-baseline justify-between gap-2">
                <span>近 14 天观看趋势</span>
                <span class="text-xs" style="color: var(--nf-text-muted)">累计 {{ trendTotal }} 次 · 按用户 / 影片 / 天去重</span>
              </div>
            </template>
            <div class="flex items-end gap-1 h-28">
              <div v-for="p in overview.viewTrend" :key="p.fullDate" class="flex-1 flex items-end h-full"
                   :title="`${p.fullDate}：${p.views} 次观看`">
                <div class="w-full rounded-t bg-[var(--el-color-primary)]"
                     :style="{ height: Math.max(3, (p.views / trendMax) * 100) + '%' }" />
              </div>
            </div>
            <div class="flex items-center justify-between text-xs mt-2" style="color: var(--nf-text-muted)">
              <span>{{ trendFirst }}</span>
              <span>峰值 {{ trendMax }} 次 / 天</span>
              <span>{{ trendLast }}</span>
            </div>
          </el-card>

          <el-card shadow="never">
            <template #header>
              <div class="flex items-baseline justify-between gap-2">
                <span>热门标签 Top 8</span>
                <span class="text-xs" style="color: var(--nf-text-muted)">按已发布标签的关联影片数</span>
              </div>
            </template>
            <div v-if="overview.hotTags.length" class="space-y-2">
              <div v-for="(t, i) in overview.hotTags" :key="t.id" class="flex items-center gap-2.5">
                <span class="w-4 shrink-0 text-xs tabular-nums" style="color: var(--nf-text-muted)">{{ i + 1 }}</span>
                <span class="w-20 shrink-0 truncate text-xs" :title="t.name">{{ t.name }}</span>
                <div class="h-2 flex-1 overflow-hidden rounded-full bg-[var(--el-fill-color-light)]">
                  <div class="h-full rounded-full bg-[var(--el-color-primary)]"
                       :style="{ width: (t.videoCount / hotTagMax) * 100 + '%' }" />
                </div>
                <span class="w-12 shrink-0 text-right text-xs tabular-nums" style="color: var(--nf-text-muted)">{{ t.videoCount }} 部</span>
                <span class="w-16 shrink-0 text-right text-xs tabular-nums" style="color: var(--nf-text-muted)">{{ t.totalViews }} 播放</span>
              </div>
            </div>
            <div v-else class="text-center text-xs py-8" style="color: var(--nf-text-muted)">暂无已发布标签的关联数据</div>
          </el-card>
        </div>

        <el-card shadow="never" class="mb-3">
          <template #header>
            <div class="flex items-baseline justify-between gap-2">
              <span>近 30 天存储增长</span>
              <span class="text-xs" style="color: var(--nf-text-muted)">
                当前 {{ formatBytes(overview.storageGrowth.totalBytes) }} · {{ overview.storageGrowth.totalVideos }} 部影片
              </span>
            </div>
          </template>
          <svg viewBox="0 0 600 120" preserveAspectRatio="none" class="w-full h-28" role="img" aria-label="近 30 天累计存储占用曲线">
            <defs>
              <linearGradient id="siteStorageFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="var(--el-color-primary)" stop-opacity="0.35" />
                <stop offset="100%" stop-color="var(--el-color-primary)" stop-opacity="0.02" />
              </linearGradient>
            </defs>
            <line v-for="y in [10, 60, 110]" :key="y" x1="0" :y1="y" x2="600" :y2="y"
                  stroke="var(--el-border-color-lighter)" stroke-width="1" />
            <polygon v-if="storageArea" :points="storageArea" fill="url(#siteStorageFill)" />
            <polyline v-if="storageLine" :points="storageLine" fill="none" stroke="var(--el-color-primary)"
                      stroke-width="2" vector-effect="non-scaling-stroke" />
          </svg>
          <div class="flex items-center justify-between text-xs mt-2" style="color: var(--nf-text-muted)">
            <span>{{ storageFirst }}</span>
            <span>期间新增 {{ growthAddedVideos }} 部 / {{ formatBytes(growthAddedBytes) }}</span>
            <span>{{ storageLast }}</span>
          </div>
          <p class="text-xs mt-2" style="color: var(--nf-text-muted)">
            口径：按影片入库日归属实际源文件大小并逐日累计；外链视频与磁盘上已找不到的文件不计字节<template v-if="overview.storageGrowth.unmeasured">（{{ overview.storageGrowth.unmeasured }} 条未计量）</template>，但仍计入影片数。曲线为累计占用，删除影片会使历史口径相应变化。
          </p>
        </el-card>

        <el-card shadow="never">
          <template #header>热门影片 Top 5</template>
          <el-table :data="overview.hot" size="small">
            <el-table-column prop="title" label="影片" />
            <el-table-column prop="viewCount" label="播放" width="100" />
            <el-table-column prop="favoriteCount" label="收藏" width="100" />
          </el-table>
        </el-card>
      </template>

      <!-- 存储体检 -->
      <template v-if="tab === 'storage' && integrity">
        <el-card shadow="never" class="mb-3">
          <p class="text-sm">已检查 <b>{{ integrity.total }}</b> 条记录，源文件丢失
            <b :class="integrity.missing.length ? 'text-red-500' : 'text-green-500'">{{ integrity.missing.length }}</b> 条</p>
          <p class="text-xs mt-1" style="color: var(--nf-text-muted)">
            允许的媒体根目录：{{ integrity.roots.join('、') || '（未配置）' }}
          </p>
        </el-card>
        <el-table v-if="integrity.missing.length" :data="integrity.missing" size="small" border class="mb-3">
          <el-table-column prop="title" label="影片" />
          <el-table-column prop="filePath" label="记录的源路径" />
        </el-table>
        <el-card shadow="never">
          <template #header>批量路径重定位</template>
          <p class="text-xs mb-2" style="color: var(--nf-text-muted)">
            换硬盘或迁移机器时使用，只替换路径字符串，不会触发重新审核。建议先预览再应用。
          </p>
          <el-form :inline="true">
            <el-form-item label="旧前缀"><el-input v-model="relocate.oldPrefix" placeholder="如 /Volumes/OldDisk" /></el-form-item>
            <el-form-item label="新前缀"><el-input v-model="relocate.newPrefix" placeholder="如 /Volumes/NewDisk" /></el-form-item>
            <el-form-item>
              <el-button v-permission="'video:admin:manage'" @click="doRelocate(true)">预览</el-button>
              <el-button v-permission="'video:admin:manage'" type="primary" @click="doRelocate(false)">应用</el-button>
            </el-form-item>
          </el-form>
          <div v-if="relocateResult" class="text-sm mt-2">
            {{ relocateResult.dryRun ? '预览' : '应用' }}结果：匹配 {{ relocateResult.updated }} 条
            <span v-if="relocateResult.invalid.length">，{{ relocateResult.invalid.length }} 条路径不合法被跳过</span>
          </div>
        </el-card>
      </template>

      <!-- 操作审计 -->
      <template v-if="tab === 'logs'">
        <tvue-crud
          :option="logOption"
          :data="logData"
          :page="logPage"
          v-model:search="logSearch"
          @on-load="onLogLoad"
        >
          <template #success="{ row }">
            <el-tag :type="row.success ? 'success' : 'danger'" size="small">{{ row.success ? '成功' : '失败' }}</el-tag>
          </template>
        </tvue-crud>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getSiteOverview, getStorageIntegrity, relocateVideoPaths, listAdminLogs,
  type SiteOverview, type AdminLogItem,
} from '../../api'

const tab = ref('overview')
const loading = ref(false)

const overview = ref<SiteOverview | null>(null)
const integrity = ref<{ total: number; missing: Array<{ id: number; title: string; filePath: string }>; roots: string[] } | null>(null)

// ---------- 看板计算（纯前端，不引入图表库） ----------
const formatBytes = (n: number): string => {
  const v = Number(n) || 0
  if (v < 1024) return `${v} B`
  if (v < 1024 ** 2) return `${(v / 1024).toFixed(1)} KB`
  if (v < 1024 ** 3) return `${(v / 1024 ** 2).toFixed(1)} MB`
  return `${(v / 1024 ** 3).toFixed(2)} GB`
}
const trendMax = computed(() => Math.max(1, ...(overview.value?.viewTrend || []).map(p => p.views)))
const trendTotal = computed(() => (overview.value?.viewTrend || []).reduce((sum, p) => sum + p.views, 0))
const trendFirst = computed(() => overview.value?.viewTrend?.[0]?.date || '')
const trendLast = computed(() => {
  const arr = overview.value?.viewTrend || []
  return arr.length ? arr[arr.length - 1].date : ''
})
const hotTagMax = computed(() => Math.max(1, ...(overview.value?.hotTags || []).map(t => t.videoCount)))

const storagePoints = computed(() => overview.value?.storageGrowth?.points || [])
const storageLine = computed(() => {
  const pts = storagePoints.value
  if (!pts.length) return ''
  const max = Math.max(...pts.map(p => p.cumulativeBytes), 1)
  return pts.map((p, i) => {
    const x = pts.length === 1 ? 0 : (i / (pts.length - 1)) * 600
    const y = 110 - (p.cumulativeBytes / max) * 100
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
})
const storageArea = computed(() => storageLine.value ? `0,120 ${storageLine.value} 600,120` : '')
const storageFirst = computed(() => storagePoints.value[0]?.date || '')
const storageLast = computed(() => storagePoints.value.length ? storagePoints.value[storagePoints.value.length - 1].date : '')
const growthAddedVideos = computed(() => storagePoints.value.reduce((sum, p) => sum + p.addedVideos, 0))
const growthAddedBytes = computed(() => storagePoints.value.reduce((sum, p) => sum + p.addedBytes, 0))

const statCards = computed(() => {
  const o = overview.value
  if (!o) return []
  return [
    { label: '影片总数', value: o.videos.total },
    { label: '待审核', value: o.videos.pending },
    { label: '已通过', value: o.videos.approved },
    { label: '已驳回', value: o.videos.rejected },
    { label: '公开影片', value: o.videos.public },
    { label: '累计播放', value: o.videos.views },
    { label: '注册用户', value: o.users },
    { label: '累计收藏', value: o.favorites },
    { label: '近 7 天新增', value: o.addedLast7Days },
    { label: '平均审核时长', value: o.avgAuditHours === null ? '—' : `${o.avgAuditHours} 小时` },
  ]
})

const loadTab = async (): Promise<void> => {
  loading.value = true
  try {
    if (tab.value === 'overview') overview.value = await getSiteOverview()
    else if (tab.value === 'storage') integrity.value = await getStorageIntegrity()
    else if (tab.value === 'logs') await loadLogs()
  } catch (error) { ElMessage.error((error as Error).message) }
  finally { loading.value = false }
}

const relocate = reactive({ oldPrefix: '', newPrefix: '' })
const relocateResult = ref<{ updated: number; invalid: unknown[]; dryRun: boolean } | null>(null)
const doRelocate = async (dryRun: boolean): Promise<void> => {
  try {
    const result = await relocateVideoPaths({ ...relocate, dryRun })
    relocateResult.value = { ...result, dryRun }
    ElMessage.success(dryRun ? `预览：将更新 ${result.updated} 条` : `已更新 ${result.updated} 条路径`)
    if (!dryRun) await loadTab()
  } catch (error) { ElMessage.error((error as Error).message) }
}

const logData = ref<AdminLogItem[]>([])
const logSearch = reactive<Record<string, unknown>>({})
const logPage = reactive({ currentPage: 1, pageSize: 15, total: 0 })
const logOption = reactive<Record<string, unknown>>({
  border: false, stripe: true, addBtn: false, editBtn: false, delBtn: false, menu: false,
  column: [
    { label: '时间', prop: 'createdAt', width: 160 },
    { label: '动作', prop: 'actionText', width: 130 },
    { label: '对象', prop: 'targetName', minWidth: 160 },
    { label: '类型', prop: 'targetTypeText', width: 110 },
    { label: '详情', prop: 'detail', minWidth: 180 },
    { label: '操作人', prop: 'operatorName', width: 120 },
    { label: '角色', prop: 'operatorRole', width: 120 },
  ],
})
const loadLogs = async (done?: () => void): Promise<void> => {
  try {
    const result = await listAdminLogs({ page: logPage.currentPage, pageSize: logPage.pageSize })
    logData.value = result.items
    logPage.total = result.total
  } catch (error) { ElMessage.error((error as Error).message) }
  finally { done?.() }
}
const onLogLoad = async (paged: { currentPage: number; pageSize: number }, _params: Record<string, unknown>, done?: () => void): Promise<void> => {
  if (paged) { logPage.currentPage = paged.currentPage; logPage.pageSize = paged.pageSize }
  await loadLogs(done)
}

onMounted(loadTab)
</script>
