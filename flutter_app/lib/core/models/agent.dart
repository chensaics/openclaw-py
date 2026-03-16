import 'package:equatable/equatable.dart';

/// Agent configuration.
class Agent extends Equatable {
  final String id;
  final String name;
  final String? systemPrompt;
  final String provider;
  final String model;
  final List<String> tools;
  final bool isDefault;

  const Agent({
    required this.id,
    required this.name,
    this.systemPrompt,
    this.provider = '',
    this.model = '',
    this.tools = const [],
    this.isDefault = false,
  });

  factory Agent.fromJson(Map<String, dynamic> json) => Agent(
        id: json['id'] as String? ?? json['name'] as String? ?? '',
        name: json['name'] as String? ?? json['id'] as String? ?? '',
        systemPrompt: json['systemPrompt'] as String? ??
            json['system_prompt'] as String? ??
            (json['config'] is Map
                ? (json['config'] as Map)['systemPrompt'] as String?
                : null),
        provider: json['provider'] as String? ??
            (json['config'] is Map
                ? (json['config'] as Map)['provider'] as String?
                : null) ??
            '',
        model: json['model'] as String? ??
            (json['config'] is Map
                ? (json['config'] as Map)['model'] as String?
                : null) ??
            '',
        tools: (json['tools'] as List?)?.cast<String>() ??
            (json['config'] is Map && (json['config'] as Map)['tools'] is List
                ? ((json['config'] as Map)['tools'] as List).cast<String>()
                : const []),
        isDefault:
            json['isDefault'] as bool? ?? json['is_default'] as bool? ?? false,
      );

  @override
  List<Object?> get props => [id, name, provider, model, isDefault];
}
