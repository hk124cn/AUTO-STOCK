// index.js
const app = getApp()

Page({
  data: {
    stockCode: '',
    refreshData: false,
    loading: false,
    error: '',
    result: null,
    searchResults: [],
    showDropdown: false,
    searchLoading: false,
    // 评分相关
    currentScoreTotal: 0,
    scoreClass: 'poor',
    trend: 'stable',
    trendText: '',
    currentReportDate: '',
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

  _searchDebounceTimer: null,
  _klineRawData: null,

  onSearchInput(e) {
    this.setData({ stockCode: e.detail.value })
    this.doSearchDebounce(e.detail.value)
  },

  doSearchDebounce(query) {
    clearTimeout(this._searchDebounceTimer)
    if (query.length < 2) {
      this.setData({ searchResults: [], showDropdown: false })
      return
    }
    this.setData({ searchLoading: true, showDropdown: true })
    this._searchDebounceTimer = setTimeout(() => {
      this.doSearch(query)
    }, 300)
  },

  doSearch(query) {
    wx.request({
      url: `${app.globalData.apiBase}/stock/search`,
      data: { q: query, limit: 10 },
      success: (res) => {
        this.setData({ searchResults: res.data || [] })
      },
      fail: () => {
        this.setData({ searchResults: [] })
      },
      complete: () => {
        this.setData({ searchLoading: false })
      }
    })
  },

  selectStock(e) {
    const rawCode = e.currentTarget.dataset.code
    const name = e.currentTarget.dataset.name
    // 确保6位代码
    const code = String(rawCode).trim().padStart(6, '0')
    this.setData({
      stockCode: code,
      showDropdown: false,
      searchResults: []
    })
    this.performSearch(code)
  },

  toggleRefresh() {
    this.setData({ refreshData: !this.data.refreshData })
  },

  search() {
    const code = this.data.stockCode.trim()
    if (!code) {
      this.setData({ error: '请输入股票代码' })
      return
    }
    this.performSearch(code)
  },

  performSearch(code) {
    if (!code) return

    let codeStr = String(code).trim()
    // 补零确保6位
    if (/^\d{1,5}$/.test(codeStr)) {
      codeStr = codeStr.padStart(6, '0')
    }
    if (!/^\d{6}$/.test(codeStr)) {
      this.setData({ error: '请输入6位数字的股票代码' })
      return
    }

    this.setData({ loading: true, error: '', showKline: false, klineData: null })

    const url = this.data.refreshData
      ? `${app.globalData.apiBase}/financial/score/${codeStr}?refresh=true`
      : `${app.globalData.apiBase}/financial/score/${codeStr}`

    wx.request({
      url,
      success: (res) => {
        const result = res.data
        const quarterScores = result && result.scores ? result.scores['本季度'] : null
        const quarter = quarterScores || { total: 0 }
        const currentScoreTotal = quarter.total
        let scoreClass = 'poor'
        if (currentScoreTotal >= 15) scoreClass = 'excellent'
        else if (currentScoreTotal >= 5) scoreClass = 'good'

        const quarterTrendsObj = result && result.quarter_trends ? result.quarter_trends['本季度'] : null
        const quarterTrends = quarterTrendsObj || {}
        const trend = quarterTrends.trend || 'stable'
        const trendText = quarterTrends.trend_text || ''
        const currentReportDate = quarter.report_date || ''

        this.setData({
          result,
          currentScoreTotal,
          scoreClass,
          trend,
          trendText,
          currentReportDate
        })

        // 评分获取后加载K线
        this.loadKline()
      },
      fail: (err) => {
        this.setData({ error: err.errMsg || '查询失败', result: null })
      },
      complete: () => {
        this.setData({ loading: false })
      }
    })
  },

  // ========== K线功能 ==========

  toggleView() {
    if (!this.data.showKline) {
      this.setData({ showKline: true })
      // 翻转到背面后绘制K线
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
      data: { quarter: '本季度' },
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
    if (!data || !data.kline || !data.kline.length) return

    const kline = data.kline
    const prevClose = data.prev_close
    const ctx = wx.createCanvasContext('klineCanvas', this)

    // 获取canvas尺寸
    const query = wx.createSelectorQuery().in(this)
    query.select('.kline-canvas').boundingClientRect((rect) => {
      if (!rect || rect.width <= 0 || rect.height <= 0) return
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
        minPrice = prevClose ? prevClose * 0.9 : 0
        maxPrice = prevClose ? prevClose * 1.1 : 100
      }
      // 添加5%边距
      const priceRange = maxPrice - minPrice
      minPrice = minPrice - priceRange * 0.05
      maxPrice = maxPrice + priceRange * 0.05

      // 绘制背景
      ctx.setFillStyle('#fff')
      ctx.fillRect(0, 0, width, height)

      // 绘制网格线
      ctx.setStrokeStyle('#f0f0f0')
      ctx.setLineWidth(0.5)
      for (let i = 0; i <= 4; i++) {
        const y = padding.top + (chartH / 4) * i
        ctx.beginPath()
        ctx.moveTo(padding.left, y)
        ctx.lineTo(width - padding.right, y)
        ctx.stroke()
      }

      // 价格映射函数
      const priceToY = (price) => {
        return padding.top + chartH * (1 - (price - minPrice) / (maxPrice - minPrice))
      }

      // 绘制蜡烛
      kline.forEach((k, i) => {
        const x = padding.left + gap * i + gap / 2
        const isUp = k.close >= k.open
        const color = isUp ? '#ef232a' : '#14b143'

        // 影线
        if (k.high != null && k.low != null) {
          ctx.setStrokeStyle(color)
          ctx.setLineWidth(1)
          ctx.beginPath()
          ctx.moveTo(x, priceToY(k.high))
          ctx.lineTo(x, priceToY(k.low))
          ctx.stroke()
        }

        // 实体
        if (k.open != null && k.close != null) {
          const yOpen = priceToY(k.open)
          const yClose = priceToY(k.close)
          const bodyTop = Math.min(yOpen, yClose)
          const bodyH = Math.max(Math.abs(yOpen - yClose), 1)

          ctx.setFillStyle(color)
          ctx.fillRect(x - candleW / 2, bodyTop, candleW, bodyH)
        }
      })

      // 绘制日期标签
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

  goToDetail() {
    if (this.data.result) {
      wx.navigateTo({
        url: `/pages/detail/detail?code=${this.data.result.code}`
      })
    }
  },

  goToMainSystem() {
    wx.navigateTo({
      url: '/pages/reports/reports'
    })
  }
})
