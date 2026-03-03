import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:pyclaw/core/models/message.dart';
import 'package:pyclaw/core/theme/colors.dart';
import 'package:pyclaw/core/theme/typography.dart';
import 'package:pyclaw/widgets/tool_call_card.dart';

/// A chat message bubble with avatar, content, and actions.
class MessageBubble extends StatelessWidget {
  final Message message;
  final VoidCallback? onEdit;
  final VoidCallback? onResend;

  const MessageBubble({
    super.key,
    required this.message,
    this.onEdit,
    this.onResend,
  });

  @override
  Widget build(BuildContext context) {
    final isUser = message.role == MessageRole.user;
    final scheme = Theme.of(context).colorScheme;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        textDirection: isUser ? TextDirection.rtl : TextDirection.ltr,
        children: [
          _Avatar(role: message.role),
          const SizedBox(width: 12),
          Flexible(
            child: Column(
              crossAxisAlignment:
                  isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
              children: [
                _RoleLabel(role: message.role),
                const SizedBox(height: 4),
                _ContentCard(
                  message: message,
                  isUser: isUser,
                  scheme: scheme,
                ),
                if (message.toolCalls.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Column(
                      children: message.toolCalls
                          .map((tc) => Padding(
                                padding: const EdgeInsets.only(bottom: 6),
                                child: ToolCallCard(toolCall: tc),
                              ))
                          .toList(),
                    ),
                  ),
                _ActionRow(
                  message: message,
                  onEdit: onEdit,
                  onResend: onResend,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Avatar extends StatelessWidget {
  final MessageRole role;
  const _Avatar({required this.role});

  @override
  Widget build(BuildContext context) {
    final (icon, color) = switch (role) {
      MessageRole.user => (Icons.person, AppColors.userAvatar),
      MessageRole.assistant => (Icons.auto_awesome, AppColors.assistantAvatar),
      MessageRole.system => (Icons.info_outline, AppColors.systemAvatar),
      MessageRole.tool => (Icons.build, AppColors.toolAvatar),
    };
    return CircleAvatar(
      radius: 18,
      backgroundColor: color.withAlpha(30),
      child: Icon(icon, size: 20, color: color),
    );
  }
}

class _RoleLabel extends StatelessWidget {
  final MessageRole role;
  const _RoleLabel({required this.role});

  @override
  Widget build(BuildContext context) {
    return Text(
      role.name[0].toUpperCase() + role.name.substring(1),
      style: Theme.of(context).textTheme.labelSmall?.copyWith(
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
    );
  }
}

class _ContentCard extends StatelessWidget {
  final Message message;
  final bool isUser;
  final ColorScheme scheme;

  const _ContentCard({
    required this.message,
    required this.isUser,
    required this.scheme,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: BoxConstraints(
        maxWidth: MediaQuery.sizeOf(context).width * 0.72,
      ),
      decoration: BoxDecoration(
        color: isUser ? scheme.primaryContainer : scheme.surfaceContainerLow,
        borderRadius: BorderRadius.only(
          topLeft: const Radius.circular(18),
          topRight: const Radius.circular(18),
          bottomLeft: Radius.circular(isUser ? 18 : 4),
          bottomRight: Radius.circular(isUser ? 4 : 18),
        ),
        boxShadow: [
          BoxShadow(
            color: scheme.shadow.withAlpha(8),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: message.content.isEmpty && message.isStreaming
          ? _StreamingIndicator(color: scheme.onSurfaceVariant)
          : MarkdownBody(
              data: message.content,
              selectable: true,
              styleSheet: MarkdownStyleSheet.fromTheme(Theme.of(context)).copyWith(
                p: AppTypography.bodyText(
                  color: isUser ? scheme.onPrimaryContainer : scheme.onSurface,
                ),
                codeblockDecoration: BoxDecoration(
                  color: scheme.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(8),
                ),
                code: AppTypography.codeStyle(
                  color: scheme.onSurface,
                  fontSize: 13,
                ),
              ),
            ),
    );
  }
}

/// Typewriter-style streaming indicator with staggered dot animation + blinking cursor.
class _StreamingIndicator extends StatefulWidget {
  final Color color;
  const _StreamingIndicator({required this.color});

  @override
  State<_StreamingIndicator> createState() => _StreamingIndicatorState();
}

class _StreamingIndicatorState extends State<_StreamingIndicator>
    with TickerProviderStateMixin {
  late AnimationController _dotCtrl;
  late AnimationController _cursorCtrl;

  @override
  void initState() {
    super.initState();
    _dotCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat();
    _cursorCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 530),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _dotCtrl.dispose();
    _cursorCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        ...List.generate(3, (i) {
          final begin = i * 0.2;
          final end = begin + 0.4;
          return AnimatedBuilder(
            animation: _dotCtrl,
            builder: (_, __) {
              final t = _dotCtrl.value;
              final visible = t >= begin && t <= end;
              return Padding(
                padding: EdgeInsets.only(left: i > 0 ? 4 : 0),
                child: AnimatedOpacity(
                  opacity: visible ? 1.0 : 0.3,
                  duration: const Duration(milliseconds: 150),
                  child: CircleAvatar(radius: 3.5, backgroundColor: widget.color),
                ),
              );
            },
          );
        }),
        const SizedBox(width: 4),
        FadeTransition(
          opacity: _cursorCtrl.drive(Tween(begin: 0.0, end: 1.0)),
          child: Container(
            width: 2,
            height: 16,
            color: widget.color,
          ),
        ),
      ],
    );
  }
}

class _ActionRow extends StatelessWidget {
  final Message message;
  final VoidCallback? onEdit;
  final VoidCallback? onResend;

  const _ActionRow({required this.message, this.onEdit, this.onResend});

  @override
  Widget build(BuildContext context) {
    if (message.isStreaming) return const SizedBox.shrink();
    final scheme = Theme.of(context).colorScheme;
    final style = TextStyle(fontSize: 12, color: scheme.onSurfaceVariant);

    return Padding(
      padding: const EdgeInsets.only(top: 4),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          IconButton(
            icon: const Icon(Icons.copy, size: 16),
            tooltip: 'Copy',
            onPressed: () {
              Clipboard.setData(ClipboardData(text: message.content));
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Copied'), duration: Duration(seconds: 1)),
              );
            },
            visualDensity: VisualDensity.compact,
            style: IconButton.styleFrom(
              foregroundColor: scheme.onSurfaceVariant,
            ),
          ),
          if (message.role == MessageRole.user && onEdit != null)
            IconButton(
              icon: const Icon(Icons.edit, size: 16),
              tooltip: 'Edit',
              onPressed: onEdit,
              visualDensity: VisualDensity.compact,
              style: IconButton.styleFrom(
                foregroundColor: scheme.onSurfaceVariant,
              ),
            ),
          if (message.role == MessageRole.assistant && onResend != null)
            IconButton(
              icon: const Icon(Icons.refresh, size: 16),
              tooltip: 'Regenerate',
              onPressed: onResend,
              visualDensity: VisualDensity.compact,
              style: IconButton.styleFrom(
                foregroundColor: scheme.onSurfaceVariant,
              ),
            ),
          const SizedBox(width: 8),
          Text(
            _formatTime(message.createdAt),
            style: style,
          ),
        ],
      ),
    );
  }

  String _formatTime(DateTime dt) {
    return '${dt.hour.toString().padLeft(2, '0')}:'
        '${dt.minute.toString().padLeft(2, '0')}';
  }
}
