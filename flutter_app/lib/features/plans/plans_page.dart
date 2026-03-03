import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:pyclaw/core/providers/plan_provider.dart';
import 'package:pyclaw/widgets/plan_progress.dart';
import 'package:pyclaw/features/plans/step_stepper.dart';

class PlansPage extends ConsumerStatefulWidget {
  const PlansPage({super.key});

  @override
  ConsumerState<PlansPage> createState() => _PlansPageState();
}

class _PlansPageState extends ConsumerState<PlansPage> {
  String? _expandedPlanId;

  @override
  void initState() {
    super.initState();
    Future.microtask(() => ref.read(planProvider.notifier).load());
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(planProvider);
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
              Icon(Icons.checklist, color: scheme.primary, size: 20),
              const SizedBox(width: 8),
              Text('Plans', style: Theme.of(context).textTheme.titleMedium),
              const Spacer(),
              IconButton(
                icon: const Icon(Icons.refresh),
                tooltip: 'Refresh',
                onPressed: () => ref.read(planProvider.notifier).load(),
              ),
            ],
          ),
        ),
        Expanded(
          child: state.isLoading
              ? const Center(child: CircularProgressIndicator())
              : state.plans.isEmpty
                  ? Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.task_alt, size: 48, color: scheme.primary.withAlpha(100)),
                          const SizedBox(height: 12),
                          Text('No active plans', style: TextStyle(color: scheme.onSurfaceVariant)),
                        ],
                      ),
                    )
                  : ListView.builder(
                      padding: const EdgeInsets.all(16),
                      itemCount: state.plans.length,
                      itemBuilder: (context, index) {
                        final plan = state.plans[index];
                        return Padding(
                          padding: const EdgeInsets.only(bottom: 12),
                          child: Column(
                            children: [
                              InkWell(
                                onTap: () {
                                  setState(() {
                                    _expandedPlanId = _expandedPlanId == plan.id ? null : plan.id;
                                  });
                                },
                                child: PlanProgress(
                                  plan: plan,
                                  onResume: () => ref.read(planProvider.notifier).resume(plan.id),
                                ),
                              ),
                              if (_expandedPlanId == plan.id)
                                Padding(
                                  padding: const EdgeInsets.only(left: 16, top: 4),
                                  child: StepStepper(steps: plan.steps),
                                ),
                            ],
                          ),
                        );
                      },
                    ),
        ),
      ],
    );
  }
}
