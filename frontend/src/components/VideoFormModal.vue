<script setup>
import { reactive, ref } from 'vue'
import NfModal from '../ui/NfModal.vue'
import PathPickerModal from './PathPickerModal.vue'
import { listTags, listTypes, createType, createVideo, updateVideo, uploadVideoFile } from '../api'
import { showToast } from '../ui/toast'

const emit = defineEmits(['saved'])

const visible = ref(false)
const submitting = ref(false)
const form = reactive({ id: null, title: '', filePath: '', typeId: null, tags: [], description: '' })
const newTypeNameInline = ref('') // 直接输入新类型，保存时自动创建
const newFormTag = ref('') // 直接输入新标签，回车加入

// 标签 / 类型选项（每次打开时刷新，保证拿到最新数据）
const tags = ref([])
const types = ref([])

const open = async (row = null) => {
  form.id = row?.id ?? null
  form.title = row?.title ?? ''
  form.filePath = row?.filePath ?? ''
  form.typeId = row?.typeId ?? null
  form.tags = row ? [...row.tags] : []
  form.description = row?.description ?? ''
  newTypeNameInline.value = ''
  newFormTag.value = ''
  pendingFile.value = null
  saveDir.value = ''
  visible.value = true
  try {
    const [t, tp] = await Promise.all([listTags(), listTypes()])
    tags.value = t
    types.value = tp
  } catch (e) {
    showToast.error(e.message)
  }
}

defineExpose({ open })

const toggleFormTag = (name) => {
  const i = form.tags.indexOf(name)
  if (i > -1) form.tags.splice(i, 1)
  else form.tags.push(name)
}

const addFormTag = () => {
  const name = newFormTag.value.trim()
  if (!name) return
  if (!form.tags.includes(name)) form.tags.push(name)
  newFormTag.value = ''
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
    // 影视类型：允许直接输入新类型，先创建再取 id
    let typeId = form.typeId
    if (newTypeNameInline.value.trim()) {
      const created = await createType(newTypeNameInline.value.trim())
      typeId = created.id
    }
    const payload = {
      title: form.title.trim(),
      filePath,
      typeId: typeId ?? null,
      tags: form.tags,
      description: form.description.trim(),
    }
    if (form.id) {
      await updateVideo(form.id, payload)
      showToast('已保存')
    } else {
      await createVideo(payload)
      showToast('已新增')
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
          <button class="nf-btn ghost" @click="openPathPicker">选择保存文件夹</button>
        </div>
        <div v-if="pendingFile" class="picked-file">
          <span class="picked-name" :title="pendingFile.name">{{ pendingFile.name }}</span>
          <button class="picked-x" title="放弃该文件" @click="clearPendingFile">✕</button>
        </div>
        <div class="save-dir-box">
          <template v-if="saveDir">
            <span class="save-dir-path" :title="saveDir">📁 {{ saveDir }}</span>
            <button class="save-dir-clear" title="恢复默认保存位置" @click="clearSaveDir">恢复默认</button>
          </template>
          <span v-else class="save-dir-default">📁 默认保存到应用 uploads 目录</span>
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
        placeholder="上传后自动填入，或手动输入本地路径 / 播放链接"
        maxlength="500"
      />
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
          {{ t.name }}
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
          {{ t.name }}
        </button>
        <span v-if="!tags.length" class="no-chip">暂无标签，可在下方输入框添加</span>
      </div>
      <input
        v-model="newFormTag"
        class="nf-input inline-add"
        placeholder="输入新标签后回车添加"
        maxlength="50"
        @keyup.enter="addFormTag"
      />
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
    <template #footer>
      <button class="nf-btn ghost" @click="visible = false">取消</button>
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

.no-chip {
  font-size: 12.5px;
  color: var(--nf-text-muted);
  line-height: 26px;
}
</style>
