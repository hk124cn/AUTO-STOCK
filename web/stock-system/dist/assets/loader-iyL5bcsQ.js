import { q as authedFetch } from "./index-CBDHGmro.js";
const CACHE_VERSION = "v1";
function getMarketState() {
  const now = /* @__PURE__ */ new Date();
  const hour = now.getHours();
  const minute = now.getMinutes();
  const day = now.getDay();
  const time = hour * 60 + minute;
  if (day === 0 || day === 6) {
    return "HOLIDAY";
  }
  if (time >= 9 * 60 + 30 && time <= 11 * 60 + 30) {
    return "TRADING_MORNING";
  }
  if (time >= 13 * 60 && time <= 15 * 60) {
    return "TRADING_AFTERNOON";
  }
  if (time >= 9 * 60 && time < 9 * 60 + 30) {
    return "PRE_OPEN";
  }
  if (time > 11 * 60 + 30 && time < 13 * 60) {
    return "LUNCH";
  }
  if (time > 15 * 60) {
    return "POST_CLOSE";
  }
  return "NIGHT";
}
function getCacheTTL(dataType) {
  if (dataType === "T1_DATA") {
    return 24 * 60 * 60 * 1e3;
  }
  const state = getMarketState();
  if (state === "TRADING_MORNING" || state === "TRADING_AFTERNOON") {
    return 30 * 1e3;
  }
  if (state === "PRE_OPEN" || state === "LUNCH") {
    return 5 * 60 * 1e3;
  }
  return 60 * 60 * 1e3;
}
const memoryCache = /* @__PURE__ */ new Map();
const memoryTime = /* @__PURE__ */ new Map();
function getLocalKey(key) {
  return `stock-system-cache:${CACHE_VERSION}:${key}`;
}
function getFromLocal(key) {
  try {
    const raw = localStorage.getItem(getLocalKey(key));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (Date.now() - parsed.time > parsed.ttl) {
      localStorage.removeItem(getLocalKey(key));
      return null;
    }
    return parsed.data;
  } catch (e) {
    return null;
  }
}
function setToLocal(key, data, ttl) {
  try {
    localStorage.setItem(getLocalKey(key), JSON.stringify({
      time: Date.now(),
      ttl,
      data
    }));
  } catch (e) {
  }
}
function getFromMemory(key) {
  const time = memoryTime.get(key);
  const ttl = memoryCache.get(key + ":ttl");
  if (!time || !ttl) return null;
  if (Date.now() - time > ttl) {
    memoryCache.delete(key);
    memoryTime.delete(key);
    return null;
  }
  return memoryCache.get(key);
}
function setToMemory(key, data, ttl) {
  memoryCache.set(key, data);
  memoryCache.set(key + ":ttl", ttl);
  memoryTime.set(key, Date.now());
}
async function smartFetch(key, fetcher, options = {}) {
  const { dataType = "REALTIME", forceRefresh = false } = options;
  if (!forceRefresh) {
    const mem = getFromMemory(key);
    if (mem !== null) {
      return { data: mem, fromCache: true };
    }
    if (dataType === "T1_DATA") {
      const local = getFromLocal(key);
      if (local !== null) {
        setToMemory(key, local, 60 * 1e3);
        return { data: local, fromCache: true };
      }
    }
  }
  const data = await fetcher();
  const ttl = getCacheTTL(dataType);
  setToMemory(key, data, ttl);
  if (dataType === "T1_DATA") {
    setToLocal(key, data, ttl);
  }
  return { data, fromCache: false };
}
function invalidateCache(prefix) {
  for (const key of memoryCache.keys()) {
    if (key.startsWith(prefix)) {
      memoryCache.delete(key);
      memoryTime.delete(key);
    }
  }
  for (let i = localStorage.length - 1; i >= 0; i--) {
    const k = localStorage.key(i);
    if (k && k.includes(`stock-system-cache:${CACHE_VERSION}:${prefix}`)) {
      localStorage.removeItem(k);
    }
  }
}
function clearAllCache() {
  memoryCache.clear();
  memoryTime.clear();
  for (let i = localStorage.length - 1; i >= 0; i--) {
    const k = localStorage.key(i);
    if (k && k.startsWith(`stock-system-cache:${CACHE_VERSION}:`)) {
      localStorage.removeItem(k);
    }
  }
}
const CACHE_KEYS = {
  SIGNALS: "signals",
  SCORES: "scores",
  POSITIONS: (mode) => `positions:${mode}`,
  TRADES: (mode) => `trades:${mode}`,
  STATS: (mode) => `stats:${mode}`,
  ACCOUNT: (mode) => `account:${mode}`,
  NAV: (mode) => `nav:${mode}`
};
const API_BASE = "/api/v1";
async function loadSignals(forceRefresh = false) {
  var _a, _b;
  const result = await smartFetch(
    CACHE_KEYS.SIGNALS,
    async () => {
      const r = await fetch(API_BASE + "/signals/latest");
      if (!r.ok) throw new Error("HTTP " + r.status);
      return await r.json();
    },
    { dataType: "T1_DATA", forceRefresh }
  );
  return {
    date: ((_a = result.data) == null ? void 0 : _a.date) || "",
    data: ((_b = result.data) == null ? void 0 : _b.data) || []
  };
}
async function loadLatestScores(forceRefresh = false) {
  var _a, _b;
  const result = await smartFetch(
    CACHE_KEYS.SCORES,
    async () => {
      const r = await fetch(API_BASE + "/scores/latest");
      if (!r.ok) throw new Error("HTTP " + r.status);
      return await r.json();
    },
    { dataType: "T1_DATA", forceRefresh }
  );
  return {
    date: ((_a = result.data) == null ? void 0 : _a.date) || "",
    data: ((_b = result.data) == null ? void 0 : _b.data) || []
  };
}
async function loadAccount(mode = "SIM", forceRefresh = false) {
  const result = await smartFetch(
    CACHE_KEYS.ACCOUNT(mode),
    async () => {
      const r = await fetch(API_BASE + `/portfolio/account?mode=${mode}`);
      if (!r.ok) throw new Error("HTTP " + r.status);
      return await r.json();
    },
    { dataType: "REALTIME", forceRefresh }
  );
  return result.data;
}
async function loadPositions(mode = "SIM", forceRefresh = false) {
  var _a;
  const result = await smartFetch(
    CACHE_KEYS.POSITIONS(mode),
    async () => {
      const r = await fetch(API_BASE + `/portfolio/positions?mode=${mode}`);
      if (!r.ok) throw new Error("HTTP " + r.status);
      return await r.json();
    },
    { dataType: "REALTIME", forceRefresh }
  );
  return ((_a = result.data) == null ? void 0 : _a.positions) || [];
}
async function loadTrades(mode = "SIM", limit = 100, forceRefresh = false) {
  var _a;
  const result = await smartFetch(
    CACHE_KEYS.TRADES(mode),
    async () => {
      const r = await fetch(API_BASE + `/portfolio/trades?mode=${mode}&limit=${limit}`);
      if (!r.ok) throw new Error("HTTP " + r.status);
      return await r.json();
    },
    { dataType: "REALTIME", forceRefresh }
  );
  return ((_a = result.data) == null ? void 0 : _a.trades) || [];
}
async function loadStats(mode = "SIM", forceRefresh = false) {
  const result = await smartFetch(
    CACHE_KEYS.STATS(mode),
    async () => {
      const r = await fetch(API_BASE + `/portfolio/stats?mode=${mode}`);
      if (!r.ok) throw new Error("HTTP " + r.status);
      return await r.json();
    },
    { dataType: "REALTIME", forceRefresh }
  );
  return result.data;
}
async function loadNavHistory(mode = "SIM", startDate, endDate, forceRefresh = false) {
  var _a;
  const params = new URLSearchParams();
  params.set("mode", mode);
  if (startDate) params.set("start_date", startDate);
  if (endDate) params.set("end_date", endDate);
  const result = await smartFetch(
    CACHE_KEYS.NAV(mode),
    async () => {
      const r = await fetch(API_BASE + `/portfolio/nav?` + params.toString());
      if (!r.ok) throw new Error("HTTP " + r.status);
      return await r.json();
    },
    { dataType: "REALTIME", forceRefresh }
  );
  return ((_a = result.data) == null ? void 0 : _a.navs) || [];
}
async function postData(url, body) {
  const r = await authedFetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  return await r.json();
}
async function buyStock(data) {
  const result = await postData(API_BASE + "/portfolio/buy", data);
  invalidateCache("positions:");
  invalidateCache("stats:");
  invalidateCache("account:");
  invalidateCache("trades:");
  return result;
}
async function sellStock(data) {
  const result = await postData(API_BASE + "/portfolio/sell", data);
  invalidateCache("positions:");
  invalidateCache("stats:");
  invalidateCache("account:");
  invalidateCache("trades:");
  return result;
}
async function updatePrices(prices) {
  const result = await postData(API_BASE + "/portfolio/update-prices", { prices });
  invalidateCache("positions:");
  invalidateCache("stats:");
  return result;
}
function formatNumber(num, decimals = 2) {
  if (num === null || num === void 0 || isNaN(num)) return "-";
  return Number(num).toFixed(decimals);
}
function formatMoney(num) {
  if (num === null || num === void 0 || isNaN(num)) return "-";
  const n = Number(num);
  return "¥" + n.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function formatMoneyInt(num) {
  if (num === null || num === void 0 || isNaN(num)) return "-";
  return "¥" + Number(num).toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}
function formatPercent(num) {
  if (num === null || num === void 0 || isNaN(num)) return "-";
  const val = Number(num);
  const prefix = val > 0 ? "+" : "";
  return prefix + val.toFixed(2) + "%";
}
function getChangeClass(value) {
  if (!value || isNaN(value)) return "flat";
  return Number(value) > 0 ? "up" : Number(value) < 0 ? "down" : "flat";
}
function formatDateYMD(date) {
  if (!date) return "";
  const d = new Date(date);
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return year + month + day;
}
function gotoYujing(code, options = {}) {
  const c = String(code).padStart(6, "0");
  const params = new URLSearchParams();
  params.set("code", c);
  if (options.cost) params.set("cost", options.cost);
  if (options.tp !== void 0 && options.tp !== null) params.set("tp", options.tp);
  if (options.sl !== void 0 && options.sl !== null) params.set("sl", options.sl);
  if (options.strategy) params.set("strategy", options.strategy);
  window.open(`https://auto-claw.top/yujing/?${params.toString()}`, "_blank");
}
const loader = /* @__PURE__ */ Object.freeze(/* @__PURE__ */ Object.defineProperty({
  __proto__: null,
  buyStock,
  clearAllCache,
  formatDateYMD,
  formatMoney,
  formatMoneyInt,
  formatNumber,
  formatPercent,
  getChangeClass,
  gotoYujing,
  loadAccount,
  loadLatestScores,
  loadNavHistory,
  loadPositions,
  loadSignals,
  loadStats,
  loadTrades,
  sellStock,
  updatePrices
}, Symbol.toStringTag, { value: "Module" }));
export {
  formatNumber as a,
  getChangeClass as b,
  clearAllCache as c,
  formatPercent as d,
  loadPositions as e,
  formatMoney as f,
  gotoYujing as g,
  loadTrades as h,
  loadStats as i,
  getCacheTTL as j,
  getMarketState as k,
  loadSignals as l,
  loadNavHistory as m,
  loader as n,
  smartFetch as s
};
