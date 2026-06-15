const __vite__mapDeps=(i,m=__vite__mapDeps,d=(m.f||(m.f=["assets/loader-iyL5bcsQ.js","assets/index-CBDHGmro.js","assets/index-Bvo5RvaK.css"])))=>i.map(i=>d[i]);
import { _ as _export_sfc, k as watch, o as onMounted, l as onUnmounted, a as openBlock, c as createElementBlock, b as createBaseVNode, n as normalizeClass, i as createCommentVNode, t as toDisplayString, u as unref, e as createTextVNode, F as Fragment, r as renderList, m as withModifiers, h as withDirectives, v as vModelText, f as ref, p as reactive, q as authedFetch, j as computed, s as __vitePreload } from "./index-CBDHGmro.js";
import { s as smartFetch, f as formatMoney, b as getChangeClass, d as formatPercent, e as loadPositions, h as loadTrades, i as loadStats, j as getCacheTTL, k as getMarketState, g as gotoYujing, a as formatNumber } from "./loader-iyL5bcsQ.js";
const API_BASE = "/api/v1";
async function loadStrategy(mode = "SIM", forceRefresh = false) {
  const result = await smartFetch(
    `strategy:${mode}`,
    async () => {
      const r = await fetch(`${API_BASE}/portfolio/strategy?mode=${mode}`);
      if (!r.ok) throw new Error("HTTP " + r.status);
      return await r.json();
    },
    { dataType: "T1_DATA", forceRefresh }
  );
  return result.data;
}
const _hoisted_1 = { class: "portfolio-page" };
const _hoisted_2 = { class: "tabs-bar" };
const _hoisted_3 = {
  key: 0,
  class: "tab-badge"
};
const _hoisted_4 = {
  key: 0,
  class: "tab-badge"
};
const _hoisted_5 = { class: "stats-grid" };
const _hoisted_6 = { class: "stat-card" };
const _hoisted_7 = { class: "stat-info" };
const _hoisted_8 = { class: "stat-value" };
const _hoisted_9 = { class: "stat-card" };
const _hoisted_10 = { class: "stat-info" };
const _hoisted_11 = { class: "stat-card" };
const _hoisted_12 = { class: "stat-info" };
const _hoisted_13 = { class: "stat-value" };
const _hoisted_14 = { class: "stat-card" };
const _hoisted_15 = { class: "stat-info" };
const _hoisted_16 = { class: "stat-value" };
const _hoisted_17 = { class: "action-bar" };
const _hoisted_18 = ["disabled"];
const _hoisted_19 = {
  key: 0,
  class: "cache-info"
};
const _hoisted_20 = {
  key: 0,
  class: "error-banner"
};
const _hoisted_21 = {
  key: 1,
  class: "info-banner"
};
const _hoisted_22 = {
  key: 2,
  class: "info-banner real"
};
const _hoisted_23 = { class: "card" };
const _hoisted_24 = { class: "card-title" };
const _hoisted_25 = {
  key: 0,
  class: "loading"
};
const _hoisted_26 = {
  key: 1,
  class: "empty"
};
const _hoisted_27 = {
  key: 2,
  class: "data-table"
};
const _hoisted_28 = ["onClick"];
const _hoisted_29 = ["onClick"];
const _hoisted_30 = ["onClick"];
const _hoisted_31 = { class: "card" };
const _hoisted_32 = { class: "card-title" };
const _hoisted_33 = {
  key: 0,
  class: "empty"
};
const _hoisted_34 = {
  key: 1,
  class: "data-table"
};
const _hoisted_35 = ["onClick"];
const _hoisted_36 = ["onClick"];
const _hoisted_37 = ["onClick", "disabled"];
const _hoisted_38 = { class: "modal" };
const _hoisted_39 = { class: "modal-header" };
const _hoisted_40 = { class: "modal-body" };
const _hoisted_41 = { class: "form-group" };
const _hoisted_42 = { class: "form-group" };
const _hoisted_43 = { class: "form-group" };
const _hoisted_44 = { class: "form-group" };
const _hoisted_45 = { class: "form-group" };
const _hoisted_46 = { class: "form-group" };
const _hoisted_47 = {
  key: 0,
  class: "form-error"
};
const _hoisted_48 = {
  key: 1,
  class: "form-info"
};
const _hoisted_49 = { class: "modal-footer" };
const _hoisted_50 = ["disabled"];
const _hoisted_51 = { class: "modal" };
const _hoisted_52 = { class: "modal-header" };
const _hoisted_53 = { class: "modal-body" };
const _hoisted_54 = {
  key: 0,
  class: "info-row"
};
const _hoisted_55 = { class: "form-group" };
const _hoisted_56 = { class: "form-group" };
const _hoisted_57 = ["max"];
const _hoisted_58 = { class: "form-group" };
const _hoisted_59 = {
  key: 1,
  class: "form-error"
};
const _hoisted_60 = {
  key: 2,
  class: "form-info"
};
const _hoisted_61 = { class: "modal-footer" };
const _hoisted_62 = ["disabled"];
const _hoisted_63 = { class: "modal" };
const _hoisted_64 = { class: "modal-header" };
const _hoisted_65 = { class: "modal-body" };
const _hoisted_66 = { class: "form-group" };
const _hoisted_67 = { class: "form-group" };
const _hoisted_68 = {
  key: 0,
  class: "form-error"
};
const _hoisted_69 = { class: "modal-footer" };
const _hoisted_70 = ["disabled"];
const _sfc_main = {
  __name: "Portfolio",
  setup(__props) {
    const activeTab = ref("SIM");
    const loading = ref(true);
    const refreshing = ref(false);
    const submitting = ref(false);
    const errorMsg = ref("");
    const positions = ref([]);
    const trades = ref([]);
    const stats = ref({});
    const showBuyModal = ref(false);
    const showSellModal = ref(false);
    const showCapitalModal = ref(false);
    const sellPos = ref(null);
    const deletingTrade = ref(null);
    const capitalError = ref("");
    const lastUpdate = ref("");
    const cacheNote = ref("");
    const cacheInfo = reactive({ sim: false, real: false });
    const currentStrategy = ref(null);
    const buyForm = reactive({ code: "", name: "", price: "", shares: "", score: "", reason: "" });
    const sellForm = reactive({ price: "", shares: "", reason: "" });
    const capitalForm = reactive({ amount: "" });
    const buyValidationError = ref("");
    const isBuyValid = computed(() => !buyValidationError.value && buyForm.code && buyForm.name && buyForm.price && buyForm.shares);
    function validateBuyForm() {
      buyValidationError.value = "";
      const price = Number(buyForm.price);
      const shares = Number(buyForm.shares);
      if (!buyForm.code) return;
      if (isNaN(price) || price <= 0) {
        buyValidationError.value = "价格必须为正数";
        return;
      }
      if (isNaN(shares) || shares < 100) {
        buyValidationError.value = "A 股最小买入 100 股";
        return;
      }
      if (shares % 100 !== 0) {
        buyValidationError.value = "A 股必须为 100 整数倍";
      }
    }
    const buyFormTotal = computed(() => {
      const p = Number(buyForm.price);
      const s = Number(buyForm.shares);
      if (!p || !s) return 0;
      return p * s + Math.max(p * s * 15e-5, 5);
    });
    const buyFormFee = computed(() => {
      const p = Number(buyForm.price);
      const s = Number(buyForm.shares);
      if (!p || !s) return 0;
      return Math.max(p * s * 15e-5, 5);
    });
    const sellValidationError = ref("");
    const isSellValid = computed(() => !sellValidationError.value && sellForm.price && sellForm.shares);
    function validateSellForm() {
      sellValidationError.value = "";
      if (!sellPos.value) return;
      const price = Number(sellForm.price);
      const shares = Number(sellForm.shares);
      if (isNaN(price) || price <= 0) {
        sellValidationError.value = "价格必须为正数";
        return;
      }
      if (isNaN(shares) || shares < 100) {
        sellValidationError.value = "A 股最小卖出 100 股";
        return;
      }
      if (shares % 100 !== 0) {
        sellValidationError.value = "A 股必须为 100 整数倍";
        return;
      }
      if (shares > sellPos.value.shares) {
        sellValidationError.value = `卖出数量不能超过持仓 ${sellPos.value.shares}`;
      }
    }
    const sellFormEstimate = computed(() => {
      if (!sellPos.value) return "";
      const price = Number(sellForm.price);
      const shares = Number(sellForm.shares);
      if (!price || !shares) return "";
      const amount = price * shares;
      const commission = Math.max(amount * 15e-5, 5);
      const stamp_tax = amount * 1e-3;
      const net = amount - commission - stamp_tax;
      const cost = sellPos.value.cost_price * shares;
      const profit = net - cost;
      const profitRate = (profit / cost * 100).toFixed(2);
      return `预计到手: ¥${formatNumber(net)} | 预计盈亏: ¥${formatNumber(profit)} (${profitRate}%)`;
    });
    async function fetchData(force = false) {
      const mode = activeTab.value;
      try {
        const [pos, tradeList, stat, strategy] = await Promise.all([
          loadPositions(mode, force),
          loadTrades(mode, 50, force),
          loadStats(mode, force),
          loadStrategy(mode, force)
        ]);
        positions.value = pos;
        trades.value = tradeList;
        stats.value = stat;
        currentStrategy.value = strategy;
        lastUpdate.value = (/* @__PURE__ */ new Date()).toLocaleTimeString("zh-CN", { hour12: false });
        const ttl = getCacheTTL("REALTIME");
        const marketState = getMarketState();
        if (ttl >= 60 * 60 * 1e3) {
          cacheNote.value = "非交易时间，价格已锁定";
        } else if (ttl >= 5 * 60 * 1e3) {
          cacheNote.value = "盘前/午休，5 分钟刷新";
        } else {
          cacheNote.value = "交易中，30 秒刷新";
        }
        cacheInfo[mode === "SIM" ? "sim" : "real"] = !force;
      } catch (e) {
        errorMsg.value = "数据加载失败: " + e.message;
      }
    }
    watch(activeTab, (newTab, oldTab) => {
      if (newTab !== oldTab) {
        fetchData(false);
      }
    });
    let refreshTimer = null;
    function setupAutoRefresh() {
      if (refreshTimer) clearInterval(refreshTimer);
      const ttl = getCacheTTL("REALTIME");
      refreshTimer = setInterval(() => {
        fetchData(false);
      }, ttl);
    }
    function watchMarketState() {
      let lastState = getMarketState();
      setInterval(() => {
        const currentState = getMarketState();
        if (currentState !== lastState) {
          lastState = currentState;
          setupAutoRefresh();
          fetchData(true);
        }
      }, 60 * 1e3);
    }
    function openBuyModal() {
      Object.assign(buyForm, { code: "", name: "", price: "", shares: "", score: "", reason: "" });
      buyValidationError.value = "";
      showBuyModal.value = true;
    }
    function closeBuyModal() {
      showBuyModal.value = false;
    }
    function openSellModal(pos) {
      sellPos.value = pos;
      Object.assign(sellForm, { price: pos.current_price, shares: pos.shares, reason: "" });
      sellValidationError.value = "";
      showSellModal.value = true;
    }
    function openCapitalModal() {
      capitalForm.amount = stats.value.initial_capital || 1e6;
      capitalError.value = "";
      showCapitalModal.value = true;
    }
    const capitalValid = computed(() => {
      const n = Number(capitalForm.amount);
      return !isNaN(n) && n > 0;
    });
    async function confirmUpdateCapital() {
      if (!capitalValid.value) return;
      if (!confirm(`⚠️ 确认要将${activeTab.value === "SIM" ? "模拟仓" : "实盘"}重置为 ¥${capitalForm.amount} 吗？
这将清空所有持仓和交易记录。`)) {
        return;
      }
      submitting.value = true;
      try {
        const r = await authedFetch("/api/v1/portfolio/update-capital", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            initial_capital: Number(capitalForm.amount),
            mode: activeTab.value
          })
        });
        const data = await r.json();
        if (data.success) {
          showCapitalModal.value = false;
          const { clearAllCache } = await __vitePreload(async () => {
            const { clearAllCache: clearAllCache2 } = await import("./loader-iyL5bcsQ.js").then((n) => n.n);
            return { clearAllCache: clearAllCache2 };
          }, true ? __vite__mapDeps([0,1,2]) : void 0);
          clearAllCache();
          await fetchData(true);
        } else {
          capitalError.value = data.error || "重置失败";
        }
      } catch (e) {
        capitalError.value = "网络错误: " + e.message;
      } finally {
        submitting.value = false;
      }
    }
    async function deleteTradeConfirm(trade) {
      const action = trade.type === "BUY" ? "买入" : "卖出";
      if (!confirm(`确认删除这条${action}记录？

${trade.trade_date}  ${trade.code} ${trade.name}  ${trade.shares}股 @ ¥${trade.price}

⚠️ 删除将反转该交易对账户和持仓的影响。`)) {
        return;
      }
      deletingTrade.value = trade.id;
      try {
        const r = await authedFetch("/api/v1/portfolio/delete-trade", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            trade_id: trade.id,
            mode: activeTab.value
          })
        });
        const data = await r.json();
        if (data.success) {
          await fetchData(true);
        } else {
          alert("删除失败: " + (data.error || "未知错误"));
        }
      } catch (e) {
        alert("网络错误: " + e.message);
      } finally {
        deletingTrade.value = null;
      }
    }
    async function refreshPrices() {
      if (positions.value.length === 0) return;
      refreshing.value = true;
      try {
        const resp = await fetch("/data/score_price_history.csv?_t=" + Date.now());
        const text = await resp.text();
        const lines = text.trim().split("\n");
        if (lines.length < 2) return;
        const headers = lines[0].split(",");
        const dateIdx = headers.indexOf("date");
        const codeIdx = headers.indexOf("code");
        const priceIdx = headers.indexOf("close_price");
        if (dateIdx < 0 || codeIdx < 0 || priceIdx < 0) {
          errorMsg.value = "价格数据格式错误";
          return;
        }
        const dateSet = /* @__PURE__ */ new Set();
        const latestByCode = {};
        for (let i = 1; i < lines.length; i++) {
          const vals = lines[i].split(",");
          const d = vals[dateIdx];
          const c = vals[codeIdx];
          const p = parseFloat(vals[priceIdx]);
          if (c && !isNaN(p)) {
            latestByCode[c] = { date: d, price: p };
            dateSet.add(d);
          }
        }
        const latestDate = [...dateSet].sort().pop();
        const prices = {};
        for (const pos of positions.value) {
          const data = latestByCode[pos.code];
          if (data && data.date === latestDate) {
            prices[pos.code] = data.price;
          }
        }
        if (Object.keys(prices).length > 0) {
          const url = `/api/v1/portfolio/update-prices?mode=${activeTab.value}`;
          await authedFetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prices })
          });
          await fetchData(true);
        } else {
          errorMsg.value = "未找到最新价格数据";
        }
      } catch (e) {
        errorMsg.value = "刷新失败: " + e.message;
      } finally {
        refreshing.value = false;
      }
    }
    async function confirmBuy() {
      if (!isBuyValid.value) return;
      submitting.value = true;
      try {
        const r = await authedFetch("/api/v1/portfolio/buy", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            code: buyForm.code,
            name: buyForm.name,
            price: Number(buyForm.price),
            shares: Number(buyForm.shares),
            score: buyForm.score ? Number(buyForm.score) : null,
            reason: buyForm.reason || null,
            mode: activeTab.value
          })
        });
        const data = await r.json();
        if (data.success) {
          closeBuyModal();
          await fetchData(true);
        } else {
          buyValidationError.value = data.error || "买入失败";
        }
      } catch (e) {
        buyValidationError.value = "网络错误: " + e.message;
      } finally {
        submitting.value = false;
      }
    }
    async function confirmSell() {
      if (!isSellValid.value) return;
      submitting.value = true;
      try {
        const r = await authedFetch("/api/v1/portfolio/sell", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            code: sellPos.value.code,
            price: Number(sellForm.price),
            shares: Number(sellForm.shares),
            reason: sellForm.reason || null,
            mode: activeTab.value
          })
        });
        const data = await r.json();
        if (data.success) {
          showSellModal.value = false;
          await fetchData(true);
        } else {
          sellValidationError.value = data.error || "卖出失败";
        }
      } catch (e) {
        sellValidationError.value = "网络错误: " + e.message;
      } finally {
        submitting.value = false;
      }
    }
    onMounted(async () => {
      await fetchData(false);
      loading.value = false;
      setupAutoRefresh();
      watchMarketState();
    });
    function gotoYujingWithPosition(code) {
      const pos = positions.value.find((p) => p.code === code);
      if (!pos) {
        gotoYujing(code);
        return;
      }
      const strategy = currentStrategy.value;
      const opts = {
        cost: pos.cost_price
      };
      if (strategy) {
        opts.tp = (strategy.take_profit * 100).toFixed(1);
        opts.sl = (strategy.stop_loss * 100).toFixed(1);
        opts.strategy = strategy.name;
      }
      gotoYujing(code, opts);
    }
    onUnmounted(() => {
      if (refreshTimer) clearInterval(refreshTimer);
    });
    return (_ctx, _cache) => {
      var _a, _b, _c;
      return openBlock(), createElementBlock("div", _hoisted_1, [
        _cache[49] || (_cache[49] = createBaseVNode("h1", { class: "page-title" }, "💼 持仓管理", -1)),
        createBaseVNode("div", _hoisted_2, [
          createBaseVNode("button", {
            class: normalizeClass(["tab-btn", { active: activeTab.value === "SIM" }]),
            onClick: _cache[0] || (_cache[0] = ($event) => activeTab.value = "SIM")
          }, [
            _cache[19] || (_cache[19] = createBaseVNode("span", { class: "tab-icon" }, "🎲", -1)),
            _cache[20] || (_cache[20] = createBaseVNode("span", null, "模拟仓（系统自动）", -1)),
            cacheInfo.sim ? (openBlock(), createElementBlock("span", _hoisted_3, "已缓存")) : createCommentVNode("", true)
          ], 2),
          createBaseVNode("button", {
            class: normalizeClass(["tab-btn", { active: activeTab.value === "REAL" }]),
            onClick: _cache[1] || (_cache[1] = ($event) => activeTab.value = "REAL")
          }, [
            _cache[21] || (_cache[21] = createBaseVNode("span", { class: "tab-icon" }, "💰", -1)),
            _cache[22] || (_cache[22] = createBaseVNode("span", null, "实盘（手动录入）", -1)),
            cacheInfo.real ? (openBlock(), createElementBlock("span", _hoisted_4, "已缓存")) : createCommentVNode("", true)
          ], 2)
        ]),
        createBaseVNode("div", _hoisted_5, [
          createBaseVNode("div", _hoisted_6, [
            _cache[24] || (_cache[24] = createBaseVNode("div", { class: "stat-icon" }, "💰", -1)),
            createBaseVNode("div", _hoisted_7, [
              createBaseVNode("div", _hoisted_8, toDisplayString(unref(formatMoney)(stats.value.total_assets)), 1),
              _cache[23] || (_cache[23] = createBaseVNode("div", { class: "stat-label" }, "总资产", -1))
            ])
          ]),
          createBaseVNode("div", _hoisted_9, [
            _cache[26] || (_cache[26] = createBaseVNode("div", { class: "stat-icon" }, "📈", -1)),
            createBaseVNode("div", _hoisted_10, [
              createBaseVNode("div", {
                class: normalizeClass(["stat-value", unref(getChangeClass)(stats.value.total_return)])
              }, toDisplayString(unref(formatPercent)(stats.value.total_return)), 3),
              _cache[25] || (_cache[25] = createBaseVNode("div", { class: "stat-label" }, "总收益率", -1))
            ])
          ]),
          createBaseVNode("div", _hoisted_11, [
            _cache[28] || (_cache[28] = createBaseVNode("div", { class: "stat-icon" }, "🏦", -1)),
            createBaseVNode("div", _hoisted_12, [
              createBaseVNode("div", _hoisted_13, toDisplayString(stats.value.position_count || 0), 1),
              _cache[27] || (_cache[27] = createBaseVNode("div", { class: "stat-label" }, "持仓数量", -1))
            ])
          ]),
          createBaseVNode("div", _hoisted_14, [
            _cache[30] || (_cache[30] = createBaseVNode("div", { class: "stat-icon" }, "💵", -1)),
            createBaseVNode("div", _hoisted_15, [
              createBaseVNode("div", _hoisted_16, toDisplayString(unref(formatMoney)(stats.value.current_capital)), 1),
              _cache[29] || (_cache[29] = createBaseVNode("div", { class: "stat-label" }, "可用资金", -1))
            ])
          ])
        ]),
        createBaseVNode("div", _hoisted_17, [
          createBaseVNode("button", {
            class: "btn btn-primary",
            onClick: openBuyModal
          }, " ➕ 记录" + toDisplayString(activeTab.value === "SIM" ? "模拟" : "实盘") + "买入 ", 1),
          createBaseVNode("button", {
            class: "btn btn-outline",
            disabled: refreshing.value,
            onClick: refreshPrices
          }, toDisplayString(refreshing.value ? "刷新中..." : "🔄 刷新价格"), 9, _hoisted_18),
          createBaseVNode("button", {
            class: "btn btn-outline",
            onClick: openCapitalModal
          }, " 💰 修改总资产 "),
          lastUpdate.value ? (openBlock(), createElementBlock("span", _hoisted_19, " 上次更新: " + toDisplayString(lastUpdate.value) + " · " + toDisplayString(cacheNote.value), 1)) : createCommentVNode("", true)
        ]),
        errorMsg.value ? (openBlock(), createElementBlock("div", _hoisted_20, [
          createTextVNode(" ⚠️ " + toDisplayString(errorMsg.value) + " ", 1),
          createBaseVNode("button", {
            class: "btn-close",
            onClick: _cache[2] || (_cache[2] = ($event) => errorMsg.value = "")
          }, "✕")
        ])) : createCommentVNode("", true),
        activeTab.value === "SIM" ? (openBlock(), createElementBlock("div", _hoisted_21, " ℹ️ 模拟仓由系统每日根据信号自动交易（晚间流水线 19:00 执行）。止盈 20%，止损 8%，单股最大仓位 20%。 ")) : (openBlock(), createElementBlock("div", _hoisted_22, " ℹ️ 实盘用于记录您真实券商账户的交易。资金独立于模拟仓，请手动录入实际成交。 ")),
        createBaseVNode("div", _hoisted_23, [
          createBaseVNode("div", _hoisted_24, [
            _cache[31] || (_cache[31] = createBaseVNode("span", null, "📋", -1)),
            createBaseVNode("span", null, toDisplayString(activeTab.value === "SIM" ? "模拟仓" : "实盘") + "当前持仓", 1)
          ]),
          loading.value ? (openBlock(), createElementBlock("div", _hoisted_25, "加载中...")) : positions.value.length === 0 ? (openBlock(), createElementBlock("div", _hoisted_26, " 暂无" + toDisplayString(activeTab.value === "SIM" ? "模拟" : "实盘") + "持仓 ", 1)) : (openBlock(), createElementBlock("table", _hoisted_27, [
            _cache[32] || (_cache[32] = createBaseVNode("thead", null, [
              createBaseVNode("tr", null, [
                createBaseVNode("th", null, "代码"),
                createBaseVNode("th", null, "名称"),
                createBaseVNode("th", null, "持仓数量"),
                createBaseVNode("th", null, "成本价"),
                createBaseVNode("th", null, "现价"),
                createBaseVNode("th", null, "盈亏金额"),
                createBaseVNode("th", null, "收益率"),
                createBaseVNode("th", null, "操作")
              ])
            ], -1)),
            createBaseVNode("tbody", null, [
              (openBlock(true), createElementBlock(Fragment, null, renderList(positions.value, (pos) => {
                return openBlock(), createElementBlock("tr", {
                  key: pos.code
                }, [
                  createBaseVNode("td", {
                    class: "code",
                    onClick: ($event) => gotoYujingWithPosition(pos.code),
                    title: "点击查看个股详情（含成本价/止盈/止损）"
                  }, toDisplayString(pos.code), 9, _hoisted_28),
                  createBaseVNode("td", {
                    class: "name clickable",
                    onClick: ($event) => gotoYujingWithPosition(pos.code),
                    title: "点击查看个股详情（含成本价/止盈/止损）"
                  }, toDisplayString(pos.name), 9, _hoisted_29),
                  createBaseVNode("td", null, toDisplayString(pos.shares), 1),
                  createBaseVNode("td", null, toDisplayString(unref(formatMoney)(pos.cost_price)), 1),
                  createBaseVNode("td", null, toDisplayString(unref(formatMoney)(pos.current_price)), 1),
                  createBaseVNode("td", {
                    class: normalizeClass(unref(getChangeClass)(pos.profit))
                  }, toDisplayString(unref(formatMoney)(pos.profit)), 3),
                  createBaseVNode("td", {
                    class: normalizeClass(unref(getChangeClass)(pos.profit_rate))
                  }, toDisplayString(unref(formatPercent)(pos.profit_rate)), 3),
                  createBaseVNode("td", null, [
                    createBaseVNode("button", {
                      class: "btn btn-sm btn-danger",
                      onClick: ($event) => openSellModal(pos)
                    }, " 卖出 ", 8, _hoisted_30)
                  ])
                ]);
              }), 128))
            ])
          ]))
        ]),
        createBaseVNode("div", _hoisted_31, [
          createBaseVNode("div", _hoisted_32, [
            _cache[33] || (_cache[33] = createBaseVNode("span", null, "📝", -1)),
            createBaseVNode("span", null, "最近" + toDisplayString(activeTab.value === "SIM" ? "模拟" : "实盘") + "交易记录", 1)
          ]),
          trades.value.length === 0 ? (openBlock(), createElementBlock("div", _hoisted_33, " 暂无" + toDisplayString(activeTab.value === "SIM" ? "模拟" : "实盘") + "交易记录 ", 1)) : (openBlock(), createElementBlock("table", _hoisted_34, [
            _cache[34] || (_cache[34] = createBaseVNode("thead", null, [
              createBaseVNode("tr", null, [
                createBaseVNode("th", null, "日期"),
                createBaseVNode("th", null, "类型"),
                createBaseVNode("th", null, "代码"),
                createBaseVNode("th", null, "名称"),
                createBaseVNode("th", null, "价格"),
                createBaseVNode("th", null, "数量"),
                createBaseVNode("th", null, "金额"),
                createBaseVNode("th", null, "费用"),
                createBaseVNode("th", null, "操作")
              ])
            ], -1)),
            createBaseVNode("tbody", null, [
              (openBlock(true), createElementBlock(Fragment, null, renderList(trades.value, (trade) => {
                return openBlock(), createElementBlock("tr", {
                  key: trade.id
                }, [
                  createBaseVNode("td", null, toDisplayString(trade.trade_date), 1),
                  createBaseVNode("td", null, [
                    createBaseVNode("span", {
                      class: normalizeClass(trade.type === "BUY" ? "up" : "down")
                    }, toDisplayString(trade.type === "BUY" ? "买入" : "卖出"), 3)
                  ]),
                  createBaseVNode("td", {
                    class: "code",
                    onClick: ($event) => gotoYujingWithPosition(trade.code),
                    title: "点击查看个股详情"
                  }, toDisplayString(trade.code), 9, _hoisted_35),
                  createBaseVNode("td", {
                    class: "clickable",
                    onClick: ($event) => gotoYujingWithPosition(trade.code),
                    title: "点击查看个股详情"
                  }, toDisplayString(trade.name), 9, _hoisted_36),
                  createBaseVNode("td", null, toDisplayString(unref(formatMoney)(trade.price)), 1),
                  createBaseVNode("td", null, toDisplayString(trade.shares), 1),
                  createBaseVNode("td", null, toDisplayString(unref(formatMoney)(trade.amount)), 1),
                  createBaseVNode("td", null, toDisplayString(unref(formatMoney)(trade.fee + (trade.stamp_tax || 0))), 1),
                  createBaseVNode("td", null, [
                    createBaseVNode("button", {
                      class: "btn btn-sm btn-outline",
                      onClick: ($event) => deleteTradeConfirm(trade),
                      disabled: deletingTrade.value === trade.id,
                      title: "删除该交易记录"
                    }, toDisplayString(deletingTrade.value === trade.id ? "删除中..." : "🗑"), 9, _hoisted_37)
                  ])
                ]);
              }), 128))
            ])
          ]))
        ]),
        showBuyModal.value ? (openBlock(), createElementBlock("div", {
          key: 3,
          class: "modal-overlay",
          onClick: withModifiers(closeBuyModal, ["self"])
        }, [
          createBaseVNode("div", _hoisted_38, [
            createBaseVNode("div", _hoisted_39, [
              createBaseVNode("h3", null, "记录" + toDisplayString(activeTab.value === "SIM" ? "模拟" : "实盘") + "买入", 1),
              createBaseVNode("button", {
                class: "btn-close",
                onClick: closeBuyModal
              }, "✕")
            ]),
            createBaseVNode("div", _hoisted_40, [
              createBaseVNode("div", _hoisted_41, [
                _cache[35] || (_cache[35] = createBaseVNode("label", null, "股票代码", -1)),
                withDirectives(createBaseVNode("input", {
                  "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => buyForm.code = $event),
                  placeholder: "如 600519",
                  maxlength: "6",
                  onInput: validateBuyForm
                }, null, 544), [
                  [vModelText, buyForm.code]
                ])
              ]),
              createBaseVNode("div", _hoisted_42, [
                _cache[36] || (_cache[36] = createBaseVNode("label", null, "股票名称", -1)),
                withDirectives(createBaseVNode("input", {
                  "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => buyForm.name = $event),
                  placeholder: "如 贵州茅台"
                }, null, 512), [
                  [vModelText, buyForm.name]
                ])
              ]),
              createBaseVNode("div", _hoisted_43, [
                _cache[37] || (_cache[37] = createBaseVNode("label", null, "买入价格", -1)),
                withDirectives(createBaseVNode("input", {
                  "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => buyForm.price = $event),
                  type: "number",
                  step: "0.01",
                  min: "0.01",
                  placeholder: "买入价格",
                  onInput: validateBuyForm
                }, null, 544), [
                  [vModelText, buyForm.price]
                ])
              ]),
              createBaseVNode("div", _hoisted_44, [
                _cache[38] || (_cache[38] = createBaseVNode("label", null, "买入数量（A 股必须为 100 整数倍）", -1)),
                withDirectives(createBaseVNode("input", {
                  "onUpdate:modelValue": _cache[6] || (_cache[6] = ($event) => buyForm.shares = $event),
                  type: "number",
                  min: "100",
                  step: "100",
                  placeholder: "买入数量（股）",
                  onInput: validateBuyForm
                }, null, 544), [
                  [vModelText, buyForm.shares]
                ])
              ]),
              createBaseVNode("div", _hoisted_45, [
                _cache[39] || (_cache[39] = createBaseVNode("label", null, "评分（可选）", -1)),
                withDirectives(createBaseVNode("input", {
                  "onUpdate:modelValue": _cache[7] || (_cache[7] = ($event) => buyForm.score = $event),
                  type: "number",
                  step: "0.1",
                  placeholder: "评分"
                }, null, 512), [
                  [vModelText, buyForm.score]
                ])
              ]),
              createBaseVNode("div", _hoisted_46, [
                _cache[40] || (_cache[40] = createBaseVNode("label", null, "买入原因（可选）", -1)),
                withDirectives(createBaseVNode("input", {
                  "onUpdate:modelValue": _cache[8] || (_cache[8] = ($event) => buyForm.reason = $event),
                  placeholder: "买入原因"
                }, null, 512), [
                  [vModelText, buyForm.reason]
                ])
              ]),
              buyValidationError.value ? (openBlock(), createElementBlock("div", _hoisted_47, "⚠️ " + toDisplayString(buyValidationError.value), 1)) : createCommentVNode("", true),
              buyFormTotal.value ? (openBlock(), createElementBlock("div", _hoisted_48, " 预计金额: " + toDisplayString(unref(formatMoney)(buyFormTotal.value)) + "（含手续费 " + toDisplayString(unref(formatMoney)(buyFormFee.value)) + "） ", 1)) : createCommentVNode("", true)
            ]),
            createBaseVNode("div", _hoisted_49, [
              createBaseVNode("button", {
                class: "btn btn-outline",
                onClick: closeBuyModal
              }, "取消"),
              createBaseVNode("button", {
                class: "btn btn-primary",
                disabled: !isBuyValid.value || submitting.value,
                onClick: confirmBuy
              }, toDisplayString(submitting.value ? "提交中..." : "确认买入"), 9, _hoisted_50)
            ])
          ])
        ])) : createCommentVNode("", true),
        showSellModal.value ? (openBlock(), createElementBlock("div", {
          key: 4,
          class: "modal-overlay",
          onClick: _cache[14] || (_cache[14] = withModifiers(($event) => showSellModal.value = false, ["self"]))
        }, [
          createBaseVNode("div", _hoisted_51, [
            createBaseVNode("div", _hoisted_52, [
              createBaseVNode("h3", null, "记录" + toDisplayString(activeTab.value === "SIM" ? "模拟" : "实盘") + "卖出 - " + toDisplayString((_a = sellPos.value) == null ? void 0 : _a.name) + " (" + toDisplayString((_b = sellPos.value) == null ? void 0 : _b.code) + ")", 1),
              createBaseVNode("button", {
                class: "btn-close",
                onClick: _cache[9] || (_cache[9] = ($event) => showSellModal.value = false)
              }, "✕")
            ]),
            createBaseVNode("div", _hoisted_53, [
              sellPos.value ? (openBlock(), createElementBlock("div", _hoisted_54, [
                _cache[41] || (_cache[41] = createBaseVNode("span", null, "当前持仓:", -1)),
                createBaseVNode("strong", null, toDisplayString(sellPos.value.shares) + " 股", 1),
                _cache[42] || (_cache[42] = createBaseVNode("span", { class: "sep" }, "|", -1)),
                _cache[43] || (_cache[43] = createBaseVNode("span", null, "成本价:", -1)),
                createBaseVNode("strong", null, toDisplayString(unref(formatMoney)(sellPos.value.cost_price)), 1)
              ])) : createCommentVNode("", true),
              createBaseVNode("div", _hoisted_55, [
                _cache[44] || (_cache[44] = createBaseVNode("label", null, "卖出价格", -1)),
                withDirectives(createBaseVNode("input", {
                  "onUpdate:modelValue": _cache[10] || (_cache[10] = ($event) => sellForm.price = $event),
                  type: "number",
                  step: "0.01",
                  min: "0.01",
                  placeholder: "卖出价格",
                  onInput: validateSellForm
                }, null, 544), [
                  [vModelText, sellForm.price]
                ])
              ]),
              createBaseVNode("div", _hoisted_56, [
                _cache[45] || (_cache[45] = createBaseVNode("label", null, "卖出数量（A 股必须为 100 整数倍）", -1)),
                withDirectives(createBaseVNode("input", {
                  "onUpdate:modelValue": _cache[11] || (_cache[11] = ($event) => sellForm.shares = $event),
                  type: "number",
                  min: "100",
                  step: "100",
                  max: (_c = sellPos.value) == null ? void 0 : _c.shares,
                  placeholder: "卖出数量",
                  onInput: validateSellForm
                }, null, 40, _hoisted_57), [
                  [vModelText, sellForm.shares]
                ])
              ]),
              createBaseVNode("div", _hoisted_58, [
                _cache[46] || (_cache[46] = createBaseVNode("label", null, "卖出原因（可选）", -1)),
                withDirectives(createBaseVNode("input", {
                  "onUpdate:modelValue": _cache[12] || (_cache[12] = ($event) => sellForm.reason = $event),
                  placeholder: "如：止盈/止损"
                }, null, 512), [
                  [vModelText, sellForm.reason]
                ])
              ]),
              sellValidationError.value ? (openBlock(), createElementBlock("div", _hoisted_59, "⚠️ " + toDisplayString(sellValidationError.value), 1)) : createCommentVNode("", true),
              sellFormEstimate.value ? (openBlock(), createElementBlock("div", _hoisted_60, toDisplayString(sellFormEstimate.value), 1)) : createCommentVNode("", true)
            ]),
            createBaseVNode("div", _hoisted_61, [
              createBaseVNode("button", {
                class: "btn btn-outline",
                onClick: _cache[13] || (_cache[13] = ($event) => showSellModal.value = false)
              }, "取消"),
              createBaseVNode("button", {
                class: "btn btn-danger",
                disabled: !isSellValid.value || submitting.value,
                onClick: confirmSell
              }, toDisplayString(submitting.value ? "提交中..." : "确认卖出"), 9, _hoisted_62)
            ])
          ])
        ])) : createCommentVNode("", true),
        showCapitalModal.value ? (openBlock(), createElementBlock("div", {
          key: 5,
          class: "modal-overlay",
          onClick: _cache[18] || (_cache[18] = withModifiers(($event) => showCapitalModal.value = false, ["self"]))
        }, [
          createBaseVNode("div", _hoisted_63, [
            createBaseVNode("div", _hoisted_64, [
              createBaseVNode("h3", null, "修改" + toDisplayString(activeTab.value === "SIM" ? "模拟仓" : "实盘") + "总资产", 1),
              createBaseVNode("button", {
                class: "btn-close",
                onClick: _cache[15] || (_cache[15] = ($event) => showCapitalModal.value = false)
              }, "✕")
            ]),
            createBaseVNode("div", _hoisted_65, [
              createBaseVNode("div", _hoisted_66, [
                createBaseVNode("label", null, "当前总资产: " + toDisplayString(unref(formatMoney)(stats.value.total_assets)), 1)
              ]),
              createBaseVNode("div", _hoisted_67, [
                _cache[47] || (_cache[47] = createBaseVNode("label", null, "新的初始资金", -1)),
                withDirectives(createBaseVNode("input", {
                  "onUpdate:modelValue": _cache[16] || (_cache[16] = ($event) => capitalForm.amount = $event),
                  type: "number",
                  step: "10000",
                  min: "0",
                  placeholder: "如 1000000"
                }, null, 512), [
                  [vModelText, capitalForm.amount]
                ]),
                _cache[48] || (_cache[48] = createBaseVNode("div", { class: "form-hint" }, [
                  createTextVNode(" ⚠️ 修改初始资金会"),
                  createBaseVNode("strong", null, "重置整个账户"),
                  createTextVNode("（清空所有持仓、交易记录、净值快照）。仅用于调整模拟仓规模或重新开始。 ")
                ], -1))
              ]),
              capitalError.value ? (openBlock(), createElementBlock("div", _hoisted_68, "⚠️ " + toDisplayString(capitalError.value), 1)) : createCommentVNode("", true)
            ]),
            createBaseVNode("div", _hoisted_69, [
              createBaseVNode("button", {
                class: "btn btn-outline",
                onClick: _cache[17] || (_cache[17] = ($event) => showCapitalModal.value = false)
              }, "取消"),
              createBaseVNode("button", {
                class: "btn btn-danger",
                disabled: !capitalValid.value || submitting.value,
                onClick: confirmUpdateCapital
              }, toDisplayString(submitting.value ? "提交中..." : "确认重置"), 9, _hoisted_70)
            ])
          ])
        ])) : createCommentVNode("", true)
      ]);
    };
  }
};
const Portfolio = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-3b3dc764"]]);
export {
  Portfolio as default
};
