/**
 * 策略相关 API 封装
 */

import { smartFetch, CACHE_KEYS } from './cache.js'

const API_BASE = '/api/v1'

export async function loadStrategy(mode = 'SIM', forceRefresh = false) {
  const result = await smartFetch(
    `strategy:${mode}`,
    async () => {
      const r = await fetch(`${API_BASE}/portfolio/strategy?mode=${mode}`)
      if (!r.ok) throw new Error('HTTP ' + r.status)
      return await r.json()
    },
    { dataType: 'T1_DATA', forceRefresh }
  )
  return result.data
}

export async function loadStrategies(forceRefresh = false) {
  const result = await smartFetch(
    'strategies:list',
    async () => {
      const r = await fetch(`${API_BASE}/strategies`)
      if (!r.ok) throw new Error('HTTP ' + r.status)
      return await r.json()
    },
    { dataType: 'T1_DATA', forceRefresh }
  )
  return result.data?.strategies || []
}
