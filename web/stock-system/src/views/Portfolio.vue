<template>
  <div class="portfolio-page">
    <h1 class="page-title">💼 持仓管理</h1>

    <!-- Tabs 切换 -->
    <div class="tabs-bar">
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'SIM' }"
        @click="activeTab = 'SIM'"
      >
        <span class="tab-icon">🎲</span>
        <span>模拟仓（系统自动）</span>
        <span class="tab-badge" v-if="cacheInfo.sim">已缓存</span>
      </button>
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'REAL' }"
        @click="activeTab = 'REAL'"
      >
        <span class="tab-icon">💰</span>
        <span>实盘（手动录入）</span>
        <span class="tab-badge" v-if="cacheInfo.real">已缓存</span>
      </button>
    </div>

    <!-- 持仓概览 -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon">💰</div>
        <div class="stat-info">
          <div class="stat-value">{{ formatMoney(stats.total_assets) }}</div>
          <div class="stat-label">总资产</div>
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
        <div class="stat-icon">🏦</div>
        <div class="stat-info">
          <div class="stat-value">{{ stats.position_count || 0 }}</div>
          <div class="stat-label">持仓数量</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">💵</div>
        <div class="stat-info">
          <div class="stat-value">{{ formatMoney(stats.current_capital) }}</div>
          <div class="stat-label">可用资金</div>
        </div>
      </div>
    </div>

    <!-- 操作按钮 -->
    <div class="action-bar">
      <button class="btn btn-primary" @click="openBuyModal">
        ➕ 记录{{ activeTab === 'SIM' ? '模拟' : '实盘' }}买入
      </button>
      <button class="btn btn-outline" :disabled="refreshing" @click="refreshPrices">
        {{ refreshing ? '刷新中...' : '🔄 刷新价格' }}
      </button>
      <button class="btn btn-outline" @click="openCapitalModal">
        💰 修改总资产
      </button>
      <span class="cache-info" v-if="lastUpdate">
        上次更新: {{ lastUpdate }} · {{ cacheNote }}
      </span>
    </div>

    <!-- 错误提示 -->
    <div v-if="errorMsg" class="error-banner">
      ⚠️ {{ errorMsg }}
      <button class="btn-close" @click="errorMsg = ''">✕</button>
    </div>

    <!-- 模拟仓说明 -->
    <div v-if="activeTab === 'SIM'" class="info-banner">
      ℹ️ 模拟仓由系统每日根据信号自动交易（晚间流水线 19:00 执行）。止盈 20%，止损 8%，单股最大仓位 20%。
    </div>
    <div v-else class="info-banner real">
      ℹ️ 实盘用于记录您真实券商账户的交易。资金独立于模拟仓，请手动录入实际成交。
    </div>

    <!-- 持仓列表 -->
    <div class="card">
      <div class="card-title">
        <span>📋</span>
        <span>{{ activeTab === 'SIM' ? '模拟仓' : '实盘' }}当前持仓</span>
      </div>
      <div v-if="loading" class="loading">加载中...</div>
      <div v-else-if="positions.length === 0" class="empty">
        暂无{{ activeTab === 'SIM' ? '模拟' : '实盘' }}持仓
      </div>
      <table v-else class="data-table">
        <thead>
          <tr>
            <th>代码</th>
            <th>名称</th>
            <th>持仓数量</th>
            <th>成本价</th>
            <th>现价</th>
            <th>盈亏金额</th>
            <th>收益率</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="pos in positions" :key="pos.code">
            <td class="code" @click="gotoYujingWithPosition(pos.code)" title="点击查看个股详情（含成本价/止盈/止损）">
              {{ pos.code }}
            </td>
            <td class="name clickable" @click="gotoYujingWithPosition(pos.code)" title="点击查看个股详情（含成本价/止盈/止损）">
              {{ pos.name }}
            </td>
            <td>{{ pos.shares }}</td>
            <td>{{ formatMoney(pos.cost_price) }}</td>
            <td>{{ formatMoney(pos.current_price) }}</td>
            <td :class="getChangeClass(pos.profit)">
              {{ formatMoney(pos.profit) }}
            </td>
            <td :class="getChangeClass(pos.profit_rate)">
              {{ formatPercent(pos.profit_rate) }}
            </td>
            <td>
              <button class="btn btn-sm btn-danger" @click="openSellModal(pos)">
                卖出
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 交易记录 -->
    <div class="card">
      <div class="card-title">
        <span>📝</span>
        <span>最近{{ activeTab === 'SIM' ? '模拟' : '实盘' }}交易记录</span>
      </div>
      <div v-if="trades.length === 0" class="empty">
        暂无{{ activeTab === 'SIM' ? '模拟' : '实盘' }}交易记录
      </div>
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
            <th>操作</th>
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
            <td class="code" @click="gotoYujingWithPosition(trade.code)" title="点击查看个股详情">
              {{ trade.code }}
            </td>
            <td class="clickable" @click="gotoYujingWithPosition(trade.code)" title="点击查看个股详情">
              {{ trade.name }}
            </td>
            <td>{{ formatMoney(trade.price) }}</td>
            <td>{{ trade.shares }}</td>
            <td>{{ formatMoney(trade.amount) }}</td>
            <td>{{ formatMoney(trade.fee + (trade.stamp_tax || 0)) }}</td>
            <td>
              <button
                class="btn btn-sm btn-outline"
                @click="deleteTradeConfirm(trade)"
                :disabled="deletingTrade === trade.id"
                title="删除该交易记录"
              >
                {{ deletingTrade === trade.id ? '删除中...' : '🗑' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 买入弹窗 -->
    <div v-if="showBuyModal" class="modal-overlay" @click.self="closeBuyModal">
      <div class="modal">
        <div class="modal-header">
          <h3>记录{{ activeTab === 'SIM' ? '模拟' : '实盘' }}买入</h3>
          <button class="btn-close" @click="closeBuyModal">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>股票代码</label>
            <input
              v-model="buyForm.code"
              placeholder="如 600519"
              maxlength="6"
              @input="validateBuyForm"
            />
          </div>
          <div class="form-group">
            <label>股票名称</label>
            <input v-model="buyForm.name" placeholder="如 贵州茅台" />
          </div>
          <div class="form-group">
            <label>买入价格</label>
            <input
              v-model="buyForm.price"
              type="number"
              step="0.01"
              min="0.01"
              placeholder="买入价格"
              @input="validateBuyForm"
            />
          </div>
          <div class="form-group">
            <label>买入数量（A 股必须为 100 整数倍）</label>
            <input
              v-model="buyForm.shares"
              type="number"
              min="100"
              step="100"
              placeholder="买入数量（股）"
              @input="validateBuyForm"
            />
          </div>
          <div class="form-group">
            <label>评分（可选）</label>
            <input v-model="buyForm.score" type="number" step="0.1" placeholder="评分" />
          </div>
          <div class="form-group">
            <label>买入原因（可选）</label>
            <input v-model="buyForm.reason" placeholder="买入原因" />
          </div>
          <div v-if="buyValidationError" class="form-error">⚠️ {{ buyValidationError }}</div>
          <div v-if="buyFormTotal" class="form-info">
            预计金额: {{ formatMoney(buyFormTotal) }}（含手续费 {{ formatMoney(buyFormFee) }}）
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-outline" @click="closeBuyModal">取消</button>
          <button class="btn btn-primary" :disabled="!isBuyValid || submitting" @click="confirmBuy">
            {{ submitting ? '提交中...' : '确认买入' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 卖出弹窗 -->
    <div v-if="showSellModal" class="modal-overlay" @click.self="showSellModal = false">
      <div class="modal">
        <div class="modal-header">
          <h3>记录{{ activeTab === 'SIM' ? '模拟' : '实盘' }}卖出 - {{ sellPos?.name }} ({{ sellPos?.code }})</h3>
          <button class="btn-close" @click="showSellModal = false">✕</button>
        </div>
        <div class="modal-body">
          <div v-if="sellPos" class="info-row">
            <span>当前持仓:</span>
            <strong>{{ sellPos.shares }} 股</strong>
            <span class="sep">|</span>
            <span>成本价:</span>
            <strong>{{ formatMoney(sellPos.cost_price) }}</strong>
          </div>
          <div class="form-group">
            <label>卖出价格</label>
            <input
              v-model="sellForm.price"
              type="number"
              step="0.01"
              min="0.01"
              placeholder="卖出价格"
              @input="validateSellForm"
            />
          </div>
          <div class="form-group">
            <label>卖出数量（A 股必须为 100 整数倍）</label>
            <input
              v-model="sellForm.shares"
              type="number"
              min="100"
              step="100"
              :max="sellPos?.shares"
              placeholder="卖出数量"
              @input="validateSellForm"
            />
          </div>
          <div class="form-group">
            <label>卖出原因（可选）</label>
            <input v-model="sellForm.reason" placeholder="如：止盈/止损" />
          </div>
          <div v-if="sellValidationError" class="form-error">⚠️ {{ sellValidationError }}</div>
          <div v-if="sellFormEstimate" class="form-info">{{ sellFormEstimate }}</div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-outline" @click="showSellModal = false">取消</button>
          <button class="btn btn-danger" :disabled="!isSellValid || submitting" @click="confirmSell">
            {{ submitting ? '提交中...' : '确认卖出' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 修改总资产弹窗 -->
    <div v-if="showCapitalModal" class="modal-overlay" @click.self="showCapitalModal = false">
      <div class="modal">
        <div class="modal-header">
          <h3>修改{{ activeTab === 'SIM' ? '模拟仓' : '实盘' }}总资产</h3>
          <button class="btn-close" @click="showCapitalModal = false">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>当前总资产: {{ formatMoney(stats.total_assets) }}</label>
          </div>
          <div class="form-group">
            <label>新的初始资金</label>
            <input
              v-model="capitalForm.amount"
              type="number"
              step="10000"
              min="0"
              placeholder="如 1000000"
            />
            <div class="form-hint">
              ⚠️ 修改初始资金会<strong>重置整个账户</strong>（清空所有持仓、交易记录、净值快照）。仅用于调整模拟仓规模或重新开始。
            </div>
          </div>
          <div v-if="capitalError" class="form-error">⚠️ {{ capitalError }}</div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-outline" @click="showCapitalModal = false">取消</button>
          <button class="btn btn-danger" :disabled="!capitalValid || submitting" @click="confirmUpdateCapital">
            {{ submitting ? '提交中...' : '确认重置' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch, onUnmounted } from 'vue'
import {
  loadAccount, loadPositions, loadTrades, loadStats,
  buyStock, sellStock, updatePrices,
  formatNumber, formatMoney, formatPercent, getChangeClass, gotoYujing
} from '../data/loader.js'
import { loadStrategy } from '../data/strategy.js'
import { getMarketState, getCacheTTL } from '../data/cache.js'
import { authedFetch } from '../auth.js'

const activeTab = ref('SIM')  // SIM | REAL
const loading = ref(true)
const refreshing = ref(false)
const submitting = ref(false)
const errorMsg = ref('')

const positions = ref([])
const trades = ref([])
const stats = ref({})
const showBuyModal = ref(false)
const showSellModal = ref(false)
const showCapitalModal = ref(false)
const sellPos = ref(null)
const deletingTrade = ref(null)
const capitalError = ref('')
const lastUpdate = ref('')
const cacheNote = ref('')
const cacheInfo = reactive({ sim: false, real: false })
const currentStrategy = ref(null)

const buyForm = reactive({ code: '', name: '', price: '', shares: '', score: '', reason: '' })
const sellForm = reactive({ price: '', shares: '', reason: '' })
const capitalForm = reactive({ amount: '' })

// 校验
const buyValidationError = ref('')
const isBuyValid = computed(() => !buyValidationError.value && buyForm.code && buyForm.name && buyForm.price && buyForm.shares)

function validateBuyForm() {
  buyValidationError.value = ''
  const price = Number(buyForm.price)
  const shares = Number(buyForm.shares)
  if (!buyForm.code) return
  if (isNaN(price) || price <= 0) {
    buyValidationError.value = '价格必须为正数'
    return
  }
  if (isNaN(shares) || shares < 100) {
    buyValidationError.value = 'A 股最小买入 100 股'
    return
  }
  if (shares % 100 !== 0) {
    buyValidationError.value = 'A 股必须为 100 整数倍'
  }
}

const buyFormTotal = computed(() => {
  const p = Number(buyForm.price)
  const s = Number(buyForm.shares)
  if (!p || !s) return 0
  return p * s + Math.max(p * s * 0.00015, 5)
})

const buyFormFee = computed(() => {
  const p = Number(buyForm.price)
  const s = Number(buyForm.shares)
  if (!p || !s) return 0
  return Math.max(p * s * 0.00015, 5)
})

const sellValidationError = ref('')
const isSellValid = computed(() => !sellValidationError.value && sellForm.price && sellForm.shares)

function validateSellForm() {
  sellValidationError.value = ''
  if (!sellPos.value) return
  const price = Number(sellForm.price)
  const shares = Number(sellForm.shares)
  if (isNaN(price) || price <= 0) { sellValidationError.value = '价格必须为正数'; return }
  if (isNaN(shares) || shares < 100) { sellValidationError.value = 'A 股最小卖出 100 股'; return }
  if (shares % 100 !== 0) { sellValidationError.value = 'A 股必须为 100 整数倍'; return }
  if (shares > sellPos.value.shares) { sellValidationError.value = `卖出数量不能超过持仓 ${sellPos.value.shares}` }
}

const sellFormEstimate = computed(() => {
  if (!sellPos.value) return ''
  const price = Number(sellForm.price)
  const shares = Number(sellForm.shares)
  if (!price || !shares) return ''
  const amount = price * shares
  const commission = Math.max(amount * 0.00015, 5)
  const stamp_tax = amount * 0.001
  const net = amount - commission - stamp_tax
  const cost = sellPos.value.cost_price * shares
  const profit = net - cost
  const profitRate = (profit / cost * 100).toFixed(2)
  return `预计到手: ¥${formatNumber(net)} | 预计盈亏: ¥${formatNumber(profit)} (${profitRate}%)`
})

// 加载数据（按当前 tab）
async function fetchData(force = false) {
  const mode = activeTab.value
  try {
    const [pos, tradeList, stat, strategy] = await Promise.all([
      loadPositions(mode, force),
      loadTrades(mode, 50, force),
      loadStats(mode, force),
      loadStrategy(mode, force)
    ])
    positions.value = pos
    trades.value = tradeList
    stats.value = stat
    currentStrategy.value = strategy
    lastUpdate.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
    const ttl = getCacheTTL('REALTIME')
    const marketState = getMarketState()
    if (ttl >= 60 * 60 * 1000) {
      cacheNote.value = '非交易时间，价格已锁定'
    } else if (ttl >= 5 * 60 * 1000) {
      cacheNote.value = '盘前/午休，5 分钟刷新'
    } else {
      cacheNote.value = '交易中，30 秒刷新'
    }
    cacheInfo[mode === 'SIM' ? 'sim' : 'real'] = !force
  } catch (e) {
    errorMsg.value = '数据加载失败: ' + e.message
  }
}

// Tab 切换时刷新（但 cache 内部会判断是否需要）
watch(activeTab, (newTab, oldTab) => {
  if (newTab !== oldTab) {
    fetchData(false)
  }
})

// 定时刷新（仅持仓和价格需要，30 秒/5 分钟/1 小时）
let refreshTimer = null
function setupAutoRefresh() {
  if (refreshTimer) clearInterval(refreshTimer)
  const ttl = getCacheTTL('REALTIME')
  refreshTimer = setInterval(() => {
    fetchData(false)
  }, ttl)
}

// 监听市场状态变化（交易 ↔ 休市）
function watchMarketState() {
  let lastState = getMarketState()
  setInterval(() => {
    const currentState = getMarketState()
    if (currentState !== lastState) {
      lastState = currentState
      setupAutoRefresh()  // 重新计算刷新间隔
      fetchData(true)  // 状态变化时强制刷新
    }
  }, 60 * 1000)
}

function openBuyModal() {
  Object.assign(buyForm, { code: '', name: '', price: '', shares: '', score: '', reason: '' })
  buyValidationError.value = ''
  showBuyModal.value = true
}

function closeBuyModal() {
  showBuyModal.value = false
}

function openSellModal(pos) {
  sellPos.value = pos
  Object.assign(sellForm, { price: pos.current_price, shares: pos.shares, reason: '' })
  sellValidationError.value = ''
  showSellModal.value = true
}

function openCapitalModal() {
  capitalForm.amount = stats.value.initial_capital || 1000000
  capitalError.value = ''
  showCapitalModal.value = true
}

const capitalValid = computed(() => {
  const n = Number(capitalForm.amount)
  return !isNaN(n) && n > 0
})

async function confirmUpdateCapital() {
  if (!capitalValid.value) return
  if (!confirm(`⚠️ 确认要将${activeTab.value === 'SIM' ? '模拟仓' : '实盘'}重置为 ¥${capitalForm.amount} 吗？\n这将清空所有持仓和交易记录。`)) {
    return
  }
  submitting.value = true
  try {
    const r = await authedFetch('/api/v1/portfolio/update-capital', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        initial_capital: Number(capitalForm.amount),
        mode: activeTab.value
      })
    })
    const data = await r.json()
    if (data.success) {
      showCapitalModal.value = false
      // 强制清缓存
      const { clearAllCache } = await import('../data/loader.js')
      clearAllCache()
      await fetchData(true)
    } else {
      capitalError.value = data.error || '重置失败'
    }
  } catch (e) {
    capitalError.value = '网络错误: ' + e.message
  } finally {
    submitting.value = false
  }
}

async function deleteTradeConfirm(trade) {
  const action = trade.type === 'BUY' ? '买入' : '卖出'
  if (!confirm(`确认删除这条${action}记录？\n\n${trade.trade_date}  ${trade.code} ${trade.name}  ${trade.shares}股 @ ¥${trade.price}\n\n⚠️ 删除将反转该交易对账户和持仓的影响。`)) {
    return
  }
  deletingTrade.value = trade.id
  try {
    const r = await authedFetch('/api/v1/portfolio/delete-trade', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        trade_id: trade.id,
        mode: activeTab.value
      })
    })
    const data = await r.json()
    if (data.success) {
      await fetchData(true)
    } else {
      alert('删除失败: ' + (data.error || '未知错误'))
    }
  } catch (e) {
    alert('网络错误: ' + e.message)
  } finally {
    deletingTrade.value = null
  }
}

async function refreshPrices() {
  if (positions.value.length === 0) return
  refreshing.value = true
  try {
    const resp = await fetch('/data/score_price_history.csv?_t=' + Date.now())
    const text = await resp.text()
    const lines = text.trim().split('\n')
    if (lines.length < 2) return
    const headers = lines[0].split(',')
    const dateIdx = headers.indexOf('date')
    const codeIdx = headers.indexOf('code')
    const priceIdx = headers.indexOf('close_price')
    if (dateIdx < 0 || codeIdx < 0 || priceIdx < 0) {
      errorMsg.value = '价格数据格式错误'
      return
    }
    const dateSet = new Set()
    const latestByCode = {}
    for (let i = 1; i < lines.length; i++) {
      const vals = lines[i].split(',')
      const d = vals[dateIdx]
      const c = vals[codeIdx]
      const p = parseFloat(vals[priceIdx])
      if (c && !isNaN(p)) {
        latestByCode[c] = { date: d, price: p }
        dateSet.add(d)
      }
    }
    const latestDate = [...dateSet].sort().pop()

    const prices = {}
    for (const pos of positions.value) {
      const data = latestByCode[pos.code]
      if (data && data.date === latestDate) {
        prices[pos.code] = data.price
      }
    }
    if (Object.keys(prices).length > 0) {
      // 加 mode 参数
      const url = `/api/v1/portfolio/update-prices?mode=${activeTab.value}`
      await authedFetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prices })
      })
      await fetchData(true)
    } else {
      errorMsg.value = '未找到最新价格数据'
    }
  } catch (e) {
    errorMsg.value = '刷新失败: ' + e.message
  } finally {
    refreshing.value = false
  }
}

async function saveSnapshotNow() {
  try {
    const url = `/api/v1/portfolio/snapshot?mode=${activeTab.value}`
    const r = await authedFetch(url, { method: 'POST' })
    const data = await r.json()
    if (data.date) {
      lastUpdate.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
      alert(`✅ 快照已保存: ${data.date}\n总资产: ¥${formatNumber(data.total_assets)}`)
    }
  } catch (e) {
    errorMsg.value = '保存快照失败: ' + e.message
  }
}

async function confirmBuy() {
  if (!isBuyValid.value) return
  submitting.value = true
  try {
    const r = await authedFetch('/api/v1/portfolio/buy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        code: buyForm.code,
        name: buyForm.name,
        price: Number(buyForm.price),
        shares: Number(buyForm.shares),
        score: buyForm.score ? Number(buyForm.score) : null,
        reason: buyForm.reason || null,
        mode: activeTab.value
      })
    })
    const data = await r.json()
    if (data.success) {
      closeBuyModal()
      await fetchData(true)
    } else {
      buyValidationError.value = data.error || '买入失败'
    }
  } catch (e) {
    buyValidationError.value = '网络错误: ' + e.message
  } finally {
    submitting.value = false
  }
}

async function confirmSell() {
  if (!isSellValid.value) return
  submitting.value = true
  try {
    const r = await authedFetch('/api/v1/portfolio/sell', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        code: sellPos.value.code,
        price: Number(sellForm.price),
        shares: Number(sellForm.shares),
        reason: sellForm.reason || null,
        mode: activeTab.value
      })
    })
    const data = await r.json()
    if (data.success) {
      showSellModal.value = false
      await fetchData(true)
    } else {
      sellValidationError.value = data.error || '卖出失败'
    }
  } catch (e) {
    sellValidationError.value = '网络错误: ' + e.message
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  await fetchData(false)
  loading.value = false
  setupAutoRefresh()
  watchMarketState()
})

// 跳转 yujing 时透传持仓信息
function gotoYujingWithPosition(code) {
  // 找到当前持仓
  const pos = positions.value.find(p => p.code === code)
  if (!pos) {
    gotoYujing(code)
    return
  }
  // 取当前账户的策略
  const strategy = currentStrategy.value
  const opts = {
    cost: pos.cost_price,
  }
  if (strategy) {
    opts.tp = (strategy.take_profit * 100).toFixed(1)
    opts.sl = (strategy.stop_loss * 100).toFixed(1)
    opts.strategy = strategy.name
  }
  gotoYujing(code, opts)
}

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
.portfolio-page { max-width: 1200px; }

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

.tab-btn.active {
  color: #00d4ff;
  border-bottom-color: #00d4ff;
}

.tab-icon { font-size: 18px; }

.tab-badge {
  font-size: 10px;
  background: rgba(46, 213, 115, 0.2);
  color: #2ed573;
  padding: 2px 6px;
  border-radius: 8px;
}

/* Stats */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 16px;
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

.action-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  align-items: center;
  flex-wrap: wrap;
}

.cache-info {
  margin-left: auto;
  font-size: 12px;
  color: #666;
}

.error-banner {
  background: rgba(255, 71, 87, 0.15);
  border: 1px solid rgba(255, 71, 87, 0.3);
  color: #ff4757;
  padding: 12px 16px;
  border-radius: 8px;
  margin-bottom: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.info-banner {
  background: rgba(0, 212, 255, 0.08);
  border: 1px solid rgba(0, 212, 255, 0.2);
  color: #00d4ff;
  padding: 12px 16px;
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 13px;
}

.info-banner.real {
  background: rgba(255, 165, 0, 0.08);
  border-color: rgba(255, 165, 0, 0.2);
  color: #ffa500;
}

.btn-close {
  background: none;
  border: none;
  color: inherit;
  cursor: pointer;
  font-size: 18px;
}

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

.code {
  font-family: monospace;
  color: #00d4ff;
  cursor: pointer;
  text-decoration: none;
}

.code:hover { text-decoration: underline; }

.name { color: #e0e0e0; }

.clickable { cursor: pointer; }
.clickable:hover { color: #00d4ff; text-decoration: underline; }

.up { color: #ff4757; }
.down { color: #2ed573; }
.flat { color: #a0a0b0; }

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

.btn-primary:hover:not(:disabled) { opacity: 0.9; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-outline {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: #a0a0b0;
}

.btn-outline:hover:not(:disabled) { border-color: #00d4ff; color: #00d4ff; }
.btn-outline:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-danger { background: rgba(255, 71, 87, 0.2); color: #ff4757; }
.btn-danger:hover:not(:disabled) { background: rgba(255, 71, 87, 0.3); }
.btn-danger:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-sm { padding: 4px 12px; font-size: 12px; }

.modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: #1a1a2e;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  width: 90%;
  max-width: 440px;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.modal-header h3 { font-size: 16px; color: #e0e0e0; }
.modal-body { padding: 20px; }

.form-group { margin-bottom: 16px; }
.form-group label {
  display: block;
  font-size: 12px;
  color: #666;
  margin-bottom: 8px;
}

.form-group input {
  width: 100%;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.05);
  color: #e0e0e0;
  font-size: 14px;
  outline: none;
}

.form-group input:focus { border-color: #00d4ff; }

.form-error { color: #ff4757; font-size: 13px; margin-top: 8px; }
.form-info {
  color: #00d4ff;
  font-size: 13px;
  margin-top: 8px;
  padding: 8px 12px;
  background: rgba(0, 212, 255, 0.1);
  border-radius: 6px;
}

.info-row {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 13px;
  color: #a0a0b0;
  margin-bottom: 16px;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 6px;
}

.info-row strong { color: #e0e0e0; }
.info-row .sep { color: #444; }

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.empty, .loading { text-align: center; padding: 40px; color: #666; }

@media (max-width: 768px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
  .stat-value { font-size: 18px; }
  .action-bar { flex-direction: column; align-items: stretch; }
  .cache-info { margin-left: 0; }
  .data-table th, .data-table td { padding: 8px; font-size: 12px; }
}
</style>
