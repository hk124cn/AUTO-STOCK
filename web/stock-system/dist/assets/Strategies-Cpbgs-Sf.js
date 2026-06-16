import { _ as _export_sfc, r as ref, p as reactive, o as onMounted, a as openBlock, c as createElementBlock, b as createBaseVNode, F as Fragment, f as renderList, h as withDirectives, y as vModelSelect, t as toDisplayString, m as withModifiers, v as vModelText, z as vModelCheckbox, d as createTextVNode, i as createCommentVNode, q as authedFetch, j as computed, n as normalizeClass, u as unref } from "./index-dXDZ0nX5.js";
import { g as getStrategyVersion, l as loadStrategyVersions, c as clearAllCache, e as getChangeClass, h as formatPercent, p as setStrategyVersion } from "./loader-wwKUpaDD.js";
const _hoisted_1 = { class: "strategies-page" };
const _hoisted_2 = { class: "card" };
const _hoisted_3 = { class: "signal-versions" };
const _hoisted_4 = { class: "version-header" };
const _hoisted_5 = { class: "version-tag" };
const _hoisted_6 = { class: "version-name" };
const _hoisted_7 = {
  key: 0,
  class: "active-badge"
};
const _hoisted_8 = { class: "version-desc" };
const _hoisted_9 = { class: "version-params" };
const _hoisted_10 = { key: 0 };
const _hoisted_11 = { key: 1 };
const _hoisted_12 = { class: "version-strategy-select" };
const _hoisted_13 = ["value", "onChange"];
const _hoisted_14 = ["value"];
const _hoisted_15 = {
  key: 0,
  class: "version-stats"
};
const _hoisted_16 = ["onClick"];
const _hoisted_17 = { class: "card" };
const _hoisted_18 = { class: "binding-grid" };
const _hoisted_19 = { class: "binding-item" };
const _hoisted_20 = ["value"];
const _hoisted_21 = { class: "binding-item" };
const _hoisted_22 = ["value"];
const _hoisted_23 = { class: "card" };
const _hoisted_24 = { class: "card-title" };
const _hoisted_25 = { class: "data-table" };
const _hoisted_26 = {
  key: 0,
  class: "default-badge"
};
const _hoisted_27 = { class: "up" };
const _hoisted_28 = { class: "down" };
const _hoisted_29 = { class: "desc" };
const _hoisted_30 = ["onClick"];
const _hoisted_31 = ["onClick"];
const _hoisted_32 = ["disabled", "title", "onClick"];
const _hoisted_33 = { class: "card" };
const _hoisted_34 = {
  key: 0,
  class: "loading"
};
const _hoisted_35 = {
  key: 1,
  class: "empty"
};
const _hoisted_36 = {
  key: 2,
  class: "data-table"
};
const _hoisted_37 = { class: "rank" };
const _hoisted_38 = ["title"];
const _hoisted_39 = { class: "down" };
const _hoisted_40 = { class: "modal" };
const _hoisted_41 = { class: "modal-header" };
const _hoisted_42 = { class: "modal-body" };
const _hoisted_43 = { class: "form-group" };
const _hoisted_44 = { class: "form-row" };
const _hoisted_45 = { class: "form-group" };
const _hoisted_46 = { class: "form-group" };
const _hoisted_47 = { class: "form-row" };
const _hoisted_48 = { class: "form-group" };
const _hoisted_49 = { class: "form-group" };
const _hoisted_50 = { class: "form-row" };
const _hoisted_51 = { class: "form-group" };
const _hoisted_52 = { class: "form-group" };
const _hoisted_53 = { class: "form-group" };
const _hoisted_54 = { class: "form-group" };
const _hoisted_55 = {
  key: 0,
  class: "form-error"
};
const _hoisted_56 = { class: "modal-footer" };
const _hoisted_57 = ["disabled"];
const API_BASE = "/api/v1";
const TRADING_MAP_KEY = "stock-system:version-trading-map";
const _sfc_main = {
  __name: "Strategies",
  setup(__props) {
    const strategies = ref([]);
    const backtestResults = ref([]);
    const loadingBacktest = ref(true);
    const submitting = ref(false);
    const editError = ref("");
    const showEditModal = ref(false);
    const signalVersions = ref([]);
    const currentVersion = ref(getStrategyVersion());
    const versionTradingMap = reactive(JSON.parse(localStorage.getItem(TRADING_MAP_KEY) || "{}"));
    async function setVersionTrading(versionId, tradingId) {
      versionTradingMap[versionId] = Number(tradingId);
      localStorage.setItem(TRADING_MAP_KEY, JSON.stringify(versionTradingMap));
      if (versionId === currentVersion.value) {
        const trading = strategies.value.find((s) => s.id === Number(tradingId));
        if (trading) {
          try {
            await authedFetch(API_BASE + "/strategies/active", {
              method: "PUT",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                threshold: trading.buy_threshold,
                take_profit: trading.take_profit,
                stop_loss: trading.stop_loss,
                cooldown_days: trading.cooldown_days,
                max_position_pct: trading.max_position_pct,
                max_positions: trading.max_positions
              })
            });
          } catch (e) {
            console.error("同步交易策略到后端失败:", e);
          }
        }
      }
    }
    async function activateVersion(versionId) {
      setStrategyVersion(versionId);
      currentVersion.value = versionId;
      try {
        await authedFetch(API_BASE + "/strategies/active", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ signal_version: versionId })
        });
      } catch (e) {
        console.error("同步信号版本到后端失败:", e);
      }
      alert(`✅ 已切换到 ${versionId} 信号版本`);
    }
    const accountBindings = reactive({ SIM: null, REAL: null });
    const editForm = reactive({
      id: null,
      name: "",
      buy_threshold: 30,
      take_profit: 0.2,
      stop_loss: 0.08,
      cooldown_days: 1,
      max_position_pct: 0.2,
      max_positions: 5,
      description: "",
      is_default: 0
    });
    const isEditValid = computed(() => {
      return editForm.name && editForm.name.trim() && editForm.buy_threshold >= 20 && editForm.buy_threshold <= 50 && editForm.take_profit > 0 && editForm.take_profit <= 0.5 && editForm.stop_loss > 0 && editForm.stop_loss <= 0.2 && editForm.cooldown_days >= 0 && editForm.cooldown_days <= 10 && editForm.max_position_pct >= 0.05 && editForm.max_position_pct <= 0.5 && editForm.max_positions >= 1 && editForm.max_positions <= 20;
    });
    async function fetchStrategies() {
      try {
        const r = await fetch(API_BASE + "/strategies");
        const d = await r.json();
        strategies.value = d.strategies || [];
      } catch (e) {
        console.error("加载策略失败:", e);
      }
    }
    async function fetchAccountBindings() {
      for (const mode of ["SIM", "REAL"]) {
        try {
          const r = await fetch(API_BASE + `/portfolio/strategy?mode=${mode}`);
          const s = await r.json();
          if (s && s.id) {
            accountBindings[mode] = s.id;
          }
        } catch (e) {
          console.error(`加载 ${mode} 策略失败`, e);
        }
      }
    }
    async function fetchBacktestTop() {
      loadingBacktest.value = true;
      try {
        const r = await fetch(API_BASE + "/backtest/top?n=10");
        const d = await r.json();
        backtestResults.value = d.results || [];
      } catch (e) {
        console.error("加载回测结果失败", e);
      } finally {
        loadingBacktest.value = false;
      }
    }
    async function bindStrategy(mode) {
      const sid = accountBindings[mode];
      if (!sid) return;
      try {
        const r = await fetch(API_BASE + `/portfolio/account?mode=${mode}`);
        const account = await r.json();
        if (account && account.id) {
          await authedFetch(API_BASE + "/portfolio/strategy", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ account_id: account.id, strategy_id: sid })
          });
          clearAllCache();
          alert(`✅ ${mode === "SIM" ? "模拟仓" : "实盘"}策略已切换`);
        }
      } catch (e) {
        alert("切换失败: " + e.message);
      }
    }
    function openEditModal(s) {
      if (s) {
        Object.assign(editForm, s);
      } else {
        Object.assign(editForm, {
          id: null,
          name: "",
          buy_threshold: 30,
          take_profit: 0.2,
          stop_loss: 0.08,
          cooldown_days: 1,
          max_position_pct: 0.2,
          max_positions: 5,
          description: "",
          is_default: 0
        });
      }
      editError.value = "";
      showEditModal.value = true;
    }
    function closeEditModal() {
      showEditModal.value = false;
    }
    function duplicateStrategy(s) {
      openEditModal(s);
      editForm.id = null;
      editForm.name = s.name + " (副本)";
      editForm.is_default = 0;
    }
    async function confirmEdit() {
      if (!isEditValid.value) return;
      submitting.value = true;
      editError.value = "";
      try {
        let r;
        if (editForm.id) {
          r = await authedFetch(API_BASE + `/strategies/${editForm.id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(editForm)
          });
        } else {
          const { id, ...body } = editForm;
          r = await authedFetch(API_BASE + "/strategies", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
          });
        }
        const data = await r.json();
        if (data.success !== false) {
          closeEditModal();
          await fetchStrategies();
        } else {
          editError.value = data.error || "保存失败";
        }
      } catch (e) {
        editError.value = "网络错误: " + e.message;
      } finally {
        submitting.value = false;
      }
    }
    async function deleteStrategyConfirm(s) {
      if (s.is_default) {
        alert("默认策略不能删除");
        return;
      }
      if (!confirm(`确认删除策略"${s.name}"？`)) return;
      try {
        const r = await authedFetch(API_BASE + `/strategies/${s.id}`, { method: "DELETE" });
        const data = await r.json();
        if (data.success) {
          await fetchStrategies();
        } else {
          alert("删除失败: " + (data.error || "未知错误"));
        }
      } catch (e) {
        alert("网络错误: " + e.message);
      }
    }
    onMounted(async () => {
      var _a;
      try {
        const verResp = await loadStrategyVersions();
        signalVersions.value = verResp.versions || [];
      } catch (e) {
        console.error("加载信号版本失败:", e);
      }
      await fetchStrategies();
      await fetchAccountBindings();
      await fetchBacktestTop();
      if (strategies.value.length > 0) {
        const defaultId = ((_a = strategies.value.find((s) => s.is_default)) == null ? void 0 : _a.id) || strategies.value[0].id;
        for (const v of signalVersions.value) {
          if (!versionTradingMap[v.id]) {
            versionTradingMap[v.id] = defaultId;
          }
        }
        localStorage.setItem(TRADING_MAP_KEY, JSON.stringify(versionTradingMap));
      }
    });
    return (_ctx, _cache) => {
      return openBlock(), createElementBlock("div", _hoisted_1, [
        _cache[40] || (_cache[40] = createBaseVNode("h1", { class: "page-title" }, "⚙️ 策略管理", -1)),
        createBaseVNode("div", _hoisted_2, [
          _cache[17] || (_cache[17] = createBaseVNode("div", { class: "card-title" }, [
            createBaseVNode("span", null, "📡"),
            createBaseVNode("span", null, "信号版本"),
            createBaseVNode("span", { class: "hint" }, " — 决定「什么算买入信号」，交易参数由下方交易策略控制")
          ], -1)),
          createBaseVNode("div", _hoisted_3, [
            (openBlock(true), createElementBlock(Fragment, null, renderList(signalVersions.value, (v) => {
              return openBlock(), createElementBlock("div", {
                key: v.id,
                class: normalizeClass(["version-card", { active: v.id === currentVersion.value }])
              }, [
                createBaseVNode("div", _hoisted_4, [
                  createBaseVNode("span", _hoisted_5, toDisplayString(v.id), 1),
                  createBaseVNode("span", _hoisted_6, toDisplayString(v.name), 1),
                  v.id === currentVersion.value ? (openBlock(), createElementBlock("span", _hoisted_7, "✓ 当前激活")) : createCommentVNode("", true)
                ]),
                createBaseVNode("div", _hoisted_8, toDisplayString(v.description), 1),
                createBaseVNode("div", _hoisted_9, [
                  createBaseVNode("span", null, "窗口: " + toDisplayString(v.lookback_days) + "天", 1),
                  v.first_break_only ? (openBlock(), createElementBlock("span", _hoisted_10, "首次突破")) : (openBlock(), createElementBlock("span", _hoisted_11, "每日触发"))
                ]),
                createBaseVNode("div", _hoisted_12, [
                  _cache[15] || (_cache[15] = createBaseVNode("label", null, "交易策略：", -1)),
                  createBaseVNode("select", {
                    value: versionTradingMap[v.id] || "",
                    onChange: ($event) => setVersionTrading(v.id, $event.target.value),
                    class: "select-input-sm"
                  }, [
                    _cache[14] || (_cache[14] = createBaseVNode("option", {
                      value: "",
                      disabled: ""
                    }, "选择交易策略", -1)),
                    (openBlock(true), createElementBlock(Fragment, null, renderList(strategies.value, (s) => {
                      return openBlock(), createElementBlock("option", {
                        key: s.id,
                        value: s.id
                      }, toDisplayString(s.name) + "（阈值≥" + toDisplayString(s.buy_threshold) + "，止盈" + toDisplayString(s.take_profit * 100) + "%，止损" + toDisplayString(s.stop_loss * 100) + "%） ", 9, _hoisted_14);
                    }), 128))
                  ], 40, _hoisted_13)
                ]),
                v.id === "v1" ? (openBlock(), createElementBlock("div", _hoisted_15, [..._cache[16] || (_cache[16] = [
                  createBaseVNode("span", null, "三年回测: 2024 +18% · 2025 +32% · 2026 +15%", -1),
                  createBaseVNode("span", null, "年均 +21.6% · 最差年 +14.6%", -1)
                ])])) : createCommentVNode("", true),
                v.id !== currentVersion.value ? (openBlock(), createElementBlock("button", {
                  key: 1,
                  class: "btn btn-primary btn-sm",
                  onClick: ($event) => activateVersion(v.id)
                }, "切换到 " + toDisplayString(v.id), 9, _hoisted_16)) : createCommentVNode("", true)
              ], 2);
            }), 128))
          ])
        ]),
        createBaseVNode("div", _hoisted_17, [
          _cache[20] || (_cache[20] = createBaseVNode("div", { class: "card-title" }, [
            createBaseVNode("span", null, "🎯"),
            createBaseVNode("span", null, "当前账户策略")
          ], -1)),
          createBaseVNode("div", _hoisted_18, [
            createBaseVNode("div", _hoisted_19, [
              _cache[18] || (_cache[18] = createBaseVNode("div", { class: "binding-label" }, "🎲 模拟仓策略", -1)),
              withDirectives(createBaseVNode("select", {
                "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => accountBindings.SIM = $event),
                class: "select-input",
                onChange: _cache[1] || (_cache[1] = ($event) => bindStrategy("SIM"))
              }, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(strategies.value, (s) => {
                  return openBlock(), createElementBlock("option", {
                    key: `sim-${s.id}`,
                    value: s.id
                  }, toDisplayString(s.name) + "（买入≥" + toDisplayString(s.buy_threshold) + ", 止盈" + toDisplayString(s.take_profit * 100) + "%, 止损" + toDisplayString(s.stop_loss * 100) + "%） ", 9, _hoisted_20);
                }), 128))
              ], 544), [
                [vModelSelect, accountBindings.SIM]
              ])
            ]),
            createBaseVNode("div", _hoisted_21, [
              _cache[19] || (_cache[19] = createBaseVNode("div", { class: "binding-label" }, "💰 实盘策略", -1)),
              withDirectives(createBaseVNode("select", {
                "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => accountBindings.REAL = $event),
                class: "select-input",
                onChange: _cache[3] || (_cache[3] = ($event) => bindStrategy("REAL"))
              }, [
                (openBlock(true), createElementBlock(Fragment, null, renderList(strategies.value, (s) => {
                  return openBlock(), createElementBlock("option", {
                    key: `real-${s.id}`,
                    value: s.id
                  }, toDisplayString(s.name) + "（买入≥" + toDisplayString(s.buy_threshold) + ", 止盈" + toDisplayString(s.take_profit * 100) + "%, 止损" + toDisplayString(s.stop_loss * 100) + "%） ", 9, _hoisted_22);
                }), 128))
              ], 544), [
                [vModelSelect, accountBindings.REAL]
              ])
            ])
          ])
        ]),
        createBaseVNode("div", _hoisted_23, [
          createBaseVNode("div", _hoisted_24, [
            _cache[21] || (_cache[21] = createBaseVNode("span", null, "📚", -1)),
            createBaseVNode("span", null, "策略库（" + toDisplayString(strategies.value.length) + " 个）", 1),
            createBaseVNode("button", {
              class: "btn btn-primary btn-sm",
              onClick: _cache[4] || (_cache[4] = ($event) => openEditModal(null)),
              style: { "margin-left": "auto" }
            }, " ➕ 新建策略 ")
          ]),
          createBaseVNode("table", _hoisted_25, [
            _cache[22] || (_cache[22] = createBaseVNode("thead", null, [
              createBaseVNode("tr", null, [
                createBaseVNode("th", null, "策略名"),
                createBaseVNode("th", null, "买入阈值"),
                createBaseVNode("th", null, "止盈%"),
                createBaseVNode("th", null, "止损%"),
                createBaseVNode("th", null, "冷却(天)"),
                createBaseVNode("th", null, "单股%"),
                createBaseVNode("th", null, "最多持仓"),
                createBaseVNode("th", null, "说明"),
                createBaseVNode("th", null, "操作")
              ])
            ], -1)),
            createBaseVNode("tbody", null, [
              (openBlock(true), createElementBlock(Fragment, null, renderList(strategies.value, (s) => {
                return openBlock(), createElementBlock("tr", {
                  key: s.id,
                  class: normalizeClass({ "is-default": s.is_default })
                }, [
                  createBaseVNode("td", null, [
                    createTextVNode(toDisplayString(s.name) + " ", 1),
                    s.is_default ? (openBlock(), createElementBlock("span", _hoisted_26, "默认")) : createCommentVNode("", true)
                  ]),
                  createBaseVNode("td", null, "≥ " + toDisplayString(s.buy_threshold), 1),
                  createBaseVNode("td", _hoisted_27, "+" + toDisplayString((s.take_profit * 100).toFixed(0)) + "%", 1),
                  createBaseVNode("td", _hoisted_28, "-" + toDisplayString((s.stop_loss * 100).toFixed(0)) + "%", 1),
                  createBaseVNode("td", null, toDisplayString(s.cooldown_days), 1),
                  createBaseVNode("td", null, toDisplayString((s.max_position_pct * 100).toFixed(0)) + "%", 1),
                  createBaseVNode("td", null, toDisplayString(s.max_positions), 1),
                  createBaseVNode("td", _hoisted_29, toDisplayString(s.description || "-"), 1),
                  createBaseVNode("td", null, [
                    createBaseVNode("button", {
                      class: "btn btn-sm btn-outline",
                      onClick: ($event) => openEditModal(s)
                    }, "编辑", 8, _hoisted_30),
                    createBaseVNode("button", {
                      class: "btn btn-sm btn-outline",
                      onClick: ($event) => duplicateStrategy(s)
                    }, "复制", 8, _hoisted_31),
                    createBaseVNode("button", {
                      class: "btn btn-sm btn-outline",
                      disabled: s.is_default,
                      title: s.is_default ? "默认策略不能删除" : "删除策略",
                      onClick: ($event) => deleteStrategyConfirm(s)
                    }, "删除", 8, _hoisted_32)
                  ])
                ], 2);
              }), 128))
            ])
          ])
        ]),
        createBaseVNode("div", _hoisted_33, [
          _cache[24] || (_cache[24] = createBaseVNode("div", { class: "card-title" }, [
            createBaseVNode("span", null, "🏆"),
            createBaseVNode("span", null, "回测历史 TOP 10"),
            createBaseVNode("span", { class: "hint" }, "（按年化收益排序）")
          ], -1)),
          loadingBacktest.value ? (openBlock(), createElementBlock("div", _hoisted_34, "加载中...")) : backtestResults.value.length === 0 ? (openBlock(), createElementBlock("div", _hoisted_35, "暂无回测结果")) : (openBlock(), createElementBlock("table", _hoisted_36, [
            _cache[23] || (_cache[23] = createBaseVNode("thead", null, [
              createBaseVNode("tr", null, [
                createBaseVNode("th", null, "排名"),
                createBaseVNode("th", null, "策略名"),
                createBaseVNode("th", null, "回测区间"),
                createBaseVNode("th", null, "总收益"),
                createBaseVNode("th", null, "年化"),
                createBaseVNode("th", null, "最大回撤"),
                createBaseVNode("th", null, "夏普"),
                createBaseVNode("th", null, "胜率")
              ])
            ], -1)),
            createBaseVNode("tbody", null, [
              (openBlock(true), createElementBlock(Fragment, null, renderList(backtestResults.value, (b, idx) => {
                return openBlock(), createElementBlock("tr", {
                  key: b.name
                }, [
                  createBaseVNode("td", _hoisted_37, toDisplayString(idx + 1), 1),
                  createBaseVNode("td", {
                    class: "name-cell",
                    title: b.readme_url
                  }, toDisplayString(b.name), 9, _hoisted_38),
                  createBaseVNode("td", null, toDisplayString(b.period || "-"), 1),
                  createBaseVNode("td", {
                    class: normalizeClass(unref(getChangeClass)(b.total_return))
                  }, toDisplayString(unref(formatPercent)(b.total_return)), 3),
                  createBaseVNode("td", {
                    class: normalizeClass(unref(getChangeClass)(b.annual_return))
                  }, toDisplayString(unref(formatPercent)(b.annual_return)), 3),
                  createBaseVNode("td", _hoisted_39, toDisplayString(unref(formatPercent)(-(b.max_drawdown || 0))), 1),
                  createBaseVNode("td", null, toDisplayString(b.sharpe ? b.sharpe.toFixed(2) : "-"), 1),
                  createBaseVNode("td", null, toDisplayString(b.win_rate ? b.win_rate.toFixed(1) + "%" : "-"), 1)
                ]);
              }), 128))
            ])
          ]))
        ]),
        showEditModal.value ? (openBlock(), createElementBlock("div", {
          key: 0,
          class: "modal-overlay",
          onClick: withModifiers(closeEditModal, ["self"])
        }, [
          createBaseVNode("div", _hoisted_40, [
            createBaseVNode("div", _hoisted_41, [
              createBaseVNode("h3", null, toDisplayString(editForm.id ? "编辑策略" : "新建策略"), 1),
              createBaseVNode("button", {
                class: "btn-close",
                onClick: closeEditModal
              }, "✕")
            ]),
            createBaseVNode("div", _hoisted_42, [
              createBaseVNode("div", _hoisted_43, [
                _cache[25] || (_cache[25] = createBaseVNode("label", null, "策略名称 *", -1)),
                withDirectives(createBaseVNode("input", {
                  "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => editForm.name = $event),
                  placeholder: "如：我的策略A / 紧止损 / 宽仓位"
                }, null, 512), [
                  [vModelText, editForm.name]
                ])
              ]),
              createBaseVNode("div", _hoisted_44, [
                createBaseVNode("div", _hoisted_45, [
                  _cache[26] || (_cache[26] = createBaseVNode("label", null, "买入阈值（前7日均分）", -1)),
                  withDirectives(createBaseVNode("input", {
                    "onUpdate:modelValue": _cache[6] || (_cache[6] = ($event) => editForm.buy_threshold = $event),
                    type: "number",
                    step: "1",
                    min: "20",
                    max: "50"
                  }, null, 512), [
                    [
                      vModelText,
                      editForm.buy_threshold,
                      void 0,
                      { number: true }
                    ]
                  ]),
                  _cache[27] || (_cache[27] = createBaseVNode("div", { class: "form-hint" }, "≥ 此分才买入（默认 30）", -1))
                ]),
                createBaseVNode("div", _hoisted_46, [
                  _cache[28] || (_cache[28] = createBaseVNode("label", null, "止盈 %", -1)),
                  withDirectives(createBaseVNode("input", {
                    "onUpdate:modelValue": _cache[7] || (_cache[7] = ($event) => editForm.take_profit = $event),
                    type: "number",
                    step: "0.01",
                    min: "0.05",
                    max: "0.5"
                  }, null, 512), [
                    [
                      vModelText,
                      editForm.take_profit,
                      void 0,
                      { number: true }
                    ]
                  ]),
                  _cache[29] || (_cache[29] = createBaseVNode("div", { class: "form-hint" }, "成本 × (1 + 此值) 为目标止盈价", -1))
                ])
              ]),
              createBaseVNode("div", _hoisted_47, [
                createBaseVNode("div", _hoisted_48, [
                  _cache[30] || (_cache[30] = createBaseVNode("label", null, "止损 %", -1)),
                  withDirectives(createBaseVNode("input", {
                    "onUpdate:modelValue": _cache[8] || (_cache[8] = ($event) => editForm.stop_loss = $event),
                    type: "number",
                    step: "0.01",
                    min: "0.03",
                    max: "0.2"
                  }, null, 512), [
                    [
                      vModelText,
                      editForm.stop_loss,
                      void 0,
                      { number: true }
                    ]
                  ]),
                  _cache[31] || (_cache[31] = createBaseVNode("div", { class: "form-hint" }, "成本 × (1 - 此值) 为目标止损价", -1))
                ]),
                createBaseVNode("div", _hoisted_49, [
                  _cache[32] || (_cache[32] = createBaseVNode("label", null, "冷却天数", -1)),
                  withDirectives(createBaseVNode("input", {
                    "onUpdate:modelValue": _cache[9] || (_cache[9] = ($event) => editForm.cooldown_days = $event),
                    type: "number",
                    step: "1",
                    min: "0",
                    max: "10"
                  }, null, 512), [
                    [
                      vModelText,
                      editForm.cooldown_days,
                      void 0,
                      { number: true }
                    ]
                  ]),
                  _cache[33] || (_cache[33] = createBaseVNode("div", { class: "form-hint" }, "同股两次信号间隔（默认 1）", -1))
                ])
              ]),
              createBaseVNode("div", _hoisted_50, [
                createBaseVNode("div", _hoisted_51, [
                  _cache[34] || (_cache[34] = createBaseVNode("label", null, "单股最大仓位 %", -1)),
                  withDirectives(createBaseVNode("input", {
                    "onUpdate:modelValue": _cache[10] || (_cache[10] = ($event) => editForm.max_position_pct = $event),
                    type: "number",
                    step: "0.05",
                    min: "0.05",
                    max: "0.5"
                  }, null, 512), [
                    [
                      vModelText,
                      editForm.max_position_pct,
                      void 0,
                      { number: true }
                    ]
                  ]),
                  _cache[35] || (_cache[35] = createBaseVNode("div", { class: "form-hint" }, "占总资产比例（默认 0.20 = 20%）", -1))
                ]),
                createBaseVNode("div", _hoisted_52, [
                  _cache[36] || (_cache[36] = createBaseVNode("label", null, "最多持仓数", -1)),
                  withDirectives(createBaseVNode("input", {
                    "onUpdate:modelValue": _cache[11] || (_cache[11] = ($event) => editForm.max_positions = $event),
                    type: "number",
                    step: "1",
                    min: "1",
                    max: "20"
                  }, null, 512), [
                    [
                      vModelText,
                      editForm.max_positions,
                      void 0,
                      { number: true }
                    ]
                  ]),
                  _cache[37] || (_cache[37] = createBaseVNode("div", { class: "form-hint" }, "同时持有股票数上限（默认 5）", -1))
                ])
              ]),
              createBaseVNode("div", _hoisted_53, [
                _cache[38] || (_cache[38] = createBaseVNode("label", null, "说明（可选）", -1)),
                withDirectives(createBaseVNode("input", {
                  "onUpdate:modelValue": _cache[12] || (_cache[12] = ($event) => editForm.description = $event),
                  placeholder: "如：高阈值 + 低仓位"
                }, null, 512), [
                  [vModelText, editForm.description]
                ])
              ]),
              createBaseVNode("div", _hoisted_54, [
                createBaseVNode("label", null, [
                  withDirectives(createBaseVNode("input", {
                    "onUpdate:modelValue": _cache[13] || (_cache[13] = ($event) => editForm.is_default = $event),
                    type: "checkbox"
                  }, null, 512), [
                    [vModelCheckbox, editForm.is_default]
                  ]),
                  _cache[39] || (_cache[39] = createTextVNode(" 设为默认策略（账户创建时自动使用） ", -1))
                ])
              ]),
              editError.value ? (openBlock(), createElementBlock("div", _hoisted_55, "⚠️ " + toDisplayString(editError.value), 1)) : createCommentVNode("", true)
            ]),
            createBaseVNode("div", _hoisted_56, [
              createBaseVNode("button", {
                class: "btn btn-outline",
                onClick: closeEditModal
              }, "取消"),
              createBaseVNode("button", {
                class: "btn btn-primary",
                disabled: !isEditValid.value || submitting.value,
                onClick: confirmEdit
              }, toDisplayString(submitting.value ? "保存中..." : "保存"), 9, _hoisted_57)
            ])
          ])
        ])) : createCommentVNode("", true)
      ]);
    };
  }
};
const Strategies = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-68509979"]]);
export {
  Strategies as default
};
