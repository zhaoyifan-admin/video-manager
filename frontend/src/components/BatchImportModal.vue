<script setup>
import { computed, ref } from 'vue'
import NfModal from '../ui/NfModal.vue'
import { batchImportVideos } from '../api'
import { useAuth } from '../composables/useAuth'
import { showToast } from '../ui/toast'

const emit = defineEmits(['imported'])

const { user } = useAuth()
const isSuperAdmin = computed(() => user.value?.role === 'admin')

const visible = ref(false)
const batchText = ref('')
const batchImporting = ref(false)

const open = () => {
  visible.value = true
}

defineExpose({ open })

// 解析批量文本：每行一条，字段用 | 分隔（标题 | 路径 | 标签 | 类型 | 备注）
const parseBatchLines = () => {
  const items = []
  const errors = []
  batchText.value.split('\n').forEach((line, i) => {
    const trimmed = line.trim()
    if (!trimmed) return
    const parts = trimmed.split('|').map((p) => p.trim())
    // 只有一列时视为纯文件路径，标题由后端从文件名生成
    const filePath = parts.length > 1 ? parts[1] : parts[0]
    const title = parts.length > 1 ? parts[0] : ''
    if (!filePath) {
      errors.push(`第 ${i + 1} 行缺少文件路径`)
      return
    }
    const item = { filePath, title }
    if (parts[2]) {
      const tagStr = parts[2].split(/[,，、\s]+/).filter(Boolean)
      if (tagStr.length) item.tags = tagStr
    }
    if (parts[3]) item.typeName = parts[3]
    if (parts[4]) item.description = parts[4]
    items.push(item)
  })
  return { items, errors }
}

const doBatchImport = async () => {
  const { items, errors } = parseBatchLines()
  if (errors.length) {
    showToast.error(errors[0])
    return
  }
  if (!items.length) {
    showToast.warning('请先粘贴要导入的内容，每行一条视频')
    return
  }
  batchImporting.value = true
  try {
    const data = await batchImportVideos(items)
    const failCount = data.failed.length
    if (failCount) {
      showToast.warning(
        `成功 ${data.success} 条，失败 ${failCount} 条：` +
          data.failed.map((f) => `第${f.index + 1}行 ${f.msg}`).join('；'),
      )
    } else {
      showToast(
        isSuperAdmin.value
          ? `成功导入 ${data.success} 条视频（管理员入库自动通过审核）`
          : `成功导入 ${data.success} 条视频，待管理员审核通过后才会在影库展示；可在「审核结果」查看进度`,
      )
    }
    visible.value = false
    batchText.value = ''
    emit('imported')
  } catch (e) {
    showToast.error(e.message)
  } finally {
    batchImporting.value = false
  }
}
</script>

<template>
  <NfModal v-model="visible" title="批量导入影片" width="680px">
    <div class="batch-hint">
      每行一条视频，字段用竖线 <code>|</code> 分隔：<br />
      <code>标题 | 文件路径或播放链接 | 标签1,标签2 | 类型 | 备注</code><br />
      仅「文件路径」为必填，其余字段可省略；只有一列时视为纯文件路径，标题自动取文件名。
    </div>
    <textarea
      v-model="batchText"
      class="nf-textarea batch-text"
      rows="10"
      placeholder="示例：
星球崛起 | /Users/me/Movies/星球崛起.mp4 | 科幻,4K | 电影 | 部分镜头精彩
纪录片地球 | uploads/纪录片地球.mkv | 自然 | 纪录片
https://example.com/watch?v=123 | 在线课程 | 前端 | 教程 | 共12集"
    ></textarea>
    <template #footer>
      <button class="nf-btn ghost" @click="visible = false">取消</button>
      <button class="nf-btn red" :disabled="batchImporting" @click="doBatchImport">
        {{ batchImporting ? '导入中…' : '开始导入' }}
      </button>
    </template>
  </NfModal>
</template>

<style scoped>
.batch-hint {
  font-size: 13px;
  line-height: 1.8;
  color: var(--nf-text-secondary);
  background: var(--nf-bg-elevated);
  border: 1px solid var(--nf-border);
  border-radius: 6px;
  padding: 10px 14px;
  margin-bottom: 12px;
}

.batch-hint code {
  background: #2a2a30;
  color: #e5e5e5;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 12px;
}

.batch-text {
  min-height: 220px;
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  font-size: 12.5px;
}
</style>
