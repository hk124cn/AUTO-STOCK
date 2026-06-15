"""API 操作密码鉴权。

设计：单密码 + in-memory token dict。
- 用户在持仓/统计/策略页面做实操时，前端调 /api/v1/auth/login 换 token
- token 存 localStorage，24h 过期
- 11 个写端点通过 Depends(verify_token) 校验 Authorization: Bearer <token>
- 服务重启 / token 过期 → 重新弹密码
- 公开端点（GET + POST /api/v1/feedback）不受影响
"""
import os
import secrets
import time
from typing import Optional

from fastapi import Header, HTTPException


# === 密码来源：环境变量 > config.py ===
def _resolve_password() -> str:
    env_pw = os.environ.get("STOCK_API_PASSWORD", "").strip()
    if env_pw:
        return env_pw
    try:
        from config.config import API_PASSWORD  # type: ignore
        return API_PASSWORD
    except (ImportError, AttributeError):
        return ""


API_PASSWORD = _resolve_password()
if not API_PASSWORD:
    raise RuntimeError(
        "未配置 API 密码。请设置环境变量 STOCK_API_PASSWORD，"
        "或在 config/config.py 定义 API_PASSWORD"
    )


# === Token 存储（in-memory dict，重启失效） ===
# 结构: {token: expires_at_unix_seconds}
_TOKEN_STORE: dict[str, float] = {}
_TOKEN_TTL_SEC = 24 * 3600  # 24 小时


def login(password: str) -> dict:
    """用密码换 token。密码错 → 401。"""
    if password != API_PASSWORD:
        raise HTTPException(status_code=401, detail="密码错误")
    token = secrets.token_urlsafe(32)
    _TOKEN_STORE[token] = time.time() + _TOKEN_TTL_SEC
    return {"token": token, "expires_in": _TOKEN_TTL_SEC}


async def verify_token(authorization: Optional[str] = Header(None)) -> str:
    """FastAPI 依赖：校验 Authorization: Bearer <token>。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="需要登录。请在持仓/统计页面点操作时输入操作密码。",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="token 为空")
    expires_at = _TOKEN_STORE.get(token)
    if expires_at is None or expires_at < time.time():
        _TOKEN_STORE.pop(token, None)
        raise HTTPException(
            status_code=401,
            detail="token 已过期或无效，请重新输入操作密码。",
        )
    return token


def cleanup_expired_tokens() -> int:
    """清理过期 token，返回清理数量。可由 cron 定期调用。"""
    now = time.time()
    expired = [t for t, exp in _TOKEN_STORE.items() if exp < now]
    for t in expired:
        _TOKEN_STORE.pop(t, None)
    return len(expired)


def active_token_count() -> int:
    """当前活跃 token 数（调试用）。"""
    now = time.time()
    return sum(1 for exp in _TOKEN_STORE.values() if exp > now)
