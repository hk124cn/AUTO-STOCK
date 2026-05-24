// webview.js
Page({
  data: {
    url: ''
  },

  onLoad(options) {
    if (options.url) {
      this.setData({ url: decodeURIComponent(options.url) })
    } else {
      this.setData({ url: 'https://auto-claw.top/reports' })
    }
  }
})