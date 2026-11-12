<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  getAdminOverview, listUsers, setUserRole, createUser, getIntegrity, relocateVideos,
  listCollections, createCollection, deleteCollection,
  listTags, createTag, updateTag, deleteTag,
} from './api'
import { showToast } from './ui/toast'
import { confirmAction } from './ui/confirm'

const router = useRouter()
const goBack = () => router.push({ name: 'list' })

const tab = ref('overview')
const TABS = [
  { key: 'overview', label: '数据看板' },
  { key: 'users', label: '用户与角色' },
  { key: 'storage', label: '存储体检' },
  { key: 'collections', label: '合集管理' },
  { key: 'tags', label: '标签管理' },
]

const loading = ref(false)
const overview = ref(null)
const users = ref([])
const integrity = ref(null)
const collections = ref([])
const tags = ref([])

const loadOverview = async () => {
  try { overview.value = await getAdminOverview() } catch (e) { showToast.error(e.message) }
}
const loadUsers = async () => {
  try { users.value = (await listUsers()).items } catch (e) { showToast.error(e.message) }
}
const loadIntegrity = async () => {
  try { integrity.value = await getIntegrity() } catch (e) { showToast.error(e.message) }
}
const loadCollections = async () => {
  try { collections.value = (await listCollections()).items } catch (e) { showToast.error(e.message) }
}
const loadTags = async () => {
  try { tags.value = await listTags() } catch (e) { showToast.error(e.message) }
}

const loadTab = async (key) => {
  tab.value = key
  loading.value = true
  try {
    if (key === 'overview') await loadOverview()
    else if (key === 'users') await loadUsers()
    else if (key === 'storage') await loadIntegrity()
    else if (key === 'tags') await loadTags()
    else await loadCollections()
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

// ---------- 合集 ----------
const newCollection = reactive({ name: '', description: '' })
const addCollection = async () => {
  if (!newCollection.name.trim()) {
    showToast.warning('请输入合集名称')
    return
  }
  try {
    await createCollection(newCollection.name.trim(), newCollection.description.trim())
    newCollection.name = ''
    newCollection.description = ''
    showToast('合集已创建')
    await loadCollections()
  } catch (e) {
    showToast.error(e.message)
  }
}
const removeCollection = async (row) => {
  const ok = await confirmAction({
    title: '删除合集',
    message: `确认删除合集「${row.name}」？其下 ${row.videoCount} 部影片不会被删除，只会解除关联。`,
  })
  if (!ok) return
  try {
    await deleteCollection(row.id)
    showToast('已删除')
    await loadCollections()
  } catch (e) {
    showToast.error(e.message)
  }
}

// ---------- 标签管理：仅超管可增删改并发布，普通用户只能选用已发布标签 ----------
const newTag = ref('')
const addTag = async () => {
  if (!newTag.value.trim()) {
    showToast.warning('请输入标签名')
    return
  }
  try {
    await createTag(newTag.value.trim())
    showToast(`标签「${newTag.value.trim()}」已创建（未发布），发布后普通用户可见`)
    newTag.value = ''
    await loadTags()
  } catch (e) {
    showToast.error(e.message)
  }
}

const toggleTagPublish = async (row) => {
  try {
    await updateTag(row.id, { isPublished: !row.isPublished })
    showToast(row.isPublished ? `「${row.name}」已下架，普通用户不再可选` : `「${row.name}」已发布`)
    await loadTags()
  } catch (e) {
    showToast.error(e.message)
  }
}

const editingTagId = ref(null) // 当前正在改名的标签 id
const editingTagName = ref('')
const startRenameTag = (row) => {
  editingTagId.value = row.id
  editingTagName.value = row.name
}
const confirmRenameTag = async () => {
  const name = editingTagName.value.trim()
  if (!name) return
  try {
    await updateTag(editingTagId.value, { name })
    showToast('标签已改名')
    editingTagId.value = null
    await loadTags()
  } catch (e) {
    showToast.error(e.message)
  }
}
const cancelRenameTag = () => { editingTagId.value = null }

const removeTag = async (row) => {
  const ok = await confirmAction({
    title: '删除标签',
    message: `确认删除标签「${row.name}」？影片与该标签的关联将一并解除，影片本身不受影响。`,
  })
  if (!ok) return
  try {
    await deleteTag(row.id)
    showToast('已删除')
    await loadTags()
  } catch (e) {
    showToast.error(e.message)
  }
}
</script>

<template>
  <div class="admin-page">
    <header class="admin-head">
      <button class="back-btn" @click="goBack">
        <svg viewBox="0 0 24 24" width="15" height="15">
          <path d="M19 11H7.83l4.88-4.88a1 1 0 1 0-1.42-1.41l-6.29 6.3a1 1 0 0 0 0 1.41l6.29 6.3a1 1 0 0 0 1.42-1.41L7.83 13H19a1 1 0 0 0 0-2z" fill="currentColor" />
        </svg>
        返回
      </button>
      <div>
        <h1 class="admin-title">站点管理</h1>
        <span class="admin-sub">超级管理员专属 · 数据、账号、存储与合集</span>
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
        <button class="nf-btn red" @click="addUser">＋ 创建账号</button>
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
        <button class="nf-btn ghost sm" @click="loadIntegrity">重新检查</button>
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
        <button class="nf-btn ghost" @click="doRelocate(true)">预览</button>
        <button class="nf-btn red" @click="doRelocate(false)">应用替换</button>
      </div>
      <div v-if="relocateResult" class="relocate-result">
        {{ relocateResult.isDryRun ? '预览结果' : '替换结果' }}：匹配 {{ relocateResult.updated }} 条
        <span v-if="relocateResult.invalid.length">，{{ relocateResult.invalid.length }} 条路径不合法被跳过</span>
      </div>
    </section>

    <!-- 合集 -->
    <section v-else-if="tab === 'collections'" class="admin-section">
      <div class="relocate-form">
        <input v-model="newCollection.name" class="nf-input" placeholder="合集名称（如：星际穿越系列）" maxlength="100" />
        <input v-model="newCollection.description" class="nf-input" placeholder="备注（可选）" maxlength="500" />
        <button class="nf-btn red" @click="addCollection">＋ 新建合集</button>
      </div>
      <div class="table-scroll my-3">
        <table class="admin-table">
          <thead><tr><th>名称</th><th>备注</th><th>影片数</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="c in collections" :key="c.id">
              <td>{{ c.name }}</td><td>{{ c.description || '—' }}</td><td>{{ c.videoCount }}</td>
              <td><button class="nf-btn sm ghost danger" @click="removeCollection(c)">删除</button></td>
            </tr>
            <tr v-if="!collections.length"><td colspan="4" class="muted">暂无合集</td></tr>
          </tbody>
        </table>
      </div>
      <p class="block-hint">在「新增/编辑视频」表单里可为影片选择所属合集，列表页可按合集筛选。</p>
    </section>

    <!-- 标签管理 -->
    <section v-else-if="tab === 'tags'" class="admin-section">
      <p class="block-hint">标签由超级管理员统一创建、发布与删除；普通用户在新增/编辑视频时只能从<b>已发布</b>的标签中选择，无法自行创建。新建标签默认未发布，发布后才会出现在普通用户的可选项里。</p>
      <div class="relocate-form">
        <input
          v-model="newTag"
          class="nf-input"
          placeholder="新标签名称（如：科幻 / 高分）"
          maxlength="50"
          @keyup.enter="addTag"
        />
        <button class="nf-btn red" @click="addTag">＋ 新建标签</button>
      </div>
      <div class="table-scroll my-3">
        <table class="admin-table">
          <thead><tr><th>标签名</th><th>状态</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="t in tags" :key="t.id">
              <td>
                <template v-if="editingTagId === t.id">
                  <input
                    v-model="editingTagName"
                    class="nf-input tag-edit-input"
                    maxlength="50"
                    @keyup.enter="confirmRenameTag"
                    @keyup.esc="cancelRenameTag"
                  />
                  <button class="nf-btn sm red" @click="confirmRenameTag">确定</button>
                  <button class="nf-btn sm ghost" @click="cancelRenameTag">取消</button>
                </template>
                <template v-else>{{ t.name }}</template>
              </td>
              <td>
                <span :class="t.isPublished ? 'good' : 'warn-dim'">{{ t.isPublished ? '已发布' : '未发布' }}</span>
              </td>
              <td>
                <button class="nf-btn sm ghost" @click="toggleTagPublish(t)">
                  {{ t.isPublished ? '下架' : '发布' }}
                </button>
                <button class="nf-btn sm ghost" @click="startRenameTag(t)">改名</button>
                <button class="nf-btn sm ghost danger" @click="removeTag(t)">删除</button>
              </td>
            </tr>
            <tr v-if="!tags.length"><td colspan="3" class="muted">暂无标签</td></tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
.admin-page { max-width: 1200px; margin: 0 auto; padding: 26px 40px 60px; }
.admin-head { display: flex; gap: 16px; margin-bottom: 24px; }
.back-btn { display: inline-flex; align-items: center; gap: 6px; height: 34px; padding: 0 15px; border: none; border-radius: 5px; background: rgba(255,255,255,.12); color: #f5f5f5; font-size: 13px; font-weight: 600; cursor: pointer; }
.back-btn:hover { background: rgba(255,255,255,.22); }
.admin-title { margin: 0 0 4px; font-size: 24px; font-weight: 800; letter-spacing: 1px; color: #fff; }
.admin-sub { font-size: 12.5px; color: var(--nf-text-muted); }
.admin-tabs { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 22px; border-bottom: 1px solid #2a2a30; padding-bottom: 12px; }
.tab-btn { padding: 7px 18px; border: 1px solid #33333a; border-radius: 5px; background: #1b1b1f; color: #b3b3b3; font-size: 13px; cursor: pointer; }
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
.block-title { margin: 24px 0 12px; font-size: 16px; font-weight: 700; color: #f5f5f5; }
.block-hint { font-size: 12.5px; line-height: 1.8; color: var(--nf-text-muted); margin: 8px 0 16px; }
.block-hint b { color: #d2d2d2; }
.block-hint code { color: #e6a01e; }
.table-scroll { overflow-x: auto; border: 1px solid #2c2c33; border-radius: 8px; }
.admin-table { width: 100%; min-width: 560px; border-collapse: collapse; font-size: 13px; }
.admin-table th { padding: 11px 14px; text-align: left; color: #8b8b92; font-weight: 600; background: #1b1b1f; border-bottom: 1px solid #2c2c33; white-space: nowrap; }
.admin-table td { padding: 11px 14px; color: #d8d8d8; border-bottom: 1px solid #24242a; }
.admin-table tr:last-child td { border-bottom: none; }
.admin-table code { font-size: 12px; color: #b3b3b3; word-break: break-all; }
.muted { color: var(--nf-text-muted); text-align: center; }
.good { color: #46d369; } .bad { color: var(--nf-red); }
.warn-dim { color: #e6a01e; }
.tag-edit-input { display: inline-block; width: 180px; height: 30px; margin-right: 8px; }
.admin-select { height: 34px; padding: 0 8px; border: 1px solid #38383f; border-radius: 4px; background: #202025; color: #e5e5e5; font-size: 12.5px; }
.integrity-summary { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; font-size: 14px; color: #d2d2d2; }
.integrity-summary b { color: #fff; }
.root-list { display: flex; flex-direction: column; gap: 6px; padding-left: 18px; margin: 0; }
.root-list code { font-size: 12.5px; color: #9fd0ff; word-break: break-all; }
.relocate-form { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.relocate-form .nf-input { flex: 1 1 260px; }
.relocate-result { margin-top: 12px; font-size: 13px; color: #d2d2d2; }
@media (max-width: 700px) { .admin-page { padding: 18px 16px 40px; } }
</style>
