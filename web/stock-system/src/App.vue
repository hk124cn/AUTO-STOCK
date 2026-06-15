<template>
  <div id="app">
    <!-- 顶部导航栏 -->
    <nav class="navbar">
      <div class="nav-brand">
        <span class="brand-icon">📈</span>
        <span class="brand-text">股票操作系统</span>
      </div>
      <div class="nav-links">
        <router-link to="/" class="nav-link" active-class="active">
          <span class="nav-icon">🏠</span>
          <span>首页</span>
        </router-link>
        <router-link to="/signals" class="nav-link" active-class="active">
          <span class="nav-icon">📡</span>
          <span>信号监控</span>
        </router-link>
        <router-link to="/portfolio" class="nav-link" active-class="active">
          <span class="nav-icon">💼</span>
          <span>持仓管理</span>
        </router-link>
        <router-link to="/stats" class="nav-link" active-class="active">
          <span class="nav-icon">📊</span>
          <span>收益统计</span>
        </router-link>
        <router-link to="/strategies" class="nav-link" active-class="active">
          <span class="nav-icon">⚙️</span>
          <span>策略</span>
        </router-link>
      </div>
    </nav>

    <!-- 主内容区 -->
    <main class="main-content">
      <router-view />
    </main>

    <!-- 全局密码弹窗（持仓/统计 实操时弹出） -->
    <PasswordModal
      :visible="authModal.visible"
      :submitting="authModal.submitting"
      :error-msg="authModal.error"
      @submit="onPasswordSubmit"
      @cancel="onPasswordCancel"
    />
  </div>
</template>

<script setup>
import { inject } from 'vue'
import PasswordModal from './components/PasswordModal.vue'
import { resolveAuthModal } from './authModal.js'
import { login } from './auth.js'

const authModal = inject('authModal')

async function onPasswordSubmit(password) {
  if (!password) return
  authModal.submitting = true
  authModal.error = ''
  try {
    await login(password)
    authModal.submitting = false
    resolveAuthModal(true)
  } catch (e) {
    authModal.submitting = false
    authModal.error = e.message || '登录失败'
  }
}

function onPasswordCancel() {
  if (authModal.submitting) return
  resolveAuthModal(false)  // 取消：让 await 返回 null（auth.js 的 authedFetch 会 reject 一次然后再弹）
}
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'PingFang SC', sans-serif;
  background: #0f0f1a;
  color: #e0e0e0;
  min-height: 100vh;
}

#app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* 导航栏 */
.navbar {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  padding: 0 24px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  position: sticky;
  top: 0;
  z-index: 100;
}

.nav-brand {
  display: flex;
  align-items: center;
  gap: 8px;
}

.brand-icon {
  font-size: 24px;
}

.brand-text {
  font-size: 18px;
  font-weight: 600;
  background: linear-gradient(135deg, #00d4ff, #7b68ee);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.nav-links {
  display: flex;
  gap: 4px;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 8px;
  text-decoration: none;
  color: #a0a0b0;
  font-size: 14px;
  transition: all 0.2s;
}

.nav-link:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
}

.nav-link.active {
  background: rgba(0, 212, 255, 0.15);
  color: #00d4ff;
}

.nav-icon {
  font-size: 16px;
}

/* 主内容 */
.main-content {
  flex: 1;
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
}

/* 通用卡片样式 */
.card {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  padding: 20px;
  margin-bottom: 16px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: #a0a0b0;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 统计数字 */
.stat-value {
  font-size: 28px;
  font-weight: 700;
  background: linear-gradient(135deg, #00d4ff, #7b68ee);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.stat-label {
  font-size: 12px;
  color: #666;
  margin-top: 4px;
}

/* 涨跌颜色 */
.up { color: #ff4757; }
.down { color: #2ed573; }
.flat { color: #a0a0b0; }

/* 表格样式 */
.data-table {
  width: 100%;
  border-collapse: collapse;
}

.data-table th {
  text-align: left;
  padding: 12px 16px;
  font-size: 12px;
  color: #666;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.data-table td {
  padding: 12px 16px;
  font-size: 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.data-table tr:hover {
  background: rgba(255, 255, 255, 0.03);
}

/* 按钮样式 */
.btn {
  padding: 8px 16px;
  border-radius: 8px;
  border: none;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-primary {
  background: linear-gradient(135deg, #00d4ff, #7b68ee);
  color: #fff;
}

.btn-primary:hover {
  opacity: 0.9;
  transform: translateY(-1px);
}

.btn-outline {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: #a0a0b0;
}

.btn-outline:hover {
  border-color: #00d4ff;
  color: #00d4ff;
}

/* 搜索框 */
.search-box {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.search-input {
  flex: 1;
  padding: 10px 16px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.05);
  color: #e0e0e0;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
}

.search-input:focus {
  border-color: #00d4ff;
}

.search-input::placeholder {
  color: #555;
}

/* 响应式 */
@media (max-width: 768px) {
  .navbar {
    padding: 0 12px;
  }

  .nav-link span:last-child {
    display: none;
  }

  .main-content {
    padding: 12px;
  }
}
</style>
