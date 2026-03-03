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
    return DropdownButtonFormField<String>(
      value: selectedModel,
      decoration: const InputDecoration(
        labelText: 'Model',
        prefixIcon: Icon(Icons.psychology),
      ),
      items: models.map((m) {
        final id = m['id'] as String? ?? m['model'] as String? ?? '';
        final label = m['label'] as String? ?? id;
        return DropdownMenuItem(value: id, child: Text(label));
      }).toList(),
      onChanged: onChanged,
    );
  }
}
