# CoPaw 对比与集成计划

> 对比日期：2026-03-02
> CoPaw 版本：v0.0.3 ([agentscope-ai/CoPaw](https://github.com/agentscope-ai/CoPaw))
> OpenClaw-Py 版本：v0.1.0 (Phase 0-67 已完成)

---

## 一、两个项目的定位对比

| 维度 | CoPaw | OpenClaw-Py |
|------|-------|-------------|
| **定位** | 个人 AI 助手 workstation | 多通道 AI Gateway + 助手 |
| **架构** | FastAPI HTTP REST + AgentScope Runtime | FastAPI + WebSocket v3 RPC 双向协议 |
| **Agent 框架** | AgentScope `ReActAgent` (外部依赖) | 自研 Agent loop + embedded runner |
| **语言** | Python 3.10+ | Python 3.12+ |
| **通道数** | 6 内置 (DingTalk, Feishu, QQ, Discord, iMessage, Console) | 25 内置 (Telegram, Discord, Slack, WhatsApp, Signal 等) |
| **UI** | React Web Console (独立前端) | Flet 跨平台桌面/移动/Web |
| **本地模型** | llama.cpp + MLX + Ollama (3 后端) | Ollama + LM Studio (2 后端) |
| **记忆** | ReMe-AI 框架 + LLM 自动压缩 | SQLite FTS5 + LanceDB 向量 + QMD |
| **技能** | 目录 SKILL.md 自动加载 + 内置 10 个 | SKILL.md + ClawHub 市场 + 20+ 内置工具 |
| **定时任务** | APScheduler + Heartbeat (HEARTBEAT.md) | APScheduler + Heartbeat + Webhook 触发 |
| **MCP** | 支持 (manager + watcher 热重载) | 支持 (stdio + HTTP 双传输) |
| **安装** | one-line curl\|sh + pip + Docker | pip + pipx + brew + Docker |
| **项目体量** | ~65 commits, ~4.5k stars | ~400 .py, ~57k LOC, Phase 61 |

---

## 二、CoPaw 的差异化能力（OpenClaw-Py 缺失）

### 2.1 本地模型运行时（P1 高价值）

CoPaw 提供完整的本地模型管理子系统：

| 能力 | CoPaw 实现 | OpenClaw-Py 状态 |
|------|-----------|-----------------|
| **llama.cpp 推理** | `local_models/backends/` + `llama-cpp-python` | ❌ 缺失 |
| **MLX 推理** (Apple Silicon) | `local_models/backends/` + `mlx-lm` | ❌ 缺失 |
| **Ollama 管理** | `providers/ollama_manager.py` (pull/list/delete) | ✅ 已有 `ollama_enhanced.py`，但无模型管理 CLI |
| **模型下载 CLI** | `copaw models download Repo/Model-GGUF` | ❌ 缺失 |
| **HuggingFace / ModelScope 下载** | 双源支持，自动选 Q4_K_M 量化 | ❌ 缺失 |
| **模型 manifest 管理** | JSON manifest + 本地路径追踪 | ❌ 缺失 |

**关键文件**：
- `src/copaw/local_models/manager.py` — 下载/注册/删除
- `src/copaw/local_models/chat_model.py` — 本地推理封装
- `src/copaw/local_models/backends/` — llama.cpp / MLX 后端
- `src/copaw/local_models/tag_parser.py` — 标签解析用于流式输出

### 2.2 桌面截图工具（P2）

| 能力 | CoPaw | OpenClaw-Py |
|------|-------|-------------|
| **OS 级全屏截图** | `mss` 库跨平台 | ❌ 缺失（仅浏览器截图） |
| **macOS 窗口截图** | `screencapture -w` | ❌ 缺失 |
| **Agent 工具注册** | `desktop_screenshot` | ❌ 缺失 |

**关键文件**：`src/copaw/agents/tools/desktop_screenshot.py`

### 2.3 文件发送工具（P2）

| 能力 | CoPaw | OpenClaw-Py |
|------|-------|-------------|
| **通用 send_file** | `send_file_to_user` 支持 image/audio/video/file | ❌ 无统一 send_file 工具 |
| **MIME 自动检测** | ✅ | 通道层有附件支持但无 Agent 工具 |
| **多模态 Block** | ImageBlock / AudioBlock / VideoBlock / FileBlock | 通道层原始附件传递 |

**关键文件**：`src/copaw/agents/tools/send_file.py`

### 2.4 Web Console UI（P3）

| 能力 | CoPaw | OpenClaw-Py |
|------|-------|-------------|
| **React Web 控制台** | 独立 `console/` 前端，嵌入 FastAPI 静态服务 | ❌ 缺失（有 Flet 桌面 UI，无 Web 控制台） |
| **浏览器内聊天** | Console chat + 流式输出 | Flet Web 模式（需 Flet server） |
| **配置面板** | Settings → Models / Channels / Skills / MCP | Flet Settings 面板 |
| **本地模型下载 UI** | Console 内下载管理 | ❌ 缺失 |

### 2.5 一键安装脚本（P2）

| 能力 | CoPaw | OpenClaw-Py |
|------|-------|-------------|
| **curl\|sh 安装器** | `install.sh` (macOS/Linux) + `install.ps1` (Windows) | ❌ 缺失 |
| **自动安装 Python** | ✅ 安装器自动管理 | ❌ 需用户预装 |
| **extras 参数** | `--extras ollama,llamacpp,mlx` | ❌ |
| **卸载** | `copaw uninstall [--purge]` | ❌ |

### 2.6 配置热重载增强（P3）

| 能力 | CoPaw | OpenClaw-Py |
|------|-------|-------------|
| **ConfigWatcher** | 文件变更 → 自动重载通道 | ✅ 已有配置热重载 |
| **MCP 热重载** | `MCPConfigWatcher` 独立监视 + 自动重连 | ❌ MCP 客户端启动后固定 |

### 2.7 Heartbeat 增强（P3）

| 能力 | CoPaw | OpenClaw-Py |
|------|-------|-------------|
| **HEARTBEAT.md 文件驱动** | 读取工作目录 HEARTBEAT.md 作为定时查询 | ❌ 心跳仅触发简单 wake-up |
| **活跃时段** | `active_hours` (start/end) | ❌ |
| **目标分发** | `target=last` 回发最近通道 | ❌ |
| **间隔语法** | `30m / 1h / 2h30m` 人类可读 | ✅ 已有 cron 表达式 |

### 2.8 Office 文件技能（P3）

| 技能 | CoPaw | OpenClaw-Py |
|------|-------|-------------|
| **PDF 读取** | `skills/pdf/` | ❌ 无内置 PDF 工具 |
| **DOCX 读取** | `skills/docx/` | ❌ |
| **XLSX 读取** | `skills/xlsx/` | ❌ |
| **PPTX 读取** | `skills/pptx/` | ❌ |
| **喜马拉雅** | `skills/himalaya/` | ❌ |
| **新闻摘要** | `skills/news/` | ❌ |

### 2.9 ReActAgent 钩子机制（对比项）

| 能力 | CoPaw | OpenClaw-Py |
|------|-------|-------------|
| **Bootstrap Hook** | `BootstrapHook` — 首次交互检查 BOOTSTRAP.md | ✅ 已有 boot-md 检查 |
| **Memory Compaction Hook** | `MemoryCompactionHook` — 上下文超限自动压缩 | ✅ 已有 compaction_policy |
| **pre_reasoning hook** | AgentScope 框架 API | ✅ 自研 hooks/registry |

---

## 三、OpenClaw-Py 的优势（CoPaw 缺失）

| 维度 | OpenClaw-Py | CoPaw |
|------|------------|-------|
| **通道数** | 25 个 | 6 个 |
| **WebSocket v3 协议** | 双向 RPC，事件推送，连接管理 | HTTP REST only |
| **OpenAI 兼容 API** | `/v1/chat/completions` + `/v1/models` + `/v1/responses` | ❌ |
| **Agent 多路由** | 7 级优先级 binding，多 Agent 分发 | 单 Agent |
| **Sub-agent 编排** | spawn / steer / kill | ❌ |
| **安全体系** | SSRF 防护 + Exec 审批 + Sandbox + 配置脱敏 | 基本 |
| **服务发现** | mDNS/Bonjour + Tailscale | ❌ |
| **设备配对** | challenge/response | ❌ |
| **嵌入提供商** | Voyage / Mistral / OpenAI / Gemini / local | 依赖 AgentScope |
| **TTS** | ElevenLabs + OpenAI + edge-tts | ❌ |
| **系统服务** | launchd / systemd / schtasks | ❌ |
| **测试** | 1848 测试，78 文件 | 基础 pytest |
| **CI/CD** | lint + typecheck + coverage + contract tests + release | 基础 CI |

---

## 四、集成计划（Phase 62-67）

### Phase 62（P1）：本地模型运行时

**目标**：支持 llama.cpp 和 MLX 本地推理，无需云 API。

**范围**：
1. 新建 `src/pyclaw/local_models/` 子模块
   - `manager.py` — 模型下载/注册/删除，HuggingFace + ModelScope 双源
   - `schema.py` — `LocalModelInfo`, `BackendType`, `DownloadSource`
   - `chat_model.py` — 统一本地推理接口，适配 Agent providers
   - `backends/llamacpp.py` — llama-cpp-python 封装
   - `backends/mlx.py` — mlx-lm 封装
2. 在 `pyproject.toml` 新增 optional deps：`llamacpp`, `mlx`
3. 新增 CLI 命令：`pyclaw models download / list / delete / select`
4. 在 Agent provider 注册表中增加 local model provider

**验收**：
- `pyclaw models download Qwen/Qwen3-4B-GGUF` 成功下载
- `pyclaw agent "Hello" --provider local` 使用本地模型回复
- llama.cpp 和 MLX 后端各有至少 1 个集成测试

**参考**：CoPaw `src/copaw/local_models/`

---

### Phase 63（P2）：桌面截图 + 文件发送工具

**目标**：为 Agent 增加 OS 级截图和通用文件发送能力。

**范围**：
1. 新建 `src/pyclaw/agents/tools/desktop_screenshot.py`
   - 基于 `mss` 库实现跨平台全屏截图
   - macOS 支持 `screencapture -w` 窗口截图
   - 注册为 Agent 工具 `desktop_screenshot(path?, capture_window?)`
2. 新建 `src/pyclaw/agents/tools/send_file.py`
   - MIME 自动检测
   - 图片/音频/视频/通用文件分类输出
   - 注册为 Agent 工具 `send_file(file_path)`
3. 在 `pyproject.toml` 新增 `mss>=9` 依赖
4. 在 tools registry 中注册新工具

**验收**：
- `desktop_screenshot` 在 Linux/macOS 上生成 PNG
- `send_file` 能向通道发送图片和文档

**参考**：CoPaw `src/copaw/agents/tools/desktop_screenshot.py`, `send_file.py`

---

### Phase 64（P2）：一键安装脚本

**目标**：降低安装门槛，提供 curl | sh 式安装体验。

**范围**：
1. 新建 `scripts/install.sh`
   - 检测 Python 版本 (>=3.12)，缺失时提示安装
   - 使用 pipx 隔离安装 pyclaw
   - 支持 `--extras ollama,llamacpp,mlx` 参数
   - 安装后执行 `pyclaw setup --wizard`
2. 新建 `scripts/install.ps1` (Windows PowerShell)
3. 在 CLI 增加 `pyclaw uninstall [--purge]` 命令
4. 更新 README.md 安装部分

**验收**：
- `curl -fsSL .../install.sh | bash` 在 Ubuntu/macOS 上成功安装
- `pyclaw uninstall --purge` 清理所有数据

**参考**：CoPaw `scripts/` 安装脚本

---

### Phase 65（P2）：Office 文件技能包

**目标**：Agent 能读取 PDF/DOCX/XLSX/PPTX。

**范围**：
1. 新增技能 `skills/pdf/SKILL.md` + 工具函数
   - 基于 `pypdf` 或 `pdfplumber` 提取文本和表格
2. 新增技能 `skills/docx/SKILL.md`
   - 基于 `python-docx` 提取段落和表格
3. 新增技能 `skills/xlsx/SKILL.md`
   - 基于 `openpyxl` 读取工作表
4. 新增技能 `skills/pptx/SKILL.md`
   - 基于 `python-pptx` 提取幻灯片文本
5. 在 `pyproject.toml` 新增 `office` optional extra

**验收**：
- Agent 能回答 "读取 report.pdf 的摘要"
- 每个技能有基础单测

**参考**：CoPaw `src/copaw/agents/skills/pdf/`, `docx/`, `xlsx/`, `pptx/`

---

### Phase 66（P3）：Heartbeat 增强

**目标**：支持 HEARTBEAT.md 驱动的定时 Agent 查询 + 回发通道。

**范围**：
1. 在 `src/pyclaw/infra/heartbeat.py` 增加：
   - 读取工作目录 `HEARTBEAT.md` 作为 Agent 查询内容
   - 支持 `active_hours` (start/end) 活跃时段
   - 支持 `target: last` 将回复分发到最近活跃通道
   - 人类可读间隔 (`30m`, `1h`, `2h30m`)
2. 在配置 schema 中增加 heartbeat 高级字段
3. 更新 CLI `pyclaw system heartbeat` 子命令

**验收**：
- 配置 `heartbeat.query: "HEARTBEAT.md"` + `heartbeat.every: "30m"` 后自动定时查询
- 回复自动发送到最近活跃的通道

**参考**：CoPaw `src/copaw/app/crons/heartbeat.py`

---

### Phase 67（P3）：MCP 热重载 + 文档更新

**目标**：MCP 配置变更后自动重连，不需重启 Gateway。

**范围**：
1. 新建 `src/pyclaw/mcp/watcher.py`
   - 监视 MCP 配置节变化
   - 差量断开/重连 MCP 客户端
2. 在 Gateway lifespan 中启动 MCP watcher
3. 更新文档：
   - `docs/api-reference.md` 增加本地模型、Office 技能 API
   - `docs/reference/PROGRESS.md` 更新 Phase 62-67
   - `docs/reference/20260302_todo.md` 新增项标记

**验收**：
- 修改 `pyclaw.json` 中 MCP 配置后，新工具自动出现在 Agent 工具池
- 文档与实现一致

**参考**：CoPaw `src/copaw/app/mcp/watcher.py`

---

## 五、不纳入集成的项

| 项 | 原因 |
|----|------|
| **AgentScope 依赖** | CoPaw 深度绑定 agentscope/agentscope-runtime，OpenClaw-Py 使用自研 Agent loop，引入会破坏架构 |
| **React Console** | OpenClaw-Py 已有 Flet UI，架构差异大，重写 Console 成本高于收益 |
| **ReMe-AI 记忆** | OpenClaw-Py 已有 SQLite FTS5 + LanceDB 完整记忆栈，替换无额外价值 |
| **Pydantic v1 schema** | CoPaw 使用 agentscope 的 Msg 类型系统，与 OpenClaw-Py 的 Pydantic v2 不兼容 |
| **DingTalk Stream 重写** | OpenClaw-Py 已有独立 DingTalk 通道实现 |
| **QQ 通道** | OpenClaw-Py 已有独立 QQ 通道实现 |
| **ModelScope 平台集成** | 面向中国区特定平台，可按需单独排期 |

---

## 六、执行优先级总结

| 优先级 | Phase | 内容 | 预估工期 | 价值 |
|--------|-------|------|---------|------|
| **P1** | Phase 62 | 本地模型运行时 (llama.cpp + MLX) | 2-3 天 | 离线运行、隐私保护、成本降低 |
| **P2** | Phase 63 | 桌面截图 + 文件发送 | 0.5 天 | Agent 工具完整度 |
| **P2** | Phase 64 | 一键安装脚本 | 1 天 | 降低安装门槛 |
| **P2** | Phase 65 | Office 文件技能包 | 1 天 | 知识处理能力 |
| **P3** | Phase 66 | Heartbeat 增强 | 0.5 天 | 主动推送场景 |
| **P3** | Phase 67 | MCP 热重载 + 文档 | 0.5 天 | 运维体验 |

**总预估**：~5.5-6.5 人天

---

## 七、与 upstream (openclaw/openclaw TS) 综合差距

Phase 62-67 完成后，OpenClaw-Py 将在以下维度超越 CoPaw：

- 通道数（25 vs 6）
- 双向 WS 协议（vs HTTP REST）
- 安全体系（SSRF/Sandbox/审批 vs 基本）
- 多 Agent 路由（vs 单 Agent）
- OpenAI 兼容 API
- 测试覆盖率

同时吸收 CoPaw 的核心差异化能力：
- 本地模型推理（llama.cpp + MLX）
- OS 级桌面截图
- 文件发送工具
- Office 文件读取
- Heartbeat 主动查询
- MCP 热重载

与 TS upstream 相比仍存在的固有差距（不影响核心可用性）：
- 原生 macOS/iOS/Android companion app（Swift/Kotlin，独立仓库）
- Canvas/A2UI 可视化工作区
- Voice Wake 唤醒词（依赖原生平台）
- 完整 Extension marketplace（40+ 扩展）
- Node 远程设备控制（camera/screen recording）

---

## 参考文档

- CoPaw 项目：[agentscope-ai/CoPaw](https://github.com/agentscope-ai/CoPaw)
- TS 原始项目：[openclaw/openclaw](https://github.com/openclaw/openclaw)
- 当前进度：[PROGRESS.md](PROGRESS.md)
- 待办清单：[20260302_todo.md](20260302_todo.md)
- Phase 54-58 计划：[openclaw-py-gap-update_82611c7a.plan.md](../../.cursor/plans/openclaw-py-gap-update_82611c7a.plan.md)
