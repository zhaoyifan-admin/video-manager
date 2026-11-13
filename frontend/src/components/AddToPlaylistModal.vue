<script setup>
import { ICONS } from '../composables/icons'
import FaIcon from '../ui/FaIcon.vue'
import NfModal from '../ui/NfModal.vue'
import { computed, ref, watch } from 'vue'
import {
  listPlaylists,
  getPlaylistsForVideo,
  createPlaylist,
  addVideoToPlaylist,
  removeVideoFromPlaylist,
} from '../api'
import { showToast } from '../ui/toast'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  videoId: { type: Number, default: 0 },
})
const emit = defineEmits(['update:modelValue', 'changed'])
const close = () => emit('update:modelValue', false)

const loading = ref(false)
// 合并后的片单列表：{ id, name, videoCount, added }
const items = ref([])
const newName = ref('')
const creating = ref(false)

// 打开时拉取「我的片单」与「该视频已加入的片单」，合并勾选态
watch(
  () => props.modelValue,
  async (open) => {
    if (!open || !props.videoId) return
    loading.value = true
    try {
      const [mine, belong] = await Promise.all([
        listPlaylists(),
        getPlaylistsForVideo(props.videoId),
      ])
      const addedMap = new Map((belong.items || []).map((x) => [x.id, x.added]))
      items.value = (mine.items || []).map((p) => ({
        id: p.id,
        name: p.name,
        videoCount: p.videoCount,
        added: !!addedMap.get(p.id),
      }))
    } catch (e) {
      showToast.error(e.message)
    } finally {
      loading.value = false
    }
  },
)

const toggle = async (row) => {
  try {
    if (row.added) {
      await removeVideoFromPlaylist(row.id, props.videoId)
      row.added = false
      row.videoCount = Math.max(0, (row.videoCount || 1) - 1)
      showToast('已移出片单')
    } else {
      await addVideoToPlaylist(row.id, props.videoId)
      row.added = true
      row.videoCount = (row.videoCount || 0) + 1
      showToast('已加入片单')
    }
    emit('changed')
  } catch (e) {
    showToast.error(e.message)
  }
}

const createAndAdd = async () => {
  const name = newName.value.trim()
  if (!name) return showToast.error('请输入片单名称')
  creating.value = true
  try {
    const data = await createPlaylist(name)
    // 新建后顺手把当前视频加进去
    await addVideoToPlaylist(data.id, props.videoId)
    items.value.unshift({ id: data.id, name: data.name, videoCount: 1, added: true })
    newName.value = ''
    showToast('已创建并加入片单')
    emit('changed')
  } catch (e) {
    showToast.error(e.message)
  } finally {
    creating.value = false
  }
}
</script>

<template>
  <NfModal
    :model-value="modelValue"
    title="加入片单"
    width="460px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <!-- 新建片单 -->
    <div class="mb-4 flex items-center gap-2">
      <input
        v-model="newName"
        class="nf-input flex-1"
        placeholder="新建片单名称，回车或点按钮"
        maxlength="50"
        @keyup.enter="createAndAdd"
      />
      <button class="nf-btn red" :disabled="creating" @click="createAndAdd">
        <FaIcon :icon="ICONS.playlistAdd" :fixed="false" />新建并加入
      </button>
    </div>

    <div class="mb-2 text-[12.5px] text-nf-muted">我的片单</div>

    <div v-if="loading" class="flex h-[120px] items-center justify-center">
      <div class="h-7 w-7 animate-spin rounded-full border-[3px] border-white/15 border-t-nf-red"></div>
    </div>

    <div v-else-if="!items.length" class="py-8 text-center text-[13px] text-nf-muted">
      还没有片单，用上方输入框创建第一个吧
    </div>

    <ul v-else class="flex max-h-[320px] flex-col gap-1.5 overflow-y-auto pr-1">
      <li
        v-for="row in items"
        :key="row.id"
        class="flex items-center gap-3 rounded-lg border px-3 py-2.5 transition-colors cursor-pointer"
        :class="row.added ? 'border-nf-red/60 bg-[rgba(229,9,20,0.1)]' : 'border-white/10 bg-nf-elevated hover:border-white/25'"
        @click="toggle(row)"
      >
        <FaIcon
          :icon="ICONS.playlist"
          :fixed="false"
          class="text-[15px]"
          :class="row.added ? 'text-nf-red' : 'text-nf-sub'"
        />
        <span class="min-w-0 flex-1 truncate text-[13.5px] text-nf-text">{{ row.name }}</span>
        <span class="shrink-0 text-[11.5px] tabular-nums text-nf-muted">{{ row.videoCount }} 部</span>
        <span
          class="flex h-[20px] w-[20px] shrink-0 items-center justify-center rounded border"
          :class="row.added ? 'border-nf-red bg-nf-red text-white' : 'border-white/25 text-transparent'"
        >
          <FaIcon :icon="ICONS.check" :fixed="false" class="text-[11px]" />
        </span>
      </li>
    </ul>
  </NfModal>
</template>
