import 'package:flutter/material.dart';
import 'package:pyclaw/core/models/cron_job.dart';

/// Bottom-sheet form for adding a new cron job.
class CronForm extends StatefulWidget {
  final Future<void> Function(Map<String, dynamic> params) onSubmit;
  const CronForm({super.key, required this.onSubmit});

  @override
  State<CronForm> createState() => _CronFormState();
}

class _CronFormState extends State<CronForm> {
  final _nameCtrl = TextEditingController();
  final _scheduleCtrl = TextEditingController();
  final _promptCtrl = TextEditingController();
  ScheduleType _type = ScheduleType.cron;
  bool _submitting = false;

  @override
  void dispose() {
    _nameCtrl.dispose();
    _scheduleCtrl.dispose();
    _promptCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('New Scheduled Task', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 16),
          TextField(
            controller: _nameCtrl,
            decoration: const InputDecoration(labelText: 'Name', prefixIcon: Icon(Icons.label)),
          ),
          const SizedBox(height: 12),
          SegmentedButton<ScheduleType>(
            segments: const [
              ButtonSegment(value: ScheduleType.cron, label: Text('Cron')),
              ButtonSegment(value: ScheduleType.every, label: Text('Interval')),
              ButtonSegment(value: ScheduleType.once, label: Text('Once')),
            ],
            selected: {_type},
            onSelectionChanged: (s) => setState(() => _type = s.first),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _scheduleCtrl,
            decoration: InputDecoration(
              labelText: _type == ScheduleType.cron
                  ? 'Cron Expression (e.g. 0 9 * * *)'
                  : _type == ScheduleType.every
                      ? 'Interval (e.g. 30m, 2h)'
                      : 'Time (e.g. 2026-03-15T09:00)',
              prefixIcon: const Icon(Icons.timer),
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _promptCtrl,
            maxLines: 3,
            decoration: const InputDecoration(
              labelText: 'Prompt',
              prefixIcon: Icon(Icons.message),
              alignLabelWithHint: true,
            ),
          ),
          const SizedBox(height: 20),
          FilledButton(
            onPressed: _submitting ? null : _submit,
            child: _submitting
                ? const SizedBox(
                    width: 20, height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                  )
                : const Text('Create'),
          ),
        ],
      ),
    );
  }

  Future<void> _submit() async {
    if (_nameCtrl.text.trim().isEmpty || _promptCtrl.text.trim().isEmpty) return;
    setState(() => _submitting = true);
    try {
      await widget.onSubmit({
        'name': _nameCtrl.text.trim(),
        'schedule_type': _type.name,
        'schedule': _scheduleCtrl.text.trim(),
        'prompt': _promptCtrl.text.trim(),
      });
      if (mounted) Navigator.pop(context);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }
}
