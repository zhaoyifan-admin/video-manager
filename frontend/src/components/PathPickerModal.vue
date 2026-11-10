<script setup>
import { ref, watch } from 'vue'
import NfModal from '../ui/NfModal.vue'
import { listDrives, listDir, makeDir } from '../api'
import { showToast } from '../ui/toast'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  initialDir: { type: String, default: '' }, // 已选过的保存目录，重新打开时直接进入
  initialFileName: { type: String, default: '' }, // 默认保存文件名（取原文件名）
})

const emit = defineEmits(['update:modelValue', 'confirm'])

// 磁盘挂载点列表（含剩余空间）
const drives = ref([])
// 当前浏览的目录；'' 表示处于磁盘根层级
const curDir = ref('')
// 当前目录下的子文件夹
const folders = ref([])
const newFolderName = ref('') // 自定义新建文件夹名
const customFileName = ref('') // 自定义保存文件名（默认取原文件名）

const fmtBytes = (b) => {
  if (b === undefined || b === null) return ''
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let v = b
  let i = 0
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i++
  }
  return `${v >= 10 || i === 0 ? Math.round(v) : v.toFixed(1)} ${units[i]}`
}

const enterDir = async (dir) => {
  try {
    const data = await listDir(dir)
    curDir.value = data.path
    folders.value = data.folders || []
  } catch (e) {
    showToast.error(e.message)
  }
}

// 返回上级：磁盘挂载点的上级回到根层级
const goUpDir = () => {
  if (!curDir.value) return
  if (drives.value.some((d) => d.path === curDir.value)) {
    curDir.value = ''
    folders.value = []
    return
  }
  listDir(curDir.value)
    .then((data) => (data.parent ? enterDir(data.parent) : null))
    .catch((e) => showToast.error(e.message))
}

const createFolder = async () => {
  const name = newFolderName.value.trim()
  if (!name || !curDir.value) return
  try {
    const data = await makeDir(curDir.value, name)
    showToast('文件夹已创建')
    newFolderName.value = ''
    await enterDir(data.path)
  } catch (e) {
    showToast.error(e.message)
  }
}

const confirmSaveDir = () => {
  if (!curDir.value) {
    showToast.warning('请先选择一个磁盘并进入目标文件夹')
    return
  }
  emit('confirm', { dir: curDir.value, fileName: customFileName.value.trim() })
  emit('update:modelValue', false)
}

// 每次打开：拉取磁盘列表，已选过目录则直接进入
watch(
  () => props.modelValue,
  async (visible) => {
    if (!visible) return
    newFolderName.value = ''
    customFileName.value = props.initialFileName
    curDir.value = ''
    folders.value = []
    try {
      drives.value = await listDrives()
      if (props.initialDir) await enterDir(props.initialDir)
    } catch (e) {
      showToast.error(e.message)
    }
  },
)
</script>

<template>
  <NfModal :model-value="modelValue" title="选择保存文件夹" width="520px" @update:model-value="emit('update:modelValue', $event)">
    <!-- 磁盘根层级：外接硬盘 / 内置磁盘挂载点 -->
    <template v-if="!curDir">
      <div class="picker-crumb">请选择磁盘（外接硬盘会出现在这里）</div>
      <div class="drive-list">
        <button
          v-for="d in drives"
          :key="d.path"
          class="drive-item"
          @click="enterDir(d.path)"
        >
          <span class="drive-icon">💽</span>
          <span class="drive-name">{{ d.name }}</span>
          <span class="drive-space">
            {{ d.free !== undefined ? `剩余 ${fmtBytes(d.free)}` : '' }}
          </span>
        </button>
      </div>
    </template>

    <!-- 目录浏览层级 -->
    <template v-else>
      <div class="picker-crumb">
        <button class="crumb-up" title="返回上级" @click="goUpDir">↑ 上级</button>
        <span class="crumb-path" :title="curDir">📁 {{ curDir }}</span>
      </div>
      <div class="folder-list">
        <template v-if="folders.length">
          <button
            v-for="f in folders"
            :key="f"
            class="folder-item"
            @click="enterDir(`${curDir.replace(/\/+$/, '')}/${f}`)"
          >
            <span class="folder-icon">📂</span>
            <span class="folder-name">{{ f }}</span>
          </button>
        </template>
        <span v-else class="no-chip">此目录下没有子文件夹（可以直接保存到当前目录，或新建文件夹）</span>
      </div>

      <!-- 不存在的文件夹：自定义输入名称并创建 -->
      <div class="new-folder-row">
        <input
          v-model="newFolderName"
          class="nf-input"
          placeholder="在当前目录下新建文件夹（输入名称即可创建）"
          maxlength="80"
          @keyup.enter="createFolder"
        />
        <button class="nf-btn ghost" @click="createFolder">＋ 新建</button>
      </div>
    </template>

    <!-- 自定义保存文件名（默认取原文件名） -->
    <div class="new-folder-row">
      <input
        v-model="customFileName"
        class="nf-input"
        :placeholder="initialFileName ? '保存的文件名，默认取原文件名' : '先选择文件后可自定义文件名'"
        :disabled="!initialFileName"
        maxlength="150"
      />
    </div>

    <template #footer>
      <button class="nf-btn ghost" @click="emit('update:modelValue', false)">取消</button>
      <button class="nf-btn red" :disabled="!curDir" @click="confirmSaveDir">保存到此处</button>
    </template>
  </NfModal>
</template>

<style scoped>
/* ===== 保存路径选择器 ===== */
.picker-crumb {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--nf-text-secondary);
}

.crumb-up {
  flex-shrink: 0;
  height: 28px;
  padding: 0 12px;
  border: 1px solid #333338;
  border-radius: 5px;
  background: #1f1f23;
  color: #b3b3b3;
  font-size: 12px;
  cursor: pointer;
}

.crumb-up:hover {
  color: #fff;
  border-color: #5c5c63;
}

.crumb-path {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.drive-list,
.folder-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 240px;
  overflow-y: auto;
  padding-right: 4px;
}

.drive-item,
.folder-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 14px;
  border: 1px solid #333338;
  border-radius: 6px;
  background: #1f1f23;
  color: #e5e5e5;
  font-size: 13.5px;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.drive-item:hover,
.folder-item:hover {
  border-color: rgba(229, 9, 20, 0.55);
  background: #232328;
}

.drive-icon,
.folder-icon {
  flex-shrink: 0;
}

.drive-name,
.folder-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.drive-space {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--nf-text-muted);
  font-variant-numeric: tabular-nums;
}

/* 新建文件夹 / 自定义文件名行 */
.new-folder-row {
  display: flex;
  gap: 8px;
  margin-top: 14px;
}

.no-chip {
  font-size: 12.5px;
  color: var(--nf-text-muted);
  line-height: 26px;
}
</style>
