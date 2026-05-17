"""QQ Bot Webhook 回调服务 — 自动捕获用户 openid"""
import json
import os
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional
from urllib.parse import urlparse, parse_qs

from cryptography.hazmat.primitives.asymmetric import ed25519


def _derive_seed(secret: str) -> bytes:
    """用 bot secret 派生 Ed25519 种子（对齐 Go 版本算法）"""
    seed = secret.encode("utf-8")
    while len(seed) < 32:
        seed = seed * 2
    return seed[:32]


def compute_signature(secret: str, plain_token: str, event_ts: str) -> str:
    """计算 QQ Bot 回调验证签名: Ed25519(secret_seed, event_ts + plain_token)"""
    seed = _derive_seed(secret)
    private_key = ed25519.Ed25519PrivateKey.from_private_bytes(seed)
    msg = (event_ts + plain_token).encode("utf-8")
    return private_key.sign(msg).hex()


class OpenIDStore:
    """线程安全的 openid 记录存储"""

    def __init__(self, filepath: Optional[str] = None):
        self._lock = threading.Lock()
        self._records: list[dict] = []
        self._filepath = filepath
        if filepath and os.path.exists(filepath):
            self._load()

    def _load(self):
        try:
            with open(self._filepath, "r", encoding="utf-8") as f:
                self._records = json.load(f)
        except Exception:
            pass

    def _save(self):
        if self._filepath:
            with open(self._filepath, "w", encoding="utf-8") as f:
                json.dump(self._records, f, indent=2, ensure_ascii=False)

    def add(self, openid: str, event_type: str, content: str, raw_event: dict):
        with self._lock:
            # 去重
            for r in self._records:
                if r["openid"] == openid:
                    r["count"] += 1
                    r["last_seen"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    r["last_content"] = content
                    self._save()
                    return
            self._records.append({
                "openid": openid,
                "first_seen": time.strftime("%Y-%m-%d %H:%M:%S"),
                "last_seen": time.strftime("%Y-%m-%d %H:%M:%S"),
                "event_type": event_type,
                "last_content": content,
                "count": 1,
            })
            self._save()

    def get_all(self) -> list[dict]:
        with self._lock:
            return list(self._records)


class CallbackHandler(BaseHTTPRequestHandler):
    """QQ Bot Webhook 回调处理器"""

    app_id: str = ""
    secret: str = ""
    store: Optional[OpenIDStore] = None

    def log_message(self, format, *args):
        """重定向日志到 stdout"""
        print(f"[{time.strftime('%H:%M:%S')}] {args[0]}")

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length)

    def _json_ok(self, data: dict):
        body = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json_err(self, code: int, msg: str):
        body = json.dumps({"error": msg}).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_verify(self, payload: dict):
        """op=13: 回调地址验证"""
        d = payload.get("d", {})
        plain_token = d.get("plain_token", "")
        event_ts = d.get("event_ts", "")
        if not plain_token or not event_ts:
            self._json_err(400, "missing plain_token or event_ts")
            return

        signature = compute_signature(self.secret, plain_token, event_ts)
        print(f"  ✅ 回调验证成功")
        self._json_ok({"plain_token": plain_token, "signature": signature})

    def _handle_dispatch(self, payload: dict):
        """op=0: 事件分发"""
        event_type = payload.get("t", "UNKNOWN")
        d = payload.get("d", {})
        openid = ""

        if event_type == "C2C_MESSAGE_CREATE":
            openid = d.get("author", {}).get("user_openid", "")
            content = d.get("content", "")
            print(f"  📨 C2C_MESSAGE_CREATE | openid={openid} | content={content[:50]}")
        elif event_type == "GROUP_AT_MESSAGE_CREATE":
            openid = d.get("author", {}).get("member_openid", "")
            group_openid = d.get("group_openid", "")
            content = d.get("content", "")
            print(f"  📨 GROUP_AT_MESSAGE_CREATE | member_openid={openid} | group={group_openid} | content={content[:50]}")
        else:
            print(f"  📨 {event_type} (未提取 openid)")
            # Try to extract any openid-like field
            author = d.get("author", {})
            openid = author.get("user_openid") or author.get("member_openid") or author.get("id") or ""

        if openid and self.store:
            content = d.get("content", "")
            self.store.add(openid, event_type, content, d)

        # ACK: 返回空 JSON
        self._json_ok({})

    def do_POST(self):
        raw = self._read_body()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            self._json_err(400, "invalid JSON")
            return

        op = payload.get("op", -1)
        print(f"  ← POST op={op} id={payload.get('id', '?')}")

        if op == 13:
            self._handle_verify(payload)
        elif op == 0:
            self._handle_dispatch(payload)
        else:
            # 未知 opcode，返回 ack
            print(f"  ⚠️ 未知 opcode: {op}")
            self._json_ok({})

    def do_GET(self):
        """显示捕获的 openid 列表（HTML 页面）"""
        if not self.store:
            self._json_err(500, "store not initialized")
            return

        records = self.store.get_all()
        rows = ""
        for r in records:
            rows += f"""<tr>
                <td><code>{r['openid']}</code></td>
                <td>{r['event_type']}</td>
                <td>{r['first_seen']}</td>
                <td>{r['last_seen']}</td>
                <td>{r['last_content'][:60]}</td>
                <td>{r['count']}</td>
            </tr>"""

        html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>qqbot-cli — OpenID 捕获</title>
<style>
  body {{ font-family: -apple-system, "SF Mono", monospace; max-width: 960px; margin: 40px auto; padding: 0 20px; background: #0d1117; color: #c9d1d9; }}
  h1 {{ color: #58a6ff; font-size: 20px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
  th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid #21262d; font-size: 13px; }}
  th {{ color: #8b949e; font-weight: 600; }}
  code {{ background: #161b22; padding: 2px 6px; border-radius: 4px; color: #7ee787; }}
  .empty {{ color: #8b949e; margin-top: 40px; text-align: center; }}
  .note {{ color: #8b949e; font-size: 12px; margin-top: 40px; }}
</style>
</head>
<body>
<h1>qqbot-cli — 捕获的 OpenID</h1>
<table>
<tr><th>OpenID</th><th>事件类型</th><th>首次捕获</th><th>最近捕获</th><th>最近内容</th><th>次数</th></tr>
{rows if rows else '<tr><td colspan="6" class="empty">等待 QQ Bot 回调事件… 请向 Bot 发送一条消息</td></tr>'}
</table>
<p class="note">访问此页面即刷新。设置 <code>export QBOT_CLI_PUSH_USER_OPENID="&lt;你的openid&gt;"</code> 后即可使用 <code>qqbot send</code> 推送消息。</p>
</body>
</html>"""
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_server(
    app_id: str,
    secret: str,
    port: int = 8080,
    save_to: Optional[str] = None,
) -> HTTPServer:
    """创建 QQ Bot Webhook 回调服务器"""
    store = OpenIDStore(save_to)

    # 注入类变量
    CallbackHandler.app_id = app_id
    CallbackHandler.secret = secret
    CallbackHandler.store = store

    server = HTTPServer(("0.0.0.0", port), CallbackHandler)
    return server
