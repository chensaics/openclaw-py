# 本地与 CI 校验一致说明

为避免「本地通过、远端 CI 失败」，本仓库提供与 GitHub Actions CI **完全一致**的本地校验方式。

## 为何会本地过、远端挂？

常见原因：

1. **Python 版本不同**：CI 在 3.10、3.11、3.12、3.13、3.14 上都会跑测试，本地可能只用了一个版本（如 3.12），在 3.10 上才会暴露的语法或行为差异只在远端出现。
2. **校验范围不同**：本地只跑了 `pytest tests/ -q` 或部分用例，CI 跑的是 `pytest --cov=pyclaw --cov-report=... tests/`，覆盖的代码路径或失败条件不一致。
3. **环境差异**：CI 每次都是干净安装 `pip install -e ".[dev]"`，本地可能多了/少了依赖或改了环境变量。

## 推荐：推送前跑与 CI 相同的校验

### 单 Python 版本（与单个 CI job 一致）

```bash
make ci
```

或直接：

```bash
./scripts/ci-local.sh
```

会依次执行与 [.github/workflows/ci.yml](https://github.com/chensaics/openclaw-py/blob/master/.github/workflows/ci.yml) 中 **test** job 相同的步骤：

1. `ruff format --check src tests`
2. `ruff check src tests`
3. `mypy src/pyclaw`
4. `pytest --cov=pyclaw --cov-report=term-missing --cov-report=xml tests/`

使用指定 Python（例如 3.10）：

```bash
PYTHON=python3.10 ./scripts/ci-local.sh
```

如需先安装依赖再跑（例如新 clone 后）：

```bash
./scripts/ci-local.sh --install
```

### 多 Python 版本（与 CI matrix 一致）

CI 会在 3.10～3.14 多个版本上跑。本地若已安装多个 Python，可一次性在所有已安装版本上跑相同校验：

```bash
make ci-matrix
```

或：

```bash
./scripts/run-ci-matrix.sh
```

脚本会依次用 `python3.10`、`python3.11`、…、`python3.14` 执行与 CI 相同的步骤，未安装的版本会跳过。适合在 push 前发现「只在某版本失败」的问题。

## Pre-push 钩子

安装 githooks 后，`git push` 前会自动跑与 CI 一致的 pytest（含 `--cov=pyclaw`）：

```bash
cp scripts/githooks/pre-push .git/hooks/pre-push
chmod +x .git/hooks/pre-push
```

这样每次 push 前都会用与 CI 相同的测试命令，减少因「本地没跑全」导致的远端失败。

## 对照表

| 步骤           | CI (ci.yml)                | 本地 `make ci` / `ci-local.sh` |
|----------------|----------------------------|---------------------------------|
| Lint           | ruff format + ruff check   | 同左                             |
| Type check     | mypy src/pyclaw            | 同左                             |
| Tests          | pytest --cov=pyclaw ...    | 同左                             |
| Python 版本    | 3.10, 3.11, 3.12, 3.13, 3.14 | 当前默认；多版本用 `make ci-matrix` |

## 小结

- **日常推送前**：执行 `make ci`，或安装 pre-push 钩子，保证与 CI 的 test job 一致。
- **发 PR 前或改过兼容性相关代码**：执行 `make ci-matrix`，在多个 Python 版本上跑一遍，再推送。
