<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useCover } from '../composables/useCover'

const props = defineProps({
  videos: { type: Array, default: () => [] }, // 全量列表，内部取前 5 条做轮播
})

defineEmits(['play', 'detail'])

const { coverCache, captureCover } = useCover()

// ================= Hero 轮播（取列表前 5 条） =================
const heroIndex = ref(0)
let heroTimer = null
const featured = computed(() => props.videos.slice(0, 5))

const startHero = () => {
  stopHero()
  heroTimer = setInterval(() => {
    if (featured.value.length > 1) {
      heroIndex.value = (heroIndex.value + 1) % featured.value.length
    }
  }, 6000)
}
const stopHero = () => {
  if (heroTimer) clearInterval(heroTimer)
  heroTimer = null
}
const heroPrev = () => {
  if (!featured.value.length) return
  heroIndex.value = (heroIndex.value - 1 + featured.value.length) % featured.value.length
}
const heroNext = () => {
  if (!featured.value.length) return
  heroIndex.value = (heroIndex.value + 1) % featured.value.length
}

watch(
  featured,
  (list) => {
    if (heroIndex.value >= list.length) heroIndex.value = 0
    // Hero 大图提前加载封面
    list.forEach((v) => captureCover(v))
  },
  { immediate: true },
)

onMounted(startHero)
onUnmounted(stopHero)
</script>

<template>
  <!-- ===== Hero 大图轮播（netflixgc 首屏大卡） ===== -->
  <section
    v-if="featured.length"
    class="hero"
    @mouseenter="stopHero"
    @mouseleave="startHero"
  >
    <div
      v-for="(v, i) in featured"
      :key="v.id"
      class="hero-slide"
      :class="[`cover-tone-${v.id % 6}`, { on: i === heroIndex }]"
    >
      <img v-if="coverCache[v.id]" class="hero-img" :src="coverCache[v.id]" alt="" />
      <div class="hero-scrim"></div>

      <div class="hero-content">
        <span v-if="v.typeName" class="hero-badge">{{ v.typeName }}</span>
        <h1 class="hero-title" :title="v.title">{{ v.title }}</h1>
        <p class="hero-desc">{{ v.description || v.filePath }}</p>
        <div v-if="v.tags.length" class="hero-tags">
          <span v-for="name in v.tags" :key="name" class="hero-chip">{{ name }}</span>
        </div>
        <div class="hero-actions">
          <button class="nf-btn red lg" @click="$emit('play', v)">
            <svg viewBox="0 0 24 24" width="18" height="18">
              <path d="M8 5.5v13l11-6.5z" fill="currentColor" />
            </svg>
            立即播放
          </button>
          <button class="nf-btn ghost lg" @click="$emit('detail', v)">影片详情</button>
        </div>
      </div>
    </div>

    <button v-if="featured.length > 1" class="hero-arrow left" @click="heroPrev">
      <svg viewBox="0 0 24 24" width="22" height="22"><path d="M15 5l-7 7 7 7" stroke="currentColor" stroke-width="2.2" fill="none" stroke-linecap="round" stroke-linejoin="round" /></svg>
    </button>
    <button v-if="featured.length > 1" class="hero-arrow right" @click="heroNext">
      <svg viewBox="0 0 24 24" width="22" height="22"><path d="M9 5l7 7-7 7" stroke="currentColor" stroke-width="2.2" fill="none" stroke-linecap="round" stroke-linejoin="round" /></svg>
    </button>

    <div v-if="featured.length > 1" class="hero-dots">
      <i
        v-for="(v, i) in featured"
        :key="v.id"
        :class="{ on: i === heroIndex }"
        @click="heroIndex = i"
      ></i>
    </div>
  </section>
</template>

<style scoped>
/* ===== Hero 轮播 ===== */
.hero {
  position: relative;
  height: 480px;
  overflow: hidden;
  background: #000;
}

.hero-slide {
  position: absolute;
  inset: 0;
  opacity: 0;
  transition: opacity 0.7s ease;
  pointer-events: none;
}

.hero-slide.on {
  opacity: 1;
  pointer-events: auto;
}

.hero-img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* 渐变遮罩：左侧加深保证文字可读 */
.hero-scrim {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(90deg, rgba(0, 0, 0, 0.82) 0%, rgba(0, 0, 0, 0.45) 42%, rgba(0, 0, 0, 0.05) 75%),
    linear-gradient(180deg, rgba(11, 11, 13, 0.35) 0%, rgba(0, 0, 0, 0) 30%, rgba(11, 11, 13, 0.95) 100%);
}

.hero-content {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 40px 56px;
  width: 100%;
}

.hero-badge {
  display: inline-block;
  padding: 3px 12px;
  border-radius: 3px;
  background: var(--nf-red);
  color: #fff;
  font-size: 12.5px;
  font-weight: 700;
  letter-spacing: 2px;
  margin-bottom: 14px;
  box-shadow: 0 3px 12px rgba(229, 9, 20, 0.5);
}

.hero-title {
  margin: 0 0 12px;
  max-width: 640px;
  font-size: 40px;
  font-weight: 800;
  line-height: 1.2;
  letter-spacing: 1px;
  color: #fff;
  text-shadow: 0 2px 18px rgba(0, 0, 0, 0.6);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.hero-desc {
  margin: 0 0 16px;
  max-width: 560px;
  font-size: 14.5px;
  line-height: 1.75;
  color: rgba(255, 255, 255, 0.82);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-shadow: 0 1px 8px rgba(0, 0, 0, 0.5);
}

.hero-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 22px;
}

.hero-chip {
  padding: 2px 12px;
  border: 1px solid rgba(255, 255, 255, 0.35);
  border-radius: 14px;
  font-size: 12px;
  line-height: 18px;
  color: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(2px);
}

.hero-actions {
  display: flex;
  gap: 12px;
}

.hero-arrow {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  z-index: 5;
  width: 44px;
  height: 44px;
  border: none;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.45);
  color: rgba(255, 255, 255, 0.85);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.25s ease, background 0.2s ease;
}

.hero:hover .hero-arrow {
  opacity: 1;
}

.hero-arrow:hover {
  background: rgba(229, 9, 20, 0.8);
  color: #fff;
}

.hero-arrow.left {
  left: 18px;
}

.hero-arrow.right {
  right: 18px;
}

.hero-dots {
  position: absolute;
  right: 40px;
  bottom: 22px;
  z-index: 5;
  display: flex;
  gap: 8px;
}

.hero-dots i {
  width: 22px;
  height: 3px;
  border-radius: 2px;
  background: rgba(255, 255, 255, 0.3);
  cursor: pointer;
  transition: background 0.2s ease;
}

.hero-dots i.on {
  background: var(--nf-red);
}

@media (max-width: 900px) {
  .hero {
    height: 400px;
  }

  .hero-content {
    padding: 0 20px 44px;
  }

  .hero-title {
    font-size: 28px;
  }
}
</style>
