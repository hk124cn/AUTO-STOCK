<template>
  <div class="container">
    <!-- 顶部搜索栏 -->
    <div class="header">
      <div class="title">📈 个股评分预警图</div>
      <div class="search-box">
        <input
          v-model="searchKeyword"
          @input="onSearch"
          @keydown.enter="onEnterSearch"
          @focus="showDropdown = true"
          @blur="hideDropdown"
          placeholder="输入代码或名称搜索，回车选中第一条 (如: 600519)"
          class="search-input"
        />
        <div v-if="showDropdown && searchResults.length" class="dropdown">
          <div
            v-for="stock in searchResults"
            :key="stock.code + stock.codeNum"
            class="dropdown-item"
            @mousedown="selectStock(stock)"
          >
            {{ stock.code }} - {{ stock.name }}
          </div>
        </div>
      </div>
      <div v-if="currentStock" class="stock-info">
        <span class="stock-name">{{ currentStock.name }}</span>
        <span class="stock-code">{{ currentStock.code }}</span>
      </div>
    </div>

    <!-- 控制面板 -->
    <div v-if="currentStock" class="controls">
      <div class="time-range">
        <button
          v-for="r in timeRanges"
          :key="r.label"
          :class="{ active: selectedRange === r.label }"
          @click="selectedRange = r.label"
        >{{ r.label }}</button>
      </div>
      <div class="toggle-btns">
        <button :class="{ active: showPrice }" @click="showPrice = !showPrice">
          <span class="checkbox">{{ showPrice ? '☑' : '☐' }}</span> 价格K线
        </button>
        <button :class="{ active: showScore }" @click="showScore = !showScore">
          <span class="checkbox">{{ showScore ? '☑' : '☐' }}</span> 评分曲线
        </button>
      </div>
    </div>

    <!-- K线图容器 -->
    <div class="charts">
      <div ref="chartRef" class="chart"></div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading">加载中...</div>
    <div v-if="error" class="error">{{ error }}</div>

  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import { searchStocks } from '../data/loader.js'

// 状态
const searchKeyword = ref('')
const searchResults = ref([])
const showDropdown = ref(false)
const currentStock = ref(null)
const selectedRange = ref('1M')
const showPrice = ref(true)
const showScore = ref(false)
const loading = ref(false)
const error = ref('')
const chartRef = ref(null)
let chart = null

// 时间范围
const timeRanges = [
  { label: '1M', days: 22 },
  { label: '3M', days: 66 },
  { label: '6M', days: 132 },
  { label: '1Y', days: 252 },
  { label: 'All', days: 99999 }
]

// 数据
let allData = { scores: [], prices: [], market: [] }

// 统一日期格式为 YYYYMMDD 字符串（处理CSV读出来的浮点数如 20160104.0）
function normalizeDate(val) {
  if (!val) return ''
  return String(val).replace(/-/g, '').replace(/\.0$/, '').trim()
}

// 搜索
async function onSearch() {
  const results = await searchStocks(searchKeyword.value)
  searchResults.value = results
  showDropdown.value = true
}

// 回车选中第一条
async function onEnterSearch() {
  if (!searchResults.value.length && searchKeyword.value) {
    await onSearch()
  }
  showDropdown.value = true
  if (searchResults.value.length) {
    selectStock(searchResults.value[0])
  }
}

// 选择股票
async function selectStock(stock) {
  currentStock.value = stock
  showDropdown.value = false
  searchKeyword.value = ''
  await loadData()
}

// 加载数据
async function loadData() {
  if (!currentStock.value) return
  loading.value = true
  error.value = ''
  try {
    const { getStockData, loadPrice } = await import('../data/loader.js')
    const code = currentStock.value.code  // 原始代码，带前导零
    const [scoreData, priceData] = await Promise.all([
      getStockData(code, '20250101', '20991231'),
      loadPrice(code)
    ])
    allData = {
      scores: scoreData.scores,
      prices: priceData,
      market: []
    }
    renderChart()
  } catch (e) {
    error.value = '加载数据失败: ' + e.message
  } finally {
    loading.value = false
  }
}

// 获取日期范围
function getDateRange() {
  const range = timeRanges.find(r => r.label === selectedRange.value)
  if (!range || !allData.prices.length) return { start: '', end: '' }

  const prices = allData.prices
  const endIdx = prices.length - 1
  const startIdx = Math.max(0, prices.length - range.days)

  return {
    start: normalizeDate(prices[startIdx]?.date || prices[startIdx]?.['日期'] || ''),
    end: normalizeDate(prices[endIdx]?.date || prices[endIdx]?.['日期'] || '')
  }
}

// 渲染图表
function renderChart() {
  if (!chartRef.value) return

  nextTick(() => {
    if (!chart) {
      chart = echarts.init(chartRef.value)
    }

    const { start, end } = getDateRange()

    const filterByDate = (rows) => {
      return rows.filter(r => {
        const rawDate = r.date || r['日期'] || ''
        const d = normalizeDate(rawDate)
        return d >= start && d <= end
      })
    }

    const priceData = filterByDate(allData.prices)
    const scoreData = filterByDate(allData.scores)

    // K线数据 [open, close, low, high]，同时构建X轴，跳过无效行
    const xAxis = []
    const priceCandles = []
    for (const p of priceData) {
      const o = parseFloat(p['开盘'])
      const c = parseFloat(p['收盘'])
      const l = parseFloat(p['最低'])
      const h = parseFloat(p['最高'])
      if ([o, c, l, h].some(v => isNaN(v) || v <= 0)) continue
      xAxis.push(normalizeDate(p.date || p['日期']))
      priceCandles.push([o, c, l, h])
    }

    // 评分查找表，按价格日期对齐
    const scoreMap = {}
    scoreData.forEach(s => {
      scoreMap[normalizeDate(s.date)] = parseFloat(s.total_score) || null
    })
    const scoreLine = xAxis.map(d => scoreMap[d] ?? null)

    const series = []
    const yAxis = []

    // 价格K线 - 左Y轴
    if (showPrice.value && priceCandles.length) {
      series.push({
        name: '价格K线',
        type: 'candlestick',
        data: priceCandles,
        yAxisIndex: 0
      })
      yAxis.push({
        type: 'value',
        position: 'left',
        axisLine: { lineStyle: { color: '#666' } },
        axisLabel: { color: '#999' },
        splitLine: { lineStyle: { color: '#333' } },
        scale: true,
        name: '价格'
      })
    }

    // 评分曲线 - 右Y轴，叠加在同一个grid上
    if (showScore.value && scoreLine.length) {
      series.push({
        name: '评分',
        type: 'line',
        data: scoreLine,
        yAxisIndex: showPrice.value ? 1 : 0,
        smooth: true,
        symbol: 'circle',
        symbolSize: 4,
        lineStyle: { color: '#ffd700', width: 2 },
        itemStyle: { color: '#ffd700' }
      })
      yAxis.push({
        type: 'value',
        position: 'right',
        axisLine: { lineStyle: { color: '#ffd700' } },
        axisLabel: { color: '#ffd700' },
        splitLine: { show: false },
        name: '评分',
        min: 0,
        max: 100
      })
    }

    // 没有任何series时清空图表
    if (!series.length) {
      chart.clear()
      return
    }

    // 构建前一日收盘价查找表（用于计算涨幅）
    const prevCloseMap = {}
    for (let i = 1; i < priceCandles.length; i++) {
      prevCloseMap[xAxis[i]] = priceCandles[i - 1][1] // 前一日收盘价
    }

    const option = {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        formatter(params) {
          if (!params.length) return ''
          const date = params[0].axisValue
          const fmtDate = date.length === 8 ? `${date.slice(0,4)}-${date.slice(4,6)}-${date.slice(6,8)}` : date
          let html = `<div style="font-weight:600;margin-bottom:6px">${fmtDate}</div>`
          for (const p of params) {
            if (p.seriesType === 'candlestick' && p.data) {
              // ECharts category轴: p.data = [categoryIndex, open, close, low, high]
              const d = p.data
              const o = Number(d[1])
              const c = Number(d[2])
              const l = Number(d[3])
              const h = Number(d[4])
              const prevClose = prevCloseMap[date]
              const pct = prevClose > 0 ? ((c - prevClose) / prevClose * 100) : 0
              const color = pct >= 0 ? '#22c55e' : '#ef4444'
              const sign = pct >= 0 ? '+' : ''
              html += `<div>开盘: ${o.toFixed(2)}　收盘: ${c.toFixed(2)}</div>`
              html += `<div>最低: ${l.toFixed(2)}　最高: ${h.toFixed(2)}</div>`
              html += `<div>涨幅: <span style="color:${color};font-weight:600">${sign}${pct.toFixed(2)}%</span></div>`
            }
            if (p.seriesType === 'line' && p.seriesName === '评分') {
              const val = p.data != null && !isNaN(p.data) ? Number(p.data).toFixed(1) : '--'
              html += `<div style="color:#ffd700">评分: ${val}</div>`
            }
          }
          return html
        }
      },
      legend: {
        show: true,
        bottom: 10,
        textStyle: { color: '#ccc' }
      },
      grid: { left: 70, right: showScore.value ? 70 : 20, top: 40, bottom: 60 },
      xAxis: {
        type: 'category',
        data: xAxis,
        axisLine: { lineStyle: { color: '#666' } },
        axisLabel: { color: '#999' }
      },
      yAxis,
      series
    }

    chart.setOption(option, true)
  })
}

// 窗口大小变化
function onResize() {
  chart?.resize()
}

// 监听变化
watch([selectedRange, showPrice, showScore], () => {
  renderChart()
})

onMounted(() => {
  window.addEventListener('resize', onResize)
  onSearch()
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
})

function hideDropdown() {
  setTimeout(() => { showDropdown.value = false }, 200)
}
</script>

<style scoped>
.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}
.header { margin-bottom: 20px; }
.title { font-size: 24px; font-weight: 700; color: #ffd700; margin-bottom: 15px; }
.search-box { position: relative; margin-bottom: 15px; }
.search-input {
  width: 100%; padding: 12px 16px; background: #2a2a4a;
  border: 1px solid #444; border-radius: 8px; color: #fff; font-size: 16px;
}
.search-input:focus { outline: none; border-color: #ffd700; }
.dropdown {
  position: absolute; top: 100%; left: 0; right: 0;
  background: #2a2a4a; border: 1px solid #444; border-radius: 8px;
  margin-top: 4px; max-height: 300px; overflow-y: auto; z-index: 100;
}
.dropdown-item { padding: 10px 16px; cursor: pointer; border-bottom: 1px solid #333; color: #ddd; }
.dropdown-item:hover { background: #3a3a5a; }
.stock-info { display: flex; gap: 12px; align-items: center; }
.stock-name { font-size: 20px; font-weight: 600; }
.stock-code { color: #888; }
.controls { display: flex; gap: 20px; margin-bottom: 20px; flex-wrap: wrap; }
.time-range, .toggle-btns { display: flex; gap: 8px; }
button {
  padding: 8px 14px; background: #2a2a4a; border: 1px solid #444;
  border-radius: 6px; color: #ccc; cursor: pointer; font-size: 14px;
  transition: all 0.15s;
}
button.active {
  background: #ffd700; color: #1a1a2e; border-color: #ffd700;
  font-weight: 600;
}
button .checkbox { margin-right: 4px; font-size: 12px; }
.charts { width: 100%; }
.chart { width: 100%; height: 600px; }
.loading, .error { text-align: center; padding: 20px; color: #888; }
.error { color: #ff6b6b; }
</style>