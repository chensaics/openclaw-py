import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:pyclaw/core/theme/app_theme.dart';
import 'package:pyclaw/core/providers/gateway_provider.dart';
import 'package:pyclaw/widgets/responsive_shell.dart';
import 'package:pyclaw/features/chat/chat_page.dart';
import 'package:pyclaw/features/sessions/sessions_page.dart';
import 'package:pyclaw/features/plans/plans_page.dart';
import 'package:pyclaw/features/cron/cron_page.dart';
import 'package:pyclaw/features/agents/agents_page.dart';
import 'package:pyclaw/features/channels/channels_page.dart';
import 'package:pyclaw/features/settings/settings_page.dart';
import 'package:pyclaw/features/system/system_page.dart';
import 'package:pyclaw/features/backup/backup_page.dart';

CustomTransitionPage<void> _fadePage(Widget child, GoRouterState state) {
  return CustomTransitionPage<void>(
    key: state.pageKey,
    child: child,
    transitionsBuilder: (context, animation, secondaryAnimation, child) {
      return FadeTransition(opacity: animation, child: child);
    },
    transitionDuration: const Duration(milliseconds: 200),
  );
}

final _router = GoRouter(
  initialLocation: '/chat',
  routes: [
    ShellRoute(
      builder: (context, state, child) => ResponsiveShell(child: child),
      routes: [
        GoRoute(path: '/chat', pageBuilder: (_, s) => _fadePage(const ChatPage(), s)),
        GoRoute(path: '/sessions', pageBuilder: (_, s) => _fadePage(const SessionsPage(), s)),
        GoRoute(path: '/agents', pageBuilder: (_, s) => _fadePage(const AgentsPage(), s)),
        GoRoute(path: '/channels', pageBuilder: (_, s) => _fadePage(const ChannelsPage(), s)),
        GoRoute(path: '/plans', pageBuilder: (_, s) => _fadePage(const PlansPage(), s)),
        GoRoute(path: '/cron', pageBuilder: (_, s) => _fadePage(const CronPage(), s)),
        GoRoute(path: '/system', pageBuilder: (_, s) => _fadePage(const SystemPage(), s)),
        GoRoute(path: '/backup', pageBuilder: (_, s) => _fadePage(const BackupPage(), s)),
        GoRoute(path: '/settings', pageBuilder: (_, s) => _fadePage(const SettingsPage(), s)),
      ],
    ),
  ],
);

class PyClawApp extends ConsumerStatefulWidget {
  const PyClawApp({super.key});

  @override
  ConsumerState<PyClawApp> createState() => _PyClawAppState();
}

class _PyClawAppState extends ConsumerState<PyClawApp> {
  @override
  void initState() {
    super.initState();
    Future.microtask(() => ref.read(gatewayProvider.notifier).connect());
  }

  @override
  Widget build(BuildContext context) {
    final themeMode = ref.watch(themeModeProvider);
    final seedColor = ref.watch(seedColorProvider);

    return MaterialApp.router(
      title: 'pyclaw',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(seedColor: seedColor),
      darkTheme: AppTheme.dark(seedColor: seedColor),
      themeMode: themeMode,
      routerConfig: _router,
    );
  }
}

final themeModeProvider = StateProvider<ThemeMode>((ref) => ThemeMode.system);
final seedColorProvider = StateProvider<Color>((ref) => const Color(0xFF6366F1));
