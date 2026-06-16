<template>
  <div class="stats-page">
    <h1 class="page-title">📊 收益统计</h1>

    <!-- Tabs 切换 -->
    <div class="tabs-bar">
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'SIM' }"
        @click="activeTab = 'SIM'"
      >
        <span class="tab-icon">🎲</span>
        <span>模拟仓</span>
      </button>
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'REAL' }"
        @click="activeTab = 'REAL'"
      >
        <span class="tab-icon">💰</span>
        <span>实盘</span>
      </button>
    </div>

    <!-- 总览统计 -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon">💰</div>
        <div class="stat-info">
          <div class="stat-value" :class="getChangeClass(stats.total_assets - stats.initial_capital)">
            {{ formatMoney(stats.total_assets || stats.initial_capital) }}
          </div>
          <div class="stat-label">当前资产</div>
          <div class="stat-sub">初始资金 {{ formatMoney(stats.initial_capital) }}</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">📈</div>
        <div class="stat-info">
          <div class="stat-value" :class="getChangeClass(stats.total_return)">
            {{ formatPercent(stats.total_return) }}
          </div>
          <div class="stat-label">总收益率</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">📊</div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.win_rate ? stats.win_rate.toFixed(1) + '%' : '-' }}</div>
          <div class="stat-label">胜率</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">📉</div>
        <div class="stat-info">
          <div class="stat-value down">{{ formatPercent(-maxDrawdown) }}</div>
          <div class="stat-label">最大回撤</div>
        </div>
      </div>
    </div>

    <!-- 收益曲线图 -->
    <div class="card">
      <div class="card-title">
        <span>📈</span>
        <span>收益曲线（{{ activeTab === 'SIM' ? '模拟仓' : '实盘' }}）</span>
        <span v-if="!hasData" class="hint">（暂无数据）</span>
      </div>
      <div ref="chartRef" class="chart-container"></div>
      <div v-if="!hasData" class="empty-state">
        <p>暂无{{ activeTab === 'SIM' ? '模拟仓' : '实盘' }}交易数据</p>
        <p class="hint-text">
          {{ activeTab === 'SIM'
            ? '模拟仓每日 19:00 由系统自动根据信号交易'
            : '请在「持仓管理」录入实盘交易后，曲线才会显示' }}
        </p>
      </div>
    </div>

    <!-- 交易统计 -->
    <div class="stats-row">
      <div class="card flex-1">
        <div class="card-title">
          <span>📋</span>
          <span>交易统计</span>
        </div>
        <div class="stat-list">
          <div class="stat-row">
            <span class="stat-label">总交易次数</span>
            <span class="stat-val">{{ stats.total_trades || 0 }}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">买入次数</span>
            <span class="stat-val up">{{ stats.buy_count || 0 }}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">卖出次数</span>
            <span class="stat-val down">{{ stats.sell_count || 0 }}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">盈利次数</span>
            <span class="stat-val up">{{ stats.win_count || 0 }}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">亏损次数</span>
            <span class="stat-val down">{{ stats.loss_count || 0 }}</span>
          </div>
        </div>
      </div>

      <div class="card flex-1">
        <div class="card-title">
          <span>💰</span>
          <span>盈亏分析</span>
        </div>
        <div class="stat-list">
          <div class="stat-row">
            <span class="stat-label">平均盈利</span>
            <span class="stat-val up">{{ formatPercent(stats.avg_win) }}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">平均亏损</span>
            <span class="stat-val down">{{ formatPercent(stats.avg_loss) }}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">最大单笔盈利</span>
            <span class="stat-val up">{{ formatPercent(stats.max_win) }}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">最大单笔亏损</span>
            <span class="stat-val down">{{ formatPercent(stats.max_loss) }}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">盈亏比</span>
            <span class="stat-val">{{ profitLossRatio }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 最近交易 -->
    <div class="card">
      <div class="card-title">
        <span>📝</span>
        <span>最近{{ activeTab === 'SIM' ? '模拟' : '实盘' }}交易记录</span>
      </div>
      <div v-if="trades.length === 0" class="empty">暂无{{ activeTab === 'SIM' ? '模拟' : '实盘' }}交易记录</div>
      <table v-else class="data-table">
        <thead>
          <tr>
            <th>日期</th>
            <th>类型</th>
            <th>代码</th>
            <th>名称</th>
            <th>价格</th>
            <th>数量</th>
            <th>金额</th>
            <th>费用</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="trade in trades" :key="trade.id">
            <td>{{ trade.trade_date }}</td>
            <td>
              <span :class="trade.type === 'BUY' ? 'up' : 'down'">
                {{ trade.type === 'BUY' ? '买入' : '卖出' }}
              </span>
            </td>
            <td class="code">{{ trade.code }}</td>
            <td>{{ trade.name }}</td>
            <td>{{ formatMoney(trade.price) }}</td>
            <td>{{ trade.shares }}</td>
            <td>{{ formatMoney(trade.amount) }}</td>
            <td>{{ formatMoney(trade.fee + (trade.stamp_tax || 0)) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import * as echarts from 'echarts'
import { loadStats, loadTrades, loadNavHistory, formatNumber, formatMoney, formatPercent, getChangeClass } from '../data/loader.js'

const activeTab = ref('SIM')

const stats = ref({})
const trades = ref([])
const navHistory = ref([])
const maxDrawdown = ref(0)
const chartRef = ref(null)
const hasData = ref(false)
let chart = null

const profitLossRatio = computed(() => {
  const win = Number(stats.value.avg_win) || 0
  const loss = Math.abs(Number(stats.value.avg_loss) || 0)
  if (loss === 0) return win > 0 ? '∞' : '-'
  return (win / loss).toFixed(2)
})

function initChart() {
  if (!chartRef.value) return
  if (chart) chart.dispose()
  chart = echarts.init(chartRef.value)

  if (navHistory.value.length === 0) {
    hasData.value = false
    return
  }
  hasData.value = true

  const dates = navHistory.value.map(n => n.date)
  const navs = navHistory.value.map(n => n.nav)
  const assets = navHistory.value.map(n => n.total_assets)

  let peak = navs[0]
  let maxDd = 0
  for (const n of navs) {
    if (n > peak) peak = n
    const dd = (peak - n) / peak
    if (dd > maxDd) maxDd = dd
  }
  maxDrawdown.value = maxDd * 100

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(26, 26, 46, 0.95)',
      borderColor: 'rgba(255, 255, 255, 0.1)',
      textStyle: { color: '#e0e0e0' },
      formatter: function (params) {
        const p = params[0]
        const a = params[1]
        return `${p.axisValue}<br/>净值: ${p.value.toFixed(4)}<br/>资产: ¥${Number(a.value).toLocaleString()}`
      }
    },
    legend: {
      data: ['净值曲线', '总资产'],
      textStyle: { color: '#a0a0b0' }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.1)' } },
      axisLabel: { color: '#666' }
    },
    yAxis: [
      {
        type: 'value',
        name: '净值',
        axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.1)' } },
        axisLabel: {
          color: '#666',
          formatter: function (val) { return val.toFixed(2) }
        },
        splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } }
      },
      {
        type: 'value',
        name: '资产',
        position: 'right',
        axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.1)' } },
        axisLabel: {
          color: '#666',
          formatter: function (val) { return (val / 10000).toFixed(0) + '万' }
        },
        splitLine: { show: false }
      }
    ],
    series: [
      {
        name: '净值曲线',
        data: navs,
        type: 'line',
        smooth: true,
        symbol: 'none',
        yAxisIndex: 0,
        lineStyle: { color: '#00d4ff', width: 2 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(0, 212, 255, 0.3)' },
            { offset: 1, color: 'rgba(0, 212, 255, 0)' }
          ])
        }
      },
      {
        name: '总资产',
        data: assets,
        type: 'line',
        smooth: true,
        symbol: 'none',
        yAxisIndex: 1,
        lineStyle: { color: '#ffa500', width: 1, type: 'dashed' }
      }
    ]
  }
  chart.setOption(option)
}

async function fetchData() {
  const mode = activeTab.value
  const [statData, tradeList, navs] = await Promise.all([
    loadStats(mode, false),
    loadTrades(mode, 20, false),
    loadNavHistory(mode, null, null, false)
  ])
  stats.value = statData || {}
  trades.value = tradeList || []
  navHistory.value = navs || []
  await nextTick()
  initChart()
}

watch(activeTab, () => {
  fetchData()
})

onMounted(async () => {
  await fetchData()

  window.addEventListener('resize', () => {
    if (chart) chart.resize()
  })
})
</script>

<style scoped>
.stats-page { max-width: 1200px; }

.page-title {
  font-size: 24px;
  font-weight: 700;
  margin-bottom: 16px;
  background: linear-gradient(135deg, #00d4ff, #7b68ee);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

/* Tabs */
.tabs-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.tab-btn {
  background: none;
  border: none;
  padding: 12px 20px;
  font-size: 14px;
  color: #a0a0b0;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}

.tab-btn:hover { color: #e0e0e0; }
.tab-btn.active { color: #00d4ff; border-bottom-color: #00d4ff; }
.tab-icon { font-size: 18px; }

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-icon { font-size: 32px; }
.stat-info { flex: 1; }

.stat-value {
  font-size: 24px;
  font-weight: 700;
  background: linear-gradient(135deg, #00d4ff, #7b68ee);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.stat-value.up {
  background: linear-gradient(135deg, #ff4757, #ff6b81);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.stat-value.down {
  background: linear-gradient(135deg, #2ed573, #7bed9f);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.stat-label { font-size: 12px; color: #666; margin-top: 4px; }
.stat-sub { font-size: 11px; color: #555; margin-top: 2px; }

.card {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  padding: 20px;
  margin-bottom: 16px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: #a0a0b0;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-title .hint {
  font-size: 12px;
  color: #666;
  font-weight: normal;
  margin-left: 8px;
}

.chart-container { width: 100%; height: 320px; }

.empty-state {
  text-align: center;
  padding: 20px;
  color: #666;
  font-size: 13px;
}

.empty-state p { margin: 4px 0; }
.empty-state .hint-text { color: #888; font-size: 12px; margin-top: 8px; }

.stats-row {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
}

.flex-1 { flex: 1; }

.stat-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.stat-label { color: #666; font-size: 14px; }
.stat-val { font-weight: 600; font-size: 14px; color: #e0e0e0; }
.stat-val.up { color: #ff4757; }
.stat-val.down { color: #2ed573; }

.data-table { width: 100%; border-collapse: collapse; }
.data-table th {
  text-align: left;
  padding: 12px 16px;
  font-size: 12px;
  color: #666;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.data-table td {
  padding: 10px 16px;
  font-size: 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.data-table tr:hover { background: rgba(255, 255, 255, 0.03); }
.code { font-family: monospace; color: #00d4ff; }
.up { color: #ff4757; }
.down { color: #2ed573; }

.empty { text-align: center; padding: 40px; color: #666; }

@media (max-width: 768px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
  .stats-row { flex-direction: column; }
  .stat-value { font-size: 18px; }
  .data-table th, .data-table td { padding: 8px; font-size: 12px; }
}
</style>
