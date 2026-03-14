import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:pyclaw/core/models/cron_job.dart';
import 'package:pyclaw/core/providers/gateway_provider.dart';
import 'package:pyclaw/core/theme/colors.dart';
import 'package:pyclaw/features/cron/cron_form.dart';

final _cronListProvider =
    FutureProvider.autoDispose<List<CronJob>>((ref) async {
  final client = ref.watch(gatewayClientProvider);
  final result = await client.call('cron.list');
  return (result['jobs'] as List?)
          ?.map((j) => CronJob.fromJson(j as Map<String, dynamic>))
          .toList() ??
      [];
});

class CronPage extends ConsumerWidget {
  const CronPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncJobs = ref.watch(_cronListProvider);
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
              Icon(Icons.schedule, color: scheme.primary, size: 20),
              const SizedBox(width: 8),
              Text('Scheduled Tasks', style: Theme.of(context).textTheme.titleMedium),
              const Spacer(),
              IconButton(
                icon: const Icon(Icons.refresh),
                onPressed: () => ref.invalidate(_cronListProvider),
              ),
              const SizedBox(width: 4),
              FilledButton.tonalIcon(
                icon: const Icon(Icons.add, size: 18),
                label: const Text('Add'),
                onPressed: () => _showAddDialog(context, ref),
              ),
            ],
          ),
        ),
        Expanded(
          child: asyncJobs.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (e, _) => Center(child: Text('Error: $e')),
            data: (jobs) => jobs.isEmpty
                ? Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.event_busy, size: 48, color: scheme.primary.withAlpha(100)),
                        const SizedBox(height: 12),
                        Text('No scheduled tasks', style: TextStyle(color: scheme.onSurfaceVariant)),
                      ],
                    ),
                  )
                : ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: jobs.length,
                    itemBuilder: (context, i) => _CronJobTile(job: jobs[i]),
                  ),
          ),
        ),
      ],
    );
  }

  void _showAddDialog(BuildContext context, WidgetRef ref) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (_) => Padding(
        padding: EdgeInsets.only(
          bottom: MediaQuery.viewInsetsOf(context).bottom,
        ),
        child: CronForm(
          onSubmit: (params) async {
            final client = ref.read(gatewayClientProvider);
            await client.call('cron.add', params);
            ref.invalidate(_cronListProvider);
          },
        ),
      ),
    );
  }
}

class _CronJobTile extends StatelessWidget {
  final CronJob job;
  const _CronJobTile({required this.job});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        leading: CircleAvatar(
          backgroundColor: job.enabled
              ? AppColors.success.withAlpha(30)
              : scheme.surfaceContainerHighest,
          child: Icon(
            job.enabled ? Icons.play_arrow : Icons.pause,
            color: job.enabled ? AppColors.success : scheme.onSurfaceVariant,
            size: 20,
          ),
        ),
        title: Text(job.name, maxLines: 1, overflow: TextOverflow.ellipsis),
        subtitle: Text(
          '${job.scheduleType.name}: ${job.schedule}',
          style: TextStyle(fontSize: 12, color: scheme.onSurfaceVariant),
        ),
        trailing: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            if (job.nextRun != null)
              Text(
                'Next: ${_fmt(job.nextRun!)}',
                style: TextStyle(fontSize: 11, color: scheme.onSurfaceVariant),
              ),
            if (job.lastRun != null)
              Text(
                'Last: ${_fmt(job.lastRun!)}',
                style: TextStyle(fontSize: 11, color: scheme.onSurfaceVariant),
              ),
          ],
        ),
      ),
    );
  }

  String _fmt(DateTime dt) =>
      '${dt.month}/${dt.day} ${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
}
