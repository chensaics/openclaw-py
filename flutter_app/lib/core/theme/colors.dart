import 'package:flutter/material.dart';

/// Color tokens that supplement the Material 3 color scheme.
abstract final class AppColors {
  // Accent seeds
  static const indigo = Color(0xFF6366F1);
  static const teal = Color(0xFF14B8A6);
  static const rose = Color(0xFFF43F5E);

  // Status
  static const success = Color(0xFF22C55E);
  static const warning = Color(0xFFF59E0B);
  static const error = Color(0xFFEF4444);
  static const info = Color(0xFF3B82F6);

  // Code block
  static const codeBlockLight = Color(0xFFF5F5F5);
  static const codeBlockDark = Color(0xFF1E1E1E);

  // Role colors for message avatars
  static const userAvatar = Color(0xFF6366F1);
  static const assistantAvatar = Color(0xFF14B8A6);
  static const systemAvatar = Color(0xFF8B5CF6);
  static const toolAvatar = Color(0xFFF59E0B);
}
