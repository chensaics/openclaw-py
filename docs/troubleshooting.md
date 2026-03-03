# 故障排除

本文档列出常见问题及诊断方法。

---

## 诊断工具

pyclaw 提供三个核心诊断命令：

```bash
# 综合诊断 — 检查配置、依赖、连接
pyclaw doctor

# 运行状态 — Gateway、通道、Agent 状态
pyclaw status [--deep]

# 实时日志 — 查看 Gateway 日志输出
pyclaw logs [--follow]
```

## 常见问题

### Gateway 无法启动

**症状**: 运行 `pyclaw gateway` 后立即退出或报错。

**排查步骤**:

1. **检查端口占用**:
   ```bash
   # 默认端口 18789
   lsof -i :18789
   ```
   如果端口已被占用，修改配置或停止占用进程：
   ```bash
   pyclaw config set gateway.port 18790
   ```

2. **检查配置合法性**:
   ```bash
   pyclaw doctor
   ```
   配置校验失败时 Gateway 会拒绝启动。`pyclaw doctor` 会显示具体的字段错误。

3. **检查 Python 版本**:
   ```bash
   python --version  # 需要 3.12+
   ```

4. **查看日志**:
   ```bash
   pyclaw logs
   ```

### 连接被拒绝

**症状**: UI 或 CLI 无法连接到 Gateway，报 "Connection refused"。

**排查步骤**:

1. **确认 Gateway 正在运行**:
   ```bash
   pyclaw status
   ```

2. **检查绑定地址**: Gateway 默认绑定 `127.0.0.1`，仅接受本地连接。远程访问需修改：
   ```bash
   pyclaw config set gateway.bind "0.0.0.0"
   ```

3. **检查认证 Token**: 如果配置了 `gateway.auth.token`，确保客户端使用了正确的 Token：
   ```bash
   pyclaw config get gateway.auth.token
   ```

### 认证失败

**症状**: 连接 Gateway 后收到认证错误。

**排查步骤**:

1. **检查 Token 配置**:
   ```bash
   pyclaw config get gateway.auth
   ```

2. **检查环境变量**: 如果 Token 通过环境变量设置，确认变量存在：
   ```bash
   echo $PYCLAW_AUTH_TOKEN
   ```

3. **重置 Token**:
   ```bash
   pyclaw config set gateway.auth.token "new-token"
   ```

### 通道收不到消息

**症状**: 已配置 Telegram/Discord 等通道，但发送消息后无反应。

**排查步骤**:

1. **检查通道状态**:
   ```bash
   pyclaw channels status
   ```

2. **确认通道已启用**: 检查配置中 `enabled: true`：
   ```bash
   pyclaw config get channels.telegram
   ```

3. **检查 allowFrom**: 如果配置了 `allowFrom`，确保你的用户 ID 在列表中。

4. **群组消息**: 群组中默认需要 @mention 才会触发 Agent。检查 `groupPolicy` 和 mention 配置。

5. **查看通道日志**:
   ```bash
   pyclaw logs --follow
   ```
   观察是否有连接错误或认证错误。

### MCP 工具不出现

**症状**: 配置了 MCP 服务器，但 Agent 未使用对应的工具。

**排查步骤**:

1. **检查 MCP 状态**:
   ```bash
   pyclaw mcp status
   ```

2. **列出已发现的工具**:
   ```bash
   pyclaw mcp list-tools
   ```

3. **检查 MCP 服务器配置**:
   ```bash
   pyclaw config get tools.mcpServers
   ```
   确保 `command` / `args` 或 `url` 正确。

4. **stdio 模式**: 确保 MCP 命令可执行（如 `npx` 在 PATH 中）。

5. **HTTP 模式**: 确保 URL 可达、认证头正确。

### Agent 回复缓慢或超时

**症状**: Agent 回复延迟很长，或报超时错误。

**排查步骤**:

1. **检查 LLM 连接**: 确认 API Key 有效、Provider 服务正常：
   ```bash
   pyclaw status --deep
   ```

2. **检查网络**: 中国用户连接 OpenAI/Anthropic 可能需要代理。设置 `HTTP_PROXY` / `HTTPS_PROXY` 环境变量。

3. **切换模型**: 尝试更快的模型（如 `gpt-4o-mini` 或 `gemini-flash`）。

4. **检查工具调用**: Agent 可能在等待工具执行（如 exec 审批）。查看 UI 是否有待审批请求。

### 配置修改不生效

**症状**: 修改了 `pyclaw.json` 但行为未变化。

**排查步骤**:

1. **需要重启的设置**: `gateway.port`、`gateway.bind` 等网络设置需要重启 Gateway。

2. **配置文件路径**: 确认修改的是正确的配置文件：
   ```bash
   echo $PYCLAW_CONFIG_PATH  # 如果设置了环境变量
   # 默认: ~/.pyclaw/pyclaw.json
   ```

3. **JSON5 语法错误**: 语法错误会导致配置加载失败，检查 `pyclaw doctor` 输出。

4. **热重载延迟**: 热重载有短暂的 debounce 延迟，稍等几秒。

### 密钥安全警告

**症状**: `pyclaw doctor` 或 `pyclaw security audit` 报告明文密钥。

**处理方法**:

1. **使用环境变量**: 将 API Key 移到 `.env` 文件或环境变量中，配置中改为 `${VAR_NAME}` 引用。

2. **自动修复**:
   ```bash
   pyclaw secrets audit   # 扫描明文密钥
   pyclaw secrets apply   # 替换为引用
   ```

3. **安全审计**:
   ```bash
   pyclaw security audit --deep --fix
   ```

## 日志与状态目录

| 路径 | 内容 |
|------|------|
| `~/.pyclaw/pyclaw.json` | 主配置文件 |
| `~/.pyclaw/sessions/` | 会话记录 |
| `~/.pyclaw/auth-profiles.json` | API Key 与 OAuth 凭证 |
| `~/.pyclaw/logs/` | 运行日志（如启用文件日志） |
| `~/.pyclaw/memory/` | 记忆存储 |
| `~/.pyclaw/cron/` | 定时任务配置与执行日志 |

## 重置与恢复

```bash
# 清理旧会话
pyclaw sessions cleanup

# 导出备份
pyclaw backup export --output backup.zip

# 从备份恢复
pyclaw backup import backup.zip

# 完全重置（谨慎操作）
rm -rf ~/.pyclaw
pyclaw setup --wizard
```

## 获取帮助

如果以上方法未解决问题：

1. 运行 `pyclaw doctor` 并保存输出
2. 查看 `pyclaw logs` 中的错误信息
3. 在 [GitHub Issues](https://github.com/chensaics/openclaw-py/issues) 提交问题，附上诊断信息

---

*相关文档: [快速开始](quickstart.md) · [配置说明](configuration.md) · [概念总览](concepts.md)*
