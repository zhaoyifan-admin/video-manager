import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

// 开发服务器：前端跑在 5173，/api 请求代理到后端 Flask(5000)
export default defineConfig({
  base: './', // 打包产物使用相对路径，任意目录/子路径部署都不会 404
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
