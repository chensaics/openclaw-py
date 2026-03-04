# openclaw-py GitHub 自动化完善计划（参考 camel，0304）

> 日期：2026-03-04  
> 参考项目：`/mnt/g/chensai/claw_examples/camel`  
> 目标：在不破坏现有发布链路的前提下，补齐 `openclaw-py` 的 GitHub 工程自动化能力（安全、治理、质量、效率）

---

## 1. 调研范围（含隐藏文件）

本计划基于对两边仓库隐藏文件的对照梳理，重点查看了：

- `camel`：`.github/workflows/*`、`.github/ISSUE_TEMPLATE/*`、`.github/PULL_REQUEST_TEMPLATE.md`、`.pre-commit-config.yaml`
- `openclaw-py`：`.github/workflows/*`、`.github/dependabot.yml`、`.github/ISSUE_TEMPLATE/*`、`.github/pull_request_template.md`、`.github/labeler.yml`、`.pre-commit-config.yaml`

已确认当前项目具备基础 CI/Release/Docker/Labeler/Stale/Dependabot 能力，但在供应链安全与治理自动化方面仍有系统性缺口。

---

## 2. 对标结论（camel 可迁移能力）

`camel` 在以下方面可直接作为参考：

1. **供应链与代码安全**
   - `codeql.yml`（代码扫描）
   - `dependency-review.yml`（PR 依赖风险门禁）
   - `scorecard.yml`（OpenSSF 供应链评分）
2. **工作流安全基线**
   - 多个 workflow 统一接入 `step-security/harden-runner`
   - action 版本大量采用 commit SHA 固定（降低供应链漂移风险）
3. **流程治理自动化**
   - `pr-label-automation.yml`（PR 创建即贴标准标签）
   - 更严格的 PR/Issue 模板约束
4. **pre-commit 与 CI 对齐**
   - pre-commit 规则较完整（格式、拼写、泄漏检测等）
   - workflow 专门执行 pre-commit，作为独立质量门禁

---

## 3. 当前仓库基线与差距

## 3.1 已有能力（openclaw-py）

- `ci.yml`：lint/test/mypy/security（含 docs-only 跳过优化）
- `release.yml`：tag 触发发布（PyPI/TestPyPI/Docker/GitHub Release）
- `docker.yml`、`install-smoke.yml`：镜像与安装链路验证
- `labeler.yml` + `.github/labeler.yml`：路径标签与 PR 大小标签
- `stale.yml`：陈旧 issue/PR 清理
- `dependabot.yml`：pip/actions/docker 依赖更新

## 3.2 关键差距（优先补齐）

1. **缺少一等公民级安全扫描**
   - 无 CodeQL workflow
   - 无 Dependency Review（PR 引入风险依赖无法自动阻断）
2. **缺少供应链治理视图**
   - 无 Scorecard 自动分析与 SARIF 上报
3. **workflow 安全基线不统一**
   - 关键 workflow 未统一 hardened runner
   - action 版本多数为 tag，未系统性 pin 到 SHA
4. **质量门禁拆分不清晰**
   - pre-commit 仅本地配置，未作为独立 CI job
5. **治理自动化可增强**
   - PR 自动标签仅路径/体量，缺少“初始状态标签”（如 `needs-review`）
   - 模板已较完善，但可增加字段校验与自动检查

---

## 4. 分阶段实施路线（P0 / P1 / P2）

## 4.1 P0（1 周）：安全基线补齐，先“可见可拦截”

### 目标

- 建立最小可用的 GitHub 安全自动化闭环（检测 + 阻断）。

### 工作项

1. 新增 `/.github/workflows/codeql.yml`
   - 触发：`push`（`master`）、`pull_request`、`schedule`
   - 语言矩阵建议：`python` + `actions`（可按仓库实际再扩展）
2. 新增 `/.github/workflows/dependency-review.yml`
   - 触发：`pull_request`
   - 将结果纳入必需检查（分支保护）
3. 在现有关键 workflow 中统一最小权限与权限声明
   - 明确 `permissions`（最小化原则）
   - 将不必要的 `write` 改为 `read`
4. 在仓库设置层启用：
   - Code scanning alerts
   - Dependabot alerts + security updates

### 验收标准（DoD）

- PR 中引入高风险依赖可被 `dependency-review` 明确拦截。
- CodeQL 在默认分支可产出扫描结果并进入 Security 面板。
- 所有主干 workflow 具备显式 `permissions`。

---

## 4.2 P1（1-2 周）：供应链治理与 workflow 强化

### 目标

- 提升 GitHub Actions 供应链可审计性与执行安全性。

### 工作项

1. 新增 `/.github/workflows/scorecard.yml`
   - 周期性执行并上传 SARIF
2. 逐步给高价值 workflow 接入 hardened runner
   - 先级建议：`ci.yml`、`release.yml`、`docker.yml`
3. 统一 action 版本管理策略
   - 从“tag 优先”迁移为“关键 action pin SHA”
   - 结合 Dependabot 管理更新节奏
4. 增加 workflow lint（可选）
   - 新增 `actionlint` job，提前发现 YAML/权限配置问题

### 验收标准（DoD）

- Scorecard 在默认分支稳定运行，结果可追踪。
- 主 workflow 完成 hardened runner 覆盖。
- 新增/修改 workflow 必须通过 actionlint（若启用）。

---

## 4.3 P2（2-4 周）：流程治理自动化与贡献体验优化

### 目标

- 将“规范执行”从文档约束升级为自动校验。

### 工作项

1. 新增 `/.github/workflows/pr-label-automation.yml`
   - PR opened 自动打 `needs-review`（或团队约定标签）
2. 新增 `/.github/workflows/pr-template-check.yml`
   - 检查 PR 描述关键字段是否填写（Summary/Verification/Security Impact）
3. 新增 `/.github/workflows/pre-commit.yml`
   - CI 中独立执行 `pre-commit run --all-files`
4. 强化模板与治理联动
   - 对 `pull_request_template.md` 的 required 段落做机器校验
   - Issue 模板按 bug/feature 的 triage 标签自动化路由（可后续接入）

### 验收标准（DoD）

- 新建 PR 自动具备初始治理标签。
- PR 未填写关键模板项时给出失败检查或阻塞提示。
- pre-commit 检查结果在 CI 可见，且与本地行为一致。

---

## 5. 建议落地文件清单（目标态）

建议最终形成如下 GitHub 自动化文件结构：

- `/.github/workflows/codeql.yml`（新增）
- `/.github/workflows/dependency-review.yml`（新增）
- `/.github/workflows/scorecard.yml`（新增）
- `/.github/workflows/pr-label-automation.yml`（新增）
- `/.github/workflows/pre-commit.yml`（新增）
- `/.github/workflows/pr-template-check.yml`（新增，可选）
- `/.github/workflows/ci.yml`（增强：权限最小化 + hardened runner）
- `/.github/workflows/release.yml`（增强：权限最小化 + hardened runner）
- `/.github/workflows/docker.yml`（增强：权限最小化 + hardened runner）
- `/.github/dependabot.yml`（增强：分组/频率/目标分支策略）

---

## 6. 分支保护与仓库策略（与 workflow 配套）

在 GitHub Repo Settings 建议同步开启：

1. **Branch protection（`master`）**
   - Require pull request before merging
   - Require status checks to pass before merging（纳入 CI、CodeQL、Dependency Review）
   - Dismiss stale approvals when new commits are pushed
2. **Security**
   - Secret scanning（含 push protection）
   - Dependabot alerts/security updates
3. **Actions**
   - 仅允许可信 actions（GitHub + allowlist）
   - 默认 token 权限最小化（仓库级）

---

## 7. 风险与缓解

| 风险 | 影响 | 缓解策略 |
|------|------|----------|
| 一次性增加检查过多导致 PR 阻塞 | 研发效率下降 | 按 P0→P1→P2 分阶段启用，先告警后阻断 |
| CodeQL 首轮噪音较大 | 团队信任度下降 | 首周进行 baseline triage，建立忽略规则与负责人 |
| SHA pin 维护成本上升 | workflow 更新变慢 | Dependabot 专门管理 `github-actions` 依赖 |
| hardened runner 触发外联限制 | 部分任务失败 | 先 `audit` 模式观察，再按白名单收敛 |

---

## 8. 里程碑与负责人建议

| 里程碑 | 时间窗 | 交付物 | Owner 建议 |
|--------|--------|--------|------------|
| M1（P0） | 第 1 周 | `codeql` + `dependency-review` + 分支保护联动 | 平台/安全 |
| M2（P1） | 第 2-3 周 | `scorecard` + hardened runner + action 版本治理 | 平台/DevOps |
| M3（P2） | 第 4-6 周 | PR 模板检查 + pre-commit CI + 标签自动化 | 平台/维护者 |

---

## 9. 实施顺序（建议执行脚本级清单）

1. 先落地 P0 的 2 个 workflow（`codeql`、`dependency-review`）并观察 3-5 天。
2. 在不改变业务逻辑的前提下改造现有 workflow 权限声明。
3. 再引入 P1 的 scorecard/hardened runner，先 `audit` 后收敛。
4. 最后引入 P2 的流程治理自动化，避免早期“流程过重”。

---

## 10. 与现有文档关系

- 进度总览：[`PROGRESS.md`](./PROGRESS.md)
- 平台实施计划：[`platform_implement_plan_0304.md`](./platform_implement_plan_0304.md)
- 差距分析：[`gap-analysis.md`](./gap-analysis.md)
- 架构说明：[`../architecture.md`](../architecture.md)

本计划聚焦 **GitHub 工程自动化层**，与业务功能开发计划并行推进。

---

## 11. 实施记录（2026-03-04）

### 11.1 新增 workflow

- `/.github/workflows/codeql.yml`
- `/.github/workflows/dependency-review.yml`
- `/.github/workflows/scorecard.yml`
- `/.github/workflows/pre-commit.yml`
- `/.github/workflows/pr-label-automation.yml`
- `/.github/workflows/pr-template-check.yml`
- `/.github/workflows/actionlint.yml`

### 11.2 已增强 workflow

- `/.github/workflows/ci.yml`：新增 hardened runner；补充顶层权限声明；security job 增加 Python 环境初始化。
- `/.github/workflows/release.yml`：各 job 接入 hardened runner；发布相关 job 显式最小权限。
- `/.github/workflows/docker.yml`：接入 hardened runner。
- `/.github/workflows/install-smoke.yml`：接入 hardened runner；新增顶层只读权限。
- `/.github/workflows/labeler.yml`：两个 job 均接入 hardened runner。
- `/.github/workflows/stale.yml`：接入 hardened runner。

### 11.3 依赖自动化增强

- `/.github/dependabot.yml`：
  - 为 pip/actions/docker 三类更新增加固定周计划（day/time/timezone）。
  - 明确 `target-branch: master`。
  - 增加 `rebase-strategy: auto` 与统一 `automated` 标签。
  - Docker 更新增加分组与 PR 数量上限，降低噪音。

### 11.4 兼容性说明

1. 所有新增检查均未改动业务代码与打包脚本，仅作用于 GitHub 自动化层。
2. hardened runner 统一使用 `egress-policy: audit`，先观测不阻断，避免影响现有发布链路。
3. 仍保留原有 `ci/release/docker/install-smoke` 触发条件与核心步骤，属于增强而非替换。

---

## 12. Branch Protection 必需检查推荐（可直接配置）

> 建议在 `Settings -> Branches -> Branch protection rules -> master` 中配置。  
> 为避免首周阻塞，推荐先用“宽松集”，观察 3-7 天后切换“严格集”。

### 12.1 宽松集（推荐立即启用）

- `CI / test`
- `CI / typecheck`
- `Dependency Review / dependency-review`
- `Pre-commit / pre-commit`
- `PR Template Check / validate-pr-body`
- `Actionlint / lint-workflows`

说明：

1. 该集合覆盖质量、依赖风险、流程规范，且对当前发布链路影响最小。
2. `CI / changes` 建议不设为 required（用于范围判定，不是质量门禁）。
3. `CI / security` 可先观察稳定性后再并入 required。

### 12.2 严格集（稳定后一并启用）

- 宽松集全部项
- `CI / security`
- `CodeQL / Analyze (python)`
- `CodeQL / Analyze (actions)`

说明：

1. CodeQL 首轮可能有历史噪音，建议先完成一次 baseline triage 再开启 required。
2. 若出现误报，优先通过规则与流程收敛，不建议直接移除检查。

### 12.3 建议保持非阻断（观察型）

- `Scorecard Supply-Chain Security / Scorecard analysis`
- `Labeler / label`
- `Labeler / size`
- `Stale / stale`
- `PR Label Automation / add-needs-review-label`

原因：上述任务更偏治理与维护效率，不建议成为代码合并硬门禁。
