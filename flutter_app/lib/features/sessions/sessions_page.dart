import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:pyclaw/core/models/session.dart';
import 'package:pyclaw/core/providers/session_provider.dart';
import 'package:pyclaw/core/providers/chat_provider.dart';
import 'package:pyclaw/features/sessions/session_tile.dart';

class SessionsPage extends ConsumerStatefulWidget {
  const SessionsPage({super.key});

  @override
  ConsumerState<SessionsPage> createState() => _SessionsPageState();
}

class _SessionsPageState extends ConsumerState<SessionsPage> {
  String _query = '';

  @override
  void initState() {
    super.initState();
    Future.microtask(() => ref.read(sessionProvider.notifier).load());
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(sessionProvider);
    final scheme = Theme.of(context).colorScheme;

    final filtered = _query.isEmpty
        ? state.sessions
        : state.sessions
            .where(
              (s) =>
                  s.title.toLowerCase().contains(_query.toLowerCase()) ||
                  (s.preview ?? '')
                      .toLowerCase()
                      .contains(_query.toLowerCase()),
            )
            .toList();

    final grouped = _groupByDate(filtered);

    return Column(
      children: [
        // Header
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          decoration: BoxDecoration(
            color: scheme.surface,
            border: Border(
                bottom: BorderSide(color: scheme.outlineVariant, width: 0.5)),
          ),
          child: Row(
            children: [
              Icon(Icons.history, color: scheme.primary, size: 20),
              const SizedBox(width: 8),
              Text('Sessions', style: Theme.of(context).textTheme.titleMedium),
              const Spacer(),
              SizedBox(
                width: 200,
                child: TextField(
                  decoration: InputDecoration(
                    hintText: 'Search...',
                    prefixIcon: const Icon(Icons.search, size: 18),
                    isDense: true,
                    contentPadding:
                        const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(20)),
                  ),
                  onChanged: (v) => setState(() => _query = v),
                ),
              ),
            ],
          ),
        ),

        // Body
        Expanded(
          child: state.isLoading
              ? const Center(child: CircularProgressIndicator())
              : filtered.isEmpty
                  ? Center(
                      child: Text('No sessions',
                          style: TextStyle(color: scheme.onSurfaceVariant)),
                    )
                  : ListView.builder(
                      padding: const EdgeInsets.all(16),
                      itemCount: grouped.length,
                      itemBuilder: (context, index) {
                        final group = grouped[index];
                        return Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Padding(
                              padding: const EdgeInsets.only(top: 8, bottom: 4),
                              child: Text(
                                group.label,
                                style: Theme.of(context)
                                    .textTheme
                                    .labelMedium
                                    ?.copyWith(
                                      color: scheme.onSurfaceVariant,
                                    ),
                              ),
                            ),
                            ...group.sessions.map((s) => SessionTile(
                                  session: s,
                                  onTap: () {
                                    ref.read(chatProvider.notifier).loadSession(
                                        s.id,
                                        agentId: s.agentId ?? 'main');
                                    context.go('/chat');
                                  },
                                  onDelete: () => ref
                                      .read(sessionProvider.notifier)
                                      .delete(s.id),
                                )),
                          ],
                        );
                      },
                    ),
        ),
      ],
    );
  }

  List<_DateGroup> _groupByDate(List<Session> sessions) {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final yesterday = today.subtract(const Duration(days: 1));
    final weekAgo = today.subtract(const Duration(days: 7));

    final todayList = <Session>[];
    final yesterdayList = <Session>[];
    final weekList = <Session>[];
    final olderList = <Session>[];

    for (final s in sessions) {
      final d = DateTime(s.updatedAt.year, s.updatedAt.month, s.updatedAt.day);
      if (d == today) {
        todayList.add(s);
      } else if (d == yesterday) {
        yesterdayList.add(s);
      } else if (d.isAfter(weekAgo)) {
        weekList.add(s);
      } else {
        olderList.add(s);
      }
    }

    return [
      if (todayList.isNotEmpty) _DateGroup('Today', todayList),
      if (yesterdayList.isNotEmpty) _DateGroup('Yesterday', yesterdayList),
      if (weekList.isNotEmpty) _DateGroup('This Week', weekList),
      if (olderList.isNotEmpty) _DateGroup('Older', olderList),
    ];
  }
}

class _DateGroup {
  final String label;
  final List<Session> sessions;
  _DateGroup(this.label, this.sessions);
}
