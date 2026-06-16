import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  base: '/',
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    minify: false
  },
  server: {
    host: '0.0.0.0',
    port: 3002,
    allowedHosts: ['stock.auto-claw.top'],
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/data': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
