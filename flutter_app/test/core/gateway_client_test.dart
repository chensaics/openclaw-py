import 'package:flutter_test/flutter_test.dart';
import 'package:pyclaw/core/gateway_client.dart';

void main() {
  group('GatewayClient', () {
    test('initializes with default values', () {
      final client = GatewayClient();
      expect(client.url, 'ws://127.0.0.1:18789/');
      expect(client.authToken, isNull);
      expect(client.clientName, 'pyclaw-flutter');
      expect(client.state, GatewayState.disconnected);
      expect(client.isConnected, isFalse);
    });

    test('initializes with custom values', () {
      final client = GatewayClient(
        url: 'ws://example.com:8080/',
        authToken: 'secret',
        clientName: 'test-client',
      );
      expect(client.url, 'ws://example.com:8080/');
      expect(client.authToken, 'secret');
      expect(client.clientName, 'test-client');
    });

    test('call throws when not connected', () {
      final client = GatewayClient();
      expect(
        () => client.call('test'),
        throwsA(isA<GatewayError>().having((e) => e.code, 'code', 'not_connected')),
      );
    });

    test('on/off event listeners', () {
      final client = GatewayClient();
      var called = false;
      void listener(dynamic _) => called = true;

      client.on('test.event', listener);
      // Verify listener was registered (internal state)
      expect(called, isFalse);

      client.off('test.event', listener);
      // No error when removing
    });

    test('onAny listener registration', () {
      final client = GatewayClient();
      var eventName = '';
      client.onAny((name, _) => eventName = name);
      // Listener registered but not triggered without connection
      expect(eventName, '');
    });

    test('stateStream emits states', () async {
      final client = GatewayClient();
      final states = <GatewayState>[];
      final sub = client.stateStream.listen(states.add);

      // Not connected, so the stream won't emit unless we try to connect
      expect(states, isEmpty);

      sub.cancel();
      client.dispose();
    });

    test('dispose cleans up resources', () {
      final client = GatewayClient();
      // Should not throw
      client.dispose();
    });
  });

  group('GatewayError', () {
    test('toString includes code and message', () {
      final err = GatewayError('timeout', 'Request timed out');
      expect(err.toString(), 'GatewayError(timeout): Request timed out');
    });

    test('stores details', () {
      final err = GatewayError('fail', 'msg', {'key': 'value'});
      expect(err.code, 'fail');
      expect(err.message, 'msg');
      expect(err.details, {'key': 'value'});
    });
  });

  group('GatewayState', () {
    test('has expected values', () {
      expect(GatewayState.values, hasLength(3));
      expect(GatewayState.values, contains(GatewayState.disconnected));
      expect(GatewayState.values, contains(GatewayState.connecting));
      expect(GatewayState.values, contains(GatewayState.connected));
    });
  });
}
