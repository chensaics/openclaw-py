import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:pyclaw/core/gateway_client.dart';
import 'package:pyclaw/core/models/session.dart';
import 'package:pyclaw/core/providers/gateway_provider.dart';
import 'package:pyclaw/core/storage/local_cache.dart';

class SessionState {
  final List<Session> sessions;
  final bool isLoading;
  final String? error;

  const SessionState({
    this.sessions = const [],
    this.isLoading = false,
    this.error,
  });

  SessionState copyWith({
    List<Session>? sessions,
    bool? isLoading,
    String? error,
  }) =>
      SessionState(
        sessions: sessions ?? this.sessions,
        isLoading: isLoading ?? this.isLoading,
        error: error,
      );
}

class SessionNotifier extends StateNotifier<SessionState> {
  final GatewayClient _client;

  SessionNotifier(this._client) : super(const SessionState()) {
    _loadFromCache();
  }

  void _loadFromCache() {
    final cached = LocalCache.getCachedSessions();
    if (cached != null) {
      final list = cached.map((s) => Session.fromJson(s)).toList();
      list.sort((a, b) => b.updatedAt.compareTo(a.updatedAt));
      state = state.copyWith(sessions: list);
    }
  }

  Future<void> load() async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final result = await _client.call('sessions.list');
      final rawList = (result['sessions'] as List?) ?? [];
      final list = rawList
          .map((s) => Session.fromJson(s as Map<String, dynamic>))
          .toList();
      list.sort((a, b) => b.updatedAt.compareTo(a.updatedAt));
      state = state.copyWith(sessions: list, isLoading: false);

      LocalCache.cacheSessions(rawList.cast<Map<String, dynamic>>());
    } catch (e) {
      state = state.copyWith(isLoading: false, error: e.toString());
    }
  }

  /// Optimistic delete: remove from UI immediately, rollback on failure.
  Future<void> delete(String sessionId) async {
    final previous = state.sessions;
    state = state.copyWith(
      sessions: state.sessions.where((s) => s.id != sessionId).toList(),
    );
    try {
      await _client.call('sessions.delete', {'session_id': sessionId});
    } catch (e) {
      state = state.copyWith(sessions: previous, error: e.toString());
    }
  }

  Future<void> reset(String sessionId) async {
    try {
      await _client.call('sessions.reset', {'session_id': sessionId});
      await load();
    } catch (e) {
      state = state.copyWith(error: e.toString());
    }
  }
}

final sessionProvider =
    StateNotifierProvider<SessionNotifier, SessionState>((ref) {
  return SessionNotifier(ref.watch(gatewayClientProvider));
});
