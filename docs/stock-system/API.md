# API文档

## 基础信息

- 基础URL：`https://stock.auto-claw.top/api/v1`
- 认证方式：写操作需 Bearer Token（密码登录获取）
- 数据格式：JSON

## 1. 信号相关

### GET /api/v1/signals/latest

获取最新信号（支持策略版本切换）

**请求参数**：
- `version`：策略版本（可选，默认 `v1`）。可选值：`v1`（每日触发）、`v2`（首次突破）

**响应**：
```json
{
  "date": "20260615",
  "version": "v2",
  "strategy_name": "首次突破",
  "count": 200,
  "data": [
    {
      "date": "20260615",
      "code": "600519",
      "name": "贵州茅台",
      "close_price": 1850.00,
      "current_score": 45.2,
      "avg7_score": 32.5,
      "prev_avg7_score": 30.1,
      "finance_score": 17.5,
      "signal": "BUY"
    }
  ]
}
```

**字段说明**：
- `current_score`：当日9因子总分（满分100）
- `avg7_score`：前7日平均分
- `finance_score`：财报子分数（满分20），v2 策略默认按此排序
- `signal`：`BUY`=买入信号，`SELL`=卖出信号，空=观望

### GET /api/v1/strategies/versions

列出所有可用策略版本

**响应**：
```json
{
  "default": "v1",
  "versions": [
    {
      "id": "v1",
      "name": "每日触发",
      "description": "7日均分≥30即买入",
      "threshold": 30.0,
      "first_break_only": false
    },
    {
      "id": "v2",
      "name": "首次突破",
      "description": "7日均分首次跨30才买",
      "threshold": 30.0,
      "first_break_only": true
    }
  ]
}
```

## 2. 持仓相关

### GET /api/v1/portfolio/positions

获取当前持仓

**请求参数**：无

**响应**：
```json
{
  "total_assets": 1000000,
  "market_value": 400000,
  "available_cash": 600000,
  "total_return": 12.35,
  "positions": [
    {
      "code": "600519",
      "name": "贵州茅台",
      "buy_date": "2026-06-03",
      "buy_price": 1800.00,
      "current_price": 1850.00,
      "quantity": 100,
      "market_value": 185000,
      "pnl": 2.78,
      "pnl_amount": 5000
    }
  ]
}
```

### POST /api/v1/portfolio/buy

记录买入（需认证）

**请求参数**：
```json
{
  "code": "600519",
  "name": "贵州茅台",
  "price": 1800.00,
  "quantity": 100,
  "date": "2026-06-03"
}
```

**响应**：
```json
{
  "success": true,
  "message": "买入记录成功",
  "trade_id": 123,
  "position": {
    "code": "600519",
    "name": "贵州茅台",
    "buy_date": "2026-06-03",
    "buy_price": 1800.00,
    "quantity": 100
  }
}
```

### POST /api/v1/portfolio/sell

记录卖出（需认证）

**请求参数**：
```json
{
  "code": "600519",
  "price": 1850.00,
  "quantity": 100,
  "date": "2026-06-15"
}
```

**响应**：
```json
{
  "success": true,
  "message": "卖出记录成功",
  "trade_id": 124,
  "pnl": 2.78,
  "pnl_amount": 5000
}
```

### GET /api/v1/portfolio/trades

获取交易记录

**请求参数**：
- `code`：股票代码（可选）
- `start_date`：开始日期（可选）
- `end_date`：结束日期（可选）
- `trade_type`：交易类型（buy/sell，可选）

**响应**：
```json
{
  "trades": [
    {
      "id": 123,
      "code": "600519",
      "name": "贵州茅台",
      "trade_date": "2026-06-03",
      "trade_type": "buy",
      "price": 1800.00,
      "quantity": 100,
      "amount": 180000,
      "fee": 270
    }
  ],
  "total": 50,
  "page": 1,
  "page_size": 20
}
```

## 3. 统计相关

### GET /api/v1/portfolio/stats

获取收益统计

**请求参数**：无

**响应**：
```json
{
  "total_trades": 25,
  "win_rate": 68.0,
  "avg_return": 5.2,
  "max_drawdown": -8.5,
  "sharpe_ratio": 1.85,
  "total_return": 12.35,
  "monthly_stats": [
    {
      "month": "2026-06",
      "return": 8.5,
      "trades": 5
    },
    {
      "month": "2026-05",
      "return": 12.3,
      "trades": 8
    }
  ]
}
```

### GET /api/v1/portfolio/nav

获取历史净值数据

**请求参数**：
- `start_date`：开始日期（可选）
- `end_date`：结束日期（可选）
- `period`：周期（day/week/month，可选）

**响应**：
```json
{
  "history": [
    {
      "date": "2026-06-01",
      "nav": 1.05,
      "return": 5.0
    },
    {
      "date": "2026-06-02",
      "nav": 1.06,
      "return": 6.0
    }
  ],
  "total_days": 30
}
```

## 4. 报告相关

### GET /api/v1/reports/today

获取今日评分报告

**请求参数**：
- `code`：股票代码

**响应**：
```json
{
  "code": "600519",
  "name": "贵州茅台",
  "current_price": 1850.00,
  "change_pct": 1.5,
  "score": 45.2,
  "avg7": 32.5,
  "signal": "buy",
  "position": {
    "buy_date": "2026-06-03",
    "buy_price": 1800.00,
    "quantity": 100,
    "pnl": 2.78
  }
}
```

### GET /api/v1/reports/top

获取评分TOP N股票

**请求参数**：
- `code`：股票代码
- `start_date`：开始日期（可选）
- `end_date`：结束日期（可选）
- `period`：周期（day/week/month，可选）

**响应**：
```json
{
  "kline": [
    {
      "date": "2026-06-01",
      "open": 1800.00,
      "close": 1820.00,
      "high": 1830.00,
      "low": 1790.00,
      "volume": 1000000
    }
  ],
  "signals": [
    {
      "date": "2026-06-03",
      "type": "buy",
      "price": 1800.00,
      "score": 45.2
    }
  ]
}
```

## 错误处理

### 错误响应格式

```json
{
  "error": {
    "code": 400,
    "message": "参数错误",
    "details": "股票代码不能为空"
  }
}
```

### 错误码

- 400：参数错误
- 404：资源不存在
- 500：服务器内部错误

## 示例代码

### Python

```python
import requests

# 获取 v2 信号（按财报分数排序）
response = requests.get('https://stock.auto-claw.top/api/v1/signals/latest?version=v2')
signals = response.json()

# 记录买入（需认证）
data = {
    'code': '600519',
    'name': '贵州茅台',
    'price': 1800.00,
    'quantity': 100,
    'date': '2026-06-03'
}
headers = {'Authorization': 'Bearer <token>'}
response = requests.post('https://stock.auto-claw.top/api/v1/portfolio/buy',
                         json=data, headers=headers)
result = response.json()
```

### JavaScript

```javascript
// 获取 v1 信号
fetch('https://stock.auto-claw.top/api/v1/signals/latest?version=v1')
  .then(response => response.json())
  .then(signals => console.log(signals));

// 获取 v2 信号（按财报分数排序）
fetch('https://stock.auto-claw.top/api/v1/signals/latest?version=v2')
  .then(response => response.json())
  .then(signals => console.log(signals));
```
