// detail.js
const app = getApp()

Page({
  data: {
    loading: false,
    error: '',
    result: null,
    activeQuarter: '本季度',
    activeTab: '',
    feedbackContent: '',
    submitting: false,
    feedbackMessage: null,
    // 计算属性
    currentScore: {},
    scoreClass: 'poor',
    // K线相关
    showKline: false,
    klineLoading: false,
    klineError: '',
    klineData: null,
    klineReportType: '',
    klineDisclosureDate: '',
    klineStats: null,
    klineTooltip: null
  },

  _klineRawData: null,

  onLoad(options) {
    if (options.code) {
      this.loadDetail(options.code)
    }
  },

  loadDetail(code) {
    this.setData({ loading: true, error: '' })

    wx.request({
      url: `${app.globalData.apiBase}/financial/detail/${code}`,
      success: (res) => {
        this.setData({ result: res.data })
        this.updateCurrentScore()
        this.loadKline()
        setTimeout(() => {
          this.drawTrendChart()
        }, 100)
      },
      fail: (err) => {
        this.setData({ error: err.errMsg || '加载失败' })
      },
      complete: () => {
        this.setData({ loading: false })
      }
    })
  },

  updateCurrentScore() {
    const { result, activeQuarter } = this.data
    if (!result) return

    const quarterData = result.scores[activeQuarter] || { total: 0 }
    const financeDataRaw = quarterData['财务数据']

    let financeData = null
    if (financeDataRaw) {
      financeData = {
        totalRevenue: financeDataRaw['营业总收入'] || '',
        totalRevenueGrowth: financeDataRaw['营业总收入同比'] || '',
        netProfit: financeDataRaw['净利润'] || '',
        netProfitGrowth: financeDataRaw['净利润同比'] || '',
        koufeiProfit: financeDataRaw['扣非净利润'] || '',
        koufeiProfitGrowth: financeDataRaw['扣非净利润同比'] || ''
      }
    }

    const currentScore = {
      total: quarterData.total || 0,
      yingshou: quarterData['营收'] || 0,
      guimu: quarterData['归母'] || 0,
      koufei: quarterData['扣非'] || 0,
      yingshou_trend: quarterData['营收趋势'] || 0,
      koufei_trend: quarterData['扣非趋势'] || 0,
      guimu_trend: quarterData['归母趋势'] || 0,
      financeData: financeData
    }
    let scoreClass = 'poor'
    if (currentScore.total >= 15) scoreClass = 'excellent'
    else if (currentScore.total >= 5) scoreClass = 'good'
    else if (currentScore.total < 0) scoreClass = 'negative'  // 负分用红色

    this.setData({ currentScore, scoreClass })
  },

  switchQuarter(e) {
    const quarter = e.currentTarget.dataset.quarter
    this.setData({ activeQuarter: quarter, showKline: false }, () => {
      this.updateCurrentScore()
      this.loadKline()
    })
  },

  toggleTab(e) {
    const tab = e.currentTarget.dataset.tab
    if (this.data.activeTab === tab) {
      this.setData({ activeTab: '' })
    } else {
      this.setData({ activeTab: tab })
    }
  },

  closeTab() {
    this.setData({ activeTab: '' })
  },

  onFeedbackInput(e) {
    this.setData({ feedbackContent: e.detail.value })
  },

  submitFeedback() {
    const { feedbackContent, result } = this.data
    if (!feedbackContent.trim()) return

    this.setData({ submitting: true, feedbackMessage: null })

    wx.request({
      url: `${app.globalData.apiBase}/feedback`,
      method: 'POST',
      header: { 'Content-Type': 'application/json' },
      data: {
        content: feedbackContent,
        code: result && result.code ? result.code : '',
        name: result && result.name ? result.name : ''
      },
      success: () => {
        this.setData({
          feedbackContent: '',
          feedbackMessage: { type: 'success', text: '感谢您的反馈！' }
        })
      },
      fail: () => {
        this.setData({
          feedbackMessage: { type: 'error', text: '提交失败，请重试' }
        })
      },
      complete: () => {
        this.setData({ submitting: false })
      }
    })
  },

  getScoreClass(score, maxScore) {
    if (score <= 0) return 'poor'
    const ratio = score / maxScore
    if (ratio >= 0.7) return 'excellent'
    if (ratio >= 0.3) return 'good'
    return 'poor'
  },

  getGrowthClass(growthStr) {
    if (!growthStr) return ''
    const growth = parseFloat(growthStr.replace('%', ''))
    if (growth > 0) return 'growth-up'
    if (growth < 0) return 'growth-down'
    return ''
  },

  // ========== K线功能 ==========

  toggleView() {
    if (!this.data.showKline) {
      this.setData({ showKline: true })
      setTimeout(() => {
        this.drawKline()
      }, 500)
    } else {
      this.setData({ showKline: false, klineTooltip: null })
    }
  },

  loadKline() {
    if (!this.data.result) return
    this.setData({ klineLoading: true, klineError: '' })

    wx.request({
      url: `${app.globalData.apiBase}/financial/kline/${this.data.result.code}`,
      data: { quarter: this.data.activeQuarter },
      success: (res) => {
        // 检查HTTP状态码
        if (res.statusCode >= 400) {
          const errData = res.data || {}
          this.setData({ klineError: errData.error || 'K线数据不存在', klineData: null })
          return
        }
        const data = res.data
        if (data && data.error) {
          this.setData({ klineError: data.error, klineData: null })
          return
        }
        this._klineRawData = data
        this.setData({
          klineData: data,
          klineReportType: data.report_type || '',
          klineDisclosureDate: data.disclosure_date || ''
        })
        this.calcKlineStats()
      },
      fail: (err) => {
        this.setData({ klineError: err.errMsg || 'K线加载失败', klineData: null })
      },
      complete: () => {
        this.setData({ klineLoading: false })
      }
    })
  },

  calcKlineStats() {
    const data = this._klineRawData
    if (!data || !data.kline || !data.kline.length || !data.prev_close) {
      this.setData({ klineStats: null })
      return
    }
    const kline = data.kline
    const prevClose = data.prev_close
    const firstDay = kline[0]
    const firstDayChange = ((firstDay.close - prevClose) / prevClose * 100).toFixed(2)

    let totalChange = null
    let totalDays = 0
    if (kline.length > 1) {
      const lastDay = kline[kline.length - 1]
      totalChange = ((lastDay.close - prevClose) / prevClose * 100).toFixed(2)
      totalDays = kline.length
    }

    this.setData({
      klineStats: {
        firstDayChange,
        firstDayUp: parseFloat(firstDayChange) >= 0,
        totalChange,
        totalUp: totalChange !== null ? parseFloat(totalChange) >= 0 : true,
        totalDays
      }
    })
  },

  drawKline() {
    const data = this._klineRawData
    if (!data || !data.kline || !data.kline.length) {
      console.log('drawKline: no data', data)
      return
    }

    const kline = data.kline
    console.log('drawKline: kline length', kline.length)

    const ctx = wx.createCanvasContext('klineCanvasDetail', this)
    const query = wx.createSelectorQuery().in(this)
    query.select('.kline-canvas').boundingClientRect((rect) => {
      if (!rect) {
        console.log('drawKline: no rect')
        return
      }
      console.log('drawKline: rect', rect.width, rect.height)
      const width = rect.width
      const height = rect.height

      const padding = { left: 10, right: 10, top: 10, bottom: 20 }
      const chartW = width - padding.left - padding.right
      const chartH = height - padding.top - padding.bottom

      // 固定7天位置，不足时靠左
      const totalSlots = 7
      const candleW = Math.min(chartW / totalSlots * 0.6, 20)
      const gap = chartW / totalSlots

      // 计算价格范围
      let minPrice = Infinity
      let maxPrice = -Infinity
      kline.forEach(k => {
        if (k.high != null) maxPrice = Math.max(maxPrice, k.high)
        if (k.low != null) minPrice = Math.min(minPrice, k.low)
      })
      // 防止minPrice === maxPrice导致除零
      if (!isFinite(minPrice) || !isFinite(maxPrice) || minPrice === maxPrice) {
        minPrice = data.prev_close ? data.prev_close * 0.9 : 0
        maxPrice = data.prev_close ? data.prev_close * 1.1 : 100
      }
      // 添加5%边距
      const priceRange = maxPrice - minPrice
      minPrice = minPrice - priceRange * 0.05
      maxPrice = maxPrice + priceRange * 0.05

      ctx.setFillStyle('#fff')
      ctx.fillRect(0, 0, width, height)

      ctx.setStrokeStyle('#f0f0f0')
      ctx.setLineWidth(0.5)
      for (let i = 0; i <= 4; i++) {
        const y = padding.top + (chartH / 4) * i
        ctx.beginPath()
        ctx.moveTo(padding.left, y)
        ctx.lineTo(width - padding.right, y)
        ctx.stroke()
      }

      const priceToY = (price) => {
        return padding.top + chartH * (1 - (price - minPrice) / (maxPrice - minPrice))
      }

      kline.forEach((k, i) => {
        const x = padding.left + gap * i + gap / 2
        const isUp = k.close >= k.open
        const color = isUp ? '#ef232a' : '#14b143'

        if (k.high != null && k.low != null) {
          ctx.setStrokeStyle(color)
          ctx.setLineWidth(1)
          ctx.beginPath()
          ctx.moveTo(x, priceToY(k.high))
          ctx.lineTo(x, priceToY(k.low))
          ctx.stroke()
        }

        if (k.open != null && k.close != null) {
          const yOpen = priceToY(k.open)
          const yClose = priceToY(k.close)
          const bodyTop = Math.min(yOpen, yClose)
          const bodyH = Math.max(Math.abs(yOpen - yClose), 1)

          ctx.setFillStyle(color)
          ctx.fillRect(x - candleW / 2, bodyTop, candleW, bodyH)
        }
      })

      ctx.setFillStyle('#999')
      ctx.setFontSize(10)
      ctx.setTextAlign('center')
      kline.forEach((k, i) => {
        const x = padding.left + gap * i + gap / 2
        const dateStr = k.date ? k.date.slice(5) : ''
        ctx.fillText(dateStr, x, height - 4)
      })

      ctx.draw()
    }).exec()
  },

  onKlineTouch(e) {
    const data = this._klineRawData
    if (!data || !data.kline || !data.kline.length) return

    const touch = e.touches[0]
    const query = wx.createSelectorQuery().in(this)
    query.select('.kline-canvas').boundingClientRect((rect) => {
      if (!rect) return
      const x = touch.clientX - rect.left
      const width = rect.width
      const padding = { left: 10, right: 10 }
      const chartW = width - padding.left - padding.right
      const totalSlots = 7
      const gap = chartW / totalSlots

      const idx = Math.floor((x - padding.left) / gap)
      if (idx < 0 || idx >= data.kline.length) {
        this.setData({ klineTooltip: null })
        return
      }

      const k = data.kline[idx]
      const prevClose = data.prev_close
      let change = null
      let changeColor = ''
      if (idx === 0 && prevClose) {
        change = ((k.close - prevClose) / prevClose * 100).toFixed(2)
      } else if (idx > 0) {
        const prevK = data.kline[idx - 1]
        if (prevK.close) {
          change = ((k.close - prevK.close) / prevK.close * 100).toFixed(2)
        }
      }
      if (change !== null) {
        changeColor = parseFloat(change) >= 0 ? 'up' : 'down'
      }

      this.setData({
        klineTooltip: {
          x: Math.min(touch.clientX - rect.left, width - 130),
          y: 10,
          date: k.date || '',
          open: k.open != null ? k.open.toFixed(2) : 'N/A',
          high: k.high != null ? k.high.toFixed(2) : 'N/A',
          low: k.low != null ? k.low.toFixed(2) : 'N/A',
          close: k.close != null ? k.close.toFixed(2) : 'N/A',
          change: change !== null ? change : 'N/A',
          changeColor
        }
      })
    }).exec()
  },

  onKlineTouchEnd() {
    this.setData({ klineTooltip: null })
  },

  goBack() {
    wx.navigateBack()
  },

  goToMainSystem() {
    wx.showModal({
      title: '多因子评分系统',
      content: '请在浏览器中打开：auto-claw.top/reports',
      showCancel: true,
      confirmText: '复制链接',
      success: (res) => {
        if (res.confirm) {
          wx.setClipboardData({
            data: 'https://auto-claw.top/reports',
            success: () => {
              wx.showToast({ title: '链接已复制', icon: 'success' })
            }
          })
        }
      }
    })
  },

  // 绘制季度趋势图
  drawTrendChart() {
    const result = this.data.result
    if (!result || !result.scores) return

    const ctx = wx.createCanvasContext('trendCanvas', this)
    const query = wx.createSelectorQuery().in(this)
    query.select('.trend-canvas').boundingClientRect((rect) => {
      if (!rect) return
      const width = rect.width
      const height = rect.height

      const padding = { left: 40, right: 15, top: 15, bottom: 30 }
      const chartW = width - padding.left - padding.right
      const chartH = height - padding.top - padding.bottom

      // 数据：上上季度、上季度、本季度
      const quarters = ['上上季度', '上季度', '本季度']
      const totalScores = quarters.map(q => result.scores[q]?.total || 0)
      const yingshouScores = quarters.map(q => result.scores[q]?.营收 || 0)
      const guimuScores = quarters.map(q => result.scores[q]?.归母 || 0)
      const koufeiScores = quarters.map(q => result.scores[q]?.扣非 || 0)

      // Y轴范围：-10 到 20
      const minY = -10
      const maxY = 20
      const yRange = maxY - minY

      const yToPrice = (val) => {
        return padding.top + chartH * (1 - (val - minY) / yRange)
      }

      // 背景
      ctx.setFillStyle('#fff')
      ctx.fillRect(0, 0, width, height)

      // Y轴网格线
      ctx.setStrokeStyle('#f0f0f0')
      ctx.setLineWidth(0.5)
      for (let i = 0; i <= 6; i++) {
        const y = padding.top + (chartH / 6) * i
        ctx.beginPath()
        ctx.moveTo(padding.left, y)
        ctx.lineTo(width - padding.right, y)
        ctx.stroke()
      }

      // Y轴标签
      ctx.setFillStyle('#999')
      ctx.setFontSize(10)
      ctx.setTextAlign('right')
      for (let i = 0; i <= 6; i++) {
        const val = maxY - (yRange / 6) * i
        const y = padding.top + (chartH / 6) * i
        ctx.fillText(val.toFixed(0), padding.left - 5, y + 3)
      }

      // X轴
      ctx.setStrokeStyle('#ddd')
      ctx.setLineWidth(1)
      ctx.beginPath()
      ctx.moveTo(padding.left, padding.top)
      ctx.lineTo(padding.left, height - padding.bottom)
      ctx.lineTo(width - padding.right, height - padding.bottom)
      ctx.stroke()

      // X轴标签
      ctx.setFillStyle('#666')
      ctx.setFontSize(11)
      ctx.setTextAlign('center')
      const xStep = chartW / 2
      quarters.forEach((q, i) => {
        const x = padding.left + xStep * i + xStep / 2
        ctx.fillText(q, x, height - 8)
      })

      // 绘制线条的函数
      const drawLine = (scores, color, width) => {
        ctx.setStrokeStyle(color)
        ctx.setLineWidth(width)
        ctx.beginPath()
        scores.forEach((s, i) => {
          const x = padding.left + xStep * i + xStep / 2
          const y = yToPrice(s)
          if (i === 0) {
            ctx.moveTo(x, y)
          } else {
            ctx.lineTo(x, y)
          }
        })
        ctx.stroke()

        // 绘制点
        scores.forEach((s, i) => {
          const x = padding.left + xStep * i + xStep / 2
          const y = yToPrice(s)
          ctx.beginPath()
          ctx.arc(x, y, 4, 0, 2 * Math.PI)
          ctx.setFillStyle(color)
          ctx.fill()
          ctx.setStrokeStyle('#fff')
          ctx.setLineWidth(1.5)
          ctx.stroke()
        })
      }

      // 按顺序绘制：总分、营收、归母、扣非
      drawLine(totalScores, '#007AFF', 2.5)  // 蓝色-总分
      drawLine(yingshouScores, '#34C759', 2)  // 绿色-营收
      drawLine(guimuScores, '#FF9500', 2)     // 橙色-归母
      drawLine(koufeiScores, '#FF3B30', 2)   // 红色-扣非

      // 图例
      const legends = [
        { name: '总分', color: '#007AFF' },
        { name: '营收', color: '#34C759' },
        { name: '归母', color: '#FF9500' },
        { name: '扣非', color: '#FF3B30' }
      ]
      const legendStartX = padding.left + 10
      const legendY = height - padding.bottom + 15
      ctx.setFontSize(10)
      legends.forEach((legend, i) => {
        const x = legendStartX + i * 55
        ctx.setFillStyle(legend.color)
        ctx.fillRect(x, legendY - 5, 10, 3)
        ctx.setFillStyle('#666')
        ctx.setTextAlign('left')
        ctx.fillText(legend.name, x + 14, legendY)
      })

      ctx.draw()
    }).exec()
  }
})
