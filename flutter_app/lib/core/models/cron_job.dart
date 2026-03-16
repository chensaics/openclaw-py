import 'package:equatable/equatable.dart';

/// Schedule type for a cron job.
enum ScheduleType { cron, every, once }

/// A scheduled task.
class CronJob extends Equatable {
  final String id;
  final String name;
  final ScheduleType scheduleType;
  final String schedule;
  final String prompt;
  final String? channelId;
  final bool enabled;
  final DateTime? lastRun;
  final DateTime? nextRun;

  const CronJob({
    required this.id,
    required this.name,
    required this.scheduleType,
    required this.schedule,
    required this.prompt,
    this.channelId,
    this.enabled = true,
    this.lastRun,
    this.nextRun,
  });

  factory CronJob.fromJson(Map<String, dynamic> json) => CronJob(
        id: json['id'] as String? ?? '',
        name: json['name'] as String? ?? '',
        scheduleType: ScheduleType.values.firstWhere(
          (s) =>
              s.name ==
              (json['scheduleType'] as String? ??
                  json['schedule_type'] as String? ??
                  'cron'),
          orElse: () => ScheduleType.cron,
        ),
        schedule: json['schedule'] as String? ?? '',
        prompt: json['prompt'] as String? ?? json['message'] as String? ?? '',
        channelId:
            json['channelId'] as String? ?? json['channel_id'] as String?,
        enabled: json['enabled'] as bool? ?? true,
        lastRun: (json['lastRun'] ?? json['last_run']) != null
            ? DateTime.tryParse((json['lastRun'] ?? json['last_run']) as String)
            : null,
        nextRun: (json['nextRun'] ?? json['next_run']) != null
            ? DateTime.tryParse((json['nextRun'] ?? json['next_run']) as String)
            : null,
      );

  @override
  List<Object?> get props =>
      [id, name, scheduleType, schedule, prompt, enabled];
}

/// A record of a cron job execution.
class ExecutionRecord extends Equatable {
  final String jobId;
  final DateTime executedAt;
  final bool success;
  final String? output;
  final String? error;
  final Duration? duration;

  const ExecutionRecord({
    required this.jobId,
    required this.executedAt,
    required this.success,
    this.output,
    this.error,
    this.duration,
  });

  factory ExecutionRecord.fromJson(Map<String, dynamic> json) =>
      ExecutionRecord(
        jobId: json['jobId'] as String? ?? json['job_id'] as String? ?? '',
        executedAt: DateTime.tryParse(json['executedAt'] as String? ??
                json['executed_at'] as String? ??
                '') ??
            DateTime.now(),
        success: json['success'] as bool? ?? false,
        output: json['output'] as String?,
        error: json['error'] as String?,
        duration: (json['durationMs'] ?? json['duration_ms']) != null
            ? Duration(
                milliseconds:
                    (json['durationMs'] ?? json['duration_ms']) as int)
            : null,
      );

  @override
  List<Object?> get props => [jobId, executedAt, success];
}
