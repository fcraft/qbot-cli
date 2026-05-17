"""CLI 入口 — typer"""
import json
import os
import sys
from typing import Optional

import typer

from . import __version__
from .api import send_c2c_message
from .serve import create_server

app = typer.Typer(name="qqbot", help="QQ Bot 消息推送 CLI")


def _print_result(result: dict):
    """打印结果并根据 errcode 决定退出码"""
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if result.get("errcode") == 0 else 1)


@app.command(name="send")
def cmd_send(
    content: Optional[str] = typer.Argument(None, help="消息内容"),
    target: str = typer.Option(
        None, "--target", "-t",
        help="目标用户 openid (默认从 QBOT_CLI_PUSH_USER_OPENID 读取)",
    ),
    type: str = typer.Option(
        "text", "--type", "-m",
        help="消息类型: text / markdown",
    ),
    file: Optional[str] = typer.Option(
        None, "--file", "-f",
        help="从文件读取消息内容 (规避 shell 转义问题)",
    ),
):
    """发送 C2C 私聊消息"""
    if file:
        if not os.path.exists(file):
            print(f"Error: file not found: {file}", file=sys.stderr)
            sys.exit(1)
        with open(file, "r", encoding="utf-8") as f:
            content = f.read()
    elif content is None:
        print("Error: 需要提供消息内容或 --file 参数", file=sys.stderr)
        sys.exit(1)

    if type == "markdown":
        msg_type = 2
    else:
        msg_type = 0

    _print_result(send_c2c_message(
        content=content,
        target=target,
        msg_type=msg_type,
    ))


@app.command(name="config")
def cmd_config(
    quiet: bool = typer.Option(False, "-q", "--quiet", help="仅输出状态，不显示测试提示"),
):
    """检查环境配置状态"""
    print("qqbot-cli 环境检查\n")

    app_id = os.getenv("QBOT_CLI_APPID")
    secret = os.getenv("QBOT_CLI_SECRET")
    openid = os.getenv("QBOT_CLI_PUSH_USER_OPENID")

    def _mask(s: str, show: int = 6) -> str:
        return s[:show] + "..." if len(s) > show else s

    if app_id:
        print(f"  QBOT_CLI_APPID   ✅  {_mask(app_id)}")
    else:
        print("  QBOT_CLI_APPID   ❌  未设置")

    if secret:
        print(f"  QBOT_CLI_SECRET  ✅  {_mask(secret)}")
    else:
        print("  QBOT_CLI_SECRET  ❌  未设置")

    if openid:
        print(f"  QBOT_CLI_PUSH_USER_OPENID   ✅  {_mask(openid, 8)}")
    else:
        print("  QBOT_CLI_PUSH_USER_OPENID   ❌  未设置（目标 openid）")

    print(f"\n  qqbot-cli         v{__version__}")

    missing = []
    if not app_id: missing.append("QBOT_CLI_APPID")
    if not secret: missing.append("QBOT_CLI_SECRET")
    if not openid: missing.append("QBOT_CLI_PUSH_USER_OPENID")

    if missing:
        print("\n" + "=" * 50)
        print("缺失环境变量，请设置：")
        print()
        print('  export QBOT_CLI_APPID="your_bot_appid"')
        print('  export QBOT_CLI_SECRET="your_bot_client_secret"')
        print('  export QBOT_CLI_PUSH_USER_OPENID="target_user_openid"')
        print()
        print("添加到 ~/.zshrc 后 source ~/.zshrc")
        sys.exit(1)

    if not quiet:
        print(f'\n  快速测试: qqbot send "test message"')


@app.command(name="serve")
def cmd_serve(
    port: int = typer.Option(8080, "--port", "-p", help="监听端口 (QQ 仅支持 80/443/8080/8443)"),
    save_to: Optional[str] = typer.Option(None, "--save-to", "-o", help="持久化 openid 到指定文件"),
):
    """启动 Webhook 回调服务，自动捕获用户 openid

    启动 HTTP 服务后，需要用 ngrok/frp 暴露公网地址，
    再到 https://q.qq.com/qqbot/#/developer/webhook-setting 配置回调 URL。

    工作流程：
      1. qqbot serve                          # 启动服务
      2. ngrok http 8080                      # 暴露公网地址
      3. 在 QQ Bot 管理端配置回调 URL          # 填入 ngrok 地址
      4. 打开 QQ，向 Bot 发一条消息            # 触发事件
      5. 访问 http://localhost:8080 查看 openid # 已自动捕获
      6. export QBOT_CLI_PUSH_USER_OPENID="<openid>"      # 设置环境变量
      7. Ctrl+C 停止服务，移除管理端回调配置     # 恢复 openclaw 连接
    """
    app_id = os.getenv("QBOT_CLI_APPID", "")
    secret = os.getenv("QBOT_CLI_SECRET", "")

    if not app_id or not secret:
        print("Error: QBOT_CLI_APPID 和 QBOT_CLI_SECRET 环境变量未设置", file=sys.stderr)
        sys.exit(1)

    server = create_server(app_id=app_id, secret=secret, port=port, save_to=save_to)

    print(f"""
╔══════════════════════════════════════════════════════╗
║         qqbot-cli Webhook 回调服务 v{__version__}           ║
╠══════════════════════════════════════════════════════╣
║  监听端口 : {port:<5}                                   ║
║  回调路径 : POST /                                  ║
║  状态页面 : GET  /                                  ║
╠══════════════════════════════════════════════════════╣
║  下一步:                                             ║
║  1. ngrok http {port}                                 ║
║  2. 在 https://q.qq.com/qqbot/#/developer/           ║
║     webhook-setting 配置回调 URL                      ║
║  3. 向 Bot 发一条消息                                 ║
║  4. 刷新 GET / 页面查看捕获的 openid                   ║
╚══════════════════════════════════════════════════════╝
""")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
        server.server_close()


@app.callback(invoke_without_command=True)
def _global(
    ctx: typer.Context,
    _version: bool = typer.Option(False, "--version", help="输出版本号"),
):
    """qqbot — QQ Bot C2C 消息推送 CLI"""
    if _version:
        from . import __version__
        print(f"qqbot-cli v{__version__}")
        sys.exit(0)

    if ctx.invoked_subcommand is None:
        print(ctx.get_help())
        sys.exit(0)
