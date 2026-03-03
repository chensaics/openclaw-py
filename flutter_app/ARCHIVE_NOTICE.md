# Flutter App — 参考设计归档

> **状态**: 已归档 (Phase 72)
> **用途**: 仅作为 UI/UX 参考设计资料，不再作为独立客户端维护

## 归档原因

Flet 框架的底层渲染引擎就是 Flutter。维护一个独立的 Flutter/Dart 客户端
等于跳过 Flet 重复实现了相同功能，造成双倍维护成本。

Phase 72 决定以 Flet UI (`src/pyclaw/ui/`) 为唯一客户端，并将本 Flutter App
中的高级 UI/UX 特性（Shimmer、Material 3 配色、动画等）反哺到 Flet UI。

## 可复用的设计参考

| 目录/文件 | 参考价值 |
|-----------|---------|
| `lib/core/theme/` | Material 3 配色方案、Typography 定义 |
| `lib/widgets/shimmer_loading.dart` | Shimmer 骨架屏实现模式 |
| `lib/widgets/stagger_list.dart` | 列表入场动画 |
| `lib/widgets/message_bubble.dart` | 聊天气泡 UI 设计 |
| `lib/widgets/latex_text.dart` | LaTeX 公式渲染集成 |
| `lib/core/models/` | 数据模型设计（已反哺到 Python 端） |
| `lib/core/providers/` | Riverpod 状态管理模式 |
| `lib/core/storage/local_cache.dart` | 离线缓存策略 |
| `web/manifest.json` | PWA 配置参考 |

## 统计

- 46 个 Dart 源文件，~4,980 LOC
- 49 个单元测试
- 9 个功能页面 + 10 个通用组件

## 如需运行

```bash
cd flutter_app
flutter pub get
flutter run -d chrome   # Web
flutter run -d macos    # Desktop
```

> 注意：此代码不再与 Gateway API 变更保持同步。如需最新客户端功能，
> 请使用 `flet run src/pyclaw/ui/app.py` 或 `python flet_app.py`。
