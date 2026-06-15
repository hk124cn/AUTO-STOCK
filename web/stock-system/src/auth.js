// 操作密码鉴权：token 存储 + authedFetch 包装
// 调用方：loader.js（自动覆盖所有走 loader 的写操作）
//       Portfolio.vue / Strategies.vue（直接 fetch 的写操作）

const TOKEN_KEY = 'stock_auth_token'
const EXPIRES_KEY = 'stock_auth_expires'
const API_BASE = '/api/v1'

// === Token 读写 ===
export function getToken() {
  const token = localStorage.getItem(TOKEN_KEY)
  const expires = parseInt(localStorage.getItem(EXPIRES_KEY) || '0', 10)
  if (!token || Date.now() > expires) {
    clearToken()
    return null
  }
  return token
}

export function setToken(token, expiresIn) {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(EXPIRES_KEY, String(Date.now() + expiresIn * 1000))
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(EXPIRES_KEY)
}

// === 登录：密码换 token ===
export async function login(password) {
  const resp = await fetch(API_BASE + '/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password })
  })
  if (!resp.ok) {
    if (resp.status === 401) throw new Error('密码错误')
    throw new Error(`登录失败: HTTP ${resp.status}`)
  }
  const data = await resp.json()
  setToken(data.token, data.expires_in)
  return data.token
}

// === 全局密码弹窗触发器（由 main.js 安装） ===
let requestPassword = null
export function installRequestPassword(fn) {
  requestPassword = fn
}

// === 包装 fetch：写操作无 token 时弹密码框；401 自动重试一次 ===
export async function authedFetch(url, options = {}) {
  const method = (options.method || 'GET').toUpperCase()
  // 读操作直接走 fetch，不带 token
  if (method === 'GET' || method === 'HEAD') {
    return fetch(url, options)
  }
  // 写操作：确保有 token
  if (!requestPassword) {
    throw new Error('AuthGuard 未安装：请在 main.js 调用 installRequestPassword')
  }
  let token = getToken()
  if (!token) {
    token = await requestPassword()
  }
  const doFetch = (t) => fetch(url, {
    ...options,
    headers: {
      ...(options.headers || {}),
      Authorization: `Bearer ${t}`
    }
  })
  let resp = await doFetch(token)
  // token 失效 → 清掉再弹一次密码
  if (resp.status === 401) {
    clearToken()
    token = await requestPassword()
    resp = await doFetch(token)
  }
  return resp
}
