# M3 多平台发布 Gate v1（签名与权限核对）

> 适用里程碑：M3 发布工程化  
> 目标：将“可构建”升级为“可发布、可回滚、可审计”

## 0) 自动化入口（已实现）

- [x] 已提供命令：`pyclaw ops release-gate`
- [x] 支持检查：版本一致性、发布/回滚说明存在、产物命名规则、`SHA256SUMS` 归档、工作区状态
- [x] 支持输出：`reference/ops/M3_RELEASE_GATE_REPORT.json`

示例：

```bash
pyclaw ops release-gate \
  --artifacts-dir dist \
  --version 1.2.3 \
  --release-notes "..." \
  --rollback-notes "..." \
  --write-report reference/ops/M3_RELEASE_GATE_REPORT.json
```

## 1) 发布前置（阻塞项）

- [ ] 版本号一致（代码、产物、发布说明）。
- [ ] 关键测试通过（单元/契约/冒烟）。
- [ ] 关键 RPC 回归通过（chat/session/config/status/logs）。
- [ ] 风险变更项有回滚预案（含触发条件）。

## 2) 平台签名与权限核对

### Android

- [ ] keystore 可用，签名 alias 与 CI 配置一致。
- [ ] `AndroidManifest` 权限声明与功能一致（无多余高危权限）。
- [ ] 产物 `apk/aab` 均可安装并启动。

### iOS / macOS

- [ ] Provisioning Profile、证书、Bundle ID 一致。
- [ ] entitlements 与权限声明（麦克风、通知、网络）一致。
- [ ] 签名验证通过（本地与 CI）。

### Windows / Linux / Web

- [ ] 桌面端依赖完整，冷启动成功。
- [ ] Web 路由/base-url 配置正确，静态资源可加载。
- [ ] 各平台产物命名、版本与哈希归档完整。

## 3) 产物归档与审计

- [ ] 生成 `SHA256` 校验文件并归档。
- [ ] 产物命名遵循统一规则（平台-版本-构建号）。
- [ ] 发布说明包含：变更摘要、兼容性、回滚路径、已知问题。
- [ ] 本次发布 Gate 记录入库（可追溯到 commit/tag）。

## 4) 回滚手册（最小模板）

| 触发条件 | 回滚动作 | 负责人 | 预计恢复时间 |
|---|---|---|---|
| P0 功能不可用 | 回退至上一个稳定 tag | Release Owner | < 30 min |
| 签名/证书异常 | 切换备用签名配置或撤回发布 | Infra Owner | < 60 min |
| 网关协议不兼容 | 回滚客户端并锁定网关版本 | Gateway Owner | < 60 min |

## 5) 发布结论

- 发布决策：`go` / `hold` / `rollback`
- 责任人签字：
- 时间：
