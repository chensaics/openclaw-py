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

## 3. Phase 2 — Flet 高级增强 + Flutter 设计反哺

> **注意**: 原计划为独立 Flutter App 重写。经过 Phase 70-71 实施后，发现 Flet 底层就是 Flutter 渲染引擎，
> 维护两套 UI 代码意义不大。Phase 72 决定统一以 Flet UI 为客户端，将 Flutter App 的设计精华反哺到 Flet UI。
> Flutter App 代码保留在 `flutter_app/` 目录作为参考设计资料（见 `ARCHIVE_NOTICE.md`）。

### 3.1 设计反哺来源

`flutter_app/` 中以下设计已反哺到 Flet UI：

| Flutter 参考 | 反哺到 Flet | 状态 |
|-------------|------------|------|
| `core/theme/colors.dart` — 颜色 tokens | `theme.py` — `PRESET_SEED_COLORS`, `StatusColors`, `RoleColors`, `CodeBlockColors` | ✅ 已完成 |
| `core/theme/app_theme.dart` — Material 3 | `theme.py` — `card_border_radius`, `input_border_radius`, `surface_container_high` 等 | ✅ 已完成 |
| `widgets/shimmer_loading.dart` — Shimmer 骨架屏 | `shimmer.py` — `ShimmerContainer`, `shimmer_chat_skeleton()`, `shimmer_list_tile()` | ✅ 已完成 |
| `widgets/stagger_list.dart` — 列表入场动画 | `shimmer.py` — `stagger_fade_in()` | ✅ 已完成 |
| `core/theme/typography.dart` — 字体 tokens | `theme.py` — `Typography.line_height`, `code_line_height` | ✅ 已完成 |

### 3.2 Flet 构建支持

使用 `flet build` 命令从 Python 代码直接生成各平台原生包：

```bash
flet build web          # PWA Web 应用
flet build macos        # macOS .app
flet build windows      # Windows .exe
flet build linux        # Linux 包
flet build apk          # Android APK
flet build ipa          # iOS IPA (需 macOS + Xcode)
```

入口文件：`flet_app.py`（项目根目录），引用 `src/pyclaw/ui/app.py`。

### 3.3 视觉设计目标（通过 Flet 实现）

#### Material 3 Design System

- `ft.Theme(color_scheme_seed=...)` 自动生成完整 Material 3 配色
- `set_seed_color()` 支持预设名称（indigo/teal/rose/...）或自定义 hex
- 浅色 / 深色模式切换 (`toggle_theme()`)

#### 动画

| 动画 | Flet 实现 |
|------|----------|
| Shimmer 骨架屏 | `ShimmerContainer` + `animate_opacity` 脉冲循环 |
| Stagger 列表入场 | `stagger_fade_in()` — 逐项 `animate_opacity` + `animate_offset` |
| 消息淡入 | `ft.AnimatedOpacity` |
| 页面切换过渡 | `page.go()` + `ft.Animation` |

#### 响应式布局

| 断点 | 布局 |
|------|------|
| Desktop (>1200px) | 三栏：NavigationRail + SessionSidebar + Content |
| Tablet (600-1200px) | 可折叠 Drawer + Content |
| Mobile (<600px) | 底部 NavigationBar + 全屏 Content + 滑动 Drawer |

### 3.4 可选 — Flet 自定义控件

对于 Flet 内置控件无法满足的高级功能，可使用 [Flet Custom Controls](https://flet.dev/docs/guides/python/custom-controls) 用 Dart 编写并在 Python 中调用：

| 候选功能 | 参考实现 |
|---------|---------|
| LaTeX 公式渲染 | `flutter_app/lib/widgets/latex_text.dart` |
| 代码高亮 | `flutter_app/lib/widgets/code_block.dart` |
| 图片手势预览 | `flutter_app/lib/widgets/image_preview.dart` |

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

### Phase 2 — Flet 高级增强 + 设计反哺 (Phase 72)

| 阶段 | 范围 | 涉及文件 | 状态 |
|------|------|----------|------|
| P2.1 | Flutter App 参考设计 (Phase 70-71) | `flutter_app/` (已归档) | ✅ 已完成 |
| P2.2 | Material 3 配色方案反哺 | `theme.py` | ✅ 已完成 |
| P2.3 | Shimmer 骨架屏 + 列表动画反哺 | 新建 `shimmer.py` | ✅ 已完成 |
| P2.4 | ui_upgrade_plan.md 融合路线更新 | 本文档 | ✅ 已完成 |
| P2.5 | flet build 多平台验证 | `flet_app.py` | ✅ 已完成 |
| P2.6 | 可选：Flet Custom Controls (LaTeX 等) | 待定 | 📋 未来 |

### 里程碑

| 里程碑 | 标志 | 状态 |
|--------|------|------|
| M1 | Flet UI 通过 Gateway WebSocket 完成聊天流式对话 | ✅ Phase 69 |
| M2 | Flet UI 所有新增功能页面可用 | ✅ Phase 69 |
| M3 | Flet UI 全功能版本发布 | ✅ Phase 69 |
| M4 | Flutter App 参考设计完成 | ✅ Phase 70-71 (已归档) |
| M5 | Flet UI 融合 Flutter 设计精华 | ✅ Phase 72 |
| M6 | Flet build 多平台原生包验证 | ✅ Phase 72 |

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

### Phase 2 (Flet 高级增强)

| 类别 | 技术 |
|------|------|
| UI 框架 | Flet (Python)，底层 Flutter 渲染 |
| 构建工具 | `flet build` — 生成 Web/Desktop/Mobile 原生包 |
| Shimmer 动画 | `ft.Animation` + `animate_opacity` 脉冲循环 |
| 列表动画 | `ft.Animation` + `animate_offset` 交错淡入 |
| 主题系统 | `ft.Theme(color_scheme_seed=...)` + `PRESET_SEED_COLORS` |
| 角色配色 | `RoleColors` — user/assistant/system/tool 头像色 |
| 自定义控件 | Flet Custom Controls (Dart) — 用于 LaTeX/代码高亮等 |

### 已归档 — Flutter App 参考设计 (Phase 70-71)

> `flutter_app/` 作为 UI/UX 参考资料保留，不再独立维护。详见 `flutter_app/ARCHIVE_NOTICE.md`。

| 类别 | 技术 |
|------|------|
| UI 框架 | Flutter 3.x + Material 3 |
| 状态管理 | Riverpod 2.x |
| 路由 | `go_router` |
| 本地存储 | `hive` |
| 代码规模 | 46 Dart 文件，~4,980 LOC，49 单元测试 |

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
