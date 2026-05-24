# AUTO-STOCK
自己学习的股票引擎

## 服务器一键同步（可直接拉取）
在云服务器项目目录执行：

```bash
bash scripts/sync_repo.sh
```

- 默认同步 `main` 分支。
- 也可指定分支：`bash scripts/sync_repo.sh work`
- 若指定分支在远端不存在，会自动回退到 `main`。

## 日常更新建议
```bash
bash scripts/sync_repo.sh
python scripts/update_data.py
```
