# 配置文件 — 从 .env 读取密钥（不在代码中硬编码）
#
# 优先级：环境变量 > .env 文件 > 报错
# 各台机器（本地 / 云服务器）独立维护自己的 .env，互不影响。
import os
from pathlib import Path


def _load_dotenv() -> None:
    """轻量 .env 加载器：把 KEY=VALUE 写到 os.environ（仅当未设置时）。

    没有第三方依赖，避免 python-dotenv。
    """
    env_file = Path(__file__).parent.parent / ".env"
    if not env_file.exists():
        return
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            # 已有的环境变量不覆盖（systemd Environment 优先）
            if key and key not in os.environ:
                os.environ[key] = value
    except Exception:
        # 配置加载失败不应阻塞导入；后续 require_env 时会报错
        pass


_load_dotenv()


def _require_env(key: str, hint: str = "") -> str:
    val = os.environ.get(key, "").strip()
    if not val:
        raise RuntimeError(
            f"缺少环境变量 {key}。"
            f"请在 .env 文件或 systemd Environment 中配置。{hint}"
        )
    return val


# === tushare.pro token ===
# 获取：https://tushare.pro 个人中心 → token
TUSHARE_TOKEN = _require_env(
    "TUSHARE_TOKEN",
    "可去 tushare.pro 个人中心获取/重置。",
)

# === API 操作密码（持仓/统计/策略 实操时用） ===
# 用户在 stock.auto-claw.top 点"买入"等按钮时弹密码框
API_PASSWORD = _require_env(
    "API_PASSWORD",
    "建议在 .env 中设为强密码。",
)
