import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:pyclaw/app.dart';
import 'package:pyclaw/core/theme/colors.dart';
import 'package:pyclaw/core/storage/local_cache.dart';

/// A row of seed color swatches for picking the app accent color.
class ThemePicker extends ConsumerWidget {
  const ThemePicker({super.key});

  static const _presets = [
    ('Indigo', AppColors.indigo),
    ('Teal', AppColors.teal),
    ('Rose', AppColors.rose),
    ('Blue', Color(0xFF3B82F6)),
    ('Amber', Color(0xFFF59E0B)),
    ('Green', Color(0xFF22C55E)),
    ('Purple', Color(0xFF8B5CF6)),
    ('Pink', Color(0xFFEC4899)),
  ];

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final currentColor = ref.watch(seedColorProvider);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Seed Color', style: Theme.of(context).textTheme.labelMedium),
        const SizedBox(height: 8),
        Wrap(
          spacing: 10,
          runSpacing: 10,
          children: _presets.map((p) {
            final isSelected = p.$2.value == currentColor.value;
            return Tooltip(
              message: p.$1,
              child: InkWell(
                onTap: () {
                  ref.read(seedColorProvider.notifier).state = p.$2;
                  LocalCache.cacheSeedColor(p.$2.value);
                },
                borderRadius: BorderRadius.circular(20),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  width: 36,
                  height: 36,
                  decoration: BoxDecoration(
                    color: p.$2,
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: isSelected
                          ? Theme.of(context).colorScheme.onSurface
                          : Theme.of(context).colorScheme.outline,
                      width: isSelected ? 3 : 1.5,
                    ),
                    boxShadow: isSelected
                        ? [BoxShadow(color: p.$2.withAlpha(80), blurRadius: 8, spreadRadius: 2)]
                        : null,
                  ),
                  child: isSelected
                      ? const Icon(Icons.check, size: 18, color: Colors.white)
                      : null,
                ),
              ),
            );
          }).toList(),
        ),
      ],
    );
  }
}
