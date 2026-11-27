import { createApp, h } from 'vue'
import { RouterView } from 'vue-router'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import Tvue from '@zhaoyifannan/tvue'
import '@zhaoyifannan/tvue/dist/index.css'
// FontAwesome Free（solid / brands）供菜单图标选择器与侧边栏共用
import '@fortawesome/fontawesome-free/css/all.min.css'
import { loadIconfontStyles } from './utils/icons'
import './theme.css'
import './console-theme.css'
import router from './router'
import { useThemeStore } from './stores/theme'
import { permissionDirective } from './directives/permission'

const app = createApp({ render: () => h(RouterView) })
const pinia = createPinia()
app.use(pinia)
useThemeStore().init()
app.use(router)
// tvue-crud 内部依赖表格、弹窗、树等控件，管理端使用 Element Plus 全量注册。
app.use(ElementPlus, { locale: undefined })
app.use(Tvue, { size: 'default', menuType: 'text', locale: 'zh-cn' })
for (const [name, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(name, component)
}
app.directive('permission', permissionDirective)
// 用户在 utils/icons.ts 的 ICONFONT_CSS_URLS 中配置阿里 iconfont 项目链接后自动加载
loadIconfontStyles()
app.mount('#app')
