import 'package:equatable/equatable.dart';

/// A conversation session.
class Session extends Equatable {
  final String id;
  final String title;
  final String? preview;
  final String? path;
  final String? agentId;
  final String? file;
  final int messageCount;
  final DateTime createdAt;
  final DateTime updatedAt;

  const Session({
    required this.id,
    this.title = '',
    this.preview,
    this.path,
    this.agentId,
    this.file,
    this.messageCount = 0,
    required this.createdAt,
    required this.updatedAt,
  });

  factory Session.fromJson(Map<String, dynamic> json) {
    final path = json['path'] as String?;
    final file = json['file'] as String?;
    final rawId = json['session_id'] as String? ??
        json['sessionId'] as String? ??
        json['id'] as String?;
    final fallbackFromFile = (file ?? '').replaceAll('.jsonl', '');
    final fallbackFromPath =
        path != null ? path.split('/').last.replaceAll('.jsonl', '') : '';
    final id = (rawId != null && rawId.isNotEmpty)
        ? rawId
        : (fallbackFromFile.isNotEmpty ? fallbackFromFile : fallbackFromPath);

    final title = (json['title'] as String?)?.trim();
    return Session(
      id: id,
      title: (title == null || title.isEmpty) ? id : title,
      preview: json['preview'] as String?,
      path: path,
      agentId: json['agentId'] as String? ?? json['agent_id'] as String?,
      file: file,
      messageCount:
          json['message_count'] as int? ?? json['messageCount'] as int? ?? 0,
      createdAt: DateTime.tryParse(json['created_at'] as String? ?? '') ??
          DateTime.tryParse(json['createdAt'] as String? ?? '') ??
          DateTime.now(),
      updatedAt: DateTime.tryParse(json['updated_at'] as String? ?? '') ??
          DateTime.tryParse(json['updatedAt'] as String? ?? '') ??
          DateTime.now(),
    );
  }

  @override
  List<Object?> get props => [id, title, messageCount, createdAt, updatedAt];
}
