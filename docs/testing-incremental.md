# 全量 / 增量测试

## 行为说明

| 模式 | 命令 | 说明 |
|------|------|------|
| **全量** | `pytest tests/`、`hatch run test-full` | 跑全部测试（与 CI 默认一致） |
| **增量** | `hatch run test-inc -- -q`、`scripts/pytest_scope.py` | 相对某一 git 基准，只跑「相关」目录/改动过的测试文件 |

增量规则（摘要）：

- 改动 **`pyproject.toml`** 或 **`tests/conftest.py`** → 始终全量。
- 改动 **`src/pyclaw/.../foo.py`** → 跑 **`tests/pyclaw/`** 下与路径最长匹配的子目录（例如 `agents/skills/loader.py` → `tests/pyclaw/agents/skills/`）。
- 改动 **`tests/pyclaw/.../test_*.py`** → 只跑这些测试文件。
- 改动 **`skills/`** 下文档/脚本 → 跑 **`tests/pyclaw/agents/skills/`**。
- 仅改文档、`.github` 等非上述路径 → 增量模式下视为「无相关变更」：默认仍全量；若设置 **`PYCLAW_INCREMENTAL_EMPTY=skip`** 则跳过 pytest。

## 本地命令

```bash
# 全量
pytest tests/
hatch run test-full
hatch run cov

# 增量（相对 origin/master；无该分支时先 fetch 或换基准）
hatch run test-inc -- -q
PYCLAW_TEST_BASE=origin/main hatch run test-inc

# 带 coverage 的增量
hatch run cov-inc -- -q

# 只看会跑哪些路径（不执行 pytest）
python scripts/pytest_scope.py targets --fallback-full
python scripts/pytest_scope.py run --mode incremental -- -q
```

## Pre-push

- 默认：**全量** `pytest tests/`。
- 增量：`export PYCLAW_PRE_PUSH_TEST_MODE=incremental`（可选 `PYCLAW_TEST_BASE=origin/main`）。

## CI（GitHub Actions）

- **push `master` / 未开变量**：始终**全量**测试（与原来一致）。
- 在仓库 **Settings → Secrets and variables → Actions → Variables** 中新增 **`PYCLAW_CI_INCREMENTAL`** = **`true`** 时：对 **Pull Request** 使用增量 + coverage；合并进主分支前仍建议至少有一次全量（例如在本地或 merge 前跑 `hatch run test-full`）。

增量会缩短 PR 检查时间，但无法保证跨包耦合问题一定能被跑到；生产仓库可只对「纯文档/单包」PR 打开，或配合定时全量 workflow。
