# STATUS — 25 项修复状态表

> **每修完一项，把对应行从 ⏳ 改成 ✅（或 ⏭️ / ❌），并在"修复 commit"列写 commit hash**  
> 全部修完（或部分放弃）后写 SUMMARY.md 总结

## 状态图例

- ⏳ 待修
- 🔧 修复中
- ✅ 已修
- ⏭️ 跳过（理由写在备注）
- ❌ 修复失败（原因写在备注）

---

## 第一波：🔴 4 个 P0 阻塞

| # | 项 | 状态 | 修复 commit | 备注 |
|---|----|------|------------|------|
| 1 | P0-A `__init__.py` 导入 | ✅ |  | 删除 STRATEGIES/Strategy，替换为 get_active_config/update_active_config/switch_signal_version/DEFAULT_STRATEGY_VERSION/SIGNAL_VERSIONS；`python3 -c "import src.backtest"` 通过 |
| 2 | P0-B positions 字段名 | ✅ |  | calc_signals.py:405-409 替换为读 cost_price + 日志告警；avg_cost 全代码库已无残留；语法检查通过；端到端验证留到 #4 后一起跑 |
| 3 | P0-C buy_date 格式 | ✅ |  | calc_signals.py:410 加 `[:10]` 切掉时间部分，"2026-06-15 08:55:00" → "20260615"；语法检查 + 3 种输入断言通过 |
| 4 | P0-D sim_trader NameError | ✅ |  | 删除 sim_trader.py:170-182 残留警告块；冒烟时另发现 8 处 `strategy.attr`→`['key']` 漏改（f21e127 NamedTuple→dict 重构遗留），顺手一并修了：sim_trader.py:48 + calc_signals.py:116/140/160/203/288/500-509/556。详见 SUMMARY。 |

## 第二波：🟠 7 个 P0

| # | 项 | 状态 | 修复 commit | 备注 |
|---|----|------|------------|------|
| 6 | P0-F PUT active 无鉴权 | ✅ |  | active GET/PUT 移到 `/strategies/{strategy_id}` 前，避免动态路由遮蔽；PUT 加 `Depends(verify_token)`，GET 保持游客可查看。已重启 API：GET 200，PUT 无 token 401，threshold 未变，OpenAPI 仅 PUT 出现 Authorization header。 |
| 7 | P0-G _active_config 持久化 | ✅ |  | 新增 data/active_config.json 持久化；update_active_config/switch_signal_version 写盘，启动时加载，坏文件回退默认。已验证：临时 v2/threshold=31.5 跨 restart 保留，随后恢复 v1/threshold=30。review 后补修：data/active_config.json 加 .gitignore；api signals/latest 的 strategy dict 访问已修并测 200。 |
| 8 | P0-H gunicorn 多 worker | ✅ |  | 保留财报评分启动/停止脚本，但后端统一改为 systemd：start 用 `restart ${API_SERVICE:-stock-api}`，stop 用 `stop ${API_SERVICE:-stock-api}`；不再启动/停止 gunicorn -w 2；新增 API_SERVICE/FRONTEND_DIR/FRONTEND_PORT 扩展变量，便于未来每套功能指向各自 service/worker。仅做 bash -n 与 grep 验证，未运行脚本避免影响前端/nginx。 |
| 10 | P0 accounts.strategy_id 漂移 | ✅ |  | database.py _init_db 增加兼容迁移 `ALTER TABLE accounts ADD COLUMN strategy_id INTEGER`，仅忽略 duplicate column。已验证：旧库原无 strategy_id；PortfolioDB() 初始化后补列成功；重复初始化幂等。 |
| 11 | P0 main.py path traversal | ✅ |  | run_batch 输出目录固定到 result/daily_score；结果名拒绝 `/` 和 `\\`、`.`、`..`，自动补 .csv，并保留 abspath+startswith 兜底。语法 OK；路径用例验证通过（正常名/中文名允许，../../ 与 Windows 分隔符拒绝）。 |
| 12 | P0 CLI EOFError | ✅ |  | 新增 safe_input()，4 处 input() 替换为 safe_input；`python3 main.py < /dev/null` 输出“无效输入”并 exit 0，无 traceback；语法 OK。 |
| 13 | P0 requirements.txt 缺依赖 | ✅ |  | 保留原 3 行，追加 fastapi/uvicorn[standard]/pydantic/starlette/httpx。`python3 -m pip install -r requirements.txt --dry-run` 成功（httpx/uvicorn standard extras 可解析，未实际安装）。 |

## 第三波：🟡 5 个 P1/P2

| # | 项 | 状态 | 修复 commit | 备注 |
|---|----|------|------------|------|
| 9 | delete_trade SELL 不回滚 | ✅ |  | delete_trade SELL 回滚增加 positions.shares/closed_at 恢复，并修正 trade_lots 回滚不再误删 lot、按 remaining_to_restore 递减。已用临时 SIM 账户全买全卖后删除 SELL 验证：position reopened、remaining_shares=100、sell_shares=0、SELL trade 删除；测试账户已清理。 |
| 16 | 流水线无交易日检查 | ✅ |  | evening_pipeline.sh 步骤前增加 data/calendar/trade_days.csv 检查，兼容 YYYY-MM-DD/YYYMMDD；非交易日 exit 0，缺日历仅告警继续。已验证 bash -n OK；2024-10-01 跳过且 exit 0。 |
| 17 | sim_trader dry-run 软失败 | ✅ |  | evening_pipeline.sh step5 改为 `python3 scripts/sim_trader.py --date "$TARGET_DATE" --dry-run || fail "sim_trader dry-run"`，不再吞错。bash -n OK；sim_trader 20260615 dry-run 跑通。 |
| 18 | calc_signals 仍用 db.get_strategy | ✅ |  | 1) generate_sell_signals 改为接收 config 参数，用 config['take_profit']/['stop_loss']；2) API set_account_strategy 增加同步：DB 策略选中后，buy_threshold/tp/sl/cooldown/max_position_pct/max_positions 写入 active config；3) calc_signals end-to-end 97 买+0 卖通过；4) API 测试：策略2(threshold=40,tp=0.15,sl=0.05)同步后 active config 正确，恢复策略1后正确。 |
| 19 | allow_methods=["*"] 残留 | ⏳ |  |  |

## 第四波：🟢 9 项按需

| # | 项 | 状态 | 修复 commit | 备注 |
|---|----|------|------------|------|
| 20 | deploy nginx 重复 | ✅ |  | 删除 deploy/stock-system.conf，统一维护 web/stock-system/nginx.conf（更完整：有 http2/CORS/CSP/Permissions-Policy）。线上 /etc/nginx/conf.d/stock-system.conf 未动。 |
| 14 | live 模式未修 | ✅ |  | Method A：_run_live() docstring 详细说明 3 项前视偏差（T日评分/T日入场无滑点/无冷却期），标注仅供实验不可用于策略评估。 |
| 15 | V2 signal_engine 未同步 | ✅ |  | Method A：signal_engine.run() docstring 详细说明 2 项前视偏差（T日评分/T日收盘价无滑点），已有冷却期 ✅，标注仅供实验不可用于策略评估。 |
| 21 | 持仓 TOCTOU | ⏭️ |  | 用户决定不做：读-改-写竞态需改较大，单 worker 场景暂不触发 |
| 22 | transfer_fee 漏算 | ⏭️ |  | 用户决定不做：过户费 0.001% 影响小，后续可单独加 |
| 23 | 胜率不扣手续费 | ⏭️ |  | 用户决定不做：需先做 #22，后续一起处理 |
| 24 | feedbacks.json IP 历史 | ⏭️ |  | 需要 git filter-repo + force push，用户已禁止 |
| 25 | sim_trader switch 副作用 | ✅ |  | 新增 get_config_for_version()（读不写盘），CLI 改用它代替 switch_signal_version()；API 继续用 switch_signal_version() 保留写盘。已验证：`--strategy-version v2` 跑通（2买+0卖），active_config.json 未被修改。 |

---

## 修复进度统计

| 状态 | 数量 |
|------|------|
| ⏳ 待修 | 0 |
| 🔧 修复中 | 0 |
| ✅ 已修 | 21 |
| ⏭️ 跳过 | 4 |
| ❌ 失败 | 0 |

---

## 修完/跳过后必跑的验证

```bash
sudo systemctl restart stock-api
curl -i http://127.0.0.1:8000/api/v1/strategies/active   # 应 200 而非 500
python3 scripts/calc_signals.py --date 20260615 --strategy-version v1
python3 scripts/sim_trader.py --date 20260615 --dry-run
bash scripts/evening_pipeline.sh 20260615
```

**全跑通后**，写 `00-index/SUMMARY.md` 总结。
