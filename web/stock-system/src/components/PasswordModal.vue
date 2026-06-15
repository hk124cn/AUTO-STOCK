<template>
  <div v-if="visible" class="auth-overlay" @click.self="onCancel">
    <div class="auth-modal">
      <div class="auth-header">
        <h3>🔒 实操密码</h3>
        <button class="auth-close" @click="onCancel">✕</button>
      </div>
      <div class="auth-body">
        <p class="auth-hint">请输入持仓/统计 实操密码以继续操作</p>
        <input
          ref="inputEl"
          v-model="password"
          type="password"
          class="auth-input"
          placeholder="操作密码"
          @keyup.enter="onSubmit"
          :disabled="submitting"
        />
        <div v-if="errorMsg" class="auth-error">⚠️ {{ errorMsg }}</div>
      </div>
      <div class="auth-footer">
        <button class="auth-btn auth-btn-outline" @click="onCancel" :disabled="submitting">取消</button>
        <button class="auth-btn auth-btn-primary" @click="onSubmit" :disabled="submitting || !password">
          {{ submitting ? '验证中...' : '确认' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  visible: Boolean,
  submitting: Boolean,
  errorMsg: String
})
const emit = defineEmits(['submit', 'cancel'])

const password = ref('')
const inputEl = ref(null)

// 每次弹窗显示时清空输入框并 focus
watch(() => props.visible, async (v) => {
  if (v) {
    password.value = ''
    await nextTick()
    inputEl.value?.focus()
  }
})

function onSubmit() {
  if (!password.value || props.submitting) return
  emit('submit', password.value)
}

function onCancel() {
  if (props.submitting) return
  emit('cancel')
}
</script>

<style scoped>
.auth-overlay {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex; align-items: center; justify-content: center;
  z-index: 9999;
}
.auth-modal {
  background: #1a1a2e;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  width: 90%; max-width: 380px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}
.auth-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 20px; border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
.auth-header h3 { font-size: 16px; color: #e0e0e0; }
.auth-close { background: none; border: none; color: inherit; cursor: pointer; font-size: 18px; }
.auth-body { padding: 20px; }
.auth-hint { font-size: 13px; color: #a0a0b0; margin-bottom: 12px; }
.auth-input {
  width: 100%; padding: 10px 12px; border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.05);
  color: #e0e0e0; font-size: 14px; outline: none;
}
.auth-input:focus { border-color: #00d4ff; }
.auth-error { color: #ff4757; font-size: 13px; margin-top: 8px; }
.auth-footer {
  display: flex; justify-content: flex-end; gap: 12px;
  padding: 16px 20px; border-top: 1px solid rgba(255, 255, 255, 0.1);
}
.auth-btn {
  padding: 8px 16px; border-radius: 8px; border: none;
  font-size: 14px; cursor: pointer; transition: all 0.2s;
}
.auth-btn-primary { background: linear-gradient(135deg, #00d4ff, #7b68ee); color: #fff; }
.auth-btn-primary:hover:not(:disabled) { opacity: 0.9; }
.auth-btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.auth-btn-outline { background: transparent; border: 1px solid rgba(255, 255, 255, 0.2); color: #a0a0b0; }
.auth-btn-outline:hover:not(:disabled) { border-color: #00d4ff; color: #00d4ff; }
</style>
