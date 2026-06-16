# 部署说明

## 环境要求

- Node.js 16+
- Python 3.8+
- SQLite 3
- Nginx

## 部署步骤

### 1. 前端部署

```bash
# 进入项目目录
cd /home/admin/AUTO-STOCK/web/stock-system

# 安装依赖
npm install

# 构建生产版本
npm run build
```

### 2. 后端部署

```bash
# 启动API服务
cd /home/admin/AUTO-STOCK
python api/main.py
```

### 3. Nginx配置

```nginx
# stock.auto-claw.top 配置
server {
    listen 80;
    server_name stock.auto-claw.top;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name stock.auto-claw.top;

    ssl_certificate /ssl/cert.pem;
    ssl_certificate_key /ssl/cert.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # 前端静态文件
    location / {
        root /home/admin/AUTO-STOCK/web/stock-system/dist;
        try_files $uri $uri/ /index.html;
    }

    # API接口
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # 数据文件
    location /data/price/ {
        alias /home/admin/AUTO-STOCK/data/price/;
    }

    location /data/signals/ {
        alias /home/admin/AUTO-STOCK/result/signals/;
    }
}
```

### 4. 域名解析

在Cloudflare添加DNS记录：
- 类型：CNAME
- 名称：stock
- 目标：auto-claw.top
- 代理状态：已代理

### 5. 定时任务

```bash
# 编辑crontab
crontab -e

# 添加以下内容（已有，无需修改）
0 19 * * 1-5 bash /home/admin/AUTO-STOCK/scripts/evening_pipeline.sh >> /home/admin/AUTO-STOCK/logs/evening_pipeline.log 2>&1
0 3 * * * python3 /home/admin/scripts/r2_backup.py >> /home/admin/logs/r2-backup.log 2>&1
```

## 数据库初始化

### 创建SQLite数据库

```bash
cd /home/admin/AUTO-STOCK
python3 -c "
import sqlite3
conn = sqlite3.connect('data/portfolio.db')
c = conn.cursor()

# 创建持仓表
c.execute('''CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    name TEXT,
    buy_date TEXT,
    buy_price REAL,
    quantity INTEGER,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')

# 创建交易记录表
c.execute('''CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    name TEXT,
    trade_date TEXT,
    trade_type TEXT,
    price REAL,
    quantity INTEGER,
    amount REAL,
    fee REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')

# 创建信号记录表
c.execute('''CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    name TEXT,
    signal_date TEXT,
    signal_type TEXT,
    score REAL,
    avg7 REAL,
    price REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')

conn.commit()
conn.close()
print('数据库初始化完成')
"
```

## 备份配置

### 修改备份脚本

```bash
# 编辑备份脚本
vi /home/admin/scripts/r2_backup.py

# 修改SOURCE_DIR
SOURCE_DIR = "/home/admin/AUTO-STOCK"

# 添加排除目录
EXCLUDE_DIRS = {
    'venv',
    'node_modules',
    '__pycache__',
    '.git',
    '.claude',
    '.vscode',
    'dist',
}
```

## 监控

### 日志文件

- 晚间流水线日志：`/home/admin/AUTO-STOCK/logs/evening_pipeline_YYYYMMDD.log`
- 备份日志：`/home/admin/logs/r2-backup.log`
- Nginx日志：`/var/log/nginx/access.log`

### 健康检查

```bash
# 检查服务状态
systemctl status nginx

# 检查定时任务
crontab -l

# 检查数据库
sqlite3 /home/admin/AUTO-STOCK/data/portfolio.db "SELECT COUNT(*) FROM positions;"
```

## 故障排除

### 1. 页面无法访问

```bash
# 检查Nginx配置
nginx -t

# 检查域名解析
nslookup stock.auto-claw.top

# 检查SSL证书
openssl s_client -connect stock.auto-claw.top:443
```

### 2. 信号计算失败

```bash
# 检查评分数据
ls -la /home/admin/AUTO-STOCK/result/daily_score/

# 手动运行信号计算
python3 /home/admin/AUTO-STOCK/scripts/calc_signals.py --date 20260612
```

### 3. 数据库问题

```bash
# 检查数据库文件
ls -la /home/admin/AUTO-STOCK/data/portfolio.db

# 检查数据库完整性
sqlite3 /home/admin/AUTO-STOCK/data/portfolio.db "PRAGMA integrity_check;"
```

## 更新

### 前端更新

```bash
cd /home/admin/AUTO-STOCK/web/stock-system
git pull
npm install
npm run build
```

### 后端更新

```bash
cd /home/admin/AUTO-STOCK
git pull
# 重启API服务
pkill -f "python api/main.py"
nohup python api/main.py > /dev/null 2>&1 &
```

### 数据库迁移

```bash
# 备份数据库
cp /home/admin/AUTO-STOCK/data/portfolio.db /home/admin/AUTO-STOCK/data/portfolio.db.backup

# 执行迁移脚本
python3 /home/admin/AUTO-STOCK/scripts/migrate_db.py
```
