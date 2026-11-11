<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { login, register, checkUsername, getAuthConfig } from './api'
import { setUser } from './composables/useAuth'
import { showToast } from './ui/toast'

const route = useRoute()
const router = useRouter()

// mode: 'login' | 'register'，两种模式共用一个表单
const mode = ref('login')
const submitting = ref(false)
const registrationEnabled = ref(true)
const form = reactive({ username: '', password: '', password2: '' })

onMounted(async () => {
  try {
    const cfg = await getAuthConfig()
    registrationEnabled.value = !!cfg.registrationEnabled
  } catch {
    // 配置读取失败时保持默认开放，后端仍会做最终校验
  }
})

const isLogin = () => mode.value === 'login'

const switchMode = (m) => {
  if (m === 'register' && !registrationEnabled.value) {
    showToast.warning('本站已关闭新用户注册，请联系管理员')
    return
  }
  mode.value = m
  resetNameCheck()
}

// ================= 注册用户名实时防重 =================
const nameState = ref('idle') // idle 未检测 / checking 检测中 / ok 可用 / taken 已占用 / invalid 格式不合法
const nameMsg = ref('')

const resetNameCheck = () => {
  nameState.value = 'idle'
  nameMsg.value = ''
}

let nameTimer = null
const doNameCheck = async () => {
  const username = form.username.trim()
  if (isLogin() || !username) {
    resetNameCheck()
    return
  }
  nameState.value = 'checking'
  try {
    const data = await checkUsername(username)
    // 输入还在变化时丢弃过期结果
    if (form.username.trim() !== username) return
    if (data.available) {
      nameState.value = 'ok'
    } else {
      // 格式问题与「已被注册」区分展示
      nameState.value = /2-50 位/.test(data.message) ? 'invalid' : 'taken'
    }
    nameMsg.value = data.message
  } catch {
    if (form.username.trim() === username) {
      nameState.value = 'idle' // 检测失败不阻塞注册，提交时后端仍会校验
      nameMsg.value = ''
    }
  }
}

// 输入防抖 500ms 自动检测；切到登录模式则清除提示
watch(
  () => form.username,
  () => {
    resetNameCheck()
    if (isLogin()) return
    clearTimeout(nameTimer)
    nameTimer = setTimeout(doNameCheck, 500)
  },
)

const onUsernameBlur = () => {
  clearTimeout(nameTimer)
  doNameCheck()
}

const submit = async () => {
  const username = form.username.trim()
  if (!username || !form.password) {
    showToast.warning('请输入用户名和密码')
    return
  }
  if (!isLogin()) {
    // 注册：以最后一次检测结果为准，未检测/过期则补一次
    if (nameState.value === 'idle' || nameState.value === 'checking') {
      await doNameCheck()
    }
    if (nameState.value === 'taken' || nameState.value === 'invalid') {
      showToast.warning(nameMsg.value)
      return
    }
    if (form.password !== form.password2) {
      showToast.warning('两次输入的密码不一致')
      return
    }
  }
  submitting.value = true
  try {
    const user = isLogin()
      ? await login(username, form.password)
      : await register(username, form.password)
    setUser(user)
    showToast(isLogin() ? `欢迎回来，${user.username}` : `注册成功，欢迎 ${user.username}`)
    // 登录前想去的页面（路由守卫记录），默认回列表页
    router.push(route.query.redirect || '/')
  } catch (e) {
    showToast.error(e.message)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-brand">
        <span class="brand-name">影库</span>
        <span class="brand-sub">VIDEO&nbsp;FACTORY</span>
      </div>
      <div class="login-title">{{ isLogin() ? '登录' : '注册新账号' }}</div>
      <p class="login-desc">
        {{ isLogin() ? '登录后查看属于你的影片与收藏' : '创建账号，保存属于你自己的影片信息与收藏' }}
      </p>

      <form class="login-form" @submit.prevent="submit">
        <div class="field-wrap">
          <input
            v-model="form.username"
            class="nf-input"
            :class="{
              err: nameState === 'taken' || nameState === 'invalid',
              good: nameState === 'ok',
            }"
            placeholder="用户名（中文 / 字母 / 数字 / 下划线）"
            maxlength="50"
            autocomplete="username"
            @blur="onUsernameBlur"
          />
          <div v-if="nameState !== 'idle'" class="name-hint" :class="nameState">
            <template v-if="nameState === 'checking'">检测中…</template>
            <template v-else>{{ nameMsg }}</template>
          </div>
        </div>
        <input
          v-model="form.password"
          class="nf-input"
          type="password"
          placeholder="密码（至少 6 位）"
          maxlength="72"
          :autocomplete="isLogin() ? 'current-password' : 'new-password'"
        />
        <input
          v-if="!isLogin()"
          v-model="form.password2"
          class="nf-input"
          type="password"
          placeholder="确认密码"
          maxlength="72"
          autocomplete="new-password"
        />
        <button class="nf-btn red lg submit" type="submit" :disabled="submitting">
          {{ submitting ? '请稍候…' : isLogin() ? '登 录' : '注 册' }}
        </button>
      </form>

      <div class="login-switch">
        <template v-if="isLogin()">
          <template v-if="registrationEnabled">
            还没有账号？<a class="switch-link" @click="switchMode('register')">立即注册</a>
          </template>
          <span v-else class="switch-closed">本站已关闭新用户注册，请联系管理员</span>
        </template>
        <template v-else>
          已有账号？<a class="switch-link" @click="switchMode('login')">直接登录</a>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background:
    radial-gradient(1000px 500px at 70% -10%, rgba(229, 9, 20, 0.16), transparent 60%),
    var(--nf-bg, #0b0b0d);
}

.login-card {
  width: 400px;
  max-width: 100%;
  padding: 44px 40px 36px;
  background: rgba(24, 24, 27, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.6);
}

.login-brand {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 30px;
}

.brand-name {
  font-size: 34px;
  font-weight: 800;
  letter-spacing: 5px;
  color: var(--nf-red);
  text-shadow: 0 0 18px rgba(229, 9, 20, 0.45);
  user-select: none;
}

.brand-sub {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 4px;
  color: var(--nf-text-muted);
  user-select: none;
}

.login-title {
  font-size: 21px;
  font-weight: 700;
  color: #f5f5f5;
}

.login-desc {
  margin: 8px 0 24px;
  font-size: 13px;
  color: var(--nf-text-muted);
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* 用户名防重：输入框状态色 + 内联提示 */
.field-wrap {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-wrap .nf-input.err {
  border-color: rgba(229, 9, 20, 0.8);
}

.field-wrap .nf-input.good {
  border-color: rgba(0, 168, 120, 0.75);
}

.name-hint {
  font-size: 12px;
  line-height: 1.4;
  color: var(--nf-text-muted);
}

.name-hint.checking {
  color: var(--nf-text-muted);
}

.name-hint.taken,
.name-hint.invalid {
  color: #ff6b72;
}

.name-hint.ok {
  color: #57cf9f;
}

.submit {
  margin-top: 6px;
  width: 100%;
}

.login-switch {
  margin-top: 22px;
  font-size: 13px;
  color: var(--nf-text-muted);
  text-align: center;
}

.switch-link {
  color: #f0c2c5;
  cursor: pointer;
  text-decoration: underline;
}

.switch-link:hover {
  color: #fff;
}

.switch-closed {
  color: #8b8b92;
}
</style>
