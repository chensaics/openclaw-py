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
        name: json['name'] as String? ?? '',
        systemPrompt: json['system_prompt'] as String?,
        provider: json['provider'] as String? ?? '',
        model: json['model'] as String? ?? '',
        tools: (json['tools'] as List?)?.cast<String>() ?? [],
        isDefault: json['is_default'] as bool? ?? false,
      );

  @override
  List<Object?> get props => [id, name, provider, model, isDefault];
}
