import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:pyclaw/core/gateway_client.dart';
import 'package:pyclaw/core/models/plan.dart';
import 'package:pyclaw/core/providers/gateway_provider.dart';

class PlanState {
  final List<Plan> plans;
  final bool isLoading;
  final String? error;

  const PlanState({
    this.plans = const [],
    this.isLoading = false,
    this.error,
  });

  PlanState copyWith({
    List<Plan>? plans,
    bool? isLoading,
    String? error,
  }) =>
      PlanState(
        plans: plans ?? this.plans,
        isLoading: isLoading ?? this.isLoading,
        error: error,
      );
}

class PlanNotifier extends StateNotifier<PlanState> {
  final GatewayClient _client;

  PlanNotifier(this._client) : super(const PlanState());

  Future<void> load() async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final result = await _client.call('plan.list');
      final list = (result['plans'] as List?)
              ?.map((p) => Plan.fromJson(p as Map<String, dynamic>))
              .toList() ??
          [];
      state = state.copyWith(plans: list, isLoading: false);
    } catch (e) {
      state = state.copyWith(isLoading: false, error: e.toString());
    }
  }

  Future<Plan?> get(String planId) async {
    try {
      final result = await _client.call('plan.get', {'planId': planId});
      return Plan.fromJson(result);
    } catch (_) {
      return null;
    }
  }

  Future<void> resume(String planId) async {
    try {
      await _client.call('plan.resume', {'planId': planId});
    } catch (e) {
      state = state.copyWith(error: e.toString());
    }
  }

  Future<void> delete(String planId) async {
    try {
      await _client.call('plan.delete', {'planId': planId});
      state = state.copyWith(
        plans: state.plans.where((p) => p.id != planId).toList(),
      );
    } catch (e) {
      state = state.copyWith(error: e.toString());
    }
  }
}

final planProvider = StateNotifierProvider<PlanNotifier, PlanState>((ref) {
  return PlanNotifier(ref.watch(gatewayClientProvider));
});
