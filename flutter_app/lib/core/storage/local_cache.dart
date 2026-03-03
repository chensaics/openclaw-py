import 'dart:convert';
import 'package:hive_flutter/hive_flutter.dart';

/// Local key-value cache backed by Hive for offline persistence.
class LocalCache {
  static const _boxName = 'pyclaw_cache';
  static Box? _box;

  static Future<void> init() async {
    await Hive.initFlutter();
    _box = await Hive.openBox(_boxName);
  }

  static Box get _store {
    assert(_box != null, 'LocalCache.init() must be called first');
    return _box!;
  }

  /// Store a JSON-serializable value.
  static Future<void> put(String key, dynamic value) async {
    await _store.put(key, jsonEncode(value));
  }

  /// Retrieve a stored value, or null if not found.
  static T? get<T>(String key) {
    final raw = _store.get(key);
    if (raw == null) return null;
    try {
      return jsonDecode(raw as String) as T;
    } catch (_) {
      return null;
    }
  }

  /// Remove a cached entry.
  static Future<void> remove(String key) async {
    await _store.delete(key);
  }

  /// Clear all cached data.
  static Future<void> clear() async {
    await _store.clear();
  }

  /// Cache a list of session snapshots.
  static Future<void> cacheSessions(List<Map<String, dynamic>> sessions) async {
    await put('sessions', sessions);
  }

  /// Get cached sessions for offline display.
  static List<Map<String, dynamic>>? getCachedSessions() {
    final data = get<List>('sessions');
    return data?.cast<Map<String, dynamic>>();
  }

  /// Cache config for offline access.
  static Future<void> cacheConfig(Map<String, dynamic> config) async {
    await put('config', config);
  }

  static Map<String, dynamic>? getCachedConfig() {
    return get<Map<String, dynamic>>('config');
  }

  /// Cache the last used gateway URL.
  static Future<void> cacheGatewayUrl(String url) async {
    await put('gateway_url', url);
  }

  static String? getCachedGatewayUrl() {
    return get<String>('gateway_url');
  }

  /// Cache theme preferences.
  static Future<void> cacheThemeMode(String mode) async {
    await put('theme_mode', mode);
  }

  static String? getCachedThemeMode() {
    return get<String>('theme_mode');
  }

  static Future<void> cacheSeedColor(int colorValue) async {
    await put('seed_color', colorValue);
  }

  static int? getCachedSeedColor() {
    return get<int>('seed_color');
  }
}
