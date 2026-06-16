/**
 * 全局数据缓存 + 智能刷新策略
 *
 * 数据类型：
 *   - T1_DATA: T-1 收盘后生成的固定数据（评分/信号），当日加载 1 次
 *   - REALTIME: 实时股价/持仓，交易时间频繁刷新
 *
 * 交易时间（A股）：
 *   - 上午 9:30-11:30
 *   - 下午 13:00-15:00
 *
 * 缓存策略：
 *   - T1_DATA：每个 key 每日 19:00 之前只加载 1 次（localStorage 记录）
 *   - REALTIME：
 *     - 交易时间内：30 秒
 *     - 盘前/中午休市：5 分钟
 *     - 收盘后/节假日：1 小时
 */

const CACHE_VERSION = 'v2'  // 2026-06-15: 升级到 v2 让旧 strategy-versions/signals 缓存失效

// A 股交易时间段判断
export function getMarketState() {
  const now = new Date()
  // 用本地时间（服务器在东八区）
  const hour = now.getHours()
  const minute = now.getMinutes()
  const day = now.getDay() // 0=周日, 6=周六
  const time = hour * 60 + minute

  // 周末
  if (day === 0 || day === 6) {
    return 'HOLIDAY'
  }

  // 9:30-11:30, 13:00-15:00
  if (time >= 9 * 60 + 30 && time <= 11 * 60 + 30) {
    return 'TRADING_MORNING'
  }
  if (time >= 13 * 60 && time <= 15 * 60) {
    return 'TRADING_AFTERNOON'
  }
  // 9:00-9:30 盘前集合竞价
  if (time >= 9 * 60 && time < 9 * 60 + 30) {
    return 'PRE_OPEN'
  }
  // 11:30-13:00 午休
  if (time > 11 * 60 + 30 && time < 13 * 60) {
    return 'LUNCH'
  }
  // 15:00 后
  if (time > 15 * 60) {
    return 'POST_CLOSE'
  }
  return 'NIGHT'  // 0:00-9:00
}

// 根据市场状态返回缓存 TTL（毫秒）
export function getCacheTTL(dataType) {
  if (dataType === 'T1_DATA') {
    // T-1 数据：当日加载 1 次（除非显式失效）
    return 24 * 60 * 60 * 1000
  }

  const state = getMarketState()
  // REALTIME
  if (state === 'TRADING_MORNING' || state === 'TRADING_AFTERNOON') {
    return 30 * 1000  // 30 秒
  }
  if (state === 'PRE_OPEN' || state === 'LUNCH') {
    return 5 * 60 * 1000  // 5 分钟
  }
  // POST_CLOSE / NIGHT / HOLIDAY
  return 60 * 60 * 1000  // 1 小时
}

// 缓存存储（localStorage + 内存）
const memoryCache = new Map()
const memoryTime = new Map()

function getLocalKey(key) {
  return `stock-system-cache:${CACHE_VERSION}:${key}`
}

function getFromLocal(key) {
  try {
    const raw = localStorage.getItem(getLocalKey(key))
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (Date.now() - parsed.time > parsed.ttl) {
      localStorage.removeItem(getLocalKey(key))
      return null
    }
    return parsed.data
  } catch (e) {
    return null
  }
}

function setToLocal(key, data, ttl) {
  try {
    localStorage.setItem(getLocalKey(key), JSON.stringify({
      time: Date.now(),
      ttl: ttl,
      data: data
    }))
  } catch (e) {
    // localStorage 满或被禁用
  }
}

function getFromMemory(key) {
  const time = memoryTime.get(key)
  const ttl = memoryCache.get(key + ':ttl')
  if (!time || !ttl) return null
  if (Date.now() - time > ttl) {
    memoryCache.delete(key)
    memoryTime.delete(key)
    return null
  }
  return memoryCache.get(key)
}

function setToMemory(key, data, ttl) {
  memoryCache.set(key, data)
  memoryCache.set(key + ':ttl', ttl)
  memoryTime.set(key, Date.now())
}

/**
 * 智能获取数据（带缓存）
 *
 * @param {string} key - 唯一 key
 * @param {function} fetcher - 异步获取函数
 * @param {object} options - { dataType: 'T1_DATA' | 'REALTIME', forceRefresh: false }
 */
export async function smartFetch(key, fetcher, options = {}) {
  const { dataType = 'REALTIME', forceRefresh = false } = options

  if (!forceRefresh) {
    // 先查内存
    const mem = getFromMemory(key)
    if (mem !== null) {
      return { data: mem, fromCache: true }
    }
    // T1_DATA 再查 localStorage
    if (dataType === 'T1_DATA') {
      const local = getFromLocal(key)
      if (local !== null) {
        setToMemory(key, local, 60 * 1000)  // 内存保留 1 分钟
        return { data: local, fromCache: true }
      }
    }
  }

  // 真正请求
  const data = await fetcher()
  const ttl = getCacheTTL(dataType)
  setToMemory(key, data, ttl)
  if (dataType === 'T1_DATA') {
    setToLocal(key, data, ttl)
  }
  return { data, fromCache: false }
}

/**
 * 主动失效缓存（买入/卖出/更新价格后调用）
 */
export function invalidateCache(prefix) {
  // 清内存
  for (const key of memoryCache.keys()) {
    if (key.startsWith(prefix)) {
      memoryCache.delete(key)
      memoryTime.delete(key)
    }
  }
  // 清 localStorage
  for (let i = localStorage.length - 1; i >= 0; i--) {
    const k = localStorage.key(i)
    if (k && k.includes(`stock-system-cache:${CACHE_VERSION}:${prefix}`)) {
      localStorage.removeItem(k)
    }
  }
}

/**
 * 清空所有缓存
 */
export function clearAllCache() {
  memoryCache.clear()
  memoryTime.clear()
  for (let i = localStorage.length - 1; i >= 0; i--) {
    const k = localStorage.key(i)
    if (k && k.startsWith(`stock-system-cache:${CACHE_VERSION}:`)) {
      localStorage.removeItem(k)
    }
  }
}

// 缓存键常量
export const CACHE_KEYS = {
  SIGNALS: 'signals',  // signals 实际键: signals:v1 / signals:v2（loader.js 拼后缀）
  STRATEGY_VERSIONS: 'strategy-versions',
  SCORES: 'scores',
  POSITIONS: (mode) => `positions:${mode}`,
  TRADES: (mode) => `trades:${mode}`,
  STATS: (mode) => `stats:${mode}`,
  ACCOUNT: (mode) => `account:${mode}`,
  NAV: (mode) => `nav:${mode}`,
}
