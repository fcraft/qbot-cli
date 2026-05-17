"""QQ Bot API v2 — token 管理与消息发送（零外部依赖）"""
import json
import os
import time
import threading
from typing import Optional
from urllib import request, error

TOKEN_URL = "https://bots.qq.com/app/getAppAccessToken"
API_BASE = "https://api.sgroup.qq.com"


class TokenManager:
    """access_token 生命周期管理，内置刷新和并发保护"""

    def __init__(self, app_id: str, client_secret: str):
        self._app_id = app_id
        self._client_secret = client_secret
        self._token: Optional[str] = None
        self._expires_at: float = 0.0
        self._lock = threading.Lock()

    def get_token(self) -> str:
        """获取有效 token，必要时自动刷新"""
        now = time.time()
        if self._token and now < self._expires_at - 60:
            return self._token

        with self._lock:
            # 双重检查：可能其他线程已刷新
            if self._token and now < self._expires_at - 60:
                return self._token

            body = json.dumps({
                "appId": self._app_id,
                "clientSecret": self._client_secret,
            }).encode("utf-8")
            req = request.Request(
                TOKEN_URL, data=body,
                headers={"Content-Type": "application/json"},
            )
            try:
                with request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
            except error.HTTPError as e:
                raise RuntimeError(f"获取 access_token 失败: HTTP {e.code} {e.reason}")
            except Exception as e:
                raise RuntimeError(f"获取 access_token 失败: {e}")

            token = data.get("access_token")
            if not token:
                raise RuntimeError(f"access_token 为空，响应: {data}")

            expires_in = int(data.get("expires_in", 7200))
            self._token = token
            self._expires_at = time.time() + expires_in
            return self._token


# ---------------------------------------------------------------------------
# 全局 TokenManager（首次调用时按环境变量初始化）
# ---------------------------------------------------------------------------

_token_manager: Optional[TokenManager] = None
_default_target: Optional[str] = None


def _get_manager() -> TokenManager:
    global _token_manager
    if _token_manager is None:
        app_id = os.getenv("QBOT_CLI_APPID", "")
        secret = os.getenv("QBOT_CLI_SECRET", "")
        if not app_id or not secret:
            raise RuntimeError(
                "QBOT_CLI_APPID 和 QBOT_CLI_SECRET 环境变量未设置"
            )
        _token_manager = TokenManager(app_id, secret)
    return _token_manager


def _get_default_target() -> str:
    global _default_target
    if _default_target is None:
        target = os.getenv("QBOT_CLI_PUSH_USER_OPENID", "")
        if not target:
            raise RuntimeError(
                "QBOT_CLI_PUSH_USER_OPENID 环境变量未设置（目标 openid）"
            )
        _default_target = target
    return _default_target


# ---------------------------------------------------------------------------
# 消息发送
# ---------------------------------------------------------------------------

def send_c2c_message(
    content: str,
    target: Optional[str] = None,
    msg_type: int = 0,
) -> dict:
    """发送 C2C 私聊消息

    Args:
        content: 消息文本内容
        target: 目标用户 openid（默认从 QBOT_CLI_PUSH_USER_OPENID 读取）
        msg_type: 0=文本, 2=markdown

    Returns:
        {"errcode": 0, "id": "...", "timestamp": ...}
        失败时 {"errcode": -1, "errmsg": "..."}
    """
    openid = target or _get_default_target()
    mgr = _get_manager()

    try:
        token = mgr.get_token()
    except RuntimeError as e:
        return {"errcode": -1, "errmsg": str(e)}

    body: dict = {"msg_seq": 1}
    if msg_type == 2:
        body["msg_type"] = 2
        body["markdown"] = {"content": content}
    else:
        body["msg_type"] = 0
        body["content"] = content

    url = f"{API_BASE}/v2/users/{openid}/messages"
    data = json.dumps(body).encode("utf-8")

    try:
        req = request.Request(url, data=data, headers={
            "Authorization": f"QQBot {token}",
            "Content-Type": "application/json",
        })
        with request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            result["errcode"] = 0
            return result
    except error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return {"errcode": -1, "errmsg": f"HTTP {e.code}: {err_body[:500]}"}
    except Exception as e:
        return {"errcode": -1, "errmsg": str(e)}
