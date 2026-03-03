import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:pyclaw/core/gateway_client.dart';

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
    await _client.disconnect();
    // Note: in a real implementation you'd recreate the client;
    // for now we reconnect to the existing URL.
    await _client.connect();
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
