# qqbot-cli

QQ Bot 消息推送 CLI，通过 QQ Bot API v2 发送 C2C 私聊消息。零外部 HTTP 依赖（仅 typer 用于 CLI 框架）。

## 安装

### 方式一：uv tool（推荐）

```bash
uv tool install git+ssh://git@github.com/HJH201314/qbot-cli.git
```

### 方式二：本地开发安装

```bash
cd repos/qqbot-cli
uv pip install -e .
```

## 配置

```bash
export QBOT_CLI_APPID="your_bot_appid"
export QBOT_CLI_SECRET="your_bot_client_secret"
export QBOT_CLI_PUSH_USER_OPENID="target_user_openid"
```

## 使用

### 发送消息

```bash
# 文本消息（默认）
qqbot send "构建完成"

# markdown 消息
qqbot send --type markdown "**构建完成** ✅"

# 从文件读取内容（推荐，规避 shell 转义）
qqbot send --file /tmp/msg.md --type markdown

# 发送给指定 openid
qqbot send -t OPENID "hello"
```

### 检查配置

```bash
qqbot config
```

### 获取 openid（首次配置）

```bash
# 启动回调服务
qqbot serve

# 另一个终端：创建公网隧道
ngrok http 8080

# 在 QQ Bot 管理端配置回调 URL
# https://q.qq.com/qqbot/#/developer/webhook-setting

# 打开 QQ 向 Bot 发一条消息
# 访问 http://localhost:8080 查看捕获的 openid
```
