import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import Home from './views/Home.vue'
import Detail from './views/Detail.vue'
import './assets/styles.css'

const routes = [
  { path: '/', component: Home },
  { path: '/detail/:code', component: Detail, props: true }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

const app = createApp(App)
app.use(router)
app.mount('#app')