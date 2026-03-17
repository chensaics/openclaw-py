# 安装指南

本文档汇总 pyclaw 的所有安装方式、可选依赖和升级/卸载方法。

---

## 系统要求

- **Python**: 3.10 或更高版本
- **操作系统**: macOS、Linux、Windows（WSL2 推荐）
- **LLM API Key**: OpenAI / Anthropic / Google Gemini / Ollama 等任一即可

## 一键安装脚本

### macOS / Linux

```bash
curl -fsSL https://raw.githubusercontent.com/chensaics/openclaw-py/master/scripts/install.sh | bash
```

附带本地模型支持：

```bash
# llama.cpp 后端
curl -fsSL https://raw.githubusercontent.com/chensaics/openclaw-py/master/scripts/install.sh | bash -s -- --extras llamacpp

# MLX 后端（Apple Silicon）
curl -fsSL https://raw.githubusercontent.com/chensaics/openclaw-py/master/scripts/install.sh | bash -s -- --extras mlx
```

### Windows (PowerShell)

```powershell
irm https://raw.githubusercontent.com/chensaics/openclaw-py/master/scripts/install.ps1 | iex
```

## 通过包管理器安装

### pip

```bash
pip install openclaw-py
```

### pipx（推荐，隔离环境）

```bash
pipx install openclaw-py
```

### Homebrew (macOS)

```bash
brew install chensaics/tap/pyclaw
```

## 从源码安装

```bash
git clone https://github.com/chensaics/openclaw-py.git
cd openclaw-py

# 基础安装
pip install -e .

# 安装全部可选依赖
pip install -e ".[all]"

# 仅安装开发依赖
pip install -e ".[dev]"
```

## Docker

```bash
# 单次运行
docker run -it --rm \
  -e OPENAI_API_KEY="sk-..." \
  ghcr.io/chensaics/openclaw-py:latest \
  pyclaw agent "Hello"

# 启动 Gateway（后台）
docker run -d \
  -e ANTHROPIC_API_KEY="sk-ant-..." \
  -p 18789:18789 \
  -v ~/.pyclaw:/root/.pyclaw \
  ghcr.io/chensaics/openclaw-py:latest \
  pyclaw gateway
```

## 可选依赖（extras）

安装时通过 `pip install openclaw-py[extra1,extra2]` 选择需要的功能：

| Extra | 功能 | 包含的库 |
|-------|------|----------|
| `ui` | Flet 桌面 UI + 系统托盘 | flet, pystray |
| `matrix` | Matrix 通道 | matrix-nio |
| `whatsapp` | WhatsApp 通道 | neonize |
| `voice` | 语音 TTS | edge-tts |
| `llamacpp` | llama.cpp 本地模型 | huggingface_hub, llama-cpp-python |
| `mlx` | MLX 本地模型 (Apple Silicon) | huggingface_hub, mlx-lm |
| `office` | 办公文档处理 | pypdf, python-docx, openpyxl, python-pptx |
| `dev` | 测试与代码检查 | pytest, ruff, mypy |
| `all` | 以上全部（dev 除外） | ui + matrix + voice + whatsapp + llamacpp + mlx + office |

示例：

```bash
# 安装 UI 和语音支持
pip install openclaw-py[ui,voice]

# 安装全部
pip install openclaw-py[all]
```

## 安装后设置

```bash
# 交互式向导：配置 Provider、模型和 API Key
pyclaw setup --wizard

# 无交互设置（通过环境变量）
pyclaw setup --non-interactive
```

## 升级

```bash
# pip
pip install --upgrade openclaw-py

# pipx
pipx upgrade openclaw-py

# Homebrew
brew upgrade pyclaw
```

## 卸载

```bash
# 一键卸载（macOS / Linux）— 自动检测 pipx/uv/pip
curl -fsSL https://raw.githubusercontent.com/chensaics/openclaw-py/master/scripts/uninstall.sh | bash

# 卸载并清除所有数据和配置
curl -fsSL https://raw.githubusercontent.com/chensaics/openclaw-py/master/scripts/uninstall.sh | bash -s -- --purge

# Windows (PowerShell)
irm https://raw.githubusercontent.com/chensaics/openclaw-py/master/scripts/uninstall.ps1 | iex
# 带清除数据：$env:PYCLAW_PURGE="1"; irm ... | iex

# 或手动卸载
pip uninstall openclaw-py     # 如果用 pip 安装
pipx uninstall openclaw-py    # 如果用 pipx 安装
pyclaw uninstall --purge      # CLI 方式 + 清除数据
```

## 作为系统服务安装

将 pyclaw Gateway 安装为系统服务，开机自启：

```bash
# 安装服务
pyclaw service install

# 查看服务状态
pyclaw service status
```

支持 macOS (launchd)、Linux (systemd) 和 Windows (schtasks)。

## 验证安装

```bash
# 检查版本
pyclaw --version

# 运行诊断
pyclaw doctor

# 查看状态
pyclaw status
```

---

*相关文档: [快速开始](quickstart.md) · [配置说明](configuration.md)*
