<template>
  <div class="signals-page">
    <h1 class="page-title">📡 信号监控</h1>

    <!-- 控制面板 -->
    <div class="control-panel">
      <div class="search-box">
        <input
          v-model="searchQuery"
          class="search-input"
          placeholder="搜索股票代码或名称..."
          @input="filterSignals"
        />
      </div>
      <div class="strategy-label">
        📡 {{ currentVersion }} - {{ strategyName }}
        <router-link to="/strategies" class="change-link">切换</router-link>
      </div>
      <div class="filter-buttons">
        <button
          class="btn"
          :class="filter === 'all' ? 'btn-primary' : 'btn-outline'"
          @click="setFilter('all')"
        >
          全部 ({{ totalCount }})
        </button>
        <button
          class="btn"
          :class="filter === 'buy' ? 'btn-primary' : 'btn-outline'"
          @click="setFilter('buy')"
        >
          买入信号 ({{ buyCount }})
        </button>
        <button
          class="btn"
          :class="filter === 'sell' ? 'btn-danger' : 'btn-outline'"
          @click="setFilter('sell')"
        >
          卖出信号 ({{ sellCount }})
        </button>
        <button
          class="btn"
          :class="filter === 'watch' ? 'btn-primary' : 'btn-outline'"
          @click="setFilter('watch')"
        >
          观望 ({{ watchCount }})
        </button>
      </div>
    </div>

    <!-- 信号统计 -->
    <div class="stats-row">
      <div class="stat-item">
        <span class="stat-num up">{{ buyCount }}</span>
        <span class="stat-desc">买入信号</span>
      </div>
      <div class="stat-item">
        <span class="stat-num">{{ watchCount }}</span>
        <span class="stat-desc">观望</span>
      </div>
      <div class="stat-item">
        <span class="stat-num highlight">{{ avgScore }}</span>
        <span class="stat-desc">平均7日均分</span>
      </div>
      <div class="stat-item">
        <span class="stat-num">{{ signalDate }}</span>
        <span class="stat-desc">信号日期</span>
      </div>
      <div class="stat-item" v-if="fromCache">
        <span class="stat-num cached">📦</span>
        <span class="stat-desc">已缓存（T-1 数据）</span>
      </div>
    </div>

    <!-- 信号列表 -->
    <div class="card">
      <div v-if="loading" class="loading">加载中...</div>
      <div v-else-if="filteredSignals.length === 0" class="empty">
        {{ searchQuery ? '没有找到匹配的股票' : '暂无信号数据' }}
      </div>
      <table v-else class="data-table">
        <thead>
          <tr>
            <th @click="sortBy('code')" class="sortable">
              代码 {{ sortField === 'code' ? (sortAsc ? '↑' : '↓') : '' }}
            </th>
            <th @click="sortBy('name')" class="sortable">
              名称 {{ sortField === 'name' ? (sortAsc ? '↑' : '↓') : '' }}
            </th>
            <th @click="sortBy('current_score')" class="sortable">
              当前评分 {{ sortField === 'current_score' ? (sortAsc ? '↑' : '↓') : '' }}
            </th>
            <th @click="sortBy('avg7_score')" class="sortable">
              7日均分 {{ sortField === 'avg7_score' ? (sortAsc ? '↑' : '↓') : '' }}
            </th>
            <th @click="sortBy('finance_score')" class="sortable">
              财报 {{ sortField === 'finance_score' ? (sortAsc ? '↑' : '↓') : '' }}
            </th>
            <th @click="sortBy('close_price')" class="sortable">
              收盘价 {{ sortField === 'close_price' ? (sortAsc ? '↑' : '↓') : '' }}
            </th>
            <th>信号</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in paginatedSignals" :key="item.code">
            <td class="code clickable" @click="gotoYujing(item.code)" title="点击查看个股详情">
              {{ item.code }}
            </td>
            <td class="name clickable" @click="gotoYujing(item.code)" title="点击查看个股详情">
              {{ item.name }}
            </td>
            <td>
              <span class="score-badge" :class="getScoreClass(item.current_score)">
                {{ item.current_score }}
              </span>
            </td>
            <td>
              <span class="score-badge avg" :class="getScoreClass(item.avg7_score)">
                {{ item.avg7_score }}
              </span>
            </td>
            <td>
              <span class="score-badge finance" :class="getFinanceClass(item.finance_score)">
                {{ item.finance_score ?? '-' }}
              </span>
            </td>
            <td class="price">{{ formatMoney(item.close_price) }}</td>
            <td>
              <span v-if="item.signal === 'BUY'" class="signal-badge buy">买入</span>
              <span v-else-if="item.signal === 'SELL'" class="signal-badge sell">卖出</span>
              <span v-else class="signal-badge watch">观望</span>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- 分页 -->
      <div v-if="totalPages > 1" class="pagination">
        <button
          class="btn btn-outline"
          :disabled="currentPage === 1"
          @click="currentPage--"
        >
          上一页
        </button>
        <span class="page-info">{{ currentPage }} / {{ totalPages }}</span>
        <button
          class="btn btn-outline"
          :disabled="currentPage === totalPages"
          @click="currentPage++"
        >
          下一页
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { loadSignals, loadStrategyVersions, getStrategyVersion, gotoYujing, formatMoney } from '../data/loader.js'

const loading = ref(true)
const signals = ref([])
const searchQuery = ref('')
const filter = ref('all')
const sortAsc = ref(false)
const currentPage = ref(1)
const pageSize = 50

const signalDate = ref('-')
const fromCache = ref(false)
const currentVersion = ref(getStrategyVersion())
const versions = ref([])
const strategyName = ref('')
// v2 按财报评分排序，v1 按 7 日均分排序
const sortField = ref(currentVersion.value === 'v2' ? 'finance_score' : 'avg7_score')

// 统计
const totalCount = computed(() => signals.value.length)
const buyCount = computed(() => signals.value.filter(s => s.signal === 'BUY').length)
const sellCount = computed(() => signals.value.filter(s => s.signal === 'SELL').length)
const watchCount = computed(() => totalCount.value - buyCount.value - sellCount.value)
const avgScore = computed(() => {
  if (signals.value.length === 0) return '-'
  const avg = signals.value.reduce((sum, s) => sum + Number(s.avg7_score), 0) / signals.value.length
  return avg.toFixed(1)
})

// 过滤和排序
const filteredSignals = computed(() => {
  let result = [...signals.value]

  // 搜索过滤
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    result = result.filter(s =>
      s.code.includes(q) || s.name.toLowerCase().includes(q)
    )
  }

  // 信号过滤
  if (filter.value === 'buy') {
    result = result.filter(s => s.signal === 'BUY')
  } else if (filter.value === 'sell') {
    result = result.filter(s => s.signal === 'SELL')
  } else if (filter.value === 'watch') {
    result = result.filter(s => s.signal !== 'BUY' && s.signal !== 'SELL')
  }

  // 排序
  result.sort((a, b) => {
    const field = sortField.value
    let va = a[field]
    let vb = b[field]

    // 数字字段转换（code/name 保持字符串比较）
    if (['current_score', 'avg7_score', 'finance_score', 'close_price'].includes(field)) {
      va = va === '-' || va == null ? -Infinity : Number(va)
      vb = vb === '-' || vb == null ? -Infinity : Number(vb)
    } else {
      va = String(va || '')
      vb = String(vb || '')
    }

    if (va < vb) return sortAsc.value ? -1 : 1
    if (va > vb) return sortAsc.value ? 1 : -1
    return 0
  })

  return result
})

// 分页
const totalPages = computed(() => Math.ceil(filteredSignals.value.length / pageSize))
const paginatedSignals = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return filteredSignals.value.slice(start, start + pageSize)
})

function setFilter(f) {
  filter.value = f
  currentPage.value = 1
}

function sortBy(field) {
  if (sortField.value === field) {
    sortAsc.value = !sortAsc.value
  } else {
    sortField.value = field
    sortAsc.value = false
  }
}

function getScoreClass(score) {
  const s = Number(score)
  if (s >= 60) return 'excellent'
  if (s >= 40) return 'good'
  if (s >= 20) return 'normal'
  return 'low'
}

function getFinanceClass(score) {
  if (score == null || score === '-') return 'low'
  const s = Number(score)
  if (s >= 15) return 'excellent'
  if (s >= 10) return 'good'
  if (s >= 5) return 'normal'
  return 'low'
}

onMounted(async () => {
  try {
    // 先取可用版本列表（下拉框渲染用）
    const verResp = await loadStrategyVersions()
    versions.value = verResp.versions || []
    strategyName.value = (versions.value.find(v => v.id === currentVersion.value) || {}).name || ''

    // 加载当前版本信号
    const signalsResp = await loadSignals(false, currentVersion.value)
    fromCache.value = false
    const list = signalsResp.data || []
    signals.value = list.map(s => ({
      code: s.code,
      name: s.name,
      close_price: Number(s.close_price),
      current_score: Number(s.current_score).toFixed(1),
      avg7_score: Number(s.avg7_score).toFixed(1),
      finance_score: s.finance_score != null ? Number(s.finance_score).toFixed(1) : '-',
      signal: s.signal
    }))

    if (list.length > 0 && list[0].date) {
      signalDate.value = list[0].date
    }
  } catch (e) {
    console.error('加载信号数据失败:', e)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.signals-page {
  max-width: 1200px;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  margin-bottom: 24px;
  background: linear-gradient(135deg, #00d4ff, #7b68ee);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

/* 控制面板 */
.control-panel {
  margin-bottom: 20px;
}

.search-box {
  margin-bottom: 12px;
}

.search-input {
  width: 100%;
  padding: 12px 16px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.05);
  color: #e0e0e0;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
}

.search-input:focus {
  border-color: #00d4ff;
}

.search-input::placeholder {
  color: #555;
}

.filter-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
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

/* 统计行 */
.stats-row {
  display: flex;
  gap: 24px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-num {
  font-size: 24px;
  font-weight: 700;
  color: #a0a0b0;
}

.stat-num.up {
  color: #ff4757;
}

.stat-num.highlight {
  background: linear-gradient(135deg, #00d4ff, #7b68ee);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.stat-desc {
  font-size: 12px;
  color: #666;
  margin-top: 4px;
}

/* 卡片 */
.card {
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  padding: 20px;
}

/* 表格 */
.data-table {
  width: 100%;
  border-collapse: collapse;
}

.data-table th {
  text-align: left;
  padding: 12px 16px;
  font-size: 12px;
  color: #666;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.sortable {
  cursor: pointer;
  user-select: none;
}

.sortable:hover {
  color: #00d4ff;
}

.data-table td {
  padding: 10px 16px;
  font-size: 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.data-table tr:hover {
  background: rgba(255, 255, 255, 0.03);
}

.code {
  font-family: monospace;
  color: #00d4ff;
}

.name {
  color: #e0e0e0;
}

.price {
  font-family: monospace;
  color: #a0a0b0;
}

/* 评分徽章 */
.score-badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 600;
  font-size: 13px;
}

.score-badge.excellent {
  background: rgba(255, 71, 87, 0.2);
  color: #ff4757;
}

.score-badge.good {
  background: rgba(255, 165, 0, 0.2);
  color: #ffa500;
}

.score-badge.normal {
  background: rgba(46, 213, 115, 0.2);
  color: #2ed573;
}

.score-badge.low {
  background: rgba(160, 160, 176, 0.2);
  color: #a0a0b0;
}

/* 信号徽章 */
.signal-badge {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.signal-badge.buy {
  background: rgba(255, 71, 87, 0.2);
  color: #ff4757;
}

.signal-badge.sell {
  background: rgba(255, 165, 0, 0.2);
  color: #ffa500;
}

.signal-badge.watch {
  background: rgba(160, 160, 176, 0.2);
  color: #a0a0b0;
}

.btn-danger {
  background: rgba(255, 71, 87, 0.15);
  color: #ff4757;
  border: 1px solid rgba(255, 71, 87, 0.3);
}

/* 分页 */
.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  margin-top: 20px;
}

.page-info {
  color: #666;
  font-size: 14px;
}

/* 按钮 */
.btn {
  padding: 8px 16px;
  border-radius: 8px;
  border: none;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-primary {
  background: linear-gradient(135deg, #00d4ff, #7b68ee);
  color: #fff;
}

.btn-primary:hover {
  opacity: 0.9;
}

.btn-outline {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: #a0a0b0;
}

.btn-outline:hover {
  border-color: #00d4ff;
  color: #00d4ff;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 加载和空状态 */
.loading, .empty {
  text-align: center;
  padding: 40px;
  color: #666;
}

@media (max-width: 768px) {
  .stats-row {
    gap: 16px;
  }

  .stat-num {
    font-size: 18px;
  }

  .data-table th,
  .data-table td {
    padding: 8px;
    font-size: 12px;
  }
}
</style>
