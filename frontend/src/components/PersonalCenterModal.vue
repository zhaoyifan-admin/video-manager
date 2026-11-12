<script setup>
import { ICONS } from '../composables/icons'
import FaIcon from '../ui/FaIcon.vue'
import { computed, ref, watch } from 'vue'
import NfModal from '../ui/NfModal.vue'
import { useAuth } from '../composables/useAuth'
import { changePassword, uploadAvatar, avatarUrl } from '../api'
import { showToast } from '../ui/toast'

const props = defineProps({ modelValue: { type: Boolean, default: false } })
const emit = defineEmits(['update:modelValue', 'logout'])
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

// 每次打开重置图片错误回退态，确保重新打开时重新尝试加载
watch(
  () => props.modelValue,
  (open) => { if (open) avatarError.value = false },
)
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
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.1);
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
</style>
