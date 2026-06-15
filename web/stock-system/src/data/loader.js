/**
 * 数据加载工具 - 股票操作系统
 *
 * 数据来源：
 *   - /api/v1/* (后端 API)
 *   - /data/*  (静态文件)
 *
 * 缓存策略（见 cache.js）：
 *   - T1_DATA（评分/信号）：当日加载 1 次
 *   - REALTIME（持仓/股价）：交易时间 30s，其他时段 5min-1h
 */

import { smartFetch, invalidateCache, clearAllCache, CACHE_KEYS } from './cache.js'

// ============== CSV 解析（RFC4180 兼容） ==============

function parseCSVLine(line) {
  const result = []
  let current = ''
  let inQuotes = false
  let i = 0
  while (i < line.length) {
    const ch = line[i]
    if (inQuotes) {
      if (ch === '"') {
        if (line[i + 1] === '"') {
          current += '"'
          i += 2
          continue
        }
        inQuotes = false
      } else {
        current += ch
      }
    } else {
      if (ch === '"') {
        inQuotes = true
      } else if (ch === ',') {
        result.push(current)
        current = ''
      } else {
        current += ch
      }
    }
    i++
  }
  result.push(current)
  return result
}

function parseCSV(text) {
  const lines = text.trim().split('\n')
  if (lines.length < 2) return []
  const headers = parseCSVLine(lines[0]).map(h => h.trim())
  const rows = []
  for (let i = 1; i < lines.length; i++) {
    const vals = parseCSVLine(lines[i])
    const row = {}
    headers.forEach((h, idx) => { row[h] = (vals[idx] || '').trim() })
    rows.push(row)
  }
  return rows
}

async function fetchCSV(path) {
  const sep = path.includes('?') ? '&' : '?'
  const finalUrl = path + sep + '_t=' + Date.now()
  try {
    const resp = await fetch(finalUrl)
    if (!resp.ok) throw new Error('HTTP ' + resp.status)
    return parseCSV(await resp.text())
  } catch (e) {
    console.error('加载CSV失败:', path, e)
    return []
  }
}

// 清空缓存（手动刷新按钮）
export { clearAllCache }

// ============== 业务 API（带智能缓存） ==============

const API_BASE = '/api/v1'

// T-1 数据：信号、评分
export async function loadSignals(forceRefresh = false) {
  const result = await smartFetch(
    CACHE_KEYS.SIGNALS,
    async () => {
      const r = await fetch(API_BASE + '/signals/latest')
      if (!r.ok) throw new Error('HTTP ' + r.status)
      return await r.json()
    },
    { dataType: 'T1_DATA', forceRefresh }
  )
  return {
    date: result.data?.date || '',
    data: result.data?.data || []
  }
}

export async function loadLatestScores(forceRefresh = false) {
  const result = await smartFetch(
    CACHE_KEYS.SCORES,
    async () => {
      const r = await fetch(API_BASE + '/scores/latest')
      if (!r.ok) throw new Error('HTTP ' + r.status)
      return await r.json()
    },
    { dataType: 'T1_DATA', forceRefresh }
  )
  return {
    date: result.data?.date || '',
    data: result.data?.data || []
  }
}

// 实时数据：持仓、统计
export async function loadAccount(mode = 'SIM', forceRefresh = false) {
  const result = await smartFetch(
    CACHE_KEYS.ACCOUNT(mode),
    async () => {
      const r = await fetch(API_BASE + `/portfolio/account?mode=${mode}`)
      if (!r.ok) throw new Error('HTTP ' + r.status)
      return await r.json()
    },
    { dataType: 'REALTIME', forceRefresh }
  )
  return result.data
}

export async function loadPositions(mode = 'SIM', forceRefresh = false) {
  const result = await smartFetch(
    CACHE_KEYS.POSITIONS(mode),
    async () => {
      const r = await fetch(API_BASE + `/portfolio/positions?mode=${mode}`)
      if (!r.ok) throw new Error('HTTP ' + r.status)
      return await r.json()
    },
    { dataType: 'REALTIME', forceRefresh }
  )
  return result.data?.positions || []
}

export async function loadTrades(mode = 'SIM', limit = 100, forceRefresh = false) {
  const result = await smartFetch(
    CACHE_KEYS.TRADES(mode),
    async () => {
      const r = await fetch(API_BASE + `/portfolio/trades?mode=${mode}&limit=${limit}`)
      if (!r.ok) throw new Error('HTTP ' + r.status)
      return await r.json()
    },
    { dataType: 'REALTIME', forceRefresh }
  )
  return result.data?.trades || []
}

export async function loadStats(mode = 'SIM', forceRefresh = false) {
  const result = await smartFetch(
    CACHE_KEYS.STATS(mode),
    async () => {
      const r = await fetch(API_BASE + `/portfolio/stats?mode=${mode}`)
      if (!r.ok) throw new Error('HTTP ' + r.status)
      return await r.json()
    },
    { dataType: 'REALTIME', forceRefresh }
  )
  return result.data
}

export async function loadNavHistory(mode = 'SIM', startDate, endDate, forceRefresh = false) {
  const params = new URLSearchParams()
  params.set('mode', mode)
  if (startDate) params.set('start_date', startDate)
  if (endDate) params.set('end_date', endDate)
  const result = await smartFetch(
    CACHE_KEYS.NAV(mode),
    async () => {
      const r = await fetch(API_BASE + `/portfolio/nav?` + params.toString())
      if (!r.ok) throw new Error('HTTP ' + r.status)
      return await r.json()
    },
    { dataType: 'REALTIME', forceRefresh }
  )
  return result.data?.navs || []
}

// 写操作（不缓存，调用后失效相关缓存）
// 使用 authedFetch 自动带 token；无 token 时弹密码框
import { authedFetch } from '../auth.js'

async function postData(url, body) {
  const r = await authedFetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
  return await r.json()
}

export async function buyStock(data) {
  const result = await postData(API_BASE + '/portfolio/buy', data)
  // 失效持仓/统计/账户
  invalidateCache('positions:')
  invalidateCache('stats:')
  invalidateCache('account:')
  invalidateCache('trades:')
  return result
}

export async function sellStock(data) {
  const result = await postData(API_BASE + '/portfolio/sell', data)
  invalidateCache('positions:')
  invalidateCache('stats:')
  invalidateCache('account:')
  invalidateCache('trades:')
  return result
}

export async function updatePrices(prices) {
  const result = await postData(API_BASE + '/portfolio/update-prices', { prices })
  invalidateCache('positions:')
  invalidateCache('stats:')
  return result
}

// ============== 工具函数 ==============

export function formatNumber(num, decimals = 2) {
  if (num === null || num === undefined || isNaN(num)) return '-'
  return Number(num).toFixed(decimals)
}

// 格式化金额（千分位分隔，2 位小数，带 ¥）
export function formatMoney(num) {
  if (num === null || num === undefined || isNaN(num)) return '-'
  const n = Number(num)
  return '¥' + n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

// 格式化整数金额（千分位分隔，不带小数）
export function formatMoneyInt(num) {
  if (num === null || num === undefined || isNaN(num)) return '-'
  return '¥' + Number(num).toLocaleString('zh-CN', { maximumFractionDigits: 0 })
}

export function formatPercent(num) {
  if (num === null || num === undefined || isNaN(num)) return '-'
  const val = Number(num)
  const prefix = val > 0 ? '+' : ''
  return prefix + val.toFixed(2) + '%'
}

export function getChangeClass(value) {
  if (!value || isNaN(value)) return 'flat'
  return Number(value) > 0 ? 'up' : Number(value) < 0 ? 'down' : 'flat'
}

export function formatDateYMD(date) {
  if (!date) return ''
  const d = new Date(date)
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return year + month + day
}

// 跳转到 yujing 个股详情（可透传持仓成本/策略）
export function gotoYujing(code, options = {}) {
  // 保留前导零（如 002463 → 002463）
  const c = String(code).padStart(6, '0')
  const params = new URLSearchParams()
  params.set('code', c)
  if (options.cost) params.set('cost', options.cost)
  if (options.tp !== undefined && options.tp !== null) params.set('tp', options.tp)
  if (options.sl !== undefined && options.sl !== null) params.set('sl', options.sl)
  if (options.strategy) params.set('strategy', options.strategy)
  window.open(`https://auto-claw.top/yujing/?${params.toString()}`, '_blank')
}
