<template>
  <div class="container">
    <header class="header">
      <div class="header-content">
        <h1 class="header-title">财报评分</h1>
      </div>
    </header>

    <div class="search-section">
      <div class="search-box-wrapper">
        <div class="search-box">
          <span class="search-icon">🔍</span>
          <input
            v-model="stockCode"
            class="search-input"
            type="text"
            placeholder="输入代码或名称 (600519 或 茅台)"
            @input="onSearchInput"
            @keyup.enter="search"
            @focus="showDropdown = searchResults.length > 0"
            @blur="hideDropdown"
            maxlength="20"
          />
        </div>
        <!-- 搜索候选下拉框 -->
        <div v-if="showDropdown && searchResults.length > 0" class="search-dropdown">
          <div
            v-for="item in searchResults"
            :key="item.code"
            class="search-item"
            @click="selectStock(item)"
          >
            <span class="search-item-code">{{ String(item.code).padStart(6, '0') }}</span>
            <span class="search-item-name" v-html="highlightMatch(item.name)"></span>
          </div>
        </div>
        <div v-else-if="showDropdown && searchLoading" class="search-dropdown">
          <div class="search-loading">搜索中...</div>
        </div>
      </div>

      <label class="refresh-checkbox">
        <input type="checkbox" v-model="refreshData" />
        <span>不是最新财报？选中这里再获取</span>
      </label>

      <button class="btn btn-full" @click="search" :disabled="loading">
        {{ loading ? '查询中...' : '查询评分' }}
      </button>
    </div>

    <div v-if="loading" class="loading">
      <div class="spinner"></div>
      <span>正在获取财报数据...</span>
    </div>

    <div v-if="error" class="error">
      {{ error }}
    </div>

    <div v-if="result && !loading" class="result">
      <!-- 翻转容器 -->
      <div class="flip-container" :class="{ flipped: showKline }">
        <!-- 正面：评分卡片 -->
        <div class="card score-card flip-front">
          <div class="stock-info">
            <div class="stock-code">{{ result.code }}</div>
            <div class="stock-name">{{ result.name }}</div>
          </div>

          <div class="score-large">
            <div class="score-number" :class="scoreClass">
              {{ currentScore.total }}
            </div>
            <div class="score-label">财报评分{{ currentScore.report_date ? '(' + currentScore.report_date + ')' : '' }}</div>
            <div class="score-max">满分 20</div>
            <div class="trend" :class="trend">
              <span v-if="trend === 'up'" style="color: #FF3B30;">↑</span>
              <span v-else-if="trend === 'down'" style="color: #34C759;">↓</span>
              <span v-else>→</span>
              <span>{{ trendText }}</span>
            </div>
          </div>
        </div>

        <!-- 背面：K线图表 -->
        <div class="card kline-card flip-back">
          <div class="kline-info">
            <span class="kline-title">公告后股价走势</span>
            <span class="kline-type">{{ klineData?.report_type || '' }}</span>
          </div>

          <div v-if="klineLoading" class="kline-loading">
            <div class="spinner"></div>
            <span>加载K线...</span>
          </div>

          <div v-else-if="klineError" class="kline-error">
            {{ klineError }}
          </div>

          <div v-else-if="showKline" class="kline-wrapper">
            <div class="kline-date">{{ klineData?.disclosure_date }} 公告</div>
            <div ref="klineChartRef" class="kline-chart"></div>
            <div v-if="klineStats" class="kline-stats">
              <span>首日涨跌幅: <span :class="parseFloat(klineStats.firstDayChange) >= 0 ? 'up' : 'down'">{{ klineStats.firstDayChange }}%</span></span>
              <span v-if="klineStats.totalChange !== null">，{{ klineStats.totalDays }}日后涨跌幅: <span :class="parseFloat(klineStats.totalChange) >= 0 ? 'up' : 'down'">{{ klineStats.totalChange }}%</span></span>
            </div>
          </div>
        </div>
      </div>

      <button class="btn btn-full toggle-btn" @click="toggleView">
        {{ showKline ? '← 返回评分' : '查看公告后K线走势 →' }}
      </button>

      <button class="btn btn-full" @click="goToDetail">
        查看详情 →
      </button>

      <div class="footer-link" @click="goToMainSystem">
        📊 进入多因子综合评分系统
      </div>
    </div>

    <!-- 默认显示的备案号 -->
    <div class="icp-filing">
      <a href="https://beian.mps.gov.cn/#/query/webSearch?code=51019002009420" rel="noreferrer" target="_blank">
        <img src="@/assets/备案图标.png" style="vertical-align:middle;width:16px;height:16px;" /> 川公网安备51019002009420号</a>
      &nbsp;|&nbsp;
      <a href="https://beian.miit.gov.cn/" target="_blank">蜀ICP备2026019242号</a>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import * as echarts from 'echarts'

const router = useRouter()
const stockCode = ref('')
const refreshData = ref(false)
const loading = ref(false)
const error = ref('')
const result = ref(null)
const searchResults = ref([])
const showDropdown = ref(false)
const searchLoading = ref(false)
let searchDebounceTimer = null

// K线相关
const showKline = ref(false)
const klineLoading = ref(false)
const klineError = ref('')
const klineData = ref(null)
const klineChartRef = ref(null)
let klineChart = null

// 切换评分/K线视图
const flipTransitioning = ref(false)

const toggleView = () => {
  if (flipTransitioning.value) return
  flipTransitioning.value = true

  if (!showKline.value) {
    // 正在翻到背面
    showKline.value = true
    setTimeout(() => {
      nextTick(() => {
        renderBackChart()
        flipTransitioning.value = false
      })
    }, 400)
  } else {
    // 正在翻到正面
    showKline.value = false
    if (klineChart) {
      klineChart.dispose()
      klineChart = null
    }
    setTimeout(() => { flipTransitioning.value = false }, 400)
  }
}

// 计算涨跌幅统计
const klineStats = computed(() => {
  if (!klineData.value?.kline?.length) return null
  const kline = klineData.value.kline
  const prevClose = klineData.value.prev_close
  if (kline.length < 1 || !prevClose) return null

  // 首日涨跌幅：(收盘价-昨日收盘价)/昨日收盘价*100
  const firstDay = kline[0]
  const firstDayChange = ((firstDay.close - prevClose) / prevClose * 100).toFixed(2)

  // 累计涨跌幅（如果有的话）
  let totalChange = null
  let totalDays = 0
  if (kline.length > 1) {
    const lastDay = kline[kline.length - 1]
    totalChange = ((lastDay.close - prevClose) / prevClose * 100).toFixed(2)
    totalDays = kline.length
  }

  return { firstDayChange, totalChange, totalDays }
})

// 构建K线图表配置（蜡烛图）
const buildKlineOption = (data, grid) => ({
  grid,
  xAxis: {
    type: 'category',
    data: data.dates,
    axisLine: { lineStyle: { color: '#ddd' } },
    axisLabel: { color: '#666', fontSize: 10 },
    min: 0,
    max: 6,  // 固定7个位置，不足7天时靠左显示
    axisPointer: {
      show: true,
      type: 'line',
      lineStyle: {
        color: '#007AFF',
        width: 1,
        type: 'dashed'
      }
    }
  },
  yAxis: {
    type: 'value',
    scale: true,
    splitLine: { lineStyle: { color: '#f0f0f0' } },
    axisLabel: { color: '#666', fontSize: 10 }
  },
  series: [
    {
      type: 'candlestick',
      data: data.values,
      barWidth: '40%',
      itemStyle: {
        color: '#ef232a',
        color0: '#14b143',
        borderColor: '#ef232a',
        borderColor0: '#14b143'
      }
    },
    {
      type: 'line',
      data: data.values.map(d => d[1]),  // 收盘价
      symbol: 'none',
      lineStyle: { width: 0, opacity: 0 },
      tooltip: { show: true }
    }
  ],
  tooltip: {
    trigger: 'item',
    confine: false,
    backgroundColor: 'rgba(28,28,30,0.95)',
    borderColor: '#38383A',
    textStyle: { color: '#fff', fontSize: 12 },
    z: 9999,
    show: true,
    appendTo: document.body,
    triggerOn: 'mousemove',
    formatter: (params) => {
      // 处理trigger: 'item'时params是对象，不是数组
      const idx = params.dataIndex ?? params[0]?.dataIndex
      if (idx === undefined || !data.kline || !data.kline[idx]) return ''
      const k = data.kline[idx]

      // 计算基准价：第1天用prevClose，后续用前一天收盘价
      let basePrice = null
      if (idx === 0) {
        basePrice = data.prevClose
      } else {
        basePrice = data.kline[idx - 1]?.close
      }

      if (!basePrice) {
        return `<div style="line-height:1.6;">
          <b>${k.date}</b><br/>
          开盘: ${k.open?.toFixed(2) || 'N/A'}<br/>
          最高: ${k.high?.toFixed(2) || 'N/A'}<br/>
          最低: ${k.low?.toFixed(2) || 'N/A'}<br/>
          收盘: ${k.close?.toFixed(2) || 'N/A'}<br/>
          <span style="color:#999;">前日收盘价获取失败，无法计算涨跌幅</span>
        </div>`
      }
      const change = ((k.close - basePrice) / basePrice * 100).toFixed(2)
      const changeColor = parseFloat(change) >= 0 ? '#ef232a' : '#14b143'
      return `<div style="line-height:1.6;">
        <b>${k.date}</b><br/>
        开盘: ${k.open?.toFixed(2) || 'N/A'}<br/>
        最高: ${k.high?.toFixed(2) || 'N/A'}<br/>
        最低: ${k.low?.toFixed(2) || 'N/A'}<br/>
        收盘: ${k.close?.toFixed(2) || 'N/A'}<br/>
        <span style="color:${changeColor};font-weight:bold;">涨跌幅: ${change}%</span>
      </div>`
    }
  },
  animation: false
})

// 渲染背面K线图（蜡烛图）
const renderBackChart = () => {
  if (!klineData.value?.kline?.length || !klineChartRef.value) return
  const data = klineData.value.kline
  const prevClose = klineData.value.prev_close
  const dates = data.map(d => d.date.slice(5))
  // 蜡烛图数据格式: [open, close, low, high]
  const values = data.map(d => [d.open, d.close, d.low, d.high])

  if (klineChart) klineChart.dispose()
  klineChart = echarts.init(klineChartRef.value)
  klineChart.setOption(buildKlineOption({ dates, values, kline: data, prevClose },
    { left: 40, right: 10, top: 10, bottom: 30 }))
}

// 加载K线数据
const loadKline = async () => {
  if (!result.value) return
  klineLoading.value = true
  klineError.value = ''
  try {
    const response = await axios.get(`/api/v1/financial/kline/${result.value.code}`, {
      params: { quarter: '本季度' }
    })
    klineData.value = response.data

    // 检查是否有错误
    if (response.data?.error) {
      klineError.value = response.data.error
      klineData.value = null
    }
  } catch (err) {
    klineError.value = err.response?.data?.error || 'K线加载失败'
    klineData.value = null
  } finally {
    klineLoading.value = false
  }
}

// 搜索输入处理（带防抖）
const onSearchInput = () => {
  clearTimeout(searchDebounceTimer)
  const query = stockCode.value.trim()
  if (query.length < 2) {
    searchResults.value = []
    showDropdown.value = false
    return
  }
  searchLoading.value = true
  showDropdown.value = true
  searchDebounceTimer = setTimeout(() => doSearch(query), 300)
}

// 执行搜索
const doSearch = async (query) => {
  try {
    const response = await axios.get('/api/v1/stock/search', {
      params: { q: query, limit: 10 }
    })
    searchResults.value = response.data || []
  } catch (e) {
    console.error('Search error:', e)
    searchResults.value = []
  } finally {
    searchLoading.value = false
  }
}

// 隐藏下拉框
const hideDropdown = () => {
  setTimeout(() => { showDropdown.value = false }, 200)
}

// 选择股票
const selectStock = (item) => {
  console.log('=== 点击搜索项 ===')
  console.log('原始 item:', item)
  console.log('item.code 类型:', typeof item.code)
  console.log('item.code 值:', item.code)
  
  // 股票代码补零到6位
  const codeStr = String(item.code).padStart(6, '0')
  console.log('处理后 codeStr:', codeStr)
  
  stockCode.value = codeStr
  console.log('stockCode.value:', stockCode.value)
  
  showDropdown.value = false
  searchResults.value = []
  // 直接调用查询API
  performSearch(stockCode.value)
}

// 执行查询
const performSearch = async (code) => {
  console.log('=== performSearch 调用 ===')
  console.log('传入 code:', code)
  console.log('code 类型:', typeof code)
  
  if (!code) {
    console.log('code 为空，返回')
    return
  }

  // 确保是6位数字
  const codeStr = String(code).trim()
  console.log('codeStr:', codeStr)
  
  if (!/^\d{6}$/.test(codeStr)) {
    console.log('代码格式不匹配:', codeStr)
    error.value = '请输入6位数字的股票代码'
    return
  }

  loading.value = true
  error.value = ''

  // 重置状态
  showKline.value = false
  klineData.value = null

  try {
    const url = refreshData.value
      ? `/api/v1/financial/score/${codeStr}?refresh=true`
      : `/api/v1/financial/score/${codeStr}`
    console.log('请求 URL:', url)
    const response = await axios.get(url)
    console.log('API 返回:', response.data)
    result.value = response.data
    // 评分获取后立即加载K线数据
    loadKline()
  } catch (err) {
    console.error('查询错误:', err)
    error.value = err.response?.data?.error || '查询失败'
    result.value = null
  } finally {
    loading.value = false
  }
}

// 高亮匹配文字
const highlightMatch = (text) => {
  const query = stockCode.value.trim().toLowerCase()
  if (query.length < 2) return text
  const idx = text.toLowerCase().indexOf(query)
  if (idx === -1) return text
  return text.substring(0, idx) + '<span class="search-item-highlight">' +
         text.substring(idx, idx + query.length) + '</span>' +
         text.substring(idx + query.length)
}

const currentScore = computed(() => {
  if (!result.value) return { total: 0 }
  return result.value.scores['本季度'] || { total: 0 }
})

const scoreClass = computed(() => {
  const score = currentScore.value.total
  if (score >= 15) return 'excellent'
  if (score >= 5) return 'good'
  return 'poor'
})

// 趋势箭头和文字
const trend = computed(() => {
  if (!result.value || !result.value.quarter_trends) return 'stable'
  return result.value.quarter_trends['本季度']?.trend || 'stable'
})

const trendText = computed(() => {
  if (!result.value || !result.value.quarter_trends) return ''
  return result.value.quarter_trends['本季度']?.trend_text || ''
})

const search = async () => {
  const code = stockCode.value.trim()
  if (!code) {
    error.value = '请输入股票代码'
    return
  }

  await performSearch(code)
}

const goToDetail = () => {
  if (result.value) {
    router.push(`/detail/${result.value.code}`)
  }
}

const goToMainSystem = () => {
  window.open('https://auto-claw.top/reports', '_blank')
}
</script>

<style scoped>
.search-section {
  margin-top: 24px;
}

.result {
  margin-top: 24px;
}

/* 翻转动画 */
.flip-container {
  perspective: 1000px;
  margin-bottom: 16px;
  display: grid;
}

.flip-front,
.flip-back {
  backface-visibility: hidden;
  transition: transform 0.5s ease;
  grid-row: 1;
  grid-column: 1;
}

.flip-front {
  transform: rotateY(0deg);
}

.flip-back {
  transform: rotateY(180deg);
}

.flip-container.flipped .flip-front {
  transform: rotateY(-180deg);
}

.flip-container.flipped .flip-back {
  transform: rotateY(0deg);
}

.toggle-btn {
  margin-bottom: 12px;
}

.refresh-checkbox {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  font-size: 14px;
  color: var(--text-secondary, #8E8E93);
  cursor: pointer;
}

.refresh-checkbox input {
  width: 18px;
  height: 18px;
  accent-color: #007AFF;
}

/* 评分卡片 - 与K线卡片同高 */
.score-card {
  min-height: 280px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 16px 20px;
  margin-bottom: 16px;
}

.score-card .stock-info {
  margin-bottom: 4px;
}

.score-card .score-large {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  margin-top: 8px;
}

/* K线卡片 */
.kline-card {
  margin-bottom: 16px;
  padding: 16px;
}

/* K线相关样式 */
.kline-wrapper {
  height: 200px;
  display: flex;
  flex-direction: column;
  margin-top: 16px;
}

.kline-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.kline-title {
  font-size: 15px;
  font-weight: 600;
  color: #007AFF;
}

.kline-type {
  color: #007AFF;
  background: rgba(0, 122, 255, 0.1);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.kline-date {
  font-size: 12px;
  color: #666;
  margin-bottom: 12px;
}

.kline-loading,
.kline-error,
.kline-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 180px;
  color: #999;
  font-size: 14px;
}

.kline-error {
  color: #ff4d4f;
}

.kline-chart {
  width: 100%;
  height: 150px;
  margin-bottom: 12px;
}

.kline-stats {
  margin-top: 24px;
  font-size: 12px;
  color: #666;
  text-align: center;
}

.kline-stats .up {
  color: #ef232a;
}

.kline-stats .down {
  color: #14b143;
}

/* 切换按钮 */
.toggle-btn {
  margin-bottom: 16px;
}

.icp-filing {
  text-align: center;
  padding: 20px 0 10px;
  font-size: 12px;
  color: #8E8E93;
}

.icp-filing a {
  color: #8E8E93;
  text-decoration: none;
}
</style>