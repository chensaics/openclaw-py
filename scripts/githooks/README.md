# Git hooks（可版本控制的副本）

- **pre-push**：在分支 push 前跑全量 pytest；推送 tag 时跳过（由 release workflow 执行），避免重复。
- 安装：`cp scripts/githooks/pre-push .git/hooks/pre-push && chmod +x .git/hooks/pre-push`
