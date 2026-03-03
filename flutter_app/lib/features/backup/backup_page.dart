import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:pyclaw/core/gateway_client.dart';
import 'package:pyclaw/core/providers/gateway_provider.dart';
import 'package:pyclaw/core/theme/colors.dart';

final _backupListProvider =
    FutureProvider.autoDispose<List<Map<String, dynamic>>>((ref) async {
  final client = ref.watch(gatewayClientProvider);
  final result = await client.call('backup.status');
  return (result['backups'] as List?)?.cast<Map<String, dynamic>>() ?? [];
});

class BackupPage extends ConsumerWidget {
  const BackupPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncBackups = ref.watch(_backupListProvider);
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
              Icon(Icons.backup, color: scheme.primary, size: 20),
              const SizedBox(width: 8),
              Text('Backup', style: Theme.of(context).textTheme.titleMedium),
              const Spacer(),
              FilledButton.tonalIcon(
                icon: const Icon(Icons.cloud_upload, size: 18),
                label: const Text('Export'),
                onPressed: () => _export(context, ref),
              ),
              const SizedBox(width: 8),
              IconButton(
                icon: const Icon(Icons.refresh),
                onPressed: () => ref.invalidate(_backupListProvider),
              ),
            ],
          ),
        ),
        Expanded(
          child: asyncBackups.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (e, _) => Center(child: Text('Error: $e')),
            data: (backups) => backups.isEmpty
                ? Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.cloud_off, size: 48, color: scheme.primary.withAlpha(100)),
                        const SizedBox(height: 12),
                        Text('No backups yet', style: TextStyle(color: scheme.onSurfaceVariant)),
                        const SizedBox(height: 8),
                        FilledButton.tonal(
                          onPressed: () => _export(context, ref),
                          child: const Text('Create First Backup'),
                        ),
                      ],
                    ),
                  )
                : ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: backups.length,
                    itemBuilder: (context, i) {
                      final b = backups[i];
                      return Card(
                        margin: const EdgeInsets.only(bottom: 8),
                        child: ListTile(
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                          leading: CircleAvatar(
                            backgroundColor: AppColors.info.withAlpha(30),
                            child: const Icon(Icons.archive, color: AppColors.info, size: 20),
                          ),
                          title: Text(
                            b['filename'] as String? ?? 'backup',
                            style: Theme.of(context).textTheme.titleSmall,
                          ),
                          subtitle: Text(
                            '${b['size_mb'] ?? '?'} MB  •  ${b['created_at'] ?? ''}',
                            style: TextStyle(fontSize: 12, color: scheme.onSurfaceVariant),
                          ),
                        ),
                      );
                    },
                  ),
          ),
        ),
      ],
    );
  }

  Future<void> _export(BuildContext context, WidgetRef ref) async {
    try {
      final client = ref.read(gatewayClientProvider);
      await client.call('backup.export');
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Backup exported successfully')),
        );
        ref.invalidate(_backupListProvider);
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Export failed: $e')),
        );
      }
    }
  }
}
