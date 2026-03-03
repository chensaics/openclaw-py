# 快速开始

从零到首次对话，5 分钟上手 pyclaw。

---

## 前置条件

- **Python 3.12** 或更高版本（运行 `python --version` 确认）
- 一个 **LLM API Key**（OpenAI、Anthropic、Google Gemini、Ollama 等均可）

## 安装

选择以下任一方式：

```bash
# macOS / Linux 一键安装
curl -fsSL https://raw.githubusercontent.com/chensaics/openclaw-py/master/scripts/install.sh | bash

# Windows (PowerShell)
irm https://raw.githubusercontent.com/chensaics/openclaw-py/master/scripts/install.ps1 | iex

# 通过 pip
pip install pyclaw

# 通过 pipx（推荐，隔离环境）
pipx install pyclaw
```

更多安装方式（Docker、Homebrew、源码等）请参阅 [安装指南](install.md)。

## 交互式设置

运行设置向导，配置 Provider、模型和 API Key：

```bash
pyclaw setup --wizard
```

向导会引导你完成：

1. 选择 LLM 提供商（Anthropic / OpenAI / Google / Ollama 等）
2. 输入 API Key
3. 设置默认模型
4. 可选：配置通道（Telegram、Discord 等）

## 首次对话

直接在终端与 Agent 对话：

```bash
pyclaw agent "你好，请介绍一下自己"
```

## 启动 Gateway

Gateway 是核心服务进程，为通道、UI 和 API 提供统一的运行时：

```bash
pyclaw gateway
```

默认监听 `http://127.0.0.1:18789`。

## 打开 UI

启动跨平台桌面 UI（自动连接到本地 Gateway）：

```bash
pyclaw ui
```

或以 Web 模式启动：

```bash
pyclaw ui --web --port 8550
```

> **推荐**: 先启动 Gateway (`pyclaw gateway`)，再启动 UI。UI 会自动通过 WebSocket 连接到 Gateway，获得流式聊天、会话管理、计划/定时任务管理、系统监控等完整功能。如果 Gateway 不可用，UI 会自动回退到本地进程内模式。

## 检查状态

确认各组件运行正常：

```bash
pyclaw status
```

深度诊断：

```bash
pyclaw doctor
```

## 常用环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OPENAI_API_KEY` | OpenAI API Key | — |
| `ANTHROPIC_API_KEY` | Anthropic API Key | — |
| `GOOGLE_API_KEY` | Google AI API Key | — |
| `PYCLAW_AUTH_TOKEN` | Gateway 认证 Token | — |
| `PYCLAW_GATEWAY_PORT` | Gateway 端口 | `18789` |
| `PYCLAW_STATE_DIR` | 状态目录 | `~/.pyclaw` |

## UI 功能概览

UI 提供 8 个功能页面，全部通过 Gateway WebSocket v3 协议与后端交互：

| 页面 | 功能 |
|------|------|
| Chat | 流式聊天、中断生成、消息编辑/重发、工具调用实时展示、计划进度条 |
| Agents | Agent 列表、创建、配置查看 |
| Channels | 消息通道连接状态 |
| Plans | 任务计划管理（查看步骤、恢复暂停、删除） |
| Cron | 定时任务管理（列表、添加、执行历史） |
| Voice | 语音合成 (TTS) 与语音转文字 (STT) |
| System | 系统信息、诊断、日志查看、数据备份 |
| Settings | 模型/Provider 配置、主题定制、语言切换 |

## 下一步

- [安装指南](install.md) — 完整安装方式与可选依赖
- [配置说明](configuration.md) — 配置文件详解、通道设置与热重载
- [概念总览](concepts.md) — 理解 Gateway、Agent、会话等核心概念
- [故障排除](troubleshooting.md) — 常见问题与诊断方法
- [UI 升级计划](reference/ui_upgrade_plan.md) — Flet 重构 + Flutter 美化计划
