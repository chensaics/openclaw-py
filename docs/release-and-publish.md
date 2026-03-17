# 发布流程：提交、打 Tag、GitHub Release、PyPI

本文档说明从代码提交到打 tag、创建 GitHub Release、以及发布 PyPI 包的操作步骤与命令。适用于维护者每次发版时按顺序执行。

---

## 重要说明

### PyPI 包名与链接

- **本项目的 PyPI 包名是 `openclaw-py`**（在 `pyproject.toml` 的 `name = "openclaw-py"`）。
- 正确链接：**https://pypi.org/project/openclaw-py/**  
- 若访问的是 https://pypi.org/project/pyclaw/ ，那是**另一个项目**，不是本仓库的包。本仓库的 CLI 入口叫 `pyclaw`，但发布到 PyPI 的包名是 `openclaw-py`。

### GitHub Release 与 Tag 的关系

- **GitHub Release 由“推送到远程的 tag”自动触发**，由 `.github/workflows/release.yml` 执行。
- 若只在本机打了 tag 但未 `git push origin <tag>`，则不会触发 Release 和 PyPI 发布。
- 若之前只推送过 `v0.1.2`，则 GitHub 的 Releases 页面只会看到 v0.1.2；tag 为 `v0.1.6` 时，需要**推送该 tag** 才会生成 v0.1.6 的 Release。
- **版本号必须一致**：`pyproject.toml` 里的 `version` 应与要打的 tag 去掉前缀 `v` 后一致（例如 tag `v0.1.7` 对应 `version = "0.1.7"`）。

---

## 一、发布前检查

1. **确认当前分支**（一般为 `master` 或 `main`）：
   ```bash
   git status
   git branch
   ```

2. **确认版本号**：编辑 `pyproject.toml`，将 `version` 改为本次要发布的版本（如 `0.1.7`）：
   ```bash
   # 编辑 pyproject.toml 中 [project] 下的 version = "0.1.7"
   ```

3. **本地跑通检查与测试**（与 CI 一致）：
   ```bash
   ruff format --check src tests && ruff check src tests
   mypy src/pyclaw
   pytest tests/
   python -m build   # 可选：确认能成功打 sdist + wheel
   ```

---

## 二、提交并推送到 GitHub

1. **提交版本号变更**（若有其他改动一并提交）：
   ```bash
   git add pyproject.toml   # 及其他修改的文件
   git commit -m "chore: bump version to 0.1.7"
   ```

2. **推送到远程**：
   ```bash
   git push origin master
   ```
   （若默认分支是 `main`，则改为 `git push origin main`。）

---

## 三、打 Tag 并推送（触发 Release 与 PyPI）

1. **创建带注释的 tag**（推荐，便于在 Releases 里看到说明）：
   ```bash
   git tag -a v0.1.7 -m "Release v0.1.7"
   ```

2. **推送该 tag 到远程**（推送后会自动触发 `.github/workflows/release.yml`）：
   ```bash
   git push origin v0.1.7
   ```

3. **若之前误打了同版本 tag 需要删除**（慎用）：
   ```bash
   git tag -d v0.1.7                    # 仅删本地
   git push origin :refs/tags/v0.1.7     # 删远程 tag（GitHub 上已生成的 Release 需在网页手动删）
   ```

---

## 四、自动流程说明（push tag 之后）

推送 `v*` tag 后，GitHub Actions 会依次执行：

| 步骤 | 说明 |
|------|------|
| **preflight** | 安装依赖、lint（ruff）、mypy、pytest、`python -m build`，并上传 `dist/` 为 artifact。 |
| **release-notes** | 用 `scripts/generate-release-notes.sh` 生成 Release 说明，并创建 **GitHub Release**，附带 `dist/*` 中的 sdist 与 wheel。 |
| **publish-testpypi** | 将包发布到 TestPyPI（需在仓库中配置 `testpypi` environment，可选）。 |
| **publish-pypi** | 将包发布到 **PyPI**（需在仓库中配置 **PyPI Trusted Publisher** 和 `pypi` environment）。 |
| **publish-docker** | 构建并推送 Docker 镜像到 Docker Hub 与 GHCR（需配置 `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN`）。 |

- 若 **PyPI 没有出现新版本**：检查 Actions 里 `publish-pypi` 是否失败；若使用 Trusted Publisher，需在 [PyPI 账户的 Publishing 设置](https://pypi.org/manage/account/publishing/) 中添加对应 GitHub 仓库与 workflow。
- 若 **GitHub Release 没有出现**：检查是否真的执行了 `git push origin v0.1.7`，以及 Actions 中 `release-notes` 是否成功。

---

## 五、PyPI 未看到包时的排查

1. **确认链接**：应打开 **https://pypi.org/project/openclaw-py/** ，不是 `pyclaw`。
2. **确认 Trusted Publisher**：在 [PyPI Publishing](https://pypi.org/manage/account/publishing/) 中为该仓库配置 Trusted Publisher，并确保 workflow 名为 `release.yml`、job 名为 `publish-pypi`，且仓库 environment 使用 `pypi`。
3. **查看 Actions**：在 GitHub 仓库的 Actions 里打开由 tag 触发的 “Release” workflow，查看 `publish-pypi` 的日志是否报错（如 403、包名/版本已存在等）。

---

## 六、常用命令速查

```bash
# 1. 改版本号后提交
vim pyproject.toml   # version = "0.1.7"
git add pyproject.toml && git commit -m "chore: bump version to 0.1.7"
git push origin master

# 2. 打 tag 并推送（触发 Release + PyPI）
git tag -a v0.1.7 -m "Release v0.1.7"
git push origin v0.1.7

# 3. 查看已有 tag
git tag -l

# 4. 本地生成 Release 说明（不发布）
./scripts/generate-release-notes.sh
# 或自上次 tag 到当前：./scripts/generate-release-notes.sh
# 或两 tag 之间：./scripts/generate-release-notes.sh v0.1.6 v0.1.7
```

---

## 七、参考

- [PyPI: Publishing package distribution releases using GitHub Actions](https://docs.pypi.org/trusted-publishers/using-a-publisher/)
- 本仓库 Release 工作流：`.github/workflows/release.yml`
- 发布说明脚本：`scripts/generate-release-notes.sh`
