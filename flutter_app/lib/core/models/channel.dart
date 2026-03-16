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
        type: json['type'] as String? ?? json['name'] as String? ?? '',
        label: json['label'] as String? ?? json['name'] as String?,
        state: ChannelState.values.firstWhere(
          (s) => s.name == _normalizeState(json),
          orElse: () => ChannelState.offline,
        ),
        messageCount: json['message_count'] as int? ??
            json['messageCount'] as int? ??
            (json['metrics'] is Map
                ? ((json['metrics'] as Map)['message_count'] as int? ?? 0)
                : 0),
        connectedAt: (json['connected_at'] ?? json['connectedAt']) != null
            ? DateTime.tryParse(
                (json['connected_at'] ?? json['connectedAt']) as String)
            : null,
        errorMessage: json['error'] as String?,
      );

  @override
  List<Object?> get props => [id, type, state, messageCount];

  static String _normalizeState(Map<String, dynamic> json) {
    final state = json['state'] as String?;
    if (state != null) {
      if (state == 'running' || state == 'online') return 'online';
      if (state == 'error') return 'error';
      return 'offline';
    }
    final status = json['status'] as String?;
    if (status == 'running') return 'online';
    if (status == 'error') return 'error';
    if ((json['running'] as bool?) == true) return 'online';
    return 'offline';
  }
}
