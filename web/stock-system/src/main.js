import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import PasswordModal from './components/PasswordModal.vue'
import { installRequestPassword } from './auth.js'
import { showPasswordModal, authModal, resolveAuthModal } from './authModal.js'
import { login } from './auth.js'

// 路由配置
const routes = [
  { path: '/', name: 'Dashboard', component: () => import('./views/Dashboard.vue') },
  { path: '/signals', name: 'Signals', component: () => import('./views/Signals.vue') },
  { path: '/portfolio', name: 'Portfolio', component: () => import('./views/Portfolio.vue') },
  { path: '/stats', name: 'Stats', component: () => import('./views/Stats.vue') },
  { path: '/strategies', name: 'Strategies', component: () => import('./views/Strategies.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

const app = createApp(App)
app.use(router)
app.component('PasswordModal', PasswordModal)

// 把 authModal 注入到全局组件，App.vue 用 inject() 拿到
app.provide('authModal', authModal)

// 安装全局密码弹窗触发器：authedFetch 缺 token 时调用此函数
installRequestPassword(showPasswordModal)

app.mount('#app')

// 暴露给 App.vue 用（不能跨 provide/inject 传函数，但本例没用）
export { authModal, resolveAuthModal, login }
