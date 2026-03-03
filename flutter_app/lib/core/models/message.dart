import 'package:equatable/equatable.dart';

/// Role of a message in the conversation.
enum MessageRole { user, assistant, system, tool }

/// A tool invocation within a message.
class ToolCall extends Equatable {
  final String id;
  final String name;
  final String arguments;
  final String? result;
  final String? error;
  final bool isRunning;
  final DateTime? startedAt;
  final DateTime? finishedAt;

  const ToolCall({
    required this.id,
    required this.name,
    this.arguments = '',
    this.result,
    this.error,
    this.isRunning = false,
    this.startedAt,
    this.finishedAt,
  });

  ToolCall copyWith({
    String? result,
    String? error,
    bool? isRunning,
    DateTime? finishedAt,
  }) {
    return ToolCall(
      id: id,
      name: name,
      arguments: arguments,
      result: result ?? this.result,
      error: error ?? this.error,
      isRunning: isRunning ?? this.isRunning,
      startedAt: startedAt,
      finishedAt: finishedAt ?? this.finishedAt,
    );
  }

  factory ToolCall.fromJson(Map<String, dynamic> json) => ToolCall(
        id: json['id'] as String? ?? '',
        name: json['name'] as String? ?? '',
        arguments: json['arguments'] as String? ?? '',
        result: json['result'] as String?,
        error: json['error'] as String?,
        isRunning: json['is_running'] as bool? ?? false,
      );

  @override
  List<Object?> get props => [id, name, arguments, result, error, isRunning];
}

/// A timeline activity embedded in a message.
class TimelineEntry extends Equatable {
  final String type;
  final String label;
  final DateTime timestamp;
  final Map<String, dynamic> data;

  const TimelineEntry({
    required this.type,
    required this.label,
    required this.timestamp,
    this.data = const {},
  });

  factory TimelineEntry.fromJson(Map<String, dynamic> json) => TimelineEntry(
        type: json['type'] as String? ?? '',
        label: json['label'] as String? ?? '',
        timestamp: DateTime.tryParse(json['ts'] as String? ?? '') ?? DateTime.now(),
        data: json['data'] as Map<String, dynamic>? ?? {},
      );

  @override
  List<Object?> get props => [type, label, timestamp];
}

/// A chat message.
class Message extends Equatable {
  final String id;
  final MessageRole role;
  final String content;
  final List<ToolCall> toolCalls;
  final List<TimelineEntry> timeline;
  final DateTime createdAt;
  final bool isStreaming;

  const Message({
    required this.id,
    required this.role,
    this.content = '',
    this.toolCalls = const [],
    this.timeline = const [],
    required this.createdAt,
    this.isStreaming = false,
  });

  Message copyWith({
    String? content,
    List<ToolCall>? toolCalls,
    List<TimelineEntry>? timeline,
    bool? isStreaming,
  }) {
    return Message(
      id: id,
      role: role,
      content: content ?? this.content,
      toolCalls: toolCalls ?? this.toolCalls,
      timeline: timeline ?? this.timeline,
      createdAt: createdAt,
      isStreaming: isStreaming ?? this.isStreaming,
    );
  }

  factory Message.fromJson(Map<String, dynamic> json) {
    final roleStr = json['role'] as String? ?? 'assistant';
    final role = MessageRole.values.firstWhere(
      (r) => r.name == roleStr,
      orElse: () => MessageRole.assistant,
    );
    return Message(
      id: json['id'] as String? ?? '',
      role: role,
      content: json['content'] as String? ?? '',
      toolCalls: (json['tool_calls'] as List?)
              ?.map((t) => ToolCall.fromJson(t as Map<String, dynamic>))
              .toList() ??
          [],
      timeline: (json['timeline'] as List?)
              ?.map((t) => TimelineEntry.fromJson(t as Map<String, dynamic>))
              .toList() ??
          [],
      createdAt: DateTime.tryParse(json['created_at'] as String? ?? '') ?? DateTime.now(),
      isStreaming: false,
    );
  }

  @override
  List<Object?> get props => [id, role, content, toolCalls, timeline, createdAt, isStreaming];
}
