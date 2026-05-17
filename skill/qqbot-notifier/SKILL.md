---
name: qqbot-notifier
description: QQ Bot 消息推送通知 CLI。需要向 QQ 推送通知或消息时使用。适用场景：(1) CI/CD 构建完成后通知 (2) 监控告警推送 (3) 定时提醒 (4) 开发工作流中的状态通知。
metadata: {"openclaw":{"emoji":"🐧","requires":{"env":["QBOT_CLI_APPID","QBOT_CLI_SECRET","QBOT_CLI_PUSH_USER_OPENID"]}}}
---

# QQ Bot 消息推送

通过 QQ Bot API v2 发送 C2C 私聊消息，支持文本和 markdown 格式。

## Setup

需要安装 `qqbot` CLI（首次使用前）：
```bash
uv tool install git+ssh://git@github.com/HJH201314/qbot-cli.git
# 或 pipx install git+ssh://...
```

环境变量（必须配置）：
```bash
export QBOT_CLI_APPID="your_bot_appid"
export QBOT_CLI_SECRET="your_bot_client_secret"
export QBOT_CLI_PUSH_USER_OPENID="target_user_openid"
```

## Usage

### 推荐：使用 --file 传递消息内容

当消息内容包含代码块（反引号）、`$` 变量、`{}`、换行符等特殊字符时，**必须使用 `--file`**，
否则 shell 会解析这些特殊字符导致命令失败。

**标准流程（两步走）：**

```bash
# 第一步：将消息内容写入临时文件
cat > /tmp/qqbot_msg.md << 'EOF'
**构建完成** ✅

修改了以下文件：
- `src/main/kotlin/Foo.kt`
EOF

# 第二步：通过文件路径发送
qqbot send --file /tmp/qqbot_msg.md --type markdown
```

### 简单消息

```bash
# 文本消息（默认）
qqbot send "构建完成 ✅"

# markdown 消息
qqbot send --type markdown "**构建完成** ✅"

# 从文件发送（推荐）
qqbot send --file /tmp/msg.md --type markdown

# 发送给指定 openid（覆盖默认值）
qqbot send -t OPENID "hello"
```

### 检查配置

```bash
qqbot config
```

## 参数说明

| 参数 | 说明 |
|------|------|
| `content` | 消息内容（位置参数） |
| `--target`, `-t` | 目标用户 openid（默认从 QBOT_CLI_PUSH_USER_OPENID 读取） |
| `--type`, `-m` | 消息类型：text（默认）/ markdown |
| `--file`, `-f` | 从文件读取消息内容（**推荐**，规避 shell 转义） |

### 获取 openid（首次配置）

如果不知道目标用户的 openid，使用 `qqbot serve` 自动捕获：

```bash
# 终端 1: 启动 Webhook 回调服务
qqbot serve

# 终端 2: 创建公网隧道
ngrok http 8080

# 然后在 QQ Bot 管理端配置回调 URL
# https://q.qq.com/qqbot/#/developer/webhook-setting
# 填入 ngrok 提供的 HTTPS 地址

# 打开 QQ 向 Bot 发一条消息
# 访问 http://localhost:8080 即可看到捕获的 openid

# 设置后即可正常使用
export QBOT_CLI_PUSH_USER_OPENID="<捕获到的_openid>"
```

**重要**: 获取 openid 后务必在管理端移除回调 URL，恢复 openclaw gateway 正常运行。

## 参数说明

| 参数 | 说明 |
|------|------|
| `content` | 消息内容（位置参数） |
| `--target`, `-t` | 目标用户 openid（默认从 QBOT_CLI_PUSH_USER_OPENID 读取） |
| `--type`, `-m` | 消息类型：text（默认）/ markdown |
| `--file`, `-f` | 从文件读取消息内容（**推荐**，规避 shell 转义） |

| `qqbot serve` 参数 | 说明 |
|------|------|
| `--port`, `-p` | 监听端口（默认 8080，QQ 仅支持 80/443/8080/8443） |
| `--save-to`, `-o` | 持久化 openid 到文件 |

## Tips

- 使用 `**bold**` 加粗
- 开头加 emoji 便于视觉分类（🎉✅❌🚨📢）
- 含代码块的消息**一律用 `--file`**，避免反引号被 shell 解析
- Token 自动管理，无需手动刷新（有效期 2 小时，CLI 内部自动续期）
- `qqbot serve` 仅在首次获取 openid 时使用，获取后应恢复 openclaw 的 WebSocket 连接
