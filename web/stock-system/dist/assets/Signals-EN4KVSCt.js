import { _ as _export_sfc, r as ref, o as onMounted, a as openBlock, c as createElementBlock, b as createBaseVNode, h as withDirectives, v as vModelText, d as createTextVNode, t as toDisplayString, e as createVNode, w as withCtx, n as normalizeClass, i as createCommentVNode, F as Fragment, f as renderList, g as resolveComponent, j as computed, u as unref } from "./index-dXDZ0nX5.js";
import { g as getStrategyVersion, l as loadStrategyVersions, a as loadSignals, b as gotoYujing, f as formatMoney } from "./loader-wwKUpaDD.js";
const _hoisted_1 = { class: "signals-page" };
const _hoisted_2 = { class: "control-panel" };
const _hoisted_3 = { class: "search-box" };
const _hoisted_4 = { class: "strategy-label" };
const _hoisted_5 = { class: "filter-buttons" };
const _hoisted_6 = { class: "stats-row" };
const _hoisted_7 = { class: "stat-item" };
const _hoisted_8 = { class: "stat-num up" };
const _hoisted_9 = { class: "stat-item" };
const _hoisted_10 = { class: "stat-num" };
const _hoisted_11 = { class: "stat-item" };
const _hoisted_12 = { class: "stat-num highlight" };
const _hoisted_13 = { class: "stat-item" };
const _hoisted_14 = { class: "stat-num" };
const _hoisted_15 = {
  key: 0,
  class: "stat-item"
};
const _hoisted_16 = { class: "card" };
const _hoisted_17 = {
  key: 0,
  class: "loading"
};
const _hoisted_18 = {
  key: 1,
  class: "empty"
};
const _hoisted_19 = {
  key: 2,
  class: "data-table"
};
const _hoisted_20 = ["onClick"];
const _hoisted_21 = ["onClick"];
const _hoisted_22 = { class: "price" };
const _hoisted_23 = {
  key: 0,
  class: "signal-badge buy"
};
const _hoisted_24 = {
  key: 1,
  class: "signal-badge sell"
};
const _hoisted_25 = {
  key: 2,
  class: "signal-badge watch"
};
const _hoisted_26 = {
  key: 3,
  class: "pagination"
};
const _hoisted_27 = ["disabled"];
const _hoisted_28 = { class: "page-info" };
const _hoisted_29 = ["disabled"];
const pageSize = 50;
const _sfc_main = {
  __name: "Signals",
  setup(__props) {
    const loading = ref(true);
    const signals = ref([]);
    const searchQuery = ref("");
    const filter = ref("all");
    const sortAsc = ref(false);
    const currentPage = ref(1);
    const signalDate = ref("-");
    const fromCache = ref(false);
    const currentVersion = ref(getStrategyVersion());
    const versions = ref([]);
    const strategyName = ref("");
    const sortField = ref(currentVersion.value === "v2" ? "finance_score" : "avg7_score");
    const totalCount = computed(() => signals.value.length);
    const buyCount = computed(() => signals.value.filter((s) => s.signal === "BUY").length);
    const sellCount = computed(() => signals.value.filter((s) => s.signal === "SELL").length);
    const watchCount = computed(() => totalCount.value - buyCount.value - sellCount.value);
    const avgScore = computed(() => {
      if (signals.value.length === 0) return "-";
      const avg = signals.value.reduce((sum, s) => sum + Number(s.avg7_score), 0) / signals.value.length;
      return avg.toFixed(1);
    });
    const filteredSignals = computed(() => {
      let result = [...signals.value];
      if (searchQuery.value) {
        const q = searchQuery.value.toLowerCase();
        result = result.filter(
          (s) => s.code.includes(q) || s.name.toLowerCase().includes(q)
        );
      }
      if (filter.value === "buy") {
        result = result.filter((s) => s.signal === "BUY");
      } else if (filter.value === "sell") {
        result = result.filter((s) => s.signal === "SELL");
      } else if (filter.value === "watch") {
        result = result.filter((s) => s.signal !== "BUY" && s.signal !== "SELL");
      }
      result.sort((a, b) => {
        const field = sortField.value;
        let va = a[field];
        let vb = b[field];
        if (["current_score", "avg7_score", "finance_score", "close_price"].includes(field)) {
          va = va === "-" || va == null ? -Infinity : Number(va);
          vb = vb === "-" || vb == null ? -Infinity : Number(vb);
        } else {
          va = String(va || "");
          vb = String(vb || "");
        }
        if (va < vb) return sortAsc.value ? -1 : 1;
        if (va > vb) return sortAsc.value ? 1 : -1;
        return 0;
      });
      return result;
    });
    const totalPages = computed(() => Math.ceil(filteredSignals.value.length / pageSize));
    const paginatedSignals = computed(() => {
      const start = (currentPage.value - 1) * pageSize;
      return filteredSignals.value.slice(start, start + pageSize);
    });
    function setFilter(f) {
      filter.value = f;
      currentPage.value = 1;
    }
    function sortBy(field) {
      if (sortField.value === field) {
        sortAsc.value = !sortAsc.value;
      } else {
        sortField.value = field;
        sortAsc.value = false;
      }
    }
    function getScoreClass(score) {
      const s = Number(score);
      if (s >= 60) return "excellent";
      if (s >= 40) return "good";
      if (s >= 20) return "normal";
      return "low";
    }
    function getFinanceClass(score) {
      if (score == null || score === "-") return "low";
      const s = Number(score);
      if (s >= 15) return "excellent";
      if (s >= 10) return "good";
      if (s >= 5) return "normal";
      return "low";
    }
    onMounted(async () => {
      try {
        const verResp = await loadStrategyVersions();
        versions.value = verResp.versions || [];
        strategyName.value = (versions.value.find((v) => v.id === currentVersion.value) || {}).name || "";
        const signalsResp = await loadSignals(false, currentVersion.value);
        fromCache.value = false;
        const list = signalsResp.data || [];
        signals.value = list.map((s) => ({
          code: s.code,
          name: s.name,
          close_price: Number(s.close_price),
          current_score: Number(s.current_score).toFixed(1),
          avg7_score: Number(s.avg7_score).toFixed(1),
          finance_score: s.finance_score != null ? Number(s.finance_score).toFixed(1) : "-",
          signal: s.signal
        }));
        if (list.length > 0 && list[0].date) {
          signalDate.value = list[0].date;
        }
      } catch (e) {
        console.error("加载信号数据失败:", e);
      } finally {
        loading.value = false;
      }
    });
    return (_ctx, _cache) => {
      const _component_router_link = resolveComponent("router-link");
      return openBlock(), createElementBlock("div", _hoisted_1, [
        _cache[21] || (_cache[21] = createBaseVNode("h1", { class: "page-title" }, "📡 信号监控", -1)),
        createBaseVNode("div", _hoisted_2, [
          createBaseVNode("div", _hoisted_3, [
            withDirectives(createBaseVNode("input", {
              "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => searchQuery.value = $event),
              class: "search-input",
              placeholder: "搜索股票代码或名称...",
              onInput: _cache[1] || (_cache[1] = (...args) => _ctx.filterSignals && _ctx.filterSignals(...args))
            }, null, 544), [
              [vModelText, searchQuery.value]
            ])
          ]),
          createBaseVNode("div", _hoisted_4, [
            createTextVNode(" 📡 " + toDisplayString(currentVersion.value) + " - " + toDisplayString(strategyName.value) + " ", 1),
            createVNode(_component_router_link, {
              to: "/strategies",
              class: "change-link"
            }, {
              default: withCtx(() => [..._cache[14] || (_cache[14] = [
                createTextVNode("切换", -1)
              ])]),
              _: 1
            })
          ]),
          createBaseVNode("div", _hoisted_5, [
            createBaseVNode("button", {
              class: normalizeClass(["btn", filter.value === "all" ? "btn-primary" : "btn-outline"]),
              onClick: _cache[2] || (_cache[2] = ($event) => setFilter("all"))
            }, " 全部 (" + toDisplayString(totalCount.value) + ") ", 3),
            createBaseVNode("button", {
              class: normalizeClass(["btn", filter.value === "buy" ? "btn-primary" : "btn-outline"]),
              onClick: _cache[3] || (_cache[3] = ($event) => setFilter("buy"))
            }, " 买入信号 (" + toDisplayString(buyCount.value) + ") ", 3),
            createBaseVNode("button", {
              class: normalizeClass(["btn", filter.value === "sell" ? "btn-danger" : "btn-outline"]),
              onClick: _cache[4] || (_cache[4] = ($event) => setFilter("sell"))
            }, " 卖出信号 (" + toDisplayString(sellCount.value) + ") ", 3),
            createBaseVNode("button", {
              class: normalizeClass(["btn", filter.value === "watch" ? "btn-primary" : "btn-outline"]),
              onClick: _cache[5] || (_cache[5] = ($event) => setFilter("watch"))
            }, " 观望 (" + toDisplayString(watchCount.value) + ") ", 3)
          ])
        ]),
        createBaseVNode("div", _hoisted_6, [
          createBaseVNode("div", _hoisted_7, [
            createBaseVNode("span", _hoisted_8, toDisplayString(buyCount.value), 1),
            _cache[15] || (_cache[15] = createBaseVNode("span", { class: "stat-desc" }, "买入信号", -1))
          ]),
          createBaseVNode("div", _hoisted_9, [
            createBaseVNode("span", _hoisted_10, toDisplayString(watchCount.value), 1),
            _cache[16] || (_cache[16] = createBaseVNode("span", { class: "stat-desc" }, "观望", -1))
          ]),
          createBaseVNode("div", _hoisted_11, [
            createBaseVNode("span", _hoisted_12, toDisplayString(avgScore.value), 1),
            _cache[17] || (_cache[17] = createBaseVNode("span", { class: "stat-desc" }, "平均7日均分", -1))
          ]),
          createBaseVNode("div", _hoisted_13, [
            createBaseVNode("span", _hoisted_14, toDisplayString(signalDate.value), 1),
            _cache[18] || (_cache[18] = createBaseVNode("span", { class: "stat-desc" }, "信号日期", -1))
          ]),
          fromCache.value ? (openBlock(), createElementBlock("div", _hoisted_15, [..._cache[19] || (_cache[19] = [
            createBaseVNode("span", { class: "stat-num cached" }, "📦", -1),
            createBaseVNode("span", { class: "stat-desc" }, "已缓存（T-1 数据）", -1)
          ])])) : createCommentVNode("", true)
        ]),
        createBaseVNode("div", _hoisted_16, [
          loading.value ? (openBlock(), createElementBlock("div", _hoisted_17, "加载中...")) : filteredSignals.value.length === 0 ? (openBlock(), createElementBlock("div", _hoisted_18, toDisplayString(searchQuery.value ? "没有找到匹配的股票" : "暂无信号数据"), 1)) : (openBlock(), createElementBlock("table", _hoisted_19, [
            createBaseVNode("thead", null, [
              createBaseVNode("tr", null, [
                createBaseVNode("th", {
                  onClick: _cache[6] || (_cache[6] = ($event) => sortBy("code")),
                  class: "sortable"
                }, " 代码 " + toDisplayString(sortField.value === "code" ? sortAsc.value ? "↑" : "↓" : ""), 1),
                createBaseVNode("th", {
                  onClick: _cache[7] || (_cache[7] = ($event) => sortBy("name")),
                  class: "sortable"
                }, " 名称 " + toDisplayString(sortField.value === "name" ? sortAsc.value ? "↑" : "↓" : ""), 1),
                createBaseVNode("th", {
                  onClick: _cache[8] || (_cache[8] = ($event) => sortBy("current_score")),
                  class: "sortable"
                }, " 当前评分 " + toDisplayString(sortField.value === "current_score" ? sortAsc.value ? "↑" : "↓" : ""), 1),
                createBaseVNode("th", {
                  onClick: _cache[9] || (_cache[9] = ($event) => sortBy("avg7_score")),
                  class: "sortable"
                }, " 7日均分 " + toDisplayString(sortField.value === "avg7_score" ? sortAsc.value ? "↑" : "↓" : ""), 1),
                createBaseVNode("th", {
                  onClick: _cache[10] || (_cache[10] = ($event) => sortBy("finance_score")),
                  class: "sortable"
                }, " 财报 " + toDisplayString(sortField.value === "finance_score" ? sortAsc.value ? "↑" : "↓" : ""), 1),
                createBaseVNode("th", {
                  onClick: _cache[11] || (_cache[11] = ($event) => sortBy("close_price")),
                  class: "sortable"
                }, " 收盘价 " + toDisplayString(sortField.value === "close_price" ? sortAsc.value ? "↑" : "↓" : ""), 1),
                _cache[20] || (_cache[20] = createBaseVNode("th", null, "信号", -1))
              ])
            ]),
            createBaseVNode("tbody", null, [
              (openBlock(true), createElementBlock(Fragment, null, renderList(paginatedSignals.value, (item) => {
                return openBlock(), createElementBlock("tr", {
                  key: item.code
                }, [
                  createBaseVNode("td", {
                    class: "code clickable",
                    onClick: ($event) => unref(gotoYujing)(item.code),
                    title: "点击查看个股详情"
                  }, toDisplayString(item.code), 9, _hoisted_20),
                  createBaseVNode("td", {
                    class: "name clickable",
                    onClick: ($event) => unref(gotoYujing)(item.code),
                    title: "点击查看个股详情"
                  }, toDisplayString(item.name), 9, _hoisted_21),
                  createBaseVNode("td", null, [
                    createBaseVNode("span", {
                      class: normalizeClass(["score-badge", getScoreClass(item.current_score)])
                    }, toDisplayString(item.current_score), 3)
                  ]),
                  createBaseVNode("td", null, [
                    createBaseVNode("span", {
                      class: normalizeClass(["score-badge avg", getScoreClass(item.avg7_score)])
                    }, toDisplayString(item.avg7_score), 3)
                  ]),
                  createBaseVNode("td", null, [
                    createBaseVNode("span", {
                      class: normalizeClass(["score-badge finance", getFinanceClass(item.finance_score)])
                    }, toDisplayString(item.finance_score ?? "-"), 3)
                  ]),
                  createBaseVNode("td", _hoisted_22, toDisplayString(unref(formatMoney)(item.close_price)), 1),
                  createBaseVNode("td", null, [
                    item.signal === "BUY" ? (openBlock(), createElementBlock("span", _hoisted_23, "买入")) : item.signal === "SELL" ? (openBlock(), createElementBlock("span", _hoisted_24, "卖出")) : (openBlock(), createElementBlock("span", _hoisted_25, "观望"))
                  ])
                ]);
              }), 128))
            ])
          ])),
          totalPages.value > 1 ? (openBlock(), createElementBlock("div", _hoisted_26, [
            createBaseVNode("button", {
              class: "btn btn-outline",
              disabled: currentPage.value === 1,
              onClick: _cache[12] || (_cache[12] = ($event) => currentPage.value--)
            }, " 上一页 ", 8, _hoisted_27),
            createBaseVNode("span", _hoisted_28, toDisplayString(currentPage.value) + " / " + toDisplayString(totalPages.value), 1),
            createBaseVNode("button", {
              class: "btn btn-outline",
              disabled: currentPage.value === totalPages.value,
              onClick: _cache[13] || (_cache[13] = ($event) => currentPage.value++)
            }, " 下一页 ", 8, _hoisted_29)
          ])) : createCommentVNode("", true)
        ])
      ]);
    };
  }
};
const Signals = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-feca41ed"]]);
export {
  Signals as default
};
