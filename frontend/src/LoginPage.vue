<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { login, register } from './api'
import { setUser } from './composables/useAuth'
import { showToast } from './ui/toast'

const route = useRoute()
const router = useRouter()

// mode: 'login' | 'register'，两种模式共用一个表单
const mode = ref('login')
const submitting = ref(false)
const form = reactive({ username: '', password: '', password2: '' })

const isLogin = () => mode.value === 'login'

const switchMode = (m) => {
  mode.value = m
}

const submit = async () => {
  const username = form.username.trim()
  if (!username || !form.password) {
    showToast.warning('请输入用户名和密码')
    return
  }
  if (!isLogin() && form.password !== form.password2) {
    showToast.warning('两次输入的密码不一致')
    return
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
        <input
          v-model="form.username"
          class="nf-input"
          placeholder="用户名（中文 / 字母 / 数字 / 下划线）"
          maxlength="50"
          autocomplete="username"
        />
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
          还没有账号？<a class="switch-link" @click="switchMode('register')">立即注册</a>
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
</style>
