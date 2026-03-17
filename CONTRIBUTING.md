# Contributing to OpenClaw-Py

感谢你对 OpenClaw-Py 的贡献兴趣！本文档介绍了如何参与项目开发。

## 开发环境

### 前置要求

- Python 3.10+
- Git

### 初始设置

```bash
git clone https://github.com/chensaics/openclaw-py.git
cd openclaw-py
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 运行测试

```bash
pytest tests/ -v
```

**与 CI 保持一致（推荐推送前执行）**：运行与 GitHub Actions 完全相同的 lint + typecheck + pytest（含 coverage）：

```bash
make ci
```

在多个 Python 版本上跑与 CI 一致的校验（需安装 python3.10～3.14）：

```bash
make ci-matrix
```

详见 [本地与 CI 校验一致说明](docs/ci-local.md)。

仅运行冒烟测试：

```bash
pytest tests/test_docker_smoke.py -v
```

### 代码检查

```bash
ruff check src/
ruff format --check src/
```

## 项目结构

```
src/pyclaw/
├── agents/        # AI Agent 运行时 (runner, tools, providers)
├── channels/      # 消息通道适配 (Telegram, Discord, Slack, ...)
├── cli/           # Typer CLI 命令
├── config/        # 配置管理 (JSON5, 迁移, 热重载)
├── gateway/       # FastAPI WebSocket 网关
├── infra/         # 基础设施 (MCP, 进程管理, 诊断)
├── media/         # 媒体处理 (下载, 缓存, 转码)
├── memory/        # 向量 + FTS5 记忆存储
├── plugins/       # 扩展系统 (entry_points)
├── social/        # Agent 社交网络
├── ui/            # Flet 桌面/移动 UI
└── web/           # OpenAI 兼容 API
```

## 贡献流程

### 1. 创建 Issue

在开始大型改动之前，请先创建一个 Issue 讨论方案。小修复和文档改进可以直接提 PR。

### 2. 分支命名

```
feat/描述      # 新功能
fix/描述       # Bug 修复
docs/描述      # 文档
refactor/描述  # 重构
test/描述      # 测试
```

### 3. 提交信息

使用 [Conventional Commits](https://www.conventionalcommits.org/) 风格：

```
feat: add Matrix channel support
fix: resolve heartbeat timeout on WhatsApp
docs: update channel onboarding guide
test: add e2e gateway tests
refactor: extract account helpers from channel plugins
```

### 4. Pull Request

- 确保所有测试通过
- 更新相关文档
- PR 描述中说明改动的动机和方案
- 如果有 Breaking Changes，在 PR 描述和 commit message 中注明

## 代码规范

### Python 风格

- 使用 `ruff` 进行 lint 和格式化
- 类型标注：所有公开 API 必须有完整的类型注解
- 使用 `from __future__ import annotations` 启用延迟注解
- 使用 `dataclass` 而不是普通 dict 来表示结构化数据
- 异步优先：IO 操作使用 `async/await`

### 导入顺序

```python
from __future__ import annotations

import stdlib_module
from stdlib import something

import third_party

from pyclaw.module import thing
```

### 日志

使用标准库 `logging`，不使用 `print`：

```python
import logging
logger = logging.getLogger(__name__)

logger.info("Channel %s started", channel_id)
logger.error("Connection failed: %s", exc)
```

### 错误处理

- 业务逻辑错误使用自定义异常
- 外部依赖用 `try/except` + 日志
- 可选依赖使用 `try/except ImportError` 模式

## 添加新通道

1. 在 `src/pyclaw/channels/<name>/` 下创建目录
2. 实现 `ChannelPlugin` 基类（`channel.py`）
3. 在 `channels/plugins/` 下添加：
   - `onboarding.py` 中的向导流程
   - `outbound_adapters.py` 中的输出配置
   - `status_issues.py` 中的健康检查
   - `actions.py` 中的动作能力
   - `normalize.py` 中的消息标准化规则
4. 在 `channels/manager.py` 中注册
5. 添加测试

## 添加新 Agent 工具

1. 在 `src/pyclaw/agents/tools/` 下创建工具文件
2. 继承 `AgentTool` 基类
3. 在 `tools/registry.py` 的 `create_default_tools()` 中注册
4. 如需要，在 `tools/tool-display.json` 中添加显示配置

## 添加新 Provider

1. 在 `src/pyclaw/agents/providers/` 下创建适配文件
2. 实现标准的 `chat_completion` / `chat_completion_stream` 接口
3. 在 `providers/registry.py` 中注册
4. 在 `agents/model_catalog.py` 中添加模型定义

## 可选依赖

部分功能依赖可选包，这些在运行时通过 `try/except ImportError` 处理：

| 功能 | 依赖包 |
|------|--------|
| 语音唤醒 | `sounddevice`, `vosk` |
| WhatsApp | `neonize` |
| Discord Voice | `discord.py[voice]`, `pynacl` |
| 浏览器自动化 | `playwright` |
| Flet UI | `flet` |

## 发布流程

### 版本号规范

遵循 [Semantic Versioning](https://semver.org/)：`MAJOR.MINOR.PATCH`

- **PATCH** (0.1.x)：Bug 修复、文档更新
- **MINOR** (0.x.0)：新功能、向后兼容的改动
- **MAJOR** (x.0.0)：破坏性 API 变更

### 发布步骤

```bash
# 1. 更新版本号
#    编辑 pyproject.toml 中的 version 字段

# 2. 更新 CHANGELOG.md
#    将 [Unreleased] 中的内容移到新版本标题下

# 3. 提交版本变更
git add pyproject.toml CHANGELOG.md
git commit -m "release: v0.2.0"

# 4. 打标签并推送（触发 CI 自动发布）
git tag v0.2.0
git push origin master --tags
```

### 自动化发布流水线

推送 `v*` 标签后，GitHub Actions 自动执行：

1. **Preflight** — lint + type check + test + build wheel
2. **TestPyPI** — 先发布到 TestPyPI 验证安装
3. **GitHub Release** — 生成 release notes 并上传构建产物
4. **PyPI** — 使用 Trusted Publisher 发布到正式 PyPI
5. **Docker** — 构建并推送多架构镜像到 Docker Hub 和 GHCR

### 本地构建验证

```bash
# 构建 wheel 和 sdist
pip install build
python -m build

# 检查构建产物
ls dist/
# pyclaw-0.1.0-py3-none-any.whl
# pyclaw-0.1.0.tar.gz

# 验证 wheel 内容
python -m zipfile -l dist/pyclaw-*.whl | head -20

# 本地安装测试
pip install dist/openclaw_py-*.whl
pyclaw --version
```

### 安装方式

```bash
# 最小安装（核心 + CLI + Gateway）
pip install openclaw-py

# 带 UI 客户端
pip install openclaw-py[ui]

# 带消息通道 SDK
pip install openclaw-py[channels]

# 全功能安装
pip install openclaw-py[all]

# Docker
docker pull ghcr.io/chensaics/openclaw-py:latest
```

### PyPI Trusted Publisher 配置

项目使用 PyPI Trusted Publisher（OIDC），无需 API token。在 PyPI 项目设置中配置：

- **Publisher**: GitHub Actions
- **Repository**: `chensaics/openclaw-py`
- **Workflow**: `release.yml`
- **Environment**: `pypi`

TestPyPI 同理，environment 设为 `testpypi`。

## 许可证

提交代码即表示你同意你的贡献按照项目的 [MIT License](LICENSE) 进行许可。
