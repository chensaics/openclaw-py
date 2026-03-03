import 'package:flutter/material.dart';
import 'package:pyclaw/core/models/plan.dart';
import 'package:pyclaw/core/theme/colors.dart';

/// Vertical stepper rendering plan steps with status icons and optional results.
class StepStepper extends StatelessWidget {
  final List<PlanStep> steps;
  const StepStepper({super.key, required this.steps});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: List.generate(steps.length, (i) {
        final step = steps[i];
        final isLast = i == steps.length - 1;
        return _StepItem(step: step, isLast: isLast);
      }),
    );
  }
}

class _StepItem extends StatelessWidget {
  final PlanStep step;
  final bool isLast;
  const _StepItem({required this.step, required this.isLast});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final (icon, color) = switch (step.status) {
      StepStatus.done => (Icons.check_circle, AppColors.success),
      StepStatus.running => (Icons.play_circle_fill, AppColors.warning),
      StepStatus.failed => (Icons.cancel, AppColors.error),
      StepStatus.skipped => (Icons.skip_next, Colors.grey),
      StepStatus.pending => (Icons.radio_button_unchecked, scheme.outline),
    };

    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Column(
            children: [
              Icon(icon, size: 22, color: color),
              if (!isLast)
                Expanded(
                  child: Container(
                    width: 2,
                    color: scheme.outlineVariant,
                  ),
                ),
            ],
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.only(bottom: 16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    step.description,
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          decoration: step.status == StepStatus.done
                              ? TextDecoration.lineThrough
                              : null,
                          fontWeight: step.status == StepStatus.running
                              ? FontWeight.w600
                              : null,
                        ),
                  ),
                  if (step.result != null) ...[
                    const SizedBox(height: 4),
                    Text(
                      step.result!,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: scheme.onSurfaceVariant,
                          ),
                      maxLines: 3,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
