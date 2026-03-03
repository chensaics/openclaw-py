import 'package:flutter/material.dart';
import 'package:pyclaw/core/models/message.dart';
import 'package:pyclaw/widgets/message_bubble.dart';
import 'package:pyclaw/widgets/shimmer_loading.dart';

class MessageList extends StatefulWidget {
  final List<Message> messages;
  final void Function(Message)? onEdit;
  final VoidCallback? onResend;
  final bool isLoading;

  const MessageList({
    super.key,
    required this.messages,
    this.onEdit,
    this.onResend,
    this.isLoading = false,
  });

  @override
  State<MessageList> createState() => _MessageListState();
}

class _MessageListState extends State<MessageList> {
  final _scrollController = ScrollController();
  int _previousCount = 0;

  @override
  void didUpdateWidget(covariant MessageList oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.messages.length > _previousCount) {
      _previousCount = widget.messages.length;
      WidgetsBinding.instance.addPostFrameCallback((_) => _scrollToBottom());
    }
  }

  void _scrollToBottom() {
    if (_scrollController.hasClients) {
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeOut,
      );
    }
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (widget.isLoading) {
      return const ShimmerLoading(itemCount: 5);
    }

    if (widget.messages.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.auto_awesome,
              size: 48,
              color: Theme.of(context).colorScheme.primary.withAlpha(100),
            ),
            const SizedBox(height: 16),
            Text(
              'Start a conversation',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.symmetric(vertical: 16),
      itemCount: widget.messages.length,
      itemBuilder: (context, index) {
        final msg = widget.messages[index];
        return _StaggeredItem(
          index: index,
          isNew: index >= _previousCount - 1,
          child: MessageBubble(
            key: ValueKey(msg.id),
            message: msg,
            onEdit: msg.role == MessageRole.user
                ? () => widget.onEdit?.call(msg)
                : null,
            onResend: msg.role == MessageRole.assistant &&
                    index == widget.messages.length - 1
                ? widget.onResend
                : null,
          ),
        );
      },
    );
  }
}

/// Fade+slide animation for newly added messages.
class _StaggeredItem extends StatefulWidget {
  final int index;
  final bool isNew;
  final Widget child;

  const _StaggeredItem({
    required this.index,
    required this.isNew,
    required this.child,
  });

  @override
  State<_StaggeredItem> createState() => _StaggeredItemState();
}

class _StaggeredItemState extends State<_StaggeredItem>
    with SingleTickerProviderStateMixin {
  late AnimationController _ctrl;
  late Animation<double> _fadeAnim;
  late Animation<Offset> _slideAnim;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 350),
    );
    final curved = CurvedAnimation(parent: _ctrl, curve: Curves.easeOutCubic);
    _fadeAnim = Tween<double>(begin: 0.0, end: 1.0).animate(curved);
    _slideAnim = Tween<Offset>(
      begin: const Offset(0, 0.15),
      end: Offset.zero,
    ).animate(curved);

    if (widget.isNew) {
      _ctrl.forward();
    } else {
      _ctrl.value = 1.0;
    }
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: _fadeAnim,
      child: SlideTransition(
        position: _slideAnim,
        child: widget.child,
      ),
    );
  }
}
