import 'package:flutter/material.dart';
import 'package:flutter_math_fork/flutter_math.dart';

/// Renders inline and block LaTeX formulas from markdown-style delimiters.
///
/// Supports:
/// - `$...$` for inline math
/// - `$$...$$` for block math
/// - `\(...\)` for inline math (alternative)
/// - `\[...\]` for block math (alternative)
class LatexText extends StatelessWidget {
  final String text;
  final TextStyle? style;

  const LatexText({super.key, required this.text, this.style});

  static final _blockPattern = RegExp(r'\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\]');
  static final _inlinePattern = RegExp(r'\$(.+?)\$|\\\((.+?)\\\)');

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;

    if (!_containsLatex(text)) {
      return SelectableText(text, style: style);
    }

    final segments = _parseSegments(text);

    return Wrap(
      crossAxisAlignment: WrapCrossAlignment.center,
      children: segments.map((seg) {
        if (seg.isBlock) {
          return Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(vertical: 8),
            alignment: Alignment.center,
            child: Math.tex(
              seg.content,
              textStyle: style?.copyWith(fontSize: (style?.fontSize ?? 14) + 2),
              mathStyle: MathStyle.display,
              onErrorFallback: (err) => Text(
                seg.content,
                style: TextStyle(color: scheme.error, fontFamily: 'monospace'),
              ),
            ),
          );
        }
        if (seg.isInline) {
          return Math.tex(
            seg.content,
            textStyle: style,
            mathStyle: MathStyle.text,
            onErrorFallback: (err) => Text(
              seg.content,
              style: TextStyle(color: scheme.error, fontFamily: 'monospace'),
            ),
          );
        }
        return Text(seg.content, style: style);
      }).toList(),
    );
  }

  bool _containsLatex(String s) =>
      s.contains(r'$') || s.contains(r'\(') || s.contains(r'\[');

  List<_Segment> _parseSegments(String input) {
    final segments = <_Segment>[];
    var remaining = input;

    while (remaining.isNotEmpty) {
      final blockMatch = _blockPattern.firstMatch(remaining);
      final inlineMatch = _inlinePattern.firstMatch(remaining);

      Match? firstMatch;
      bool isBlock = false;

      if (blockMatch != null && inlineMatch != null) {
        if (blockMatch.start <= inlineMatch.start) {
          firstMatch = blockMatch;
          isBlock = true;
        } else {
          firstMatch = inlineMatch;
        }
      } else if (blockMatch != null) {
        firstMatch = blockMatch;
        isBlock = true;
      } else if (inlineMatch != null) {
        firstMatch = inlineMatch;
      }

      if (firstMatch == null) {
        if (remaining.isNotEmpty) segments.add(_Segment(remaining));
        break;
      }

      if (firstMatch.start > 0) {
        segments.add(_Segment(remaining.substring(0, firstMatch.start)));
      }

      final latex = firstMatch.group(1) ?? firstMatch.group(2) ?? '';
      segments.add(isBlock ? _Segment.block(latex) : _Segment.inline(latex));
      remaining = remaining.substring(firstMatch.end);
    }

    return segments;
  }
}

class _Segment {
  final String content;
  final bool isInline;
  final bool isBlock;

  _Segment(this.content) : isInline = false, isBlock = false;
  _Segment.inline(this.content) : isInline = true, isBlock = false;
  _Segment.block(this.content) : isInline = false, isBlock = true;
}
