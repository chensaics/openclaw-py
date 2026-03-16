import 'dart:async';
import 'dart:convert';
import 'package:uuid/uuid.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

/// Error returned by gateway RPC calls.
class GatewayError implements Exception {
  final String code;
  final String message;
  final dynamic details;

  GatewayError(this.code, this.message, [this.details]);

  @override
  String toString() => 'GatewayError($code): $message';
}

/// Connection state for the gateway.
enum GatewayState { disconnected, connecting, connected }

/// WebSocket v3 protocol client for the pyclaw gateway.
class GatewayClient {
  String url;
  String? authToken;
  final String clientName;

  WebSocketChannel? _channel;
  GatewayState _state = GatewayState.disconnected;
  final _uuid = const Uuid();

  final _pending = <String, Completer<Map<String, dynamic>>>{};
  final _eventListeners = <String, List<void Function(dynamic)>>{};
  final _globalListeners = <void Function(String, dynamic)>[];
  final _stateController = StreamController<GatewayState>.broadcast();

  Timer? _heartbeatTimer;
  Timer? _reconnectTimer;
  bool _shouldReconnect = true;
  int _reconnectAttempts = 0;

  static const _heartbeatInterval = Duration(seconds: 30);
  static const _maxReconnectDelay = Duration(seconds: 30);

  GatewayClient({
    this.url = 'ws://127.0.0.1:18789/',
    this.authToken,
    this.clientName = 'pyclaw-flutter',
  });

  GatewayState get state => _state;
  bool get isConnected => _state == GatewayState.connected;
  Stream<GatewayState> get stateStream => _stateController.stream;

  /// Connect to the gateway and perform the v3 handshake.
  Future<void> connect() async {
    if (_state == GatewayState.connected) return;
    _shouldReconnect = true;
    _state = GatewayState.connecting;
    _stateController.add(_state);

    try {
      _channel = WebSocketChannel.connect(Uri.parse(url));
      await _channel!.ready;

      _channel!.stream.listen(
        _onMessage,
        onDone: _onDone,
        onError: (e) => _onDone(),
        cancelOnError: false,
      );

      final connectParams = <String, dynamic>{
        'minProtocol': 1,
        'maxProtocol': 3,
        'clientName': clientName,
      };
      if (authToken != null) {
        connectParams['auth'] = {'token': authToken};
      }

      await call('connect', connectParams);
      _state = GatewayState.connected;
      _stateController.add(_state);
      _reconnectAttempts = 0;
      _startHeartbeat();
    } catch (e) {
      _state = GatewayState.disconnected;
      _stateController.add(_state);
      _scheduleReconnect();
      rethrow;
    }
  }

  /// Disconnect from the gateway.
  Future<void> disconnect() async {
    _shouldReconnect = false;
    _heartbeatTimer?.cancel();
    _reconnectTimer?.cancel();
    await _channel?.sink.close();
    _channel = null;
    _state = GatewayState.disconnected;
    _stateController.add(_state);
    for (final c in _pending.values) {
      if (!c.isCompleted) {
        c.completeError(GatewayError('disconnected', 'Connection closed'));
      }
    }
    _pending.clear();
  }

  /// Send an RPC request and wait for the response.
  Future<Map<String, dynamic>> call(
    String method, [
    Map<String, dynamic>? params,
    Duration timeout = const Duration(seconds: 30),
  ]) async {
    if (_channel == null) {
      throw GatewayError('not_connected', 'Not connected to gateway');
    }

    final reqId = _uuid.v4().substring(0, 12);
    final frame = <String, dynamic>{
      'type': 'req',
      'id': reqId,
      'method': method,
    };
    if (params != null) frame['params'] = params;

    final completer = Completer<Map<String, dynamic>>();
    _pending[reqId] = completer;

    _channel!.sink.add(jsonEncode(frame));

    try {
      return await completer.future.timeout(timeout, onTimeout: () {
        _pending.remove(reqId);
        throw GatewayError('timeout', 'RPC call "$method" timed out');
      });
    } catch (e) {
      _pending.remove(reqId);
      rethrow;
    }
  }

  /// Register a listener for a specific event type.
  void on(String eventName, void Function(dynamic) callback) {
    _eventListeners.putIfAbsent(eventName, () => []).add(callback);
  }

  /// Remove an event listener.
  void off(String eventName, void Function(dynamic) callback) {
    _eventListeners[eventName]?.remove(callback);
  }

  /// Register a listener for all events.
  void onAny(void Function(String, dynamic) callback) {
    _globalListeners.add(callback);
  }

  void _onMessage(dynamic raw) {
    try {
      final data = jsonDecode(raw as String) as Map<String, dynamic>;
      final type = data['type'] as String?;

      if (type == 'res') {
        _handleResponse(data);
      } else if (type == 'event') {
        _handleEvent(data);
      }
    } catch (_) {}
  }

  void _handleResponse(Map<String, dynamic> data) {
    final id = data['id'] as String? ?? '';
    final completer = _pending.remove(id);
    if (completer == null || completer.isCompleted) return;

    if (data['ok'] == true) {
      completer.complete(
        (data['payload'] as Map<String, dynamic>?) ?? {},
      );
    } else {
      final err = data['error'] as Map<String, dynamic>? ?? {};
      completer.completeError(GatewayError(
        err['code'] as String? ?? 'unknown',
        err['message'] as String? ?? 'Unknown error',
        err['details'],
      ));
    }
  }

  void _handleEvent(Map<String, dynamic> data) {
    final eventName = data['event'] as String? ?? '';
    final payload = data['payload'];

    for (final cb in _globalListeners) {
      try {
        cb(eventName, payload);
      } catch (_) {}
    }
    for (final cb in _eventListeners[eventName] ?? []) {
      try {
        cb(payload);
      } catch (_) {}
    }
  }

  void _onDone() {
    _state = GatewayState.disconnected;
    _stateController.add(_state);
    _heartbeatTimer?.cancel();
    if (_shouldReconnect) _scheduleReconnect();
  }

  void _startHeartbeat() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = Timer.periodic(_heartbeatInterval, (_) async {
      if (isConnected) {
        try {
          await call('health', null, const Duration(seconds: 10));
        } catch (_) {}
      }
    });
  }

  void _scheduleReconnect() {
    _reconnectTimer?.cancel();
    final delay = Duration(
      seconds: (1 << _reconnectAttempts).clamp(1, _maxReconnectDelay.inSeconds),
    );
    _reconnectAttempts++;
    _reconnectTimer = Timer(delay, () async {
      if (!_shouldReconnect || isConnected) return;
      try {
        await connect();
      } catch (_) {}
    });
  }

  void dispose() {
    _shouldReconnect = false;
    _heartbeatTimer?.cancel();
    _reconnectTimer?.cancel();
    _channel?.sink.close();
    _stateController.close();
  }

  /// Update endpoint/auth and reconnect if needed.
  Future<void> updateEndpoint({
    required String newUrl,
    String? newAuthToken,
    bool reconnect = true,
  }) async {
    final normalized = newUrl.trim();
    if (normalized.isEmpty) {
      throw GatewayError('invalid_url', 'Gateway URL cannot be empty');
    }

    final shouldReconnectNow = reconnect && (_channel != null || isConnected);
    if (shouldReconnectNow) {
      await disconnect();
    }

    url = normalized;
    authToken = newAuthToken;

    if (reconnect) {
      await connect();
    }
  }
}
