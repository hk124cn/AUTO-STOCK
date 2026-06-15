<template>
  <div class="strategies-page">
    <h1 class="page-title">⚙️ 策略管理</h1>

    <!-- 当前绑定 -->
    <div class="card">
      <div class="card-title">
        <span>🎯</span>
        <span>当前账户策略</span>
      </div>
      <div class="binding-grid">
        <div class="binding-item">
          <div class="binding-label">🎲 模拟仓策略</div>
          <select v-model="accountBindings.SIM" class="select-input" @change="bindStrategy('SIM')">
            <option v-for="s in strategies" :key="`sim-${s.id}`" :value="s.id">
              {{ s.name }}（买入≥{{ s.buy_threshold }}, 止盈{{ s.take_profit*100 }}%, 止损{{ s.stop_loss*100 }}%）
            </option>
          </select>
        </div>
        <div class="binding-item">
          <div class="binding-label">💰 实盘策略</div>
          <select v-model="accountBindings.REAL" class="select-input" @change="bindStrategy('REAL')">
            <option v-for="s in strategies" :key="`real-${s.id}`" :value="s.id">
              {{ s.name }}（买入≥{{ s.buy_threshold }}, 止盈{{ s.take_profit*100 }}%, 止损{{ s.stop_loss*100 }}%）
            </option>
          </select>
        </div>
      </div>
    </div>

    <!-- 策略库 -->
    <div class="card">
      <div class="card-title">
        <span>📚</span>
        <span>策略库（{{ strategies.length }} 个）</span>
        <button class="btn btn-primary btn-sm" @click="openEditModal(null)" style="margin-left: auto;">
          ➕ 新建策略
        </button>
      </div>
      <table class="data-table">
        <thead>
          <tr>
            <th>策略名</th>
            <th>买入阈值</th>
            <th>止盈%</th>
            <th>止损%</th>
            <th>冷却(天)</th>
            <th>单股%</th>
            <th>最多持仓</th>
            <th>说明</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in strategies" :key="s.id" :class="{ 'is-default': s.is_default }">
            <td>
              {{ s.name }}
              <span v-if="s.is_default" class="default-badge">默认</span>
            </td>
            <td>≥ {{ s.buy_threshold }}</td>
            <td class="up">+{{ (s.take_profit * 100).toFixed(0) }}%</td>
            <td class="down">-{{ (s.stop_loss * 100).toFixed(0) }}%</td>
            <td>{{ s.cooldown_days }}</td>
            <td>{{ (s.max_position_pct * 100).toFixed(0) }}%</td>
            <td>{{ s.max_positions }}</td>
            <td class="desc">{{ s.description || '-' }}</td>
            <td>
              <button class="btn btn-sm btn-outline" @click="openEditModal(s)">编辑</button>
              <button class="btn btn-sm btn-outline" @click="duplicateStrategy(s)">复制</button>
              <button
                class="btn btn-sm btn-outline"
                :disabled="s.is_default"
                :title="s.is_default ? '默认策略不能删除' : '删除策略'"
                @click="deleteStrategyConfirm(s)"
              >删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 回测 TOP 10 -->
    <div class="card">
      <div class="card-title">
        <span>🏆</span>
        <span>回测历史 TOP 10</span>
        <span class="hint">（按年化收益排序）</span>
      </div>
      <div v-if="loadingBacktest" class="loading">加载中...</div>
      <div v-else-if="backtestResults.length === 0" class="empty">暂无回测结果</div>
      <table v-else class="data-table">
        <thead>
          <tr>
            <th>排名</th>
            <th>策略名</th>
            <th>回测区间</th>
            <th>总收益</th>
            <th>年化</th>
            <th>最大回撤</th>
            <th>夏普</th>
            <th>胜率</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(b, idx) in backtestResults" :key="b.name">
            <td class="rank">{{ idx + 1 }}</td>
            <td class="name-cell" :title="b.readme_url">{{ b.name }}</td>
            <td>{{ b.period || '-' }}</td>
            <td :class="getChangeClass(b.total_return)">{{ formatPercent(b.total_return) }}</td>
            <td :class="getChangeClass(b.annual_return)">{{ formatPercent(b.annual_return) }}</td>
            <td class="down">{{ formatPercent(-(b.max_drawdown || 0)) }}</td>
            <td>{{ b.sharpe ? b.sharpe.toFixed(2) : '-' }}</td>
            <td>{{ b.win_rate ? b.win_rate.toFixed(1) + '%' : '-' }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 编辑/新建策略弹窗 -->
    <div v-if="showEditModal" class="modal-overlay" @click.self="closeEditModal">
      <div class="modal">
        <div class="modal-header">
          <h3>{{ editForm.id ? '编辑策略' : '新建策略' }}</h3>
          <button class="btn-close" @click="closeEditModal">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>策略名称 *</label>
            <input v-model="editForm.name" placeholder="如：稳健 / 激进 / 自定义" />
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>买入阈值（前7日均分）</label>
              <input v-model.number="editForm.buy_threshold" type="number" step="1" min="20" max="50" />
              <div class="form-hint">≥ 此分才买入（默认 30）</div>
            </div>
            <div class="form-group">
              <label>止盈 %</label>
              <input v-model.number="editForm.take_profit" type="number" step="0.01" min="0.05" max="0.5" />
              <div class="form-hint">成本 × (1 + 此值) 为目标止盈价</div>
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>止损 %</label>
              <input v-model.number="editForm.stop_loss" type="number" step="0.01" min="0.03" max="0.2" />
              <div class="form-hint">成本 × (1 - 此值) 为目标止损价</div>
            </div>
            <div class="form-group">
              <label>冷却天数</label>
              <input v-model.number="editForm.cooldown_days" type="number" step="1" min="0" max="10" />
              <div class="form-hint">同股两次信号间隔（默认 1）</div>
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>单股最大仓位 %</label>
              <input v-model.number="editForm.max_position_pct" type="number" step="0.05" min="0.05" max="0.5" />
              <div class="form-hint">占总资产比例（默认 0.20 = 20%）</div>
            </div>
            <div class="form-group">
              <label>最多持仓数</label>
              <input v-model.number="editForm.max_positions" type="number" step="1" min="1" max="20" />
              <div class="form-hint">同时持有股票数上限（默认 5）</div>
            </div>
          </div>
          <div class="form-group">
            <label>说明（可选）</label>
            <input v-model="editForm.description" placeholder="如：高阈值 + 低仓位" />
          </div>
          <div class="form-group">
            <label>
              <input v-model="editForm.is_default" type="checkbox" />
              设为默认策略（账户创建时自动使用）
            </label>
          </div>
          <div v-if="editError" class="form-error">⚠️ {{ editError }}</div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-outline" @click="closeEditModal">取消</button>
          <button class="btn btn-primary" :disabled="!isEditValid || submitting" @click="confirmEdit">
            {{ submitting ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { formatPercent, getChangeClass, clearAllCache } from '../data/loader.js'
import { authedFetch } from '../auth.js'

const API_BASE = '/api/v1'

const strategies = ref([])
const backtestResults = ref([])
const loadingBacktest = ref(true)
const submitting = ref(false)
const editError = ref('')
const showEditModal = ref(false)

const accountBindings = reactive({ SIM: null, REAL: null })

const editForm = reactive({
  id: null,
  name: '',
  buy_threshold: 30,
  take_profit: 0.20,
  stop_loss: 0.08,
  cooldown_days: 1,
  max_position_pct: 0.20,
  max_positions: 5,
  description: '',
  is_default: 0
})

const isEditValid = computed(() => {
  return editForm.name && editForm.name.trim() &&
    editForm.buy_threshold >= 20 && editForm.buy_threshold <= 50 &&
    editForm.take_profit > 0 && editForm.take_profit <= 0.5 &&
    editForm.stop_loss > 0 && editForm.stop_loss <= 0.2 &&
    editForm.cooldown_days >= 0 && editForm.cooldown_days <= 10 &&
    editForm.max_position_pct >= 0.05 && editForm.max_position_pct <= 0.5 &&
    editForm.max_positions >= 1 && editForm.max_positions <= 20
})

async function fetchStrategies() {
  try {
    const r = await fetch(API_BASE + '/strategies')
    const d = await r.json()
    strategies.value = d.strategies || []
  } catch (e) {
    console.error('加载策略失败:', e)
  }
}

async function fetchAccountBindings() {
  for (const mode of ['SIM', 'REAL']) {
    try {
      const r = await fetch(API_BASE + `/portfolio/strategy?mode=${mode}`)
      const s = await r.json()
      if (s && s.id) {
        accountBindings[mode] = s.id
      }
    } catch (e) {
      console.error(`加载 ${mode} 策略失败`, e)
    }
  }
}

async function fetchBacktestTop() {
  loadingBacktest.value = true
  try {
    const r = await fetch(API_BASE + '/backtest/top?n=10')
    const d = await r.json()
    backtestResults.value = d.results || []
  } catch (e) {
    console.error('加载回测结果失败', e)
  } finally {
    loadingBacktest.value = false
  }
}

async function bindStrategy(mode) {
  const sid = accountBindings[mode]
  if (!sid) return
  try {
    // 先获取账户 ID
    const r = await fetch(API_BASE + `/portfolio/account?mode=${mode}`)
    const account = await r.json()
    if (account && account.id) {
      await authedFetch(API_BASE + '/portfolio/strategy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account_id: account.id, strategy_id: sid })
      })
      clearAllCache()
      alert(`✅ ${mode === 'SIM' ? '模拟仓' : '实盘'}策略已切换`)
    }
  } catch (e) {
    alert('切换失败: ' + e.message)
  }
}

function openEditModal(s) {
  if (s) {
    Object.assign(editForm, s)
  } else {
    Object.assign(editForm, {
      id: null, name: '', buy_threshold: 30, take_profit: 0.20,
      stop_loss: 0.08, cooldown_days: 1, max_position_pct: 0.20,
      max_positions: 5, description: '', is_default: 0
    })
  }
  editError.value = ''
  showEditModal.value = true
}

function closeEditModal() {
  showEditModal.value = false
}

function duplicateStrategy(s) {
  openEditModal(s)
  editForm.id = null
  editForm.name = s.name + ' (副本)'
  editForm.is_default = 0
}

async function confirmEdit() {
  if (!isEditValid.value) return
  submitting.value = true
  editError.value = ''
  try {
    let r
    if (editForm.id) {
      r = await authedFetch(API_BASE + `/strategies/${editForm.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editForm)
      })
    } else {
      const { id, ...body } = editForm
      r = await authedFetch(API_BASE + '/strategies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      })
    }
    const data = await r.json()
    if (data.success !== false) {
      closeEditModal()
      await fetchStrategies()
    } else {
      editError.value = data.error || '保存失败'
    }
  } catch (e) {
    editError.value = '网络错误: ' + e.message
  } finally {
    submitting.value = false
  }
}

async function deleteStrategyConfirm(s) {
  if (s.is_default) {
    alert('默认策略不能删除')
    return
  }
  if (!confirm(`确认删除策略"${s.name}"？`)) return
  try {
    const r = await authedFetch(API_BASE + `/strategies/${s.id}`, { method: 'DELETE' })
    const data = await r.json()
    if (data.success) {
      await fetchStrategies()
    } else {
      alert('删除失败: ' + (data.error || '未知错误'))
    }
  } catch (e) {
    alert('网络错误: ' + e.message)
  }
}

onMounted(async () => {
  await fetchStrategies()
  await fetchAccountBindings()
  await fetchBacktestTop()
})
</script>

<style scoped>
.strategies-page { max-width: 1200px; }

.page-title {
  font-size: 24px;
  font-weight: 700;
  margin-bottom: 24px;
  background: linear-gradient(135deg, #00d4ff, #7b68ee);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
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

.card-title .hint {
  font-size: 12px;
  color: #666;
  font-weight: normal;
  margin-left: 8px;
}

.binding-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.binding-item {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
  padding: 12px;
}

.binding-label {
  font-size: 13px;
  color: #a0a0b0;
  margin-bottom: 8px;
}

.select-input {
  width: 100%;
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.05);
  color: #e0e0e0;
  font-size: 14px;
  outline: none;
}

.select-input:focus { border-color: #00d4ff; }

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
.data-table tr.is-default { background: rgba(0, 212, 255, 0.05); }

.rank { color: #666; font-size: 12px; }
.up { color: #ff4757; }
.down { color: #2ed573; }
.desc { color: #888; font-size: 12px; }

.default-badge {
  font-size: 10px;
  background: rgba(0, 212, 255, 0.2);
  color: #00d4ff;
  padding: 2px 6px;
  border-radius: 8px;
  margin-left: 6px;
}

.btn {
  padding: 6px 12px;
  border-radius: 6px;
  border: none;
  font-size: 13px;
  cursor: pointer;
  margin-right: 4px;
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

.btn-sm { padding: 4px 10px; font-size: 12px; }

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
  max-width: 520px;
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

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.form-group { margin-bottom: 16px; }
.form-group label {
  display: block;
  font-size: 12px;
  color: #666;
  margin-bottom: 8px;
}

.form-group input[type="text"],
.form-group input[type="number"]:not([type="checkbox"]) {
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
.form-hint { font-size: 11px; color: #666; margin-top: 4px; }
.form-error { color: #ff4757; font-size: 13px; margin-top: 8px; }

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.loading, .empty {
  text-align: center;
  padding: 40px;
  color: #666;
}

@media (max-width: 768px) {
  .binding-grid { grid-template-columns: 1fr; }
  .form-row { grid-template-columns: 1fr; }
  .data-table th, .data-table td { padding: 8px; font-size: 12px; }
}
</style>
