import 'package:flutter/material.dart';

/// Dropdown for selecting a model from the provider list.
class ModelSelector extends StatelessWidget {
  final List<Map<String, dynamic>> models;
  final String? selectedModel;
  final ValueChanged<String?> onChanged;

  const ModelSelector({
    super.key,
    required this.models,
    this.selectedModel,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final ids = models
        .map((m) =>
            m['model_id'] as String? ??
            m['id'] as String? ??
            m['model'] as String? ??
            '')
        .where((id) => id.isNotEmpty)
        .toSet();
    final effectiveSelected =
        (selectedModel != null && ids.contains(selectedModel))
            ? selectedModel
            : null;

    return DropdownButtonFormField<String>(
      value: effectiveSelected,
      decoration: const InputDecoration(
        labelText: 'Model',
        prefixIcon: Icon(Icons.psychology),
      ),
      items: models.map((m) {
        final id = m['model_id'] as String? ??
            m['id'] as String? ??
            m['model'] as String? ??
            '';
        final provider = m['provider'] as String? ?? '';
        final label = m['display_name'] as String? ??
            m['label'] as String? ??
            (provider.isNotEmpty ? '$provider/$id' : id);
        return DropdownMenuItem(value: id, child: Text(label));
      }).toList(),
      onChanged: onChanged,
    );
  }
}
