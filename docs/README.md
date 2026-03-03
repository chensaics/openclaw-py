# OpenClaw-Py 文档

> **pyclaw** — 多通道 AI 网关，将 AI Agent 连接到 25+ 消息平台。

---

## 入门

- [快速开始](quickstart.md) — 从零到首次对话，5 分钟上手
- [安装指南](install.md) — 所有安装方式与可选依赖
- [README](../README.md) — 项目总览、特性列表、CLI 速查表

## 配置

- [配置说明](configuration.md) — 配置文件路径、格式、常见任务与热重载
- [环境变量](configuration.md#环境变量) — 核心环境变量一览

## 概念与架构

- [概念总览](concepts.md) — Gateway、Agent、会话、记忆、工具、通道与安全
- [架构设计](architecture.md) — 面向开发者的组件详解与设计决策

## API

- [API 参考](api-reference.md) — Gateway WebSocket RPC + OpenAI 兼容 HTTP + MCP

## CLI

- [CLI 命令参考](../README.md#cli-reference) — 全部 CLI 命令速查表

## 通道与提供商

- [支持的通道](../README.md#supported-channels) — 25 个消息通道列表
- [LLM 提供商](../README.md#supported-llm-providers) — 核心 + OpenAI 兼容 + 中国提供商

## 工具与自动化

- [MCP 工具](../README.md#mcp-model-context-protocol) — 外部工具服务器接入
- [定时任务](api-reference.md#定时任务) — cron 定时任务 API

## 帮助

- [故障排除](troubleshooting.md) — 常见问题与诊断命令

## 内部参考

以下为开发团队内部参考资料：

- [进度记录](reference/PROGRESS.md) — 开发阶段进度
- [待办清单](reference/20260302_todo.md) — 当前待办事项
- [差距分析](reference/gap-analysis.md) — 功能差距分析
- [UI 升级计划](reference/ui_upgrade_plan.md) — Flet 重构 + Flutter 美化计划
- [maxclaw 对比](reference/maxclaw_comparison_plan.md) — maxclaw 功能集成计划
- [国际化资源](../.i18n/README.md) — 翻译词汇表与翻译记忆
