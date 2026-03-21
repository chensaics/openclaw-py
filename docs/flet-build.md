# Flet 打包：Windows / macOS / Linux / Android / iOS

本仓库的桌面与 Web UI 基于 [Flet](https://flet.dev)，使用 **Flutter SDK** 和 **flet build** 打包成各平台安装包。入口为根目录的 `flet_app.py`，配置在 `pyproject.toml` 的 `[tool.flet]`。

官方文档：[Publishing a Flet app](https://docs.flet.dev/publish/)（含 [Flutter SDK 要求](https://docs.flet.dev/publish/#flutter-sdk)）。

---

## 一、前置条件

### 1. Flutter SDK

打包任意平台都需要 Flutter。若系统 `PATH` 中尚无满足版本要求的 Flutter，首次执行 `flet build` 时会**自动下载并安装**到 `$HOME/flutter/{version}`。

查看当前 Flet 所需 Flutter 版本：

```bash
flet --version
# 或
uv run python -c "import flet.version; print(flet.version.flutter_version)"
```

也可自行安装 Flutter 并加入 PATH：[flutter.dev](https://flutter.dev)。

### 2. Python 环境与依赖

打包会用到当前环境的依赖，需安装**含 UI 的依赖**：

```bash
pip install -e ".[ui]"
# 或
uv pip install -e ".[ui]"
```

---

## 二、平台与运行环境

`flet build` 需在**对应操作系统**上运行（或使用该系统的 CI runner）。参考官方 [Platform matrix](https://docs.flet.dev/publish/#platform-matrix)：

| 在以下系统运行 | 可打包目标 |
|----------------|------------|
| **macOS**      | apk / aab（Android）、ipa / ios-simulator（iOS）、macos、linux、windows、web |
| **Windows**    | apk / aab、ipa（需 WSL）、macos、linux、windows、web |
| **Linux**      | apk / aab、ipa、macos、linux、web（*不含 windows*） |

- **Android**：apk（调试/分发）、aab（Google Play 上架）
- **iOS**：ipa（真机/TestFlight/App Store）、ios-simulator（模拟器）
- **桌面**：windows、macos、linux
- **Web**：web（静态站点，可部署到任意静态托管）

---

## 三、打包命令

在仓库**根目录**（含 `pyproject.toml` 和 `flet_app.py`）执行。

### 桌面

```bash
# Windows 安装包（.exe 等）
flet build windows

# macOS 应用（.app）
flet build macos

# Linux 安装包
flet build linux
```

### Android

```bash
# APK（可直接安装）
flet build apk

# AAB（用于 Google Play）
flet build aab
```

### iOS

```bash
# 真机 / TestFlight / App Store（.ipa）
flet build ipa

# 仅模拟器
flet build ios-simulator
```

### Web

```bash
# 输出到 build/web，可部署到任意静态托管
flet build web
```

### 常用选项

- `--output <dir>`：指定输出目录（默认 `<当前目录>/build/<目标平台>`）
- `--clear-cache`：清除 Flutter 模板缓存后重建
- `--verbose` / `-v`：详细日志

示例：

```bash
flet build windows --output dist/win
flet build web -v
```

---

## 四、配置说明（pyproject.toml）

当前与打包相关的配置示例：

```toml
[tool.flet]
module = "flet_app"        # 入口模块（flet_app.py 中的 main(page)）
project = "OpenClaw"
org = "ai.openclaw"        # 反向域名，用于 Bundle ID 等
product = "OpenClaw"       # 显示名称
description = "Multi-channel AI gateway"
company = "OpenClaw"       # Windows/macOS 关于对话框
copyright = "Copyright (C) OpenClaw"

[tool.flet.app]
path = "."                 # 应用根目录（相对当前目录）

# 关键：web(Pyodide) 不能带服务端依赖
[project]
dependencies = [
  "fastapi>=0.115; sys_platform != 'emscripten'",
  "uvicorn>=0.34; sys_platform != 'emscripten'",
  "websockets>=14; sys_platform != 'emscripten'",
]

# 按目标平台追加依赖（Flet 会 append）
[tool.flet.web]
dependencies = ["flet-web>=0.82.2"]

[tool.flet.linux]
dependencies = ["flet-desktop-light>=0.82.2", "uvloop>=0.21"]

[tool.flet.windows]
dependencies = ["flet-desktop-light>=0.82.2"]

[tool.flet.macos]
dependencies = ["flet-desktop-light>=0.82.2", "uvloop>=0.21"]
```

更多选项（图标、启动图、权限、版本号等）见 [Configuration options](https://docs.flet.dev/publish/#configuration-options)。

---

## 五、CI/CD 示例（GitHub Actions）

在 GitHub Actions 中可为多平台并行打包并上传制品，参考 [Flet 官方 CI/CD](https://docs.flet.dev/publish/#github-actions)。要点：

- **Desktop**：`ubuntu-latest` 可打 linux；`macos-latest` 打 macos；`windows-latest` 打 windows。
- **Android**：`flet build apk` / `flet build aab` 在 Ubuntu 或 Windows runner 上运行。
- **iOS**：`flet build ipa` / `flet build ios-simulator` 需在 **macOS** runner 上运行。
- 环境变量建议设置 `FLET_CLI_NO_RICH_OUTPUT=1`，便于看日志。
- Linux 桌面构建可能需安装系统依赖（GTK、GStreamer 等），见官方示例中的 “Install Linux dependencies” 步骤。

---

## 六、故障排查

### Flutter 自动安装失败（EOFError / 压缩包不完整）

若出现类似错误：

```text
Flutter SDK 3.41.x is required. It will be installed now. Proceed? ...
Installing Flutter 3.41.x...
EOFError: Compressed file ended before the end-of-stream marker was reached
```

说明 Flet 自动下载的 Flutter 压缩包**不完整或损坏**（多为网络、代理、CDN 导致）。解决方式：**改用手动安装 Flutter**，并加入 `PATH`，Flet 检测到有效 Flutter 后不会再自动下载。

1. **查看当前 Flet 要求的 Flutter 版本**：
   ```bash
   python -c "import flet.version; print(flet.version.flutter_version)"
   ```
2. **手动安装 Flutter**（任选一种）：
   - 官方：[Install Flutter](https://docs.flutter.dev/get-started/install)（按系统选择 Linux/macOS/Windows）。
   - Linux 示例（以 3.41.4 为例，版本号按上一步输出调整）：
     ```bash
     cd ~
     git clone https://github.com/flutter/flutter.git -b 3.41.4 --depth 1
     export PATH="$HOME/flutter/bin:$PATH"
     flutter doctor
     ```
   - 若使用稳定分支：`git clone ... -b stable --depth 1`，再 `flutter upgrade` 到所需版本。
3. **将 Flutter 固定到当前 shell 或 `~/.bashrc` / `~/.zshrc`**：
   ```bash
   export PATH="$HOME/flutter/bin:$PATH"
   ```
4. 再次执行 `flet build linux`（或对应平台），Flet 会使用系统 PATH 中的 Flutter，不再触发自动安装。

### main.py not found / 入口找不到

若报错 `main.py not found in the root of Flet app directory. Use --module-name option...`，说明 Flet 把入口当成了默认的 `main.py`。本仓库入口是 **`flet_app.py`**，应在 `pyproject.toml` 中配置 `[tool.flet.app] path = "."` 且 `[tool.flet] module = "flet_app"`，确保在**仓库根目录**执行 `flet build`。若仍报错，可显式指定入口：

```bash
flet build linux --module-name flet_app
```

### Flutter 未在 PATH 中

`flutter doctor` 提示 “The flutter binary is not on your path” 时，将 Flutter 的 `bin` 加入 PATH 后再打包：

```bash
export PATH="/home/cs/flutter/3.41.4/bin:$PATH"   # 版本号按实际路径
flet build linux
```

可写入 `~/.bashrc` 或 `~/.zshrc` 持久生效。

### 其他

- **web 构建遇到 `uvicorn ... ResolutionImpossible`**：避免在主依赖使用 `uvicorn[standard]`（会引入 `httptools` 等在 Pyodide 下不可用的依赖）。将主依赖改为 `uvicorn`，需要本地网关高性能运行时再安装 `uvicorn[standard]`（例如 `pip install -e ".[server_standard]"`）。
- **Flutter 版本不符**：用 `flet --version` 或 `flet.version.flutter_version` 查看所需版本；必要时安装/切换对应 Flutter 或使用 `--clear-cache` 重建。
- **依赖缺失**：确保已 `pip install -e ".[ui]"`，打包会使用当前环境的依赖。
- **Web 资源**：PWA 相关文件（如 `web/manifest.json`、`web/service-worker.js`）在 `flet build web` 时会按 Flet 约定包含；若缺资源可查 [Excluding files and directories](https://docs.flet.dev/publish/#excluding-files-and-directories) 与项目 `web/` 目录。

---

## 七、参考链接

- [Publishing a Flet app](https://docs.flet.dev/publish/)
- [Flutter SDK 要求](https://docs.flet.dev/publish/#flutter-sdk)
- [Platform matrix](https://docs.flet.dev/publish/#platform-matrix)
- [Configuration options](https://docs.flet.dev/publish/#configuration-options)
- [GitHub Actions 示例](https://docs.flet.dev/publish/#github-actions)
