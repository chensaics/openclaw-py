import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:pyclaw/app.dart';
import 'package:pyclaw/core/providers/config_provider.dart';
import 'package:pyclaw/core/providers/gateway_provider.dart';
import 'package:pyclaw/core/gateway_client.dart';
import 'package:pyclaw/features/settings/theme_picker.dart';
import 'package:pyclaw/widgets/model_selector.dart';

class SettingsPage extends ConsumerStatefulWidget {
  const SettingsPage({super.key});

  @override
  ConsumerState<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends ConsumerState<SettingsPage> {
  final _gatewayUrlController = TextEditingController(text: 'ws://127.0.0.1:18789/');

  @override
  void initState() {
    super.initState();
    Future.microtask(() => ref.read(configProvider.notifier).load());
  }

  @override
  void dispose() {
    _gatewayUrlController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final config = ref.watch(configProvider);
    final gwState = ref.watch(gatewayProvider);
    final scheme = Theme.of(context).colorScheme;

    return Column(
      children: [
        // Header
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          decoration: BoxDecoration(
            color: scheme.surface,
            border: Border(bottom: BorderSide(color: scheme.outlineVariant, width: 0.5)),
          ),
          child: Row(
            children: [
              Icon(Icons.settings, color: scheme.primary, size: 20),
              const SizedBox(width: 8),
              Text('Settings', style: Theme.of(context).textTheme.titleMedium),
            ],
          ),
        ),

        Expanded(
          child: config.isLoading
              ? const Center(child: CircularProgressIndicator())
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    _sectionTitle(context, 'Connection'),
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          children: [
                            Row(
                              children: [
                                _statusChip(gwState),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: TextField(
                                    controller: _gatewayUrlController,
                                    decoration: const InputDecoration(
                                      labelText: 'Gateway URL',
                                      prefixIcon: Icon(Icons.link),
                                    ),
                                  ),
                                ),
                                const SizedBox(width: 8),
                                FilledButton.tonal(
                                  onPressed: () {
                                    ref.read(gatewayProvider.notifier)
                                        .setUrl(_gatewayUrlController.text);
                                  },
                                  child: const Text('Connect'),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 20),

                    _sectionTitle(context, 'Model'),
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: ModelSelector(
                          models: config.models,
                          selectedModel: config.config['model'] as String?,
                          onChanged: (v) {
                            if (v != null) ref.read(configProvider.notifier).set('model', v);
                          },
                        ),
                      ),
                    ),
                    const SizedBox(height: 20),

                    _sectionTitle(context, 'Appearance'),
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          children: [
                            _themeModeRow(context, ref),
                            const SizedBox(height: 16),
                            const ThemePicker(),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 20),

                    _sectionTitle(context, 'System'),
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            ListTile(
                              leading: const Icon(Icons.info_outline),
                              title: const Text('Version'),
                              subtitle: const Text('0.1.0'),
                              contentPadding: EdgeInsets.zero,
                            ),
                            ListTile(
                              leading: const Icon(Icons.storage),
                              title: const Text('Providers'),
                              subtitle: Text(config.providers.join(', ')),
                              contentPadding: EdgeInsets.zero,
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
        ),
      ],
    );
  }

  Widget _sectionTitle(BuildContext context, String title) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(title, style: Theme.of(context).textTheme.titleSmall),
    );
  }

  Widget _statusChip(GatewayState state) {
    final (color, label) = switch (state) {
      GatewayState.connected => (Colors.green, 'Connected'),
      GatewayState.connecting => (Colors.orange, 'Connecting...'),
      GatewayState.disconnected => (Colors.red, 'Disconnected'),
    };
    return Chip(
      avatar: CircleAvatar(radius: 5, backgroundColor: color),
      label: Text(label, style: const TextStyle(fontSize: 12)),
      visualDensity: VisualDensity.compact,
    );
  }

  Widget _themeModeRow(BuildContext context, WidgetRef ref) {
    final mode = ref.watch(themeModeProvider);
    return SegmentedButton<ThemeMode>(
      segments: const [
        ButtonSegment(value: ThemeMode.system, label: Text('System'), icon: Icon(Icons.brightness_auto)),
        ButtonSegment(value: ThemeMode.light, label: Text('Light'), icon: Icon(Icons.light_mode)),
        ButtonSegment(value: ThemeMode.dark, label: Text('Dark'), icon: Icon(Icons.dark_mode)),
      ],
      selected: {mode},
      onSelectionChanged: (s) => ref.read(themeModeProvider.notifier).state = s.first,
    );
  }
}
