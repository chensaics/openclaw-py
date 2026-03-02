# pyclaw UI 升级计划 — Flet 重构 + Flutter 美化

> 创建日期：2026-03-02

---

## 目录

- [1. 现状分析](#1-现状分析)
- [2. Phase 1 — Flet 重构（接入 Gateway + 功能完善）](#2-phase-1--flet-重构接入-gateway--功能完善)
  - [2.1 Gateway WebSocket Client](#21-gateway-websocket-client)
  - [2.2 Chat 页面重构](#22-chat-页面重构)
  - [2.3 新增页面 / 面板](#23-新增页面--面板)
  - [2.4 Session 管理增强](#24-session-管理增强)
  - [2.5 Settings 页面增强](#25-settings-页面增强)
  - [2.6 主题 / 布局增强](#26-主题--布局增强)
  - [2.7 工具接入](#27-工具接入)
- [3. Phase 2 — Flutter 原生美化](#3-phase-2--flutter-原生美化)
  - [3.1 Flutter 项目结构](#31-flutter-项目结构)
  - [3.2 视觉设计目标](#32-视觉设计目标)
  - [3.3 聊天体验增强](#33-聊天体验增强)
  - [3.4 平台特性](#34-平台特性)
  - [3.5 状态管理](#35-状态管理)
- [4. 实施路线](#4-实施路线)
- [5. 技术选型](#5-技术选型)

---

## 1. 现状分析

当前 UI 模块位于 `src/pyclaw/ui/`，共约 14 个文件 ~2,600 行代码。

### 文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `app.py` | ~905 | 主应用控制器：ChatView、SessionSidebar、SettingsView、导航 |
| `i18n.py` | ~302 | 国际化：内置翻译 + locale JSON 加载 |
| `agents_panel.py` | ~235 | Agent 列表 / 创建 / 编辑面板 |
| `onboarding.py` | ~194 | 4 步首次设置向导 |
| `media_preview.py` | ~142 | 图片 / 音频 / 视频预览组件 |
| `permissions.py` | ~146 | 移动端权限请求（麦克风、相机、存储） |
| `channels_panel.py` | ~126 | 频道状态面板 |
| `theme.py` | ~109 | 颜色方案、排版、间距、Flet Theme 转换 |
| `menubar.py` | ~106 | 桌面菜单栏（File/View/Help）— 未接入主布局 |
| `toolbar.py` | ~90 | 聊天工具栏（附件、语音、模型选择）— 未接入主布局 |
| `voice.py` | ~165 | TTS/STT 语音面板 |
| `tray.py` | ~69 | 系统托盘图标 |
| `locales/de.json` | ~46 | 德语翻译 |

### 当前架构

```
PyClawApp (app.py)
│
├── NavigationRail (Chat / Agents / Channels / Voice / Settings)
│
├── SessionSidebar ──► SessionManager (本地 JSONL)
│
├── Content Area (按导航索引切换)
│   ├── ChatView ──► run_agent() (进程内调用，非 Gateway)
│   ├── AgentsPanel
│   ├── ChannelStatusPanel ──► load_config() (读本地配置)
│   ├── Voice panel (edge-tts + Whisper API)
│   └── SettingsView
│
└── Progress listener ──► add_progress_listener()
```

### 现存问题

1. **未接入 Gateway**：UI 直接调用 `run_agent()`，与 Gateway 的 25+ RPC 方法完全隔离
2. **无流式渲染**：等待 Agent 完成后才一次性显示回复
3. **新功能缺失**：Plan / Interrupt / Message Bus / Cron History / Backup / Daily Summary 等功能在 UI 中完全未体现
4. **组件未接入**：`toolbar.py` 和 `menubar.py` 已定义但未使用
5. **主题简陋**：仅用 `color_scheme_seed` 设置 Flet Theme，无精细控制
6. **非响应式**：固定布局，未适配不同屏幕尺寸

---

## 2. Phase 1 — Flet 重构（接入 Gateway + 功能完善）

### 2.1 Gateway WebSocket Client

**新建文件**：`src/pyclaw/ui/gateway_client.py`

实现 WebSocket v3 协议客户端，作为 UI 与 Gateway 之间的通信层。

#### 协议格式

请求帧（client → server）：
```json
{
  "type": "req",
  "id": "unique-request-id",
  "method": "method.name",
  "params": { ... }
}
```

响应帧（server → client）：
```json
{
  "type": "res",
  "id": "same-request-id",
  "ok": true,
  "payload": { ... }
}
```

事件帧（server → client，推送）：
```json
{
  "type": "event",
  "event": "event.name",
  "payload": { ... },
  "seq": 42
}
```

#### 核心功能

| 功能 | 说明 |
|------|------|
| `connect()` | WebSocket 握手 + v3 协议 connect 认证 |
| `call(method, params)` | RPC 调用，返回 `Future[response]` |
| `on_event(event_name, callback)` | 注册事件监听器 |
| 自动重连 | 断线后指数退避重连 |
| 心跳保活 | 定期发送 `health` 保持连接 |

#### 影响范围

- `app.py` 中的 `_get_agent_reply()` 从直接调用 `run_agent()` 改为调用 `gateway_client.call("chat.send", ...)`
- 所有配置读写从 `load_config()` 改为 `config.get` / `config.set` RPC
- 会话管理从本地 `SessionManager` 改为 `sessions.*` RPC

### 2.2 Chat 页面重构

**修改文件**：`src/pyclaw/ui/app.py` — `ChatView` 类

#### 流式渲染

监听 Gateway 事件实现逐 token 显示：

| 事件 | UI 行为 |
|------|---------|
| `chat.agent_start` | 显示"思考中"指示器 |
| `chat.message_start` | 创建空消息气泡 |
| `chat.message_update` | 追加 `delta` 文本到当前气泡 |
| `chat.message_end` | 完成气泡，显示 token 用量 |
| `chat.tool_start` | 添加 ToolCallCard（加载状态） |
| `chat.tool_end` | 更新 ToolCallCard（展示结果） |
| `chat.agent_end` | 隐藏指示器 |
| `chat.error` | 显示错误提示 |

#### 新增交互

| 功能 | 实现 |
|------|------|
| 中断按钮 | 生成期间显示"停止"按钮 → `chat.abort` RPC |
| 消息编辑 | 用户消息右键 → `chat.edit` RPC |
| 消息重发 | 助手消息右键 → `chat.resend` RPC |
| Plan 进度条 | Chat 顶部区域显示当前 Plan 的步骤进度 |
| Timeline 展示 | 消息内嵌展示 timeline 条目（工具调用、状态变更） |
| 代码块增强 | Markdown 代码块语法高亮、复制按钮 |
| 消息搜索 | 输入框上方搜索栏，过滤会话消息 |

### 2.3 新增页面 / 面板

在 NavigationRail 中添加以下页面：

#### Plan 管理页

**新建文件**：`src/pyclaw/ui/plan_panel.py`

| RPC 方法 | UI 功能 |
|----------|---------|
| `plan.list` | 计划列表（标题、状态、进度百分比） |
| `plan.get` | 计划详情（步骤列表、各步骤状态） |
| `plan.resume` | 恢复暂停的计划 |
| `plan.delete` | 删除计划 |

视觉元素：
- Stepper 组件展示步骤链
- 每步骤带状态图标（pending / running / completed / failed）
- 进度条显示总体完成度

#### Cron 管理页

**新建文件**：`src/pyclaw/ui/cron_panel.py`

| RPC 方法 | UI 功能 |
|----------|---------|
| `cron.list` | 定时任务列表 |
| `cron.add` | 添加定时任务表单（cron / interval / once） |
| `cron.remove` | 删除定时任务 |
| `cron.history` | 执行历史时间线 |

视觉元素：
- 任务卡片（名称、调度表达式、启用状态、下次执行时间）
- 执行历史表格（时间、状态、输出摘要）

#### Backup 管理页

**新建文件**：`src/pyclaw/ui/backup_panel.py`

| RPC 方法 | UI 功能 |
|----------|---------|
| `backup.export` | 一键导出备份 |
| `backup.status` | 备份列表（文件名、大小、日期） |

#### MCP 状态页

**新建文件**：`src/pyclaw/ui/mcp_panel.py`

- 显示已连接的 MCP 服务器列表
- 每个服务器下展示可用工具及其 schema

#### 系统监控页

**新建文件**：`src/pyclaw/ui/system_panel.py`

| RPC 方法 | UI 功能 |
|----------|---------|
| `system.info` | 系统信息（平台、Python 版本、内存） |
| `doctor.run` | 诊断检查结果 |
| `usage.get` | Token 用量统计图表 |
| `logs.tail` | 实时日志滚动 |

### 2.4 Session 管理增强

**修改文件**：`src/pyclaw/ui/app.py` — `SessionSidebar` 类

| 功能 | 实现 |
|------|------|
| Gateway 接入 | `sessions.list` / `sessions.preview` / `sessions.delete` / `sessions.reset` |
| 会话搜索 | 顶部搜索框，过滤会话列表 |
| 会话重命名 | 双击会话名编辑 |
| 会话分组 | 按日期分组（今天 / 昨天 / 本周 / 更早） |

### 2.5 Settings 页面增强

**修改文件**：`src/pyclaw/ui/app.py` — `SettingsView` 类

| 功能 | 实现 |
|------|------|
| 配置读写 | `config.get` / `config.set` / `config.patch` RPC |
| Agent 管理 | `agents.list` / `agents.add` / `agents.remove` |
| Model 选择器 | `models.list` / `models.providers` 动态获取 |
| Channel 配置 | `channels.list` / `channels.status` 实时状态 |
| Auth 管理 | Auth profile 管理面板 |
| 语言切换 | 下拉选择 locale（en / zh-CN / ja / de） |
| 主题定制 | 种子色选择器 + 实时预览 |

### 2.6 主题 / 布局增强

**修改文件**：`src/pyclaw/ui/theme.py`、`src/pyclaw/ui/app.py`

#### 布局改进

| 场景 | 布局 |
|------|------|
| 桌面 (>1200px) | NavigationRail + SessionSidebar + ContentArea |
| 平板 (600-1200px) | 可折叠 Drawer + ContentArea |
| 手机 (<600px) | 底部 NavigationBar + 全屏 Content + 滑动 Drawer |

#### 视觉改进

- 接入 `toolbar.py` 和 `menubar.py` 到主布局
- 头像 / 角色图标（用户 / 助手 / 系统）
- 消息气泡圆角、微妙阴影、呼吸间距
- 代码块主题随暗色 / 亮色模式自动切换
- 页面切换过渡动画
- 消息出现淡入动画
- 自定义主题色选择器

### 2.7 工具接入

| 功能 | 实现 |
|------|------|
| 文件上传 | 拖拽上传，通过 `chat.send` 的 `attachments` 参数传递 |
| 浏览器控制 | `browser.*` RPC 面板（导航、截图、点击） |
| 语音优化 | TTS + Whisper 通过 Gateway `tts.*` 方法 |

---

## 3. Phase 2 — Flutter 原生美化

### 3.1 Flutter 项目结构

在项目根目录新建 `flutter_app/`：

```
flutter_app/
├── lib/
│   ├── main.dart                      # 入口
│   ├── app.dart                       # MaterialApp + 路由
│   ├── core/
│   │   ├── gateway_client.dart        # WebSocket v3 协议客户端 (Dart)
│   │   ├── models/                    # 数据模型
│   │   │   ├── message.dart           # Message, ToolCall, Timeline
│   │   │   ├── session.dart           # Session
│   │   │   ├── plan.dart              # Plan, Step
│   │   │   ├── cron_job.dart          # CronJob, ExecutionRecord
│   │   │   ├── agent.dart             # Agent config
│   │   │   └── channel.dart           # Channel status
│   │   ├── providers/                 # Riverpod 状态管理
│   │   │   ├── gateway_provider.dart  # 连接状态
│   │   │   ├── chat_provider.dart     # 消息流
│   │   │   ├── session_provider.dart  # 会话列表
│   │   │   ├── config_provider.dart   # 配置
│   │   │   └── plan_provider.dart     # 计划
│   │   └── theme/
│   │       ├── app_theme.dart         # Material 3 ThemeData
│   │       ├── colors.dart            # 颜色 tokens
│   │       └── typography.dart        # 字体 tokens
│   ├── features/
│   │   ├── chat/
│   │   │   ├── chat_page.dart         # 聊天页面
│   │   │   ├── message_list.dart      # 消息列表
│   │   │   └── chat_input.dart        # 输入框 + 工具栏
│   │   ├── sessions/
│   │   │   ├── sessions_page.dart     # 会话管理
│   │   │   └── session_tile.dart      # 会话列表项
│   │   ├── plans/
│   │   │   ├── plans_page.dart        # 计划管理
│   │   │   └── step_stepper.dart      # 步骤 Stepper
│   │   ├── cron/
│   │   │   ├── cron_page.dart         # 定时任务
│   │   │   └── cron_form.dart         # 添加任务表单
│   │   ├── agents/
│   │   │   └── agents_page.dart       # Agent 管理
│   │   ├── channels/
│   │   │   └── channels_page.dart     # 频道状态
│   │   ├── settings/
│   │   │   ├── settings_page.dart     # 设置
│   │   │   └── theme_picker.dart      # 主题色选择
│   │   ├── backup/
│   │   │   └── backup_page.dart       # 备份管理
│   │   └── system/
│   │       └── system_page.dart       # 系统监控
│   └── widgets/
│       ├── message_bubble.dart        # 消息气泡
│       ├── tool_call_card.dart        # 工具调用卡片
│       ├── plan_progress.dart         # 计划进度指示器
│       ├── model_selector.dart        # 模型选择下拉
│       ├── responsive_shell.dart      # 自适应布局壳
│       └── code_block.dart            # 代码块（高亮 + 复制）
├── pubspec.yaml
├── test/
│   ├── core/
│   └── features/
├── assets/
│   ├── fonts/
│   └── images/
├── android/
├── ios/
├── macos/
├── windows/
├── linux/
└── web/
```

### 3.2 视觉设计目标

#### Material 3 Design System

- 使用 `ThemeData` + `ColorScheme.fromSeed()` 自动生成完整配色
- Dynamic Color：Android 12+ 跟随壁纸取色
- 支持浅色 / 深色 / 跟随系统三种模式

#### 字体

| 用途 | 字体 |
|------|------|
| 正文 | Inter (Latin) + Noto Sans SC (CJK) |
| 代码 | JetBrains Mono |
| 加载 | Google Fonts 动态加载 |

#### 动画

| 动画 | 场景 |
|------|------|
| Hero 转场 | 会话列表 → 聊天页面 |
| Stagger 动画 | 列表项依次出现 |
| 打字机效果 | LLM 回复逐字符显示 |
| Shimmer 骨架屏 | 加载中占位 |
| 淡入淡出 | 页面切换 |
| 弹性 | 发送按钮、通知提示 |

#### 响应式布局

| 断点 | 布局 |
|------|------|
| Desktop (>1200px) | 三栏：NavigationRail + SessionList + Content |
| Tablet (600-1200px) | 可折叠 Drawer + Content |
| Mobile (<600px) | 底部 NavigationBar + 全屏 Content + 滑动 Drawer |

### 3.3 聊天体验增强

| 功能 | 技术方案 |
|------|----------|
| Markdown 渲染 | `flutter_markdown` + `highlight.dart` 代码高亮 |
| LaTeX 公式 | `flutter_math_fork` |
| 消息气泡 | 圆角卡片 + 头像 + 时间戳 + 对齐 |
| 工具调用卡片 | `ExpansionTile` 展开/折叠，显示工具名、参数、结果 |
| 流式打字 | 监听 `chat.message_update` 事件，逐 token 更新 `Text` widget |
| 图片预览 | `InteractiveViewer` 手势缩放 + `Hero` 放大 |
| 语音消息 | 长按录音 + 波形 `CustomPainter` + 播放控制 |
| 文件附件 | `file_picker` + 文件类型图标 + 内联预览 |

### 3.4 平台特性

| 平台 | 特性 |
|------|------|
| iOS / Android | FCM 推送通知、Share Extension、Siri Shortcuts / App Actions |
| macOS | 系统托盘 (`tray_manager`)、全局快捷键、多窗口 |
| Windows | 系统托盘、Jump List、窗口管理 |
| Linux | 系统托盘 (`ayatana_appindicator`)、桌面通知 |
| Web | PWA manifest、Service Worker 离线缓存、URL 路由 |

### 3.5 状态管理

使用 **Riverpod** 管理全局状态：

```
GatewayProvider (连接状态, WebSocket 实例)
    ├── ChatProvider (当前消息列表, 流式状态)
    ├── SessionProvider (会话列表, 当前选中)
    ├── ConfigProvider (配置数据)
    ├── PlanProvider (计划列表)
    ├── CronProvider (定时任务)
    └── SystemProvider (系统信息)
```

特性：
- 离线缓存：使用 `shared_preferences` / `hive` 本地存储
- 乐观更新：UI 先行更新，失败时回滚
- 自动刷新：Gateway 事件触发 Provider 更新

---

## 4. 实施路线

### Phase 1 — Flet 重构

| 阶段 | 范围 | 涉及文件 | 预估工作量 |
|------|------|----------|-----------|
| P1.1 | Gateway WebSocket Client | 新建 `gateway_client.py` | 2-3 天 |
| P1.2 | Chat 页面重构（流式 + 中断 + 编辑） | 修改 `app.py` (ChatView) | 3-4 天 |
| P1.3 | 新增 Plan / Cron / Backup / MCP / System 页面 | 新建 5 个面板文件 | 3-4 天 |
| P1.4 | Session 管理增强 | 修改 `app.py` (SessionSidebar) | 1-2 天 |
| P1.5 | Settings 页面增强 | 修改 `app.py` (SettingsView) | 1-2 天 |
| P1.6 | 主题 / 布局 / 响应式 | 修改 `theme.py`、`app.py` | 2-3 天 |
| P1.7 | 工具接入（文件、浏览器、语音） | 修改多个文件 | 2-3 天 |

**Phase 1 总计**：约 14-21 天

### Phase 2 — Flutter 原生

| 阶段 | 范围 | 涉及文件 | 预估工作量 |
|------|------|----------|-----------|
| P2.1 | Flutter 项目搭建 + Gateway Client | 新建 `flutter_app/` | 3-4 天 |
| P2.2 | 核心页面（Chat + Session + Settings） | features/chat, sessions, settings | 5-7 天 |
| P2.3 | 扩展页面（Plan / Cron / Backup / System） | features/plans, cron, backup, system | 3-4 天 |
| P2.4 | 视觉美化 + 动画 + 响应式 | widgets/, theme/ | 3-5 天 |
| P2.5 | 平台特性 + 发布构建 | 各平台目录 + CI | 3-4 天 |

**Phase 2 总计**：约 17-24 天

### 里程碑

| 里程碑 | 标志 | 预计时间 |
|--------|------|----------|
| M1 | Flet UI 通过 Gateway WebSocket 完成聊天流式对话 | P1.1 + P1.2 完成 |
| M2 | Flet UI 所有新增功能页面可用 | P1.3 完成 |
| M3 | Flet UI 全功能版本发布 | Phase 1 完成 |
| M4 | Flutter App 核心聊天功能可用 | P2.1 + P2.2 完成 |
| M5 | Flutter App 全功能 + 多平台发布 | Phase 2 完成 |

---

## 5. 技术选型

### Phase 1 (Flet)

| 类别 | 技术 |
|------|------|
| UI 框架 | Flet (Python) |
| WebSocket | `websockets` (Python, 已有依赖) |
| Markdown | `ft.Markdown` (Flet 内置) |
| 主题 | `ft.Theme` + 自定义 `AppTheme` |
| i18n | 自建 `I18n` 类 (已有) |
| TTS | edge-tts (已有) |
| 状态管理 | Python async + callback 模式 |

### Phase 2 (Flutter)

| 类别 | 技术 |
|------|------|
| UI 框架 | Flutter 3.x |
| 设计语言 | Material 3 |
| 状态管理 | Riverpod 2.x |
| WebSocket | `web_socket_channel` |
| Markdown | `flutter_markdown` |
| 代码高亮 | `highlight` |
| LaTeX | `flutter_math_fork` |
| HTTP | `dio` |
| 路由 | `go_router` |
| 本地存储 | `hive` / `shared_preferences` |
| 推送 | `firebase_messaging` |
| 字体 | `google_fonts` |
| 文件选择 | `file_picker` |
| 图片查看 | `photo_view` |
| 系统托盘 | `tray_manager` (macOS/Windows/Linux) |

---

## 附录：Gateway RPC 方法清单（UI 需要接入）

| 方法 | 用途 |
|------|------|
| `connect` | 握手认证 |
| `health` | 健康检查 |
| `status` | 网关状态 |
| `chat.send` | 发送消息并流式接收回复 |
| `chat.abort` | 中断当前生成 |
| `chat.history` | 获取会话历史 |
| `chat.edit` | 编辑消息重新生成 |
| `chat.resend` | 重新生成回复 |
| `sessions.list` | 会话列表 |
| `sessions.preview` | 会话消息预览 |
| `sessions.delete` | 删除会话 |
| `sessions.reset` | 重置会话 |
| `config.get` | 获取配置 |
| `config.set` | 设置配置 |
| `config.patch` | 部分更新配置 |
| `agents.list` | Agent 列表 |
| `agents.add` | 添加 Agent |
| `agents.remove` | 移除 Agent |
| `models.list` | 模型列表 |
| `models.providers` | 提供商列表 |
| `channels.list` | 频道列表 |
| `channels.status` | 频道状态 |
| `tools.catalog` | 工具目录（含 schema） |
| `tools.list` | 工具名列表 |
| `cron.list` | 定时任务列表 |
| `cron.add` | 添加定时任务 |
| `cron.remove` | 移除定时任务 |
| `cron.history` | 执行历史 |
| `plan.list` | 计划列表 |
| `plan.get` | 计划详情 |
| `plan.resume` | 恢复计划 |
| `plan.delete` | 删除计划 |
| `backup.export` | 导出备份 |
| `backup.status` | 备份列表 |
| `system.info` | 系统信息 |
| `doctor.run` | 诊断检查 |
| `usage.get` | 用量统计 |
| `logs.tail` | 日志查看 |
| `browser.*` | 浏览器控制 (10+ 子方法) |
| `tts.speak` | 文字转语音 |
| `tts.voices` | 语音列表 |
