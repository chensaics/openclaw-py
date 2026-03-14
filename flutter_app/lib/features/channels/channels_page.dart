import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:pyclaw/core/models/channel.dart';
import 'package:pyclaw/core/providers/gateway_provider.dart';
import 'package:pyclaw/core/theme/colors.dart';

final _channelsProvider =
    FutureProvider.autoDispose<List<Channel>>((ref) async {
  final client = ref.watch(gatewayClientProvider);
  final result = await client.call('channels.list');
  return (result['channels'] as List?)
          ?.map((c) => Channel.fromJson(c as Map<String, dynamic>))
          .toList() ??
      [];
});

class ChannelsPage extends ConsumerWidget {
  const ChannelsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncChannels = ref.watch(_channelsProvider);
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
              Icon(Icons.hub, color: scheme.primary, size: 20),
              const SizedBox(width: 8),
              Text('Channels', style: Theme.of(context).textTheme.titleMedium),
              const Spacer(),
              IconButton(
                icon: const Icon(Icons.refresh),
                onPressed: () => ref.invalidate(_channelsProvider),
              ),
            ],
          ),
        ),
        Expanded(
          child: asyncChannels.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (e, _) => Center(child: Text('Error: $e')),
            data: (channels) => channels.isEmpty
                ? Center(
                    child: Text('No channels configured', style: TextStyle(color: scheme.onSurfaceVariant)),
                  )
                : ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: channels.length,
                    itemBuilder: (context, i) => _ChannelTile(channel: channels[i]),
                  ),
          ),
        ),
      ],
    );
  }
}

class _ChannelTile extends StatelessWidget {
  final Channel channel;
  const _ChannelTile({required this.channel});

  IconData get _typeIcon => switch (channel.type) {
        'telegram' => Icons.telegram,
        'discord' => Icons.discord,
        'slack' => Icons.mark_unread_chat_alt,
        'wechat' => Icons.wechat,
        'webhook' => Icons.webhook,
        _ => Icons.hub,
      };

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final (statusColor, statusLabel) = switch (channel.state) {
      ChannelState.online => (AppColors.success, 'Online'),
      ChannelState.offline => (Colors.grey, 'Offline'),
      ChannelState.error => (AppColors.error, 'Error'),
    };

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        leading: CircleAvatar(
          backgroundColor: statusColor.withAlpha(30),
          child: Icon(_typeIcon, color: statusColor, size: 22),
        ),
        title: Text(
          channel.label ?? channel.type,
          style: Theme.of(context).textTheme.titleSmall,
        ),
        subtitle: Text(
          '${channel.messageCount} messages',
          style: TextStyle(fontSize: 12, color: scheme.onSurfaceVariant),
        ),
        trailing: Chip(
          label: Text(statusLabel, style: TextStyle(fontSize: 11, color: statusColor)),
          backgroundColor: statusColor.withAlpha(20),
          visualDensity: VisualDensity.compact,
          side: BorderSide.none,
        ),
      ),
    );
  }
}
