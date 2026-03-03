import 'package:flutter_test/flutter_test.dart';
import 'package:pyclaw/core/storage/local_cache.dart';

void main() {
  group('LocalCache', () {
    test('getCachedSessions returns null before init', () {
      // Before Hive init, the getter should handle null gracefully
      // (In real usage, init() is called before any access)
      expect(LocalCache.getCachedSessions(), isNull);
    });

    test('getCachedConfig returns null before init', () {
      expect(LocalCache.getCachedConfig(), isNull);
    });

    test('getCachedGatewayUrl returns null before init', () {
      expect(LocalCache.getCachedGatewayUrl(), isNull);
    });

    test('getCachedThemeMode returns null before init', () {
      expect(LocalCache.getCachedThemeMode(), isNull);
    });

    test('getCachedSeedColor returns null before init', () {
      expect(LocalCache.getCachedSeedColor(), isNull);
    });
  });
}
