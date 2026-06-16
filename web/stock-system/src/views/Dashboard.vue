<template>
  <div class="dashboard">
    <div class="dashboard-header">
      <h1 class="page-title">📊 股票操作系统</h1>
      <div class="strategy-label">
        📡 {{ currentVersion }} - {{ strategyName }}
        <router-link to="/strategies" class="change-link">切换</router-link>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon">📡</div>
        <div class="stat-info">
          <div class="stat-value">{{ signalCount }}</div>
          <div class="stat-label">今日买入信号</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">🎯</div>
        <div class="stat-info">
          <div class="stat-value">{{ stockCount }}</div>
          <div class="stat-label">自选股数</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">⭐</div>
        <div class="stat-info">
          <div class="stat-value">{{ topScore }}</div>
          <div class="stat-label">最高评分</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">📅</div>
        <div class="stat-info">
          <div class="stat-value">{{ formatDateDisplay(latestDate) }}</div>
          <div class="stat-label">最新数据日期</div>
        </div>
      </div>
    </div>

    <!-- 今日信号列表 -->
    <div class="card">
      <div class="card-title">
        <span>🎯</span>
        <span>今日买入信号 (Top 20)</span>
        <router-link to="/signals" class="view-all">查看全部 →</router-link>
      </div>
      <div v-if="loading" class="loading">加载中...</div>
      <div v-else-if="topSignals.length === 0" class="empty">暂无买入信号</div>
      <table v-else class="data-table">
        <thead>
          <tr>
            <th>排名</th>
            <th>代码</th>
            <th>名称</th>
            <th>当前评分</th>
            <th>7日均分</th>
            <th>收盘价</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(item, idx) in topSignals" :key="item.code">
            <td class="rank">{{ idx + 1 }}</td>
            <td class="code clickable" @click="gotoYujing(item.code)" title="点击查看个股详情">
              {{ item.code }}
            </td>
            <td class="name clickable" @click="gotoYujing(item.code)" title="点击查看个股详情">
              {{ item.name }}
            </td>
            <td>
              <span class="score" :class="getScoreClass(item.current_score)">
                {{ item.current_score }}
              </span>
            </td>
            <td>
              <span class="score avg" :class="getScoreClass(item.avg7_score)">
                {{ item.avg7_score }}
              </span>
            </td>
            <td class="price">{{ formatMoney(item.close_price) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 最新评分 Top 10（自选股内） -->
    <div class="card">
      <div class="card-title">
        <span>🏆</span>
        <span>自选股最新评分 Top 10</span>
      </div>
      <div v-if="loading" class="loading">加载中...</div>
      <div v-else-if="topScores.length === 0" class="empty">暂无评分数据</div>
      <table v-else class="data-table">
        <thead>
          <tr>
            <th>排名</th>
            <th>代码</th>
            <th>名称</th>
            <th>7日均分</th>
            <th>当前评分</th>
            <th>收盘价</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(item, idx) in topScores" :key="item.code">
            <td class="rank">{{ idx + 1 }}</td>
            <td class="code clickable" @click="gotoYujing(item.code)" title="点击查看个股详情">
              {{ item.code }}
            </td>
            <td class="name clickable" @click="gotoYujing(item.code)" title="点击查看个股详情">
              {{ item.name }}
            </td>
            <td>
              <span class="score total" :class="getScoreClass(item.avg7_score)">
                {{ item.avg7_score }}
              </span>
            </td>
            <td>{{ formatNumber(item.current_score) }}</td>
            <td class="price">{{ formatMoney(item.close_price) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { loadSignals, loadStrategyVersions, getStrategyVersion, formatNumber, formatMoney, clearAllCache, gotoYujing } from '../data/loader.js'

const loading = ref(true)
const signalCount = ref(0)
const stockCount = ref(0)
const topScore = ref(0)
const latestDate = ref('')
const topSignals = ref([])
const topScores = ref([])
const currentVersion = ref(getStrategyVersion())
const versions = ref([])
const strategyName = ref('')

function getScoreClass(score) {
  const s = Number(score)
  if (s >= 60) return 'excellent'
  if (s >= 40) return 'good'
  if (s >= 20) return 'normal'
  return 'low'
}

// YYYYMMDD → YYYY-MM-DD 显示
function formatDateDisplay(date) {
  if (!date || date === '-') return '-'
  const s = String(date)
  if (s.length === 8) {
    return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`
  }
  return s
}

onMounted(async () => {
  clearAllCache()
  try {
    // 先取可用版本
    const verResp = await loadStrategyVersions()
    versions.value = verResp.versions || []
    strategyName.value = (versions.value.find(v => v.id === currentVersion.value) || {}).name || ''

    const signalsResp = await loadSignals(false, currentVersion.value)
    const signalsList = signalsResp.data || []

    // 1. 统计
    latestDate.value = signalsResp.date || ''
    stockCount.value = signalsList.length

    // 2. 买入信号
    const buySignals = signalsList.filter(s => s.signal === 'BUY')
    signalCount.value = buySignals.length
    topSignals.value = buySignals.slice(0, 20).map(s => ({
      code: s.code,
      name: s.name,
      current_score: Number(s.current_score).toFixed(1),
      avg7_score: Number(s.avg7_score).toFixed(1),
      close_price: Number(s.close_price)
    }))

    // 3. 自选股评分 Top 10（按 7 日均分排序）
    const sorted = signalsList
      .filter(s => s.avg7_score && !isNaN(Number(s.avg7_score)))
      .sort((a, b) => Number(b.avg7_score) - Number(a.avg7_score))

    if (sorted.length > 0) {
      topScore.value = Number(sorted[0].avg7_score).toFixed(1)
    }

    topScores.value = sorted.slice(0, 10).map(s => ({
      code: s.code,
      name: s.name,
      avg7_score: Number(s.avg7_score).toFixed(1),
      current_score: Number(s.current_score || 0).toFixed(1),
      close_price: Number(s.close_price)
    }))
  } catch (e) {
    console.error('加载数据失败:', e)
  } finally {
    loading.value = false
  }
})

</script>

<style scoped>
.dashboard { max-width: 1200px; }

.dashboard-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 16px;
}

.strategy-label {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #a0a0b0;
  font-size: 13px;
}

.change-link {
  color: #7b68ee;
  font-size: 12px;
  text-decoration: none;
}

.change-link:hover {
  text-decoration: underline;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  margin-bottom: 24px;
  background: linear-gradient(135deg, #00d4ff, #7b68ee);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

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
  font-size: 28px;
  font-weight: 700;
  background: linear-gradient(135deg, #00d4ff, #7b68ee);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.stat-label { font-size: 12px; color: #666; margin-top: 4px; }

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

.view-all {
  margin-left: auto;
  font-size: 13px;
  color: #00d4ff;
  text-decoration: none;
}

.view-all:hover { text-decoration: underline; }

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

.rank { color: #666; font-size: 12px; }
.code { font-family: monospace; color: #00d4ff; }
.name { color: #e0e0e0; }
.clickable { cursor: pointer; }
.clickable:hover { color: #00d4ff; text-decoration: underline; }
.price { font-family: monospace; color: #a0a0b0; }

.score {
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 600;
}

.score.excellent { background: rgba(255, 71, 87, 0.2); color: #ff4757; }
.score.good { background: rgba(255, 165, 0, 0.2); color: #ffa500; }
.score.normal { background: rgba(46, 213, 115, 0.2); color: #2ed573; }
.score.low { background: rgba(160, 160, 176, 0.2); color: #a0a0b0; }
.score.total {
  background: linear-gradient(135deg, rgba(0, 212, 255, 0.2), rgba(123, 104, 238, 0.2));
  color: #00d4ff;
}
.score.avg { font-size: 12px; }

.loading, .empty {
  text-align: center;
  padding: 40px;
  color: #666;
}

@media (max-width: 768px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
  .stat-value { font-size: 20px; }
  .data-table th, .data-table td { padding: 8px; font-size: 12px; }
}
</style>
