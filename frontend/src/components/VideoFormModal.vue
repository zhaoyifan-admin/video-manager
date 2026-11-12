<script setup>
import { ICONS } from '../composables/icons'
import FaIcon from '../ui/FaIcon.vue'
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import NfModal from '../ui/NfModal.vue'
import PathPickerModal from './PathPickerModal.vue'
import {
  listTags, listTypes, listCollections, createType,
  createVideo, updateVideo, uploadVideoFile,
} from '../api'
import { useAuth } from '../composables/useAuth'
import { showToast } from '../ui/toast'

const emit = defineEmits(['saved'])
const router = useRouter()

const { user } = useAuth()
const isSuperAdmin = computed(() => user.value?.role === 'admin')

const visible = ref(false)
const submitting = ref(false)
const form = reactive({
  id: null, title: '', filePath: '', subtitlePath: '', collectionId: null,
  typeId: null, tags: [], description: '',
  isPublic: false, auditStatus: 0, auditReason: '',
})
const collections = ref([])
const originalPath = ref('')
const originalSubtitle = ref('')
const newTypeNameInline = ref('') // 直接输入新类型，保存时自动创建
// 标签改为管理员统一管理发布：表单里只从已发布标签中挑选，不再内联新建

// 标签 / 类型选项（每次打开时刷新，保证拿到最新数据）
const tags = ref([])
const types = ref([])

const open = async (row = null) => {
  form.id = row?.id ?? null
  form.title = row?.title ?? ''
  form.filePath = row?.filePath ?? ''
  form.subtitlePath = row?.subtitlePath ?? ''
  form.collectionId = row?.collectionId ?? null
  form.typeId = row?.typeId ?? null
  form.tags = row ? [...row.tags] : []
  form.description = row?.description ?? ''
  form.isPublic = row?.isPublic ?? false
  form.auditStatus = row?.auditStatus ?? 0
  form.auditReason = row?.auditReason ?? ''
  originalPath.value = form.filePath
  originalSubtitle.value = form.subtitlePath
  newTypeNameInline.value = ''
  pendingFile.value = null
  saveDir.value = ''
  visible.value = true
  try {
    const [t, tp, cs] = await Promise.all([listTags(), listTypes(), listCollections()])
    tags.value = t
    types.value = tp
    collections.value = cs.items
  } catch (e) {
    showToast.error(e.message)
  }
}

defineExpose({ open })

// 公开展示：仅「已通过审核」的视频可设置；未过审时置灰并说明原因
const canSetPublic = computed(() => !!form.id && form.auditStatus === 1)
const isRejected = computed(() => !!form.id && form.auditStatus === 2)
// 换了源文件或字幕 = 换了内容，保存后必须重新审核并收回公开（防绕过）
const contentChanged = computed(() => !!form.id && (
  form.filePath.trim() !== originalPath.value ||
  form.subtitlePath.trim() !== originalSubtitle.value
))

const publicHint = computed(() => {
  if (!form.id) return '新上传的视频需先通过管理员审核，通过后才能在此设置公开'
  if (form.auditStatus === 0) return '等待管理员审核中，通过后才能设为公开'
  if (form.auditStatus === 2) return '保存后会重新提交审核，审核期间不可公开'
  return '勾选后所有用户可观看；取消则仅自己可见'
})

const toggleFormTag = (name) => {
  const i = form.tags.indexOf(name)
  if (i > -1) form.tags.splice(i, 1)
  else form.tags.push(name)
}

// 隐藏的文件输入框：选择后暂存，点「保存」时才上传到指定保存目录
const fileInput = ref(null)
const pendingFile = ref(null) // 待上传的原始 File 对象
const saveDir = ref('') // 自定义保存目录（绝对路径），空 = 默认 uploads 目录
const customFileName = ref('') // 自定义保存文件名（选择器里设置）
const pickFile = () => fileInput.value?.click()

const onPickFile = (e) => {
  const raw = e.target.files?.[0]
  e.target.value = '' // 允许重复选择同一文件
  if (!raw) return
  pendingFile.value = raw
  // 标题始终取原始文件名赋值（含扩展名）
  form.title = raw.name
}

const clearPendingFile = () => {
  pendingFile.value = null
}

// ================= 保存路径选择器（浏览外接硬盘 / 新建文件夹） =================
const pathVisible = ref(false)

const openPathPicker = () => {
  pathVisible.value = true
}

const onPathConfirm = ({ dir, fileName }) => {
  saveDir.value = dir
  if (fileName) customFileName.value = fileName
}

const clearSaveDir = () => {
  saveDir.value = ''
}

const submitForm = async () => {
  if (!form.title.trim()) {
    showToast.warning('请输入视频标题')
    return
  }
  submitting.value = true
  try {
    // 选择新文件时：先上传到指定保存目录（无则默认 uploads），再入库
    let filePath = form.filePath.trim()
    if (pendingFile.value) {
      const data = await uploadVideoFile(
        pendingFile.value,
        saveDir.value,
        customFileName.value.trim() || undefined,
      )
      filePath = data.filePath
      showToast('视频文件已保存到目标文件夹')
    }
    // 影视类型：允许直接输入新类型，先创建再取 id（管理员直接发布，普通用户进待审核）
    let typeId = form.typeId
    if (newTypeNameInline.value.trim()) {
      const created = await createType(newTypeNameInline.value.trim(), isSuperAdmin.value)
      typeId = created.id
    }
    const payload = {
      title: form.title.trim(),
      filePath,
      subtitlePath: form.subtitlePath.trim(),
      collectionId: form.collectionId ?? null,
      typeId: typeId ?? null,
      tags: form.tags,
      description: form.description.trim(),
      isPublic: canSetPublic.value && form.isPublic,
    }
    if (form.id) {
      const data = await updateVideo(form.id, payload)
      showToast(data?.resubmitted ? '已修改并重新提交审核，等待管理员复核' : '已保存')
    } else {
      await createVideo(payload)
      if (isSuperAdmin.value) {
        showToast('已新增')
      } else {
        showToast.withAction(
          '已提交审核，可在「审核结果」查看进度',
          '查看我的提交',
          () => router.push({ name: 'mySubmissions' }),
        )
      }
    }
    visible.value = false
    emit('saved', { isEdit: !!form.id })
  } catch (e) {
    showToast.error(e.message)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <NfModal v-model="visible" :title="form.id ? '编辑影片' : '新增影片'" width="560px">
    <!-- 被驳回的视频：打开编辑时先告知理由，说明保存即重新送审 -->
    <div v-if="isRejected" class="form-reject-note">
      <strong>审核未通过</strong>
      <span>{{ form.auditReason || '管理员未填写理由' }}</span>
      <span class="form-reject-tip">请按要求修改（可重新选择文件上传），保存后将自动重新提交审核。</span>
    </div>
    <div v-if="contentChanged" class="form-resubmit-note">
      更换了视频文件或字幕，保存后该片会<b>重新进入待审核</b>并自动收回公开状态，需管理员复核通过后才能再次公开。
    </div>
    <div class="nf-field">
      <label class="nf-label">标题</label>
      <input v-model="form.title" class="nf-input" placeholder="视频标题" maxlength="200" />
    </div>
    <div class="nf-field">
      <label class="nf-label">视频文件</label>
      <input ref="fileInput" type="file" accept="video/*" hidden @change="onPickFile" />
      <div class="upload-row">
        <div class="upload-btns">
          <button class="nf-btn ghost" @click="pickFile">
            {{ pendingFile ? '重新选择文件' : '选择文件' }}
          </button>
          <button class="nf-btn ghost" @click="openPathPicker"><FaIcon :icon="ICONS.folderOpen" :fixed="false" />选择保存文件夹</button>
        </div>
        <div v-if="pendingFile" class="picked-file">
          <span class="picked-name" :title="pendingFile.name">{{ pendingFile.name }}</span>
          <button class="picked-x" title="放弃该文件" @click="clearPendingFile"><FaIcon :icon="ICONS.close" :fixed="false" /></button>
        </div>
        <div class="save-dir-box">
          <template v-if="saveDir">
            <span class="save-dir-path" :title="saveDir"><FaIcon :icon="ICONS.folderOpen" :fixed="false" /> {{ saveDir }}</span>
            <button class="save-dir-clear" title="恢复默认保存位置" @click="clearSaveDir"><FaIcon :icon="ICONS.reset" :fixed="false" />恢复默认</button>
          </template>
          <span v-else class="save-dir-default"><FaIcon :icon="ICONS.folderOpen" :fixed="false" /> 默认保存到应用 uploads 目录</span>
        </div>
        <span class="upload-hint">
          点「保存」时才会把文件写入所选文件夹；文件夹不存在可在选择器里新建；标题自动取原始文件名
        </span>
      </div>
    </div>
    <div class="nf-field">
      <label class="nf-label">文件路径</label>
      <input
        v-model="form.filePath"
        class="nf-input"
        placeholder="上传后自动填入，或手动输入已登记媒体目录下的视频绝对路径"
        maxlength="500"
      />
      <span class="upload-hint">路径需位于允许的媒体目录内（uploads / 外接硬盘 / 常用媒体目录，或 config.py 的 MEDIA_ROOTS）</span>
    </div>
    <div class="nf-field">
      <label class="nf-label">字幕文件（可选，.vtt / .srt）</label>
      <input
        v-model="form.subtitlePath"
        class="nf-input"
        placeholder="字幕文件的绝对路径，留空表示不使用字幕"
        maxlength="500"
      />
    </div>
    <div class="nf-field">
      <label class="nf-label">所属合集（可选）</label>
      <select v-model="form.collectionId" class="nf-input">
        <option :value="null">不加入合集</option>
        <option v-for="c in collections" :key="c.id" :value="c.id">{{ c.name }}</option>
      </select>
    </div>
    <div class="nf-field">
      <label class="nf-label">影视类型（单选）</label>
      <div class="chip-select">
        <button class="chip-opt" :class="{ on: form.typeId === null }" @click="form.typeId = null">
          未分类
        </button>
        <button
          v-for="t in types"
          :key="t.id"
          class="chip-opt"
          :class="{ on: form.typeId === t.id }"
          @click="form.typeId = t.id"
        >
          {{ t.name }}<span v-if="t.isPublished === false" class="chip-unpub">未发布</span>
        </button>
      </div>
      <input
        v-model="newTypeNameInline"
        class="nf-input inline-add"
        placeholder="或输入新类型名，保存时自动创建"
        maxlength="50"
      />
    </div>
    <div class="nf-field">
      <label class="nf-label">标签（可多选）</label>
      <div class="chip-select">
        <button
          v-for="t in tags"
          :key="t.id"
          class="chip-opt"
          :class="{ on: form.tags.includes(t.name) }"
          @click="toggleFormTag(t.name)"
        >
          {{ t.name }}<span v-if="t.isPublished === false" class="chip-unpub">未发布</span>
        </button>
        <span v-if="!tags.length" class="no-chip">暂无可选标签，可在「标签 / 类型管理」中提交新标签，审核通过后即可选用</span>
      </div>
      <span class="upload-hint">标签由系统统一管理：可直接选用已发布的标签；需要新标签请在「标签 / 类型管理」中提交，管理员审核通过后方可选用</span>
    </div>
    <div class="nf-field">
      <label class="nf-label">备注</label>
      <textarea
        v-model="form.description"
        class="nf-textarea"
        rows="3"
        maxlength="1000"
        placeholder="剧情简介、备注信息…"
      ></textarea>
    </div>
    <div class="nf-field">
      <label class="nf-label">公开展示</label>
      <label class="public-toggle" :class="{ disabled: !canSetPublic }">
        <input v-model="form.isPublic" type="checkbox" :disabled="!canSetPublic" />
        <span>允许所有用户观看</span>
      </label>
      <div class="public-hint">{{ publicHint }}</div>
    </div>
    <template #footer>
      <button class="nf-btn ghost" @click="visible = false"><FaIcon :icon="ICONS.close" :fixed="false" />取消</button>
      <button class="nf-btn red" :disabled="submitting" @click="submitForm">
        {{ submitting ? '保存中…' : '保存' }}
      </button>
    </template>
  </NfModal>

  <PathPickerModal
    v-model="pathVisible"
    :initial-dir="saveDir"
    :initial-file-name="pendingFile?.name || ''"
    @confirm="onPathConfirm"
  />
</template>

<style scoped>
/* 驳回理由提示 */
.form-reject-note {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin-bottom: 16px;
  padding: 10px 12px;
  border-left: 3px solid #ff525b;
  border-radius: 4px;
  background: rgba(112, 14, 20, 0.28);
  font-size: 12.5px;
  line-height: 1.6;
  color: #ffd0d2;
  word-break: break-all;
}

.form-reject-note strong {
  font-size: 13px;
}

.form-reject-tip {
  color: #ffb3b8;
}

.form-resubmit-note {
  margin-bottom: 16px;
  padding: 10px 12px;
  border-left: 3px solid #e6a01e;
  border-radius: 4px;
  background: rgba(120, 80, 10, 0.25);
  font-size: 12.5px;
  line-height: 1.7;
  color: #f0d9a8;
}

.form-resubmit-note b {
  color: #ffd479;
}

/* 公开展示勾选 */
.public-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13.5px;
  color: #f5f5f5;
  cursor: pointer;
  user-select: none;
}

.public-toggle.disabled {
  color: var(--nf-text-muted);
  cursor: not-allowed;
}

.public-toggle input {
  width: 16px;
  height: 16px;
  margin: 0;
  accent-color: var(--nf-red);
  cursor: inherit;
}

.public-hint {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--nf-text-muted);
}

/* ===== 上传区 ===== */
.upload-row {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.upload-btns {
  display: flex;
  gap: 8px;
}

.upload-hint {
  font-size: 12px;
  color: var(--nf-text-muted);
  line-height: 1.5;
}

/* 已选择但未上传的文件条 */
.picked-file {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: #1f1f23;
  border: 1px solid #333338;
  border-radius: 5px;
  font-size: 12.5px;
  color: #e5e5e5;
}

.picked-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.picked-x {
  flex-shrink: 0;
  width: 18px;
  height: 18px;
  border: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.1);
  color: #9a9aa2;
  font-size: 10px;
  cursor: pointer;
}

.picked-x:hover {
  background: var(--nf-red);
  color: #fff;
}

/* 保存路径显示条 */
.save-dir-box {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 12px;
  background: rgba(229, 9, 20, 0.07);
  border: 1px dashed rgba(229, 9, 20, 0.4);
  border-radius: 5px;
  font-size: 12.5px;
}

.save-dir-path {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #f0c2c5;
}

.save-dir-default {
  color: var(--nf-text-muted);
}

.save-dir-clear {
  flex-shrink: 0;
  border: none;
  background: transparent;
  color: var(--nf-text-secondary);
  font-size: 12px;
  cursor: pointer;
  text-decoration: underline;
}

.save-dir-clear:hover {
  color: #fff;
}

.inline-add {
  margin-top: 9px;
  height: 32px;
  font-size: 12.5px;
}

/* 管理员视角下未发布标签的角标 */
.chip-unpub {
  margin-left: 5px;
  padding: 1px 5px;
  border-radius: 3px;
  background: rgba(230, 160, 30, 0.2);
  color: #e6a01e;
  font-size: 10px;
  font-weight: 600;
}

.no-chip {
  font-size: 12.5px;
  color: var(--nf-text-muted);
  line-height: 26px;
}
</style>
