// reports.js - 多因子评分报告页面
const app = getApp()

Page({
  data: {
    loading: true,
    error: '',
    hasData: false,
    date: '',
    totalCount: 0,
    // 大盘概览
    maxScore: 0,
    minScore: 0,
    avgScore: 0,
    medianScore: 0,
    // 评分分布
    distribution: [],
    // TOP榜单
    topList: [],
    // 各因子单项冠军
    champions: [],
    // 自选股
    selfCount: 0,
    selfAvg: 0,
    selfStocks: [],
    // 特别关注股票
    focusStocks: [],
    // 搜索
    searchKey: '',
    searchResults: []
  },

  onLoad() {
    this.loadReports()
  },

  onShow() {
    // 刷新数据
  },

  loadReports() {
    this.setData({ loading: true, error: '' })

    wx.request({
      url: `${app.globalData.apiBase}/reports/today`,
      success: (res) => {
        if (res.statusCode === 404) {
          this.setData({ error: res.data.error || '今日报告不存在', loading: false })
          return
        }
        if (res.statusCode !== 200) {
          this.setData({ error: '加载失败', loading: false })
          return
        }

        const data = res.data.data
        const count = data.length

        // 计算统计数据
        const scores = data.map(r => parseFloat(r.total_score || 0))
        const sortedScores = [...scores].sort((a, b) => a - b)
        const maxScore = Math.max(...scores).toFixed(2)
        const minScore = Math.min(...scores).toFixed(2)
        const avgScore = (scores.reduce((a, b) => a + b, 0) / count).toFixed(2)
        const medianScore = sortedScores[Math.floor(count / 2)].toFixed(2)

        // 评分分布
        const buckets = { '90+': 0, '80-90': 0, '70-80': 0, '60-70': 0, '50-60': 0, '40-50': 0, '30-40': 0, '20-30': 0, '10-20': 0, '10以下': 0 }
        scores.forEach(s => {
          if (s >= 90) buckets['90+']++
          else if (s >= 80) buckets['80-90']++
          else if (s >= 70) buckets['70-80']++
          else if (s >= 60) buckets['60-70']++
          else if (s >= 50) buckets['50-60']++
          else if (s >= 40) buckets['40-50']++
          else if (s >= 30) buckets['30-40']++
          else if (s >= 20) buckets['20-30']++
          else if (s >= 10) buckets['10-20']++
          else buckets['10以下']++
        })
        const distribution = Object.entries(buckets).map(([name, cnt]) => ({
          name,
          count: cnt,
          pct: (cnt / count * 100).toFixed(1)
        }))

        // TOP 10
        const sortedData = [...data].sort((a, b) => parseFloat(b.total_score || 0) - parseFloat(a.total_score || 0))
        const topList = sortedData.slice(0, 10).map((r, i) => ({
          rank: i + 1,
          code: r.code,
          name: r.name,
          score: parseFloat(r.total_score || 0).toFixed(2),
          scoreClass: this.getScoreClass(parseFloat(r.total_score || 0))
        }))

        // 各因子单项冠军
        const factorNames = ['关注度', '单日涨跌幅', '股息率', '今年相对大盘强弱', '财报', '5日涨跌幅', '行业相对强弱', '新闻', '资金流向']
        const champions = factorNames.map(f => {
          const best = data.reduce((prev, curr) => (parseFloat(curr[f] || 0) > parseFloat(prev[f] || 0)) ? curr : prev)
          return {
            factor: f,
            code: best.code,
            name: best.name,
            score: parseFloat(best[f] || 0).toFixed(2)
          }
        })

        // 自选股（从data中筛选，假设self_stocks在localStorage）
        let selfStocks = []
        let selfCount = 0
        let selfAvg = '0.00'
        try {
          const selfCodes = wx.getStorageSync('self_stocks') || []
          if (selfCodes.length > 0) {
            const selfData = data.filter(r => selfCodes.includes(r.code))
            selfCount = selfData.length
            if (selfData.length > 0) {
              const selfScores = selfData.map(r => parseFloat(r.total_score || 0))
              selfAvg = (selfScores.reduce((a, b) => a + b, 0) / selfData.length).toFixed(2)
            }
            selfStocks = selfData.sort((a, b) => parseFloat(b.total_score || 0) - parseFloat(a.total_score || 0)).slice(0, 10).map((r, i) => ({
              rank: i + 1,
              code: r.code,
              name: r.name,
              score: parseFloat(r.total_score || 0).toFixed(2),
              scoreClass: this.getScoreClass(parseFloat(r.total_score || 0))
            }))
          }
        } catch (e) {}

        // 特别关注股票
        let focusStocks = []
        try {
          const focusCodes = wx.getStorageSync('focus_stocks') || []
          if (focusCodes.length > 0) {
            focusStocks = focusCodes.map(code => {
              const stock = data.find(r => r.code === code)
              if (!stock) return null
              const totalScore = parseFloat(stock.total_score || 0)
              const factors = factorNames.map(f => {
                const val = parseFloat(stock[f] || 0)
                return {
                  name: f,
                  value: val.toFixed(2),
                  change: '0.00',
                  changeClass: '',
                  status: val >= 7 ? '强' : (val >= 4 ? '中' : '弱'),
                  statusClass: val >= 7 ? 'sg' : (val >= 4 ? 'sm' : 'sb')
                }
              })
              return {
                code: stock.code,
                name: stock.name,
                totalScore: totalScore.toFixed(2),
                factors,
                history: [],
                changeDesc: '',
                rank: 0,
                total: count,
                strongFactors: '',
                weakFactors: ''
              }
            }).filter(s => s !== null)
          }
        } catch (e) {}

        this.setData({
          loading: false,
          hasData: true,
          date: res.data.date,
          totalCount: count,
          maxScore, minScore, avgScore, medianScore,
          distribution,
          topList,
          champions,
          selfCount, selfAvg, selfStocks,
          focusStocks
        })
      },
      fail: (err) => {
        this.setData({ error: '网络错误', loading: false })
      }
    })
  },

  getScoreClass(score) {
    return score >= 60 ? 'gs' : (score >= 40 ? 'gm' : 'gb')
  },

  onSearchInput(e) {
    this.setData({ searchKey: e.detail.value })
  },

  onSearch() {
    const key = this.data.searchKey.trim().toLowerCase()
    if (key.length < 2) {
      this.setData({ searchResults: [] })
      return
    }

    wx.request({
      url: `${app.globalData.apiBase}/reports/search?q=${key}`,
      success: (res) => {
        if (res.data && res.data.data) {
          this.setData({
            searchResults: res.data.data.map(r => ({
              code: r.code,
              name: r.name,
              score: parseFloat(r.total_score || 0).toFixed(2),
              scoreClass: this.getScoreClass(parseFloat(r.total_score || 0))
            }))
          })
        }
      }
    })
  },

  viewStock(e) {
    const rawCode = e.currentTarget.dataset.code
    // 确保6位代码
    const code = String(rawCode).trim().padStart(6, '0')
    wx.navigateTo({
      url: `/pages/detail/detail?code=${code}`
    })
  }
})