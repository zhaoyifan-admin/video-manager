<script setup>
import { ref } from 'vue'
import NfModal from '../ui/NfModal.vue'
import { listTags, createTag, deleteTag, listTypes, createType, deleteType } from '../api'
import { showToast } from '../ui/toast'
import { confirmAction } from '../ui/confirm'

const emit = defineEmits(['changed'])

const visible = ref(false)
const newTagName = ref('')
const newTypeName = ref('')

const tags = ref([])
const types = ref([])

const open = async () => {
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

const addTag = async () => {
  const name = newTagName.value.trim()
  if (!name) return
  try {
    await createTag(name)
    newTagName.value = ''
    tags.value = await listTags()
    showToast('标签已添加')
    emit('changed')
  } catch (e) {
    showToast.error(e.message)
  }
}

const removeTag = async (tag) => {
  const ok = await confirmAction({
    title: '删除标签',
    message: `确认删除标签「${tag.name}」？已挂接该标签的视频会同步解除关联。`,
  })
  if (!ok) return
  try {
    await deleteTag(tag.id)
    tags.value = await listTags()
    showToast('标签已删除')
    emit('changed')
  } catch (e) {
    showToast.error(e.message)
  }
}

const addType = async () => {
  const name = newTypeName.value.trim()
  if (!name) return
  try {
    await createType(name)
    newTypeName.value = ''
    types.value = await listTypes()
    showToast('类型已添加')
    emit('changed')
  } catch (e) {
    showToast.error(e.message)
  }
}

const removeType = async (item) => {
  const ok = await confirmAction({
    title: '删除类型',
    message: `确认删除类型「${item.name}」？使用该类型的视频会变为未分类。`,
  })
  if (!ok) return
  try {
    await deleteType(item.id)
    types.value = await listTypes()
    showToast('类型已删除')
    emit('changed')
  } catch (e) {
    showToast.error(e.message)
  }
}
</script>

<template>
  <NfModal v-model="visible" title="标签 / 类型管理" width="640px">
    <div class="manage-cols">
      <div class="manage-col">
        <h3>标签（可多选）</h3>
        <div class="tag-add">
          <input
            v-model="newTagName"
            class="nf-input"
            placeholder="输入新标签名"
            maxlength="50"
            @keyup.enter="addTag"
          />
          <button class="nf-btn red" @click="addTag">添加</button>
        </div>
        <div class="tag-list">
          <template v-if="tags.length">
            <span v-for="t in tags" :key="t.id" class="manage-tag">
              {{ t.name }}
              <button class="tag-x" title="删除" @click="removeTag(t)">✕</button>
            </span>
          </template>
          <span v-else class="no-chip">暂无标签</span>
        </div>
      </div>
      <div class="manage-col">
        <h3>影视类型（单选）</h3>
        <div class="tag-add">
          <input
            v-model="newTypeName"
            class="nf-input"
            placeholder="输入新类型名"
            maxlength="50"
            @keyup.enter="addType"
          />
          <button class="nf-btn red" @click="addType">添加</button>
        </div>
        <div class="tag-list">
          <template v-if="types.length">
            <span v-for="t in types" :key="t.id" class="manage-tag type">
              {{ t.name }}
              <button class="tag-x" title="删除" @click="removeType(t)">✕</button>
            </span>
          </template>
          <span v-else class="no-chip">暂无类型</span>
        </div>
      </div>
    </div>
  </NfModal>
</template>

<style scoped>
/* 标签 / 类型管理双栏 */
.manage-cols {
  display: flex;
  gap: 24px;
}

.manage-col {
  flex: 1;
  min-width: 0;
}

.manage-col h3 {
  font-size: 14px;
  margin: 0 0 12px;
  color: var(--nf-text-secondary);
}

.tag-add {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-height: 40px;
}

.manage-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px 4px 13px;
  border-radius: 16px;
  background: #1f1f23;
  border: 1px solid #333338;
  color: #e5e5e5;
  font-size: 12.5px;
  line-height: 18px;
}

.manage-tag.type {
  border-color: rgba(229, 9, 20, 0.4);
}

.tag-x {
  width: 18px;
  height: 18px;
  border: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.1);
  color: #9a9aa2;
  font-size: 10px;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.15s ease;
}

.tag-x:hover {
  background: var(--nf-red);
  color: #fff;
}

.no-chip {
  font-size: 12.5px;
  color: var(--nf-text-muted);
  line-height: 26px;
}
</style>
