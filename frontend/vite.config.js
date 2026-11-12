import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

// 开发服务器：前端跑在 5173，/api 请求代理到后端 Flask(5000)
export default defineConfig({
  // 必须用根绝对路径：前端是 createWebHistory，/detail/:id、/play/:id 这类二级路由
  // 会把相对资源 ./assets/... 解析成 /detail/assets/...，Flask 兜底返回 HTML，
  // 浏览器因 MIME 不符丢弃 JS/CSS，表现为详情页 / 播放页白屏。
  base: '/',
  plugins: [vue(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
    },
  },
})
