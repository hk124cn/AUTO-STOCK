// 全局密码弹窗状态（共享给 main.js / App.vue / PasswordModal）
import { reactive } from 'vue'

export const authModal = reactive({
  visible: false,
  submitting: false,
  error: '',
  resolver: null  // resolve(password-success) 或 reject(password-fail)
})

export function showPasswordModal() {
  return new Promise((resolve, reject) => {
    authModal.visible = true
    authModal.error = ''
    authModal.submitting = false
    authModal.resolver = resolve
  })
}

export function resolveAuthModal(success) {
  if (authModal.resolver) {
    const r = authModal.resolver
    authModal.resolver = null
    r(success)
  }
  authModal.visible = false
}
