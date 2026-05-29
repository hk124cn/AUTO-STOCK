<template>
  <div id="app">
    <StockKline />
  </div>
</template>

<script setup>
import StockKline from './views/StockKline.vue'
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
  background: #1a1a2e;
  color: #eee;
  min-height: 100vh;
}
#app { min-height: 100vh; }
</style>