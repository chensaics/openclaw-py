import 'package:equatable/equatable.dart';

/// Channel status.
enum ChannelState { online, offline, error }

/// A channel connecting to external platforms.
class Channel extends Equatable {
  final String id;
  final String type;
  final String? label;
  final ChannelState state;
  final int messageCount;
  final DateTime? connectedAt;
  final String? errorMessage;

  const Channel({
    required this.id,
    required this.type,
    this.label,
    this.state = ChannelState.offline,
    this.messageCount = 0,
    this.connectedAt,
    this.errorMessage,
  });

  factory Channel.fromJson(Map<String, dynamic> json) => Channel(
        id: json['id'] as String? ?? '',
        type: json['type'] as String? ?? '',
        label: json['label'] as String?,
        state: ChannelState.values.firstWhere(
          (s) => s.name == (json['state'] as String? ?? 'offline'),
          orElse: () => ChannelState.offline,
        ),
        messageCount: json['message_count'] as int? ?? 0,
        connectedAt: json['connected_at'] != null
            ? DateTime.tryParse(json['connected_at'] as String)
            : null,
        errorMessage: json['error'] as String?,
      );

  @override
  List<Object?> get props => [id, type, state, messageCount];
}
