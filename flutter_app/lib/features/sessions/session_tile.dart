import 'package:flutter/material.dart';
import 'package:pyclaw/core/models/session.dart';

/// A single session item in the session list.
class SessionTile extends StatelessWidget {
  final Session session;
  final VoidCallback? onTap;
  final VoidCallback? onDelete;

  const SessionTile({
    super.key,
    required this.session,
    this.onTap,
    this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;

    return Card(
      margin: const EdgeInsets.only(bottom: 6),
      child: ListTile(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        leading: Hero(
          tag: 'session-avatar-${session.id}',
          child: CircleAvatar(
            backgroundColor: scheme.primaryContainer,
            child: Icon(Icons.chat_bubble_outline, color: scheme.onPrimaryContainer, size: 18),
          ),
        ),
        title: Text(
          session.title.isNotEmpty ? session.title : 'Session ${session.id.substring(0, 8)}',
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        subtitle: session.preview != null
            ? Text(
                session.preview!,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(fontSize: 12, color: scheme.onSurfaceVariant),
              )
            : null,
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              '${session.messageCount} msgs',
              style: TextStyle(fontSize: 11, color: scheme.onSurfaceVariant),
            ),
            if (onDelete != null)
              IconButton(
                icon: Icon(Icons.delete_outline, size: 18, color: scheme.error),
                onPressed: () => _confirmDelete(context),
                tooltip: 'Delete',
              ),
          ],
        ),
        onTap: onTap,
      ),
    );
  }

  void _confirmDelete(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete Session?'),
        content: const Text('This action cannot be undone.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          FilledButton(
            onPressed: () {
              Navigator.pop(ctx);
              onDelete?.call();
            },
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(context).colorScheme.error,
            ),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
  }
}
