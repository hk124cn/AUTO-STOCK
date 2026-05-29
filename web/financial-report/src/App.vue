<template>
  <div class="app">
    <router-view />
  </div>
</template>

<script setup>
</script>

<style scoped>
.app {
  min-height: 100vh;
  background: #000;
}
</style>

<style>
/* 全局ECharts tooltip样式 */
html body .echarts-tooltip,
html body .echarts-tooltip * {
  background-color: rgba(28, 28, 30, 0.95) ;
  border-color: #38383A ;
  color: #fb9090 ;
  border-radius: 8px ;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3) ;
}
</style>