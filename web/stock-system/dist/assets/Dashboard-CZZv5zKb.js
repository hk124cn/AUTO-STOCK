import { g as getStrategyVersion, c as clearAllCache, l as loadStrategyVersions, a as loadSignals, b as gotoYujing, f as formatMoney, d as formatNumber } from "./loader-wwKUpaDD.js";
import { _ as _export_sfc, r as ref, o as onMounted, a as openBlock, c as createElementBlock, b as createBaseVNode, d as createTextVNode, t as toDisplayString, e as createVNode, w as withCtx, F as Fragment, f as renderList, g as resolveComponent, u as unref, n as normalizeClass } from "./index-dXDZ0nX5.js";
const _hoisted_1 = { class: "dashboard" };
const _hoisted_2 = { class: "dashboard-header" };
const _hoisted_3 = { class: "strategy-label" };
const _hoisted_4 = { class: "stats-grid" };
const _hoisted_5 = { class: "stat-card" };
const _hoisted_6 = { class: "stat-info" };
const _hoisted_7 = { class: "stat-value" };
const _hoisted_8 = { class: "stat-card" };
const _hoisted_9 = { class: "stat-info" };
const _hoisted_10 = { class: "stat-value" };
const _hoisted_11 = { class: "stat-card" };
const _hoisted_12 = { class: "stat-info" };
const _hoisted_13 = { class: "stat-value" };
const _hoisted_14 = { class: "stat-card" };
const _hoisted_15 = { class: "stat-info" };
const _hoisted_16 = { class: "stat-value" };
const _hoisted_17 = { class: "card" };
const _hoisted_18 = { class: "card-title" };
const _hoisted_19 = {
  key: 0,
  class: "loading"
};
const _hoisted_20 = {
  key: 1,
  class: "empty"
};
const _hoisted_21 = {
  key: 2,
  class: "data-table"
};
const _hoisted_22 = { class: "rank" };
const _hoisted_23 = ["onClick"];
const _hoisted_24 = ["onClick"];
const _hoisted_25 = { class: "price" };
const _hoisted_26 = { class: "card" };
const _hoisted_27 = {
  key: 0,
  class: "loading"
};
const _hoisted_28 = {
  key: 1,
  class: "empty"
};
const _hoisted_29 = {
  key: 2,
  class: "data-table"
};
const _hoisted_30 = { class: "rank" };
const _hoisted_31 = ["onClick"];
const _hoisted_32 = ["onClick"];
const _hoisted_33 = { class: "price" };
const _sfc_main = {
  __name: "Dashboard",
  setup(__props) {
    const loading = ref(true);
    const signalCount = ref(0);
    const stockCount = ref(0);
    const topScore = ref(0);
    const latestDate = ref("");
    const topSignals = ref([]);
    const topScores = ref([]);
    const currentVersion = ref(getStrategyVersion());
    const versions = ref([]);
    const strategyName = ref("");
    function getScoreClass(score) {
      const s = Number(score);
      if (s >= 60) return "excellent";
      if (s >= 40) return "good";
      if (s >= 20) return "normal";
      return "low";
    }
    function formatDateDisplay(date) {
      if (!date || date === "-") return "-";
      const s = String(date);
      if (s.length === 8) {
        return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`;
      }
      return s;
    }
    onMounted(async () => {
      clearAllCache();
      try {
        const verResp = await loadStrategyVersions();
        versions.value = verResp.versions || [];
        strategyName.value = (versions.value.find((v) => v.id === currentVersion.value) || {}).name || "";
        const signalsResp = await loadSignals(false, currentVersion.value);
        const signalsList = signalsResp.data || [];
        latestDate.value = signalsResp.date || "";
        stockCount.value = signalsList.length;
        const buySignals = signalsList.filter((s) => s.signal === "BUY");
        signalCount.value = buySignals.length;
        topSignals.value = buySignals.slice(0, 20).map((s) => ({
          code: s.code,
          name: s.name,
          current_score: Number(s.current_score).toFixed(1),
          avg7_score: Number(s.avg7_score).toFixed(1),
          close_price: Number(s.close_price)
        }));
        const sorted = signalsList.filter((s) => s.avg7_score && !isNaN(Number(s.avg7_score))).sort((a, b) => Number(b.avg7_score) - Number(a.avg7_score));
        if (sorted.length > 0) {
          topScore.value = Number(sorted[0].avg7_score).toFixed(1);
        }
        topScores.value = sorted.slice(0, 10).map((s) => ({
          code: s.code,
          name: s.name,
          avg7_score: Number(s.avg7_score).toFixed(1),
          current_score: Number(s.current_score || 0).toFixed(1),
          close_price: Number(s.close_price)
        }));
      } catch (e) {
        console.error("加载数据失败:", e);
      } finally {
        loading.value = false;
      }
    });
    return (_ctx, _cache) => {
      const _component_router_link = resolveComponent("router-link");
      return openBlock(), createElementBlock("div", _hoisted_1, [
        createBaseVNode("div", _hoisted_2, [
          _cache[1] || (_cache[1] = createBaseVNode("h1", { class: "page-title" }, "📊 股票操作系统", -1)),
          createBaseVNode("div", _hoisted_3, [
            createTextVNode(" 📡 " + toDisplayString(currentVersion.value) + " - " + toDisplayString(strategyName.value) + " ", 1),
            createVNode(_component_router_link, {
              to: "/strategies",
              class: "change-link"
            }, {
              default: withCtx(() => [..._cache[0] || (_cache[0] = [
                createTextVNode("切换", -1)
              ])]),
              _: 1
            })
          ])
        ]),
        createBaseVNode("div", _hoisted_4, [
          createBaseVNode("div", _hoisted_5, [
            _cache[3] || (_cache[3] = createBaseVNode("div", { class: "stat-icon" }, "📡", -1)),
            createBaseVNode("div", _hoisted_6, [
              createBaseVNode("div", _hoisted_7, toDisplayString(signalCount.value), 1),
              _cache[2] || (_cache[2] = createBaseVNode("div", { class: "stat-label" }, "今日买入信号", -1))
            ])
          ]),
          createBaseVNode("div", _hoisted_8, [
            _cache[5] || (_cache[5] = createBaseVNode("div", { class: "stat-icon" }, "🎯", -1)),
            createBaseVNode("div", _hoisted_9, [
              createBaseVNode("div", _hoisted_10, toDisplayString(stockCount.value), 1),
              _cache[4] || (_cache[4] = createBaseVNode("div", { class: "stat-label" }, "自选股数", -1))
            ])
          ]),
          createBaseVNode("div", _hoisted_11, [
            _cache[7] || (_cache[7] = createBaseVNode("div", { class: "stat-icon" }, "⭐", -1)),
            createBaseVNode("div", _hoisted_12, [
              createBaseVNode("div", _hoisted_13, toDisplayString(topScore.value), 1),
              _cache[6] || (_cache[6] = createBaseVNode("div", { class: "stat-label" }, "最高评分", -1))
            ])
          ]),
          createBaseVNode("div", _hoisted_14, [
            _cache[9] || (_cache[9] = createBaseVNode("div", { class: "stat-icon" }, "📅", -1)),
            createBaseVNode("div", _hoisted_15, [
              createBaseVNode("div", _hoisted_16, toDisplayString(formatDateDisplay(latestDate.value)), 1),
              _cache[8] || (_cache[8] = createBaseVNode("div", { class: "stat-label" }, "最新数据日期", -1))
            ])
          ])
        ]),
        createBaseVNode("div", _hoisted_17, [
          createBaseVNode("div", _hoisted_18, [
            _cache[11] || (_cache[11] = createBaseVNode("span", null, "🎯", -1)),
            _cache[12] || (_cache[12] = createBaseVNode("span", null, "今日买入信号 (Top 20)", -1)),
            createVNode(_component_router_link, {
              to: "/signals",
              class: "view-all"
            }, {
              default: withCtx(() => [..._cache[10] || (_cache[10] = [
                createTextVNode("查看全部 →", -1)
              ])]),
              _: 1
            })
          ]),
          loading.value ? (openBlock(), createElementBlock("div", _hoisted_19, "加载中...")) : topSignals.value.length === 0 ? (openBlock(), createElementBlock("div", _hoisted_20, "暂无买入信号")) : (openBlock(), createElementBlock("table", _hoisted_21, [
            _cache[13] || (_cache[13] = createBaseVNode("thead", null, [
              createBaseVNode("tr", null, [
                createBaseVNode("th", null, "排名"),
                createBaseVNode("th", null, "代码"),
                createBaseVNode("th", null, "名称"),
                createBaseVNode("th", null, "当前评分"),
                createBaseVNode("th", null, "7日均分"),
                createBaseVNode("th", null, "收盘价")
              ])
            ], -1)),
            createBaseVNode("tbody", null, [
              (openBlock(true), createElementBlock(Fragment, null, renderList(topSignals.value, (item, idx) => {
                return openBlock(), createElementBlock("tr", {
                  key: item.code
                }, [
                  createBaseVNode("td", _hoisted_22, toDisplayString(idx + 1), 1),
                  createBaseVNode("td", {
                    class: "code clickable",
                    onClick: ($event) => unref(gotoYujing)(item.code),
                    title: "点击查看个股详情"
                  }, toDisplayString(item.code), 9, _hoisted_23),
                  createBaseVNode("td", {
                    class: "name clickable",
                    onClick: ($event) => unref(gotoYujing)(item.code),
                    title: "点击查看个股详情"
                  }, toDisplayString(item.name), 9, _hoisted_24),
                  createBaseVNode("td", null, [
                    createBaseVNode("span", {
                      class: normalizeClass(["score", getScoreClass(item.current_score)])
                    }, toDisplayString(item.current_score), 3)
                  ]),
                  createBaseVNode("td", null, [
                    createBaseVNode("span", {
                      class: normalizeClass(["score avg", getScoreClass(item.avg7_score)])
                    }, toDisplayString(item.avg7_score), 3)
                  ]),
                  createBaseVNode("td", _hoisted_25, toDisplayString(unref(formatMoney)(item.close_price)), 1)
                ]);
              }), 128))
            ])
          ]))
        ]),
        createBaseVNode("div", _hoisted_26, [
          _cache[15] || (_cache[15] = createBaseVNode("div", { class: "card-title" }, [
            createBaseVNode("span", null, "🏆"),
            createBaseVNode("span", null, "自选股最新评分 Top 10")
          ], -1)),
          loading.value ? (openBlock(), createElementBlock("div", _hoisted_27, "加载中...")) : topScores.value.length === 0 ? (openBlock(), createElementBlock("div", _hoisted_28, "暂无评分数据")) : (openBlock(), createElementBlock("table", _hoisted_29, [
            _cache[14] || (_cache[14] = createBaseVNode("thead", null, [
              createBaseVNode("tr", null, [
                createBaseVNode("th", null, "排名"),
                createBaseVNode("th", null, "代码"),
                createBaseVNode("th", null, "名称"),
                createBaseVNode("th", null, "7日均分"),
                createBaseVNode("th", null, "当前评分"),
                createBaseVNode("th", null, "收盘价")
              ])
            ], -1)),
            createBaseVNode("tbody", null, [
              (openBlock(true), createElementBlock(Fragment, null, renderList(topScores.value, (item, idx) => {
                return openBlock(), createElementBlock("tr", {
                  key: item.code
                }, [
                  createBaseVNode("td", _hoisted_30, toDisplayString(idx + 1), 1),
                  createBaseVNode("td", {
                    class: "code clickable",
                    onClick: ($event) => unref(gotoYujing)(item.code),
                    title: "点击查看个股详情"
                  }, toDisplayString(item.code), 9, _hoisted_31),
                  createBaseVNode("td", {
                    class: "name clickable",
                    onClick: ($event) => unref(gotoYujing)(item.code),
                    title: "点击查看个股详情"
                  }, toDisplayString(item.name), 9, _hoisted_32),
                  createBaseVNode("td", null, [
                    createBaseVNode("span", {
                      class: normalizeClass(["score total", getScoreClass(item.avg7_score)])
                    }, toDisplayString(item.avg7_score), 3)
                  ]),
                  createBaseVNode("td", null, toDisplayString(unref(formatNumber)(item.current_score)), 1),
                  createBaseVNode("td", _hoisted_33, toDisplayString(unref(formatMoney)(item.close_price)), 1)
                ]);
              }), 128))
            ])
          ]))
        ])
      ]);
    };
  }
};
const Dashboard = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-527a167d"]]);
export {
  Dashboard as default
};
