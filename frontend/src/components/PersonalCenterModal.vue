<script setup>
import { ICONS } from '../composables/icons'
import FaIcon from '../ui/FaIcon.vue'
import { computed, ref, watch } from 'vue'
import NfModal from '../ui/NfModal.vue'
import { useAuth } from '../composables/useAuth'
import { changePassword, uploadAvatar, avatarUrl, listPlaylists, createPlaylist, updatePlaylist, deletePlaylist } from '../api'
import { showToast } from '../ui/toast'
import { confirmAction } from '../ui/confirm'

const props = defineProps({ modelValue: { type: Boolean, default: false } })
const emit = defineEmits(['update:modelValue', 'logout', 'view-playlist'])
const close = () => emit('update:modelValue', false)

const { user, patchUser } = useAuth()

// ===== 角色中文映射 =====
const ROLE_LABEL = { admin: '超级管理员', manager: '管理员', reviewer: '审核员', user: '普通用户' }
const roleLabel = computed(() => ROLE_LABEL[user.value?.role] || '普通用户')

const initial = computed(() => (user.value?.username || '?').slice(0, 1).toUpperCase())

// ===== 头像预览 =====
const ts = ref(Date.now())
const avatarError = ref(false)
const avatarSrc = computed(() => avatarUrl(ts.value))
const fileInput = ref(null)

// 每次打开重置图片错误回退态，并确保重新加载「我的片单」
watch(
  () => props.modelValue,
  (open) => { if (open) { avatarError.value = false; loadPlaylists() } },
)

// ===== 我的片单：个人独立维度，与系统合集（管理员维度）互不干扰 =====
const playlists = ref([])
const newPlaylistName = ref('')
const editingId = ref(0)
const editingName = ref('')
const creatingPlaylist = ref(false)

const loadPlaylists = async () => {
  try {
    const data = await listPlaylists()
    playlists.value = data.items || []
  } catch (err) {
    showToast.error(err.message)
  }
}

const addPlaylist = async () => {
  const name = newPlaylistName.value.trim()
  if (!name) return showToast.error('请输入片单名称')
  creatingPlaylist.value = true
  try {
    const data = await createPlaylist(name)
    playlists.value.unshift(data)
    newPlaylistName.value = ''
    showToast('片单已创建')
  } catch (err) {
    showToast.error(err.message)
  } finally {
    creatingPlaylist.value = false
  }
}

const startRename = (row) => {
  editingId.value = row.id
  editingName.value = row.name
}

const confirmRename = async () => {
  const name = editingName.value.trim()
  if (!name) return showToast.error('请输入片单名称')
  const id = editingId.value
  try {
    await updatePlaylist(id, name)
    const row = playlists.value.find((p) => p.id === id)
    if (row) row.name = name
    editingId.value = 0
    showToast('已重命名')
  } catch (err) {
    showToast.error(err.message)
  }
}

const delPlaylist = async (row) => {
  const ok = await confirmAction({
    title: '删除片单',
    message: `确认删除片单「${row.name}」？\n片单内的影片不会被删除，仅移除该片单归类。`,
  })
  if (!ok) return
  try {
    await deletePlaylist(row.id)
    playlists.value = playlists.value.filter((p) => p.id !== row.id)
    showToast('片单已删除')
  } catch (err) {
    showToast.error(err.message)
  }
}

const viewPlaylist = (row) => {
  close()
  emit('view-playlist', row.id)
}
// 头像时间戳变化（上传成功）后允许重新加载图片
watch(ts, () => { avatarError.value = false })

const pickAvatar = () => fileInput.value?.click()
const onAvatarChange = async (e) => {
  const file = e.target.files?.[0]
  e.target.value = '' // 允许重复选择同一文件
  if (!file) return
  try {
    const data = await uploadAvatar(file)
    patchUser({ avatar: data.avatar })
    ts.value = Date.now()
    showToast('头像已更新')
  } catch (err) {
    showToast.error(err.message)
  }
}

// ===== 修改密码 =====
const form = ref({ old: '', next: '', confirm: '' })
const saving = ref(false)

const submitPassword = async () => {
  const { old, next, confirm } = form.value
  if (!old) return showToast.error('请输入当前密码')
  if (next.length < 6) return showToast.error('新密码至少 6 位')
  if (next !== confirm) return showToast.error('两次输入的新密码不一致')
  saving.value = true
  try {
    await changePassword(old, next)
    showToast('密码修改成功，请牢记新密码')
    form.value = { old: '', next: '', confirm: '' }
  } catch (err) {
    showToast.error(err.message)
  } finally {
    saving.value = false
  }
}

const onLogout = () => {
  close()
  emit('logout')
}
</script>

<template>
  <NfModal :model-value="modelValue" title="个人中心" width="480px" @update:model-value="emit('update:modelValue', $event)">
    <!-- 资料卡：头像 + 账号信息 -->
    <div class="pc-card">
      <div class="pc-avatar">
        <img
          v-if="user.avatar && !avatarError"
          :src="avatarSrc"
          class="pc-avatar-img"
          alt="头像"
          @error="avatarError = true"
        />
        <span v-else class="pc-avatar-letter">{{ initial }}</span>
        <button class="pc-avatar-edit" @click="pickAvatar"><FaIcon :icon="ICONS.camera" :fixed="false" />上传头像</button>
        <input
          ref="fileInput"
          type="file"
          accept="image/png,image/jpeg,image/gif,image/webp"
          hidden
          @change="onAvatarChange"
        />
      </div>
      <div class="pc-meta">
        <div class="pc-name">{{ user.username }}</div>
        <div class="pc-role">
          <span class="pc-role-tag">{{ roleLabel }}</span>
        </div>
        <div class="pc-tip">支持 png / jpg / gif / webp，大小不超过 5MB</div>
      </div>
    </div>

    <!-- 修改密码 -->
    <div class="pc-section-title">修改密码</div>
    <form class="pc-form" @submit.prevent="submitPassword">
      <div class="nf-field">
        <label class="nf-label">当前密码</label>
        <input
          v-model="form.old"
          class="nf-input"
          type="password"
          autocomplete="current-password"
          placeholder="请输入当前密码"
        />
      </div>
      <div class="nf-field">
        <label class="nf-label">新密码</label>
        <input
          v-model="form.next"
          class="nf-input"
          type="password"
          autocomplete="new-password"
          placeholder="至少 6 位"
        />
      </div>
      <div class="nf-field">
        <label class="nf-label">确认新密码</label>
        <input
          v-model="form.confirm"
          class="nf-input"
          type="password"
          autocomplete="new-password"
          placeholder="再次输入新密码"
        />
      </div>
      <button class="nf-btn red pc-submit" type="submit" :disabled="saving">
        {{ saving ? '保存中…' : '修改密码' }}
      </button>
    </form>

    <!-- 我的片单：个人自建，与系统合集独立 -->
    <div class="pc-section-title">我的片单</div>
    <div class="pc-playlist-new">
      <input
        v-model="newPlaylistName"
        class="nf-input"
        placeholder="新建片单名称"
        maxlength="50"
        @keyup.enter="addPlaylist"
      />
      <button class="nf-btn red" :disabled="creatingPlaylist" @click="addPlaylist">
        <FaIcon :icon="ICONS.playlistAdd" :fixed="false" />新建
      </button>
    </div>
    <ul v-if="playlists.length" class="pc-playlist-list">
      <li v-for="row in playlists" :key="row.id" class="pc-playlist-row">
        <template v-if="editingId === row.id">
          <input v-model="editingName" class="nf-input pc-playlist-rename" maxlength="50" @keyup.enter="confirmRename" />
          <button class="nf-btn sm red" @click="confirmRename"><FaIcon :icon="ICONS.check" :fixed="false" />确定</button>
          <button class="nf-btn sm ghost" @click="editingId = 0"><FaIcon :icon="ICONS.close" :fixed="false" />取消</button>
        </template>
        <template v-else>
          <FaIcon :icon="ICONS.playlist" :fixed="false" class="pc-playlist-ico" />
          <span class="pc-playlist-name" :title="row.name">{{ row.name }}</span>
          <span class="pc-playlist-count">{{ row.videoCount }} 部</span>
          <div class="pc-playlist-ops">
            <button class="nf-btn sm ghost" @click="viewPlaylist(row)"><FaIcon :icon="ICONS.playlist" :fixed="false" />查看</button>
            <button class="nf-btn sm ghost" @click="startRename(row)"><FaIcon :icon="ICONS.edit" :fixed="false" />重命名</button>
            <button class="nf-btn sm ghost danger" @click="delPlaylist(row)"><FaIcon :icon="ICONS.remove" :fixed="false" />删除</button>
          </div>
        </template>
      </li>
    </ul>
    <div v-else class="pc-playlist-empty">还没有片单，用上方输入框创建第一个吧</div>

    <template #footer>
      <button class="nf-btn ghost" @click="close"><FaIcon :icon="ICONS.close" :fixed="false" />关闭</button>
      <button class="nf-btn text" @click="onLogout"><FaIcon :icon="ICONS.logout" :fixed="false" />退出登录</button>
    </template>
  </NfModal>
</template>

<style scoped>
/* ===== 资料卡 ===== */
.pc-card {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 16px;
  border: 1px solid var(--nf-border);
  border-radius: 10px;
  background: var(--nf-bg-elevated);
}

.pc-avatar {
  position: relative;
  width: 76px;
  height: 76px;
  flex-shrink: 0;
}

.pc-avatar-img,
.pc-avatar-letter {
  width: 76px;
  height: 76px;
  border-radius: 50%;
  object-fit: cover;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--nf-red);
  color: #fff;
  font-size: 30px;
  font-weight: 800;
  box-shadow: 0 0 0 1px var(--nf-overlay);
}

.pc-avatar-edit {
  position: absolute;
  left: 50%;
  bottom: -10px;
  transform: translateX(-50%);
  padding: 3px 10px;
  border: 1px solid var(--nf-border);
  border-radius: 12px;
  background: #2a2a30;
  color: var(--nf-text-secondary);
  font-size: 11px;
  white-space: nowrap;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.pc-avatar-edit:hover {
  background: var(--nf-red);
  color: #fff;
  border-color: var(--nf-red);
}

.pc-meta {
  min-width: 0;
}

.pc-name {
  font-size: 18px;
  font-weight: 700;
  color: #fff;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pc-role {
  margin-top: 6px;
}

.pc-role-tag {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 10px;
  background: rgba(229, 9, 20, 0.18);
  color: #ff8a90;
  font-size: 12px;
  font-weight: 600;
}

.pc-tip {
  margin-top: 8px;
  font-size: 11.5px;
  color: var(--nf-text-muted);
}

/* ===== 分区标题 ===== */
.pc-section-title {
  margin: 22px 0 14px;
  padding-left: 12px;
  position: relative;
  font-size: 14px;
  font-weight: 700;
  color: #fff;
}

.pc-section-title::before {
  content: '';
  position: absolute;
  left: 0;
  top: 2px;
  bottom: 2px;
  width: 3px;
  border-radius: 2px;
  background: var(--nf-red);
}

.pc-submit {
  width: 100%;
  margin-top: 4px;
}

/* ===== 我的片单 ===== */
.pc-playlist-new {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.pc-playlist-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.pc-playlist-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border: 1px solid var(--nf-border);
  border-radius: 9px;
  background: var(--nf-bg-elevated);
}

.pc-playlist-ico {
  color: var(--nf-red);
  font-size: 15px;
  flex-shrink: 0;
}

.pc-playlist-name {
  flex: 1;
  min-width: 0;
  font-size: 13.5px;
  color: #fff;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pc-playlist-count {
  flex-shrink: 0;
  font-size: 11.5px;
  color: var(--nf-text-muted);
  font-variant-numeric: tabular-nums;
}

.pc-playlist-ops {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.pc-playlist-rename {
  flex: 1;
}

.pc-playlist-empty {
  padding: 14px;
  text-align: center;
  font-size: 12.5px;
  color: var(--nf-text-muted);
  border: 1px dashed var(--nf-border);
  border-radius: 9px;
}
</style>
