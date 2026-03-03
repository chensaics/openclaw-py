import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:pyclaw/core/gateway_client.dart';
import 'package:pyclaw/core/providers/gateway_provider.dart';

class ConfigState {
  final Map<String, dynamic> config;
  final List<Map<String, dynamic>> models;
  final List<String> providers;
  final bool isLoading;

  const ConfigState({
    this.config = const {},
    this.models = const [],
    this.providers = const [],
    this.isLoading = false,
  });

  ConfigState copyWith({
    Map<String, dynamic>? config,
    List<Map<String, dynamic>>? models,
    List<String>? providers,
    bool? isLoading,
  }) =>
      ConfigState(
        config: config ?? this.config,
        models: models ?? this.models,
        providers: providers ?? this.providers,
        isLoading: isLoading ?? this.isLoading,
      );
}

class ConfigNotifier extends StateNotifier<ConfigState> {
  final GatewayClient _client;

  ConfigNotifier(this._client) : super(const ConfigState());

  Future<void> load() async {
    state = state.copyWith(isLoading: true);
    try {
      final configRes = await _client.call('config.get');
      final config = configRes['config'] as Map<String, dynamic>? ?? {};

      List<Map<String, dynamic>> models = [];
      List<String> providers = [];
      try {
        final modelsRes = await _client.call('models.list');
        models = (modelsRes['models'] as List?)
                ?.cast<Map<String, dynamic>>() ??
            [];
      } catch (_) {}
      try {
        final providersRes = await _client.call('models.providers');
        providers = (providersRes['providers'] as List?)?.cast<String>() ?? [];
      } catch (_) {}

      state = state.copyWith(
        config: config,
        models: models,
        providers: providers,
        isLoading: false,
      );
    } catch (_) {
      state = state.copyWith(isLoading: false);
    }
  }

  Future<void> patch(Map<String, dynamic> updates) async {
    try {
      await _client.call('config.patch', updates);
      final merged = {...state.config, ...updates};
      state = state.copyWith(config: merged);
    } catch (_) {}
  }

  Future<void> set(String key, dynamic value) async {
    try {
      await _client.call('config.set', {'key': key, 'value': value});
      final updated = {...state.config, key: value};
      state = state.copyWith(config: updated);
    } catch (_) {}
  }
}

final configProvider =
    StateNotifierProvider<ConfigNotifier, ConfigState>((ref) {
  return ConfigNotifier(ref.watch(gatewayClientProvider));
});
