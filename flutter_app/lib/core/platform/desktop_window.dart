import 'dart:io';
import 'package:flutter/foundation.dart';

/// Desktop window configuration applied at startup.
abstract final class DesktopWindow {
  /// Minimum window dimensions for desktop platforms.
  static const minWidth = 800.0;
  static const minHeight = 600.0;

  /// Default window dimensions.
  static const defaultWidth = 1280.0;
  static const defaultHeight = 820.0;

  /// Whether the current platform supports desktop window management.
  static bool get isDesktopPlatform {
    if (kIsWeb) return false;
    return Platform.isMacOS || Platform.isWindows || Platform.isLinux;
  }

  /// Configure the desktop window. Call from main() after ensureInitialized.
  ///
  /// Note: actual window size/title configuration requires platform-specific
  /// native code or packages like `window_manager`. This provides the constants
  /// and detection logic; the native configuration is done in the platform
  /// runner files (macos/Runner, windows/runner, linux/my_application.cc).
  static void configure() {
    if (!isDesktopPlatform) return;
    // Window size constraints are set in the native platform runners.
    // This method exists as a hook for future programmatic control
    // (e.g., restoring saved window position from LocalCache).
    debugPrint('Desktop window configured: ${Platform.operatingSystem}');
  }
}
