import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:pyclaw/core/providers/chat_provider.dart';
import 'package:pyclaw/features/chat/message_list.dart';
import 'package:pyclaw/features/chat/chat_input.dart';

class ChatPage extends ConsumerStatefulWidget {
  const ChatPage({super.key});

  @override
  ConsumerState<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends ConsumerState<ChatPage> {
  @override
  Widget build(BuildContext context) {
    final chatState = ref.watch(chatProvider);
    final scheme = Theme.of(context).colorScheme;

    return Column(
      children: [
        // Toolbar
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          decoration: BoxDecoration(
            color: scheme.surface,
            border: Border(bottom: BorderSide(color: scheme.outlineVariant, width: 0.5)),
          ),
          child: Row(
            children: [
              Icon(Icons.chat, color: scheme.primary, size: 20),
              const SizedBox(width: 8),
              Text('Chat', style: Theme.of(context).textTheme.titleMedium),
              const Spacer(),
              if (chatState.isGenerating)
                Padding(
                  padding: const EdgeInsets.only(right: 12),
                  child: SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2, color: scheme.primary),
                  ),
                ),
              IconButton(
                icon: const Icon(Icons.add),
                tooltip: 'New Chat',
                onPressed: () => ref.read(chatProvider.notifier).newSession(),
              ),
            ],
          ),
        ),

        // Messages
        Expanded(
          child: MessageList(
            messages: chatState.messages,
            onEdit: (msg) => _showEditDialog(context, msg.id, msg.content),
            onResend: () => ref.read(chatProvider.notifier).resend(),
          ),
        ),

        // Error banner
        if (chatState.error != null)
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            color: scheme.errorContainer,
            child: Row(
              children: [
                Icon(Icons.error_outline, color: scheme.error, size: 18),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    chatState.error!,
                    style: TextStyle(color: scheme.onErrorContainer, fontSize: 13),
                  ),
                ),
              ],
            ),
          ),

        // Input
        ChatInput(
          isGenerating: chatState.isGenerating,
          onSend: (text) => ref.read(chatProvider.notifier).send(text),
          onAbort: () => ref.read(chatProvider.notifier).abort(),
        ),
      ],
    );
  }

  void _showEditDialog(BuildContext context, String messageId, String currentContent) {
    final controller = TextEditingController(text: currentContent);
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Edit Message'),
        content: TextField(
          controller: controller,
          maxLines: 5,
          decoration: const InputDecoration(
            hintText: 'Edit your message...',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () {
              Navigator.pop(ctx);
              ref.read(chatProvider.notifier).editMessage(messageId, controller.text);
            },
            child: const Text('Save & Regenerate'),
          ),
        ],
      ),
    );
    controller.dispose();
  }
}
