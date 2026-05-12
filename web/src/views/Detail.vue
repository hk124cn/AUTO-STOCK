<template>
  <div class="container">
    <button class="back-btn" @click="goBack">
      ← 返回
    </button>

    <div v-if="loading" class="loading">
      <div class="spinner"></div>
      <span>正在加载...</span>
    </div>

    <div v-if="error" class="error">
      {{ error }}
    </div>

    <div v-if="result && !loading" class="result">
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

      <div class="card">
        <div class="stock-info">
          <div class="stock-code">{{ result.code }}</div>
          <div class="stock-name">{{ result.name }}</div>
        </div>

        <div class="score-large">
          <div class="score-number" :class="scoreClass">
            {{ currentScore.total }}
          </div>
          <div class="score-label">{{ activeQuarter }}评分</div>
          <div class="score-max">满分 20</div>
          <div class="updated-time">更新于 {{ result.updated_at }}</div>
        </div>
      </div>

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
        <a href="https://beian.miit.gov.cn/" target="_blank">蜀ICP备2026019242号</a>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import * as echarts from 'echarts'

const route = useRoute()
const router = useRouter()

const chartRef = ref(null)
const chartInitialized = ref(false)
const loading = ref(false)
const error = ref('')
const result = ref(null)
const activeQuarter = ref('本季度')

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
  alert('多因子综合评分系统开发中...')
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
.result {
  margin-bottom: 40px;
}

.progress-item {
  margin-bottom: 20px;
  cursor: pointer;
  position: relative;
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

</style>