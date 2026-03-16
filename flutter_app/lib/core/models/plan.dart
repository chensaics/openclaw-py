import 'package:equatable/equatable.dart';

/// Status of a plan step.
enum StepStatus { pending, running, done, failed, skipped }

/// A step within a plan.
class PlanStep extends Equatable {
  final int index;
  final String description;
  final StepStatus status;
  final String? result;

  const PlanStep({
    required this.index,
    required this.description,
    this.status = StepStatus.pending,
    this.result,
  });

  factory PlanStep.fromJson(Map<String, dynamic> json) => PlanStep(
        index: json['index'] as int? ?? 0,
        description: json['description'] as String? ?? '',
        status: StepStatus.values.firstWhere(
          (s) => s.name == (json['status'] as String? ?? 'pending'),
          orElse: () => StepStatus.pending,
        ),
        result: json['result'] as String?,
      );

  @override
  List<Object?> get props => [index, description, status, result];
}

/// A task plan with decomposed steps.
class Plan extends Equatable {
  final String id;
  final String goal;
  final List<PlanStep> steps;
  final DateTime createdAt;

  const Plan({
    required this.id,
    required this.goal,
    this.steps = const [],
    required this.createdAt,
  });

  int get completedCount =>
      steps.where((s) => s.status == StepStatus.done).length;
  int get totalCount => steps.length;
  double get progress => totalCount > 0 ? completedCount / totalCount : 0;

  factory Plan.fromJson(Map<String, dynamic> json) => Plan(
        id: json['id'] as String? ?? '',
        goal: json['goal'] as String? ?? '',
        steps: (json['steps'] as List?)
                ?.map((s) => PlanStep.fromJson(s as Map<String, dynamic>))
                .toList() ??
            [],
        createdAt: DateTime.tryParse(json['createdAt'] as String? ??
                json['created_at'] as String? ??
                '') ??
            DateTime.now(),
      );

  @override
  List<Object?> get props => [id, goal, steps, createdAt];
}
