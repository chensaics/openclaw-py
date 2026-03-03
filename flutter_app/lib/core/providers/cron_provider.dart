import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:pyclaw/core/gateway_client.dart';
import 'package:pyclaw/core/models/cron_job.dart';
import 'package:pyclaw/core/providers/gateway_provider.dart';

class CronState {
  final List<CronJob> jobs;
  final List<ExecutionRecord> history;
  final bool isLoading;
  final String? error;

  const CronState({
    this.jobs = const [],
    this.history = const [],
    this.isLoading = false,
    this.error,
  });

  CronState copyWith({
    List<CronJob>? jobs,
    List<ExecutionRecord>? history,
    bool? isLoading,
    String? error,
  }) =>
      CronState(
        jobs: jobs ?? this.jobs,
        history: history ?? this.history,
        isLoading: isLoading ?? this.isLoading,
        error: error,
      );
}

class CronNotifier extends StateNotifier<CronState> {
  final GatewayClient _client;
  Timer? _refreshTimer;

  CronNotifier(this._client) : super(const CronState()) {
    _client.on('cron.executed', _onCronExecuted);
    _startAutoRefresh();
  }

  void _startAutoRefresh() {
    _refreshTimer = Timer.periodic(const Duration(seconds: 60), (_) {
      if (_client.isConnected) load();
    });
  }

  Future<void> load() async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final result = await _client.call('cron.list');
      final jobs = (result['jobs'] as List?)
              ?.map((j) => CronJob.fromJson(j as Map<String, dynamic>))
              .toList() ??
          [];
      state = state.copyWith(jobs: jobs, isLoading: false);
    } catch (e) {
      state = state.copyWith(isLoading: false, error: e.toString());
    }
  }

  Future<void> loadHistory(String jobId) async {
    try {
      final result = await _client.call('cron.history', {'job_id': jobId});
      final records = (result['records'] as List?)
              ?.map((r) => ExecutionRecord.fromJson(r as Map<String, dynamic>))
              .toList() ??
          [];
      state = state.copyWith(history: records);
    } catch (e) {
      state = state.copyWith(error: e.toString());
    }
  }

  Future<void> add(Map<String, dynamic> params) async {
    try {
      await _client.call('cron.add', params);
      await load();
    } catch (e) {
      state = state.copyWith(error: e.toString());
    }
  }

  Future<void> remove(String jobId) async {
    final previous = state.jobs;
    state = state.copyWith(
      jobs: state.jobs.where((j) => j.id != jobId).toList(),
    );
    try {
      await _client.call('cron.remove', {'job_id': jobId});
    } catch (e) {
      state = state.copyWith(jobs: previous, error: e.toString());
    }
  }

  void _onCronExecuted(dynamic payload) {
    if (payload is Map) {
      final record = ExecutionRecord.fromJson(payload.cast<String, dynamic>());
      state = state.copyWith(history: [record, ...state.history]);
    }
    load();
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    _client.off('cron.executed', _onCronExecuted);
    super.dispose();
  }
}

final cronProvider = StateNotifierProvider<CronNotifier, CronState>((ref) {
  return CronNotifier(ref.watch(gatewayClientProvider));
});
