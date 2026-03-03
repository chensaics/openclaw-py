import 'package:equatable/equatable.dart';

/// A conversation session.
class Session extends Equatable {
  final String id;
  final String title;
  final String? preview;
  final int messageCount;
  final DateTime createdAt;
  final DateTime updatedAt;

  const Session({
    required this.id,
    this.title = '',
    this.preview,
    this.messageCount = 0,
    required this.createdAt,
    required this.updatedAt,
  });

  factory Session.fromJson(Map<String, dynamic> json) => Session(
        id: json['session_id'] as String? ?? json['id'] as String? ?? '',
        title: json['title'] as String? ?? '',
        preview: json['preview'] as String?,
        messageCount: json['message_count'] as int? ?? 0,
        createdAt: DateTime.tryParse(json['created_at'] as String? ?? '') ?? DateTime.now(),
        updatedAt: DateTime.tryParse(json['updated_at'] as String? ?? '') ?? DateTime.now(),
      );

  @override
  List<Object?> get props => [id, title, messageCount, createdAt, updatedAt];
}
