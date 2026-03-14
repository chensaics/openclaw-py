import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:pyclaw/core/gateway_client.dart';
import 'package:pyclaw/core/providers/gateway_provider.dart';
import 'package:pyclaw/core/theme/colors.dart';

final _systemInfoProvider =
    FutureProvider.autoDispose<Map<String, dynamic>>((ref) async {
  final client = ref.watch(gatewayClientProvider);
  return await client.call('system.info');
});

final _doctorProvider =
    FutureProvider.autoDispose.family<Map<String, dynamic>, void>((ref, _) async {
  final client = ref.watch(gatewayClientProvider);
  return await client.call('doctor.run');
});

class SystemPage extends ConsumerWidget {
  const SystemPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncInfo = ref.watch(_systemInfoProvider);
    final scheme = Theme.of(context).colorScheme;

    return Column(
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          decoration: BoxDecoration(
            color: scheme.surface,
            border: Border(bottom: BorderSide(color: scheme.outlineVariant, width: 0.5)),
          ),
          child: Row(
            children: [
              Icon(Icons.monitor_heart, color: scheme.primary, size: 20),
              const SizedBox(width: 8),
              Text('System', style: Theme.of(context).textTheme.titleMedium),
              const Spacer(),
              FilledButton.tonalIcon(
                icon: const Icon(Icons.health_and_safety, size: 18),
                label: const Text('Doctor'),
                onPressed: () => _showDoctor(context, ref),
              ),
              const SizedBox(width: 8),
              IconButton(
                icon: const Icon(Icons.refresh),
                onPressed: () => ref.invalidate(_systemInfoProvider),
              ),
            ],
          ),
        ),
        Expanded(
          child: asyncInfo.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (e, _) => Center(child: Text('Error: $e')),
            data: (info) => ListView(
              padding: const EdgeInsets.all(16),
              children: [
                _InfoCard(
                  title: 'Runtime',
                  items: {
                    'Version': info['version']?.toString() ?? 'unknown',
                    'Python': info['python_version']?.toString() ?? '',
                    'Uptime': info['uptime']?.toString() ?? '',
                    'PID': info['pid']?.toString() ?? '',
                  },
                ),
                const SizedBox(height: 12),
                _InfoCard(
                  title: 'Resources',
                  items: {
                    'CPU': '${info['cpu_percent'] ?? '?'}%',
                    'Memory': '${info['memory_mb'] ?? '?'} MB',
                    'Active Sessions': info['active_sessions']?.toString() ?? '0',
                    'Connected Channels': info['connected_channels']?.toString() ?? '0',
                  },
                ),
                const SizedBox(height: 12),
                _InfoCard(
                  title: 'Configuration',
                  items: {
                    'Provider': info['default_provider']?.toString() ?? '',
                    'Model': info['default_model']?.toString() ?? '',
                    'Tools': info['tool_count']?.toString() ?? '0',
                    'Agents': info['agent_count']?.toString() ?? '0',
                  },
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  void _showDoctor(BuildContext context, WidgetRef ref) {
    showDialog(
      context: context,
      builder: (_) => _DoctorDialog(ref: ref),
    );
  }
}

class _InfoCard extends StatelessWidget {
  final String title;
  final Map<String, String> items;

  const _InfoCard({required this.title, required this.items});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 12),
            ...items.entries.map((e) => Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(e.key, style: TextStyle(color: scheme.onSurfaceVariant, fontSize: 13)),
                      Text(e.value, style: const TextStyle(fontWeight: FontWeight.w500, fontSize: 13)),
                    ],
                  ),
                )),
          ],
        ),
      ),
    );
  }
}

class _DoctorDialog extends StatelessWidget {
  final WidgetRef ref;
  const _DoctorDialog({required this.ref});

  @override
  Widget build(BuildContext context) {
    final asyncDoctor = ref.watch(_doctorProvider(null));

    return AlertDialog(
      title: const Row(
        children: [
          Icon(Icons.health_and_safety, size: 22),
          SizedBox(width: 8),
          Text('System Doctor'),
        ],
      ),
      content: SizedBox(
        width: 400,
        child: asyncDoctor.when(
          loading: () => const SizedBox(
            height: 100,
            child: Center(child: CircularProgressIndicator()),
          ),
          error: (e, _) => Text('Error: $e'),
          data: (result) {
            final checks = (result['checks'] as List?) ?? [];
            return Column(
              mainAxisSize: MainAxisSize.min,
              children: checks.map((c) {
                final check = c as Map<String, dynamic>;
                final ok = check['ok'] as bool? ?? false;
                return ListTile(
                  leading: Icon(
                    ok ? Icons.check_circle : Icons.error,
                    color: ok ? AppColors.success : AppColors.error,
                    size: 20,
                  ),
                  title: Text(check['name'] as String? ?? '', style: const TextStyle(fontSize: 14)),
                  subtitle: check['detail'] != null
                      ? Text(check['detail'] as String, style: const TextStyle(fontSize: 12))
                      : null,
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                );
              }).toList(),
            );
          },
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Close'),
        ),
      ],
    );
  }
}
