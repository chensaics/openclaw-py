import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:pyclaw/core/gateway_client.dart';
import 'package:pyclaw/core/models/agent.dart';
import 'package:pyclaw/core/providers/gateway_provider.dart';
import 'package:pyclaw/core/theme/colors.dart';

final _agentsProvider = FutureProvider.autoDispose<List<Agent>>((ref) async {
  final client = ref.watch(gatewayClientProvider);
  final result = await client.call('agents.list');
  return (result['agents'] as List?)
          ?.map((a) => Agent.fromJson(a as Map<String, dynamic>))
          .toList() ??
      [];
});

class AgentsPage extends ConsumerWidget {
  const AgentsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final asyncAgents = ref.watch(_agentsProvider);
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
              Icon(Icons.smart_toy, color: scheme.primary, size: 20),
              const SizedBox(width: 8),
              Text('Agents', style: Theme.of(context).textTheme.titleMedium),
              const Spacer(),
              IconButton(
                icon: const Icon(Icons.refresh),
                onPressed: () => ref.invalidate(_agentsProvider),
              ),
            ],
          ),
        ),
        Expanded(
          child: asyncAgents.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (e, _) => Center(child: Text('Error: $e')),
            data: (agents) => agents.isEmpty
                ? Center(
                    child: Text('No agents configured', style: TextStyle(color: scheme.onSurfaceVariant)),
                  )
                : ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: agents.length,
                    itemBuilder: (context, i) => _AgentCard(agent: agents[i]),
                  ),
          ),
        ),
      ],
    );
  }
}

class _AgentCard extends StatelessWidget {
  final Agent agent;
  const _AgentCard({required this.agent});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;

    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                CircleAvatar(
                  backgroundColor: AppColors.assistantAvatar.withAlpha(30),
                  child: const Icon(Icons.smart_toy, size: 20, color: AppColors.assistantAvatar),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Text(agent.name, style: Theme.of(context).textTheme.titleSmall),
                          if (agent.isDefault) ...[
                            const SizedBox(width: 8),
                            Chip(
                              label: const Text('Default', style: TextStyle(fontSize: 10)),
                              visualDensity: VisualDensity.compact,
                              backgroundColor: scheme.primaryContainer,
                              labelStyle: TextStyle(color: scheme.onPrimaryContainer),
                            ),
                          ],
                        ],
                      ),
                      if (agent.provider.isNotEmpty || agent.model.isNotEmpty)
                        Text(
                          '${agent.provider}/${agent.model}',
                          style: TextStyle(fontSize: 12, color: scheme.onSurfaceVariant),
                        ),
                    ],
                  ),
                ),
              ],
            ),
            if (agent.tools.isNotEmpty) ...[
              const SizedBox(height: 12),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: agent.tools.map((t) {
                  return Chip(
                    label: Text(t, style: const TextStyle(fontSize: 11)),
                    visualDensity: VisualDensity.compact,
                    avatar: const Icon(Icons.build, size: 14),
                  );
                }).toList(),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
