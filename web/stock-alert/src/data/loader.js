/**
 * 数据加载工具 - 直接读取本地CSV文件
 * 数据目录：
 *   - /yujing/data/score_price_history.csv   (评分历史)
 *   - /yujing/data/price/                   (个股价格)
 */

const BASE_URL = '/yujing/data'

// 缓存
const cache = {}

async function fetchCSV(path) {
  if (cache[path]) return cache[path]
  try {
    const resp = await fetch(BASE_URL + path)
    const text = await resp.text()
    const lines = text.trim().split('\n')
    const headers = lines[0].split(',')
    const rows = []
    for (let i = 1; i < lines.length; i++) {
      const vals = lines[i].split(',')
      const row = {}
      headers.forEach((h, idx) => { row[h] = vals[idx] })
      rows.push(row)
    }
    cache[path] = rows
    return rows
  } catch (e) {
    console.error('加载CSV失败:', path, e)
    return []
  }
}

// 统一日期为 YYYYMMDD 字符串（处理CSV读出来的浮点数如 20160104.0）
function normalizeDate(val) {
  if (!val) return ''
  return String(val).replace(/-/g, '').replace(/\.0$/, '').trim()
}

// 统一股票代码为数字字符串（用于比较），保留前导零（用于显示）
function normalizeCode(val) {
  return String(val).replace(/^0+/, '') || String(val)
}

// 加载评分历史 (score_price_history.csv)
export async function loadScoreHistory() {
  return fetchCSV('/score_price_history.csv')
}

// 加载个股价格 (data/price/{code}.csv) — 保留前导零，文件名有前导零
export async function loadPrice(code) {
  return fetchCSV(`/price/${code}.csv`)
}

// 加载大盘指数 (000300 沪深300)
export async function loadMarketIndex(code = '000300') {
  return fetchCSV(`/price/${code}.csv`)
}

// 根据股票代码和日期范围获取数据
// code: 原始代码（带前导零），用于加载文件
export async function getStockData(code, startDate, endDate) {
  const normalizedCode = normalizeCode(code)

  const [scoreRows, priceRows] = await Promise.all([
    loadScoreHistory(),
    loadPrice(code)
  ])

  // 过滤日期范围
  const filterByDate = (rows, start, end) => {
    return rows.filter(r => {
      const rawDate = r.date || r['日期'] || ''
      const d = normalizeDate(rawDate)
      return d >= start && d <= end
    })
  }

  // 评分数据：按 code 过滤
  const scoreFiltered = scoreRows.filter(r => normalizeCode(r.code) === normalizedCode)

  return {
    scores: filterByDate(scoreFiltered, startDate, endDate),
    prices: filterByDate(priceRows, startDate, endDate)
  }
}

// 搜索股票（从评分历史中获取）
export async function searchStocks(keyword) {
  const rows = await loadScoreHistory()
  const seen = {}
  const results = []

  for (const r of rows) {
    const codeNum = normalizeCode(r.code)
    if (!seen[codeNum]) {
      seen[codeNum] = true
      // 保留原始格式用于显示（前导零不丢失）
      results.push({ code: String(r.code), codeNum, name: r.name })
    }
  }

  if (!keyword) return results.slice(0, 50)
  const kw = keyword.toLowerCase().trim()
  return results.filter(s =>
    s.codeNum.includes(kw) || s.name.toLowerCase().includes(kw)
  ).slice(0, 20)
}