# P1 Secrets 审计报告模板

## 审计范围

- 配置文件（`pyclaw.json` / `openclaw.json`）
- 环境变量注入
- 日志输出与错误栈
- 外部通道与 provider 凭证

## 审计检查项

- 明文 key 是否出现在配置与仓库文件
- 运行日志是否出现凭证片段
- 错误信息是否包含 request header/body 敏感字段
- Secrets 引用是否统一使用环境变量或 secret store

## 风险分级

- Critical：可直接导致凭证泄露或远程接管
- High：高概率泄露或绕过保护
- Medium：局部暴露、可控但需修复
- Low：治理性改进项

## 修复跟踪

| 项目 | 等级 | 位置 | 修复 PR | 验证结果 |
|---|---|---|---|---|
