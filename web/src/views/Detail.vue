<template>
  <div class="container">
    <div class="header-row">
      <button class="back-btn" @click="goBack">
        ← 返回
      </button>
      <div class="tab-switch">
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'score' }"
          @click="toggleTab('score')"
        >
          评分说明
        </button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'feedback' }"
          @click="toggleTab('feedback')"
        >
          建议反馈
        </button>
      </div>
    </div>

    <!-- 关闭按钮 -->
    <button
      v-if="activeTab"
      class="close-tab-btn"
      @click="activeTab = ''"
    >
      ← 返回股票详情
    </button>

    <!-- 评分说明 -->
    <div v-if="activeTab === 'score'" class="info-card">
      <div class="info-title">📊 评分规则说明</div>
      <div class="info-section">
        <div class="info-subtitle">评分指标与权重</div>
        <div class="info-table">
          <div class="info-row header">
            <span>指标</span>
            <span>满分</span>
            <span>负增长封顶</span>
          </div>
          <div class="info-row">
            <span>扣非净利润</span>
            <span>10分</span>
            <span>-5分</span>
          </div>
          <div class="info-row">
            <span>归母净利润</span>
            <span>5分</span>
            <span>-2.5分</span>
          </div>
          <div class="info-row">
            <span>营业收入</span>
            <span>5分</span>
            <span>-2.5分</span>
          </div>
        </div>
        <div class="info-note">满分 20 分，最低 -10 分</div>
      </div>

      <div class="info-section">
        <div class="info-subtitle">计算规则</div>
        <div class="info-text">
          <p><strong>正增长：</strong>基础分 = 满分 × (同比增长率 / 40%)，最大为满分</p>
          <p><strong>负增长：</strong>基础分 = 封顶分 × (同比 / 100) / 10</p>
        </div>
      </div>

      <div class="info-section">
        <div class="info-subtitle">趋势分计算</div>
        <div class="info-text">
          <p>基于最近3个季度同比变化趋势：</p>
          <p>• 连续增长/下降：±7.5% × 满分</p>
          <p>• V型/倒V反转：±5% × 满分</p>
          <p>• 整体变化：±5% × 满分</p>
          <p class="info-note">趋势分范围：±10% × 满分</p>
        </div>
      </div>

      <div class="info-section">
        <div class="info-subtitle">数据来源</div>
        <div class="info-text">
          <p>财务数据来源于上市公司季报披露的合并报表数据，采用AKShare获取公开市场数据。</p>
        </div>
      </div>

      <div class="info-section">
        <div class="info-subtitle">如何使用评分</div>
        <div class="info-text">
          <p>本评分是对抽离出来的单季度财报数据的分析，能有效避免整体财报增长，但最新季度已经出现下滑的问题。</p>
        </div>
        <div class="info-text" style="margin-top: 12px;">
          <p><strong>短期持股使用方法：</strong></p>
          <p>如果最新季度和上季度评分相差不大，接下来短期走势平稳的可能性较大；如果相差太大，则接下来短期走势出现大幅度上涨或者大幅度下跌的可能较大。</p>
        </div>
        <div class="info-text" style="margin-top: 12px;">
          <p><strong>长期持股使用方法：</strong></p>
          <p>主要看得分高低，结合基本面判断是否进入好转或者下滑通道。</p>
        </div>
        <div class="info-text" style="margin-top: 12px;">
          <p><strong>注意事项：</strong></p>
          <p>• 本评分仅基于财务数据，不构成投资建议</p>
          <p>• 评分反映历史业绩，未来表现可能不同</p>
          <p>• 投资需综合考虑行业、估值、市场情绪等因素</p>
        </div>
      </div>
    </div>

    <!-- 建议反馈 -->
    <div v-if="activeTab === 'feedback'" class="info-card">
      <div class="info-title">💡 功能建议反馈</div>
      <div class="info-text">
        <p>欢迎提出宝贵建议！您可以通过以下方式反馈：</p>
      </div>

      <div class="feedback-form">
        <textarea
          v-model="feedbackContent"
          class="feedback-textarea"
          placeholder="请输入您的建议或问题..."
          rows="5"
        ></textarea>
        <div class="feedback-actions">
          <button
            class="feedback-btn submit"
            :disabled="!feedbackContent.trim() || submitting"
            @click="submitFeedback"
          >
            {{ submitting ? '提交中...' : '提交建议' }}
          </button>
          <button
            v-if="feedbackSubmitted"
            class="feedback-btn success"
            @click="feedbackSubmitted = false"
          >
            已提交，继续反馈
          </button>
        </div>
        <div v-if="feedbackMessage" class="feedback-message" :class="feedbackMessage.type">
          {{ feedbackMessage.text }}
        </div>
      </div>

      <div class="info-section">
        <div class="info-subtitle">其他联系方式</div>
        <div class="info-text contact">
          <p>📧 邮箱：qw_129@sina.com</p>
          <p>🌐 网站：auto-claw.top</p>
        </div>
      </div>
    </div>

    <div v-if="loading" class="loading">
      <div class="spinner"></div>
      <span>正在加载...</span>
    </div>

    <div v-if="error" class="error">
      {{ error }}
    </div>

    <!-- 股票详情内容 -->
    <div v-if="result && !loading && !activeTab" class="result">
      <!-- 季度选择器 -->
      <div class="quarter-tabs">
        <button
          v-for="quarter in ['本季度', '上季度', '上上季度']"
          :key="quarter"
          class="quarter-tab"
          :class="{ active: activeQuarter === quarter }"
          @click="activeQuarter = quarter"
        >
          {{ quarter }}
          <span v-if="result.scores[quarter]?.report_date" class="quarter-date">
            {{ formatDate(result.scores[quarter].report_date) }}
          </span>
        </button>
      </div>

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
            <div class="score-label">{{ activeQuarter }}评分（满分20）</div>
            <div class="updated-time" v-if="klineData?.disclosure_date">财报发布于 {{ klineData.disclosure_date }}</div>
            <div class="updated-time" v-else-if="klineError" style="color: #ff4d4f;">{{ klineError }}</div>
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

      <!-- 切换按钮 -->
      <button class="btn btn-full toggle-btn" @click="toggleView">
        {{ showKline ? '← 返回评分' : '查看公告后K线走势 →' }}
      </button>

      <div class="card">
        <h3 style="margin-bottom: 16px; font-size: 17px; font-weight: 600;">分项得分 （点击看详情）</h3>

        <!-- 营业收入 -->
        <div class="progress-item" @click="toggleProgressTip('营业收入', currentScore.营收, currentScore['营收趋势'], 5, $event)">
          <div class="progress-label">
            <span>营业收入</span>
            <span>{{ currentScore.营收 || 0 }} / 5</span>
          </div>
          <div class="progress-bar">
            <div class="progress-fill" :class="getScoreClass(currentScore.营收, 5)" :style="{ width: ((currentScore.营收 || 0) > 0 ? (currentScore.营收 || 0) / 5 * 100 : 0) + '%' }"></div>
          </div>
        </div>

        <!-- 归母净利润 -->
        <div class="progress-item" @click="toggleProgressTip('归母净利润', currentScore.归母, currentScore['归母趋势'], 5, $event)">
          <div class="progress-label">
            <span>归母净利润</span>
            <span>{{ currentScore.归母 || 0 }} / 5</span>
          </div>
          <div class="progress-bar">
            <div class="progress-fill" :class="getScoreClass(currentScore.归母, 5)" :style="{ width: ((currentScore.归母 || 0) > 0 ? (currentScore.归母 || 0) / 5 * 100 : 0) + '%' }"></div>
          </div>
        </div>

        <!-- 扣非净利润 -->
        <div class="progress-item" @click="toggleProgressTip('扣非净利润', currentScore.扣非, currentScore['扣非趋势'], 10, $event)">
          <div class="progress-label">
            <span>扣非净利润</span>
            <span>{{ currentScore.扣非 || 0 }} / 10</span>
          </div>
          <div class="progress-bar">
            <div class="progress-fill" :class="getScoreClass(currentScore.扣非, 10)" :style="{ width: ((currentScore.扣非 || 0) > 0 ? (currentScore.扣非 || 0) / 10 * 100 : 0) + '%' }"></div>
          </div>
        </div>

        <!-- 浮动提示框 -->
        <div v-if="progressTip.show" class="progress-tooltip" :style="{ top: progressTip.y + 'px', left: progressTip.x + 'px' }" @click.stop="hideProgressTip">
          <div class="tooltip-title">{{ progressTip.name }}</div>
          <div class="tooltip-row">
            <span>得分：</span>
            <span>{{ progressTip.score }} / {{ progressTip.max }}</span>
          </div>
          <div class="tooltip-row">
            <span>基础分：</span>
            <span>{{ (progressTip.score - progressTip.trend).toFixed(2) }}</span>
          </div>
          <div class="tooltip-row">
            <span>趋势分：</span>
            <span :style="{ color: progressTip.trend >= 0 ? '#FF3B30' : '#34C759' }">
              {{ progressTip.trend >= 0 ? '+' : '' }}{{ progressTip.trend }}
            </span>
          </div>
          <div class="tooltip-hint">点击任意处关闭</div>
        </div>
      </div>

      <!-- 财务数据卡片 -->
      <div class="card" v-if="currentScore.财务数据">
        <h3 style="margin-bottom: 16px; font-size: 17px; font-weight: 600;">单季度财务数据</h3>
        <div class="finance-grid">
          <div class="finance-item">
            <div class="finance-label">营业总收入</div>
            <div class="finance-value">{{ currentScore.财务数据.营业总收入 }}</div>
          </div>
          <div class="finance-item">
            <div class="finance-label">营业总收入同比</div>
            <div class="finance-value" :class="getGrowthClass(currentScore.财务数据.营业总收入同比)">
              {{ currentScore.财务数据.营业总收入同比 }}
            </div>
          </div>
          <div class="finance-item">
            <div class="finance-label">净利润</div>
            <div class="finance-value">{{ currentScore.财务数据.净利润 }}</div>
          </div>
          <div class="finance-item">
            <div class="finance-label">净利润同比</div>
            <div class="finance-value" :class="getGrowthClass(currentScore.财务数据.净利润同比)">
              {{ currentScore.财务数据.净利润同比 }}
            </div>
          </div>
          <div class="finance-item">
            <div class="finance-label">扣非净利润</div>
            <div class="finance-value">{{ currentScore.财务数据.扣非净利润 }}</div>
          </div>
          <div class="finance-item">
            <div class="finance-label">扣非净利润同比</div>
            <div class="finance-value" :class="getGrowthClass(currentScore.财务数据.扣非净利润同比)">
              {{ currentScore.财务数据.扣非净利润同比 }}
            </div>
          </div>
        </div>
      </div>

      <div class="card">
        <h3 style="margin-bottom: 16px; font-size: 17px; font-weight: 600;">季度得分趋势</h3>

        <!-- 图表状态提示 -->
        <!--
        评分说明：
        - 评分基于最近3个季度的同比增长率趋势计算
        - trend = 趋势分：反映增长率的变化趋势（连续上升/下降/反转等）
        - total = 基础分 + 趋势分
        - 本季度评分 = 基于 [上季, 上上季, 本季] 的3个季度趋势
      -->

        <div ref="chartRef" class="chart-container"></div>
      </div>

      <div class="card">
        <h3 style="margin-bottom: 16px; font-size: 17px; font-weight: 600;">趋势解读</h3>
        <div class="insight">
          <span class="insight-icon">📈</span>
          <span class="insight-text">{{ result.quarter_trends[activeQuarter]?.trend_text || '' }}</span>
        </div>
      </div>

      <div class="card">
        <h3 style="margin-bottom: 16px; font-size: 17px; font-weight: 600;">简要说明</h3>
        <div v-for="(insight, index) in result.quarter_insights[activeQuarter] || []" :key="index" class="insight">
          <span class="insight-icon">💡</span>
          <span class="insight-text">{{ insight }}</span>
        </div>
      </div>

      <div class="footer-link" @click="goToMainSystem">
        📊 进入多因子综合评分系统
      </div>

      <div class="icp-filing">
        <a href="https://beian.mps.gov.cn/#/query/webSearch?code=51019002009420" rel="noreferrer" target="_blank">
          <img src="@/assets/备案图标.png" style="vertical-align:middle;width:16px;height:16px;" /> 川公网安备51019002009420号</a>
           |
        <a href="https://beian.miit.gov.cn/" target="_blank">蜀ICP备2026019242号</a>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import * as echarts from 'echarts'

const route = useRoute()
const router = useRouter()

const activeTab = ref('')
const feedbackContent = ref('')
const feedbackSubmitted = ref(false)
const submitting = ref(false)
const feedbackMessage = ref(null)

const toggleTab = (tab) => {
  if (activeTab.value === tab) {
    activeTab.value = ''
  } else {
    activeTab.value = tab
  }
}

const chartRef = ref(null)
const chartInitialized = ref(false)
const loading = ref(false)
const error = ref('')
const result = ref(null)
const activeQuarter = ref('本季度')

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

// 监听季度切换，回到评分视图并重新加载K线
watch(activeQuarter, () => {
  showKline.value = false
  if (result.value) {
    loadKline()
  }
})

// 计算涨跌幅统计
const klineStats = computed(() => {
  if (!klineData.value?.kline?.length) return null
  const kline = klineData.value.kline
  const prevClose = klineData.value.prev_close
  if (kline.length < 1 || !prevClose) return null

  // 首日涨跌幅：(收盘价-昨日收盘价)/昨日收盘价*100
  const firstDay = kline[0]
  const firstDayChange = ((firstDay.close - prevClose) / prevClose * 100).toFixed(2)

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
    axisLabel: { color: '#666', fontSize: 11 },
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
    axisLabel: { color: '#666', fontSize: 11 }
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
    { left: 50, right: 15, top: 15, bottom: 40 }))
}

// 加载K线数据
const loadKline = async () => {
  if (!result.value) return
  klineLoading.value = true
  klineError.value = ''
  try {
    const response = await axios.get(`/api/v1/financial/kline/${result.value.code}`, {
      params: { quarter: activeQuarter.value }
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

const currentScore = computed(() => {
  if (!result.value) return { total: 0, 扣非: 0, 归母: 0, 营收: 0, report_date: '' }
  return result.value.scores[activeQuarter.value] || { total: 0, 扣非: 0, 归母: 0, 营收: 0, report_date: '' }
})

const scoreClass = computed(() => {
  const score = currentScore.value.total
  if (score >= 15) return 'excellent'
  if (score >= 5) return 'good'
  return 'poor'
})

const getScoreClass = (score, maxScore) => {
  if (score <= 0) return 'poor'  // 负分或零分=差（绿色）
  const ratio = score / maxScore
  if (ratio >= 0.7) return 'excellent'  // 高分=好（红色）
  if (ratio >= 0.3) return 'good'       // 中分=一般（橙色）
  return 'poor'  // 低分=差（绿色）
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return `${date.getFullYear()}-${(date.getMonth() + 1).toString().padStart(2, '0')}-${date.getDate().toString().padStart(2, '0')}`
}

const getGrowthClass = (growthStr) => {
  if (!growthStr) return ''
  const growth = parseFloat(growthStr.replace('%', ''))
  if (growth > 0) return 'growth-up'   // 上涨/增长 → 红色
  if (growth < 0) return 'growth-down' // 下跌/下降 → 绿色
  return ''
}

// 进度条浮动提示
const progressTip = ref({
  show: false,
  name: '',
  score: 0,
  max: 10,
  trend: 0,
  x: 0,
  y: 0
})

const showProgressTip = (name, score, trend, maxScore, e) => {
  progressTip.value = {
    show: true,
    name: name,
    score: score || 0,
    max: maxScore,
    trend: trend || 0,
    x: e.clientX,
    y: e.clientY - 100
  }
}

const toggleProgressTip = (name, score, trend, maxScore, e) => {
  // 如果当前显示的是同一个项目，则关闭
  if (progressTip.value.show && progressTip.value.name === name) {
    hideProgressTip()
  } else {
    showProgressTip(name, score, trend, maxScore, e)
  }
}

const hideProgressTip = () => {
  progressTip.value.show = false
}

const loadData = async () => {
  loading.value = true
  error.value = ''

  try {
    const code = route.params.code
    const response = await axios.get(`/api/v1/financial/score/${code}`)
    result.value = response.data

    await nextTick()
    setTimeout(initChart, 100)
    // 评分获取后立即加载K线数据
    loadKline()
  } catch (err) {
    console.error('Load error:', err)
    error.value = err.response?.data?.error || '加载失败'
  } finally {
    loading.value = false
  }
}

const initChart = () => {
  // 如果 chartRef 不存在（DOM还没渲染），等待后重试
  if (!chartRef.value) {
    setTimeout(initChart, 500)
    return
  }

  // 如果 result.value 存在但数据还没加载完成，也等待后重试
  if (!result.value || !result.value.scores) {
    setTimeout(initChart, 500)
    return
  }

    const chart = echarts.init(chartRef.value)

    // 季度名称和日期映射
  const quarters = ['上上季度', '上季度', '本季度']
  const quarterNames = [
    result.value.scores['上上季度']?.report_date || '上上季度',
    result.value.scores['上季度']?.report_date || '上季度',
    result.value.scores['本季度']?.report_date || '本季度'
  ]

  // 组合显示名称
  const quarterLabels = quarterNames.map((date, i) => {
    if (date.includes('-')) {
      return quarters[i] + '\n(' + date + ')'
    }
    return quarters[i]
  })

  // 总分数据
  const totalScores = [
    result.value.scores['上上季度']?.total || 0,
    result.value.scores['上季度']?.total || 0,
    result.value.scores['本季度']?.total || 0
  ]

  // 分项数据
  const koufeiScores = [
    result.value.scores['上上季度']?.扣非 || 0,
    result.value.scores['上季度']?.扣非 || 0,
    result.value.scores['本季度']?.扣非 || 0
  ]
  const guimuScores = [
    result.value.scores['上上季度']?.归母 || 0,
    result.value.scores['上季度']?.归母 || 0,
    result.value.scores['本季度']?.归母 || 0
  ]
  const yingshouScores = [
    result.value.scores['上上季度']?.营收 || 0,
    result.value.scores['上季度']?.营收 || 0,
    result.value.scores['本季度']?.营收 || 0
  ]

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(28,28,30,0.95)',
      borderColor: '#38383A',
      textStyle: { color: '#fff' },
      formatter: (params) => {
        // 获取当前季度的索引，映射到报告日期
        const quarterIndex = quarters.indexOf(params[0].name)
        const reportDates = [
          result.value.scores['上上季度']?.report_date || '',
          result.value.scores['上季度']?.report_date || '',
          result.value.scores['本季度']?.report_date || ''
        ]
        const titleWithDate = reportDates[quarterIndex]
          ? params[0].name + ' (' + reportDates[quarterIndex] + ')'
          : params[0].name

        let html = `<b>${titleWithDate}</b><br/>`
        params.forEach(p => {
          let value = p.value
          if (p.seriesName === '总分' || p.seriesName === '营业收入' || p.seriesName === '归母净利润' || p.seriesName === '扣非净利润') {
            value = value.toFixed(2) + '分'
          } else {
            value = value.toFixed(2)
          }
          html += `${p.seriesName}: <b>${value}</b><br/>`
        })
        return html
      }
    },
    legend: {
      data: ['总分', '营业收入', '归母净利润', '扣非净利润'],
      textStyle: { color: '#8E8E93', fontSize: 11 },
      bottom: 0,
      itemWidth: 12,
      itemHeight: 12
    },
    grid: {
      left: '8%',
      right: '8%',
      top: '8%',
      bottom: '30%'
    },
    xAxis: {
      type: 'category',
      data: quarters,
      axisLine: { lineStyle: { color: '#38383A' } },
      axisLabel: { color: '#8E8E93', fontSize: 13, fontWeight: 500 }
    },
    yAxis: {
      type: 'value',
      min: -10,
      max: 20,
      splitLine: { lineStyle: { color: '#2C2C2E' } },
      axisLabel: { color: '#8E8E93' }
    },
    series: [
      {
        name: '总分',
        data: totalScores,
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 10,
        lineStyle: { color: '#007AFF', width: 3 },
        itemStyle: { color: '#007AFF', borderColor: '#fff', borderWidth: 2 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(0,122,255,0.3)' },
            { offset: 1, color: 'rgba(0,122,255,0.05)' }
          ])
        }
      },
      {
        name: '营业收入',
        data: yingshouScores,
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 8,
        lineStyle: { color: '#34C759', width: 2 },
        itemStyle: { color: '#34C759' }
      },
      {
        name: '归母净利润',
        data: guimuScores,
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 8,
        lineStyle: { color: '#FF9500', width: 2 },
        itemStyle: { color: '#FF9500' }
      },
      {
        name: '扣非净利润',
        data: koufeiScores,
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 8,
        lineStyle: { color: '#FF3B30', width: 2 },
        itemStyle: { color: '#FF3B30' }
      }
    ]
  }

  chart.setOption(option)
  chartInitialized.value = true
  window.addEventListener('resize', () => chart.resize())
}

const goBack = () => {
  router.push('/')
}

const goToMainSystem = () => {
  window.open('https://auto-claw.top/reports', '_blank')
}

const submitFeedback = async () => {
  if (!feedbackContent.value.trim()) return

  submitting.value = true
  feedbackMessage.value = null

  try {
    const response = await fetch('/api/v1/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        content: feedbackContent.value,
        code: result.value?.code || '',
        name: result.value?.name || ''
      })
    })
    const data = await response.json()

    if (data.success) {
      feedbackSubmitted.value = true
      feedbackMessage.value = {
        type: 'success',
        text: data.message || '感谢您的反馈！'
      }
      feedbackContent.value = ''
    } else {
      throw new Error(data.error || '提交失败')
    }
  } catch (err) {
    feedbackMessage.value = {
      type: 'error',
      text: '提交失败，请稍后重试'
    }
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  loadData()
  // 点击其他地方关闭提示框
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})

const handleClickOutside = (e) => {
  // 如果提示框显示，且点击的不是提示框本身
  if (progressTip.value.show) {
    const tooltip = document.querySelector('.progress-tooltip')
    const progressItems = document.querySelectorAll('.progress-item')
    let clickedOnProgress = false
    progressItems.forEach(item => {
      if (item.contains(e.target)) {
        clickedOnProgress = true
      }
    })
    if (!clickedOnProgress && (!tooltip || !tooltip.contains(e.target))) {
      hideProgressTip()
    }
  }
}
</script>

<style scoped>
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

.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.tab-switch {
  display: flex;
  gap: 8px;
}

.tab-btn {
  padding: 8px 16px;
  border: 1px solid #38383A;
  background: #2C2C2E;
  color: #8E8E93;
  font-size: 14px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.tab-btn.active {
  background: #007AFF;
  border-color: #007AFF;
  color: #fff;
}

.tab-btn:hover:not(.active) {
  background: #3A3A3C;
  color: #fff;
}

.close-tab-btn {
  width: 100%;
  padding: 12px;
  margin-bottom: 16px;
  background: #2C2C2E;
  border: 1px solid #38383A;
  border-radius: 10px;
  color: #8E8E93;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.close-tab-btn:hover {
  background: #3A3A3C;
  color: #fff;
}

.info-card {
  background: #1C1C1E;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;
}

.info-title {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #38383A;
}

.info-section {
  margin-bottom: 20px;
}

.info-section:last-child {
  margin-bottom: 0;
}

.info-subtitle {
  font-size: 15px;
  font-weight: 600;
  color: #fff;
  margin-bottom: 12px;
}

.info-table {
  background: #2C2C2E;
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 8px;
}

.info-row {
  display: flex;
  padding: 10px 12px;
  font-size: 14px;
  border-bottom: 1px solid #38383A;
}

.info-row:last-child {
  border-bottom: none;
}

.info-row.header {
  background: #3A3A3C;
  color: #8E8E93;
  font-weight: 500;
}

.info-row span {
  flex: 1;
  text-align: center;
}

.info-row span:first-child {
  text-align: left;
}

.info-row span:last-child {
  text-align: right;
}

.info-note {
  font-size: 12px;
  color: #8E8E93;
  text-align: center;
  margin-top: 8px;
}

.info-text {
  font-size: 14px;
  color: #AEAEB2;
  line-height: 1.8;
}

.info-text p {
  margin-bottom: 8px;
}

.info-text p:last-child {
  margin-bottom: 0;
}

.feedback-form {
  margin: 16px 0;
}

.feedback-textarea {
  width: 100%;
  background: #2C2C2E;
  border: 1px solid #38383A;
  border-radius: 8px;
  padding: 12px;
  color: #fff;
  font-size: 14px;
  resize: none;
  font-family: inherit;
}

.feedback-textarea:focus {
  outline: none;
  border-color: #007AFF;
}

.feedback-textarea::placeholder {
  color: #8E8E93;
}

.feedback-actions {
  display: flex;
  gap: 12px;
  margin-top: 12px;
}

.feedback-btn {
  padding: 10px 20px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.feedback-btn.submit {
  background: #007AFF;
  color: #fff;
}

.feedback-btn.submit:disabled {
  background: #48484A;
  color: #8E8E93;
  cursor: not-allowed;
}

.feedback-btn.success {
  background: #34C759;
  color: #fff;
}

.feedback-message {
  margin-top: 12px;
  padding: 12px;
  border-radius: 8px;
  font-size: 14px;
  text-align: center;
}

.feedback-message.success {
  background: rgba(52, 199, 89, 0.15);
  color: #34C759;
}

.feedback-message.error {
  background: rgba(255, 59, 48, 0.15);
  color: #FF3B30;
}

.contact p {
  margin-bottom: 8px;
}

.result {
  margin-bottom: 40px;
  margin-top: 24px;
}

.progress-item {
  margin-bottom: 20px;
  cursor: pointer
}

.progress-item:last-child {
  margin-bottom: 0;
}

.progress-label {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 15px;
}

.progress-bar {
  height: 8px;
  background: #2C2C2E;
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.5s ease;
}

.progress-fill.excellent { background: #FF3B30; }  /* 高分=红色 */
.progress-fill.good { background: #FF9500; }
.progress-fill.poor { background: #34C759; }  /* 低分=绿色 */

/* 季度选项卡样式 */
.quarter-tabs {
  display: flex;
  background: #2C2C2E;
  border-radius: 12px;
  padding: 4px;
  margin-bottom: 20px;
}

.quarter-tab {
  flex: 1;
  padding: 12px 8px;
  border: none;
  background: transparent;
  color: #8E8E93;
  font-size: 15px;
  font-weight: 500;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  transition: all 0.2s ease;
}

.quarter-tab.active {
  background: #3A3A3C;
  color: #fff;
  font-weight: 600;
}

.quarter-date {
  font-size: 11px;
  color: #8E8E93;
  font-weight: 400;
}

.quarter-tab.active .quarter-date {
  color: #AEAEB2;
}

/* 财务数据样式 */
.finance-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.finance-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.finance-label {
  font-size: 13px;
  color: #8E8E93;
}

.finance-value {
  font-size: 16px;
  font-weight: 500;
  color: #fff;
}

.finance-value.growth-up {
  color: #FF3B30;  /* 上涨 → 红色 */
}

.finance-value.growth-down {
  color: #34C759;  /* 下跌 → 绿色 */
}

/* 进度条浮动提示 */
.progress-tooltip {
  position: fixed;
  background: rgba(30, 30, 30, 0.95);
  border: 1px solid #38383A;
  border-radius: 8px;
  padding: 12px;
  font-size: 13px;
  color: #fff;
  z-index: 1000;
  min-width: 140px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.progress-tooltip .tooltip-title {
  font-weight: 600;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid #38383A;
}

.progress-tooltip .tooltip-row {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
}

.progress-tooltip .tooltip-hint {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #38383A;
  font-size: 11px;
  color: #8E8E93;
  text-align: center;
}

.icp-filing {
  text-align: center;
  padding: 20px 0 30px;
  font-size: 12px;
  color: #8E8E93;
}

.icp-filing a {
  color: #8E8E93;
  text-decoration: none;
}

/* 评分卡片 - 与K线卡片同高 */
.score-card {
  min-height: 306px;
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

/* 切换按钮 */
.toggle-btn {
  margin-bottom: 16px;
}

/* K线相关样式 */
.kline-wrapper {
  height: 240px;
  display: flex;
  flex-direction: column;
  margin-top: 16px;
}

.kline-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
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
  margin-bottom: 16px;
}

.kline-loading,
.kline-error,
.kline-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #999;
  font-size: 14px;
}

.kline-error {
  color: #ff4d4f;
}

.kline-chart {
  width: 100%;
  height: 160px;
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
</style>