import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Typography tokens for the application.
abstract final class AppTypography {
  /// Code font family used in code blocks and inline code.
  static TextStyle codeStyle({double fontSize = 13, Color? color}) {
    return GoogleFonts.jetBrainsMono(
      fontSize: fontSize,
      height: 1.5,
      color: color,
    );
  }

  /// Monospace text style for system output.
  static TextStyle monoStyle({double fontSize = 12, Color? color}) {
    return GoogleFonts.jetBrainsMono(
      fontSize: fontSize,
      height: 1.6,
      color: color,
    );
  }

  /// Body text with CJK support (Inter + Noto Sans SC via Google Fonts).
  static TextStyle bodyText({
    double fontSize = 14,
    FontWeight fontWeight = FontWeight.normal,
    Color? color,
  }) {
    return GoogleFonts.inter(
      fontSize: fontSize,
      fontWeight: fontWeight,
      height: 1.6,
      color: color,
    );
  }
}
