<script setup>
import { ICONS } from '../composables/icons'
import FaIcon from '../ui/FaIcon.vue'
import { useCover } from '../composables/useCover'

defineProps({
  video: { type: Object, required: true },
  // 编辑/删除/公开设置权限：本人视频或超级管理员
  manageable: { type: Boolean, default: false },
  // 非本人视频（公开共享）时显示归属者
  showOwner: { type: Boolean, default: false },
  // 是否显示「审核记录」入口（我的提交页开启）
  showAuditLog: { type: Boolean, default: false },
  // 列表页批量管理模式：显示复选框，点击卡片变为选中而非播放
  selectable: { type: Boolean, default: false },
  selected: { type: Boolean, default: false },
})

defineEmits(['play', 'edit', 'remove', 'toggle-fav', 'toggle-public', 'audit-log', 'select', 'add-playlist'])

const { coverCache, durationCache, onMetaLoaded, mediaSrc } = useCover()
</script>

<template>
  <div
    v-lazy-cover="video"
    class="video-card-inner"
    :class="[`cover-tone-${video.id % 6}`, { 'is-selected': selectable && selected }]"
    @click="selectable ? $emit('select', video) : $emit('play', video)"
  >
    <!-- 批量管理模式：右上角复选框 -->
    <label v-if="selectable" class="card-check" @click.stop>
      <input type="checkbox" :checked="selected" @change="$emit('select', video)" />
    </label>
    <!-- 视频背景卡片：视频铺满整卡，内容叠加展示 -->
    <video
      v-if="video.filePath"
      class="card-video"
      :class="{ 'nf-media-ready': !!coverCache[video.id] }"
      :src="mediaSrc(video)"
      :poster="coverCache[video.id] || undefined"
      muted
      loop
      playsinline
      preload="metadata"
      @loadedmetadata="onMetaLoaded(video, $event)"
    ></video>
    <div class="card-scrim"></div>

    <!-- 左上角徽章组：类型 / 公开 / 审核状态 -->
    <div class="cover-badges">
      <span v-if="video.typeName" class="cover-type">{{ video.typeName }}</span>
      <span
        v-if="video.ratingCount"
        class="inline-flex items-center gap-1 rounded bg-black/60 px-1.5 py-[2px] text-[10.5px] font-semibold tabular-nums text-nf-amber"
        :title="`${video.ratingCount} 人评分`"
      >
        <FaIcon :icon="ICONS.star" :fixed="false" class="text-[10px]" />{{ Number(video.avgScore).toFixed(1) }}
      </span>
      <span
        v-if="video.isWantToWatch"
        class="inline-flex items-center rounded bg-black/60 px-1.5 py-[2px] text-[10.5px] text-nf-red"
        title="已加入想看清单"
      >
        <FaIcon :icon="ICONS.wantlist" :fixed="false" class="text-[10px]" />
      </span>
      <span v-if="video.isPublic" class="cover-public" title="公开视频，所有用户可观看">公开</span>
      <span v-if="video.auditStatus === 0" class="cover-audit pending" title="等待管理员审核">待审核</span>
      <span v-else-if="video.auditStatus === 2" class="cover-audit rejected" title="管理员已驳回，仅自己可见">已驳回</span>
    </div>

    <!-- 驳回红条：常显告知上传用户未通过及理由（hover 时让位给详情浮层） -->
    <div v-if="video.auditStatus === 2" class="reject-banner">
      <span class="reject-banner-label">审核未通过</span>
      <span class="reject-banner-reason">{{ video.auditReason || '管理员未填写理由' }}</span>
      <span class="reject-banner-tip">修改后保存即可重新提交审核</span>
    </div>
    <button
      class="cover-fav"
      :class="{ active: video.isFavorite }"
      :title="video.isFavorite ? '取消收藏' : '收藏'"
      @click.stop="$emit('toggle-fav', video)"
    >
      <FaIcon :icon="ICONS.fav" :variant="video.isFavorite ? 'solid' : 'regular'" :fixed="false" class="text-[16px]" />
    </button>

    <!-- 默认态：底部信息条（标题 + 时长 / 标签） -->
    <div class="card-bar">
      <div class="bar-title-row">
        <span class="bar-title" :title="video.title">{{ video.title }}</span>
        <span v-if="durationCache[video.id]" class="bar-duration">
          {{ durationCache[video.id] }}
        </span>
      </div>
      <div class="bar-tags">
        <span v-if="showOwner" class="chip owner" :title="`来自 ${video.ownerName}`">
          来自 {{ video.ownerName }}
        </span>
        <template v-if="video.tags.length">
          <span v-for="name in video.tags" :key="name" class="chip">{{ name }}</span>
        </template>
        <span v-else class="bar-muted">无标签</span>
      </div>
    </div>

    <!-- 悬停态：详情浮层 -->
    <div class="card-detail">
      <div class="detail-title" :title="video.title">{{ video.title }}</div>
      <div v-if="video.auditStatus === 2" class="detail-reason">
        <span class="detail-label">未通过理由</span>
        <span class="detail-reason-text">{{ video.auditReason || '管理员未填写理由' }}</span>
        <span class="detail-reason-tip">修改并保存后会重新提交审核</span>
      </div>
      <div v-if="video.typeName" class="detail-row">
        <span class="detail-label">类型</span>
        <span class="detail-value">{{ video.typeName }}</span>
      </div>
      <div v-if="durationCache[video.id]" class="detail-row">
        <span class="detail-label">时长</span>
        <span class="detail-value">{{ durationCache[video.id] }}</span>
      </div>
      <div v-if="video.filePath" class="detail-row">
        <span class="detail-label">路径</span>
        <span class="detail-value" :title="video.filePath">{{ video.filePath }}</span>
      </div>
      <div v-if="showOwner" class="detail-row">
        <span class="detail-label">归属</span>
        <span class="detail-value">{{ video.ownerName }}</span>
      </div>
      <div v-if="video.description" class="detail-row">
        <span class="detail-label">备注</span>
        <span class="detail-value desc" :title="video.description">{{ video.description }}</span>
      </div>
      <div class="detail-row">
        <span class="detail-label">标签</span>
        <span class="detail-value">
          <template v-if="video.tags.length">
            <span v-for="name in video.tags" :key="name" class="chip">{{ name }}</span>
          </template>
          <template v-else>无标签</template>
        </span>
      </div>
      <!-- 播放大按钮 -->
      <div class="detail-play">
        <button class="play-big" title="播放" @click.stop="$emit('play', video)">
          <FaIcon :icon="ICONS.play" :fixed="false" class="text-[26px]" />
        </button>
      </div>
      <div class="detail-footer">
        <span class="bar-muted">{{ video.updatedAt }}</span>
        <div class="detail-ops">
          <button class="nf-btn sm ghost" @click.stop="$emit('add-playlist', video)"><FaIcon :icon="ICONS.playlist" :fixed="false" />片单</button>
          <button v-if="showAuditLog" class="nf-btn sm ghost" @click.stop="$emit('audit-log', video)"><FaIcon :icon="ICONS.auditLog" :fixed="false" />审核记录</button>
          <button v-if="manageable" class="nf-btn sm ghost" @click.stop="$emit('toggle-public', video)">
            {{ video.isPublic ? '设为私有' : '设为公开' }}
          </button>
          <button v-if="manageable" class="nf-btn sm ghost" @click.stop="$emit('edit', video)"><FaIcon :icon="ICONS.edit" :fixed="false" />编辑</button>
          <button v-if="manageable" class="nf-btn sm ghost danger" @click.stop="$emit('remove', video)"><FaIcon :icon="ICONS.remove" :fixed="false" />删除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ===== 驳回红条 / 详情浮层中的理由 ===== */
.reject-banner {
  position: absolute;
  top: 42px;
  left: 10px;
  right: 10px;
  z-index: 4;
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 8px 10px;
  border-left: 3px solid #ff525b;
  border-radius: 4px;
  background: rgba(112, 14, 20, 0.92);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.45);
  color: #fff;
  transition: opacity 0.2s ease;
}

.video-card-inner:hover .reject-banner {
  opacity: 0;
  pointer-events: none;
}

.reject-banner-label {
  font-size: 11.5px;
  font-weight: 700;
  letter-spacing: 0.5px;
  color: #ffd0d2;
}

.reject-banner-reason {
  font-size: 12px;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-all;
}

.reject-banner-tip,
.detail-reason-tip {
  font-size: 11px;
  color: #ffb3b8;
}

.detail-reason {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 10px;
  padding: 8px 10px;
  border-left: 3px solid #ff525b;
  border-radius: 4px;
  background: rgba(112, 14, 20, 0.35);
}

.detail-reason .detail-label {
  font-size: 11.5px;
  font-weight: 700;
  color: #ffd0d2;
}

.detail-reason-text {
  font-size: 12px;
  line-height: 1.6;
  color: #fff;
  word-break: break-all;
}

/* 批量选择 */
.card-check {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 5;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 5px;
  background: rgba(0, 0, 0, 0.72);
  cursor: pointer;
}

.card-check input {
  width: 16px;
  height: 16px;
  margin: 0;
  accent-color: var(--nf-red);
  cursor: pointer;
}

.video-card-inner.is-selected {
  outline: 2px solid var(--nf-red);
  outline-offset: -2px;
}

/* ===== 视频背景卡片 ===== */
.video-card-inner {
  position: relative;
  height: 420px;
  display: flex;
  cursor: pointer;
  overflow: hidden;
  border-radius: 8px;
  border: 1px solid var(--nf-border);
  transition:
    transform 0.25s ease,
    box-shadow 0.25s ease,
    border-color 0.25s ease;
}

.video-card-inner:hover {
  transform: scale(1.035);
  border-color: rgba(229, 9, 20, 0.55);
  box-shadow:
    0 14px 40px rgba(0, 0, 0, 0.7),
    0 0 0 1px rgba(229, 9, 20, 0.25);
  z-index: 5;
}

/* 窄屏两列布局：降低卡片高度，避免竖长卡片占满整屏 */
@media (max-width: 600px) {
  .video-card-inner { height: 300px; }
}

.card-video {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  background: rgba(0, 0, 0, 0.3);
}

.card-scrim {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    180deg,
    rgba(0, 0, 0, 0.35) 0%,
    rgba(0, 0, 0, 0) 38%,
    rgba(0, 0, 0, 0.2) 62%,
    rgba(0, 0, 0, 0.8) 100%
  );
}

/* ===== 默认态：底部信息条 ===== */
.card-bar {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 2;
  padding: 10px 14px 12px;
  background: rgba(0, 0, 0, 0.72);
  backdrop-filter: blur(6px);
  color: #fff;
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.video-card-inner:hover .card-bar {
  opacity: 0;
  transform: translateY(100%);
}

.bar-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.bar-title {
  flex: 1;
  min-width: 0;
  font-size: 15px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bar-duration {
  flex-shrink: 0;
  padding: 1px 8px;
  border-radius: 9px;
  background: rgba(0, 0, 0, 0.55);
  font-size: 12px;
  line-height: 18px;
  font-variant-numeric: tabular-nums;
  color: var(--nf-text-primary);
}

.bar-tags {
  display: flex;
  align-items: center;
  gap: 6px;
  overflow: hidden;
  white-space: nowrap;
}

.bar-tags .chip,
.detail-value .chip {
  flex-shrink: 0;
  display: inline-block;
  padding: 1px 9px;
  border-radius: 10px;
  background: var(--nf-overlay);
  border: 1px solid var(--nf-overlay);
  font-size: 12px;
  line-height: 18px;
  color: var(--nf-text-primary);
}

.bar-muted {
  font-size: 12px;
  color: var(--nf-text-primary);
}

/* ===== 悬停态：详情浮层 ===== */
.card-detail {
  position: absolute;
  inset: 0;
  z-index: 3;
  display: flex;
  flex-direction: column;
  padding: 16px;
  color: #fff;
  background: rgba(10, 10, 12, 0.9);
  backdrop-filter: blur(10px);
  opacity: 0;
  transform: translateY(16px);
  pointer-events: none;
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.video-card-inner:hover .card-detail {
  opacity: 1;
  transform: none;
  pointer-events: auto;
}

.detail-title {
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 10px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-row {
  display: flex;
  gap: 8px;
  font-size: 12px;
  line-height: 20px;
  margin-bottom: 6px;
  min-width: 0;
}

.detail-label {
  color: var(--nf-text-primary);
  flex-shrink: 0;
}

.detail-value {
  color: var(--nf-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.detail-value.desc {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  white-space: normal;
}

.detail-play {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.play-big {
  width: 58px;
  height: 58px;
  border-radius: 50%;
  border: none;
  background: var(--nf-red);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow:
    0 6px 24px rgba(229, 9, 20, 0.45),
    0 2px 8px rgba(0, 0, 0, 0.4);
  transition: transform 0.2s ease, filter 0.2s ease;
}

.play-big:hover {
  transform: scale(1.12);
  filter: brightness(1.15);
}

.play-big svg {
  margin-left: 3px;
}

.detail-footer {
  margin-top: auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding-top: 10px;
  border-top: 1px solid var(--nf-overlay);
  font-size: 12px;
}

.detail-footer > span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-ops {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.detail-ops .nf-btn {
  height: 26px;
  padding: 0 11px;
  font-size: 12px;
}

.detail-ops .danger:hover {
  background: rgba(229, 9, 20, 0.8);
}

.detail-ops .pass:hover {
  background: rgba(0, 128, 96, 0.85);
}

/* ===== 封面角标 ===== */
.cover-fav {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 4;
  width: 30px;
  height: 30px;
  border: none;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(2px);
  color: var(--nf-text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: transform 0.15s ease, color 0.15s ease, background 0.15s ease;
}

.cover-fav:hover {
  transform: scale(1.12);
  color: #fff;
  background: rgba(229, 9, 20, 0.75);
}

.cover-fav.active {
  color: var(--nf-red);
  background: rgba(0, 0, 0, 0.55);
}

/* 左上角徽章组：类型 / 公开 / 审核状态 */
.cover-badges {
  position: absolute;
  top: 10px;
  left: 10px;
  z-index: 4;
  display: flex;
  gap: 6px;
  max-width: calc(100% - 56px);
  overflow: hidden;
}

.cover-type {
  flex-shrink: 0;
  padding: 2px 9px;
  border-radius: 3px;
  background: var(--nf-red);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 1px;
  line-height: 18px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
}

/* 公开徽章：绿色 */
.cover-public {
  flex-shrink: 0;
  padding: 2px 9px;
  border-radius: 3px;
  background: rgba(0, 128, 96, 0.85);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 1px;
  line-height: 18px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
}

/* 审核徽章：待审核黄 / 已驳回红 */
.cover-audit {
  flex-shrink: 0;
  padding: 2px 9px;
  border-radius: 3px;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 1px;
  line-height: 18px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
}

.cover-audit.pending {
  background: rgba(190, 138, 0, 0.9);
}

.cover-audit.rejected {
  background: rgba(120, 24, 28, 0.92);
}

/* 非本人公开视频的归属者胶囊 */
.bar-tags .chip.owner {
  background: rgba(229, 9, 20, 0.22);
  border-color: rgba(229, 9, 20, 0.45);
  color: #f0c2c5;
}
</style>
