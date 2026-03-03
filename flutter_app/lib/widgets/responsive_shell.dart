import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:pyclaw/core/gateway_client.dart';
import 'package:pyclaw/core/providers/gateway_provider.dart';
import 'package:pyclaw/core/theme/app_theme.dart';
import 'package:pyclaw/core/theme/colors.dart';

/// Destinations for the navigation rail / bar.
class _NavItem {
  final String label;
  final IconData icon;
  final IconData selectedIcon;
  final String route;

  const _NavItem(this.label, this.icon, this.selectedIcon, this.route);
}

const _destinations = [
  _NavItem('Chat', Icons.chat_outlined, Icons.chat, '/chat'),
  _NavItem('Sessions', Icons.history_outlined, Icons.history, '/sessions'),
  _NavItem('Agents', Icons.smart_toy_outlined, Icons.smart_toy, '/agents'),
  _NavItem('Channels', Icons.hub_outlined, Icons.hub, '/channels'),
  _NavItem('Plans', Icons.checklist_outlined, Icons.checklist, '/plans'),
  _NavItem('Cron', Icons.schedule_outlined, Icons.schedule, '/cron'),
  _NavItem('System', Icons.monitor_heart_outlined, Icons.monitor_heart, '/system'),
  _NavItem('Settings', Icons.settings_outlined, Icons.settings, '/settings'),
];

/// Adaptive layout shell: NavigationRail (desktop/tablet) or NavigationBar (mobile).
class ResponsiveShell extends ConsumerWidget {
  final Widget child;
  const ResponsiveShell({super.key, required this.child});

  int _currentIndex(BuildContext context) {
    final loc = GoRouterState.of(context).uri.toString();
    final idx = _destinations.indexWhere((d) => loc.startsWith(d.route));
    return idx < 0 ? 0 : idx;
  }

  void _onTap(BuildContext context, int index) {
    context.go(_destinations[index].route);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isMobile = AppTheme.isMobile(context);
    final selected = _currentIndex(context);
    final gwState = ref.watch(gatewayProvider);

    if (isMobile) {
      return Scaffold(
        body: child,
        bottomNavigationBar: NavigationBar(
          selectedIndex: selected,
          onDestinationSelected: (i) => _onTap(context, i),
          destinations: _destinations.map((d) {
            return NavigationDestination(
              icon: Icon(d.icon),
              selectedIcon: Icon(d.selectedIcon),
              label: d.label,
            );
          }).toList(),
        ),
      );
    }

    return Scaffold(
      body: Row(
        children: [
          NavigationRail(
            selectedIndex: selected,
            onDestinationSelected: (i) => _onTap(context, i),
            extended: AppTheme.isDesktop(context),
            labelType: AppTheme.isDesktop(context)
                ? NavigationRailLabelType.none
                : NavigationRailLabelType.all,
            leading: Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.auto_awesome, color: Theme.of(context).colorScheme.primary),
                  const SizedBox(height: 4),
                  _GatewayDot(gwState),
                ],
              ),
            ),
            destinations: _destinations.map((d) {
              return NavigationRailDestination(
                icon: Icon(d.icon),
                selectedIcon: Icon(d.selectedIcon),
                label: Text(d.label),
              );
            }).toList(),
          ),
          const VerticalDivider(width: 1, thickness: 1),
          Expanded(child: child),
        ],
      ),
    );
  }
}

class _GatewayDot extends StatelessWidget {
  final GatewayState state;
  const _GatewayDot(this.state);

  @override
  Widget build(BuildContext context) {
    final color = switch (state) {
      GatewayState.connected => AppColors.success,
      GatewayState.connecting => AppColors.warning,
      GatewayState.disconnected => AppColors.error,
    };
    return Tooltip(
      message: 'Gateway: ${state.name}',
      child: Container(
        width: 8,
        height: 8,
        decoration: BoxDecoration(shape: BoxShape.circle, color: color),
      ),
    );
  }
}
