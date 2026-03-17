# Git hooks（可版本控制的副本）

- **pre-push**：在每次 push 前（含分支与 **tag**）跑与 CI 一致的 pytest（`--cov=pyclaw`），避免「push tag 后 CI 才报错」。
- 安装：`cp scripts/githooks/pre-push .git/hooks/pre-push && chmod +x .git/hooks/pre-push`
- 临时跳过：`PYCLAW_SKIP_PRE_PUSH=1 git push ...`
