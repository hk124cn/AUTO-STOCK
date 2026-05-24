# 财报评分翻转股价走势功能实现

## 需求背景
在网页版财报评分的显示界面（Home.vue 和 Detail.vue 的评分卡片），增加点击翻转功能，显示财报发布后7个交易日的股价走势图，方便直观对比评分与实际走势的关系。

## 关键技术方案

### 1. 公告日期获取与匹配
- **API**: `ak.stock_zh_a_disclosure_report_cninfo(symbol, keyword='报告', start_date, end_date)`
- **匹配逻辑**: 从公告标题提取报告期类型
  - "2024年年度报告" → 报告期 2024-12-31
  - "2024年半年度报告" → 报告期 2024-06-30
  - "2025年第一季度报告" → 报告期 2025-03-31
  - "2025年第三季度报告" → 报告期 2025-09-30

### 2. 缓存策略（智能过期）
- **缓存文件**: `data/disclosure/{code}.csv`
- **过期判断**: 获取财务数据的最新报告期，与缓存中所有公告的报告期对比
  - 如果 最新财务报告期 > 缓存中最新公告的报告期 → 过期，需刷新
- **一直有效**: 只要财报还没发布，就一直用缓存

### 3. 季度到公告日期的映射
- 本季度: 找最新财务报告期对应的公告日期
- 上季度: 找倒数第二个报告期对应的公告日期
- 上上季度: 找倒数第三个报告期对应的公告日期

### 4. 翻转实现要点
- **ECharts在隐藏容器初始化问题**: 背面卡片初始时 `display: none` 或被旋转隐藏，echarts.init() 会得到尺寸0。解决方案：获取数据时不立即初始化背面图表，等用户点击翻转后（动画600ms结束后）再 dispose+reinit
- **正面不显示背面内容**: 正面保持简洁，不显示背面K线影子
- **切换季度自动翻回正面**: 避免用户在背面时切换季度导致显示错误

---

## 实现步骤（已完成）

### Step 1: 后端 - data_manager.py
**文件**: `src/datafactory/data_manager.py`

新增函数:
- `get_disclosure_dates(code, refresh=False)` - 获取财报披露日期列表
- `get_disclosure_date_by_quarter(code, quarter)` - 根据季度获取公告日期
- `get_kline_after_disclosure(code, quarter, days=7)` - 获取公告后N日K线

### Step 2: 后端 - API接口
**文件**: `api/main.py`

新增接口:
```python
@app.get("/api/v1/financial/kline/{code}")
async def get_financial_kline(code: str, quarter: str = "本季度"):
    """获取财报发布后的K线数据"""
```

### Step 3: 前端 - Home.vue
**文件**: `web/src/views/Home.vue`

改动:
- 添加翻转卡片组件（flip-card）
- 正面: 评分展示 + "点击查看财报发布后7日内股价趋势 →"
- 背面: 公告日期 + ECharts折线图 + "← 点击返回评分"
- 加载评分后立即获取K线数据（但背面图表延迟到翻转后初始化）
- 切换到背面时700ms后重新初始化ECharts

### Step 4: 前端 - Detail.vue
**文件**: `web/src/views/Detail.vue`

改动:
- 同Home.vue的翻转逻辑
- 正面显示: 股票代码/名称 + 评分 + "本季度评分（满分20）" + "财报发布于 {公告日期}"
- 背面显示: "公告后股价走势" + 公告日期 + ECharts折线图
- 季度切换时自动翻回正面并重新加载K线数据

---

## 修改文件清单

| 文件 | 改动内容 |
|------|----------|
| `src/datafactory/data_manager.py` | 新增 `get_disclosure_dates()`, `get_disclosure_date_by_quarter()`, `get_kline_after_disclosure()` |
| `api/main.py` | 新增 `/api/v1/financial/kline/{code}` 接口 |
| `web/src/views/Home.vue` | 翻转卡片、K线图加载、布局调整 |
| `web/src/views/Detail.vue` | 翻转卡片、K线图加载、季度切换逻辑、文字调整 |

---

## 验证方法
1. 启动后端: `uvicorn api.main:app --host 0.0.0.0 --port 8000`
2. 启动前端: `cd web && npm run dev` (端口3000)
3. 访问首页或详情页，输入股票代码（如600519、600660）
4. 点击评分卡片 → 应显示股价走势图
5. 验证K线范围是公告后7个交易日
6. 详情页切换季度 → 应自动翻回正面并加载新季度K线