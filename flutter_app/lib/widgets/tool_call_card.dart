import 'package:flutter/material.dart';
import 'package:pyclaw/core/models/message.dart';
import 'package:pyclaw/core/theme/colors.dart';
import 'package:pyclaw/core/theme/typography.dart';

/// Card showing a tool invocation with expandable result.
class ToolCallCard extends StatelessWidget {
  final ToolCall toolCall;
  const ToolCallCard({super.key, required this.toolCall});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;

    return Card(
      elevation: 0,
      color: scheme.surfaceContainerLow,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: scheme.outlineVariant, width: 0.5),
      ),
      child: ExpansionTile(
        leading: toolCall.isRunning
            ? const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: AppColors.warning,
                ),
              )
            : Icon(
                toolCall.error != null ? Icons.error_outline : Icons.check_circle,
                size: 20,
                color: toolCall.error != null ? AppColors.error : AppColors.success,
              ),
        title: Text(
          toolCall.name,
          style: Theme.of(context).textTheme.titleSmall,
        ),
        subtitle: toolCall.isRunning
            ? const Text('Running...', style: TextStyle(color: AppColors.warning, fontSize: 12))
            : null,
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
        children: [
          if (toolCall.arguments.isNotEmpty) ...[
            _Section(label: 'Arguments', content: toolCall.arguments, scheme: scheme),
            const SizedBox(height: 8),
          ],
          if (toolCall.result != null)
            _Section(label: 'Result', content: toolCall.result!, scheme: scheme),
          if (toolCall.error != null)
            _Section(label: 'Error', content: toolCall.error!, scheme: scheme, isError: true),
        ],
      ),
    );
  }
}

class _Section extends StatelessWidget {
  final String label;
  final String content;
  final ColorScheme scheme;
  final bool isError;

  const _Section({
    required this.label,
    required this.content,
    required this.scheme,
    this.isError = false,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: Theme.of(context).textTheme.labelSmall?.copyWith(
                color: scheme.onSurfaceVariant,
              ),
        ),
        const SizedBox(height: 4),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            color: isError
                ? AppColors.error.withAlpha(20)
                : scheme.surfaceContainerHighest,
            borderRadius: BorderRadius.circular(8),
          ),
          child: SelectableText(
            content.length > 2000 ? '${content.substring(0, 2000)}…' : content,
            style: AppTypography.codeStyle(
              fontSize: 12,
              color: isError ? AppColors.error : scheme.onSurface,
            ),
          ),
        ),
      ],
    );
  }
}
