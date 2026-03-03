import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:pyclaw/core/gateway_client.dart';
import 'package:pyclaw/core/providers/gateway_provider.dart';

class SystemState {
  final Map<String, dynamic> info;
  final List<Map<String, dynamic>> doctorChecks;
  final bool isLoading;
  final String? error;

  const SystemState({
    this.info = const {},
    this.doctorChecks = const [],
    this.isLoading = false,
    this.error,
  });

  SystemState copyWith({
    Map<String, dynamic>? info,
    List<Map<String, dynamic>>? doctorChecks,
    bool? isLoading,
    String? error,
  }) =>
      SystemState(
        info: info ?? this.info,
        doctorChecks: doctorChecks ?? this.doctorChecks,
        isLoading: isLoading ?? this.isLoading,
        error: error,
      );
}

class SystemNotifier extends StateNotifier<SystemState> {
  final GatewayClient _client;
  Timer? _refreshTimer;

  SystemNotifier(this._client) : super(const SystemState()) {
    _startAutoRefresh();
  }

  void _startAutoRefresh() {
    _refreshTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      if (_client.isConnected) loadInfo();
    });
  }

  Future<void> loadInfo() async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final result = await _client.call('system.info');
      state = state.copyWith(info: result, isLoading: false);
    } catch (e) {
      state = state.copyWith(isLoading: false, error: e.toString());
    }
  }

  Future<void> runDoctor() async {
    try {
      final result = await _client.call('doctor.run');
      final checks = (result['checks'] as List?)
              ?.cast<Map<String, dynamic>>() ??
          [];
      state = state.copyWith(doctorChecks: checks);
    } catch (e) {
      state = state.copyWith(error: e.toString());
    }
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    super.dispose();
  }
}

final systemProvider =
    StateNotifierProvider<SystemNotifier, SystemState>((ref) {
  return SystemNotifier(ref.watch(gatewayClientProvider));
});
