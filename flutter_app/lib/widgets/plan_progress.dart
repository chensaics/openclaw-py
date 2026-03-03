import 'package:flutter/material.dart';
import 'package:pyclaw/core/models/plan.dart';
import 'package:pyclaw/core/theme/colors.dart';

/// Displays the progress of a plan as a stepper with linear indicator.
class PlanProgress extends StatelessWidget {
  final Plan plan;
  final VoidCallback? onResume;

  const PlanProgress({super.key, required this.plan, this.onResume});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.checklist, color: scheme.primary, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    plan.goal,
                    style: Theme.of(context).textTheme.titleSmall,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                Text(
                  '${plan.completedCount}/${plan.totalCount}',
                  style: Theme.of(context).textTheme.labelMedium?.copyWith(
                        color: scheme.onSurfaceVariant,
                      ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: plan.progress,
                backgroundColor: scheme.surfaceContainerHighest,
                color: plan.progress >= 1.0 ? AppColors.success : scheme.primary,
                minHeight: 6,
              ),
            ),
            const SizedBox(height: 12),
            ...plan.steps.map((step) => _StepRow(step: step)),
            if (onResume != null && plan.progress < 1.0)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: FilledButton.tonal(
                  onPressed: onResume,
                  child: const Text('Resume'),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _StepRow extends StatelessWidget {
  final PlanStep step;
  const _StepRow({required this.step});

  @override
  Widget build(BuildContext context) {
    final (icon, color) = switch (step.status) {
      StepStatus.done => (Icons.check_circle, AppColors.success),
      StepStatus.running => (Icons.play_circle, AppColors.warning),
      StepStatus.failed => (Icons.cancel, AppColors.error),
      StepStatus.skipped => (Icons.skip_next, Colors.grey),
      StepStatus.pending => (Icons.radio_button_unchecked, Colors.grey),
    };

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        children: [
          Icon(icon, size: 18, color: color),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              step.description,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    decoration: step.status == StepStatus.done
                        ? TextDecoration.lineThrough
                        : null,
                    color: step.status == StepStatus.pending
                        ? Theme.of(context).colorScheme.onSurfaceVariant
                        : null,
                  ),
            ),
          ),
        ],
      ),
    );
  }
}
