# OpenClaw-Py v0.1.3 发布说明

**发布日期**: 2026-03-14

## 概述

本版本以 **Flet UI 增强与文档/参考体系重构** 为主：响应式布局、国际化、PWA、新面板与快捷键齐备，同时完成 M0 文档重建（里程碑驱动的 PROGRESS + REFERENCE_TABLES），并接入 MkDocs 文档站与 GitHub Pages 部署。

## 主要变更

### 新增
- **UI 能力**
  - 响应式 Shell（断点布局）、外置 locale JSON（i18n）、桌面托盘快捷操作
  - PWA：manifest、service worker、离线缓存
  - 提供商/模型联动配置、CJK 字体回退、加载与动效（shimmer、气泡淡入、发送按钮动效）
  - 聊天导出 Markdown、附件、快捷键（Cmd/Ctrl+K 搜索、+N 新会话、+E 导出）
  - 流式打字指示、回到底部浮动按钮、可复用组件（page_header、empty_state、card_tile、status_chip）
- **新面板**
  - 配置、Cron、调试、实例、日志、节点、总览、计划、会话、技能、系统、用量等面板
- **文档与流程**
  - MkDocs 文档站与 GitHub Pages 部署工作流
  - 参考文档重构：PROGRESS.md（里程碑/看板）+ REFERENCE_TABLES.md（六大矩阵）

### 变更
- 提供商默认值统一至 `model_catalog._KNOWN_PROVIDERS`
- 工具栏重构为 `ChatToolbar`，动态模型更新
- 气泡样式优化（圆角、角色头像、阴影）
- 提供商名称英文优先、CJK 括号内
- 依赖拆分：频道相关 SDK 放入可选 `[channels]` extra
- 参考与文档目录整理，历史规划归档

### 修复
- Flet Dropdown 使用 `on_select` 替代 `on_change`
- `ft.alignment.bottom_center` 改为 `ft.Alignment(0, 1)` 以兼容 Flet
- ChatMessage 搜索：构造函数中初始化 `_message_content`
- 工具展示元数据：修正嵌套 key 访问与回退

## 安装

```bash
pip install openclaw-py==0.1.3
```

## 链接

- [变更列表 (v0.1.2...v0.1.3)](https://github.com/chensaics/openclaw-py/compare/v0.1.2...v0.1.3)
- [CHANGELOG 全文](../CHANGELOG.md)
