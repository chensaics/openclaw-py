import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:pyclaw/core/gateway_client.dart';
import 'package:pyclaw/core/storage/local_cache.dart';

/// Global gateway client singleton.
final gatewayClientProvider = Provider<GatewayClient>((ref) {
  final client = GatewayClient();
  ref.onDispose(() => client.dispose());
  return client;
});

/// Manages gateway connection lifecycle.
class GatewayNotifier extends StateNotifier<GatewayState> {
  final GatewayClient _client;
  StreamSubscription<GatewayState>? _sub;

  GatewayNotifier(this._client) : super(GatewayState.disconnected) {
    _sub = _client.stateStream.listen((s) => state = s);
    final cachedUrl = LocalCache.getCachedGatewayUrl();
    if (cachedUrl != null && cachedUrl.trim().isNotEmpty) {
      _client.url = cachedUrl.trim();
    }
  }

  Future<void> connect() async {
    try {
      await _client.connect();
    } catch (_) {
      // reconnect is handled internally by the client
    }
  }

  Future<void> disconnect() => _client.disconnect();

  /// Update the gateway URL and reconnect.
  Future<void> setUrl(String url) async {
    await _client.updateEndpoint(newUrl: url, reconnect: true);
    await LocalCache.cacheGatewayUrl(_client.url);
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }
}

final gatewayProvider =
    StateNotifierProvider<GatewayNotifier, GatewayState>((ref) {
  return GatewayNotifier(ref.watch(gatewayClientProvider));
});
